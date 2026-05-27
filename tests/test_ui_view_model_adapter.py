from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ui.adapter.build_view_model import (
    RUNTIME_MODE_EXECUTE,
    apply_runtime_overrides,
    build_view_model,
    load_runtime_settings,
)


def _write_minimal_nba_run(artifacts_root: Path) -> Path:
    """Create a compact latest-run fixture for adapter shape tests."""
    run_dir = artifacts_root / "UC-NBA-RET-001" / "20270101T000000Z"
    run_dir.mkdir(parents=True, exist_ok=True)

    artifact_paths = {
        "topic": run_dir / "ingestion" / "event_bus" / "topic.jsonl",
        "raw_events": run_dir / "storage" / "raw" / "events.jsonl",
        "curated_records": run_dir / "storage" / "curated" / "records.json",
        "resolved_records": run_dir / "identity_360" / "resolved_records.json",
        "feature_rows": run_dir / "features" / "feature_rows.json",
        "model_predictions": run_dir / "models" / "predictions.json",
        "activation_payloads": run_dir / "serving_activation" / "activation_payloads.json",
        "monitoring_report": run_dir / "monitoring_governance" / "report.json",
    }
    for path in artifact_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    artifact_paths["topic"].write_text(
        json.dumps({"payload": {"customer_id": "CUST-001"}}) + "\n",
        encoding="utf-8",
    )
    artifact_paths["raw_events"].write_text(
        json.dumps({"topic": "raw", "payload": {"customer_id": "CUST-001"}}) + "\n",
        encoding="utf-8",
    )
    artifact_paths["curated_records"].write_text(
        json.dumps([{"customer_id": "CUST-001"}]),
        encoding="utf-8",
    )
    artifact_paths["resolved_records"].write_text(
        json.dumps([{"unified_customer_id": "U-CUST-001"}]),
        encoding="utf-8",
    )
    artifact_paths["feature_rows"].write_text(
        json.dumps([{"customer_id": "U-CUST-001", "risk_score": 0.2}]),
        encoding="utf-8",
    )
    artifact_paths["model_predictions"].write_text(
        json.dumps(
            {
                "metrics": {"primary_kpi": "retention_lift"},
                "rows": [{"customer_id": "U-CUST-001"}],
            }
        ),
        encoding="utf-8",
    )
    artifact_paths["activation_payloads"].write_text(
        json.dumps([{"destination": "campaign_orchestrator"}]),
        encoding="utf-8",
    )
    artifact_paths["monitoring_report"].write_text(
        json.dumps({"run_status": "pass", "validation_gates": {"contract_tests_pass": "pass"}}),
        encoding="utf-8",
    )

    summary = {
        "use_case_id": "UC-NBA-RET-001",
        "name": "Next Best Action for Retention",
        "run_id": run_dir.name,
        "seed": 77,
        "infra_profile": "local",
        "records": {
            "source_tables": {"crm_customers": 1},
            "curated_rows": 1,
            "feature_rows": 1,
        },
        "model_metrics": {"primary_kpi": "retention_lift"},
        "run_status": "pass",
        "artifacts": {
            "ingestion_event_bus": {
                "raw.uc_nba_ret_001.crm_customers.v1": artifact_paths["topic"].as_posix()
            },
            "raw_events": artifact_paths["raw_events"].as_posix(),
            "curated_records": artifact_paths["curated_records"].as_posix(),
            "resolved_records": artifact_paths["resolved_records"].as_posix(),
            "feature_rows": artifact_paths["feature_rows"].as_posix(),
            "model_predictions": artifact_paths["model_predictions"].as_posix(),
            "activation_payloads": artifact_paths["activation_payloads"].as_posix(),
            "monitoring_report": artifact_paths["monitoring_report"].as_posix(),
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return run_dir


def test_ui_schema_file_is_valid_json() -> None:
    schema_path = Path("ui/contracts/view_model.schema.json")
    assert schema_path.exists()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["type"] == "object"
    assert "use_cases" in schema["properties"]


def test_runtime_config_loader_and_overrides(tmp_path: Path) -> None:
    runtime_config = tmp_path / "runtime.yaml"
    runtime_config.write_text(
        "\n".join(
            [
                "mode: execute_backend",
                "execution:",
                "  infra_profile: oss",
                "  seed: 55",
                "  output_dir: artifacts",
                "  strict_model_backends: true",
            ]
        ),
        encoding="utf-8",
    )

    settings, warnings = load_runtime_settings(runtime_config)
    assert not warnings
    assert settings["mode"] == RUNTIME_MODE_EXECUTE
    assert settings["execution"]["infra_profile"] == "oss"
    assert settings["execution"]["seed"] == 55
    assert settings["execution"]["strict_model_backends"] is True

    class _Args:
        runtime_mode = None
        run_backend = False
        use_case = "UC-NBA-RET-001"
        infra_profile = "local"
        seed = 99
        output_dir = None
        oss_compose_file = None
        strict_model_backends = False

    merged = apply_runtime_overrides(settings=settings, args=_Args())
    assert merged["execution"]["use_case_id"] == "UC-NBA-RET-001"
    assert merged["execution"]["infra_profile"] == "local"
    assert merged["execution"]["seed"] == 99
    assert merged["execution"]["strict_model_backends"] is True


def test_ui_view_model_script_generates_expected_shape(tmp_path: Path) -> None:
    output_path = tmp_path / "view_model.json"
    artifacts_root = tmp_path / "artifacts"
    _write_minimal_nba_run(artifacts_root)

    subprocess.run(
        [
            sys.executable,
            "ui/adapter/build_view_model.py",
            "--output",
            str(output_path),
            "--artifacts-root",
            str(artifacts_root),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["meta"]["schema_version"] == "1.0.0"
    assert "runtime" in payload["meta"]
    assert len(payload["platform_flow"]) == 8
    assert payload["platform_flow"][0]["label"] == "Data Sources"
    assert payload["platform_flow"][-1]["label"] == "Monitoring + Governance"

    use_case_ids = {row["use_case_id"] for row in payload["use_cases"]}
    assert use_case_ids == {
        "UC-NBA-RET-001",
        "UC-CHURN-RET-002",
        "UC-MMM-PLN-003",
        "UC-INCR-MKT-004",
    }

    nba = [row for row in payload["use_cases"] if row["use_case_id"] == "UC-NBA-RET-001"][0]
    assert nba["latest_run"] is not None
    guided_steps = nba["latest_run"].get("guided_steps", [])
    assert len(guided_steps) == 8
    assert guided_steps[0]["layer_id"] == "data_sources"
    assert guided_steps[-1]["layer_id"] == "monitoring_governance"


def test_ui_view_model_compacts_large_oss_runtime_sections(tmp_path: Path) -> None:
    artifacts_root = tmp_path / "artifacts"
    run_dir = artifacts_root / "UC-NBA-RET-001" / "20270101T000000Z"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "use_case_id": "UC-NBA-RET-001",
        "name": "Next Best Action for Retention",
        "run_id": "20270101T000000Z",
        "seed": 77,
        "infra_profile": "oss",
        "records": {"source_tables": {"crm_customers": 1}},
        "model_metrics": {"primary_kpi": "retention_lift"},
        "run_status": "pass",
        "artifacts": {
            "ingestion_event_bus": {
                "raw.uc_nba_ret_001.crm_customers.v1": "artifacts/UC-NBA-RET-001/20270101T000000Z/ingestion/event_bus/topic.jsonl"
            },
            "raw_events": "artifacts/UC-NBA-RET-001/20270101T000000Z/storage/raw/events.jsonl",
            "curated_records": "artifacts/UC-NBA-RET-001/20270101T000000Z/storage/curated/records.json",
            "resolved_records": "artifacts/UC-NBA-RET-001/20270101T000000Z/identity_360/resolved_records.json",
            "feature_rows": "artifacts/UC-NBA-RET-001/20270101T000000Z/features/feature_rows.json",
            "model_predictions": "artifacts/UC-NBA-RET-001/20270101T000000Z/models/predictions.json",
            "activation_payloads": "artifacts/UC-NBA-RET-001/20270101T000000Z/serving_activation/activation_payloads.json",
            "monitoring_report": "artifacts/UC-NBA-RET-001/20270101T000000Z/monitoring_governance/report.json",
        },
        "oss_runtime": {
            "status": "executed",
            "kafka_topics_published": 1,
            "kafka_messages_consumed": 1,
            "postgres_rows_loaded": 1,
            "minio_objects_uploaded": 1,
            "warnings": [],
            "ingestion_event_bus": {"raw.uc_nba_ret_001.crm_customers.v1": "topic-path"},
            "curated_rows": [{"customer_id": "CUST-001"}],
        },
    }

    (run_dir / "ingestion" / "event_bus").mkdir(parents=True, exist_ok=True)
    (run_dir / "storage" / "raw").mkdir(parents=True, exist_ok=True)
    (run_dir / "storage" / "curated").mkdir(parents=True, exist_ok=True)
    (run_dir / "identity_360").mkdir(parents=True, exist_ok=True)
    (run_dir / "features").mkdir(parents=True, exist_ok=True)
    (run_dir / "models").mkdir(parents=True, exist_ok=True)
    (run_dir / "serving_activation").mkdir(parents=True, exist_ok=True)
    (run_dir / "monitoring_governance").mkdir(parents=True, exist_ok=True)

    (run_dir / "ingestion" / "event_bus" / "topic.jsonl").write_text(
        json.dumps({"payload": {"customer_id": "CUST-001"}}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "storage" / "raw" / "events.jsonl").write_text(
        json.dumps({"topic": "raw", "payload": {"customer_id": "CUST-001"}}) + "\n",
        encoding="utf-8",
    )
    (run_dir / "storage" / "curated" / "records.json").write_text(
        json.dumps([{"customer_id": "CUST-001"}]),
        encoding="utf-8",
    )
    (run_dir / "identity_360" / "resolved_records.json").write_text(
        json.dumps([{"unified_customer_id": "U-CUST-001"}]),
        encoding="utf-8",
    )
    (run_dir / "features" / "feature_rows.json").write_text(
        json.dumps([{"customer_id": "U-CUST-001", "risk_score": 0.2}]),
        encoding="utf-8",
    )
    (run_dir / "models" / "predictions.json").write_text(
        json.dumps({"metrics": {"primary_kpi": "retention_lift"}, "rows": [{"customer_id": "U-CUST-001"}]}),
        encoding="utf-8",
    )
    (run_dir / "serving_activation" / "activation_payloads.json").write_text(
        json.dumps([{"destination": "campaign_orchestrator"}]),
        encoding="utf-8",
    )
    (run_dir / "monitoring_governance" / "report.json").write_text(
        json.dumps({"run_status": "pass", "validation_gates": {"contract_tests_pass": "pass"}}),
        encoding="utf-8",
    )

    (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")

    payload = build_view_model(
        config_dir=Path("use_cases/configs"),
        artifacts_root=artifacts_root,
    )

    nba = [row for row in payload["use_cases"] if row["use_case_id"] == "UC-NBA-RET-001"][0]
    assert nba["latest_run"] is not None

    compact_runtime = nba["latest_run"]["oss_runtime"]
    assert compact_runtime is not None
    assert compact_runtime["status"] == "executed"
    assert "curated_rows" not in compact_runtime
    assert compact_runtime["topics"] == ["raw.uc_nba_ret_001.crm_customers.v1"]
    assert len(nba["latest_run"]["guided_steps"]) == 8
