from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.ui_live_server as ui_live_server
from scripts.ui_live_server import (
    _validate_governance_approve_request,
    _validate_inference_request,
    build_api_error_payload,
    build_inference_contract_export,
    build_openapi_spec,
    build_prometheus_metrics,
    load_portfolio_summary,
    load_run_data_quality_details,
    load_run_registry,
    load_run_summary_details,
    load_run_stage_details,
    load_enterprise_hardening,
    parse_run_data_quality_path,
    parse_run_stages_path,
    parse_run_summary_path,
    parse_portfolio_summary_query,
    parse_run_registry_query,
    resolve_artifact_download_path,
    run_inference_batch,
    run_inference_online,
)
from stack.model_registry import register_model_candidate_from_summary


def test_parse_run_registry_query_valid() -> None:
    filters, error = parse_run_registry_query(
        query={
            "use_case_id": ["UC-NBA-RET-001"],
            "limit": ["7"],
            "offset": ["2"],
            "status": ["pass"],
            "infra": ["oss"],
            "seed": ["101"],
            "sort": ["asc"],
            "q": ["uplift"],
        }
    )

    assert error is None
    assert filters == {
        "use_case_id": "UC-NBA-RET-001",
        "limit": 7,
        "offset": 2,
        "status_filter": "pass",
        "infra_filter": "oss",
        "seed": 101,
        "sort": "asc",
        "query": "uplift",
    }


def test_parse_run_registry_query_validation_errors() -> None:
    _, error_limit = parse_run_registry_query(query={"limit": ["x"]})
    _, error_status = parse_run_registry_query(query={"status": ["maybe"]})
    _, error_infra = parse_run_registry_query(query={"infra": ["edge"]})
    _, error_seed = parse_run_registry_query(query={"seed": ["abc"]})
    _, error_sort = parse_run_registry_query(query={"sort": ["newest"]})

    assert "limit" in str(error_limit)
    assert "status" in str(error_status)
    assert "infra" in str(error_infra)
    assert "seed" in str(error_seed)
    assert "sort" in str(error_sort)


def test_load_run_registry_filters_and_pagination(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-NBA-RET-001",
        run_id="20270101T010101Z",
        run_status="pass",
        infra_profile="local",
        seed=101,
    )
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-NBA-RET-001",
        run_id="20270102T010101Z",
        run_status="pass",
        infra_profile="oss",
        seed=101,
    )
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-CHURN-RET-002",
        run_id="20270103T010101Z",
        run_status="fail",
        infra_profile="oss",
        seed=202,
    )

    payload = load_run_registry(
        artifacts_root=artifacts_root,
        use_case_id="UC-NBA-RET-001",
        status_filter="pass",
        infra_filter="oss",
        seed=101,
        limit=1,
        offset=0,
        sort="desc",
        query="retention_lift",
    )

    assert payload["count"] == 1
    assert payload["total"] == 1
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert payload["runs"][0]["use_case_id"] == "UC-NBA-RET-001"
    assert payload["runs"][0]["run_status"] == "pass"
    assert payload["runs"][0]["infra_profile"] == "oss"


def test_parse_portfolio_summary_query_valid_and_errors() -> None:
    filters, error = parse_portfolio_summary_query(
        query={
            "status": ["pass"],
            "infra": ["oss"],
            "sort": ["asc"],
            "limit_per_use_case": ["3"],
        }
    )
    assert error is None
    assert filters == {
        "status_filter": "pass",
        "infra_filter": "oss",
        "sort": "asc",
        "limit_per_use_case": 3,
    }

    _, error_bad_status = parse_portfolio_summary_query(query={"status": ["unknown"]})
    _, error_bad_limit = parse_portfolio_summary_query(query={"limit_per_use_case": ["x"]})
    assert "status" in str(error_bad_status)
    assert "limit_per_use_case" in str(error_bad_limit)


def test_standardized_api_error_payload_shape() -> None:
    payload = build_api_error_payload(
        code="invalid_query",
        message="bad query",
        details={"field": "status"},
    )
    assert payload["error"] == "bad query"
    assert payload["error_code"] == "invalid_query"
    assert payload["details"] == {"field": "status"}


