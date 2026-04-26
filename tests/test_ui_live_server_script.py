from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.ui_live_server import _validate_run_request, build_backend_command, load_run_history


def test_ui_live_server_help() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/ui_live_server.py", "--help"],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "--port" in result.stdout
    assert "Serve live UI + run API" in result.stdout


def test_build_backend_command_selected_use_case() -> None:
    cmd = build_backend_command(
        use_case_id="UC-NBA-RET-001",
        infra_profile="oss",
        seed=123,
        runtime_mode="synthetic_only",
        scenario_id="nba_high_risk_save",
        failure_injection=["dq_fail", "schema_fail"],
        strict_model_backends=True,
        source_data_root="data/production",
        require_real_data=True,
    )
    cmd_text = " ".join(cmd)

    assert "ui/adapter/build_view_model.py" in cmd_text
    assert "--runtime-mode execute_backend" in cmd_text
    assert "--infra-profile oss" in cmd_text
    assert "--seed 123" in cmd_text
    assert "--execution-mode synthetic_only" in cmd_text
    assert "--scenario-id nba_high_risk_save" in cmd_text
    assert "--failure-injection dq_fail" in cmd_text
    assert "--failure-injection schema_fail" in cmd_text
    assert "--use-case UC-NBA-RET-001" in cmd_text
    assert "--strict-model-backends" in cmd_text
    assert "--source-data-root data/production" in cmd_text
    assert "--require-real-data" in cmd_text


def test_validate_run_request_strict_model_backends_type() -> None:
    assert (
        _validate_run_request(
            {
                "use_case_id": "UC-NBA-RET-001",
                "infra_profile": "local",
                "seed": 101,
                "runtime_mode": "synthetic_only",
                "scenario_id": "nba_high_risk_save",
                "failure_injection": ["dq_fail"],
                "strict_model_backends": True,
                "source_data_root": "data/production",
                "require_real_data": True,
            }
        )
        is None
    )
    assert (
        _validate_run_request(
            {
                "use_case_id": "UC-NBA-RET-001",
                "infra_profile": "local",
                "seed": 101,
                "runtime_mode": "invalid",
            }
        )
        == "runtime_mode must be one of: default, synthetic_only."
    )
    assert (
        _validate_run_request(
            {
                "use_case_id": "UC-NBA-RET-001",
                "infra_profile": "local",
                "seed": 101,
                "strict_model_backends": "yes",
            }
        )
        == "strict_model_backends must be a boolean."
    )
    assert (
        _validate_run_request(
            {
                "use_case_id": "UC-NBA-RET-001",
                "infra_profile": "local",
                "seed": 101,
                "source_data_root": 123,
            }
        )
        == "source_data_root must be a string or null."
    )
    assert (
        _validate_run_request(
            {
                "use_case_id": "UC-NBA-RET-001",
                "infra_profile": "local",
                "seed": 101,
                "require_real_data": "true",
            }
        )
        == "require_real_data must be a boolean."
    )
    assert (
        _validate_run_request(
            {
                "use_case_id": "UC-NBA-RET-001",
                "infra_profile": "local",
                "seed": 101,
                "failure_injection": ["bad_flag"],
            }
        )
        == "failure_injection values must be one of: backend_unavailable, dq_fail, schema_fail"
    )


