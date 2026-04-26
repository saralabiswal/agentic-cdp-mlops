from __future__ import annotations

"""Optional product-like integration adapters.

These adapters deliberately keep third-party dependencies lazy. Standalone runs
must continue to work without MLflow, Feast, Splink, Airflow, or Keycloak
installed; when a dependency is present, the adapter records that it can be
used and performs lightweight integration work where it is safe to do so.
"""

import importlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENTERPRISE_HARDENING_CONFIG_PATH = Path("ui/config/enterprise_hardening.json")


def optional_module_status(module_name: str) -> dict[str, Any]:
    """Return dependency availability without importing at module load time."""
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # pragma: no cover - depends on local environment.
        return {
            "dependency": module_name,
            "available": False,
            "error": str(exc),
        }
    version = getattr(module, "__version__", None)
    return {
        "dependency": module_name,
        "available": True,
        "version": str(version) if version is not None else None,
    }


def load_optional_integration_config(
    *, config_path: Path = ENTERPRISE_HARDENING_CONFIG_PATH, profile: str = "product_like"
) -> dict[str, Any]:
    """Load optional integration enablement for a profile."""
    payload: dict[str, Any] = {}
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                parsed = json.load(f)
            if isinstance(parsed, dict):
                payload = parsed
        except (OSError, json.JSONDecodeError):
            payload = {}

    profile_modules = (
        payload.get("profiles", {})
        if isinstance(payload.get("profiles"), dict)
        else {}
    )
    profile_cfg = profile_modules.get(profile, {}) if isinstance(profile_modules, dict) else {}
    module_flags = (
        profile_cfg.get("modules", {})
        if isinstance(profile_cfg, dict) and isinstance(profile_cfg.get("modules"), dict)
        else {}
    )
    module_defaults = payload.get("modules", {}) if isinstance(payload.get("modules"), dict) else {}
    modules: dict[str, bool] = {}
    for key, cfg in module_defaults.items():
        default_enabled = bool(cfg.get("enabled", False)) if isinstance(cfg, dict) else False
        modules[str(key)] = bool(module_flags.get(key, default_enabled))
    for key, value in module_flags.items():
        modules[str(key)] = bool(value)
    return {"profile": profile, "modules": modules}


def integration_enabled(config: dict[str, Any], module_id: str) -> bool:
    """Return whether an optional integration is enabled in config."""
    modules = config.get("modules", {})
    return bool(modules.get(module_id, False)) if isinstance(modules, dict) else False


