from __future__ import annotations

"""End-to-end architecture orchestrator.

This module runs the platform layers in architecture order:
1) data sources
2) ingestion and event bus
3) raw + curated storage
4) identity and customer 360
5) feature layer
6) model layer
7) serving + activation
8) monitoring + governance

When `infra_profile="oss"`, this orchestrator attempts full OSS execution for
all use cases (Kafka/Postgres/MinIO). If OSS services are unavailable, the run
falls back to local adapters while recording fallback warnings.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipelines.contract_loader import (
    DEFAULT_CONFIG_DIR,
    list_config_paths,
    load_contract,
    load_contract_by_id,
)
from stack.layers import (
    build_feature_layer,
    build_raw_and_curated_storage,
    collect_source_data_with_metadata,
    ingest_to_event_bus,
    resolve_identity_customer_360,
    run_model_layer,
    run_monitoring_and_governance,
    run_serving_and_activation,
)
from stack.model_registry import register_model_candidate_from_summary
from stack.optional_integrations import (
    integration_enabled,
    load_optional_integration_config,
    write_airflow_dag_artifact,
    write_feast_feature_store_artifacts,
    write_keycloak_auth_artifact,
    write_mlflow_integration,
    write_product_like_integration_manifest,
    write_splink_identity_artifact,
)
from stack.oss_runtime import run_oss_golden_path
from stack.scenario_library import (
    resolve_scenario_preset,
    to_failure_injection_flags,
)

DEFAULT_OUTPUT_DIR = Path("artifacts")
DEFAULT_OSS_COMPOSE_FILE = Path("infra/docker-compose.oss.yml")


def run_full_stack(
    use_case_id: str,
    config_dir: Path = DEFAULT_CONFIG_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    seed: int = 7,
    infra_profile: str = "local",
    oss_compose_file: Path = DEFAULT_OSS_COMPOSE_FILE,
    strict_model_backends: bool = False,
    source_data_root: Path | None = None,
    require_real_data: bool = False,
    runtime_mode: str = "default",
    scenario_id: str | None = None,
    failure_injection: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Run one use case through every platform layer and return run summary metadata."""
    contract = load_contract_by_id(use_case_id=use_case_id, config_dir=config_dir)
    normalized_runtime_mode = _normalize_runtime_mode(runtime_mode=runtime_mode)
    failure_injection_flags = to_failure_injection_flags(
        flags=failure_injection,
        scenario_id=scenario_id,
        use_case_id=use_case_id,
    )
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / use_case_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    stage_telemetry: list[dict[str, Any]] = []
    optional_config = load_optional_integration_config(profile="product_like")
    product_like_artifacts: dict[str, str] = {}

    # Stage 1: Data Sources
    stage_start = time.perf_counter()
    source_tables, source_data = collect_source_data_with_metadata(
        contract=contract,
        seed=seed,
        source_data_root=source_data_root,
        require_real_data=require_real_data,
        runtime_mode=normalized_runtime_mode,
        scenario_id=scenario_id,
    )
    _append_stage_telemetry(
        stage_telemetry=stage_telemetry,
        layer_id="data_sources",
        started_at=stage_start,
        detail=str(source_data.get("mode", "unknown")),
    )
    _enforce_real_data_readiness(
        use_case_id=use_case_id,
        source_data_metadata=source_data,
        require_real_data=require_real_data,
        strict_model_backends=strict_model_backends,
    )
    oss_runtime_report: dict[str, Any] | None = None
    used_oss_golden_path = False

    if infra_profile == "oss":
        stage_start = time.perf_counter()
        oss_runtime_report = run_oss_golden_path(
            compose_file=oss_compose_file,
            run_dir=run_dir,
            run_id=run_id,
            use_case_id=use_case_id,
            source_tables=source_tables,
        )
        if oss_runtime_report["status"] == "executed":
            used_oss_golden_path = True
            ingest_paths = dict(oss_runtime_report["ingestion_event_bus"])
            curated_rows = list(oss_runtime_report["curated_rows"])
            storage_paths = dict(oss_runtime_report["storage_paths"])
            _append_stage_telemetry(
                stage_telemetry=stage_telemetry,
                layer_id="ingestion_event_bus",
                started_at=stage_start,
                detail="executed_oss_golden_path",
            )
            _append_stage_telemetry(
                stage_telemetry=stage_telemetry,
                layer_id="raw_curated_storage",
                started_at=stage_start,
                detail="executed_oss_golden_path",
            )

    if not used_oss_golden_path:
        # Stage 2: Ingestion + Event Bus
        stage_start = time.perf_counter()
        bus, ingest_paths = ingest_to_event_bus(
            use_case_id=use_case_id, source_tables=source_tables, output_dir=run_dir
        )
        _append_stage_telemetry(
            stage_telemetry=stage_telemetry,
            layer_id="ingestion_event_bus",
            started_at=stage_start,
            detail=f"topics={len(ingest_paths)}",
        )
        # Stage 3: Raw Storage + Curated Warehouse
        stage_start = time.perf_counter()
        curated_rows, storage_paths = build_raw_and_curated_storage(
            use_case_id=use_case_id, bus=bus, output_dir=run_dir
        )
        _append_stage_telemetry(
            stage_telemetry=stage_telemetry,
            layer_id="raw_curated_storage",
            started_at=stage_start,
            detail=f"curated_rows={len(curated_rows)}",
        )
    # Stage 4: Identity Resolution + Customer 360
    stage_start = time.perf_counter()
    resolved_rows, identity_paths = resolve_identity_customer_360(
        use_case_id=use_case_id, curated_rows=curated_rows, output_dir=run_dir
    )
    splink_artifact = write_splink_identity_artifact(
        run_dir=run_dir,
        use_case_id=use_case_id,
        curated_rows=curated_rows,
        resolved_rows=resolved_rows,
        enabled=integration_enabled(optional_config, "splink"),
    )
    product_like_artifacts["splink_identity_resolution"] = splink_artifact
    _append_stage_telemetry(
        stage_telemetry=stage_telemetry,
        layer_id="identity_customer_360",
        started_at=stage_start,
        detail=f"resolved_rows={len(resolved_rows)}",
    )
    # Stage 5: Feature Layer
    stage_start = time.perf_counter()
    feature_rows, feature_path = build_feature_layer(
        use_case_id=use_case_id, resolved_rows=resolved_rows, output_dir=run_dir
    )
    feast_artifacts = write_feast_feature_store_artifacts(
        run_dir=run_dir,
        use_case_id=use_case_id,
        feature_rows=feature_rows,
        feature_path=feature_path,
        enabled=integration_enabled(optional_config, "feast"),
    )
    product_like_artifacts.update(feast_artifacts)
    _append_stage_telemetry(
        stage_telemetry=stage_telemetry,
        layer_id="feature_layer",
        started_at=stage_start,
        detail=f"feature_rows={len(feature_rows)}",
    )
    # Stage 6: Model Layer
    stage_start = time.perf_counter()
    model_rows, model_metrics, model_artifacts = run_model_layer(
        contract=contract,
        feature_rows=feature_rows,
        output_dir=run_dir,
        seed=seed,
        strict_model_backends=strict_model_backends,
    )
    mlflow_lineage_path = write_mlflow_integration(
        run_dir=run_dir,
        use_case_id=use_case_id,
        run_id=run_id,
        model_metrics=model_metrics,
        model_artifacts=model_artifacts,
        enabled=integration_enabled(optional_config, "mlflow"),
    )
    product_like_artifacts["mlflow_lineage"] = mlflow_lineage_path
    _append_stage_telemetry(
        stage_telemetry=stage_telemetry,
        layer_id="model_layer",
        started_at=stage_start,
        detail=f"model_rows={len(model_rows)}",
    )
    _enforce_real_data_split_validation(
        use_case_id=use_case_id,
        source_data_metadata=source_data,
        model_metrics=model_metrics,
        strict_model_backends=strict_model_backends,
    )
    # Stage 7: Serving + Activation
    stage_start = time.perf_counter()
    activation_rows, activation_path = run_serving_and_activation(
        contract=contract, model_rows=model_rows, output_dir=run_dir
    )
    _append_stage_telemetry(
        stage_telemetry=stage_telemetry,
        layer_id="serving_activation",
        started_at=stage_start,
        detail=f"activation_rows={len(activation_rows)}",
    )
    # Stage 8: Monitoring + Governance
    stage_start = time.perf_counter()
    monitoring_report, monitoring_path = run_monitoring_and_governance(
        contract=contract,
        model_rows=model_rows,
        model_metrics=model_metrics,
        output_dir=run_dir,
        run_id=run_id,
        seed=seed,
        source_data_metadata=source_data,
        failure_injection=failure_injection_flags,
    )
    monitoring_exports = _write_monitoring_compatibility_exports(
        run_dir=run_dir,
        monitoring_report=monitoring_report,
        stage_telemetry=stage_telemetry,
    )
    airflow_artifact = write_airflow_dag_artifact(
        run_dir=run_dir,
        use_case_id=use_case_id,
        enabled=integration_enabled(optional_config, "airflow"),
    )
    keycloak_artifact = write_keycloak_auth_artifact(
        run_dir=run_dir,
        enabled=integration_enabled(optional_config, "keycloak"),
    )
    product_like_artifacts.update(
        {
            "data_quality_expectations": monitoring_exports["data_quality_expectations"],
            "monitoring_summary": monitoring_exports["monitoring_summary"],
            "airflow_dag_metadata": airflow_artifact,
            "keycloak_oidc_readiness": keycloak_artifact,
        }
    )
    _append_stage_telemetry(
        stage_telemetry=stage_telemetry,
        layer_id="monitoring_governance",
        started_at=stage_start,
        detail=f"run_status={monitoring_report.get('run_status', 'unknown')}",
    )
    telemetry_path = _write_stage_telemetry(run_dir=run_dir, rows=stage_telemetry)
    product_like_manifest = write_product_like_integration_manifest(
        run_dir=run_dir,
        profile=str(optional_config.get("profile", "product_like")),
        artifacts=product_like_artifacts,
    )

    summary = {
        "use_case_id": use_case_id,
        "name": contract.name,
        "run_id": run_id,
        "seed": seed,
        "runtime_mode": normalized_runtime_mode,
        "scenario_id": scenario_id,
        "failure_injection": {
            key: value for key, value in failure_injection_flags.items() if value
        },
        "infra_profile": infra_profile,
        "strict_model_backends": strict_model_backends,
        "source_data": source_data,
        "records": {
            "source_tables": {table: len(rows) for table, rows in source_tables.items()},
            "curated_rows": len(curated_rows),
            "feature_rows": len(feature_rows),
            "model_rows": len(model_rows),
            "activation_rows": len(activation_rows),
        },
        "model_metrics": model_metrics,
        "run_status": monitoring_report["run_status"],
        "artifacts": {
            "ingestion_event_bus": ingest_paths,
            **storage_paths,
            **identity_paths,
            "splink_identity_resolution": splink_artifact,
            "feature_rows": feature_path,
            **feast_artifacts,
            **model_artifacts,
            "mlflow_lineage": mlflow_lineage_path,
            "activation_payloads": activation_path,
            "monitoring_report": monitoring_path,
            **monitoring_exports,
            "airflow_dag_metadata": airflow_artifact,
            "keycloak_oidc_readiness": keycloak_artifact,
            "product_like_integrations": product_like_manifest,
            "stage_telemetry": telemetry_path,
        },
        "telemetry": {
            "stage_count": len(stage_telemetry),
            "stages": stage_telemetry,
        },
    }
    if oss_runtime_report is not None:
        summary["oss_runtime"] = oss_runtime_report

    summary_path = run_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    summary["summary_path"] = str(summary_path)

    model_registry_meta = register_model_candidate_from_summary(
        summary=summary,
        artifacts_root=output_dir,
        summary_path=summary_path,
    )
    summary["model_registry"] = model_registry_meta

    # Persist model-registry metadata back into summary artifact for traceability.
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


