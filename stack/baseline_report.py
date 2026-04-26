from __future__ import annotations

"""Baseline report builder for strict real-data model runs.

Creates a compact snapshot from the latest run per use case so teams can track
model/governance drift against a known baseline.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stack.run_registry import DEFAULT_ARTIFACTS_ROOT, get_run_summary, list_run_summaries


def generate_baseline_report(
    *,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
) -> dict[str, Any]:
    """Build baseline snapshot from the latest run of each use case."""
    root = Path(artifacts_root)
    listing = list_run_summaries(
        artifacts_root=root,
        run_status="all",
        infra_profile="all",
        sort="desc",
        limit=1_000_000,
        offset=0,
    )
    rows = listing.get("runs", [])
    if not isinstance(rows, list):
        rows = []

    latest_by_use_case: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        use_case_id = str(row.get("use_case_id", "")).strip()
        if not use_case_id or use_case_id in latest_by_use_case:
            continue
        latest_by_use_case[use_case_id] = row

    run_rows: list[dict[str, Any]] = []
    for use_case_id in sorted(latest_by_use_case):
        compact = latest_by_use_case[use_case_id]
        run_id = str(compact.get("run_id", "")).strip()
        if not run_id:
            continue
        summary = get_run_summary(
            use_case_id=use_case_id,
            run_id=run_id,
            artifacts_root=root,
        )
        if not isinstance(summary, dict):
            continue
        run_rows.append(_build_baseline_run_row(summary=summary, artifacts_root=root))

    pass_count = sum(
        1 for row in run_rows if str(row.get("run_status", "")).lower() == "pass"
    )
    fail_count = sum(
        1 for row in run_rows if str(row.get("run_status", "")).lower() == "fail"
    )

    return {
        "generated_at_utc": _utc_now(),
        "artifacts_root": str(root.as_posix()),
        "selection": {
            "strategy": "latest_per_use_case",
            "input_runs_considered": len(rows),
            "selected_run_count": len(run_rows),
        },
        "totals": {
            "use_case_count": len(run_rows),
            "latest_pass_count": pass_count,
            "latest_fail_count": fail_count,
            "all_pass": fail_count == 0 and len(run_rows) > 0,
        },
        "runs": run_rows,
    }


def write_baseline_report(
    *,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Generate and persist baseline report JSON."""
    root = Path(artifacts_root)
    target = output_path if output_path is not None else root / "baseline_report.json"
    payload = generate_baseline_report(artifacts_root=root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["report_path"] = str(target.as_posix())
    return payload


def _build_baseline_run_row(
    *,
    summary: dict[str, Any],
    artifacts_root: Path,
) -> dict[str, Any]:
    """Build compact run row containing model and governance snapshot fields."""
    model_metrics = summary.get("model_metrics", {})
    if not isinstance(model_metrics, dict):
        model_metrics = {}

    primary_kpi = model_metrics.get("primary_kpi")
    primary_kpi_name = str(primary_kpi).strip() if isinstance(primary_kpi, str) else None
    primary_kpi_value = (
        model_metrics.get(primary_kpi_name) if primary_kpi_name is not None else None
    )

    monitoring = _read_monitoring_report(summary=summary, artifacts_root=artifacts_root)
    data_quality: dict[str, Any] = {}
    deployment_readiness: dict[str, Any] = {}
    if isinstance(monitoring, dict):
        raw_dq = monitoring.get("data_quality")
        raw_dr = monitoring.get("deployment_readiness")
        if isinstance(raw_dq, dict):
            data_quality = raw_dq
        if isinstance(raw_dr, dict):
            deployment_readiness = raw_dr

    strict_mode = bool(summary.get("strict_model_backends", False))
    run_status = str(summary.get("run_status", "unknown")).lower()
    run_row = {
        "use_case_id": summary.get("use_case_id"),
        "name": summary.get("name"),
        "run_id": summary.get("run_id"),
        "run_status": run_status,
        "infra_profile": str(summary.get("infra_profile", "local")).lower(),
        "seed": summary.get("seed"),
        "strict_model_backends": strict_mode,
        "model_backend": model_metrics.get("model_backend"),
        "model_version": model_metrics.get("model_version"),
        "primary_kpi": primary_kpi_name,
        "primary_kpi_value": primary_kpi_value,
        "metric_snapshot": _metric_snapshot(model_metrics=model_metrics),
        "data_quality_status": data_quality.get("status"),
        "data_quality_summary": data_quality.get("summary", {}),
        "deployment_readiness_status": deployment_readiness.get("status"),
        "deployment_blockers": deployment_readiness.get("blockers", []),
        "summary_path": summary.get("summary_path"),
    }
    return run_row


def _metric_snapshot(*, model_metrics: dict[str, Any]) -> dict[str, Any]:
    """Select stable KPI-supporting metrics for baseline comparison."""
    selected_keys = [
        "avg_expected_uplift",
        "avg_confidence",
        "auc_overall",
        "tf_holdout_auc",
        "avg_churn_risk_score",
        "avg_incremental_lift",
        "avg_iROAS",
        "avg_recommended_spend",
        "avg_expected_incremental_revenue",
        "revenue_mape",
    ]
    snapshot: dict[str, Any] = {}
    for key in selected_keys:
        if key in model_metrics:
            snapshot[key] = model_metrics.get(key)
    return snapshot


def _read_monitoring_report(
    *,
    summary: dict[str, Any],
    artifacts_root: Path,
) -> dict[str, Any] | None:
    """Load monitoring-governance report referenced in run summary artifacts."""
    artifacts = summary.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    report_path_text = artifacts.get("monitoring_report")
    if not isinstance(report_path_text, str):
        return None
    path = _resolve_artifact_path(path_text=report_path_text, artifacts_root=artifacts_root)
    return _read_json_object(path)


def _resolve_artifact_path(*, path_text: str, artifacts_root: Path) -> Path:
    """Resolve artifact path from absolute or project-relative forms."""
    path = Path(path_text)
    if path.is_absolute():
        return path
    cwd_candidate = Path.cwd() / path
    if cwd_candidate.exists():
        return cwd_candidate
    root_candidate = artifacts_root / path
    if root_candidate.exists():
        return root_candidate
    return root_candidate


def _read_json_object(path: Path) -> dict[str, Any] | None:
    """Read JSON dictionary from disk."""
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _utc_now() -> str:
    """Return current UTC timestamp as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
