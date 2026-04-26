from __future__ import annotations

"""Generic OSS runtime path for all use cases.

This module executes the OSS golden path for any configured use case:
1) publish source entities directly to Kafka topics
2) consume topic values back into the pipeline
3) build raw + curated artifacts from consumed events
4) persist curated rows to Postgres
5) upload raw/curated snapshots to MinIO

If OSS infra is unavailable, caller receives `fallback_local` status and can
continue with local adapters.
"""

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from stack.compose_utils import compose_cmd, detect_compose_command
from stack.layers.ingestion_event_bus import LocalEventBus
from stack.layers.storage import build_raw_and_curated_storage

KAFKA_BIN = "/opt/kafka/bin"


def run_oss_golden_path(
    *,
    compose_file: Path,
    run_dir: Path,
    run_id: str,
    use_case_id: str,
    source_tables: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Run use-case data flow on OSS infra and return artifacts + status report."""
    report: dict[str, Any] = {
        "status": "fallback_local",
        "compose_file": str(compose_file),
        "warnings": [],
        "kafka_topics_published": 0,
        "kafka_messages_consumed": 0,
        "postgres_rows_loaded": 0,
        "minio_objects_uploaded": 0,
    }

    if not source_tables:
        report["warnings"].append("No source tables available for OSS execution.")
        return report

    if not compose_file.exists():
        report["warnings"].append(f"Compose file not found: {compose_file}")
        return report

    try:
        detect_compose_command()
    except RuntimeError as exc:
        report["warnings"].append(f"{exc} Using local fallback.")
        return report

    running = _running_services(compose_file=compose_file)
    required = {"kafka", "postgres", "minio", "mc"}
    missing = sorted(required - running)
    if missing:
        report["warnings"].append(
            f"OSS profile services not running: {missing}. Using local fallback."
        )
        return report

    ready, reason = _wait_for_oss_readiness(compose_file=compose_file, timeout_seconds=90)
    if not ready:
        report["warnings"].append(f"OSS services not ready: {reason}. Using local fallback.")
        return report

    try:
        topic_rows = _publish_source_tables_to_kafka(
            compose_file=compose_file,
            use_case_id=use_case_id,
            run_id=run_id,
            source_tables=source_tables,
        )
        consumed_rows = _consume_source_tables_from_kafka(
            compose_file=compose_file,
            topic_rows=topic_rows,
        )
        bus = _build_event_bus_from_consumed_rows(consumed_rows)
        ingestion_paths = _write_ingestion_artifacts(bus=bus, run_dir=run_dir)
        curated_rows, storage_paths = build_raw_and_curated_storage(
            use_case_id=use_case_id,
            bus=bus,
            output_dir=run_dir,
        )
        postgres_rows_loaded = _load_curated_into_postgres(
            compose_file=compose_file,
            use_case_id=use_case_id,
            run_id=run_id,
            curated_records_jsonl_path=Path(storage_paths["curated_records_jsonl"]),
        )
        minio_uploaded = _upload_artifacts_to_minio(
            compose_file=compose_file,
            use_case_id=use_case_id,
            run_id=run_id,
            raw_events_path=Path(storage_paths["raw_events"]),
            curated_records_jsonl_path=Path(storage_paths["curated_records_jsonl"]),
        )
    except Exception as exc:  # noqa: BLE001
        report["warnings"].append(f"OSS runtime failed: {exc}")
        return report

    report["status"] = "executed"
    report["kafka_topics_published"] = len(topic_rows)
    report["kafka_messages_consumed"] = sum(len(rows) for rows in consumed_rows.values())
    report["postgres_rows_loaded"] = postgres_rows_loaded
    report["minio_objects_uploaded"] = minio_uploaded
    report["ingestion_event_bus"] = ingestion_paths
    report["storage_paths"] = storage_paths
    report["curated_rows"] = curated_rows
    return report


def _publish_source_tables_to_kafka(
    *,
    compose_file: Path,
    use_case_id: str,
    run_id: str,
    source_tables: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Publish source rows to run-scoped raw topics."""
    use_case_slug = use_case_id.lower().replace("-", "_")
    run_suffix = run_id.lower()

    topic_rows: dict[str, list[dict[str, Any]]] = {}
    for table_name in sorted(source_tables):
        rows = source_tables[table_name]
        topic = f"raw.{use_case_slug}.{table_name}.v1.{run_suffix}"

        _run(
            compose_cmd(
                compose_file=compose_file,
                args=[
                    "exec",
                    "-T",
                    "kafka",
                    "bash",
                    "-lc",
                    (
                        f"{KAFKA_BIN}/kafka-topics.sh --bootstrap-server kafka:9092 "
                        f"--create --if-not-exists --topic {topic}"
                    ),
                ],
            )
        )

        lines = [json.dumps(row) for row in rows]
        if lines:
            _run(
                compose_cmd(
                    compose_file=compose_file,
                    args=[
                        "exec",
                        "-T",
                        "kafka",
                        "bash",
                        "-lc",
                        (
                            f"{KAFKA_BIN}/kafka-console-producer.sh --bootstrap-server kafka:9092 "
                            f"--topic {topic}"
                        ),
                    ],
                ),
                input_text="\n".join(lines) + "\n",
            )
        topic_rows[topic] = rows

    return topic_rows


def _consume_source_tables_from_kafka(
    *,
    compose_file: Path,
    topic_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Consume exactly the expected number of rows from each run-scoped topic."""
    consumed: dict[str, list[dict[str, Any]]] = {}
    for topic, expected_rows in topic_rows.items():
        expected_count = len(expected_rows)
        if expected_count == 0:
            consumed[topic] = []
            continue

        result = _run(
            compose_cmd(
                compose_file=compose_file,
                args=[
                    "exec",
                    "-T",
                    "kafka",
                    "bash",
                    "-lc",
                    (
                        f"{KAFKA_BIN}/kafka-console-consumer.sh --bootstrap-server kafka:9092 "
                        f"--topic {topic} --from-beginning --max-messages {expected_count} "
                        "--timeout-ms 10000"
                    ),
                ],
            )
        )
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        consumed[topic] = [json.loads(line) for line in lines]
    return consumed


def _build_event_bus_from_consumed_rows(
    consumed_rows: dict[str, list[dict[str, Any]]]
) -> LocalEventBus:
    """Create an in-memory bus populated with consumed OSS topic rows."""
    bus = LocalEventBus()
    for topic in sorted(consumed_rows):
        for row in consumed_rows[topic]:
            bus.publish(topic=topic, payload=row)
    return bus


def _write_ingestion_artifacts(bus: LocalEventBus, run_dir: Path) -> dict[str, str]:
    """Persist per-topic ingestion artifacts from OSS-consumed events."""
    target = run_dir / "ingestion" / "event_bus"
    target.mkdir(parents=True, exist_ok=True)

    artifact_paths: dict[str, str] = {}
    for topic in sorted(bus.topics):
        events = bus.topics[topic]
        safe_topic = topic.replace(".", "_")
        topic_file = target / f"{safe_topic}.jsonl"
        with topic_file.open("w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
        artifact_paths[topic] = str(topic_file)
    return artifact_paths


def _load_curated_into_postgres(
    *,
    compose_file: Path,
    use_case_id: str,
    run_id: str,
    curated_records_jsonl_path: Path,
) -> int:
    """Load curated rows into a generic JSONB warehouse table for queryability."""
    lines = [
        line.strip()
        for line in curated_records_jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    wrapped_lines = []
    for line in lines:
        wrapped_lines.append(
            json.dumps(
                {
                    "use_case_id": use_case_id,
                    "run_id": run_id,
                    "record": json.loads(line),
                }
            )
        )

    _run(
        compose_cmd(
            compose_file=compose_file,
            args=[
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "cdp",
                "-d",
                "cdp",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                (
                    "CREATE TABLE IF NOT EXISTS cdp_curated_rows ("
                    "ingested_at timestamptz DEFAULT now(), payload jsonb);"
                ),
            ],
        )
    )

    if wrapped_lines:
        _run(
            compose_cmd(
                compose_file=compose_file,
                args=[
                    "exec",
                    "-T",
                    "postgres",
                    "psql",
                    "-U",
                    "cdp",
                    "-d",
                    "cdp",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    "COPY cdp_curated_rows(payload) FROM STDIN;",
                ],
            ),
            input_text="\n".join(wrapped_lines) + "\n",
        )
    return len(wrapped_lines)


def _upload_artifacts_to_minio(
    *,
    compose_file: Path,
    use_case_id: str,
    run_id: str,
    raw_events_path: Path,
    curated_records_jsonl_path: Path,
) -> int:
    """Upload raw and curated artifacts into a versioned MinIO object path."""
    upload_count = 0
    objects = [
        (raw_events_path, f"{use_case_id}/{run_id}/storage/raw/events.jsonl"),
        (
            curated_records_jsonl_path,
            f"{use_case_id}/{run_id}/storage/curated/records.jsonl",
        ),
    ]

    _run(
        compose_cmd(
            compose_file=compose_file,
            args=[
                "exec",
                "-T",
                "mc",
                "sh",
                "-lc",
                (
                    "mc alias set local http://minio:9000 \"$MINIO_ROOT_USER\" "
                    "\"$MINIO_ROOT_PASSWORD\" >/dev/null && "
                    "mc mb -p local/cdp-artifacts >/dev/null 2>&1 || true"
                ),
            ],
        )
    )

    for source_path, object_key in objects:
        file_content = source_path.read_text(encoding="utf-8")
        _run(
            compose_cmd(
                compose_file=compose_file,
                args=[
                    "exec",
                    "-T",
                    "mc",
                    "sh",
                    "-lc",
                    (
                        "mc alias set local http://minio:9000 \"$MINIO_ROOT_USER\" "
                        "\"$MINIO_ROOT_PASSWORD\" >/dev/null && "
                        f"mc pipe local/cdp-artifacts/{object_key}"
                    ),
                ],
            ),
            input_text=file_content,
        )
        upload_count += 1
    return upload_count


def _running_services(compose_file: Path) -> set[str]:
    """Return currently running services for the selected compose file."""
    result = _run(
        compose_cmd(
            compose_file=compose_file,
            args=["ps", "--services", "--status", "running"],
        ),
        check=False,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _wait_for_oss_readiness(compose_file: Path, timeout_seconds: int) -> tuple[bool, str]:
    """Wait until Kafka/Postgres/MinIO command probes pass."""
    deadline = time.time() + timeout_seconds
    last_reason = "unknown"

    while time.time() < deadline:
        kafka_probe = _run(
            compose_cmd(
                compose_file=compose_file,
                args=[
                    "exec",
                    "-T",
                    "kafka",
                    "bash",
                    "-lc",
                    f"{KAFKA_BIN}/kafka-topics.sh --bootstrap-server kafka:9092 --list >/dev/null 2>&1",
                ],
            ),
            check=False,
        )
        if kafka_probe.returncode != 0:
            last_reason = "kafka probe failed"
            time.sleep(2)
            continue

        postgres_probe = _run(
            compose_cmd(
                compose_file=compose_file,
                args=[
                    "exec",
                    "-T",
                    "postgres",
                    "psql",
                    "-U",
                    "cdp",
                    "-d",
                    "cdp",
                    "-t",
                    "-A",
                    "-c",
                    "SELECT 1;",
                ],
            ),
            check=False,
        )
        if postgres_probe.returncode != 0:
            last_reason = "postgres probe failed"
            time.sleep(2)
            continue

        minio_probe = _run(
            compose_cmd(
                compose_file=compose_file,
                args=[
                    "exec",
                    "-T",
                    "mc",
                    "sh",
                    "-lc",
                    (
                        "mc alias set local http://minio:9000 \"$MINIO_ROOT_USER\" "
                        "\"$MINIO_ROOT_PASSWORD\" >/dev/null"
                    ),
                ],
            ),
            check=False,
        )
        if minio_probe.returncode != 0:
            last_reason = "minio probe failed"
            time.sleep(2)
            continue

        return True, "ready"

    return False, last_reason


def _run(
    cmd: list[str], input_text: str | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command with captured output and optional strict mode."""
    result = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip() or "<no stderr>"
        raise RuntimeError(f"Command failed: {' '.join(cmd)} :: {stderr}")
    return result
