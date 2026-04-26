from __future__ import annotations

"""OSS infrastructure mirror helpers.

This module mirrors locally produced artifacts to the optional OSS profile:
- Kafka for event topics
- PostgreSQL for curated rows
- MinIO for raw/curated file objects

The mirror is intentionally best-effort and never blocks local run completion.
On any infra issue, the caller receives a fallback report.
"""

import json
import subprocess
from pathlib import Path
from typing import Any

from stack.compose_utils import compose_cmd, detect_compose_command

KAFKA_BIN = "/opt/kafka/bin"


def mirror_run_to_oss(
    compose_file: Path,
    use_case_id: str,
    run_id: str,
    event_topic_files: dict[str, str],
    raw_events_path: str,
    curated_records_jsonl_path: str,
) -> dict[str, Any]:
    """Mirror one run's data products to OSS services if they are available."""
    report: dict[str, Any] = {
        "status": "fallback_local",
        "compose_file": str(compose_file),
        "warnings": [],
        "kafka_topics_published": 0,
        "postgres_rows_loaded": 0,
        "minio_objects_uploaded": 0,
    }

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

    try:
        topic_count = _publish_kafka_topics(compose_file=compose_file, topic_files=event_topic_files)
        postgres_count = _load_curated_into_postgres(
            compose_file=compose_file,
            use_case_id=use_case_id,
            run_id=run_id,
            curated_records_jsonl_path=Path(curated_records_jsonl_path),
        )
        minio_count = _upload_artifacts_to_minio(
            compose_file=compose_file,
            use_case_id=use_case_id,
            run_id=run_id,
            raw_events_path=Path(raw_events_path),
            curated_records_jsonl_path=Path(curated_records_jsonl_path),
        )
    except Exception as exc:  # noqa: BLE001
        report["warnings"].append(f"OSS mirror failed: {exc}")
        return report

    report["status"] = "mirrored"
    report["kafka_topics_published"] = topic_count
    report["postgres_rows_loaded"] = postgres_count
    report["minio_objects_uploaded"] = minio_count
    return report


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
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return set(lines)


def _publish_kafka_topics(compose_file: Path, topic_files: dict[str, str]) -> int:
    """Create topics when needed and publish JSONL event files to Kafka."""
    published_topics = 0
    for topic, file_path in topic_files.items():
        file_content = Path(file_path).read_text(encoding="utf-8")
        if not file_content.strip():
            continue

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
                        f"{KAFKA_BIN}/kafka-console-producer.sh "
                        f"--bootstrap-server kafka:9092 --topic {topic}"
                    ),
                ],
            ),
            input_text=file_content,
        )
        published_topics += 1
    return published_topics


def _load_curated_into_postgres(
    compose_file: Path,
    use_case_id: str,
    run_id: str,
    curated_records_jsonl_path: Path,
) -> int:
    """Load curated rows into a generic JSONB warehouse table for inspection/querying."""
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


def _run(
    cmd: list[str], input_text: str | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Execute command and surface concise error context when a step fails."""
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
