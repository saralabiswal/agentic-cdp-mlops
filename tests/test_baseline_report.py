from __future__ import annotations

import json
from pathlib import Path

from stack.baseline_report import generate_baseline_report, write_baseline_report


def test_generate_baseline_report_uses_latest_run_per_use_case(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-NBA-RET-001",
        run_id="20270101T010101Z",
        run_status="pass",
        primary_kpi_value=0.11,
        data_quality_status="pass",
        readiness_status="ready",
    )
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-NBA-RET-001",
        run_id="20270102T010101Z",
        run_status="pass",
        primary_kpi_value=0.19,
        data_quality_status="pass",
        readiness_status="pending_approval",
    )
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-CHURN-RET-002",
        run_id="20270101T010101Z",
        run_status="fail",
        primary_kpi="60_day_incremental_churn_reduction",
        primary_kpi_value=0.05,
        model_backend="tensorflow",
        data_quality_status="warn",
        readiness_status="blocked",
        blockers=["usage_signals.range_recency_norm"],
    )

    payload = generate_baseline_report(artifacts_root=artifacts_root)
    assert payload["selection"]["strategy"] == "latest_per_use_case"
    assert payload["totals"]["use_case_count"] == 2
    assert payload["totals"]["latest_pass_count"] == 1
    assert payload["totals"]["latest_fail_count"] == 1

    nba_row = next(row for row in payload["runs"] if row["use_case_id"] == "UC-NBA-RET-001")
    churn_row = next(row for row in payload["runs"] if row["use_case_id"] == "UC-CHURN-RET-002")

    assert nba_row["run_id"] == "20270102T010101Z"
    assert nba_row["model_backend"] == "tensorflow"
    assert nba_row["primary_kpi"] == "30_day_incremental_retention_lift"
    assert nba_row["primary_kpi_value"] == 0.19
    assert nba_row["data_quality_status"] == "pass"
    assert nba_row["deployment_readiness_status"] == "pending_approval"

    assert churn_row["data_quality_status"] == "warn"
    assert churn_row["deployment_readiness_status"] == "blocked"
    assert churn_row["deployment_blockers"] == ["usage_signals.range_recency_norm"]


def test_write_baseline_report_writes_json_file(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-MMM-PLN-003",
        run_id="20270105T010101Z",
        run_status="pass",
        primary_kpi="portfolio_incremental_revenue_at_fixed_budget",
        primary_kpi_value=1200.5,
        model_backend="pymc_marketing_adapter",
        data_quality_status="pass",
        readiness_status="pending_approval",
    )

    payload = write_baseline_report(artifacts_root=artifacts_root)
    report_path = Path(payload["report_path"])
    assert report_path.exists()

    parsed = json.loads(report_path.read_text(encoding="utf-8"))
    assert parsed["totals"]["use_case_count"] == 1
    assert parsed["runs"][0]["use_case_id"] == "UC-MMM-PLN-003"
    assert parsed["runs"][0]["model_backend"] == "pymc_marketing_adapter"


def _write_summary(
    *,
    artifacts_root: Path,
    use_case_id: str,
    run_id: str,
    run_status: str,
    primary_kpi: str = "30_day_incremental_retention_lift",
    primary_kpi_value: float = 0.1,
    model_backend: str = "tensorflow",
    data_quality_status: str = "pass",
    readiness_status: str = "ready",
    blockers: list[str] | None = None,
) -> None:
    run_dir = artifacts_root / use_case_id / run_id
    monitoring_dir = run_dir / "monitoring_governance"
    monitoring_dir.mkdir(parents=True, exist_ok=True)
    monitoring_report = monitoring_dir / "report.json"
    monitoring_report.write_text(
        json.dumps(
            {
                "data_quality": {
                    "status": data_quality_status,
                    "summary": {
                        "total_checks": 1,
                        "passed_checks": 1 if data_quality_status == "pass" else 0,
                        "warn_checks": 1 if data_quality_status == "warn" else 0,
                        "failed_checks": 1 if data_quality_status == "fail" else 0,
                    },
                },
                "deployment_readiness": {
                    "status": readiness_status,
                    "blockers": blockers or [],
                },
            }
        ),
        encoding="utf-8",
    )

    summary = {
        "use_case_id": use_case_id,
        "name": "baseline-test",
        "run_id": run_id,
        "seed": 101,
        "infra_profile": "local",
        "run_status": run_status,
        "strict_model_backends": True,
        "model_metrics": {
            "primary_kpi": primary_kpi,
            primary_kpi: primary_kpi_value,
            "model_backend": model_backend,
            "avg_expected_uplift": 0.12,
        },
        "artifacts": {
            "monitoring_report": str(monitoring_report.as_posix()),
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
