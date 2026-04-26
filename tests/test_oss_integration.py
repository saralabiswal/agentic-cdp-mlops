from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from stack.orchestrator import run_full_stack

COMPOSE_FILE = Path("infra/docker-compose.oss.yml")
COMPOSE_WRAPPER = Path("scripts/compose.sh")
KAFKA_BIN = "/opt/kafka/bin"
REQUIRED_SERVICES = {"kafka", "postgres", "minio", "mc"}
USE_CASE_IDS = [
    "UC-NBA-RET-001",
    "UC-CHURN-RET-002",
    "UC-MMM-PLN-003",
    "UC-INCR-MKT-004",
]


@pytest.mark.parametrize("use_case_id", USE_CASE_IDS)
def test_oss_integration_end_to_end(use_case_id: str, tmp_path: Path) -> None:
    if os.environ.get("RUN_OSS_TESTS") != "1":
        pytest.skip("Set RUN_OSS_TESTS=1 to run OSS integration tests.")

    if not COMPOSE_WRAPPER.exists():
        pytest.skip(f"Missing compose wrapper: {COMPOSE_WRAPPER}")

    if not _services_running():
        pytest.skip("OSS services are not running. Run `make infra-up` first.")

    summary = run_full_stack(
        use_case_id=use_case_id,
        output_dir=tmp_path,
        seed=101,
        infra_profile="oss",
        oss_compose_file=COMPOSE_FILE,
    )

    assert summary["run_status"] == "pass"
    assert "oss_runtime" in summary
    assert summary["oss_runtime"]["status"] == "executed", summary["oss_runtime"].get(
        "warnings", []
    )
    assert summary["oss_runtime"]["kafka_topics_published"] >= 1
    assert summary["oss_runtime"]["kafka_messages_consumed"] > 0
    assert summary["oss_runtime"]["postgres_rows_loaded"] > 0
    assert summary["oss_runtime"]["minio_objects_uploaded"] >= 2

    run_id = summary["run_id"]
    topic = next(iter(summary["oss_runtime"]["ingestion_event_bus"].keys()))

    kafka_read = _compose_exec(
        [
            "exec",
            "-T",
            "kafka",
            "bash",
            "-lc",
            (
                f"{KAFKA_BIN}/kafka-console-consumer.sh "
                f"--bootstrap-server kafka:9092 --topic {topic} "
                "--from-beginning --max-messages 1 --timeout-ms 10000"
            ),
        ]
    )
    assert kafka_read.stdout.strip()

    safe_run_id = run_id.replace("'", "''")
    pg_count = _compose_exec(
        [
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
            (
                "SELECT count(*) FROM cdp_curated_rows "
                f"WHERE payload->>'run_id' = '{safe_run_id}' "
                f"AND payload->>'use_case_id' = '{use_case_id}';"
            ),
        ]
    )
    assert int(pg_count.stdout.strip() or "0") > 0

    minio_ls = _compose_exec(
        [
            "exec",
            "-T",
            "mc",
            "sh",
            "-lc",
            (
                "mc alias set local http://minio:9000 \"$MINIO_ROOT_USER\" "
                "\"$MINIO_ROOT_PASSWORD\" >/dev/null && "
                f"mc ls local/cdp-artifacts/{use_case_id}/{run_id}/storage --recursive"
            ),
        ]
    )
    out = minio_ls.stdout
    assert "events.jsonl" in out
    assert "records.jsonl" in out


def _services_running() -> bool:
    result = _compose_exec(
        ["ps", "--services", "--status", "running"],
        check=False,
    )
    if result.returncode != 0:
        return False
    running = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return REQUIRED_SERVICES.issubset(running)


def _compose_exec(
    args: list[str], check: bool = True
) -> subprocess.CompletedProcess[str]:
    cmd = [str(COMPOSE_WRAPPER), "-f", str(COMPOSE_FILE), *args]
    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip() or "<no stderr>"
        raise RuntimeError(f"Compose command failed: {' '.join(cmd)} :: {stderr}")
    return result
