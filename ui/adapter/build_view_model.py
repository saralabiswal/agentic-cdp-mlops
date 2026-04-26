#!/usr/bin/env python3
"""Build a stable UI view model from contracts and run artifacts.

The output JSON supports two runtime modes:
1. latest_artifacts: read latest summaries already present in artifacts/
2. execute_backend: trigger orchestrator run(s) first, then build UI payload

This keeps the UI static but data-real, with no frontend rewrite needed
when switching between snapshot and live execution workflows.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.contract_loader import DEFAULT_CONFIG_DIR, UseCaseContract, list_config_paths, load_contract
from stack.scenario_library import list_scenario_presets

DEFAULT_OUTPUT = Path("ui/data/view_model.json")
DEFAULT_ARTIFACTS_ROOT = Path("artifacts")
DEFAULT_RUNTIME_CONFIG = Path("ui/config/runtime.yaml")
SCHEMA_VERSION = "1.0.0"

RUNTIME_MODE_LATEST = "latest_artifacts"
RUNTIME_MODE_EXECUTE = "execute_backend"

DEFAULT_RUNTIME_SETTINGS: dict[str, Any] = {
    "mode": RUNTIME_MODE_LATEST,
    "execution": {
        "use_case_id": None,
        "infra_profile": "local",
        "seed": 101,
        "runtime_mode": "default",
        "scenario_id": None,
        "failure_injection": [],
        "output_dir": "artifacts",
        "oss_compose_file": "infra/docker-compose.oss.yml",
        "strict_model_backends": False,
        "source_data_root": None,
        "require_real_data": False,
    },
}


ARCHITECTURE_FLOW: list[dict[str, Any]] = [
    {
        "order": 1,
        "layer_id": "data_sources",
        "label": "Data Sources",
        "upstream": ["Business Systems", "Channel Signals", "Experiment Logs"],
        "downstream": ["Ingestion + Event Bus"],
        "business_summary": "Collects first-party customer and campaign signals required for decisions.",
        "technical_summary": "Contract-aware source generation and connector abstraction for repeatable ingestion.",
        "components": {
            "current": ["Python source generators"],
            "oss_profile": ["Kafka producer inputs (via adapter)", "File-based local fallback"],
            "scalable_swap_ins": ["Airbyte", "Kafka Connect", "Debezium"],
        },
    },
    {
        "order": 2,
        "layer_id": "ingestion_event_bus",
        "label": "Ingestion + Event Bus",
        "upstream": ["Data Sources"],
        "downstream": ["Raw Storage + Curated Warehouse"],
        "business_summary": "Creates a reliable event trail so decisions are explainable and replayable.",
        "technical_summary": "Canonical topic naming, append-only events, and deterministic artifact persistence.",
        "components": {
            "current": ["In-memory LocalEventBus", "JSONL topic artifacts"],
            "oss_profile": ["Apache Kafka"],
            "scalable_swap_ins": ["Apache Kafka", "Redpanda", "Apache Pulsar"],
        },
    },
    {
        "order": 3,
        "layer_id": "raw_curated_storage",
        "label": "Raw Storage + Curated Warehouse",
        "upstream": ["Ingestion + Event Bus"],
        "downstream": ["Identity Resolution + Customer 360"],
        "business_summary": "Preserves immutable evidence and creates analytics-ready curated data.",
        "technical_summary": "Stores raw event logs and curated joins in JSON/JSONL with warehouse mirroring options.",
        "components": {
            "current": ["Local artifact files (JSON/JSONL)"],
            "oss_profile": ["PostgreSQL mirror", "MinIO snapshots"],
            "scalable_swap_ins": ["PostgreSQL", "ClickHouse", "MinIO", "Apache Iceberg"],
        },
    },
    {
        "order": 4,
        "layer_id": "identity_customer_360",
        "label": "Identity Resolution + Customer 360",
        "upstream": ["Raw Storage + Curated Warehouse"],
        "downstream": ["Feature Layer"],
        "business_summary": "Unifies customer records so targeting and measurement use a single customer truth.",
        "technical_summary": "Deterministic unified IDs and household keys for person-level use cases.",
        "components": {
            "current": ["Deterministic identity mapper"],
            "oss_profile": ["Local mapping artifacts"],
            "scalable_swap_ins": ["Splink", "DuckDB", "Record linkage workflows"],
        },
    },
    {
        "order": 5,
        "layer_id": "feature_layer",
        "label": "Feature Layer",
        "upstream": ["Identity Resolution + Customer 360"],
        "downstream": ["Model Layer"],
        "business_summary": "Transforms raw behavior into measurable business signals used by models.",
        "technical_summary": "Use-case-specific feature projections persisted as model-ready rows.",
        "components": {
            "current": ["Python feature builders"],
            "oss_profile": ["Artifact-backed feature rows"],
            "scalable_swap_ins": ["dbt", "Feast", "DuckDB"],
        },
    },
    {
        "order": 6,
        "layer_id": "model_layer",
        "label": "Model Layer (MMM, Incrementality, Attribution, Experimentation)",
        "upstream": ["Feature Layer"],
        "downstream": ["Serving + Activation"],
        "business_summary": "Generates recommendations and causal insights to optimize marketing outcomes.",
        "technical_summary": "Pluggable model registry validates outputs against contract fields.",
        "components": {
            "current": ["Use-case model modules", "Output schema validator"],
            "oss_profile": ["Local model execution", "OSS data sinks for all use cases"],
            "scalable_swap_ins": ["MLflow", "Airflow", "PyMC", "EconML"],
        },
    },
    {
        "order": 7,
        "layer_id": "serving_activation",
        "label": "Serving + Activation",
        "upstream": ["Model Layer (MMM, Incrementality, Attribution, Experimentation)"],
        "downstream": ["Monitoring + Governance"],
        "business_summary": "Turns model output into actions that campaign systems can execute.",
        "technical_summary": "Use-case payload adapters map model rows into destination contracts.",
        "components": {
            "current": ["Python payload adapters", "Activation artifacts"],
            "oss_profile": ["File-backed payload delivery"],
            "scalable_swap_ins": ["FastAPI", "BentoML", "Webhook connectors"],
        },
    },
    {
        "order": 8,
        "layer_id": "monitoring_governance",
        "label": "Monitoring + Governance",
        "upstream": ["Serving + Activation"],
        "downstream": ["Feedback to Data Sources and Model Layer"],
        "business_summary": "Maintains trust through validation gates, alerts, and deployment readiness checks.",
        "technical_summary": "Contract coverage checks, gate results, and run-status reporting.",
        "components": {
            "current": ["Validation gate evaluator", "Run report artifacts"],
            "oss_profile": ["Local governance reports"],
            "scalable_swap_ins": ["Great Expectations", "Evidently", "Prometheus", "Grafana"],
        },
    },
]


USE_CASE_NARRATIVES: dict[str, dict[str, str]] = {
    "UC-NBA-RET-001": {
        "business_problem": "Retention teams need personalized, policy-safe actions for each customer touchpoint.",
        "business_outcome": "Increase incremental retention lift while controlling contact fatigue and compliance risk.",
    },
    "UC-CHURN-RET-002": {
        "business_problem": "High-risk customers are not identified early enough for effective retention intervention.",
        "business_outcome": "Reduce avoidable churn by prioritizing high-risk segments with action recommendations.",
    },
    "UC-MMM-PLN-003": {
        "business_problem": "Budget allocation across channels is often based on lagging heuristics.",
        "business_outcome": "Optimize channel spend to maximize incremental revenue at fixed portfolio budget.",
    },
    "UC-INCR-MKT-004": {
        "business_problem": "Attribution alone cannot separate true causal lift from correlated conversions.",
        "business_outcome": "Measure incrementality and recommend scale/pause/retest decisions with confidence bounds.",
    },
}


STAGE_REQUIREMENTS: list[dict[str, Any]] = [
    {"layer_id": "data_sources", "label": "Data Sources", "kind": "source_tables"},
    {"layer_id": "ingestion_event_bus", "label": "Ingestion + Event Bus", "kind": "topic_files"},
    {
        "layer_id": "raw_curated_storage",
        "label": "Raw Storage + Curated Warehouse",
        "kind": "artifact_keys",
        "keys": ["raw_events", "curated_records"],
    },
    {
        "layer_id": "identity_customer_360",
        "label": "Identity Resolution + Customer 360",
        "kind": "artifact_keys",
        "keys": ["resolved_records"],
    },
    {
        "layer_id": "feature_layer",
        "label": "Feature Layer",
        "kind": "artifact_keys",
        "keys": ["feature_rows"],
    },
    {
        "layer_id": "model_layer",
        "label": "Model Layer",
        "kind": "artifact_keys",
        "keys": ["model_predictions"],
    },
    {
        "layer_id": "serving_activation",
        "label": "Serving + Activation",
        "kind": "artifact_keys",
        "keys": ["activation_payloads"],
    },
    {
        "layer_id": "monitoring_governance",
        "label": "Monitoring + Governance",
        "kind": "artifact_keys",
        "keys": ["monitoring_report"],
    },
]


@dataclass(frozen=True)
class LatestSummary:
    """Container for latest-run artifact metadata per use case."""

    run_id: str
    path: Path
    data: dict[str, Any]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for view-model generation."""
    parser = argparse.ArgumentParser(
        description="Build UI view model JSON from use-case contracts and latest artifacts."
    )
    parser.add_argument(
        "--config-dir",
        default=str(DEFAULT_CONFIG_DIR),
        help="Directory containing use-case YAML contracts.",
    )
    parser.add_argument(
        "--artifacts-root",
        default=None,
        help="Root artifact directory. Defaults to runtime.execution.output_dir.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output JSON path for UI view model.",
    )
    parser.add_argument(
        "--runtime-config",
        default=str(DEFAULT_RUNTIME_CONFIG),
        help="Runtime config YAML path. Supports latest_artifacts/execute_backend modes.",
    )
    parser.add_argument(
        "--runtime-mode",
        choices=[RUNTIME_MODE_LATEST, RUNTIME_MODE_EXECUTE],
        default=None,
        help="Override runtime mode from config file.",
    )
    parser.add_argument(
        "--run-backend",
        action="store_true",
        help="Shortcut for --runtime-mode execute_backend.",
    )
    parser.add_argument(
        "--use-case",
        default=None,
        help="Optional use case ID for execute_backend mode.",
    )
    parser.add_argument(
        "--infra-profile",
        choices=["local", "oss"],
        default=None,
        help="Optional infra profile override for execute_backend mode.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional seed override for execute_backend mode.",
    )
    parser.add_argument(
        "--execution-mode",
        choices=["default", "synthetic_only"],
        default=None,
        help="Execution runtime mode for backend runs.",
    )
    parser.add_argument(
        "--scenario-id",
        default=None,
        help="Optional deterministic scenario preset ID.",
    )
    parser.add_argument(
        "--failure-injection",
        action="append",
        default=None,
        help=(
            "Optional failure injection toggle (repeatable): "
            "dq_fail, schema_fail, backend_unavailable."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output dir override for execute_backend mode.",
    )
    parser.add_argument(
        "--oss-compose-file",
        default=None,
        help="Optional compose file override for execute_backend mode.",
    )
    parser.add_argument(
        "--strict-model-backends",
        action="store_true",
        help="Fail backend run when advanced model backends are unavailable.",
    )
    parser.add_argument(
        "--source-data-root",
        default=None,
        help="Optional root directory for production CSV source datasets.",
    )
    parser.add_argument(
        "--require-real-data",
        action="store_true",
        help="Fail backend execution when real source datasets are missing.",
    )
    return parser.parse_args()


def load_runtime_settings(config_path: Path) -> tuple[dict[str, Any], list[str]]:
    """Load runtime settings with defaults and relaxed validation."""
    settings = copy.deepcopy(DEFAULT_RUNTIME_SETTINGS)
    warnings: list[str] = []

    if not config_path.exists():
        return settings, warnings

    try:
        with config_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except OSError as exc:
        warnings.append(f"Failed to read runtime config {config_path.as_posix()}: {exc}")
        return settings, warnings
    except yaml.YAMLError as exc:
        warnings.append(f"Invalid YAML in runtime config {config_path.as_posix()}: {exc}")
        return settings, warnings

    if not isinstance(raw, dict):
        warnings.append(
            f"Runtime config must be an object: {config_path.as_posix()}"
        )
        return settings, warnings

    mode = raw.get("mode")
    if isinstance(mode, str):
        settings["mode"] = mode

    execution = raw.get("execution")
    if isinstance(execution, dict):
        for key in settings["execution"]:
            if key in execution:
                settings["execution"][key] = execution[key]
    elif execution is not None:
        warnings.append("runtime.execution must be an object; defaults applied.")

    return settings, warnings


def apply_runtime_overrides(settings: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Apply CLI overrides on top of runtime settings."""
    merged = copy.deepcopy(settings)

    if args.runtime_mode:
        merged["mode"] = args.runtime_mode
    if args.run_backend:
        merged["mode"] = RUNTIME_MODE_EXECUTE

    execution = merged["execution"]
    if args.use_case is not None:
        execution["use_case_id"] = args.use_case
    if args.infra_profile is not None:
        execution["infra_profile"] = args.infra_profile
    if args.seed is not None:
        execution["seed"] = args.seed
    if getattr(args, "execution_mode", None) is not None:
        execution["runtime_mode"] = str(args.execution_mode)
    if getattr(args, "scenario_id", None) is not None:
        execution["scenario_id"] = str(args.scenario_id).strip() or None
    if getattr(args, "failure_injection", None):
        execution["failure_injection"] = [str(item).strip() for item in args.failure_injection if str(item).strip()]
    if args.output_dir is not None:
        execution["output_dir"] = args.output_dir
    if args.oss_compose_file is not None:
        execution["oss_compose_file"] = args.oss_compose_file
    if getattr(args, "strict_model_backends", False):
        execution["strict_model_backends"] = True
    if getattr(args, "source_data_root", None) is not None:
        execution["source_data_root"] = args.source_data_root
    if getattr(args, "require_real_data", False):
        execution["require_real_data"] = True

    return merged


def execute_backend_if_requested(
    runtime_settings: dict[str, Any], config_dir: Path
) -> tuple[dict[str, Any], list[str]]:
    """Run orchestrator when mode is execute_backend and capture execution metadata."""
    report: dict[str, Any] = {
        "mode": runtime_settings.get("mode", RUNTIME_MODE_LATEST),
        "backend_executed": False,
        "execution_scope": "none",
        "executed_use_cases": [],
        "run_ids": {},
        "infra_profile": runtime_settings.get("execution", {}).get("infra_profile", "local"),
        "seed": runtime_settings.get("execution", {}).get("seed", 0),
        "runtime_mode": runtime_settings.get("execution", {}).get("runtime_mode", "default"),
        "scenario_id": runtime_settings.get("execution", {}).get("scenario_id"),
        "failure_injection": list(runtime_settings.get("execution", {}).get("failure_injection", [])),
        "output_dir": runtime_settings.get("execution", {}).get("output_dir", "artifacts"),
        "strict_model_backends": bool(
            runtime_settings.get("execution", {}).get("strict_model_backends", False)
        ),
        "executed_at_utc": None,
    }
    warnings: list[str] = []

    if runtime_settings.get("mode") != RUNTIME_MODE_EXECUTE:
        return report, warnings

    execution = runtime_settings.get("execution", {})
    use_case_id = execution.get("use_case_id")
    infra_profile = str(execution.get("infra_profile", "local"))
    seed = int(execution.get("seed", 101))
    runtime_mode = str(execution.get("runtime_mode", "default"))
    scenario_id = execution.get("scenario_id")
    failure_injection = execution.get("failure_injection", [])
    output_dir = Path(str(execution.get("output_dir", "artifacts")))
    oss_compose_file = Path(str(execution.get("oss_compose_file", "infra/docker-compose.oss.yml")))
    strict_model_backends = bool(execution.get("strict_model_backends", False))
    source_data_root_raw = execution.get("source_data_root")
    source_data_root = (
        Path(str(source_data_root_raw))
        if isinstance(source_data_root_raw, str) and source_data_root_raw.strip()
        else None
    )
    require_real_data = bool(execution.get("require_real_data", False))

    report["execution_scope"] = "single_use_case" if use_case_id else "all_use_cases"

    try:
        from stack.orchestrator import run_full_stack, run_full_stack_all

        if use_case_id:
            summary = run_full_stack(
                use_case_id=str(use_case_id),
                config_dir=config_dir,
                output_dir=output_dir,
                seed=seed,
                infra_profile=infra_profile,
                oss_compose_file=oss_compose_file,
                strict_model_backends=strict_model_backends,
                source_data_root=source_data_root,
                require_real_data=require_real_data,
                runtime_mode=runtime_mode,
                scenario_id=str(scenario_id).strip() if isinstance(scenario_id, str) and scenario_id.strip() else None,
                failure_injection=[
                    str(item).strip()
                    for item in failure_injection
                    if str(item).strip()
                ],
            )
            summaries = [summary]
        else:
            summaries = run_full_stack_all(
                config_dir=config_dir,
                output_dir=output_dir,
                seed=seed,
                infra_profile=infra_profile,
                oss_compose_file=oss_compose_file,
                strict_model_backends=strict_model_backends,
                source_data_root=source_data_root,
                require_real_data=require_real_data,
                runtime_mode=runtime_mode,
                scenario_id=str(scenario_id).strip() if isinstance(scenario_id, str) and scenario_id.strip() else None,
                failure_injection=[
                    str(item).strip()
                    for item in failure_injection
                    if str(item).strip()
                ],
            )

        report["backend_executed"] = True
        report["executed_use_cases"] = [
            str(summary.get("use_case_id", "")) for summary in summaries if summary.get("use_case_id")
        ]
        report["run_ids"] = {
            str(summary.get("use_case_id")): str(summary.get("run_id"))
            for summary in summaries
            if summary.get("use_case_id") and summary.get("run_id")
        }
        report["executed_at_utc"] = datetime.now(timezone.utc).isoformat()

    except Exception as exc:  # pragma: no cover - defensive fallback path
        warnings.append(f"Backend execution failed; continuing with existing artifacts. Error: {exc}")

    return report, warnings


def discover_latest_summaries(artifacts_root: Path) -> tuple[dict[str, LatestSummary], list[str]]:
    """Find latest summary per use case using run_id lexical ordering."""
    latest: dict[str, LatestSummary] = {}
    warnings: list[str] = []

    if not artifacts_root.exists():
        warnings.append(f"Artifacts root does not exist: {artifacts_root.as_posix()}")
        return latest, warnings

    for summary_path in sorted(artifacts_root.glob("*/*/summary.json")):
        use_case_id = summary_path.parents[1].name
        run_id = summary_path.parent.name

        try:
            data = _read_json(summary_path)
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"Failed to parse {summary_path.as_posix()}: {exc}")
            continue

        current = latest.get(use_case_id)
        if current is None or run_id > current.run_id:
            latest[use_case_id] = LatestSummary(run_id=run_id, path=summary_path, data=data)

    return latest, warnings


def build_view_model(
    config_dir: Path,
    artifacts_root: Path,
    runtime_report: dict[str, Any] | None = None,
    extra_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build contract-driven UI payload with business and technical sections."""
    latest_map, warnings = discover_latest_summaries(artifacts_root=artifacts_root)
    all_warnings = list(extra_warnings or []) + warnings

    use_case_payloads: list[dict[str, Any]] = []
    for config_path in list_config_paths(config_dir=config_dir):
        contract = load_contract(config_path)
        narrative = USE_CASE_NARRATIVES.get(
            contract.use_case_id,
            {
                "business_problem": "Business problem statement not defined.",
                "business_outcome": "Business outcome statement not defined.",
            },
        )

        latest = latest_map.get(contract.use_case_id)
        run_payload = _build_latest_run_payload(contract=contract, latest=latest)

        use_case_payloads.append(
            {
                "use_case_id": contract.use_case_id,
                "name": contract.name,
                "primary_kpi": contract.primary_kpi,
                "business_problem": narrative["business_problem"],
                "business_outcome": narrative["business_outcome"],
                "contract": {
                    "baseline": contract.baseline,
                    "target": contract.target,
                    "entities": contract.entities,
                    "features": contract.features,
                    "output_type": contract.output_contract.type,
                    "output_fields": contract.output_contract.fields,
                    "sla_latency_ms": contract.output_contract.sla_latency_ms,
                    "refresh": contract.output_contract.refresh,
                    "decision_policy": contract.decision_policy,
                    "experiment": contract.experiment,
                    "governance": contract.governance,
                    "monitoring": contract.monitoring,
                },
                "latest_run": run_payload,
            }
        )

    use_case_payloads.sort(key=lambda row: row["use_case_id"])

    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "config_root": config_dir.as_posix(),
            "artifacts_root": artifacts_root.as_posix(),
            "adapter": "ui/adapter/build_view_model.py",
            "runtime": runtime_report or {},
            "warnings": all_warnings,
            "scenario_library": list_scenario_presets(),
        },
        "platform_flow": ARCHITECTURE_FLOW,
        "portfolio_snapshot": _build_portfolio_snapshot(use_case_payloads),
        "use_cases": use_case_payloads,
    }


