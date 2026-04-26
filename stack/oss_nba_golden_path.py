from __future__ import annotations

"""NBA-first OSS runtime path.

This module executes the requested golden path for `UC-NBA-RET-001`:
1) publish source entities directly to Kafka topics
2) consume topic values back into the pipeline
3) build curated rows and persist them to Postgres
4) store raw/curated snapshots in MinIO

If OSS infra is unavailable, caller receives `fallback_local` status and can
continue with local adapters.
"""

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stack.compose_utils import compose_cmd, detect_compose_command

USE_CASE_ID = "UC-NBA-RET-001"
USE_CASE_SLUG = "uc_nba_ret_001"
REQUIRED_TABLES = ("crm_customers", "behavior_signals", "contact_history")
KAFKA_BIN = "/opt/kafka/bin"


def run_nba_oss_golden_path(
    compose_file: Path,
    run_dir: Path,
    run_id: str,
    source_tables: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Run NBA golden path on OSS infra and return artifacts + status report."""
    report: dict[str, Any] = {
        "status": "fallback_local",
        "compose_file": str(compose_file),
        "warnings": [],
        "kafka_topics_published": 0,
        "kafka_messages_consumed": 0,
        "postgres_rows_loaded": 0,
        "minio_objects_uploaded": 0,
    }

    missing_tables = sorted(set(REQUIRED_TABLES) - set(source_tables))
    if missing_tables:
        report["warnings"].append(f"Missing required source tables: {missing_tables}")
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
            source_tables=source_tables,
            run_id=run_id,
        )
        consumed_rows = _consume_source_tables_from_kafka(
            compose_file=compose_file,
            topic_rows=topic_rows,
        )
        curated_rows = _curate_nba_rows(consumed_rows)
        artifact_paths = _write_local_artifacts(
            run_dir=run_dir,
            topic_rows=consumed_rows,
            curated_rows=curated_rows,
        )
        postgres_rows_loaded = _load_curated_into_postgres(
            compose_file=compose_file,
            run_id=run_id,
            curated_rows=curated_rows,
        )
        minio_uploaded = _upload_snapshots_to_minio(
            compose_file=compose_file,
            use_case_id=USE_CASE_ID,
            run_id=run_id,
            raw_events_path=Path(artifact_paths["storage"]["raw_events"]),
            curated_jsonl_path=Path(artifact_paths["storage"]["curated_records_jsonl"]),
        )
    except Exception as exc:  # noqa: BLE001
        report["warnings"].append(f"NBA OSS runtime failed: {exc}")
        return report

    report["status"] = "executed"
    report["kafka_topics_published"] = len(topic_rows)
    report["kafka_messages_consumed"] = sum(len(rows) for rows in consumed_rows.values())
    report["postgres_rows_loaded"] = postgres_rows_loaded
    report["minio_objects_uploaded"] = minio_uploaded
    report["ingestion_event_bus"] = artifact_paths["ingestion_event_bus"]
    report["storage_paths"] = artifact_paths["storage"]
    report["curated_rows"] = curated_rows
    return report


def _publish_source_tables_to_kafka(
    compose_file: Path,
    source_tables: dict[str, list[dict[str, Any]]],
    run_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Publish source rows to run-scoped raw topics."""
    topic_rows: dict[str, list[dict[str, Any]]] = {}
    run_suffix = run_id.lower()

    for table_name in REQUIRED_TABLES:
        rows = source_tables[table_name]
        topic = f"raw.{USE_CASE_SLUG}.{table_name}.v1.{run_suffix}"
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


def _curate_nba_rows(consumed_rows: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Join consumed entities into curated NBA customer rows."""
    by_table: dict[str, list[dict[str, Any]]] = {}
    for topic, rows in consumed_rows.items():
        table_name = _table_from_topic(topic)
        by_table[table_name] = rows

    customers = {row["customer_id"]: row for row in by_table["crm_customers"]}
    behavior = {row["customer_id"]: row for row in by_table["behavior_signals"]}
    contact = {row["customer_id"]: row for row in by_table["contact_history"]}

    curated: list[dict[str, Any]] = []
    for customer_id, profile in customers.items():
        curated.append(
            {
                "customer_id": customer_id,
                **profile,
                **behavior[customer_id],
                **contact[customer_id],
            }
        )
    return curated


def _table_from_topic(topic: str) -> str:
    """Extract source table name from canonical run-scoped topic string."""
    # Topic pattern:
    # raw.uc_nba_ret_001.<table>.v1.<run_id>
    parts = topic.split(".")
    if len(parts) < 5:
        raise ValueError(f"Unexpected topic format: {topic}")
    return parts[2]


def _write_local_artifacts(
    run_dir: Path,
    topic_rows: dict[str, list[dict[str, Any]]],
    curated_rows: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    """Write ingestion and storage artifacts used by downstream layers."""
    ingestion_dir = run_dir / "ingestion" / "event_bus"
    raw_dir = run_dir / "storage" / "raw"
    curated_dir = run_dir / "storage" / "curated"
    ingestion_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    curated_dir.mkdir(parents=True, exist_ok=True)

    ingest_paths: dict[str, str] = {}
    raw_events: list[dict[str, Any]] = []

    for topic, rows in topic_rows.items():
        events = [
            {
                "event_ts": datetime.now(timezone.utc).isoformat(),
                "topic": topic,
                "payload": row,
            }
            for row in rows
        ]
        raw_events.extend(events)

        safe_topic = topic.replace(".", "_")
        topic_file = ingestion_dir / f"{safe_topic}.jsonl"
        with topic_file.open("w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
        ingest_paths[topic] = str(topic_file)

    raw_events_file = raw_dir / "events.jsonl"
    with raw_events_file.open("w", encoding="utf-8") as f:
        for event in raw_events:
            f.write(json.dumps(event) + "\n")

    curated_json = curated_dir / "records.json"
    with curated_json.open("w", encoding="utf-8") as f:
        json.dump(curated_rows, f, indent=2)

    curated_jsonl = curated_dir / "records.jsonl"
    with curated_jsonl.open("w", encoding="utf-8") as f:
        for row in curated_rows:
            f.write(json.dumps(row) + "\n")

    return {
        "ingestion_event_bus": ingest_paths,
        "storage": {
            "raw_events": str(raw_events_file),
            "curated_records": str(curated_json),
            "curated_records_jsonl": str(curated_jsonl),
        },
    }


def _load_curated_into_postgres(
    compose_file: Path, run_id: str, curated_rows: list[dict[str, Any]]
) -> int:
    """Load curated NBA rows into Postgres JSONB table for downstream SQL access."""
    wrapped_rows = [
        json.dumps({"use_case_id": USE_CASE_ID, "run_id": run_id, "record": row})
        for row in curated_rows
    ]

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

    if wrapped_rows:
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
            input_text="\n".join(wrapped_rows) + "\n",
        )
    return len(wrapped_rows)


def _upload_snapshots_to_minio(
    compose_file: Path,
    use_case_id: str,
    run_id: str,
    raw_events_path: Path,
    curated_jsonl_path: Path,
) -> int:
    """Upload raw and curated snapshots to MinIO under a run-scoped prefix."""
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

    objects = [
        (raw_events_path, f"{use_case_id}/{run_id}/storage/raw/events.jsonl"),
        (curated_jsonl_path, f"{use_case_id}/{run_id}/storage/curated/records.jsonl"),
    ]
    uploaded = 0
    for source_path, object_key in objects:
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
            input_text=source_path.read_text(encoding="utf-8"),
        )
        uploaded += 1
    return uploaded


def _running_services(compose_file: Path) -> set[str]:
    """Return running service names for the compose profile."""
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
