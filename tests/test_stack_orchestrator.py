from __future__ import annotations

import json
from pathlib import Path

import pytest

from stack.orchestrator import (
    _enforce_real_data_split_validation,
    run_full_stack,
    run_full_stack_all,
)

USE_CASE_IDS = [
    "UC-NBA-RET-001",
    "UC-CHURN-RET-002",
    "UC-MMM-PLN-003",
    "UC-INCR-MKT-004",
]


@pytest.mark.parametrize("use_case_id", USE_CASE_IDS)
def test_full_stack_creates_layer_artifacts(use_case_id: str, tmp_path: Path) -> None:
    summary = run_full_stack(use_case_id=use_case_id, output_dir=tmp_path, seed=19)
    assert summary["run_status"] == "pass"

    summary_path = Path(summary["summary_path"])
    assert summary_path.exists()

    with summary_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    artifact_keys = set(payload["artifacts"].keys())
    expected_subset = {
        "raw_events",
        "curated_records",
        "feature_rows",
        "model_predictions",
        "model_metrics",
        "model_manifest",
        "activation_payloads",
        "monitoring_report",
    }
    assert expected_subset.issubset(artifact_keys)

    for path in payload["artifacts"].values():
        if isinstance(path, dict):
            for nested in path.values():
                assert Path(nested).exists()
        else:
            assert Path(path).exists()


@pytest.mark.parametrize("use_case_id", USE_CASE_IDS)
def test_full_stack_writes_model_versioned_artifacts(use_case_id: str, tmp_path: Path) -> None:
    summary = run_full_stack(use_case_id=use_case_id, output_dir=tmp_path, seed=29)
    artifacts = summary["artifacts"]

    predictions_path = Path(artifacts["model_predictions"])
    metrics_path = Path(artifacts["model_metrics"])
    manifest_path = Path(artifacts["model_manifest"])

    assert predictions_path.exists()
    assert metrics_path.exists()
    assert manifest_path.exists()

    metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert metrics_payload["artifact_schema_version"] == "1.0"
    assert metrics_payload["use_case_id"] == use_case_id
    assert "split_metrics" in metrics_payload
    assert "model_version" in metrics_payload["model_metrics"]

    assert manifest_payload["artifact_schema_version"] == "1.0"
    assert manifest_payload["use_case_id"] == use_case_id
    assert manifest_payload["artifacts"]["predictions"]["path"] == str(
        predictions_path.as_posix()
    )
    assert manifest_payload["artifacts"]["metrics"]["path"] == str(metrics_path.as_posix())


def test_full_stack_all_runs_every_use_case(tmp_path: Path) -> None:
    summaries = run_full_stack_all(output_dir=tmp_path, seed=23)
    assert len(summaries) == 4
    assert {summary["use_case_id"] for summary in summaries} == set(USE_CASE_IDS)


def test_full_stack_oss_profile_graceful_fallback(tmp_path: Path) -> None:
    summary = run_full_stack(
        use_case_id="UC-NBA-RET-001",
        output_dir=tmp_path,
        seed=5,
        infra_profile="oss",
        oss_compose_file=tmp_path / "missing-compose.yml",
    )
    assert summary["infra_profile"] == "oss"
    assert summary["run_status"] == "pass"
    assert "oss_runtime" in summary
    assert summary["oss_runtime"]["status"] == "fallback_local"


def test_full_stack_oss_profile_non_nba_runtime_fallback(tmp_path: Path) -> None:
    summary = run_full_stack(
        use_case_id="UC-MMM-PLN-003",
        output_dir=tmp_path,
        seed=5,
        infra_profile="oss",
        oss_compose_file=tmp_path / "missing-compose.yml",
    )
    assert summary["infra_profile"] == "oss"
    assert summary["run_status"] == "pass"
    assert "oss_runtime" in summary
    assert summary["oss_runtime"]["status"] == "fallback_local"


def test_full_stack_writes_optional_product_like_integration_artifacts(tmp_path: Path) -> None:
    summary = run_full_stack(
        use_case_id="UC-NBA-RET-001",
        output_dir=tmp_path,
        seed=31,
    )
    artifacts = summary["artifacts"]
    expected = {
        "mlflow_lineage",
        "splink_identity_resolution",
        "feast_registry",
        "feast_feature_view",
        "feast_offline_features",
        "feast_repo_config",
        "airflow_dag_metadata",
        "keycloak_oidc_readiness",
        "product_like_integrations",
    }
    assert expected.issubset(set(artifacts))
    for key in expected:
        assert Path(artifacts[key]).exists(), key

    manifest = json.loads(Path(artifacts["product_like_integrations"]).read_text(encoding="utf-8"))
    assert manifest["profile"] == "product_like"
    assert "feast_registry" in manifest["artifacts"]

    mlflow_payload = json.loads(Path(artifacts["mlflow_lineage"]).read_text(encoding="utf-8"))
    assert mlflow_payload["integration"] == "mlflow"
    assert mlflow_payload["status"] in {
        "executed",
        "adapter_ready_missing_dependency",
        "adapter_ready_execution_failed",
        "implemented_optional_not_enabled",
    }


def test_enforce_real_data_split_validation_blocks_strict_fail() -> None:
    with pytest.raises(RuntimeError, match="Strict real-data split validation failed"):
        _enforce_real_data_split_validation(
            use_case_id="UC-NBA-RET-001",
            source_data_metadata={"mode": "real_dataset"},
            model_metrics={
                "split_validation": {
                    "summary": {"failed_checks": 1},
                    "checks": [{"name": "holdout_rows_min", "status": "fail"}],
                }
            },
            strict_model_backends=True,
        )


def test_enforce_real_data_split_validation_noop_when_not_strict_or_not_real() -> None:
    _enforce_real_data_split_validation(
        use_case_id="UC-NBA-RET-001",
        source_data_metadata={"mode": "synthetic_fallback"},
        model_metrics={"split_validation": {"summary": {"failed_checks": 99}}},
        strict_model_backends=True,
    )
    _enforce_real_data_split_validation(
        use_case_id="UC-NBA-RET-001",
        source_data_metadata={"mode": "real_dataset"},
        model_metrics={"split_validation": {"summary": {"failed_checks": 99}}},
        strict_model_backends=False,
    )