def test_load_run_history_sorted_and_stage_health(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    use_case_id = "UC-NBA-RET-001"
    older_run = artifacts_root / use_case_id / "20270101T010101Z"
    newer_run = artifacts_root / use_case_id / "20270102T010101Z"
    older_run.mkdir(parents=True, exist_ok=True)
    newer_run.mkdir(parents=True, exist_ok=True)

    older_files = _write_run_artifacts(older_run, include_model_predictions=True)
    newer_files = _write_run_artifacts(newer_run, include_model_predictions=False)

    _write_summary(
        run_dir=older_run,
        run_id="20270101T010101Z",
        artifact_paths=older_files,
        run_status="pass",
    )
    _write_summary(
        run_dir=newer_run,
        run_id="20270102T010101Z",
        artifact_paths=newer_files,
        run_status="fail",
    )

    payload = load_run_history(
        use_case_id=use_case_id,
        limit=5,
        artifacts_root=artifacts_root,
    )
    runs = payload["runs"]
    assert len(runs) == 2
    assert runs[0]["run_id"] == "20270102T010101Z"
    assert runs[1]["run_id"] == "20270101T010101Z"
    assert runs[0]["stage_total"] == 8
    assert runs[0]["stage_pass_count"] == 7
    assert runs[1]["stage_pass_count"] == 8


def test_load_run_history_filters_limit_status_and_infra(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    use_case_id = "UC-NBA-RET-001"

    run_local_pass = artifacts_root / use_case_id / "20270101T010101Z"
    run_oss_fail = artifacts_root / use_case_id / "20270102T010101Z"
    run_oss_pass = artifacts_root / use_case_id / "20270103T010101Z"
    run_local_pass.mkdir(parents=True, exist_ok=True)
    run_oss_fail.mkdir(parents=True, exist_ok=True)
    run_oss_pass.mkdir(parents=True, exist_ok=True)

    files_local_pass = _write_run_artifacts(run_local_pass, include_model_predictions=True)
    files_oss_fail = _write_run_artifacts(run_oss_fail, include_model_predictions=True)
    files_oss_pass = _write_run_artifacts(run_oss_pass, include_model_predictions=True)

    _write_summary(
        run_dir=run_local_pass,
        run_id="20270101T010101Z",
        artifact_paths=files_local_pass,
        run_status="pass",
        infra_profile="local",
    )
    _write_summary(
        run_dir=run_oss_fail,
        run_id="20270102T010101Z",
        artifact_paths=files_oss_fail,
        run_status="fail",
        infra_profile="oss",
    )
    _write_summary(
        run_dir=run_oss_pass,
        run_id="20270103T010101Z",
        artifact_paths=files_oss_pass,
        run_status="pass",
        infra_profile="oss",
    )

    payload = load_run_history(
        use_case_id=use_case_id,
        limit=1,
        status_filter="pass",
        infra_filter="oss",
        artifacts_root=artifacts_root,
    )
    runs = payload["runs"]

    assert payload["filters"] == {
        "limit": 1,
        "status": "pass",
        "infra": "oss",
        "baseline": "latest",
    }
    assert len(runs) == 1
    assert runs[0]["run_id"] == "20270103T010101Z"
    assert runs[0]["run_status"] == "pass"
    assert runs[0]["infra_profile"] == "oss"


def test_load_run_history_comparison_with_previous_baseline(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    use_case_id = "UC-NBA-RET-001"

    run_old = artifacts_root / use_case_id / "20270101T010101Z"
    run_mid = artifacts_root / use_case_id / "20270102T010101Z"
    run_new = artifacts_root / use_case_id / "20270103T010101Z"
    run_old.mkdir(parents=True, exist_ok=True)
    run_mid.mkdir(parents=True, exist_ok=True)
    run_new.mkdir(parents=True, exist_ok=True)

    files_old = _write_run_artifacts(run_old, include_model_predictions=True)
    files_mid = _write_run_artifacts(run_mid, include_model_predictions=False)
    files_new = _write_run_artifacts(run_new, include_model_predictions=True)

    _write_summary(
        run_dir=run_old,
        run_id="20270101T010101Z",
        artifact_paths=files_old,
        run_status="pass",
        avg_expected_uplift=0.17,
    )
    _write_summary(
        run_dir=run_mid,
        run_id="20270102T010101Z",
        artifact_paths=files_mid,
        run_status="fail",
        avg_expected_uplift=0.19,
    )
    _write_summary(
        run_dir=run_new,
        run_id="20270103T010101Z",
        artifact_paths=files_new,
        run_status="pass",
        avg_expected_uplift=0.25,
    )

    payload = load_run_history(
        use_case_id=use_case_id,
        limit=3,
        baseline="previous",
        artifacts_root=artifacts_root,
    )
    runs = payload["runs"]

    assert payload["baseline"]["requested"] == "previous"
    assert payload["baseline"]["resolved_run_id"] == "20270102T010101Z"
    assert payload["baseline"]["strategy"] == "previous"

    assert runs[0]["run_id"] == "20270103T010101Z"
    comparison = runs[0]["comparison"]
    assert comparison["baseline_run_id"] == "20270102T010101Z"
    assert comparison["status_transition"] == "fail->pass"
    assert comparison["status_changed"] is True
    assert comparison["stage_pass_delta"] == 1
    assert comparison["stage_status_changes"] == 1
    assert isinstance(comparison["stage_status_deltas"], list)
    assert any(row["changed"] is True for row in comparison["stage_status_deltas"])
    kpi_delta = next(
        row for row in comparison["kpi_deltas"] if row["name"] == "avg_expected_uplift"
    )
    assert round(float(kpi_delta["delta"]), 4) == 0.06

    assert runs[1]["run_id"] == "20270102T010101Z"
    mid_comparison = runs[1]["comparison"]
    assert mid_comparison["status_transition"] == "fail->fail"
    assert mid_comparison["status_changed"] is False
    assert mid_comparison["stage_pass_delta"] == 0


def _write_run_artifacts(run_dir: Path, include_model_predictions: bool) -> dict[str, str]:
    ingestion_dir = run_dir / "ingestion" / "event_bus"
    raw_dir = run_dir / "storage" / "raw"
    curated_dir = run_dir / "storage" / "curated"
    identity_dir = run_dir / "identity_360"
    feature_dir = run_dir / "features"
    model_dir = run_dir / "models"
    serving_dir = run_dir / "serving_activation"
    monitoring_dir = run_dir / "monitoring_governance"

    for directory in [
        ingestion_dir,
        raw_dir,
        curated_dir,
        identity_dir,
        feature_dir,
        model_dir,
        serving_dir,
        monitoring_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    topic_path = ingestion_dir / "topic.jsonl"
    topic_path.write_text(json.dumps({"payload": {"customer_id": "CUST-1"}}) + "\n", encoding="utf-8")

    raw_events = raw_dir / "events.jsonl"
    raw_events.write_text(json.dumps({"payload": {"customer_id": "CUST-1"}}) + "\n", encoding="utf-8")

    curated_records = curated_dir / "records.json"
    curated_records.write_text(json.dumps([{"customer_id": "CUST-1"}]), encoding="utf-8")

    resolved_records = identity_dir / "resolved_records.json"
    resolved_records.write_text(json.dumps([{"unified_customer_id": "U-CUST-1"}]), encoding="utf-8")

    feature_rows = feature_dir / "feature_rows.json"
    feature_rows.write_text(json.dumps([{"customer_id": "U-CUST-1", "risk_score": 0.4}]), encoding="utf-8")

    activation_payloads = serving_dir / "activation_payloads.json"
    activation_payloads.write_text(json.dumps([{"destination": "campaign"}]), encoding="utf-8")

    monitoring_report = monitoring_dir / "report.json"
    monitoring_report.write_text(json.dumps({"run_status": "pass"}), encoding="utf-8")

    model_predictions = model_dir / "predictions.json"
    if include_model_predictions:
        model_predictions.write_text(
            json.dumps({"rows": [{"customer_id": "U-CUST-1"}], "metrics": {"primary_kpi": "lift"}}),
            encoding="utf-8",
        )

    return {
        "ingestion_event_bus": {"raw.uc_nba_ret_001.crm_customers.v1": str(topic_path)},
        "raw_events": str(raw_events),
        "curated_records": str(curated_records),
        "resolved_records": str(resolved_records),
        "feature_rows": str(feature_rows),
        "model_predictions": str(model_predictions),
        "activation_payloads": str(activation_payloads),
        "monitoring_report": str(monitoring_report),
    }


def _write_summary(
    run_dir: Path,
    run_id: str,
    artifact_paths: dict[str, object],
    run_status: str,
    infra_profile: str = "local",
    avg_expected_uplift: float = 0.21,
) -> None:
    summary = {
        "use_case_id": "UC-NBA-RET-001",
        "run_id": run_id,
        "infra_profile": infra_profile,
        "seed": 101,
        "run_status": run_status,
        "records": {
            "source_tables": {"crm_customers": 1},
            "curated_rows": 1,
            "feature_rows": 1,
            "model_rows": 1,
            "activation_rows": 1,
        },
        "model_metrics": {
            "primary_kpi": "retention_lift",
            "avg_expected_uplift": avg_expected_uplift,
        },
        "artifacts": artifact_paths,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
