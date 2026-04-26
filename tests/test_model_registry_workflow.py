from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from stack.model_registry import (
    evaluate_model_promotion_readiness,
    list_model_registry_entries,
    promote_model_version,
    register_model_candidate_from_summary,
)
from stack.orchestrator import run_full_stack


def test_run_full_stack_auto_registers_candidate_entry(tmp_path: Path) -> None:
    summary = run_full_stack(use_case_id="UC-NBA-RET-001", output_dir=tmp_path, seed=11)
    registry_path = tmp_path / "model_registry" / "registry.json"
    assert registry_path.exists()
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    assert payload["entries"]

    entry = next(
        row
        for row in payload["entries"]
        if row["use_case_id"] == "UC-NBA-RET-001" and row["run_id"] == summary["run_id"]
    )
    assert entry["stage"] == "candidate"
    assert entry["model_version"] == summary["model_metrics"]["model_version"]
    assert summary["model_registry"]["registry_path"] == str(registry_path.as_posix())


def test_model_readiness_strict_backend_blocking(tmp_path: Path) -> None:
    summary = _write_summary_fixture(
        artifacts_root=tmp_path,
        use_case_id="UC-NBA-RET-001",
        run_id="20270101T010101Z",
        model_backend="heuristic_fallback",
        run_status="pass",
        deployment_status="ready",
    )
    register_model_candidate_from_summary(
        summary=summary,
        artifacts_root=tmp_path,
        summary_path=tmp_path / "UC-NBA-RET-001" / "20270101T010101Z" / "summary.json",
    )

    readiness = evaluate_model_promotion_readiness(
        use_case_id="UC-NBA-RET-001",
        run_id="20270101T010101Z",
        artifacts_root=tmp_path,
        require_strict_backend=True,
    )
    assert readiness["ready"] is False
    assert "advanced_backend_requirement" in readiness["blocking_failures"]


def test_model_promotion_to_prod_demotes_previous_prod(tmp_path: Path) -> None:
    summary_old = _write_summary_fixture(
        artifacts_root=tmp_path,
        use_case_id="UC-NBA-RET-001",
        run_id="20270101T010101Z",
        model_backend="tensorflow",
        run_status="pass",
        deployment_status="ready",
    )
    summary_new = _write_summary_fixture(
        artifacts_root=tmp_path,
        use_case_id="UC-NBA-RET-001",
        run_id="20270102T010101Z",
        model_backend="tensorflow",
        run_status="pass",
        deployment_status="ready",
    )

    register_model_candidate_from_summary(
        summary=summary_old,
        artifacts_root=tmp_path,
        summary_path=tmp_path / "UC-NBA-RET-001" / "20270101T010101Z" / "summary.json",
    )
    register_model_candidate_from_summary(
        summary=summary_new,
        artifacts_root=tmp_path,
        summary_path=tmp_path / "UC-NBA-RET-001" / "20270102T010101Z" / "summary.json",
    )

    promote_model_version(
        use_case_id="UC-NBA-RET-001",
        run_id="20270101T010101Z",
        target_stage="prod",
        artifacts_root=tmp_path,
        require_strict_backend=True,
    )
    promote_model_version(
        use_case_id="UC-NBA-RET-001",
        run_id="20270102T010101Z",
        target_stage="prod",
        artifacts_root=tmp_path,
        require_strict_backend=True,
    )

    listed = list_model_registry_entries(
        artifacts_root=tmp_path,
        use_case_id="UC-NBA-RET-001",
        limit=20,
    )
    by_run = {row["run_id"]: row for row in listed["entries"]}
    assert by_run["20270102T010101Z"]["stage"] == "prod"
    assert by_run["20270101T010101Z"]["stage"] == "approved"


def test_cli_model_registry_commands(tmp_path: Path) -> None:
    summary = _write_summary_fixture(
        artifacts_root=tmp_path,
        use_case_id="UC-NBA-RET-001",
        run_id="20270105T010101Z",
        model_backend="tensorflow",
        run_status="pass",
        deployment_status="ready",
    )
    register_model_candidate_from_summary(
        summary=summary,
        artifacts_root=tmp_path,
        summary_path=tmp_path / "UC-NBA-RET-001" / "20270105T010101Z" / "summary.json",
    )

    readiness_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "model-readiness",
        "--artifacts-root",
        str(tmp_path),
        "--use-case",
        "UC-NBA-RET-001",
        "--run-id",
        "20270105T010101Z",
        "--require-strict-backend",
    ]
    readiness_result = subprocess.run(
        readiness_cmd, check=True, capture_output=True, text=True
    )
    readiness_payload = json.loads(readiness_result.stdout)
    assert readiness_payload["ready"] is True

    promote_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "model-promote",
        "--artifacts-root",
        str(tmp_path),
        "--use-case",
        "UC-NBA-RET-001",
        "--run-id",
        "20270105T010101Z",
        "--to",
        "approved",
    ]
    promote_result = subprocess.run(promote_cmd, check=True, capture_output=True, text=True)
    promote_payload = json.loads(promote_result.stdout)
    assert promote_payload["entry"]["stage"] == "approved"

    list_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "model-registry-list",
        "--artifacts-root",
        str(tmp_path),
        "--use-case",
        "UC-NBA-RET-001",
        "--stage",
        "approved",
    ]
    list_result = subprocess.run(list_cmd, check=True, capture_output=True, text=True)
    list_payload = json.loads(list_result.stdout)
    assert list_payload["count"] == 1
    assert list_payload["entries"][0]["run_id"] == "20270105T010101Z"


def _write_summary_fixture(
    *,
    artifacts_root: Path,
    use_case_id: str,
    run_id: str,
    model_backend: str,
    run_status: str,
    deployment_status: str,
) -> dict[str, object]:
    run_dir = artifacts_root / use_case_id / run_id
    models_dir = run_dir / "models"
    monitoring_dir = run_dir / "monitoring_governance"
    models_dir.mkdir(parents=True, exist_ok=True)
    monitoring_dir.mkdir(parents=True, exist_ok=True)

    predictions_path = models_dir / "predictions.json"
    metrics_path = models_dir / "metrics.json"
    manifest_path = models_dir / "manifest.json"
    monitoring_path = monitoring_dir / "report.json"

    predictions_path.write_text(json.dumps({"rows": [{"id": "1"}], "metrics": {}}), encoding="utf-8")
    metrics_path.write_text(
        json.dumps(
            {
                "artifact_schema_version": "1.0",
                "model_metrics": {
                    "primary_kpi": "30_day_incremental_retention_lift",
                },
            }
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps({"artifact_schema_version": "1.0"}),
        encoding="utf-8",
    )
    monitoring_path.write_text(
        json.dumps({"deployment_readiness": {"status": deployment_status}}),
        encoding="utf-8",
    )

    summary = {
        "use_case_id": use_case_id,
        "name": use_case_id,
        "run_id": run_id,
        "seed": 7,
        "infra_profile": "local",
        "run_status": run_status,
        "strict_model_backends": False,
        "model_metrics": {
            "primary_kpi": "30_day_incremental_retention_lift",
            "30_day_incremental_retention_lift": 0.12,
            "model_version": "nba_retention_tf_v1",
            "model_backend": model_backend,
        },
        "artifacts": {
            "model_predictions": str(predictions_path.as_posix()),
            "model_metrics": str(metrics_path.as_posix()),
            "model_manifest": str(manifest_path.as_posix()),
            "monitoring_report": str(monitoring_path.as_posix()),
        },
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    return summary
