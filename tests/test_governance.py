from __future__ import annotations

import json
from pathlib import Path

import pytest

from stack.governance import approve_run_governance


def test_approve_run_governance_accepts_warning_and_writes_ledger(tmp_path: Path) -> None:
    _write_run_with_monitoring(
        artifacts_root=tmp_path,
        use_case_id="UC-INCR-MKT-004",
        run_id="20270101T010101Z",
        deployment_status="pending_approval",
        blockers=[],
        warning_checks=["campaign_experiments.enum_audience_tier"],
    )

    payload = approve_run_governance(
        artifacts_root=tmp_path,
        use_case_id="UC-INCR-MKT-004",
        run_id="20270101T010101Z",
        approved_by="qa-user",
        note="approved in test",
        accept_warnings=["campaign_experiments.enum_audience_tier"],
        warning_rationale="accepted for test release",
    )

    deployment = payload["deployment_readiness"]
    assert deployment["status"] == "ready"
    assert deployment["approval"]["status"] == "approved"
    assert deployment["approval"]["approved_by"] == "qa-user"
    assert deployment["warning_dispositions"][0]["decision"] == "accepted"
    assert (
        deployment["warning_dispositions"][0]["name"]
        == "campaign_experiments.enum_audience_tier"
    )

    ledger_path = tmp_path / "governance_approvals.json"
    assert ledger_path.exists()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger["approvals"][0]["run_id"] == "20270101T010101Z"
    assert ledger["warning_decisions"][0]["decision"] == "accepted"


def test_approve_run_governance_blocks_when_blockers_exist(tmp_path: Path) -> None:
    _write_run_with_monitoring(
        artifacts_root=tmp_path,
        use_case_id="UC-NBA-RET-001",
        run_id="20270101T010101Z",
        deployment_status="blocked",
        blockers=["required_field_coverage_full"],
        warning_checks=[],
    )

    with pytest.raises(ValueError, match="blocked by deployment blockers"):
        approve_run_governance(
            artifacts_root=tmp_path,
            use_case_id="UC-NBA-RET-001",
            run_id="20270101T010101Z",
        )


def _write_run_with_monitoring(
    *,
    artifacts_root: Path,
    use_case_id: str,
    run_id: str,
    deployment_status: str,
    blockers: list[str],
    warning_checks: list[str],
) -> None:
    run_dir = artifacts_root / use_case_id / run_id
    monitoring_dir = run_dir / "monitoring_governance"
    models_dir = run_dir / "models"
    monitoring_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    report_path = monitoring_dir / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "use_case_id": use_case_id,
                "run_status": "pass",
                "deployment_readiness": {
                    "status": deployment_status,
                    "score": 1.0,
                    "approval_required": True,
                    "blockers": blockers,
                    "failed_gates": [],
                    "failed_model_checks": [],
                    "failed_data_quality_checks": [],
                    "warning_data_quality_checks": warning_checks,
                },
            }
        ),
        encoding="utf-8",
    )

    predictions_path = models_dir / "predictions.json"
    metrics_path = models_dir / "metrics.json"
    manifest_path = models_dir / "manifest.json"
    predictions_path.write_text(json.dumps({"rows": [{"id": "1"}]}), encoding="utf-8")
    metrics_path.write_text(
        json.dumps({"model_metrics": {"primary_kpi": "kpi"}}),
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps({"artifact_schema_version": "1.0"}), encoding="utf-8")

    summary = {
        "use_case_id": use_case_id,
        "run_id": run_id,
        "name": use_case_id,
        "run_status": "pass",
        "infra_profile": "local",
        "strict_model_backends": False,
        "model_metrics": {
            "primary_kpi": "kpi",
            "model_version": "v1",
            "model_backend": "tensorflow",
        },
        "artifacts": {
            "model_predictions": str(predictions_path.as_posix()),
            "model_metrics": str(metrics_path.as_posix()),
            "model_manifest": str(manifest_path.as_posix()),
            "monitoring_report": str(report_path.as_posix()),
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