def write_mlflow_integration(
    *,
    run_dir: Path,
    use_case_id: str,
    run_id: str,
    model_metrics: dict[str, Any],
    model_artifacts: dict[str, Any],
    enabled: bool,
) -> str:
    """Write MLflow-compatible lineage and optionally log to MLflow."""
    target_dir = run_dir / "enterprise_hardening"
    target_dir.mkdir(parents=True, exist_ok=True)
    dependency = optional_module_status("mlflow")
    metric_items = {
        key: value
        for key, value in model_metrics.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    status = "implemented_optional_not_enabled"
    mlflow_run_id = None
    error = None
    if enabled and dependency["available"]:
        try:  # pragma: no cover - exercised only when mlflow is installed locally.
            mlflow = importlib.import_module("mlflow")
            experiment_name = f"cdp-{use_case_id}"
            mlflow.set_experiment(experiment_name)
            with mlflow.start_run(run_name=run_id) as active_run:
                mlflow_run_id = active_run.info.run_id
                mlflow.log_params(
                    {
                        "use_case_id": use_case_id,
                        "model_backend": str(model_metrics.get("model_backend", "unknown")),
                        "model_version": str(model_metrics.get("model_version", "unknown")),
                        "primary_kpi": str(model_metrics.get("primary_kpi", "unknown")),
                    }
                )
                if metric_items:
                    mlflow.log_metrics({key: float(value) for key, value in metric_items.items()})
                for artifact_path in model_artifacts.values():
                    path = Path(str(artifact_path))
                    if path.exists() and path.is_file():
                        mlflow.log_artifact(str(path))
            status = "executed"
        except Exception as exc:
            status = "adapter_ready_execution_failed"
            error = str(exc)
    elif enabled:
        status = "adapter_ready_missing_dependency"

    payload = {
        "artifact_schema_version": "1.0",
        "integration": "mlflow",
        "status": status,
        "enabled": enabled,
        "dependency": dependency,
        "use_case_id": use_case_id,
        "run_id": run_id,
        "experiment_name": f"cdp-{use_case_id}",
        "run_name": run_id,
        "mlflow_run_id": mlflow_run_id,
        "metrics": metric_items,
        "params": {
            "model_backend": model_metrics.get("model_backend", "unknown"),
            "model_version": model_metrics.get("model_version", "unknown"),
            "primary_kpi": model_metrics.get("primary_kpi", "unknown"),
        },
        "artifacts": model_artifacts,
        "error": error,
        "notes": "Optional MLflow adapter. Standalone runs keep this lineage artifact even without MLflow installed.",
    }
    target_file = target_dir / "mlflow_lineage.json"
    _write_json(target_file, payload)
    return str(target_file)


def write_splink_identity_artifact(
    *,
    run_dir: Path,
    use_case_id: str,
    curated_rows: list[dict[str, Any]],
    resolved_rows: list[dict[str, Any]],
    enabled: bool,
) -> str:
    """Write optional Splink identity-resolution adapter artifact."""
    target_dir = run_dir / "enterprise_hardening"
    target_dir.mkdir(parents=True, exist_ok=True)
    dependency = optional_module_status("splink")
    status = (
        "optional_not_enabled"
        if not enabled
        else "adapter_ready_dependency_available"
        if dependency["available"]
        else "adapter_ready_missing_dependency"
    )
    sample_pairs = []
    for idx, row in enumerate(resolved_rows[:10]):
        sample_pairs.append(
            {
                "source_record": str(curated_rows[idx].get("customer_id", idx)) if idx < len(curated_rows) else str(idx),
                "resolved_record": str(row.get("unified_customer_id", row.get("customer_id", idx))),
                "match_probability": row.get("match_confidence", 0.98),
                "match_method": "splink_optional_adapter" if enabled else "deterministic_fallback",
            }
        )
    target_file = target_dir / "splink_identity_resolution.json"
    _write_json(
        target_file,
        {
            "artifact_schema_version": "1.0",
            "integration": "splink",
            "status": status,
            "enabled": enabled,
            "dependency": dependency,
            "use_case_id": use_case_id,
            "record_count": len(resolved_rows),
            "sample_matches": sample_pairs,
            "notes": "Optional Splink adapter contract. Built-in deterministic identity remains the standalone fallback.",
        },
    )
    return str(target_file)


def write_feast_feature_store_artifacts(
    *,
    run_dir: Path,
    use_case_id: str,
    feature_rows: list[dict[str, Any]],
    feature_path: str,
    enabled: bool,
) -> dict[str, str]:
    """Write optional Feast offline feature-store artifacts."""
    target_dir = run_dir / "feature_store"
    target_dir.mkdir(parents=True, exist_ok=True)
    dependency = optional_module_status("feast")
    status = (
        "optional_not_enabled"
        if not enabled
        else "adapter_ready_dependency_available"
        if dependency["available"]
        else "adapter_ready_missing_dependency"
    )
    entity_key = _infer_entity_key(feature_rows)
    feature_names = sorted({key for row in feature_rows for key in row.keys() if key != entity_key})
    registry_payload = {
        "artifact_schema_version": "1.0",
        "integration": "feast",
        "status": status,
        "enabled": enabled,
        "dependency": dependency,
        "use_case_id": use_case_id,
        "project": "customer_data_platform",
        "entity_key": entity_key,
        "feature_names": feature_names,
        "offline_source": feature_path,
        "row_count": len(feature_rows),
        "notes": "Optional Feast adapter contract. The standalone feature layer remains the source of truth when Feast is absent.",
    }
    registry_file = target_dir / "feast_registry.json"
    feature_view_file = target_dir / "feature_view.json"
    offline_file = target_dir / "offline_features.json"
    repo_file = target_dir / "feature_store.yaml"
    _write_json(registry_file, registry_payload)
    _write_json(
        feature_view_file,
        {
            "name": f"{use_case_id.lower().replace('-', '_')}_features",
            "entity": entity_key,
            "features": feature_names,
            "source": feature_path,
        },
    )
    _write_json(
        offline_file,
        {
            "use_case_id": use_case_id,
            "row_count": len(feature_rows),
            "rows": feature_rows[:25],
        },
    )
    repo_file.write_text(
        "\n".join(
            [
                "project: customer_data_platform",
                "provider: local",
                "registry: feast_registry.db",
                f"offline_store_source: {feature_path}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "feast_registry": str(registry_file),
        "feast_feature_view": str(feature_view_file),
        "feast_offline_features": str(offline_file),
        "feast_repo_config": str(repo_file),
    }


def write_airflow_dag_artifact(
    *,
    run_dir: Path,
    use_case_id: str,
    enabled: bool,
) -> str:
    """Write optional Airflow DAG wrapper artifact."""
    target_dir = run_dir / "orchestration"
    target_dir.mkdir(parents=True, exist_ok=True)
    dependency = optional_module_status("airflow")
    status = (
        "optional_not_enabled"
        if not enabled
        else "adapter_ready_dependency_available"
        if dependency["available"]
        else "adapter_ready_missing_dependency"
    )
    dag_id = f"cdp_{use_case_id.lower().replace('-', '_')}"
    dag_file = target_dir / f"{dag_id}_dag.py"
    dag_file.write_text(
        f'''"""Optional Airflow DAG wrapper for {use_case_id}."""

from __future__ import annotations

from datetime import datetime

try:
    from airflow import DAG
    from airflow.operators.bash import BashOperator
except Exception:  # pragma: no cover - optional runtime dependency.
    DAG = None
    BashOperator = None


if DAG and BashOperator:
    with DAG(
        dag_id="{dag_id}",
        start_date=datetime(2026, 1, 1),
        schedule=None,
        catchup=False,
        tags=["customer-data-platform", "optional"],
    ) as dag:
        BashOperator(
            task_id="run_full_stack",
            bash_command="./.venv311/bin/python -m pipelines.run_use_case --use-case-id {use_case_id}",
        )
''',
        encoding="utf-8",
    )
    metadata_file = target_dir / "airflow_dag_metadata.json"
    _write_json(
        metadata_file,
        {
            "artifact_schema_version": "1.0",
            "integration": "airflow",
            "status": status,
            "enabled": enabled,
            "dependency": dependency,
            "dag_id": dag_id,
            "dag_file": str(dag_file),
            "notes": "Optional Airflow DAG wrapper; standalone execution does not require Airflow.",
        },
    )
    return str(metadata_file)


def write_keycloak_auth_artifact(
    *,
    run_dir: Path,
    enabled: bool,
) -> str:
    """Write optional Keycloak/OIDC readiness artifact."""
    target_dir = run_dir / "security"
    target_dir.mkdir(parents=True, exist_ok=True)
    dependency = optional_module_status("keycloak")
    issuer = os.getenv("CDP_KEYCLOAK_ISSUER", "").strip()
    client_id = os.getenv("CDP_KEYCLOAK_CLIENT_ID", "").strip()
    configured = bool(issuer and client_id)
    status = (
        "optional_not_enabled"
        if not enabled
        else "configured"
        if configured
        else "adapter_ready_missing_config"
    )
    target_file = target_dir / "keycloak_oidc_readiness.json"
    _write_json(
        target_file,
        {
            "artifact_schema_version": "1.0",
            "integration": "keycloak",
            "status": status,
            "enabled": enabled,
            "dependency": dependency,
            "oidc": {
                "issuer_configured": bool(issuer),
                "client_id_configured": bool(client_id),
                "required_env": ["CDP_KEYCLOAK_ISSUER", "CDP_KEYCLOAK_CLIENT_ID"],
            },
            "roles": ["viewer", "operator", "admin"],
            "notes": "Optional Keycloak/OIDC contract. Standalone mode remains unauthenticated/local.",
        },
    )
    return str(target_file)


def write_product_like_integration_manifest(
    *,
    run_dir: Path,
    profile: str,
    artifacts: dict[str, str],
) -> str:
    """Persist an index of optional product-like integration artifacts."""
    target_dir = run_dir / "enterprise_hardening"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "product_like_integrations.json"
    _write_json(
        target_file,
        {
            "artifact_schema_version": "1.0",
            "profile": profile,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "artifacts": artifacts,
            "notes": "Optional integration manifest. Missing dependencies do not block standalone execution.",
        },
    )
    return str(target_file)


def _infer_entity_key(rows: list[dict[str, Any]]) -> str:
    """Infer the feature entity key used by the feature rows."""
    for candidate in ["customer_id", "campaign_id", "period"]:
        if rows and candidate in rows[0]:
            return candidate
    return "entity_id"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON payload with parent directories created."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