def run_full_stack_all(
    config_dir: Path = DEFAULT_CONFIG_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    seed: int = 7,
    infra_profile: str = "local",
    oss_compose_file: Path = DEFAULT_OSS_COMPOSE_FILE,
    strict_model_backends: bool = False,
    source_data_root: Path | None = None,
    require_real_data: bool = False,
    runtime_mode: str = "default",
    scenario_id: str | None = None,
    failure_injection: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Run every use case config through the full platform stack."""
    summaries: list[dict[str, Any]] = []
    for config_path in list_config_paths(config_dir=config_dir):
        contract = load_contract(config_path)
        summaries.append(
            run_full_stack(
                use_case_id=contract.use_case_id,
                config_dir=config_dir,
                output_dir=output_dir,
                seed=seed,
                infra_profile=infra_profile,
                oss_compose_file=oss_compose_file,
                strict_model_backends=strict_model_backends,
                source_data_root=source_data_root,
                require_real_data=require_real_data,
                runtime_mode=runtime_mode,
                scenario_id=_scenario_for_use_case(
                    scenario_id=scenario_id,
                    use_case_id=contract.use_case_id,
                ),
                failure_injection=failure_injection,
            )
        )
    return summaries


def _normalize_runtime_mode(*, runtime_mode: str) -> str:
    """Normalize runtime mode to supported values."""
    normalized = str(runtime_mode or "default").strip().lower()
    if normalized in {"default", "auto"}:
        return "default"
    if normalized == "synthetic_only":
        return "synthetic_only"
    raise ValueError(f"Unsupported runtime_mode '{runtime_mode}'. Allowed: default, synthetic_only.")


def _scenario_for_use_case(*, scenario_id: str | None, use_case_id: str) -> str | None:
    """Return scenario id only when it belongs to the current use case."""
    if not scenario_id:
        return None
    preset = resolve_scenario_preset(scenario_id=scenario_id, use_case_id=None)
    if preset is None or preset.use_case_id != use_case_id:
        return None
    return scenario_id


def _append_stage_telemetry(
    *,
    stage_telemetry: list[dict[str, Any]],
    layer_id: str,
    started_at: float,
    detail: str,
) -> None:
    """Append one stage telemetry row with duration."""
    stage_telemetry.append(
        {
            "layer_id": layer_id,
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 3),
            "detail": detail,
        }
    )


def _write_stage_telemetry(*, run_dir: Path, rows: list[dict[str, Any]]) -> str:
    """Persist stage telemetry as JSONL artifact for observability demos."""
    target_dir = run_dir / "telemetry"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "stage_events.jsonl"
    with target_file.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return str(target_file)


def _write_mlflow_lineage(
    *,
    run_dir: Path,
    use_case_id: str,
    run_id: str,
    model_metrics: dict[str, Any],
    model_artifacts: dict[str, Any],
) -> str:
    """Persist MLflow-compatible lineage without requiring MLflow at demo time."""
    target_dir = run_dir / "enterprise_hardening"
    target_dir.mkdir(parents=True, exist_ok=True)
    metric_items = {
        key: value
        for key, value in model_metrics.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    payload = {
        "artifact_schema_version": "1.0",
        "integration": "mlflow",
        "status": "local_lineage_artifact",
        "use_case_id": use_case_id,
        "run_id": run_id,
        "experiment_name": f"cdp-{use_case_id}",
        "run_name": run_id,
        "metrics": metric_items,
        "params": {
            "model_backend": model_metrics.get("model_backend", "unknown"),
            "model_version": model_metrics.get("model_version", "unknown"),
            "primary_kpi": model_metrics.get("primary_kpi", "unknown"),
        },
        "artifacts": model_artifacts,
        "notes": "Compatible lineage export; real MLflow logging can be enabled when mlflow is installed/configured.",
    }
    target_file = target_dir / "mlflow_lineage.json"
    with target_file.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return str(target_file)


def _write_monitoring_compatibility_exports(
    *,
    run_dir: Path,
    monitoring_report: dict[str, Any],
    stage_telemetry: list[dict[str, Any]],
) -> dict[str, str]:
    """Write lightweight Great Expectations/Evidently-compatible artifacts."""
    target_dir = run_dir / "enterprise_hardening"
    target_dir.mkdir(parents=True, exist_ok=True)
    data_quality = monitoring_report.get("data_quality", {})
    model_validation = monitoring_report.get("model_validation", {})
    readiness = monitoring_report.get("deployment_readiness", {})

    ge_payload = {
        "artifact_schema_version": "1.0",
        "integration": "great_expectations_compatible",
        "status": data_quality.get("status", "unknown") if isinstance(data_quality, dict) else "unknown",
        "summary": data_quality.get("summary", {}) if isinstance(data_quality, dict) else {},
        "checks": data_quality.get("checks", []) if isinstance(data_quality, dict) else [],
        "gates": data_quality.get("gates", {}) if isinstance(data_quality, dict) else {},
        "notes": "Compatibility export generated from built-in data-quality gates.",
    }
    evidently_payload = {
        "artifact_schema_version": "1.0",
        "integration": "evidently_compatible",
        "run_status": monitoring_report.get("run_status", "unknown"),
        "model_validation": model_validation,
        "deployment_readiness": readiness,
        "stage_telemetry": stage_telemetry,
        "notes": "Compatibility export generated from built-in model, governance, and stage telemetry checks.",
    }

    ge_file = target_dir / "data_quality_expectations.json"
    evidently_file = target_dir / "monitoring_summary.json"
    with ge_file.open("w", encoding="utf-8") as f:
        json.dump(ge_payload, f, indent=2)
    with evidently_file.open("w", encoding="utf-8") as f:
        json.dump(evidently_payload, f, indent=2)
    return {
        "data_quality_expectations": str(ge_file),
        "monitoring_summary": str(evidently_file),
    }


def _enforce_real_data_readiness(
    *,
    use_case_id: str,
    source_data_metadata: dict[str, Any],
    require_real_data: bool,
    strict_model_backends: bool,
) -> None:
    """Block runs when real-dataset quality/volume gates fail under strict paths."""
    mode = str(source_data_metadata.get("mode", "unknown")).strip().lower()
    if mode != "real_dataset":
        return
    if not (require_real_data or strict_model_backends):
        return

    readiness = source_data_metadata.get("readiness")
    if not isinstance(readiness, dict):
        return
    if str(readiness.get("status", "pass")).strip().lower() != "fail":
        return

    blockers = readiness.get("blocking_checks", [])
    if not isinstance(blockers, list):
        blockers = [str(blockers)]
    blocker_text = ", ".join(str(item) for item in blockers if str(item).strip()) or "unknown"
    raise RuntimeError(
        "Real-data readiness gate failed for "
        f"{use_case_id}. blocking_checks={blocker_text}"
    )


def _enforce_real_data_split_validation(
    *,
    use_case_id: str,
    source_data_metadata: dict[str, Any],
    model_metrics: dict[str, Any],
    strict_model_backends: bool,
) -> None:
    """Block strict real-data runs when train/validation split checks fail."""
    if not strict_model_backends:
        return
    mode = str(source_data_metadata.get("mode", "unknown")).strip().lower()
    if mode != "real_dataset":
        return

    split_validation = model_metrics.get("split_validation")
    if not isinstance(split_validation, dict):
        raise RuntimeError(
            "Strict real-data split validation missing for "
            f"{use_case_id}. Expected model_metrics['split_validation']."
        )
    summary = split_validation.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    failed_checks = int(summary.get("failed_checks", 0) or 0)
    if failed_checks <= 0:
        return

    checks = split_validation.get("checks", [])
    if not isinstance(checks, list):
        checks = []
    failed_names = [
        str(row.get("name"))
        for row in checks
        if isinstance(row, dict) and str(row.get("status", "pass")) != "pass"
    ]
    failed_text = ", ".join(failed_names) if failed_names else "unknown_split_check"
    raise RuntimeError(
        "Strict real-data split validation failed for "
        f"{use_case_id}. failed_checks={failed_text}"
    )
