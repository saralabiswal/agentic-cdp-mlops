from __future__ import annotations

from pathlib import Path

from pipelines.contract_loader import load_contract_by_id
from stack.layers.monitoring_governance import run_monitoring_and_governance


def test_monitoring_governance_builds_readiness_and_scientific_metadata(tmp_path: Path) -> None:
    contract = load_contract_by_id("UC-NBA-RET-001")
    model_rows = [
        {
            "customer_id": "U-CUST-0001",
            "action_id": "offer_10pct_discount",
            "action_channel": "email",
            "expected_uplift": 0.21,
            "confidence": 0.82,
            "reason_codes": ["high_churn_risk", "high_customer_value"],
            "score_ts": "2026-04-22T10:00:00Z",
            "model_version": "nba_retention_v0_1",
            "policy_version": "policy_v1",
        }
    ]
    metrics = {
        "primary_kpi": contract.primary_kpi,
        "avg_expected_uplift": 0.21,
        "avg_confidence": 0.82,
    }

    report, report_path = run_monitoring_and_governance(
        contract=contract,
        model_rows=model_rows,
        model_metrics=metrics,
        output_dir=tmp_path,
        run_id="20260422T180000Z",
        seed=101,
    )

    assert Path(report_path).exists()
    assert report["run_status"] == "pass"
    assert report["deployment_readiness"]["status"] == "pending_approval"
    assert report["model_validation"]["summary"]["failed_checks"] == 0
    assert report["scientific_governance"]["run_id"] == "20260422T180000Z"
    assert report["scientific_governance"]["seed"] == 101
    assert report["scientific_governance"]["contract_fingerprint_sha256"]


def test_monitoring_governance_blocks_when_required_metrics_are_missing(tmp_path: Path) -> None:
    contract = load_contract_by_id("UC-NBA-RET-001")
    model_rows = [
        {
            "customer_id": "U-CUST-0001",
            "action_id": "offer_10pct_discount",
            "action_channel": "email",
            "expected_uplift": 0.21,
            "confidence": 0.82,
            "reason_codes": ["high_churn_risk", "high_customer_value"],
            "score_ts": "2026-04-22T10:00:00Z",
            "model_version": "nba_retention_v0_1",
            "policy_version": "policy_v1",
        }
    ]
    # Missing avg_confidence should fail one standardized model-validation check.
    metrics = {
        "primary_kpi": contract.primary_kpi,
        "avg_expected_uplift": 0.21,
    }

    report, _ = run_monitoring_and_governance(
        contract=contract,
        model_rows=model_rows,
        model_metrics=metrics,
        output_dir=tmp_path,
        run_id="20260422T180001Z",
        seed=101,
    )

    assert report["run_status"] == "fail"
    assert report["deployment_readiness"]["status"] == "blocked"
    assert "avg_confidence_range" in report["deployment_readiness"]["failed_model_checks"]


def test_monitoring_governance_includes_fail_warn_data_quality_gates(tmp_path: Path) -> None:
    contract = load_contract_by_id("UC-NBA-RET-001")
    model_rows = [
        {
            "customer_id": "U-CUST-0001",
            "action_id": "offer_10pct_discount",
            "action_channel": "email",
            "expected_uplift": 0.21,
            "confidence": 0.82,
            "reason_codes": ["high_churn_risk", "high_customer_value"],
            "score_ts": "2026-04-22T10:00:00Z",
            "model_version": "nba_retention_v0_1",
            "policy_version": "policy_v1",
        }
    ]
    metrics = {
        "primary_kpi": contract.primary_kpi,
        "avg_expected_uplift": 0.21,
        "avg_confidence": 0.82,
    }
    source_data_metadata = {
        "mode": "real_dataset",
        "data_quality": {
            "checks": [
                {
                    "name": "unique_key_customer_id",
                    "table": "crm_customers",
                    "severity": "fail",
                    "status": "fail",
                    "expectation": "unique key values",
                    "reason": "blocking threshold breached",
                },
                {
                    "name": "enum_historical_action_id",
                    "table": "behavior_signals",
                    "severity": "warn",
                    "status": "warn",
                    "expectation": "historical_action_id in configured enum",
                    "reason": "warning threshold breached",
                },
            ],
            "table_summaries": {},
        },
    }

    report, _ = run_monitoring_and_governance(
        contract=contract,
        model_rows=model_rows,
        model_metrics=metrics,
        output_dir=tmp_path,
        run_id="20260422T180002Z",
        seed=101,
        source_data_metadata=source_data_metadata,
    )

    assert report["run_status"] == "fail"
    assert report["data_quality"]["status"] == "fail"
    assert report["data_quality"]["gates"]["fail_gate"] == "fail"
    assert report["data_quality"]["gates"]["warn_gate"] == "warn"
    assert "crm_customers.unique_key_customer_id" in report["deployment_readiness"]["blockers"]
    assert (
        "behavior_signals.enum_historical_action_id"
        in report["deployment_readiness"]["warning_data_quality_checks"]
    )
