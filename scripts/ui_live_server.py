#!/usr/bin/env python3
"""Serve UI + lightweight run API for browser-driven backend execution.

Endpoints:
1) GET /api/health -> server health
2) GET /api/scenarios -> scenario catalog and runtime-mode metadata
3) GET /api/oss-inventory -> OSS component/license inventory
5) GET /metrics -> Prometheus-compatible runtime/run metrics
6) GET /api/view-model -> latest UI view model JSON
7) POST /api/run -> trigger backend execution and rebuild view model
8) GET /api/jobs -> list recent run jobs
9) GET /api/jobs/<job_id> -> job status/details
10) POST /api/simulation/session -> create stage-by-stage simulation session
11) GET /api/simulation/session/<session_id> -> simulation session state
12) POST /api/simulation/session/<session_id>/run-all -> execute/reveal all stages
13) POST /api/simulation/session/<session_id>/run-next -> execute/reveal next stage
14) POST /api/simulation/session/<session_id>/reset -> reset stage cursor
15) POST /api/simulation/session/<session_id>/pause -> pause simulation progression
16) POST /api/simulation/session/<session_id>/resume -> resume simulation progression
17) GET /api/artifacts/download?path=... -> download one artifact file
18) GET /api/run-history?use_case_id=...&limit=...&status=...&infra=...&baseline=... -> recent run comparisons
19) GET /api/runs?use_case_id=...&status=...&infra=...&seed=...&q=... -> run registry listing
20) GET /api/runs/<use_case_id>/<run_id> -> one run summary
21) GET /api/runs/<use_case_id>/<run_id>/stages -> stage-level technical details
22) GET /api/runs/<use_case_id>/<run_id>/data-quality -> compact data-quality blockers/warnings
23) GET /api/portfolio/summary?status=...&infra=... -> cross-use-case KPI rollup
24) POST /api/inference/online -> single-record scoring + activation
25) POST /api/inference/batch -> multi-record scoring + activation
26) GET /api/contracts/inference -> JSON schema export for inference contracts
27) GET /api/openapi.json -> OpenAPI-style endpoint/schema export
28) POST /api/governance/approve -> approve deployment readiness for one run

Static UI is served from repository root, with default redirect:
`/` -> `/ui/experience/`
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import mimetypes
import subprocess
import sys
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

# Ensure direct script execution (`python scripts/ui_live_server.py`) can
# import repository modules such as `stack.*`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.contract_loader import load_contract_by_id
from models import get_model_for_use_case
from stack.layers.serving_activation import (
    build_activation_payloads,
    get_activation_contract_fields,
)
from stack.model_registry import list_model_registry_entries
from stack.run_registry import get_run_summary, list_run_summaries
from stack.governance import approve_run_governance
from stack.orchestrator import run_full_stack
from stack.scenario_library import (
    FAILURE_INJECTION_KEYS,
    list_scenario_presets,
)

ROOT = PROJECT_ROOT
VIEW_MODEL_PATH = ROOT / "ui" / "data" / "view_model.json"
MAX_JOBS = 25
MAX_RUN_HISTORY_LIMIT = 12
MAX_PORTFOLIO_LIMIT_PER_USE_CASE = 20
RUN_STATUS_FILTERS = {"all", "pass", "fail"}
INFRA_FILTERS = {"all", "local", "oss"}
RUNS_SORT_VALUES = {"asc", "desc"}
EXECUTION_RUNTIME_MODES = {"default", "synthetic_only"}
INFERENCE_REGISTRY_STAGES = {"auto", "candidate", "approved", "prod"}
INFERENCE_REGISTRY_RESOLUTION_ORDER = ["prod", "approved", "candidate"]
INFERENCE_SCHEMA_VERSION = "1.0.0"
OPENAPI_VERSION = "3.1.0"
OSS_INVENTORY_PATH = ROOT / "docs" / "OSS_INVENTORY.json"
OSS_INVENTORY_GENERATOR = ROOT / "scripts" / "generate_oss_inventory.py"
ENTERPRISE_HARDENING_CONFIG_PATH = ROOT / "ui" / "config" / "enterprise_hardening.json"

ENTERPRISE_HARDENING_MODULES: list[dict[str, str]] = [
    {
        "module_id": "mlflow",
        "name": "Model Tracking",
        "technology": "MLflow adapter",
        "import_name": "mlflow",
        "purpose": "Experiment tracking and model registry lineage.",
        "target_stage": "model_layer",
        "category": "lightweight",
        "activation_mode": "optional_package",
    },
    {
        "module_id": "data_quality_artifacts",
        "name": "DQ Compatibility Artifacts",
        "technology": "Great Expectations-compatible artifacts",
        "import_name": "",
        "purpose": "Great Expectations-compatible validation export from current DQ gates.",
        "target_stage": "monitoring_governance",
        "category": "lightweight",
        "activation_mode": "built_in",
    },
    {
        "module_id": "monitoring_artifacts",
        "name": "Monitoring Compatibility Artifacts",
        "technology": "Evidently-compatible summary",
        "import_name": "",
        "purpose": "Evidently-compatible model and governance monitoring summary.",
        "target_stage": "monitoring_governance",
        "category": "lightweight",
        "activation_mode": "built_in",
    },
    {
        "module_id": "prometheus_metrics",
        "name": "Prometheus Metrics Endpoint",
        "technology": "Prometheus /metrics",
        "import_name": "",
        "purpose": "Prometheus text metrics exposed by the live UI/API server.",
        "target_stage": "monitoring_governance",
        "category": "lightweight",
        "activation_mode": "built_in",
    },
    {
        "module_id": "feast",
        "name": "Feature Store",
        "technology": "Feast adapter",
        "import_name": "feast",
        "purpose": "Feature store for offline/online feature consistency.",
        "target_stage": "feature_layer",
        "category": "heavy",
        "activation_mode": "profile_driven",
    },
    {
        "module_id": "splink",
        "name": "Identity Resolution",
        "technology": "Splink adapter",
        "import_name": "splink",
        "purpose": "Probabilistic entity resolution for Customer 360 enrichment.",
        "target_stage": "identity_customer_360",
        "category": "heavy",
        "activation_mode": "profile_driven",
    },
    {
        "module_id": "airflow",
        "name": "Apache Airflow",
        "technology": "Airflow DAG adapter",
        "import_name": "airflow",
        "purpose": "Scheduled DAG orchestration for product-like runtime.",
        "target_stage": "pipeline_orchestration",
        "category": "heavy",
        "activation_mode": "profile_driven",
    },
    {
        "module_id": "keycloak",
        "name": "Keycloak",
        "technology": "Keycloak OIDC adapter",
        "import_name": "keycloak",
        "purpose": "OIDC and role-based access control for multi-user deployments.",
        "target_stage": "serving_activation",
        "category": "heavy",
        "activation_mode": "profile_driven",
    },
]

INFERENCE_INPUT_CONTRACTS: dict[str, dict[str, dict[str, str]]] = {
    "UC-NBA-RET-001": {
        "required": {
            "customer_id": "string",
            "risk_score": "number",
            "value_score": "number",
            "score_ts": "string",
        },
        "optional": {
            "historical_action_id": "string",
            "observed_uplift": "number",
            "retained_30d": "binary_label",
        },
    },
    "UC-CHURN-RET-002": {
        "required": {
            "customer_id": "string",
            "recency_norm": "number",
            "engagement_norm": "number",
            "support_ticket_norm": "number",
            "score_ts": "string",
        },
        "optional": {
            "churned_60d": "binary_label",
        },
    },
    "UC-MMM-PLN-003": {
        "required": {
            "period": "string",
            "channel": "string",
            "weekly_spend": "number",
            "impressions": "number",
            "clicks": "number",
            "promo_index": "number",
        },
        "optional": {
            "observed_revenue": "number",
            "seasonality_index": "number",
            "macro_index": "number",
        },
    },
    "UC-INCR-MKT-004": {
        "required": {
            "campaign_id": "string",
            "test_window": "string",
            "treated_customers": "number",
            "control_customers": "number",
            "treated_conversions": "number",
            "control_conversions": "number",
            "aov": "number",
            "campaign_cost": "number",
        },
        "optional": {
            "pre_period_conversion_rate": "number",
            "audience_tier": "string",
        },
    },
}

INFERENCE_OUTPUT_FIELD_TYPE_HINTS: dict[str, str] = {
    "customer_id": "string",
    "action_id": "string",
    "action_channel": "string",
    "expected_uplift": "number",
    "confidence": "number",
    "reason_codes": "string_array",
    "score_ts": "string",
    "model_version": "string",
    "policy_version": "string",
    "churn_risk_score": "number",
    "risk_band": "string",
    "recommended_action": "string",
    "period": "string",
    "channel": "string",
    "base_contribution": "number",
    "incremental_contribution": "number",
    "response_curve_params": "object",
    "saturation_point": "number",
    "recommended_spend": "number",
    "expected_incremental_revenue": "number",
    "uncertainty_interval": "object",
    "campaign_id": "string",
    "test_window": "string",
    "incremental_lift": "number",
    "ci_low": "number",
    "ci_high": "number",
    "p_value": "number",
    "iROAS": "number",
    "decision_recommendation": "string",
    "analysis_version": "string",
}

ACTIVATION_FIELD_TYPE_HINTS: dict[str, str] = {
    "destination": "string",
    "customer_id": "string",
    "action_id": "string",
    "action_channel": "string",
    "priority": "string",
    "reason_code": "string",
    "recommended_action": "string",
    "risk_band": "string",
    "channel": "string",
    "recommended_spend": "number",
    "expected_incremental_revenue": "number",
    "uncertainty_interval": "object",
    "campaign_id": "string",
    "decision_recommendation": "string",
    "incremental_lift": "number",
    "iROAS": "number",
}

STAGE_DEFINITIONS: list[tuple[str, str]] = [
    ("data_sources", "Data Sources"),
    ("ingestion_event_bus", "Ingestion + Event Bus"),
    ("raw_curated_storage", "Raw Storage + Curated Warehouse"),
    ("identity_customer_360", "Identity Resolution + Customer 360"),
    ("feature_layer", "Feature Layer"),
    ("model_layer", "Model Layer"),
    ("serving_activation", "Serving + Activation"),
    ("monitoring_governance", "Monitoring + Governance"),
]

JOBS_LOCK = threading.Lock()
JOBS: dict[str, "RunJob"] = {}
SIM_SESSIONS_LOCK = threading.Lock()
SIM_SESSIONS: dict[str, "SimulationSession"] = {}


@dataclass
class RunJob:
    """Background execution job metadata."""

    job_id: str
    status: str
    created_at_utc: str
    request: dict[str, Any]
    command: list[str]
    started_at_utc: str | None = None
    finished_at_utc: str | None = None
    exit_code: int | None = None
    output_tail: str = ""


@dataclass
class SimulationSession:
    """In-memory stage-by-stage simulation state."""

    session_id: str
    use_case_id: str
    infra_profile: str
    seed: int
    runtime_mode: str
    scenario_id: str | None
    failure_injection: list[str]
    created_at_utc: str
    updated_at_utc: str
    run_id: str | None = None
    run_status: str | None = None
    stage_cursor: int = 0
    stage_total: int = len(STAGE_DEFINITIONS)
    paused: bool = False
    last_error: str | None = None


def parse_args() -> argparse.Namespace:
    """Parse CLI args for the live UI server."""
    parser = argparse.ArgumentParser(description="Serve live UI + run API.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host.")
    parser.add_argument("--port", type=int, default=8080, help="Bind port.")
    return parser.parse_args()


def build_backend_command(
    *,
    use_case_id: str | None,
    infra_profile: str,
    seed: int,
    runtime_mode: str = "default",
    scenario_id: str | None = None,
    failure_injection: list[str] | None = None,
    output_dir: str = "artifacts",
    oss_compose_file: str = "infra/docker-compose.oss.yml",
    strict_model_backends: bool = False,
    source_data_root: str | None = None,
    require_real_data: bool = False,
) -> list[str]:
    """Build adapter command that executes backend and writes UI data."""
    cmd = [
        sys.executable,
        "ui/adapter/build_view_model.py",
        "--runtime-mode",
        "execute_backend",
        "--infra-profile",
        infra_profile,
        "--seed",
        str(seed),
        "--execution-mode",
        runtime_mode,
        "--output-dir",
        output_dir,
        "--oss-compose-file",
        oss_compose_file,
    ]
    if scenario_id:
        cmd.extend(["--scenario-id", scenario_id])
    for toggle in failure_injection or []:
        cmd.extend(["--failure-injection", toggle])
    if strict_model_backends:
        cmd.append("--strict-model-backends")
    if source_data_root:
        cmd.extend(["--source-data-root", source_data_root])
    if require_real_data:
        cmd.append("--require-real-data")
    if use_case_id:
        cmd.extend(["--use-case", use_case_id])
    return cmd


def submit_run_job(request: dict[str, Any]) -> RunJob:
    """Create and dispatch background backend execution job."""
    use_case_id = request.get("use_case_id")
    infra_profile = request.get("infra_profile", "local")
    seed = int(request.get("seed", 101))
    runtime_mode = str(request.get("runtime_mode", "default")).strip().lower() or "default"
    scenario_id = (
        str(request.get("scenario_id", "")).strip()
        if request.get("scenario_id") is not None
        else None
    )
    if scenario_id == "":
        scenario_id = None
    failure_injection = _normalize_failure_injection_flags(request.get("failure_injection"))
    output_dir = str(request.get("output_dir", "artifacts"))
    oss_compose_file = str(request.get("oss_compose_file", "infra/docker-compose.oss.yml"))
    strict_model_backends = bool(request.get("strict_model_backends", False))
    source_data_root = request.get("source_data_root")
    require_real_data = bool(request.get("require_real_data", False))
    source_data_root_text = (
        str(source_data_root).strip() if isinstance(source_data_root, str) else None
    )

    command = build_backend_command(
        use_case_id=use_case_id,
        infra_profile=infra_profile,
        seed=seed,
        runtime_mode=runtime_mode,
        scenario_id=scenario_id,
        failure_injection=failure_injection,
        output_dir=output_dir,
        oss_compose_file=oss_compose_file,
        strict_model_backends=strict_model_backends,
        source_data_root=source_data_root_text,
        require_real_data=require_real_data,
    )

    job = RunJob(
        job_id=uuid.uuid4().hex,
        status="queued",
        created_at_utc=_utc_now(),
        request={
            "use_case_id": use_case_id,
            "infra_profile": infra_profile,
            "seed": seed,
            "runtime_mode": runtime_mode,
            "scenario_id": scenario_id,
            "failure_injection": failure_injection,
            "output_dir": output_dir,
            "oss_compose_file": oss_compose_file,
            "strict_model_backends": strict_model_backends,
            "source_data_root": source_data_root_text,
            "require_real_data": require_real_data,
        },
        command=command,
    )

    with JOBS_LOCK:
        JOBS[job.job_id] = job
        _prune_jobs_locked()

    worker = threading.Thread(
        target=_run_job_worker,
        args=(job.job_id,),
        daemon=True,
    )
    worker.start()
    return job


def list_jobs() -> list[dict[str, Any]]:
    """Return recent jobs sorted by creation time descending."""
    with JOBS_LOCK:
        jobs = sorted(JOBS.values(), key=lambda row: row.created_at_utc, reverse=True)
        return [asdict(row) for row in jobs]


def get_job(job_id: str) -> dict[str, Any] | None:
    """Return one job payload when found."""
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        return asdict(job) if job else None


def _run_job_worker(job_id: str) -> None:
    """Execute adapter command and persist completion status."""
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at_utc = _utc_now()
        command = list(job.command)

    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    merged_output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    if len(merged_output) > 12000:
        merged_output = merged_output[-12000:]

    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return
        job.exit_code = result.returncode
        job.finished_at_utc = _utc_now()
        job.output_tail = merged_output
        job.status = "succeeded" if result.returncode == 0 else "failed"


def _prune_jobs_locked() -> None:
    """Cap in-memory job history to avoid unbounded growth."""
    if len(JOBS) <= MAX_JOBS:
        return
    ordered = sorted(JOBS.values(), key=lambda row: row.created_at_utc, reverse=True)
    keep_ids = {row.job_id for row in ordered[:MAX_JOBS]}
    for job_id in list(JOBS):
        if job_id not in keep_ids:
            JOBS.pop(job_id, None)


def _utc_now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


class LiveUIHandler(SimpleHTTPRequestHandler):
    """HTTP handler for API + static UI routing."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/ui/experience/")
            self.end_headers()
            return

        if path == "/api/health":
            self._send_json({"status": "ok", "server_time_utc": _utc_now()})
            return

        if path == "/api/scenarios":
            query = parse_qs(parsed.query or "")
            use_case_id = (query.get("use_case_id", [""])[0] or "").strip() or None
            self._send_json(
                {
                    "generated_at_utc": _utc_now(),
                    "use_case_id": use_case_id,
                    "scenarios": list_scenario_presets(use_case_id=use_case_id),
                    "runtime_modes": sorted(EXECUTION_RUNTIME_MODES),
                    "failure_injection_keys": sorted(FAILURE_INJECTION_KEYS),
                }
            )
            return

        if path == "/api/oss-inventory":
            payload = load_oss_inventory()
            if payload is None:
                self._send_error(
                    code="oss_inventory_unavailable",
                    message="Unable to load OSS inventory.",
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return
            self._send_json(payload)
            return

        if path == "/api/enterprise-hardening":
            query = parse_qs(parsed.query or "")
            profile = (query.get("profile", ["standalone"])[0] or "standalone").strip().lower()
            if profile not in {"standalone", "product_like"}:
                self._send_error(
                    code="invalid_query",
                    message="Query parameter 'profile' must be 'standalone' or 'product_like'.",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            self._send_json(load_enterprise_hardening(profile=profile))
            return

        if path == "/metrics":
            self._send_text(
                build_prometheus_metrics(artifacts_root=ROOT / "artifacts"),
                content_type="text/plain; version=0.0.4; charset=utf-8",
            )
            return

        if path == "/api/view-model":
            payload = _load_or_build_view_model()
            if payload is None:
                self._send_error(
                    code="view_model_unavailable",
                    message="Unable to load or build view model.",
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return
            self._send_json(payload)
            return

        if path == "/api/contracts/inference":
            self._send_json(build_inference_contract_export())
            return

        if path == "/api/openapi.json":
            forwarded_proto = str(self.headers.get("X-Forwarded-Proto", "http")).strip() or "http"
            host = str(self.headers.get("Host", "")).strip()
            base_url = f"{forwarded_proto}://{host}" if host else None
            self._send_json(build_openapi_spec(base_url=base_url))
            return

        if path == "/api/jobs":
            self._send_json({"jobs": list_jobs()})
            return

        if path == "/api/portfolio/summary":
            query = parse_qs(parsed.query or "")
            filters, validation_error = parse_portfolio_summary_query(query=query)
            if validation_error:
                self._send_error(
                    code="invalid_query",
                    message=validation_error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            payload = load_portfolio_summary(
                status_filter=filters["status_filter"],
                infra_filter=filters["infra_filter"],
                sort=filters["sort"],
                limit_per_use_case=filters["limit_per_use_case"],
                artifacts_root=ROOT / "artifacts",
            )
            self._send_json(payload)
            return

        if path == "/api/artifacts/download":
            query = parse_qs(parsed.query or "")
            path_values = query.get("path", [])
            if not path_values or not str(path_values[0]).strip():
                self._send_error(
                    code="missing_query_param",
                    message="Query parameter 'path' is required.",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            download_path, path_error = resolve_artifact_download_path(
                path_text=str(path_values[0]),
                artifacts_root=ROOT / "artifacts",
            )
            if path_error or download_path is None:
                self._send_error(
                    code="invalid_query",
                    message=path_error or "Invalid artifact path.",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            self._send_file(download_path)
            return

        if path == "/api/runs":
            query = parse_qs(parsed.query or "")
            filters, validation_error = parse_run_registry_query(query=query)
            if validation_error:
                self._send_error(
                    code="invalid_query",
                    message=validation_error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            payload = load_run_registry(
                artifacts_root=ROOT / "artifacts",
                use_case_id=filters["use_case_id"],
                limit=filters["limit"],
                offset=filters["offset"],
                status_filter=filters["status_filter"],
                infra_filter=filters["infra_filter"],
                seed=filters["seed"],
                sort=filters["sort"],
                query=filters["query"],
            )
            self._send_json(payload)
            return

        if path.startswith("/api/runs/") and path.endswith("/data-quality"):
            parsed_path, path_error = parse_run_data_quality_path(path=path)
            if path_error:
                self._send_error(
                    code="invalid_path",
                    message=path_error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            use_case_id = parsed_path["use_case_id"]
            run_id = parsed_path["run_id"]
            payload = load_run_data_quality_details(
                use_case_id=use_case_id,
                run_id=run_id,
                artifacts_root=ROOT / "artifacts",
            )
            if payload is None:
                self._send_error(
                    code="run_not_found",
                    message=f"Run not found for use_case_id={use_case_id}, run_id={run_id}",
                    status=HTTPStatus.NOT_FOUND,
                )
                return
            self._send_json(payload)
            return

        if path.startswith("/api/runs/") and path.endswith("/stages"):
            parsed_path, path_error = parse_run_stages_path(path=path)
            if path_error:
                self._send_error(
                    code="invalid_path",
                    message=path_error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            use_case_id = parsed_path["use_case_id"]
            run_id = parsed_path["run_id"]
            payload = load_run_stage_details(
                use_case_id=use_case_id,
                run_id=run_id,
                artifacts_root=ROOT / "artifacts",
            )
            if payload is None:
                self._send_error(
                    code="run_not_found",
                    message=f"Run not found for use_case_id={use_case_id}, run_id={run_id}",
                    status=HTTPStatus.NOT_FOUND,
                )
                return
            self._send_json(payload)
            return

        if path.startswith("/api/runs/"):
            parsed_path, path_error = parse_run_summary_path(path=path)
            if path_error:
                self._send_error(
                    code="invalid_path",
                    message=path_error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            use_case_id = parsed_path["use_case_id"]
            run_id = parsed_path["run_id"]
            payload = load_run_summary_details(
                use_case_id=use_case_id,
                run_id=run_id,
                artifacts_root=ROOT / "artifacts",
            )
            if payload is None:
                self._send_error(
                    code="run_not_found",
                    message=f"Run not found for use_case_id={use_case_id}, run_id={run_id}",
                    status=HTTPStatus.NOT_FOUND,
                )
                return
            self._send_json(payload)
            return

        if path == "/api/run-history":
            query = parse_qs(parsed.query or "")
            use_case_values = query.get("use_case_id", [])
            if not use_case_values or not use_case_values[0].strip():
                self._send_error(
                    code="missing_query_param",
                    message="Query parameter 'use_case_id' is required.",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            use_case_id = use_case_values[0].strip()
            limit_raw = (query.get("limit", ["6"])[0] or "6").strip()
            try:
                limit = int(limit_raw)
            except ValueError:
                self._send_error(
                    code="invalid_query",
                    message="Query parameter 'limit' must be an integer.",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            status_filter = (query.get("status", ["all"])[0] or "all").strip().lower()
            if status_filter not in RUN_STATUS_FILTERS:
                self._send_error(
                    code="invalid_query",
                    message=(
                        "Query parameter 'status' must be one of: "
                        + ", ".join(sorted(RUN_STATUS_FILTERS))
                    ),
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            infra_filter = (query.get("infra", ["all"])[0] or "all").strip().lower()
            if infra_filter not in INFRA_FILTERS:
                self._send_error(
                    code="invalid_query",
                    message=(
                        "Query parameter 'infra' must be one of: "
                        + ", ".join(sorted(INFRA_FILTERS))
                    ),
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            baseline = (query.get("baseline", ["latest"])[0] or "latest").strip()

            payload = load_run_history(
                use_case_id=use_case_id,
                limit=max(1, min(MAX_RUN_HISTORY_LIMIT, limit)),
                status_filter=status_filter,
                infra_filter=infra_filter,
                baseline=baseline,
            )
            self._send_json(payload)
            return

        if path.startswith("/api/jobs/"):
            job_id = path.replace("/api/jobs/", "", 1)
            payload = get_job(job_id)
            if payload is None:
                self._send_error(
                    code="job_not_found",
                    message=f"Unknown job_id: {job_id}",
                    status=HTTPStatus.NOT_FOUND,
                )
                return
            self._send_json(payload)
            return

        if path.startswith("/api/simulation/session/"):
            session_id = path.replace("/api/simulation/session/", "", 1).strip()
            payload = get_simulation_session_state(session_id=session_id)
            if payload is None:
                self._send_error(
                    code="session_not_found",
                    message=f"Unknown session_id: {session_id}",
                    status=HTTPStatus.NOT_FOUND,
                )
                return
            self._send_json(payload)
            return

        if path.startswith("/api/"):
            self._send_error(
                code="not_found",
                message=f"Unknown API endpoint: {path}",
                status=HTTPStatus.NOT_FOUND,
            )
            return

        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/run":
            body = self._read_json_body()
            if body is None:
                self._send_error(
                    code="invalid_body",
                    message="Request body must be valid JSON object.",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            validation_error = _validate_run_request(body)
            if validation_error:
                self._send_error(
                    code="invalid_body",
                    message=validation_error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            job = submit_run_job(body)
            self._send_json(
                {
                    "job_id": job.job_id,
                    "status": job.status,
                    "status_url": f"/api/jobs/{job.job_id}",
                    "request": job.request,
                },
                status=HTTPStatus.ACCEPTED,
            )
            return

        if path == "/api/simulation/session":
            body = self._read_json_body()
            if body is None:
                self._send_error(
                    code="invalid_body",
                    message="Request body must be valid JSON object.",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            error = _validate_simulation_session_request(body)
            if error:
                self._send_error(
                    code="invalid_body",
                    message=error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            payload = create_simulation_session(payload=body)
            self._send_json(payload, status=HTTPStatus.CREATED)
            return

        if path.startswith("/api/simulation/session/") and path.endswith("/run-all"):
            body = self._read_json_body() or {}
            session_id = (
                path.replace("/api/simulation/session/", "", 1).replace("/run-all", "").strip()
            )
            payload, error = run_simulation_step(session_id=session_id, action="run_all", payload=body)
            if error:
                self._send_error(
                    code="simulation_error",
                    message=error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            self._send_json(payload)
            return

        if path.startswith("/api/simulation/session/") and path.endswith("/run-next"):
            body = self._read_json_body() or {}
            session_id = (
                path.replace("/api/simulation/session/", "", 1).replace("/run-next", "").strip()
            )
            payload, error = run_simulation_step(session_id=session_id, action="run_next", payload=body)
            if error:
                self._send_error(
                    code="simulation_error",
                    message=error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            self._send_json(payload)
            return

        if path.startswith("/api/simulation/session/") and path.endswith("/reset"):
            body = self._read_json_body() or {}
            session_id = path.replace("/api/simulation/session/", "", 1).replace("/reset", "").strip()
            payload, error = run_simulation_step(session_id=session_id, action="reset", payload=body)
            if error:
                self._send_error(
                    code="simulation_error",
                    message=error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            self._send_json(payload)
            return

        if path.startswith("/api/simulation/session/") and path.endswith("/pause"):
            body = self._read_json_body() or {}
            session_id = path.replace("/api/simulation/session/", "", 1).replace("/pause", "").strip()
            payload, error = run_simulation_step(session_id=session_id, action="pause", payload=body)
            if error:
                self._send_error(
                    code="simulation_error",
                    message=error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            self._send_json(payload)
            return

        if path.startswith("/api/simulation/session/") and path.endswith("/resume"):
            body = self._read_json_body() or {}
            session_id = path.replace("/api/simulation/session/", "", 1).replace("/resume", "").strip()
            payload, error = run_simulation_step(session_id=session_id, action="resume", payload=body)
            if error:
                self._send_error(
                    code="simulation_error",
                    message=error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            self._send_json(payload)
            return

        if path == "/api/governance/approve":
            body = self._read_json_body()
            if body is None:
                self._send_error(
                    code="invalid_body",
                    message="Request body must be valid JSON object.",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            validation_error = _validate_governance_approve_request(body)
            if validation_error:
                self._send_error(
                    code="invalid_body",
                    message=validation_error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            try:
                response = approve_run_governance(
                    use_case_id=str(body["use_case_id"]).strip(),
                    run_id=str(body["run_id"]).strip(),
                    artifacts_root=ROOT / "artifacts",
                    approved_by=(
                        str(body.get("approved_by", "")).strip()
                        if body.get("approved_by") is not None
                        else None
                    ),
                    note=(
                        str(body.get("note", "")).strip()
                        if body.get("note") is not None
                        else None
                    ),
                    accept_warnings=[
                        str(item).strip()
                        for item in body.get("accept_warnings", [])
                        if str(item).strip()
                    ],
                    accept_all_warnings=bool(body.get("accept_all_warnings", False)),
                    warning_rationale=(
                        str(body.get("warning_rationale", "")).strip()
                        if body.get("warning_rationale") is not None
                        else None
                    ),
                    force=bool(body.get("force", False)),
                )
            except ValueError as exc:
                self._send_error(
                    code="invalid_body",
                    message=str(exc),
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            except Exception as exc:  # pragma: no cover - defensive catch.
                self._send_error(
                    code="governance_approval_failed",
                    message=f"Unexpected governance approval error: {exc}",
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            self._send_json(response)
            return

        if path in {"/api/inference/online", "/api/inference/batch"}:
            mode = "online" if path.endswith("/online") else "batch"
            body = self._read_json_body()
            if body is None:
                self._send_error(
                    code="invalid_body",
                    message="Request body must be valid JSON object.",
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            validation_error = _validate_inference_request(payload=body, mode=mode)
            if validation_error:
                self._send_error(
                    code="invalid_body",
                    message=validation_error,
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            try:
                if mode == "online":
                    response = run_inference_online(
                        use_case_id=str(body["use_case_id"]),
                        record=dict(body["record"]),
                        seed=int(body.get("seed", 101)),
                        registry_stage=str(body.get("registry_stage", "auto")),
                        artifacts_root=ROOT / "artifacts",
                    )
                else:
                    response = run_inference_batch(
                        use_case_id=str(body["use_case_id"]),
                        records=[dict(row) for row in body["records"]],
                        seed=int(body.get("seed", 101)),
                        registry_stage=str(body.get("registry_stage", "auto")),
                        artifacts_root=ROOT / "artifacts",
                    )
            except ValueError as exc:
                self._send_error(
                    code="invalid_body",
                    message=str(exc),
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            except RuntimeError as exc:
                self._send_error(
                    code="inference_failed",
                    message=str(exc),
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return
            except Exception as exc:  # pragma: no cover - defensive catch.
                self._send_error(
                    code="inference_failed",
                    message=f"Unexpected inference error: {exc}",
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            self._send_json(response)
            return

        self._send_error(code="not_found", message="Not found", status=HTTPStatus.NOT_FOUND)

    def _read_json_body(self) -> dict[str, Any] | None:
        """Parse JSON request body into dictionary."""
        raw_len = self.headers.get("Content-Length")
        if raw_len is None:
            return {}
        try:
            body_len = int(raw_len)
        except ValueError:
            return None

        raw = self.rfile.read(body_len)
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _send_json(self, payload: Any, status: int = HTTPStatus.OK) -> None:
        """Write JSON response payload."""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(
        self,
        payload: str,
        status: int = HTTPStatus.OK,
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        """Write text response payload."""
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        """Write file download response."""
        try:
            body = path.read_bytes()
        except OSError as exc:
            self._send_error(
                code="artifact_read_failed",
                message=f"Failed to read artifact file: {exc}",
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename=\"{path.name}\"')
        self.end_headers()
        self.wfile.write(body)

    def _send_error(
        self,
        *,
        code: str,
        message: str,
        status: int,
        details: Any | None = None,
    ) -> None:
        """Write standardized API error payload."""
        self._send_json(
            build_api_error_payload(code=code, message=message, details=details),
            status=status,
        )


def _load_or_build_view_model() -> dict[str, Any] | None:
    """Load view model artifact; build from latest artifacts if missing."""
    if not VIEW_MODEL_PATH.exists():
        cmd = [sys.executable, "ui/adapter/build_view_model.py"]
        subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)

    if not VIEW_MODEL_PATH.exists():
        return None

    try:
        with VIEW_MODEL_PATH.open("r", encoding="utf-8") as f:
            parsed = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def load_oss_inventory() -> dict[str, Any] | None:
    """Load generated OSS inventory, generating it on-demand when missing."""
    if not OSS_INVENTORY_PATH.exists():
        subprocess.run(
            [sys.executable, str(OSS_INVENTORY_GENERATOR.as_posix())],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    if not OSS_INVENTORY_PATH.exists():
        return None
    try:
        with OSS_INVENTORY_PATH.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_enterprise_hardening(*, profile: str = "standalone") -> dict[str, Any]:
    """Build optional enterprise-hardening readiness payload."""
    config = _load_enterprise_hardening_config()
    config_modules = config.get("modules", {}) if isinstance(config.get("modules"), dict) else {}
    profile_modules = _enterprise_profile_modules(config=config, profile=profile)
    modules: list[dict[str, Any]] = []
    ready_count = 0
    enabled_count = 0

    for row in ENTERPRISE_HARDENING_MODULES:
        module_id = row["module_id"]
        module_cfg = config_modules.get(module_id, {}) if isinstance(config_modules, dict) else {}
        configured = bool(profile_modules.get(module_id, module_cfg.get("enabled", False)))
        import_name = str(row.get("import_name", ""))
        package_installed = True if not import_name else _module_available(import_name)
        status = "planned"
        runtime_status = "not_enabled"
        if configured:
            status = "implemented"
            runtime_status = "dependency_available" if package_installed else "adapter_ready_missing_dependency"
        elif package_installed:
            status = "available"
            runtime_status = "dependency_available_not_enabled"
        if configured:
            enabled_count += 1
        if status == "implemented":
            ready_count += 1
        modules.append(
            {
                "module_id": module_id,
                "name": row["name"],
                "technology": row.get("technology", row["name"]),
                "purpose": row["purpose"],
                "target_stage": row["target_stage"],
                "category": row.get("category", "heavy"),
                "activation_mode": row.get("activation_mode", "profile_driven"),
                "configured": configured,
                "package_installed": package_installed,
                "status": status,
                "runtime_status": runtime_status,
                "notes": str(module_cfg.get("notes", "")).strip() or None,
            }
        )

    return {
        "generated_at_utc": _utc_now(),
        "profile": profile,
        "summary": {
            "module_count": len(modules),
            "enabled_count": enabled_count,
            "ready_count": ready_count,
        },
        "modules": modules,
    }


def _enterprise_profile_modules(*, config: dict[str, Any], profile: str) -> dict[str, bool]:
    """Return profile-specific module enablement flags."""
    profiles = config.get("profiles")
    if not isinstance(profiles, dict):
        return {}
    profile_cfg = profiles.get(profile)
    if not isinstance(profile_cfg, dict):
        return {}
    modules = profile_cfg.get("modules")
    if not isinstance(modules, dict):
        return {}
    return {str(key): bool(value) for key, value in modules.items()}


def _load_enterprise_hardening_config() -> dict[str, Any]:
    """Load enterprise-hardening config file when present."""
    if not ENTERPRISE_HARDENING_CONFIG_PATH.exists():
        return {}
    try:
        with ENTERPRISE_HARDENING_CONFIG_PATH.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _module_available(import_name: str) -> bool:
    """Return True when the Python module import target is installed."""
    return importlib.util.find_spec(import_name) is not None


def build_prometheus_metrics(*, artifacts_root: Path | None = None) -> str:
    """Build Prometheus-compatible metrics from latest run artifacts."""
    root = artifacts_root if artifacts_root is not None else ROOT / "artifacts"
    summaries = _load_metric_summaries(artifacts_root=root)
    lines = [
        "# HELP cdp_run_total Total run summaries by status.",
        "# TYPE cdp_run_total counter",
    ]
    status_counts: dict[str, int] = {}
    use_case_latest: dict[str, dict[str, Any]] = {}
    for summary in summaries:
        status = str(summary.get("run_status", "unknown")).strip().lower() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        use_case_id = str(summary.get("use_case_id", "unknown"))
        current = use_case_latest.get(use_case_id)
        if current is None or str(summary.get("run_id", "")) > str(current.get("run_id", "")):
            use_case_latest[use_case_id] = summary

    for status in sorted(status_counts):
        lines.append(f'cdp_run_total{{status="{_metric_label(status)}"}} {status_counts[status]}')

    lines.extend(
        [
            "# HELP cdp_latest_run_status Latest run status by use case, 1 for pass and 0 otherwise.",
            "# TYPE cdp_latest_run_status gauge",
            "# HELP cdp_latest_stage_pass_ratio Latest stage pass ratio by use case.",
            "# TYPE cdp_latest_stage_pass_ratio gauge",
            "# HELP cdp_latest_records_count Latest record counts by use case and record type.",
            "# TYPE cdp_latest_records_count gauge",
        ]
    )
    for use_case_id in sorted(use_case_latest):
        summary = use_case_latest[use_case_id]
        status_value = 1 if str(summary.get("run_status", "")).lower() == "pass" else 0
        labels = f'use_case_id="{_metric_label(use_case_id)}",run_id="{_metric_label(str(summary.get("run_id", "")))}"'
        lines.append(f"cdp_latest_run_status{{{labels}}} {status_value}")
        telemetry = summary.get("telemetry")
        stage_rows = telemetry.get("stages", []) if isinstance(telemetry, dict) else []
        stage_total = len(stage_rows) if isinstance(stage_rows, list) else 0
        stage_ratio = 1.0 if status_value == 1 and stage_total > 0 else 0.0
        lines.append(f"cdp_latest_stage_pass_ratio{{{labels}}} {stage_ratio}")
        records = summary.get("records")
        if isinstance(records, dict):
            for record_type, value in sorted(records.items()):
                if isinstance(value, (int, float)):
                    lines.append(
                        "cdp_latest_records_count"
                        f'{{{labels},record_type="{_metric_label(str(record_type))}"}} {value}'
                    )
    lines.append("")
    return "\n".join(lines)


def _load_metric_summaries(*, artifacts_root: Path) -> list[dict[str, Any]]:
    """Load compact run summaries for metrics export."""
    if not artifacts_root.exists():
        return []
    summaries: list[dict[str, Any]] = []
    for summary_path in sorted(artifacts_root.glob("*/*/summary.json")):
        try:
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            summaries.append(payload)
    return summaries


def _metric_label(value: str) -> str:
    """Escape a Prometheus label value."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def build_api_error_payload(
    *,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    """Build standardized API error payload."""
    payload: dict[str, Any] = {
        "error": message,
        "error_code": code,
    }
    if details is not None:
        payload["details"] = details
    return payload


def _validate_simulation_session_request(payload: dict[str, Any]) -> str | None:
    """Validate simulation-session create request."""
    use_case_id = payload.get("use_case_id")
    if not isinstance(use_case_id, str) or not use_case_id.strip():
        return "use_case_id must be a non-empty string."
    infra_profile = str(payload.get("infra_profile", "local")).strip().lower()
    if infra_profile not in INFRA_FILTERS - {"all"}:
        return "infra_profile must be 'local' or 'oss'."
    runtime_mode = str(payload.get("runtime_mode", "default")).strip().lower()
    if runtime_mode not in EXECUTION_RUNTIME_MODES:
        return "runtime_mode must be one of: default, synthetic_only."
    try:
        int(payload.get("seed", 101))
    except (TypeError, ValueError):
        return "seed must be an integer."
    scenario_id = payload.get("scenario_id")
    if scenario_id is not None and not isinstance(scenario_id, str):
        return "scenario_id must be a string or null."
    failure_flags_raw = payload.get("failure_injection", [])
    if failure_flags_raw is not None and not isinstance(failure_flags_raw, list):
        return "failure_injection must be an array of strings."
    if isinstance(failure_flags_raw, list):
        for item in failure_flags_raw:
            if not isinstance(item, str):
                return "failure_injection must contain only strings."
    return None


def create_simulation_session(*, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a new in-memory simulation session."""
    session = SimulationSession(
        session_id=uuid.uuid4().hex,
        use_case_id=str(payload["use_case_id"]).strip(),
        infra_profile=str(payload.get("infra_profile", "local")).strip().lower(),
        seed=int(payload.get("seed", 101)),
        runtime_mode=str(payload.get("runtime_mode", "default")).strip().lower() or "default",
        scenario_id=(
            str(payload.get("scenario_id", "")).strip() if payload.get("scenario_id") is not None else None
        )
        or None,
        failure_injection=_normalize_failure_injection_flags(payload.get("failure_injection")),
        created_at_utc=_utc_now(),
        updated_at_utc=_utc_now(),
    )
    with SIM_SESSIONS_LOCK:
        SIM_SESSIONS[session.session_id] = session
    return get_simulation_session_state(session_id=session.session_id) or {"session_id": session.session_id}


def get_simulation_session_state(*, session_id: str) -> dict[str, Any] | None:
    """Return current simulation-session state with stage-progress payload."""
    with SIM_SESSIONS_LOCK:
        session = SIM_SESSIONS.get(session_id)
        if session is None:
            return None
        snapshot = SimulationSession(**asdict(session))

    payload: dict[str, Any] = {
        "session_id": snapshot.session_id,
        "use_case_id": snapshot.use_case_id,
        "infra_profile": snapshot.infra_profile,
        "seed": snapshot.seed,
        "runtime_mode": snapshot.runtime_mode,
        "scenario_id": snapshot.scenario_id,
        "failure_injection": snapshot.failure_injection,
        "run_id": snapshot.run_id,
        "run_status": snapshot.run_status,
        "stage_cursor": snapshot.stage_cursor,
        "stage_total": snapshot.stage_total,
        "paused": snapshot.paused,
        "created_at_utc": snapshot.created_at_utc,
        "updated_at_utc": snapshot.updated_at_utc,
        "last_error": snapshot.last_error,
    }
    if snapshot.run_id:
        stage_details = load_run_stage_details(
            use_case_id=snapshot.use_case_id,
            run_id=snapshot.run_id,
            artifacts_root=ROOT / "artifacts",
        )
        if stage_details:
            stages = stage_details.get("stages", [])
            if not isinstance(stages, list):
                stages = []
            cursor = max(0, min(int(snapshot.stage_cursor), len(stages)))
            payload["visible_stages"] = stages[:cursor]
            payload["next_stage"] = stages[cursor] if cursor < len(stages) else None
            payload["stage_details"] = stage_details
    return payload


def run_simulation_step(
    *,
    session_id: str,
    action: str,
    payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Advance/reset/pause/resume simulation cursor and optionally execute backend run."""
    request = payload or {}
    action_key = action.strip().lower()
    if action_key not in {"run_all", "run_next", "reset", "pause", "resume"}:
        return None, "Unsupported simulation action."

    with SIM_SESSIONS_LOCK:
        session = SIM_SESSIONS.get(session_id)
        if session is None:
            return None, f"Unknown session_id: {session_id}"
        if action_key in {"run_all", "run_next"} and session.paused:
            return None, "Simulation is paused. Resume before running stages."
        should_rerun = bool(request.get("rerun", False))
        needs_run = session.run_id is None or should_rerun
        execution_ctx = {
            "use_case_id": session.use_case_id,
            "infra_profile": session.infra_profile,
            "seed": session.seed,
            "runtime_mode": session.runtime_mode,
            "scenario_id": session.scenario_id,
            "failure_injection": list(session.failure_injection),
        }

    if action_key in {"run_all", "run_next"} and needs_run:
        summary, error = _execute_simulation_backend(**execution_ctx)
        if error:
            with SIM_SESSIONS_LOCK:
                existing = SIM_SESSIONS.get(session_id)
                if existing:
                    existing.last_error = error
                    existing.updated_at_utc = _utc_now()
            return None, error
        with SIM_SESSIONS_LOCK:
            existing = SIM_SESSIONS.get(session_id)
            if existing:
                existing.run_id = str(summary.get("run_id"))
                existing.run_status = str(summary.get("run_status", "unknown"))
                existing.last_error = None
                existing.updated_at_utc = _utc_now()

    with SIM_SESSIONS_LOCK:
        session = SIM_SESSIONS.get(session_id)
        if session is None:
            return None, f"Unknown session_id: {session_id}"
        if action_key == "run_all":
            session.stage_cursor = session.stage_total
        elif action_key == "run_next":
            session.stage_cursor = min(session.stage_total, session.stage_cursor + 1)
        elif action_key == "reset":
            session.stage_cursor = 0
            session.paused = False
            if should_rerun:
                session.run_id = None
                session.run_status = None
        elif action_key == "pause":
            session.paused = True
        elif action_key == "resume":
            session.paused = False
        session.updated_at_utc = _utc_now()

    return get_simulation_session_state(session_id=session_id), None


def _execute_simulation_backend(
    *,
    use_case_id: str,
    infra_profile: str,
    seed: int,
    runtime_mode: str,
    scenario_id: str | None,
    failure_injection: list[str],
) -> tuple[dict[str, Any], str | None]:
    """Execute one full-stack run for simulation session."""
    try:
        summary = run_full_stack(
            use_case_id=use_case_id,
            output_dir=ROOT / "artifacts",
            seed=seed,
            infra_profile=infra_profile,
            runtime_mode=runtime_mode,
            scenario_id=scenario_id,
            failure_injection=failure_injection,
        )
        return summary, None
    except Exception as exc:  # pragma: no cover - defensive runtime path.
        return {}, f"Simulation backend execution failed: {exc}"


def parse_run_summary_path(path: str) -> tuple[dict[str, str], str | None]:
    """Parse `/api/runs/<use_case_id>/<run_id>` path."""
    parts = path.split("/")
    if len(parts) != 5:
        return {}, "Path must be /api/runs/<use_case_id>/<run_id>."
    use_case_id = parts[3].strip()
    run_id = parts[4].strip()
    if not use_case_id or not run_id:
        return {}, "Both use_case_id and run_id are required."
    return {"use_case_id": use_case_id, "run_id": run_id}, None


def parse_run_stages_path(path: str) -> tuple[dict[str, str], str | None]:
    """Parse `/api/runs/<use_case_id>/<run_id>/stages` path."""
    parts = path.split("/")
    if len(parts) != 6 or parts[5] != "stages":
        return {}, "Path must be /api/runs/<use_case_id>/<run_id>/stages."
    use_case_id = parts[3].strip()
    run_id = parts[4].strip()
    if not use_case_id or not run_id:
        return {}, "Both use_case_id and run_id are required."
    return {"use_case_id": use_case_id, "run_id": run_id}, None


def parse_run_data_quality_path(path: str) -> tuple[dict[str, str], str | None]:
    """Parse `/api/runs/<use_case_id>/<run_id>/data-quality` path."""
    parts = path.split("/")
    if len(parts) != 6 or parts[5] != "data-quality":
        return {}, "Path must be /api/runs/<use_case_id>/<run_id>/data-quality."
    use_case_id = parts[3].strip()
    run_id = parts[4].strip()
    if not use_case_id or not run_id:
        return {}, "Both use_case_id and run_id are required."
    return {"use_case_id": use_case_id, "run_id": run_id}, None


def load_run_history(
    use_case_id: str,
    limit: int = 6,
    status_filter: str = "all",
    infra_filter: str = "all",
    baseline: str = "latest",
    artifacts_root: Path | None = None,
) -> dict[str, Any]:
    """Load recent run summaries for one use case with comparable stage metrics."""
    root = artifacts_root if artifacts_root is not None else ROOT / "artifacts"
    use_case_dir = root / use_case_id
    normalized_status_filter = status_filter.lower().strip() or "all"
    normalized_infra_filter = infra_filter.lower().strip() or "all"
    normalized_baseline = baseline.strip() or "latest"
    runs: list[dict[str, Any]] = []

    if not use_case_dir.exists():
        return {
            "use_case_id": use_case_id,
            "filters": {
                "limit": limit,
                "status": normalized_status_filter,
                "infra": normalized_infra_filter,
                "baseline": normalized_baseline,
            },
            "baseline": {
                "requested": normalized_baseline,
                "resolved_run_id": None,
                "strategy": "none",
            },
            "runs": runs,
        }

    for summary_path in sorted(use_case_dir.glob("*/summary.json"), reverse=True):
        if len(runs) >= limit:
            break

        summary = _read_json_file(summary_path)
        if not isinstance(summary, dict):
            continue

        run_status = str(summary.get("run_status", "unknown")).lower()
        infra_profile = str(summary.get("infra_profile", "local")).lower()
        if normalized_status_filter != "all" and run_status != normalized_status_filter:
            continue
        if normalized_infra_filter != "all" and infra_profile != normalized_infra_filter:
            continue

        stage_health = _compute_stage_health(summary, artifacts_root=root)
        stage_pass_count = sum(1 for row in stage_health if row["status"] == "pass")
        model_metrics = summary.get("model_metrics", {})
        if not isinstance(model_metrics, dict):
            model_metrics = {}

        kpi_values: list[dict[str, Any]] = []
        for key in sorted(model_metrics):
            if key == "primary_kpi":
                continue
            kpi_values.append({"name": key, "value": model_metrics[key]})

        runs.append(
            {
                "run_id": str(summary.get("run_id", summary_path.parent.name)),
                "run_status": run_status,
                "infra_profile": infra_profile,
                "seed": summary.get("seed"),
                "primary_kpi": str(model_metrics.get("primary_kpi", "n/a")),
                "kpi_values": kpi_values,
                "stage_health": stage_health,
                "stage_pass_count": stage_pass_count,
                "stage_total": len(stage_health),
                "summary_path": _relativize_path(summary_path),
            }
        )

    baseline_info = _attach_run_comparisons(runs=runs, baseline=normalized_baseline)

    return {
        "use_case_id": use_case_id,
        "filters": {
            "limit": limit,
            "status": normalized_status_filter,
            "infra": normalized_infra_filter,
            "baseline": normalized_baseline,
        },
        "baseline": baseline_info,
        "runs": runs,
    }


def parse_run_registry_query(query: dict[str, list[str]]) -> tuple[dict[str, Any], str | None]:
    """Parse and validate `/api/runs` query parameters."""
    limit_raw = (query.get("limit", ["50"])[0] or "50").strip()
    offset_raw = (query.get("offset", ["0"])[0] or "0").strip()
    try:
        limit = int(limit_raw)
        offset = int(offset_raw)
    except ValueError:
        return {}, "Query parameters 'limit' and 'offset' must be integers."

    status_filter = (query.get("status", ["all"])[0] or "all").strip().lower()
    if status_filter not in RUN_STATUS_FILTERS:
        return (
            {},
            "Query parameter 'status' must be one of: " + ", ".join(sorted(RUN_STATUS_FILTERS)),
        )

    infra_filter = (query.get("infra", ["all"])[0] or "all").strip().lower()
    if infra_filter not in INFRA_FILTERS:
        return (
            {},
            "Query parameter 'infra' must be one of: " + ", ".join(sorted(INFRA_FILTERS)),
        )

    seed: int | None = None
    seed_raw = (query.get("seed", [""])[0] or "").strip()
    if seed_raw:
        try:
            seed = int(seed_raw)
        except ValueError:
            return {}, "Query parameter 'seed' must be an integer."

    sort = (query.get("sort", ["desc"])[0] or "desc").strip().lower()
    if sort not in RUNS_SORT_VALUES:
        return {}, "Query parameter 'sort' must be 'asc' or 'desc'."

    return (
        {
            "use_case_id": (query.get("use_case_id", [""])[0] or "").strip() or None,
            "limit": max(1, min(500, limit)),
            "offset": max(0, offset),
            "status_filter": status_filter,
            "infra_filter": infra_filter,
            "seed": seed,
            "sort": sort,
            "query": (query.get("q", [""])[0] or "").strip() or None,
        },
        None,
    )


def load_run_registry(
    *,
    use_case_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    status_filter: str = "all",
    infra_filter: str = "all",
    seed: int | None = None,
    sort: str = "desc",
    query: str | None = None,
    artifacts_root: Path | None = None,
) -> dict[str, Any]:
    """Load run-registry listing with stable filter semantics used by `/api/runs`."""
    root = artifacts_root if artifacts_root is not None else ROOT / "artifacts"
    return list_run_summaries(
        artifacts_root=root,
        use_case_id=use_case_id,
        run_status=status_filter,
        infra_profile=infra_filter,
        seed=seed,
        query=query,
        sort=sort,
        limit=limit,
        offset=offset,
    )


def parse_portfolio_summary_query(query: dict[str, list[str]]) -> tuple[dict[str, Any], str | None]:
    """Parse and validate `/api/portfolio/summary` query parameters."""
    status_filter = (query.get("status", ["all"])[0] or "all").strip().lower()
    if status_filter not in RUN_STATUS_FILTERS:
        return (
            {},
            "Query parameter 'status' must be one of: " + ", ".join(sorted(RUN_STATUS_FILTERS)),
        )

    infra_filter = (query.get("infra", ["all"])[0] or "all").strip().lower()
    if infra_filter not in INFRA_FILTERS:
        return (
            {},
            "Query parameter 'infra' must be one of: " + ", ".join(sorted(INFRA_FILTERS)),
        )

    sort = (query.get("sort", ["desc"])[0] or "desc").strip().lower()
    if sort not in RUNS_SORT_VALUES:
        return {}, "Query parameter 'sort' must be 'asc' or 'desc'."

    limit_raw = (query.get("limit_per_use_case", ["1"])[0] or "1").strip()
    try:
        limit_per_use_case = int(limit_raw)
    except ValueError:
        return {}, "Query parameter 'limit_per_use_case' must be an integer."

    return (
        {
            "status_filter": status_filter,
            "infra_filter": infra_filter,
            "sort": sort,
            "limit_per_use_case": max(1, min(MAX_PORTFOLIO_LIMIT_PER_USE_CASE, limit_per_use_case)),
        },
        None,
    )


def load_portfolio_summary(
    *,
    status_filter: str = "all",
    infra_filter: str = "all",
    sort: str = "desc",
    limit_per_use_case: int = 1,
    artifacts_root: Path | None = None,
) -> dict[str, Any]:
    """Build cross-use-case KPI rollup for business-facing portfolio comparisons."""
    root = artifacts_root if artifacts_root is not None else ROOT / "artifacts"
    list_payload = list_run_summaries(
        artifacts_root=root,
        run_status=status_filter,
        infra_profile=infra_filter,
        sort=sort,
        limit=1_000_000,
        offset=0,
    )
    rows = list_payload.get("runs", [])
    grouped: dict[str, list[dict[str, Any]]] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            use_case_id = str(row.get("use_case_id", "")).strip()
            if not use_case_id:
                continue
            bucket = grouped.setdefault(use_case_id, [])
            if len(bucket) < limit_per_use_case:
                bucket.append(row)

    use_cases: list[dict[str, Any]] = []
    latest_by_use_case: list[dict[str, Any]] = []
    kpi_comparison: list[dict[str, Any]] = []
    for use_case_id in sorted(grouped):
        selected_rows = grouped[use_case_id]
        run_cards: list[dict[str, Any]] = []
        for rank, row in enumerate(selected_rows, start=1):
            summary = get_run_summary(
                use_case_id=use_case_id,
                run_id=str(row.get("run_id", "")),
                artifacts_root=root,
            )
            run_cards.append(
                _build_portfolio_run_card(
                    row=row,
                    summary=summary,
                    rank_within_use_case=rank,
                    artifacts_root=root,
                )
            )

        latest_run = run_cards[0]
        latest_by_use_case.append(latest_run)
        kpi_comparison.append(
            {
                "use_case_id": use_case_id,
                "run_id": latest_run.get("run_id"),
                "kpi_name": latest_run.get("primary_kpi"),
                "kpi_value": latest_run.get("primary_kpi_value"),
            }
        )
        use_cases.append(
            {
                "use_case_id": use_case_id,
                "latest_run": latest_run,
                "runs": run_cards,
            }
        )

    pass_count = sum(
        1 for row in latest_by_use_case if str(row.get("run_status", "")).lower() == "pass"
    )
    fail_count = sum(
        1 for row in latest_by_use_case if str(row.get("run_status", "")).lower() == "fail"
    )
    stage_rates = [
        _to_float(row.get("stage_pass_rate"))
        for row in latest_by_use_case
        if _to_float(row.get("stage_pass_rate")) is not None
    ]
    avg_stage_pass_rate = (
        round(sum(stage_rates) / len(stage_rates), 4) if stage_rates else None
    )

    return {
        "generated_at_utc": _utc_now(),
        "filters": {
            "status": status_filter,
            "infra": infra_filter,
            "sort": sort,
            "limit_per_use_case": limit_per_use_case,
        },
        "totals": {
            "use_case_count": len(use_cases),
            "latest_pass_count": pass_count,
            "latest_fail_count": fail_count,
            "avg_stage_pass_rate": avg_stage_pass_rate,
        },
        "latest_by_use_case": latest_by_use_case,
        "kpi_comparison": kpi_comparison,
        "use_cases": use_cases,
        "index": list_payload.get("index", {}),
    }


def load_run_stage_details(
    *,
    use_case_id: str,
    run_id: str,
    artifacts_root: Path | None = None,
) -> dict[str, Any] | None:
    """Load stage-by-stage technical details for one run."""
    root = artifacts_root if artifacts_root is not None else ROOT / "artifacts"
    summary = get_run_summary(
        use_case_id=use_case_id,
        run_id=run_id,
        artifacts_root=root,
    )
    if summary is None:
        return None

    stage_health = _compute_stage_health(summary, artifacts_root=root)
    stage_details = [
        _build_stage_detail_row(stage_row=row, summary=summary, artifacts_root=root)
        for row in stage_health
    ]
    stage_pass_count = sum(
        1 for row in stage_details if str(row.get("status", "")).lower() == "pass"
    )
    return {
        "use_case_id": str(summary.get("use_case_id", use_case_id)),
        "run_id": str(summary.get("run_id", run_id)),
        "run_status": str(summary.get("run_status", "unknown")).lower(),
        "infra_profile": str(summary.get("infra_profile", "local")).lower(),
        "seed": summary.get("seed"),
        "summary_path": _display_path_text(
            summary.get("summary_path"),
            artifacts_root=root,
            fallback_path=root / use_case_id / run_id / "summary.json",
        ),
        "stage_total": len(stage_details),
        "stage_pass_count": stage_pass_count,
        "stages": stage_details,
    }


def load_run_summary_details(
    *,
    use_case_id: str,
    run_id: str,
    artifacts_root: Path | None = None,
) -> dict[str, Any] | None:
    """Load one run summary with inline evidence needed by the experience UI."""
    root = artifacts_root if artifacts_root is not None else ROOT / "artifacts"
    summary = get_run_summary(
        use_case_id=use_case_id,
        run_id=run_id,
        artifacts_root=root,
    )
    if summary is None:
        return None

    payload = _sanitize_paths_for_response(summary, artifacts_root=root)
    monitoring_report = _read_monitoring_report(summary=summary, artifacts_root=root)
    if isinstance(monitoring_report, dict):
        payload["monitoring_report"] = _sanitize_paths_for_response(
            monitoring_report,
            artifacts_root=root,
        )
    return payload


def load_run_data_quality_details(
    *,
    use_case_id: str,
    run_id: str,
    artifacts_root: Path | None = None,
) -> dict[str, Any] | None:
    """Load compact data-quality blockers and warnings for one run."""
    root = artifacts_root if artifacts_root is not None else ROOT / "artifacts"
    summary = get_run_summary(
        use_case_id=use_case_id,
        run_id=run_id,
        artifacts_root=root,
    )
    if summary is None:
        return None

    artifacts = summary.get("artifacts")
    monitoring_report_path: str | None = None
    if isinstance(artifacts, dict):
        path_text = artifacts.get("monitoring_report")
        if isinstance(path_text, str):
            monitoring_report_path = _relativize_path(
                _resolve_path(path_text=path_text, artifacts_root=root)
            )

    monitoring_report = _read_monitoring_report(summary=summary, artifacts_root=root)
    data_quality: dict[str, Any] = {}
    if isinstance(monitoring_report, dict):
        raw_data_quality = monitoring_report.get("data_quality")
        if isinstance(raw_data_quality, dict):
            data_quality = raw_data_quality

    blocker_rows = _build_data_quality_issue_rows(
        checks=data_quality.get("checks"),
        target_status="fail",
    )
    warning_rows = _build_data_quality_issue_rows(
        checks=data_quality.get("checks"),
        target_status="warn",
    )
    blocker_names = [_data_quality_issue_name(row) for row in blocker_rows]
    warning_names = [_data_quality_issue_name(row) for row in warning_rows]

    if not blocker_names or not warning_names:
        deployment_readiness: dict[str, Any] = {}
        if isinstance(monitoring_report, dict):
            raw_readiness = monitoring_report.get("deployment_readiness")
            if isinstance(raw_readiness, dict):
                deployment_readiness = raw_readiness
        if not blocker_names:
            blocker_names = _string_list(
                deployment_readiness.get("failed_data_quality_checks")
            )
        if not warning_names:
            warning_names = _string_list(
                deployment_readiness.get("warning_data_quality_checks")
            )

    data_quality_status = str(data_quality.get("status", "not_available")).strip().lower()
    data_quality_mode = str(data_quality.get("mode", "unknown")).strip().lower()

    return {
        "use_case_id": str(summary.get("use_case_id", use_case_id)),
        "run_id": str(summary.get("run_id", run_id)),
        "run_status": str(summary.get("run_status", "unknown")).lower(),
        "infra_profile": str(summary.get("infra_profile", "local")).lower(),
        "seed": summary.get("seed"),
        "summary_path": _display_path_text(
            summary.get("summary_path"),
            artifacts_root=root,
            fallback_path=root / use_case_id / run_id / "summary.json",
        ),
        "monitoring_report_path": monitoring_report_path,
        "data_quality_status": data_quality_status,
        "data_quality_mode": data_quality_mode,
        "data_quality_reason": data_quality.get("reason"),
        "blocker_count": len(blocker_names),
        "warning_count": len(warning_names),
        "blocker_names": blocker_names,
        "warning_names": warning_names,
        "blockers": blocker_rows,
        "warnings": warning_rows,
    }


def _build_data_quality_issue_rows(
    *,
    checks: Any,
    target_status: str,
) -> list[dict[str, Any]]:
    """Build compact rows for fail/warn checks from data-quality payload."""
    rows: list[dict[str, Any]] = []
    normalized_target = target_status.strip().lower()
    if normalized_target not in {"fail", "warn"}:
        return rows
    if not isinstance(checks, list):
        return rows

    for check in checks:
        if not isinstance(check, dict):
            continue
        status = str(check.get("status", "pass")).strip().lower()
        if status != normalized_target:
            continue
        table = str(check.get("table", "unknown_table")).strip() or "unknown_table"
        name = str(check.get("name", "unknown_check")).strip() or "unknown_check"
        rows.append(
            {
                "table": table,
                "name": name,
                "status": status,
                "severity": str(check.get("severity", "fail")).strip().lower() or "fail",
                "reason": check.get("reason"),
                "violation_count": check.get("violation_count"),
            }
        )
    rows.sort(key=lambda row: (str(row.get("table")), str(row.get("name"))))
    return rows


def _data_quality_issue_name(row: dict[str, Any]) -> str:
    """Build stable `<table>.<check>` names for compact governance views."""
    table = str(row.get("table", "unknown_table")).strip() or "unknown_table"
    name = str(row.get("name", "unknown_check")).strip() or "unknown_check"
    return f"{table}.{name}"


def _string_list(value: Any) -> list[str]:
    """Normalize arbitrary list-like values into compact non-empty string list."""
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            rows.append(text)
    return rows


def _build_portfolio_run_card(
    *,
    row: dict[str, Any],
    summary: dict[str, Any] | None,
    rank_within_use_case: int,
    artifacts_root: Path,
) -> dict[str, Any]:
    """Build normalized run card used in portfolio summary responses."""
    primary_kpi = row.get("primary_kpi")
    primary_kpi_value = row.get("primary_kpi_value")
    stage_health: list[dict[str, Any]] = []
    deployment_readiness_status: str | None = None

    if isinstance(summary, dict):
        model_metrics = summary.get("model_metrics")
        if isinstance(model_metrics, dict):
            kpi_name = model_metrics.get("primary_kpi")
            if isinstance(kpi_name, str):
                primary_kpi = kpi_name
                primary_kpi_value = model_metrics.get(kpi_name)

        stage_health = _compute_stage_health(summary, artifacts_root=artifacts_root)
        deployment_readiness_status = _read_deployment_readiness_status(
            summary=summary,
            artifacts_root=artifacts_root,
        )

    stage_pass_count = sum(1 for item in stage_health if item.get("status") == "pass")
    stage_total = len(stage_health)
    stage_pass_rate = (
        round(stage_pass_count / max(stage_total, 1), 4) if stage_total > 0 else None
    )
    return {
        "rank_within_use_case": rank_within_use_case,
        "use_case_id": row.get("use_case_id"),
        "name": row.get("name"),
        "run_id": row.get("run_id"),
        "run_status": row.get("run_status"),
        "infra_profile": row.get("infra_profile"),
        "seed": row.get("seed"),
        "run_timestamp_utc": row.get("run_timestamp_utc"),
        "primary_kpi": primary_kpi,
        "primary_kpi_value": primary_kpi_value,
        "deployment_readiness_status": deployment_readiness_status
        or row.get("deployment_readiness_status"),
        "stage_pass_count": stage_pass_count,
        "stage_total": stage_total,
        "stage_pass_rate": stage_pass_rate,
        "summary_path": row.get("summary_path"),
    }


def _read_deployment_readiness_status(
    *,
    summary: dict[str, Any],
    artifacts_root: Path,
) -> str | None:
    """Read deployment-readiness status from monitoring artifact when available."""
    report = _read_monitoring_report(summary=summary, artifacts_root=artifacts_root)
    if not isinstance(report, dict):
        return None
    deployment_readiness = report.get("deployment_readiness")
    if not isinstance(deployment_readiness, dict):
        return None
    status = deployment_readiness.get("status")
    return str(status) if status is not None else None


def _build_stage_detail_row(
    *,
    stage_row: dict[str, Any],
    summary: dict[str, Any],
    artifacts_root: Path,
) -> dict[str, Any]:
    """Build one stage detail payload with concrete input/output evidence."""
    layer_id = str(stage_row.get("layer_id", "unknown"))
    artifacts = summary.get("artifacts")
    records = summary.get("records")
    if not isinstance(artifacts, dict):
        artifacts = {}
    if not isinstance(records, dict):
        records = {}

    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []

    if layer_id == "data_sources":
        source_tables = records.get("source_tables", {})
        if isinstance(source_tables, dict):
            for table, row_count in sorted(source_tables.items()):
                outputs.append({"name": str(table), "row_count": row_count})
            inputs.append({"name": "contract_seed", "value": summary.get("seed")})

    elif layer_id == "ingestion_event_bus":
        topics = artifacts.get("ingestion_event_bus", {})
        if isinstance(topics, dict):
            for topic, path_text in sorted(topics.items()):
                outputs.append(
                    _artifact_row(
                        name=f"topic:{topic}",
                        path_text=path_text,
                        artifacts_root=artifacts_root,
                    )
                )
        inputs.append({"name": "source_tables", "value": records.get("source_tables", {})})

    elif layer_id == "raw_curated_storage":
        outputs.append(_artifact_row(name="raw_events", path_text=artifacts.get("raw_events"), artifacts_root=artifacts_root))
        outputs.append(_artifact_row(name="curated_records", path_text=artifacts.get("curated_records"), artifacts_root=artifacts_root))
        inputs.append({"name": "ingestion_topics", "value": list((artifacts.get("ingestion_event_bus") or {}).keys())})

    elif layer_id == "identity_customer_360":
        outputs.append(_artifact_row(name="resolved_records", path_text=artifacts.get("resolved_records"), artifacts_root=artifacts_root))
        inputs.append(_artifact_row(name="curated_records", path_text=artifacts.get("curated_records"), artifacts_root=artifacts_root))

    elif layer_id == "feature_layer":
        outputs.append(_artifact_row(name="feature_rows", path_text=artifacts.get("feature_rows"), artifacts_root=artifacts_root))
        inputs.append(_artifact_row(name="resolved_records", path_text=artifacts.get("resolved_records"), artifacts_root=artifacts_root))

    elif layer_id == "model_layer":
        outputs.append(_artifact_row(name="model_predictions", path_text=artifacts.get("model_predictions"), artifacts_root=artifacts_root))
        outputs.append(_artifact_row(name="model_metrics", path_text=artifacts.get("model_metrics"), artifacts_root=artifacts_root))
        outputs.append(_artifact_row(name="model_manifest", path_text=artifacts.get("model_manifest"), artifacts_root=artifacts_root))
        for optional_key in ["model_training_report", "model_binary"]:
            if optional_key in artifacts:
                outputs.append(
                    _artifact_row(
                        name=optional_key,
                        path_text=artifacts.get(optional_key),
                        artifacts_root=artifacts_root,
                    )
                )
        outputs.append(_artifact_row(name="mlflow_lineage", path_text=artifacts.get("mlflow_lineage"), artifacts_root=artifacts_root))
        model_metrics = summary.get("model_metrics")
        if isinstance(model_metrics, dict):
            for key in sorted(model_metrics):
                outputs.append({"name": f"metric:{key}", "value": model_metrics[key]})
        inputs.append(_artifact_row(name="feature_rows", path_text=artifacts.get("feature_rows"), artifacts_root=artifacts_root))

    elif layer_id == "serving_activation":
        outputs.append(_artifact_row(name="activation_payloads", path_text=artifacts.get("activation_payloads"), artifacts_root=artifacts_root))
        inputs.append(_artifact_row(name="model_predictions", path_text=artifacts.get("model_predictions"), artifacts_root=artifacts_root))

    elif layer_id == "monitoring_governance":
        outputs.append(_artifact_row(name="monitoring_report", path_text=artifacts.get("monitoring_report"), artifacts_root=artifacts_root))
        outputs.append(
            _artifact_row(
                name="data_quality_expectations",
                path_text=artifacts.get("data_quality_expectations"),
                artifacts_root=artifacts_root,
            )
        )
        outputs.append(
            _artifact_row(
                name="monitoring_summary",
                path_text=artifacts.get("monitoring_summary"),
                artifacts_root=artifacts_root,
            )
        )
        readiness = _read_deployment_readiness_status(summary=summary, artifacts_root=artifacts_root)
        if readiness is not None:
            outputs.append({"name": "deployment_readiness_status", "value": readiness})
        inputs.append(_artifact_row(name="model_predictions", path_text=artifacts.get("model_predictions"), artifacts_root=artifacts_root))

    return {
        "layer_id": layer_id,
        "label": stage_row.get("label"),
        "status": stage_row.get("status"),
        "detail": stage_row.get("detail"),
        "inputs": inputs,
        "outputs": outputs,
    }


def _artifact_row(
    *,
    name: str,
    path_text: Any,
    artifacts_root: Path,
) -> dict[str, Any]:
    """Return normalized artifact evidence row with existence metadata."""
    if not isinstance(path_text, str):
        return {"name": name, "path": None, "exists": False}
    path = _resolve_path(path_text=path_text, artifacts_root=artifacts_root)
    return {
        "name": name,
        "path": _relativize_path(path, artifacts_root=artifacts_root),
        "exists": path.exists(),
    }


def _attach_run_comparisons(
    runs: list[dict[str, Any]],
    baseline: str,
) -> dict[str, Any]:
    """Attach run-to-run comparison metadata relative to selected baseline."""
    requested = baseline.strip() or "latest"
    if not runs:
        return {"requested": requested, "resolved_run_id": None, "strategy": "none"}

    if requested == "latest":
        baseline_run = runs[0]
        strategy = "latest"
    elif requested == "previous":
        baseline_run = runs[1] if len(runs) > 1 else None
        strategy = "previous"
    else:
        baseline_run = next((row for row in runs if row.get("run_id") == requested), None)
        strategy = "run_id"
        if baseline_run is None:
            baseline_run = runs[0]
            strategy = "latest_fallback"

    resolved_run_id = str(baseline_run.get("run_id")) if baseline_run else None
    for run in runs:
        run["comparison"] = _compute_run_comparison(
            run=run,
            baseline_run=baseline_run,
            baseline_selection=requested,
        )

    return {
        "requested": requested,
        "resolved_run_id": resolved_run_id,
        "strategy": strategy,
    }


def _compute_run_comparison(
    run: dict[str, Any],
    baseline_run: dict[str, Any] | None,
    baseline_selection: str,
) -> dict[str, Any]:
    """Compute KPI/status/stage deltas for one run against baseline."""
    if baseline_run is None:
        return {
            "baseline_selection": baseline_selection,
            "baseline_run_id": None,
            "status_transition": "n/a",
            "status_changed": False,
            "stage_pass_delta": None,
            "stage_status_changes": None,
            "stage_status_deltas": [],
            "kpi_deltas": [],
        }

    baseline_run_id = str(baseline_run.get("run_id", ""))
    baseline_status = str(baseline_run.get("run_status", "unknown"))
    run_status = str(run.get("run_status", "unknown"))
    status_transition = f"{baseline_status}->{run_status}"

    baseline_stage_pass = _to_int(baseline_run.get("stage_pass_count"))
    run_stage_pass = _to_int(run.get("stage_pass_count"))
    stage_pass_delta = run_stage_pass - baseline_stage_pass

    baseline_stage_map = _stage_status_map(baseline_run.get("stage_health"))
    run_stage_map = _stage_status_map(run.get("stage_health"))
    all_stage_ids = set(baseline_stage_map) | set(run_stage_map)
    stage_status_changes = sum(
        1
        for stage_id in all_stage_ids
        if baseline_stage_map.get(stage_id, "unknown") != run_stage_map.get(stage_id, "unknown")
    )
    stage_status_deltas = [
        {
            "layer_id": stage_id,
            "baseline_status": baseline_stage_map.get(stage_id, "unknown"),
            "current_status": run_stage_map.get(stage_id, "unknown"),
            "changed": baseline_stage_map.get(stage_id, "unknown")
            != run_stage_map.get(stage_id, "unknown"),
        }
        for stage_id in sorted(all_stage_ids)
    ]

    return {
        "baseline_selection": baseline_selection,
        "baseline_run_id": baseline_run_id,
        "status_transition": status_transition,
        "status_changed": baseline_status != run_status,
        "stage_pass_delta": stage_pass_delta,
        "stage_status_changes": stage_status_changes,
        "stage_status_deltas": stage_status_deltas,
        "kpi_deltas": _kpi_delta_rows(run=run, baseline_run=baseline_run),
    }


def _stage_status_map(stage_rows: Any) -> dict[str, str]:
    """Convert stage health rows into layer_id -> status map."""
    mapping: dict[str, str] = {}
    if not isinstance(stage_rows, list):
        return mapping
    for row in stage_rows:
        if not isinstance(row, dict):
            continue
        layer_id = str(row.get("layer_id", "")).strip()
        if not layer_id:
            continue
        mapping[layer_id] = str(row.get("status", "unknown"))
    return mapping


def _kpi_delta_rows(run: dict[str, Any], baseline_run: dict[str, Any]) -> list[dict[str, Any]]:
    """Build numeric KPI deltas for keys present in current or baseline run."""
    run_kpis = _kpi_numeric_map(run.get("kpi_values"))
    baseline_kpis = _kpi_numeric_map(baseline_run.get("kpi_values"))
    rows: list[dict[str, Any]] = []

    for name in sorted(set(run_kpis) | set(baseline_kpis)):
        current = run_kpis.get(name)
        baseline = baseline_kpis.get(name)
        delta = None
        if current is not None and baseline is not None:
            delta = current - baseline
        rows.append(
            {
                "name": name,
                "current": current,
                "baseline": baseline,
                "delta": delta,
            }
        )
    return rows


def _kpi_numeric_map(kpi_rows: Any) -> dict[str, float]:
    """Convert KPI row list into numeric value map when possible."""
    mapping: dict[str, float] = {}
    if not isinstance(kpi_rows, list):
        return mapping
    for row in kpi_rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", "")).strip()
        if not name:
            continue
        numeric = _to_float(row.get("value"))
        if numeric is not None:
            mapping[name] = numeric
    return mapping


def _to_float(value: Any) -> float | None:
    """Parse floats from int/float/string values; return None when non-numeric."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _to_int(value: Any) -> int:
    """Parse integer-like values and default to zero on invalid input."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return 0
    return 0


def _validate_run_request(payload: dict[str, Any]) -> str | None:
    """Validate /api/run request payload."""
    use_case_id = payload.get("use_case_id")
    if use_case_id is not None and not isinstance(use_case_id, str):
        return "use_case_id must be a string or null."

    infra_profile = payload.get("infra_profile", "local")
    if infra_profile not in {"local", "oss"}:
        return "infra_profile must be 'local' or 'oss'."

    seed = payload.get("seed", 101)
    try:
        int(seed)
    except (TypeError, ValueError):
        return "seed must be an integer."

    runtime_mode = str(payload.get("runtime_mode", "default")).strip().lower()
    if runtime_mode not in EXECUTION_RUNTIME_MODES:
        return "runtime_mode must be one of: default, synthetic_only."

    scenario_id = payload.get("scenario_id")
    if scenario_id is not None and not isinstance(scenario_id, str):
        return "scenario_id must be a string or null."

    failure_injection = payload.get("failure_injection", [])
    if failure_injection is not None and not isinstance(failure_injection, list):
        return "failure_injection must be an array of strings."
    if isinstance(failure_injection, list):
        for item in failure_injection:
            if not isinstance(item, str):
                return "failure_injection must contain only strings."
            normalized = item.strip().lower()
            if normalized and normalized not in FAILURE_INJECTION_KEYS:
                return (
                    "failure_injection values must be one of: "
                    + ", ".join(sorted(FAILURE_INJECTION_KEYS))
                )

    strict_model_backends = payload.get("strict_model_backends", False)
    if strict_model_backends is not None and not isinstance(strict_model_backends, bool):
        return "strict_model_backends must be a boolean."

    source_data_root = payload.get("source_data_root")
    if source_data_root is not None and not isinstance(source_data_root, str):
        return "source_data_root must be a string or null."

    require_real_data = payload.get("require_real_data", False)
    if require_real_data is not None and not isinstance(require_real_data, bool):
        return "require_real_data must be a boolean."

    return None


def _normalize_failure_injection_flags(value: Any) -> list[str]:
    """Normalize failure-injection payload values into sorted unique keys."""
    if not isinstance(value, list):
        return []
    rows: set[str] = set()
    for item in value:
        text = str(item).strip().lower()
        if text and text in FAILURE_INJECTION_KEYS:
            rows.add(text)
    return sorted(rows)


def _validate_governance_approve_request(payload: dict[str, Any]) -> str | None:
    """Validate `/api/governance/approve` request payload."""
    allowed_keys = {
        "use_case_id",
        "run_id",
        "approved_by",
        "note",
        "accept_warnings",
        "accept_all_warnings",
        "warning_rationale",
        "force",
    }
    unknown = sorted(set(payload) - allowed_keys)
    if unknown:
        return "Unknown request field(s): " + ", ".join(unknown)

    use_case_id = payload.get("use_case_id")
    if not isinstance(use_case_id, str) or not use_case_id.strip():
        return "use_case_id must be a non-empty string."

    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        return "run_id must be a non-empty string."

    approved_by = payload.get("approved_by")
    if approved_by is not None and not isinstance(approved_by, str):
        return "approved_by must be a string or null."

    note = payload.get("note")
    if note is not None and not isinstance(note, str):
        return "note must be a string or null."

    warning_rationale = payload.get("warning_rationale")
    if warning_rationale is not None and not isinstance(warning_rationale, str):
        return "warning_rationale must be a string or null."

    accept_warnings = payload.get("accept_warnings", [])
    if not isinstance(accept_warnings, list):
        return "accept_warnings must be an array of strings."
    if any(not isinstance(item, str) for item in accept_warnings):
        return "accept_warnings must contain only strings."

    accept_all_warnings = payload.get("accept_all_warnings", False)
    if not isinstance(accept_all_warnings, bool):
        return "accept_all_warnings must be a boolean."

    force = payload.get("force", False)
    if not isinstance(force, bool):
        return "force must be a boolean."

    return None


def _validate_inference_request(payload: dict[str, Any], mode: str) -> str | None:
    """Validate `/api/inference/online|batch` request payload."""
    use_case_id = payload.get("use_case_id")
    if not isinstance(use_case_id, str) or not use_case_id.strip():
        return "use_case_id must be a non-empty string."
    use_case_id = use_case_id.strip()
    if use_case_id not in INFERENCE_INPUT_CONTRACTS:
        known = ", ".join(sorted(INFERENCE_INPUT_CONTRACTS))
        return f"use_case_id must be one of: {known}"

    seed = payload.get("seed", 101)
    try:
        int(seed)
    except (TypeError, ValueError):
        return "seed must be an integer."

    registry_stage = str(payload.get("registry_stage", "auto")).strip().lower()
    if registry_stage not in INFERENCE_REGISTRY_STAGES:
        return (
            "registry_stage must be one of: "
            + ", ".join(sorted(INFERENCE_REGISTRY_STAGES))
        )

    if mode == "online":
        allowed_keys = {"use_case_id", "record", "seed", "registry_stage"}
        if not isinstance(payload.get("record"), dict):
            return "record must be an object for /api/inference/online."
        unknown = sorted(set(payload) - allowed_keys)
        if unknown:
            return "Unknown request field(s): " + ", ".join(unknown)
        return _validate_inference_record_contract(
            use_case_id=use_case_id,
            record=payload["record"],
            row_index=0,
        )

    if mode == "batch":
        allowed_keys = {"use_case_id", "records", "seed", "registry_stage"}
        records = payload.get("records")
        if not isinstance(records, list) or not records:
            return "records must be a non-empty array for /api/inference/batch."
        unknown = sorted(set(payload) - allowed_keys)
        if unknown:
            return "Unknown request field(s): " + ", ".join(unknown)
        for idx, row in enumerate(records):
            if not isinstance(row, dict):
                return f"records[{idx}] must be an object."
            row_error = _validate_inference_record_contract(
                use_case_id=use_case_id,
                record=row,
                row_index=idx,
            )
            if row_error:
                return row_error
        return None

    return "Unsupported inference mode."


def _validate_inference_record_contract(
    *,
    use_case_id: str,
    record: dict[str, Any],
    row_index: int,
) -> str | None:
    """Validate one model-input record against strict use-case contract."""
    schema = INFERENCE_INPUT_CONTRACTS.get(use_case_id)
    if schema is None:
        return f"Unsupported use_case_id '{use_case_id}'."

    required = dict(schema.get("required", {}))
    optional = dict(schema.get("optional", {}))
    allowed = set(required) | set(optional)

    unknown_fields = sorted(set(record) - allowed)
    if unknown_fields:
        return (
            f"records[{row_index}] includes unsupported field(s): "
            + ", ".join(unknown_fields)
        )

    missing_fields = [key for key in sorted(required) if key not in record]
    if missing_fields:
        return (
            f"records[{row_index}] missing required field(s): "
            + ", ".join(missing_fields)
        )

    for key, type_name in {**required, **optional}.items():
        if key not in record:
            continue
        if not _matches_contract_type(record[key], type_name):
            return (
                f"records[{row_index}].{key} must satisfy type '{type_name}' "
                f"(received {type(record[key]).__name__})."
            )
    return None


def _matches_contract_type(value: Any, type_name: str) -> bool:
    """Return True when value conforms to the declared input contract type."""
    if type_name == "string":
        return isinstance(value, str) and bool(value.strip())

    if type_name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    if type_name == "binary_label":
        if isinstance(value, bool):
            return True
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            return value.strip().lower() in {"0", "1", "true", "false", "yes", "no"}
        return False

    return False


def run_inference_online(
    *,
    use_case_id: str,
    record: dict[str, Any],
    seed: int = 101,
    registry_stage: str = "auto",
    artifacts_root: Path | None = None,
) -> dict[str, Any]:
    """Run single-record inference and return prediction + activation payload."""
    batch_response = run_inference_batch(
        use_case_id=use_case_id,
        records=[record],
        seed=seed,
        registry_stage=registry_stage,
        artifacts_root=artifacts_root,
    )
    prediction = batch_response["predictions"][0]
    activation = batch_response["activations"][0]
    return {
        "mode": "online",
        "use_case_id": batch_response["use_case_id"],
        "seed": batch_response["seed"],
        "registry_stage": batch_response["registry_stage"],
        "registry_run_id": batch_response["registry_run_id"],
        "model_version": batch_response["model_version"],
        "model_backend": batch_response["model_backend"],
        "output_contract": batch_response["output_contract"],
        "activation_contract": batch_response["activation_contract"],
        "prediction_count": 1,
        "activation_count": 1,
        "prediction": prediction,
        "activation": activation,
        "model_metrics": batch_response["model_metrics"],
        "registry": batch_response["registry"],
    }


def run_inference_batch(
    *,
    use_case_id: str,
    records: list[dict[str, Any]],
    seed: int = 101,
    registry_stage: str = "auto",
    artifacts_root: Path | None = None,
) -> dict[str, Any]:
    """Run batch inference and return predictions + activation payloads."""
    root = artifacts_root if artifacts_root is not None else ROOT / "artifacts"
    schema = INFERENCE_INPUT_CONTRACTS.get(use_case_id)
    if schema is None:
        known = ", ".join(sorted(INFERENCE_INPUT_CONTRACTS))
        raise ValueError(f"Unsupported use_case_id '{use_case_id}'. Known: {known}")
    if not records:
        raise ValueError("records must contain at least one row.")

    for idx, row in enumerate(records):
        if not isinstance(row, dict):
            raise ValueError(f"records[{idx}] must be an object.")
        row_error = _validate_inference_record_contract(
            use_case_id=use_case_id,
            record=row,
            row_index=idx,
        )
        if row_error:
            raise ValueError(row_error)

    contract = load_contract_by_id(use_case_id=use_case_id)
    model = get_model_for_use_case(use_case_id)
    rows, model_metrics = model.run(
        records=records,
        contract=contract,
        seed=int(seed),
    )

    _validate_prediction_response_contract(
        rows=rows,
        required_fields=contract.output_contract.fields,
    )
    activation_rows = build_activation_payloads(use_case_id=use_case_id, model_rows=rows)
    activation_required_fields = get_activation_contract_fields(use_case_id)
    _validate_activation_response_contract(
        rows=activation_rows,
        required_fields=activation_required_fields,
    )

    registry_meta = _resolve_registry_metadata(
        use_case_id=use_case_id,
        requested_stage=registry_stage,
        artifacts_root=root,
    )
    model_version = _resolve_inference_model_version(
        rows=rows,
        model_metrics=model_metrics,
        registry_meta=registry_meta,
    )
    model_backend = str(model_metrics.get("model_backend", "unknown"))

    return {
        "mode": "batch",
        "use_case_id": use_case_id,
        "seed": int(seed),
        "registry_stage": registry_meta["stage"],
        "registry_run_id": registry_meta["run_id"],
        "model_version": model_version,
        "model_backend": model_backend,
        "output_contract": {
            "type": contract.output_contract.type,
            "fields": list(contract.output_contract.fields),
        },
        "activation_contract": {
            "fields": activation_required_fields,
        },
        "record_count": len(records),
        "prediction_count": len(rows),
        "activation_count": len(activation_rows),
        "predictions": rows,
        "activations": activation_rows,
        "model_metrics": model_metrics,
        "registry": registry_meta,
    }


def _resolve_registry_metadata(
    *,
    use_case_id: str,
    requested_stage: str,
    artifacts_root: Path,
) -> dict[str, Any]:
    """Resolve preferred model-registry entry for inference metadata."""
    normalized_stage = requested_stage.strip().lower() or "auto"
    if normalized_stage not in INFERENCE_REGISTRY_STAGES:
        raise ValueError(
            "registry_stage must be one of: "
            + ", ".join(sorted(INFERENCE_REGISTRY_STAGES))
        )

    payload = list_model_registry_entries(
        artifacts_root=artifacts_root,
        use_case_id=use_case_id,
        limit=1_000,
    )
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        entries = []

    selected: dict[str, Any] | None = None
    if normalized_stage == "auto":
        for stage_name in INFERENCE_REGISTRY_RESOLUTION_ORDER:
            selected = next(
                (
                    row
                    for row in entries
                    if str(row.get("stage", "")).strip().lower() == stage_name
                ),
                None,
            )
            if selected:
                break
        if selected is None and entries:
            selected = entries[0] if isinstance(entries[0], dict) else None
    else:
        selected = next(
            (
                row
                for row in entries
                if str(row.get("stage", "")).strip().lower() == normalized_stage
            ),
            None,
        )
        if selected is None:
            raise ValueError(
                "No model-registry entry found for "
                f"use_case_id={use_case_id} at stage='{normalized_stage}'."
            )

    if selected is None:
        return {
            "requested_stage": normalized_stage,
            "stage": "unregistered",
            "registered": False,
            "run_id": None,
            "model_version": None,
            "model_backend": None,
            "updated_at_utc": None,
        }

    return {
        "requested_stage": normalized_stage,
        "stage": str(selected.get("stage", "unknown")).strip().lower() or "unknown",
        "registered": True,
        "run_id": selected.get("run_id"),
        "model_version": selected.get("model_version"),
        "model_backend": selected.get("model_backend"),
        "updated_at_utc": selected.get("updated_at_utc"),
    }


def _resolve_inference_model_version(
    *,
    rows: list[dict[str, Any]],
    model_metrics: dict[str, Any],
    registry_meta: dict[str, Any],
) -> str:
    """Resolve one stable model-version identifier for inference responses."""
    versions: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in ("model_version", "analysis_version"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                versions.add(value.strip())

    if len(versions) == 1:
        return next(iter(versions))
    if len(versions) > 1:
        return ",".join(sorted(versions))

    metric_version = model_metrics.get("model_version")
    if isinstance(metric_version, str) and metric_version.strip():
        return metric_version.strip()

    registry_version = registry_meta.get("model_version")
    if isinstance(registry_version, str) and registry_version.strip():
        return registry_version.strip()

    return "unknown"


def _validate_prediction_response_contract(
    *,
    rows: list[dict[str, Any]],
    required_fields: list[str],
) -> None:
    """Enforce model output contract in inference responses."""
    if not rows:
        raise RuntimeError("Inference returned zero prediction rows.")
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RuntimeError(f"Inference prediction row {idx} is not an object.")
        missing = [field for field in required_fields if field not in row]
        if missing:
            raise RuntimeError(
                f"Inference prediction row {idx} missing required field(s): {missing}"
            )


def _validate_activation_response_contract(
    *,
    rows: list[dict[str, Any]],
    required_fields: list[str],
) -> None:
    """Enforce activation output contract in inference responses."""
    if not rows:
        raise RuntimeError("Inference returned zero activation rows.")
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RuntimeError(f"Inference activation row {idx} is not an object.")
        missing = [field for field in required_fields if field not in row]
        if missing:
            raise RuntimeError(
                f"Inference activation row {idx} missing required field(s): {missing}"
            )


def build_inference_contract_export() -> dict[str, Any]:
    """Export machine-readable JSON schemas for inference request/response contracts."""
    use_case_rows: list[dict[str, Any]] = []
    for use_case_id in sorted(INFERENCE_INPUT_CONTRACTS):
        contract = load_contract_by_id(use_case_id=use_case_id)
        use_case_rows.append(
            {
                "use_case_id": use_case_id,
                "name": contract.name,
                "primary_kpi": contract.primary_kpi,
                "schemas": _build_use_case_inference_schemas(use_case_id=use_case_id),
            }
        )

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema_version": INFERENCE_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "endpoints": {
            "online": "/api/inference/online",
            "batch": "/api/inference/batch",
            "openapi": "/api/openapi.json",
        },
        "registry_stage_enum": sorted(INFERENCE_REGISTRY_STAGES),
        "resolved_registry_stage_enum": [
            "candidate",
            "approved",
            "prod",
            "unregistered",
            "unknown",
        ],
        "use_cases": use_case_rows,
    }


def build_openapi_spec(*, base_url: str | None = None) -> dict[str, Any]:
    """Build OpenAPI-style spec for inference contracts and serving endpoints."""
    per_use_case = {
        use_case_id: _build_use_case_inference_schemas(use_case_id=use_case_id)
        for use_case_id in sorted(INFERENCE_INPUT_CONTRACTS)
    }

    schemas: dict[str, Any] = {
        "ApiError": {
            "type": "object",
            "properties": {
                "error": {"type": "string"},
                "error_code": {"type": "string"},
                "details": {},
            },
            "required": ["error", "error_code"],
            "additionalProperties": False,
        },
        "InferenceContractExport": {
            "type": "object",
            "properties": {
                "schema_version": {"type": "string"},
                "generated_at_utc": {"type": "string"},
                "endpoints": {"type": "object"},
                "registry_stage_enum": {"type": "array", "items": {"type": "string"}},
                "resolved_registry_stage_enum": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "use_cases": {"type": "array", "items": {"type": "object"}},
            },
            "required": [
                "schema_version",
                "generated_at_utc",
                "endpoints",
                "registry_stage_enum",
                "resolved_registry_stage_enum",
                "use_cases",
            ],
            "additionalProperties": True,
        },
        "GovernanceApprovalRequest": {
            "type": "object",
            "properties": {
                "use_case_id": {"type": "string"},
                "run_id": {"type": "string"},
                "approved_by": {"type": "string"},
                "note": {"type": "string"},
                "accept_warnings": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "accept_all_warnings": {"type": "boolean"},
                "warning_rationale": {"type": "string"},
                "force": {"type": "boolean"},
            },
            "required": ["use_case_id", "run_id"],
            "additionalProperties": False,
        },
        "GovernanceApprovalResponse": {
            "type": "object",
            "properties": {
                "use_case_id": {"type": "string"},
                "run_id": {"type": "string"},
                "monitoring_report_path": {"type": "string"},
                "accepted_warnings": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "force": {"type": "boolean"},
                "deployment_readiness": {"type": "object"},
            },
            "required": [
                "use_case_id",
                "run_id",
                "monitoring_report_path",
                "accepted_warnings",
                "force",
                "deployment_readiness",
            ],
            "additionalProperties": True,
        },
    }
    online_request_refs: list[dict[str, str]] = []
    batch_request_refs: list[dict[str, str]] = []
    online_response_refs: list[dict[str, str]] = []
    batch_response_refs: list[dict[str, str]] = []

    for use_case_id, schema_bundle in per_use_case.items():
        base_name = _schema_component_name(use_case_id=use_case_id, suffix="")
        online_req_name = f"{base_name}OnlineRequest"
        batch_req_name = f"{base_name}BatchRequest"
        online_resp_name = f"{base_name}OnlineResponse"
        batch_resp_name = f"{base_name}BatchResponse"

        schemas[online_req_name] = schema_bundle["online_request"]
        schemas[batch_req_name] = schema_bundle["batch_request"]
        schemas[online_resp_name] = schema_bundle["online_response"]
        schemas[batch_resp_name] = schema_bundle["batch_response"]

        online_request_refs.append({"$ref": f"#/components/schemas/{online_req_name}"})
        batch_request_refs.append({"$ref": f"#/components/schemas/{batch_req_name}"})
        online_response_refs.append({"$ref": f"#/components/schemas/{online_resp_name}"})
        batch_response_refs.append({"$ref": f"#/components/schemas/{batch_resp_name}"})

    spec: dict[str, Any] = {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": "CDP Inference API Contracts",
            "version": INFERENCE_SCHEMA_VERSION,
            "description": (
                "Contract-driven inference endpoints for online and batch scoring, "
                "including activation payload contracts."
            ),
        },
        "paths": {
            "/api/inference/online": {
                "post": {
                    "summary": "Run single-record inference",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": {"oneOf": online_request_refs}}
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Online inference response",
                            "content": {
                                "application/json": {"schema": {"oneOf": online_response_refs}}
                            },
                        },
                        "400": {
                            "description": "Validation error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiError"}
                                }
                            },
                        },
                        "500": {
                            "description": "Inference runtime error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiError"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/inference/batch": {
                "post": {
                    "summary": "Run batch inference",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": {"oneOf": batch_request_refs}}
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Batch inference response",
                            "content": {
                                "application/json": {"schema": {"oneOf": batch_response_refs}}
                            },
                        },
                        "400": {
                            "description": "Validation error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiError"}
                                }
                            },
                        },
                        "500": {
                            "description": "Inference runtime error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiError"}
                                }
                            },
                        },
                    },
                }
            },
            "/api/contracts/inference": {
                "get": {
                    "summary": "Export inference contracts",
                    "responses": {
                        "200": {
                            "description": "Inference contract schema export",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/InferenceContractExport"
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/api/openapi.json": {
                "get": {
                    "summary": "Export OpenAPI-style spec",
                    "responses": {
                        "200": {
                            "description": "OpenAPI JSON",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        }
                    },
                }
            },
            "/metrics": {
                "get": {
                    "summary": "Export Prometheus-compatible runtime and run metrics",
                    "responses": {
                        "200": {
                            "description": "Prometheus text exposition",
                            "content": {"text/plain": {"schema": {"type": "string"}}},
                        }
                    },
                }
            },
            "/api/governance/approve": {
                "post": {
                    "summary": "Approve deployment readiness for one run",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/GovernanceApprovalRequest"
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Governance approval updated",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/GovernanceApprovalResponse"
                                    }
                                }
                            },
                        },
                        "400": {
                            "description": "Validation error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiError"}
                                }
                            },
                        },
                        "500": {
                            "description": "Unexpected governance approval error",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ApiError"}
                                }
                            },
                        },
                    },
                }
            },
        },
        "components": {"schemas": schemas},
    }
    if base_url:
        spec["servers"] = [{"url": base_url}]
    return spec


def _build_use_case_inference_schemas(*, use_case_id: str) -> dict[str, Any]:
    """Build request and response JSON schemas for one use case."""
    return {
        "online_request": _build_online_request_schema(use_case_id=use_case_id),
        "batch_request": _build_batch_request_schema(use_case_id=use_case_id),
        "online_response": _build_online_response_schema(use_case_id=use_case_id),
        "batch_response": _build_batch_response_schema(use_case_id=use_case_id),
        "prediction_row": _build_prediction_row_schema(use_case_id=use_case_id),
        "activation_row": _build_activation_row_schema(use_case_id=use_case_id),
    }


def _build_online_request_schema(*, use_case_id: str) -> dict[str, Any]:
    """Build JSON schema for `/api/inference/online` request payload."""
    return {
        "type": "object",
        "properties": {
            "use_case_id": {"type": "string", "enum": [use_case_id]},
            "registry_stage": {
                "type": "string",
                "enum": sorted(INFERENCE_REGISTRY_STAGES),
                "default": "auto",
            },
            "seed": {"type": "integer", "default": 101},
            "record": _build_input_record_schema(use_case_id=use_case_id),
        },
        "required": ["use_case_id", "record"],
        "additionalProperties": False,
    }


def _build_batch_request_schema(*, use_case_id: str) -> dict[str, Any]:
    """Build JSON schema for `/api/inference/batch` request payload."""
    return {
        "type": "object",
        "properties": {
            "use_case_id": {"type": "string", "enum": [use_case_id]},
            "registry_stage": {
                "type": "string",
                "enum": sorted(INFERENCE_REGISTRY_STAGES),
                "default": "auto",
            },
            "seed": {"type": "integer", "default": 101},
            "records": {
                "type": "array",
                "minItems": 1,
                "items": _build_input_record_schema(use_case_id=use_case_id),
            },
        },
        "required": ["use_case_id", "records"],
        "additionalProperties": False,
    }


def _build_online_response_schema(*, use_case_id: str) -> dict[str, Any]:
    """Build JSON schema for `/api/inference/online` response payload."""
    return {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["online"]},
            "use_case_id": {"type": "string", "enum": [use_case_id]},
            "seed": {"type": "integer"},
            "registry_stage": {
                "type": "string",
                "enum": ["candidate", "approved", "prod", "unregistered", "unknown"],
            },
            "registry_run_id": {"type": ["string", "null"]},
            "model_version": {"type": "string"},
            "model_backend": {"type": "string"},
            "output_contract": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["type", "fields"],
                "additionalProperties": False,
            },
            "activation_contract": {
                "type": "object",
                "properties": {
                    "fields": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["fields"],
                "additionalProperties": False,
            },
            "prediction_count": {"type": "integer", "enum": [1]},
            "activation_count": {"type": "integer", "enum": [1]},
            "prediction": _build_prediction_row_schema(use_case_id=use_case_id),
            "activation": _build_activation_row_schema(use_case_id=use_case_id),
            "model_metrics": {"type": "object"},
            "registry": _build_registry_metadata_schema(),
        },
        "required": [
            "mode",
            "use_case_id",
            "seed",
            "registry_stage",
            "registry_run_id",
            "model_version",
            "model_backend",
            "output_contract",
            "activation_contract",
            "prediction_count",
            "activation_count",
            "prediction",
            "activation",
            "model_metrics",
            "registry",
        ],
        "additionalProperties": False,
    }


def _build_batch_response_schema(*, use_case_id: str) -> dict[str, Any]:
    """Build JSON schema for `/api/inference/batch` response payload."""
    return {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["batch"]},
            "use_case_id": {"type": "string", "enum": [use_case_id]},
            "seed": {"type": "integer"},
            "registry_stage": {
                "type": "string",
                "enum": ["candidate", "approved", "prod", "unregistered", "unknown"],
            },
            "registry_run_id": {"type": ["string", "null"]},
            "model_version": {"type": "string"},
            "model_backend": {"type": "string"},
            "output_contract": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "fields": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["type", "fields"],
                "additionalProperties": False,
            },
            "activation_contract": {
                "type": "object",
                "properties": {
                    "fields": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["fields"],
                "additionalProperties": False,
            },
            "record_count": {"type": "integer", "minimum": 1},
            "prediction_count": {"type": "integer", "minimum": 1},
            "activation_count": {"type": "integer", "minimum": 1},
            "predictions": {
                "type": "array",
                "minItems": 1,
                "items": _build_prediction_row_schema(use_case_id=use_case_id),
            },
            "activations": {
                "type": "array",
                "minItems": 1,
                "items": _build_activation_row_schema(use_case_id=use_case_id),
            },
            "model_metrics": {"type": "object"},
            "registry": _build_registry_metadata_schema(),
        },
        "required": [
            "mode",
            "use_case_id",
            "seed",
            "registry_stage",
            "registry_run_id",
            "model_version",
            "model_backend",
            "output_contract",
            "activation_contract",
            "record_count",
            "prediction_count",
            "activation_count",
            "predictions",
            "activations",
            "model_metrics",
            "registry",
        ],
        "additionalProperties": False,
    }


def _build_registry_metadata_schema() -> dict[str, Any]:
    """Build JSON schema for inference registry metadata block."""
    return {
        "type": "object",
        "properties": {
            "requested_stage": {
                "type": "string",
                "enum": sorted(INFERENCE_REGISTRY_STAGES),
            },
            "stage": {
                "type": "string",
                "enum": ["candidate", "approved", "prod", "unregistered", "unknown"],
            },
            "registered": {"type": "boolean"},
            "run_id": {"type": ["string", "null"]},
            "model_version": {"type": ["string", "null"]},
            "model_backend": {"type": ["string", "null"]},
            "updated_at_utc": {"type": ["string", "null"]},
        },
        "required": [
            "requested_stage",
            "stage",
            "registered",
            "run_id",
            "model_version",
            "model_backend",
            "updated_at_utc",
        ],
        "additionalProperties": False,
    }


def _build_input_record_schema(*, use_case_id: str) -> dict[str, Any]:
    """Build strict input-record schema for one use case."""
    schema = INFERENCE_INPUT_CONTRACTS.get(use_case_id)
    if schema is None:
        raise ValueError(f"Unsupported use_case_id '{use_case_id}'.")

    required = dict(schema.get("required", {}))
    optional = dict(schema.get("optional", {}))
    properties: dict[str, Any] = {}
    for field, type_name in {**required, **optional}.items():
        properties[field] = _json_schema_for_declared_type(type_name)

    return {
        "type": "object",
        "properties": properties,
        "required": sorted(required),
        "additionalProperties": False,
    }


def _build_prediction_row_schema(*, use_case_id: str) -> dict[str, Any]:
    """Build output prediction-row schema from use-case output contract fields."""
    contract = load_contract_by_id(use_case_id=use_case_id)
    properties: dict[str, Any] = {}
    for field in contract.output_contract.fields:
        field_type = INFERENCE_OUTPUT_FIELD_TYPE_HINTS.get(field)
        if field_type:
            properties[field] = _json_schema_for_declared_type(field_type)
        else:
            properties[field] = {"description": "Output contract field."}

    return {
        "type": "object",
        "properties": properties,
        "required": sorted(contract.output_contract.fields),
        "additionalProperties": True,
    }


def _build_activation_row_schema(*, use_case_id: str) -> dict[str, Any]:
    """Build activation payload row schema from serving activation contract fields."""
    fields = get_activation_contract_fields(use_case_id)
    properties: dict[str, Any] = {}
    for field in fields:
        field_type = ACTIVATION_FIELD_TYPE_HINTS.get(field)
        if field_type:
            properties[field] = _json_schema_for_declared_type(field_type)
        else:
            properties[field] = {}
    return {
        "type": "object",
        "properties": properties,
        "required": sorted(fields),
        "additionalProperties": True,
    }


def _json_schema_for_declared_type(type_name: str) -> dict[str, Any]:
    """Map internal contract type tokens to JSON Schema objects."""
    if type_name == "string":
        return {"type": "string", "minLength": 1}
    if type_name == "number":
        return {"type": "number"}
    if type_name == "binary_label":
        return {
            "oneOf": [
                {"type": "boolean"},
                {"type": "number"},
                {
                    "type": "string",
                    "enum": ["0", "1", "true", "false", "yes", "no"],
                },
            ]
        }
    if type_name == "string_array":
        return {"type": "array", "items": {"type": "string"}}
    if type_name == "object":
        return {"type": "object"}
    return {}


def _schema_component_name(*, use_case_id: str, suffix: str) -> str:
    """Build OpenAPI component-safe schema name."""
    base = use_case_id.replace("-", "_")
    if suffix:
        return f"{base}_{suffix}"
    return base


def _compute_stage_health(
    summary: dict[str, Any],
    artifacts_root: Path | None = None,
) -> list[dict[str, str]]:
    """Compute pass/fail stage statuses directly from summary artifact evidence."""
    artifacts = summary.get("artifacts", {})
    records = summary.get("records", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
    if not isinstance(records, dict):
        records = {}

    source_tables = records.get("source_tables", {})
    source_rows = 0
    if isinstance(source_tables, dict):
        for value in source_tables.values():
            if isinstance(value, int):
                source_rows += value

    stage_health: list[dict[str, str]] = []
    for layer_id, label in STAGE_DEFINITIONS:
        status = "pass"
        detail = "Required evidence found."

        if layer_id == "data_sources":
            if source_rows <= 0:
                status = "fail"
                detail = "No source rows recorded."
            else:
                detail = f"{source_rows} source row(s) recorded."

        elif layer_id == "ingestion_event_bus":
            topics = artifacts.get("ingestion_event_bus", {})
            if not isinstance(topics, dict) or not topics:
                status = "fail"
                detail = "No ingestion topics found."
            else:
                missing = 0
                for path_text in topics.values():
                    if not isinstance(path_text, str) or not _path_exists(path_text, artifacts_root=artifacts_root):
                        missing += 1
                if missing:
                    status = "fail"
                    detail = f"{missing} ingestion artifact(s) missing."
                else:
                    detail = f"{len(topics)} ingestion topic artifact(s) present."

        elif layer_id == "raw_curated_storage":
            missing = _missing_artifacts(
                artifacts,
                ["raw_events", "curated_records"],
                artifacts_root=artifacts_root,
            )
            if missing:
                status = "fail"
                detail = f"Missing: {', '.join(missing)}"

        elif layer_id == "identity_customer_360":
            missing = _missing_artifacts(
                artifacts,
                ["resolved_records"],
                artifacts_root=artifacts_root,
            )
            if missing:
                status = "fail"
                detail = f"Missing: {', '.join(missing)}"

        elif layer_id == "feature_layer":
            missing = _missing_artifacts(
                artifacts,
                ["feature_rows"],
                artifacts_root=artifacts_root,
            )
            if missing:
                status = "fail"
                detail = f"Missing: {', '.join(missing)}"

        elif layer_id == "model_layer":
            missing = _missing_artifacts(
                artifacts,
                ["model_predictions"],
                artifacts_root=artifacts_root,
            )
            if missing:
                status = "fail"
                detail = f"Missing: {', '.join(missing)}"

        elif layer_id == "serving_activation":
            missing = _missing_artifacts(
                artifacts,
                ["activation_payloads"],
                artifacts_root=artifacts_root,
            )
            if missing:
                status = "fail"
                detail = f"Missing: {', '.join(missing)}"

        elif layer_id == "monitoring_governance":
            missing = _missing_artifacts(
                artifacts,
                ["monitoring_report"],
                artifacts_root=artifacts_root,
            )
            if missing:
                status = "fail"
                detail = f"Missing: {', '.join(missing)}"

        stage_health.append(
            {
                "layer_id": layer_id,
                "label": label,
                "status": status,
                "detail": detail,
            }
        )

    return stage_health


def _missing_artifacts(
    artifacts: dict[str, Any],
    keys: list[str],
    artifacts_root: Path | None = None,
) -> list[str]:
    """Return required artifact keys that are missing or non-existent."""
    missing: list[str] = []
    for key in keys:
        path_text = artifacts.get(key)
        if not isinstance(path_text, str) or not _path_exists(path_text, artifacts_root=artifacts_root):
            missing.append(key)
    return missing


def _read_monitoring_report(
    *,
    summary: dict[str, Any],
    artifacts_root: Path,
) -> dict[str, Any] | None:
    """Read monitoring-governance report referenced by run summary."""
    artifacts = summary.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    monitoring_report = artifacts.get("monitoring_report")
    if not isinstance(monitoring_report, str):
        return None
    path = _resolve_path(path_text=monitoring_report, artifacts_root=artifacts_root)
    return _read_json_file(path)


def _path_exists(path_text: str, artifacts_root: Path | None = None) -> bool:
    """Check whether a relative/absolute artifact path exists."""
    return _resolve_path(path_text=path_text, artifacts_root=artifacts_root).exists()


def _display_path_text(
    value: Any,
    *,
    artifacts_root: Path | None = None,
    fallback_path: Path | None = None,
) -> str | None:
    """Return a repo-friendly artifact path for UI/API payloads."""
    if isinstance(value, str) and value.strip():
        path = Path(value)
        if path.is_absolute():
            return _relativize_path(path, artifacts_root=artifacts_root)
        return path.as_posix()
    if fallback_path is not None:
        return _relativize_path(fallback_path, artifacts_root=artifacts_root)
    return None


def _sanitize_paths_for_response(value: Any, *, artifacts_root: Path | None = None) -> Any:
    """Recursively remove machine-local absolute paths from JSON-like responses."""
    if isinstance(value, dict):
        return {
            str(key): _sanitize_paths_for_response(item, artifacts_root=artifacts_root)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _sanitize_paths_for_response(item, artifacts_root=artifacts_root)
            for item in value
        ]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and Path(stripped).is_absolute():
            return _relativize_path(Path(stripped), artifacts_root=artifacts_root)
    return value


def _resolve_path(path_text: str, artifacts_root: Path | None = None) -> Path:
    """Resolve artifact path strings against repo/artifacts roots when relative."""
    path = Path(path_text)
    if path.is_absolute():
        return path

    if artifacts_root is not None:
        candidate = artifacts_root / path
        if candidate.exists():
            return candidate

    return ROOT / path


def resolve_artifact_download_path(
    *,
    path_text: str,
    artifacts_root: Path | None = None,
) -> tuple[Path | None, str | None]:
    """Validate and resolve safe artifact download path."""
    value = path_text.strip()
    if not value:
        return None, "Query parameter 'path' must be a non-empty string."

    resolved = _resolve_path(path_text=value, artifacts_root=artifacts_root).resolve()
    root_resolved = ROOT.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        return None, "Artifact path must remain within repository root."
    if not resolved.exists():
        return None, f"Artifact path does not exist: {value}"
    if not resolved.is_file():
        return None, f"Artifact path is not a file: {value}"
    return resolved, None


def _read_json_file(path: Path) -> dict[str, Any] | None:
    """Read JSON object from disk."""
    try:
        with path.open("r", encoding="utf-8") as f:
            parsed = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _relativize_path(path: Path, artifacts_root: Path | None = None) -> str:
    """Return repo/artifacts-relative path when possible, else absolute path."""
    if not path.is_absolute():
        return str(path.as_posix())

    try:
        return str(path.relative_to(ROOT).as_posix())
    except ValueError:
        pass

    if artifacts_root is not None:
        try:
            return str(path.relative_to(artifacts_root.parent).as_posix())
        except ValueError:
            pass
        try:
            return str((Path(artifacts_root.name) / path.relative_to(artifacts_root)).as_posix())
        except ValueError:
            pass

    return str(path.as_posix())


def main() -> int:
    """Start threaded HTTP server for live UI + API."""
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), LiveUIHandler)
    print(f"Live UI server running on http://{args.host}:{args.port}/ui/experience/")
    print(
        "API endpoints: /api/health, /api/view-model, /api/run, /api/jobs, "
        "/api/scenarios, /api/oss-inventory, /api/enterprise-hardening, "
        "/api/simulation/session, /api/simulation/session/<session_id>, "
        "/api/simulation/session/<session_id>/run-all, "
        "/api/simulation/session/<session_id>/run-next, "
        "/api/simulation/session/<session_id>/reset, "
        "/api/simulation/session/<session_id>/pause, "
        "/api/simulation/session/<session_id>/resume, "
        "/api/artifacts/download, "
        "/api/run-history, /api/runs, /api/runs/<use_case_id>/<run_id>, "
        "/api/runs/<use_case_id>/<run_id>/stages, "
        "/api/runs/<use_case_id>/<run_id>/data-quality, /api/portfolio/summary, "
        "/api/governance/approve, "
        "/api/inference/online, /api/inference/batch, /api/contracts/inference, "
        "/api/openapi.json, /metrics"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