def test_build_inference_contract_export_contains_all_use_cases() -> None:
    payload = build_inference_contract_export()
    assert payload["schema_version"] == "1.0.0"
    assert payload["endpoints"]["online"] == "/api/inference/online"
    assert payload["endpoints"]["batch"] == "/api/inference/batch"

    use_cases = payload["use_cases"]
    assert len(use_cases) == 4
    nba = next(row for row in use_cases if row["use_case_id"] == "UC-NBA-RET-001")
    assert "schemas" in nba
    assert "online_request" in nba["schemas"]
    assert "online_response" in nba["schemas"]
    assert "record" in nba["schemas"]["online_request"]["properties"]
    assert nba["schemas"]["batch_request"]["properties"]["records"]["type"] == "array"


def test_build_openapi_spec_includes_inference_paths_and_components() -> None:
    payload = build_openapi_spec(base_url="http://127.0.0.1:8080")
    assert payload["openapi"] == "3.1.0"
    assert payload["servers"][0]["url"] == "http://127.0.0.1:8080"

    paths = payload["paths"]
    assert "/api/inference/online" in paths
    assert "/api/inference/batch" in paths
    assert "/api/contracts/inference" in paths
    assert "/api/openapi.json" in paths
    assert "/api/governance/approve" in paths

    schemas = payload["components"]["schemas"]
    assert "ApiError" in schemas
    assert "InferenceContractExport" in schemas

    online_req = paths["/api/inference/online"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["oneOf"]
    batch_req = paths["/api/inference/batch"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["oneOf"]
    assert len(online_req) == 4
    assert len(batch_req) == 4


def test_validate_governance_approve_request_contract_errors() -> None:
    valid_error = _validate_governance_approve_request(
        {
            "use_case_id": "UC-NBA-RET-001",
            "run_id": "20270101T010101Z",
            "approved_by": "qa-user",
            "note": "looks good",
            "accept_warnings": ["table.check_a"],
            "accept_all_warnings": False,
            "warning_rationale": "accepted for release",
            "force": False,
        }
    )
    assert valid_error is None

    use_case_error = _validate_governance_approve_request({"run_id": "20270101T010101Z"})
    run_id_error = _validate_governance_approve_request(
        {"use_case_id": "UC-NBA-RET-001"}
    )
    warnings_type_error = _validate_governance_approve_request(
        {
            "use_case_id": "UC-NBA-RET-001",
            "run_id": "20270101T010101Z",
            "accept_warnings": "table.check",
        }
    )
    unknown_field_error = _validate_governance_approve_request(
        {
            "use_case_id": "UC-NBA-RET-001",
            "run_id": "20270101T010101Z",
            "surprise": "x",
        }
    )

    assert "use_case_id" in str(use_case_error)
    assert "run_id" in str(run_id_error)
    assert "accept_warnings" in str(warnings_type_error)
    assert "Unknown request field" in str(unknown_field_error)


def test_validate_inference_request_contract_errors() -> None:
    valid_online_error = _validate_inference_request(
        payload={
            "use_case_id": "UC-NBA-RET-001",
            "registry_stage": "auto",
            "record": {
                "customer_id": "CUST-1",
                "risk_score": 0.62,
                "value_score": 0.51,
                "score_ts": "2026-04-22T10:30:00Z",
            },
        },
        mode="online",
    )
    assert valid_online_error is None

    missing_record_error = _validate_inference_request(
        payload={"use_case_id": "UC-NBA-RET-001"},
        mode="online",
    )
    bad_type_error = _validate_inference_request(
        payload={
            "use_case_id": "UC-NBA-RET-001",
            "record": {
                "customer_id": "CUST-1",
                "risk_score": "0.62",
                "value_score": 0.51,
                "score_ts": "2026-04-22T10:30:00Z",
            },
        },
        mode="online",
    )
    unknown_field_error = _validate_inference_request(
        payload={
            "use_case_id": "UC-NBA-RET-001",
            "records": [
                {
                    "customer_id": "CUST-1",
                    "risk_score": 0.62,
                    "value_score": 0.51,
                    "score_ts": "2026-04-22T10:30:00Z",
                    "unexpected": "x",
                }
            ],
        },
        mode="batch",
    )

    assert "record must be an object" in str(missing_record_error)
    assert "must satisfy type 'number'" in str(bad_type_error)
    assert "unsupported field" in str(unknown_field_error)


def test_run_inference_online_returns_model_version_and_registry_stage(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    _register_candidate_entry(
        artifacts_root=artifacts_root,
        use_case_id="UC-NBA-RET-001",
        run_id="20270120T010101Z",
        model_version="nba_retention_tf_v2",
        model_backend="tensorflow",
    )

    payload = run_inference_online(
        use_case_id="UC-NBA-RET-001",
        record={
            "customer_id": "CUST-42",
            "risk_score": 0.66,
            "value_score": 0.58,
            "score_ts": "2026-04-22T11:00:00Z",
        },
        seed=101,
        registry_stage="auto",
        artifacts_root=artifacts_root,
    )

    assert payload["mode"] == "online"
    assert payload["registry_stage"] == "candidate"
    assert payload["model_version"] != "unknown"
    assert payload["prediction_count"] == 1
    assert payload["activation_count"] == 1
    assert payload["registry"]["registered"] is True
    assert payload["registry"]["run_id"] == "20270120T010101Z"
    assert "customer_id" in payload["prediction"]
    assert "destination" in payload["activation"]


def test_run_inference_batch_contract_and_stage_resolution(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    payload = run_inference_batch(
        use_case_id="UC-INCR-MKT-004",
        records=[
            {
                "campaign_id": "CMP-1",
                "test_window": "2026-W10",
                "treated_customers": 2100,
                "control_customers": 700,
                "treated_conversions": 256,
                "control_conversions": 74,
                "aov": 98.5,
                "campaign_cost": 15000.0,
            },
            {
                "campaign_id": "CMP-2",
                "test_window": "2026-W11",
                "treated_customers": 2300,
                "control_customers": 760,
                "treated_conversions": 281,
                "control_conversions": 80,
                "aov": 102.5,
                "campaign_cost": 16300.0,
            },
        ],
        seed=101,
        registry_stage="auto",
        artifacts_root=artifacts_root,
    )

    assert payload["mode"] == "batch"
    assert payload["registry_stage"] == "unregistered"
    assert payload["record_count"] == 2
    assert payload["prediction_count"] == 2
    assert payload["activation_count"] == 2
    assert len(payload["output_contract"]["fields"]) > 0
    assert len(payload["activation_contract"]["fields"]) > 0

    with pytest.raises(ValueError, match="No model-registry entry found"):
        run_inference_online(
            use_case_id="UC-NBA-RET-001",
            record={
                "customer_id": "CUST-1",
                "risk_score": 0.31,
                "value_score": 0.45,
                "score_ts": "2026-04-22T10:30:00Z",
            },
            registry_stage="prod",
            artifacts_root=artifacts_root,
        )


def test_parse_run_paths_for_summary_stages_and_data_quality() -> None:
    summary_parsed, summary_error = parse_run_summary_path(
        "/api/runs/UC-NBA-RET-001/20270101T010101Z"
    )
    assert summary_error is None
    assert summary_parsed["use_case_id"] == "UC-NBA-RET-001"
    assert summary_parsed["run_id"] == "20270101T010101Z"

    stages_parsed, stages_error = parse_run_stages_path(
        "/api/runs/UC-NBA-RET-001/20270101T010101Z/stages"
    )
    assert stages_error is None
    assert stages_parsed["use_case_id"] == "UC-NBA-RET-001"
    assert stages_parsed["run_id"] == "20270101T010101Z"

    dq_parsed, dq_error = parse_run_data_quality_path(
        "/api/runs/UC-NBA-RET-001/20270101T010101Z/data-quality"
    )
    assert dq_error is None
    assert dq_parsed["use_case_id"] == "UC-NBA-RET-001"
    assert dq_parsed["run_id"] == "20270101T010101Z"

    _, bad_summary_error = parse_run_summary_path("/api/runs/UC-NBA-RET-001")
    _, bad_stages_error = parse_run_stages_path("/api/runs/UC-NBA-RET-001/only")
    _, bad_dq_error = parse_run_data_quality_path("/api/runs/UC-NBA-RET-001/only")
    assert "Path must be /api/runs/<use_case_id>/<run_id>" in str(bad_summary_error)
    assert "Path must be /api/runs/<use_case_id>/<run_id>/stages" in str(bad_stages_error)
    assert "Path must be /api/runs/<use_case_id>/<run_id>/data-quality" in str(
        bad_dq_error
    )


def test_resolve_artifact_download_path_safety(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    run_dir = artifacts_root / "UC-NBA-RET-001" / "20270101T010101Z"
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = run_dir / "summary.json"
    artifact_path.write_text('{"ok": true}', encoding="utf-8")

    monkeypatch.setattr(ui_live_server, "ROOT", tmp_path)

    resolved, error = resolve_artifact_download_path(
        path_text="artifacts/UC-NBA-RET-001/20270101T010101Z/summary.json",
        artifacts_root=artifacts_root,
    )
    assert error is None
    assert resolved == artifact_path.resolve()

    blocked, blocked_error = resolve_artifact_download_path(
        path_text="/etc/passwd",
        artifacts_root=artifacts_root,
    )
    assert blocked is None
    assert "within repository root" in str(blocked_error)


def test_load_enterprise_hardening_statuses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "enterprise_hardening.json"
    config_path.write_text(
        json.dumps(
            {
                "modules": {
                    "mlflow": {"enabled": True},
                    "feast": {"enabled": True},
                    "splink": {"enabled": False},
                    "airflow": {"enabled": False},
                    "keycloak": {"enabled": False},
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(ui_live_server, "ENTERPRISE_HARDENING_CONFIG_PATH", config_path)
    monkeypatch.setattr(
        ui_live_server,
        "_module_available",
        lambda import_name: import_name in {"mlflow", "splink"},
    )

    payload = load_enterprise_hardening(profile="product_like")
    assert payload["profile"] == "product_like"
    assert payload["summary"]["module_count"] == 8
    assert payload["summary"]["enabled_count"] == 2
    assert payload["summary"]["ready_count"] == 2

    by_id = {row["module_id"]: row for row in payload["modules"]}
    assert by_id["mlflow"]["status"] == "implemented"
    assert by_id["feast"]["status"] == "implemented"
    assert by_id["feast"]["runtime_status"] == "adapter_ready_missing_dependency"
    assert by_id["splink"]["status"] == "available"
    assert by_id["keycloak"]["status"] == "planned"
    assert by_id["data_quality_artifacts"]["activation_mode"] == "built_in"


def test_load_enterprise_hardening_profile_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_path = tmp_path / "enterprise_hardening.json"
    config_path.write_text(
        json.dumps(
            {
                "profiles": {
                    "standalone": {"modules": {"mlflow": False, "data_quality_artifacts": True}},
                    "product_like": {"modules": {"mlflow": True, "data_quality_artifacts": True}},
                },
                "modules": {
                    "mlflow": {"enabled": False},
                    "data_quality_artifacts": {"enabled": True},
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(ui_live_server, "ENTERPRISE_HARDENING_CONFIG_PATH", config_path)
    monkeypatch.setattr(ui_live_server, "_module_available", lambda import_name: import_name == "mlflow")

    standalone = load_enterprise_hardening(profile="standalone")
    product_like = load_enterprise_hardening(profile="product_like")

    standalone_by_id = {row["module_id"]: row for row in standalone["modules"]}
    product_by_id = {row["module_id"]: row for row in product_like["modules"]}

    assert standalone_by_id["mlflow"]["configured"] is False
    assert product_by_id["mlflow"]["configured"] is True
    assert product_by_id["mlflow"]["status"] == "implemented"


def test_build_prometheus_metrics_from_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "UC-NBA-RET-001" / "20270107T010101Z"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "use_case_id": "UC-NBA-RET-001",
                "run_id": "20270107T010101Z",
                "run_status": "pass",
                "records": {"model_rows": 3},
                "telemetry": {"stages": [{"layer_id": "data_sources"}]},
            }
        ),
        encoding="utf-8",
    )

    metrics = build_prometheus_metrics(artifacts_root=tmp_path)

    assert 'cdp_run_total{status="pass"} 1' in metrics
    assert 'cdp_latest_run_status{use_case_id="UC-NBA-RET-001",run_id="20270107T010101Z"} 1' in metrics
    assert 'record_type="model_rows"' in metrics


def test_load_run_stage_details(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    use_case_id = "UC-NBA-RET-001"
    run_id = "20270105T010101Z"
    run_dir = artifacts_root / use_case_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    artifact_paths = _write_stage_artifacts(run_dir=run_dir)
    _write_stage_summary(
        run_dir=run_dir,
        use_case_id=use_case_id,
        run_id=run_id,
        infra_profile="oss",
        run_status="pass",
        artifact_paths=artifact_paths,
    )

    payload = load_run_stage_details(
        use_case_id=use_case_id,
        run_id=run_id,
        artifacts_root=artifacts_root,
    )
    assert payload is not None
    assert payload["use_case_id"] == use_case_id
    assert payload["run_id"] == run_id
    assert payload["stage_total"] == 8
    assert payload["stage_pass_count"] >= 7
    assert payload["summary_path"] == f"artifacts/{use_case_id}/{run_id}/summary.json"

    model_stage = next(row for row in payload["stages"] if row["layer_id"] == "model_layer")
    assert model_stage["status"] in {"pass", "fail"}
    assert any(str(item.get("name", "")).startswith("metric:") for item in model_stage["outputs"])
    assert all(
        not str(item.get("path", "")).startswith(str(tmp_path))
        for item in model_stage["outputs"]
    )

    missing = load_run_stage_details(
        use_case_id=use_case_id,
        run_id="does-not-exist",
        artifacts_root=artifacts_root,
    )
    assert missing is None


def test_load_run_summary_details_inlines_monitoring_report(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    use_case_id = "UC-NBA-RET-001"
    run_id = "20270105T020202Z"
    run_dir = artifacts_root / use_case_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    artifact_paths = _write_stage_artifacts(run_dir=run_dir)
    _write_stage_summary(
        run_dir=run_dir,
        use_case_id=use_case_id,
        run_id=run_id,
        infra_profile="oss",
        run_status="pass",
        artifact_paths=artifact_paths,
    )
    Path(str(artifact_paths["monitoring_report"])).write_text(
        json.dumps({"validation_gates": {"data_quality": "pass", "model_quality": "pass"}}),
        encoding="utf-8",
    )

    payload = load_run_summary_details(
        use_case_id=use_case_id,
        run_id=run_id,
        artifacts_root=artifacts_root,
    )

    assert payload is not None
    assert payload["run_id"] == run_id
    assert payload["summary_path"] == f"artifacts/{use_case_id}/{run_id}/summary.json"
    assert payload["artifacts"]["model_predictions"].startswith("artifacts/")
    assert not payload["artifacts"]["model_predictions"].startswith(str(tmp_path))
    assert payload["monitoring_report"]["validation_gates"]["data_quality"] == "pass"
    assert payload["monitoring_report"]["validation_gates"]["model_quality"] == "pass"

    missing = load_run_summary_details(
        use_case_id=use_case_id,
        run_id="does-not-exist",
        artifacts_root=artifacts_root,
    )
    assert missing is None


def test_load_run_data_quality_details(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    use_case_id = "UC-NBA-RET-001"
    run_id = "20270106T010101Z"
    run_dir = artifacts_root / use_case_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    artifact_paths = _write_stage_artifacts(run_dir=run_dir)
    _write_stage_summary(
        run_dir=run_dir,
        use_case_id=use_case_id,
        run_id=run_id,
        infra_profile="oss",
        run_status="fail",
        artifact_paths=artifact_paths,
    )

    monitoring_report_path = Path(str(artifact_paths["monitoring_report"]))
    monitoring_payload = {
        "deployment_readiness": {
            "status": "blocked",
            "failed_data_quality_checks": ["crm_customers.unique_key_customer_id"],
            "warning_data_quality_checks": ["behavior_signals.range_observed_uplift"],
        },
        "data_quality": {
            "status": "fail",
            "mode": "real_dataset",
            "reason": None,
            "checks": [
                {
                    "table": "crm_customers",
                    "name": "unique_key_customer_id",
                    "status": "fail",
                    "severity": "fail",
                    "reason": "Duplicate customer IDs",
                    "violation_count": 2,
                },
                {
                    "table": "behavior_signals",
                    "name": "range_observed_uplift",
                    "status": "warn",
                    "severity": "warn",
                    "reason": "Some uplift values exceeded expected bounds",
                    "violation_count": 1,
                },
                {
                    "table": "behavior_signals",
                    "name": "range_risk_score",
                    "status": "pass",
                    "severity": "fail",
                    "reason": "within expected bounds",
                    "violation_count": 0,
                },
            ],
        },
    }
    monitoring_report_path.write_text(json.dumps(monitoring_payload), encoding="utf-8")

    payload = load_run_data_quality_details(
        use_case_id=use_case_id,
        run_id=run_id,
        artifacts_root=artifacts_root,
    )
    assert payload is not None
    assert payload["use_case_id"] == use_case_id
    assert payload["run_id"] == run_id
    assert payload["data_quality_status"] == "fail"
    assert payload["data_quality_mode"] == "real_dataset"
    assert payload["blocker_count"] == 1
    assert payload["warning_count"] == 1
    assert payload["blocker_names"] == ["crm_customers.unique_key_customer_id"]
    assert payload["warning_names"] == ["behavior_signals.range_observed_uplift"]
    assert payload["blockers"][0]["reason"] == "Duplicate customer IDs"
    assert payload["warnings"][0]["violation_count"] == 1

    missing = load_run_data_quality_details(
        use_case_id=use_case_id,
        run_id="does-not-exist",
        artifacts_root=artifacts_root,
    )
    assert missing is None


def test_load_portfolio_summary_cross_use_case_rollup(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-NBA-RET-001",
        run_id="20270101T010101Z",
        run_status="pass",
        infra_profile="local",
        seed=101,
    )
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-CHURN-RET-002",
        run_id="20270102T010101Z",
        run_status="fail",
        infra_profile="oss",
        seed=202,
    )
    _write_summary(
        artifacts_root=artifacts_root,
        use_case_id="UC-CHURN-RET-002",
        run_id="20270103T010101Z",
        run_status="pass",
        infra_profile="oss",
        seed=203,
    )

    payload = load_portfolio_summary(
        status_filter="all",
        infra_filter="all",
        sort="desc",
        limit_per_use_case=1,
        artifacts_root=artifacts_root,
    )
    assert payload["totals"]["use_case_count"] == 2
    assert len(payload["latest_by_use_case"]) == 2
    assert len(payload["kpi_comparison"]) == 2
    assert payload["index"]["used"] is True


def _write_summary(
    *,
    artifacts_root: Path,
    use_case_id: str,
    run_id: str,
    run_status: str,
    infra_profile: str,
    seed: int,
) -> None:
    run_dir = artifacts_root / use_case_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "use_case_id": use_case_id,
        "run_id": run_id,
        "name": "test-run",
        "infra_profile": infra_profile,
        "seed": seed,
        "run_status": run_status,
        "records": {
            "curated_rows": 10,
            "feature_rows": 10,
            "model_rows": 10,
            "activation_rows": 10,
        },
        "model_metrics": {
            "primary_kpi": "retention_lift",
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


def _write_stage_artifacts(*, run_dir: Path) -> dict[str, object]:
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
    raw_events = raw_dir / "events.jsonl"
    curated_records = curated_dir / "records.json"
    resolved_records = identity_dir / "resolved_records.json"
    feature_rows = feature_dir / "feature_rows.json"
    model_predictions = model_dir / "predictions.json"
    activation_payloads = serving_dir / "activation_payloads.json"
    monitoring_report = monitoring_dir / "report.json"

    topic_path.write_text(json.dumps({"payload": {"customer_id": "CUST-1"}}) + "\n", encoding="utf-8")
    raw_events.write_text(json.dumps({"payload": {"customer_id": "CUST-1"}}) + "\n", encoding="utf-8")
    curated_records.write_text(json.dumps([{"customer_id": "CUST-1"}]), encoding="utf-8")
    resolved_records.write_text(json.dumps([{"unified_customer_id": "U-CUST-1"}]), encoding="utf-8")
    feature_rows.write_text(json.dumps([{"customer_id": "U-CUST-1", "risk_score": 0.3}]), encoding="utf-8")
    model_predictions.write_text(
        json.dumps({"rows": [{"customer_id": "U-CUST-1"}], "metrics": {"primary_kpi": "retention_lift"}}),
        encoding="utf-8",
    )
    activation_payloads.write_text(json.dumps([{"destination": "campaign"}]), encoding="utf-8")
    monitoring_report.write_text(
        json.dumps({"deployment_readiness": {"status": "ready"}}),
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


def _write_stage_summary(
    *,
    run_dir: Path,
    use_case_id: str,
    run_id: str,
    infra_profile: str,
    run_status: str,
    artifact_paths: dict[str, object],
) -> None:
    summary = {
        "use_case_id": use_case_id,
        "name": "stage-test",
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
            "retention_lift": 0.22,
        },
        "artifacts": artifact_paths,
        "summary_path": str((run_dir / "summary.json").as_posix()),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


def _register_candidate_entry(
    *,
    artifacts_root: Path,
    use_case_id: str,
    run_id: str,
    model_version: str,
    model_backend: str,
) -> None:
    run_dir = artifacts_root / use_case_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "use_case_id": use_case_id,
        "name": "registry-fixture",
        "run_id": run_id,
        "seed": 101,
        "infra_profile": "local",
        "run_status": "pass",
        "model_metrics": {
            "primary_kpi": "retention_lift",
            "model_version": model_version,
            "model_backend": model_backend,
        },
        "artifacts": {},
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    register_model_candidate_from_summary(
        summary=summary,
        artifacts_root=artifacts_root,
        summary_path=summary_path,
    )