def _build_latest_run_payload(
    contract: UseCaseContract, latest: LatestSummary | None
) -> dict[str, Any] | None:
    """Convert raw summary JSON into compact UI-facing technical metadata."""
    if latest is None:
        return None

    summary = latest.data
    artifacts = dict(summary.get("artifacts", {}))

    monitoring_report = _load_monitoring_report(artifacts)
    artifact_checks = _build_artifact_file_checks(artifacts=artifacts)
    stage_health = _build_stage_health(summary=summary, artifact_checks=artifact_checks)

    return {
        "run_id": str(summary.get("run_id", latest.run_id)),
        "summary_path": str(latest.path.as_posix()),
        "run_status": str(summary.get("run_status", "unknown")),
        "infra_profile": str(summary.get("infra_profile", "local")),
        "seed": int(summary.get("seed", 0)),
        "records": dict(summary.get("records", {})),
        "model_metrics": dict(summary.get("model_metrics", {})),
        "metric_highlights": _metric_highlights(summary.get("model_metrics", {})),
        "monitoring_report": monitoring_report,
        "artifacts": artifacts,
        "artifact_file_checks": artifact_checks,
        "stage_health": stage_health,
        "guided_steps": _build_guided_steps(
            contract=contract,
            summary=summary,
            artifacts=artifacts,
            stage_health=stage_health,
        ),
        "oss_runtime": _compact_oss_section(summary.get("oss_runtime")),
        "oss_mirror": _compact_oss_section(summary.get("oss_mirror")),
    }


def _build_portfolio_snapshot(use_cases: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate latest-run counters for top-level dashboard tiles."""
    with_runs = 0
    pass_count = 0
    fail_count = 0
    total_curated_rows = 0

    for item in use_cases:
        latest = item.get("latest_run")
        if latest is None:
            continue
        with_runs += 1
        if latest.get("run_status") == "pass":
            pass_count += 1
        else:
            fail_count += 1

        records = latest.get("records", {})
        curated_rows = records.get("curated_rows")
        if isinstance(curated_rows, int):
            total_curated_rows += curated_rows

    return {
        "use_cases_total": len(use_cases),
        "use_cases_with_runs": with_runs,
        "latest_runs_pass": pass_count,
        "latest_runs_fail": fail_count,
        "total_latest_curated_rows": total_curated_rows,
    }


def _metric_highlights(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    """Emit deterministic metric highlights excluding the primary KPI label key."""
    highlights: list[dict[str, Any]] = []
    if not isinstance(metrics, dict):
        return highlights

    for key in sorted(metrics):
        if key == "primary_kpi":
            continue
        highlights.append({"name": key, "value": metrics[key]})
    return highlights


def _load_monitoring_report(artifacts: dict[str, str]) -> dict[str, Any] | None:
    """Load monitoring report JSON when present, otherwise return None."""
    path_text = artifacts.get("monitoring_report")
    if not path_text:
        return None

    path = _to_abs_path(path_text)
    if not path.exists():
        return None

    try:
        return _read_json(path)
    except (OSError, json.JSONDecodeError):
        return None


def _build_artifact_file_checks(artifacts: dict[str, str]) -> list[dict[str, Any]]:
    """Flatten artifact path maps into existence checks for technical UI display."""
    checks: list[dict[str, Any]] = []

    ingestion = artifacts.get("ingestion_event_bus", {})
    if isinstance(ingestion, dict):
        for topic in sorted(ingestion):
            path_text = str(ingestion[topic])
            checks.append(
                {
                    "label": f"topic::{topic}",
                    "path": path_text,
                    "exists": _to_abs_path(path_text).exists(),
                }
            )

    for key in sorted(artifacts):
        if key == "ingestion_event_bus":
            continue
        path_value = artifacts.get(key)
        if not isinstance(path_value, str):
            continue
        checks.append(
            {
                "label": key,
                "path": path_value,
                "exists": _to_abs_path(path_value).exists(),
            }
        )

    return checks


def _build_stage_health(
    summary: dict[str, Any], artifact_checks: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """Compute stage-level pass/fail indicators from records and artifacts."""
    artifacts = summary.get("artifacts", {})
    records = summary.get("records", {})
    check_by_label = {row["label"]: row["exists"] for row in artifact_checks}

    stage_rows: list[dict[str, str]] = []
    for requirement in STAGE_REQUIREMENTS:
        kind = requirement["kind"]
        status = "pass"
        detail = ""

        if kind == "source_tables":
            source_tables = records.get("source_tables", {}) if isinstance(records, dict) else {}
            total = 0
            if isinstance(source_tables, dict):
                for value in source_tables.values():
                    if isinstance(value, int):
                        total += value
            if total <= 0:
                status = "fail"
                detail = "No source rows recorded."
            else:
                detail = f"{total} source rows observed across tables."

        elif kind == "topic_files":
            topic_map = artifacts.get("ingestion_event_bus", {}) if isinstance(artifacts, dict) else {}
            if not isinstance(topic_map, dict) or not topic_map:
                status = "fail"
                detail = "No ingestion topic artifacts found."
            else:
                missing = 0
                for topic in topic_map:
                    label = f"topic::{topic}"
                    if not check_by_label.get(label, False):
                        missing += 1
                if missing:
                    status = "fail"
                    detail = f"{missing} ingestion topic artifact(s) missing."
                else:
                    detail = f"{len(topic_map)} ingestion topic artifact(s) present."

        elif kind == "artifact_keys":
            missing_keys: list[str] = []
            for key in requirement.get("keys", []):
                if not isinstance(artifacts, dict):
                    missing_keys.append(key)
                    continue
                path = artifacts.get(key)
                if not isinstance(path, str):
                    missing_keys.append(key)
                    continue
                if not _to_abs_path(path).exists():
                    missing_keys.append(key)

            if missing_keys:
                status = "fail"
                detail = f"Missing artifact(s): {', '.join(missing_keys)}"
            else:
                detail = "Required artifacts found."

        stage_rows.append(
            {
                "layer_id": requirement["layer_id"],
                "label": requirement["label"],
                "status": status,
                "detail": detail,
            }
        )

    return stage_rows


def _build_guided_steps(
    contract: UseCaseContract,
    summary: dict[str, Any],
    artifacts: dict[str, Any],
    stage_health: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Build a technical guided walkthrough with per-stage input/output evidence."""
    records = summary.get("records", {}) if isinstance(summary.get("records", {}), dict) else {}
    source_tables = records.get("source_tables", {}) if isinstance(records.get("source_tables", {}), dict) else {}
    stage_map = {row.get("layer_id"): row for row in stage_health}
    flow_by_id = {row["layer_id"]: row for row in ARCHITECTURE_FLOW}

    ingestion_topics = artifacts.get("ingestion_event_bus", {})
    if not isinstance(ingestion_topics, dict):
        ingestion_topics = {}

    step_ids = [row["layer_id"] for row in sorted(ARCHITECTURE_FLOW, key=lambda r: r["order"])]
    steps: list[dict[str, Any]] = []
    for layer_id in step_ids:
        flow = flow_by_id[layer_id]
        stage = stage_map.get(layer_id, {})

        inputs: list[dict[str, Any]] = []
        outputs: list[dict[str, Any]] = []

        if layer_id == "data_sources":
            inputs = [
                {"name": "contract.entities", "value": ", ".join(contract.entities) or "n/a"},
                {"name": "contract.features", "value": str(len(contract.features))},
            ]
            for table_name in sorted(source_tables):
                outputs.append(
                    {
                        "name": table_name,
                        "path": None,
                        "exists": True,
                        "row_count": source_tables[table_name],
                        "sample_fields": [],
                        "note": "Source table row count from summary.",
                    }
                )

        elif layer_id == "ingestion_event_bus":
            inputs = [{"name": "source_tables", "value": str(len(source_tables))}]
            for topic in sorted(ingestion_topics):
                outputs.append(_artifact_output(name=topic, path_text=str(ingestion_topics[topic])))

        elif layer_id == "raw_curated_storage":
            inputs = [{"name": "topic_files", "value": str(len(ingestion_topics))}]
            for key in ["raw_events", "curated_records", "curated_records_jsonl"]:
                path_text = artifacts.get(key)
                if isinstance(path_text, str):
                    outputs.append(_artifact_output(name=key, path_text=path_text))

        elif layer_id == "identity_customer_360":
            inputs = [{"name": "curated_rows", "value": str(records.get("curated_rows", "n/a"))}]
            for key in ["identity_map", "resolved_records", "note"]:
                path_text = artifacts.get(key)
                if isinstance(path_text, str):
                    outputs.append(_artifact_output(name=key, path_text=path_text))

        elif layer_id == "feature_layer":
            inputs = [{"name": "resolved_rows", "value": str(records.get("curated_rows", "n/a"))}]
            path_text = artifacts.get("feature_rows")
            if isinstance(path_text, str):
                outputs.append(_artifact_output(name="feature_rows", path_text=path_text))

        elif layer_id == "model_layer":
            inputs = [
                {"name": "feature_rows", "value": str(records.get("feature_rows", "n/a"))},
                {
                    "name": "output_contract_fields",
                    "value": str(len(contract.output_contract.fields)),
                },
            ]
            path_text = artifacts.get("model_predictions")
            if isinstance(path_text, str):
                outputs.append(_artifact_output(name="model_predictions", path_text=path_text))
            metrics = summary.get("model_metrics", {})
            if isinstance(metrics, dict):
                outputs.append(
                    {
                        "name": "model_metrics",
                        "path": None,
                        "exists": True,
                        "row_count": None,
                        "sample_fields": sorted(metrics.keys()),
                        "note": "Metric keys reported by model layer.",
                    }
                )

        elif layer_id == "serving_activation":
            inputs = [{"name": "model_rows", "value": str(records.get("model_rows", "n/a"))}]
            path_text = artifacts.get("activation_payloads")
            if isinstance(path_text, str):
                outputs.append(_artifact_output(name="activation_payloads", path_text=path_text))

        elif layer_id == "monitoring_governance":
            inputs = [{"name": "model_metrics", "value": str(len(summary.get("model_metrics", {})))}]
            path_text = artifacts.get("monitoring_report")
            if isinstance(path_text, str):
                outputs.append(_artifact_output(name="monitoring_report", path_text=path_text))

        steps.append(
            {
                "layer_id": layer_id,
                "label": flow["label"],
                "status": stage.get("status", "unknown"),
                "detail": stage.get("detail", "No stage detail available."),
                "explanation": flow["technical_summary"],
                "inputs": inputs,
                "outputs": outputs,
            }
        )

    return steps


def _artifact_output(name: str, path_text: str) -> dict[str, Any]:
    """Return artifact metadata for guided technical exploration."""
    abs_path = _to_abs_path(path_text)
    exists = abs_path.exists()
    row_count: int | None = None
    sample_fields: list[str] = []
    note = ""

    if exists:
        row_count, sample_fields, note = _summarize_artifact(abs_path)

    return {
        "name": name,
        "path": path_text,
        "exists": exists,
        "row_count": row_count,
        "sample_fields": sample_fields,
        "note": note,
    }


def _summarize_artifact(path: Path) -> tuple[int | None, list[str], str]:
    """Read lightweight artifact stats for UI explanation panels."""
    suffix = path.suffix.lower()

    try:
        if suffix == ".jsonl":
            count = 0
            sample_fields: list[str] = []
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    count += 1
                    if sample_fields:
                        continue
                    parsed = json.loads(stripped)
                    if isinstance(parsed, dict):
                        if isinstance(parsed.get("payload"), dict):
                            sample_fields = sorted(parsed["payload"].keys())[:12]
                        else:
                            sample_fields = sorted(parsed.keys())[:12]
            return count, sample_fields, ""

        if suffix == ".json":
            parsed = _read_json(path)

            if isinstance(parsed, dict) and isinstance(parsed.get("rows"), list):
                rows = parsed["rows"]
                fields: list[str] = []
                if rows and isinstance(rows[0], dict):
                    fields = sorted(rows[0].keys())[:12]
                return len(rows), fields, ""

            if isinstance(parsed, list):
                fields = sorted(parsed[0].keys())[:12] if parsed and isinstance(parsed[0], dict) else []
                return len(parsed), fields, ""

            if isinstance(parsed, dict):
                return None, sorted(parsed.keys())[:12], "Object artifact"

    except (OSError, json.JSONDecodeError):
        return None, [], "Failed to summarize artifact"

    return None, [], "Unsupported artifact type"


def _compact_oss_section(section: Any) -> dict[str, Any] | None:
    """Keep only counters/status from OSS sections to avoid huge UI payloads."""
    if not isinstance(section, dict):
        return None

    keys = [
        "status",
        "compose_file",
        "kafka_topics_published",
        "kafka_messages_consumed",
        "postgres_rows_loaded",
        "minio_objects_uploaded",
        "warnings",
    ]
    compact = {key: section.get(key) for key in keys if key in section}

    ingestion = section.get("ingestion_event_bus")
    if isinstance(ingestion, dict):
        compact["topics"] = sorted(ingestion)

    return compact


def _read_json(path: Path) -> Any:
    """Read JSON file and return parsed object."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _to_abs_path(path_text: str) -> Path:
    """Resolve path against repo root when path is relative."""
    path = Path(path_text)
    if path.is_absolute():
        return path
    return ROOT / path


def main() -> int:
    """CLI entrypoint for generating the UI view model."""
    args = parse_args()

    config_dir = Path(args.config_dir)
    runtime_config_path = Path(args.runtime_config)

    runtime_settings, runtime_warnings = load_runtime_settings(config_path=runtime_config_path)
    runtime_settings = apply_runtime_overrides(settings=runtime_settings, args=args)

    runtime_report, execution_warnings = execute_backend_if_requested(
        runtime_settings=runtime_settings,
        config_dir=config_dir,
    )

    execution = runtime_settings.get("execution", {})
    artifacts_root = Path(args.artifacts_root) if args.artifacts_root else Path(str(execution.get("output_dir", DEFAULT_ARTIFACTS_ROOT.as_posix())))
    output_path = Path(args.output)

    payload = build_view_model(
        config_dir=config_dir,
        artifacts_root=artifacts_root,
        runtime_report=runtime_report,
        extra_warnings=runtime_warnings + execution_warnings,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote UI view model: {output_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
