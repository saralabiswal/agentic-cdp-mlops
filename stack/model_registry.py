from __future__ import annotations

"""Model registry and promotion workflow utilities.

This module tracks model run outputs as lifecycle entries and supports
promotion across stages (`candidate` -> `approved` -> `prod`) with
readiness checks derived from run artifacts and governance reports.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stack.run_registry import DEFAULT_ARTIFACTS_ROOT, get_run_summary

MODEL_REGISTRY_VERSION = 1
MODEL_REGISTRY_REL_PATH = Path("model_registry/registry.json")
PROMOTION_STAGES = {"candidate", "approved", "prod"}
PROMOTION_TARGET_STAGES = {"approved", "prod"}
STRICT_BACKEND_REQUIREMENTS: dict[str, set[str]] = {
    "UC-NBA-RET-001": {"tensorflow"},
    "UC-CHURN-RET-002": {"tensorflow"},
    "UC-MMM-PLN-003": {"pymc_marketing_adapter"},
    "UC-INCR-MKT-004": {"econml_dowhy"},
}
REQUIRED_MODEL_ARTIFACT_KEYS = {
    "model_predictions",
    "model_metrics",
    "model_manifest",
}


def register_model_candidate_from_summary(
    *,
    summary: dict[str, Any],
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    summary_path: Path | None = None,
) -> dict[str, Any]:
    """Upsert model run as registry entry in `candidate` stage."""
    use_case_id = str(summary.get("use_case_id", "")).strip()
    run_id = str(summary.get("run_id", "")).strip()
    if not use_case_id or not run_id:
        raise ValueError("Summary must include use_case_id and run_id.")

    registry_path = _resolve_registry_path(artifacts_root=artifacts_root)
    payload = _load_registry_payload(registry_path=registry_path)
    entry = _build_entry_from_summary(
        summary=summary,
        summary_path=summary_path,
        existing_entry=_find_entry(payload["entries"], use_case_id=use_case_id, run_id=run_id),
    )

    entries: list[dict[str, Any]] = payload["entries"]
    replaced = False
    for idx, row in enumerate(entries):
        if _entry_key(row) == (use_case_id, run_id):
            entries[idx] = entry
            replaced = True
            break
    if not replaced:
        entries.append(entry)

    entries.sort(key=_entry_sort_key, reverse=True)
    _save_registry_payload(registry_path=registry_path, payload=payload)

    return {
        "registry_path": str(registry_path.as_posix()),
        "use_case_id": use_case_id,
        "run_id": run_id,
        "stage": entry["stage"],
        "entry_count": len(entries),
    }


def list_model_registry_entries(
    *,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    use_case_id: str | None = None,
    stage: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """List model-registry entries with optional filtering."""
    registry_path = _resolve_registry_path(artifacts_root=artifacts_root)
    payload = _load_registry_payload(registry_path=registry_path)
    normalized_stage = (stage or "").strip().lower() or None

    rows: list[dict[str, Any]] = []
    for entry in payload["entries"]:
        if use_case_id and str(entry.get("use_case_id")) != use_case_id:
            continue
        if normalized_stage and str(entry.get("stage", "")).lower() != normalized_stage:
            continue
        rows.append(entry)

    rows.sort(key=_entry_sort_key, reverse=True)
    safe_limit = max(1, int(limit))
    sliced = rows[:safe_limit]
    return {
        "registry_path": str(registry_path.as_posix()),
        "total": len(rows),
        "count": len(sliced),
        "limit": safe_limit,
        "entries": sliced,
    }


def evaluate_model_promotion_readiness(
    *,
    use_case_id: str,
    run_id: str,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    require_strict_backend: bool = False,
) -> dict[str, Any]:
    """Evaluate promotion readiness using summary + governance artifacts."""
    summary = get_run_summary(
        use_case_id=use_case_id,
        run_id=run_id,
        artifacts_root=artifacts_root,
    )
    if summary is None:
        return {
            "use_case_id": use_case_id,
            "run_id": run_id,
            "ready": False,
            "require_strict_backend": require_strict_backend,
            "blocking_failures": ["summary_exists"],
            "checks": [
                _check_row(
                    name="summary_exists",
                    status="fail",
                    blocking=True,
                    actual=False,
                    expectation="summary.json exists for run",
                    message="Run summary was not found.",
                )
            ],
        }

    checks: list[dict[str, Any]] = []
    run_status = str(summary.get("run_status", "unknown")).lower()
    checks.append(
        _check_row(
            name="run_status_pass",
            status="pass" if run_status == "pass" else "fail",
            blocking=True,
            actual=run_status,
            expectation="pass",
            message="Run must pass monitoring/governance gates.",
        )
    )

    artifacts = summary.get("artifacts", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
    missing_keys = [
        key
        for key in sorted(REQUIRED_MODEL_ARTIFACT_KEYS)
        if not isinstance(artifacts.get(key), str) or not _resolve_path(artifacts_root, str(artifacts.get(key))).exists()
    ]
    checks.append(
        _check_row(
            name="required_model_artifacts",
            status="pass" if not missing_keys else "fail",
            blocking=True,
            actual=[] if not missing_keys else missing_keys,
            expectation="model_predictions, model_metrics, model_manifest exist",
            message="Model artifacts must exist before promotion.",
        )
    )

    model_metrics = summary.get("model_metrics", {})
    if not isinstance(model_metrics, dict):
        model_metrics = {}
    model_version = str(model_metrics.get("model_version", "")).strip()
    checks.append(
        _check_row(
            name="model_version_present",
            status="pass" if model_version else "fail",
            blocking=True,
            actual=model_version or None,
            expectation="non-empty model_version",
            message="Model version is required for lifecycle management.",
        )
    )

    backend = str(model_metrics.get("model_backend", "unknown")).strip()
    required_backends = STRICT_BACKEND_REQUIREMENTS.get(use_case_id, set())
    strict_backend_ok = backend in required_backends if required_backends else True
    checks.append(
        _check_row(
            name="advanced_backend_requirement",
            status="pass" if strict_backend_ok else "fail",
            blocking=require_strict_backend,
            actual=backend,
            expectation=", ".join(sorted(required_backends)) if required_backends else "n/a",
            message=(
                "Advanced backend is recommended."
                if not require_strict_backend
                else "Required advanced backend missing."
            ),
        )
    )

    deployment_status = _read_deployment_status(
        artifacts_root=artifacts_root,
        monitoring_report_path=artifacts.get("monitoring_report"),
    )
    deployment_ok = deployment_status in {"ready", "pending_approval"}
    checks.append(
        _check_row(
            name="deployment_readiness_not_blocked",
            status="pass" if deployment_ok else "fail",
            blocking=True,
            actual=deployment_status,
            expectation="ready or pending_approval",
            message="Monitoring/governance deployment readiness must not be blocked.",
        )
    )

    blocking_failures = [
        str(row["name"])
        for row in checks
        if row["blocking"] and str(row["status"]) != "pass"
    ]

    return {
        "use_case_id": use_case_id,
        "run_id": run_id,
        "ready": not blocking_failures,
        "require_strict_backend": require_strict_backend,
        "blocking_failures": blocking_failures,
        "checks": checks,
        "context": {
            "model_backend": backend,
            "required_backends": sorted(required_backends),
            "model_version": model_version or None,
            "run_status": run_status,
            "deployment_readiness_status": deployment_status,
        },
    }


def promote_model_version(
    *,
    use_case_id: str,
    run_id: str,
    target_stage: str,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    require_strict_backend: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Promote a model run to `approved` or `prod` when readiness checks pass."""
    normalized_stage = target_stage.strip().lower()
    if normalized_stage not in PROMOTION_TARGET_STAGES:
        raise ValueError(f"target_stage must be one of: {sorted(PROMOTION_TARGET_STAGES)}")

    readiness = evaluate_model_promotion_readiness(
        use_case_id=use_case_id,
        run_id=run_id,
        artifacts_root=artifacts_root,
        require_strict_backend=require_strict_backend,
    )
    if not readiness["ready"] and not force:
        blockers = ", ".join(readiness["blocking_failures"])
        raise ValueError(
            "Promotion blocked by readiness checks: "
            + blockers
            + ". Use force=True only for exceptional overrides."
        )

    summary = get_run_summary(
        use_case_id=use_case_id,
        run_id=run_id,
        artifacts_root=artifacts_root,
    )
    if summary is None:
        raise ValueError(f"Run summary not found: use_case_id={use_case_id}, run_id={run_id}")

    registry_path = _resolve_registry_path(artifacts_root=artifacts_root)
    payload = _load_registry_payload(registry_path=registry_path)
    existing = _find_entry(payload["entries"], use_case_id=use_case_id, run_id=run_id)
    entry = _build_entry_from_summary(
        summary=summary,
        summary_path=Path(str(summary.get("summary_path", ""))) if summary.get("summary_path") else None,
        existing_entry=existing,
    )

    previous_stage = str(existing.get("stage", "candidate")) if existing else "candidate"
    entry["stage"] = normalized_stage
    entry["updated_at_utc"] = _utc_now()
    entry.setdefault("promotion_history", [])
    entry["promotion_history"].append(
        {
            "from_stage": previous_stage,
            "to_stage": normalized_stage,
            "at_utc": _utc_now(),
            "forced": bool(force),
            "require_strict_backend": bool(require_strict_backend),
            "actor": _actor_name(),
        }
    )

    if normalized_stage == "prod":
        _demote_other_prod_entries(
            payload["entries"],
            use_case_id=use_case_id,
            keep_run_id=run_id,
        )

    _upsert_entry(payload["entries"], entry)
    payload["entries"].sort(key=_entry_sort_key, reverse=True)
    _save_registry_payload(registry_path=registry_path, payload=payload)

    return {
        "registry_path": str(registry_path.as_posix()),
        "use_case_id": use_case_id,
        "run_id": run_id,
        "target_stage": normalized_stage,
        "force": bool(force),
        "readiness": readiness,
        "entry": entry,
    }


def _resolve_registry_path(artifacts_root: Path) -> Path:
    """Return filesystem path for registry payload under artifacts root."""
    return Path(artifacts_root) / MODEL_REGISTRY_REL_PATH


def _load_registry_payload(registry_path: Path) -> dict[str, Any]:
    """Load registry JSON or return default schema when missing."""
    if not registry_path.exists():
        return {
            "version": MODEL_REGISTRY_VERSION,
            "updated_at_utc": _utc_now(),
            "entries": [],
        }

    try:
        with registry_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {
            "version": MODEL_REGISTRY_VERSION,
            "updated_at_utc": _utc_now(),
            "entries": [],
        }
    if not isinstance(payload, dict):
        return {
            "version": MODEL_REGISTRY_VERSION,
            "updated_at_utc": _utc_now(),
            "entries": [],
        }
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        entries = []
    return {
        "version": int(payload.get("version", MODEL_REGISTRY_VERSION)),
        "updated_at_utc": str(payload.get("updated_at_utc", _utc_now())),
        "entries": entries,
    }


def _save_registry_payload(registry_path: Path, payload: dict[str, Any]) -> None:
    """Persist registry payload atomically."""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    payload["version"] = MODEL_REGISTRY_VERSION
    payload["updated_at_utc"] = _utc_now()
    with registry_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _build_entry_from_summary(
    *,
    summary: dict[str, Any],
    summary_path: Path | None,
    existing_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Create registry entry payload from run summary."""
    use_case_id = str(summary.get("use_case_id"))
    run_id = str(summary.get("run_id"))
    model_metrics = summary.get("model_metrics", {})
    artifacts = summary.get("artifacts", {})
    if not isinstance(model_metrics, dict):
        model_metrics = {}
    if not isinstance(artifacts, dict):
        artifacts = {}

    primary_kpi = model_metrics.get("primary_kpi")
    primary_kpi_value = (
        model_metrics.get(str(primary_kpi))
        if isinstance(primary_kpi, str)
        else None
    )
    previous_stage = str(existing_entry.get("stage", "candidate")) if existing_entry else "candidate"
    stage = previous_stage if previous_stage in PROMOTION_STAGES else "candidate"
    created_at = (
        str(existing_entry.get("created_at_utc"))
        if existing_entry and existing_entry.get("created_at_utc")
        else _utc_now()
    )
    promotion_history = (
        list(existing_entry.get("promotion_history", []))
        if existing_entry and isinstance(existing_entry.get("promotion_history"), list)
        else []
    )

    return {
        "use_case_id": use_case_id,
        "run_id": run_id,
        "name": summary.get("name"),
        "stage": stage,
        "run_status": str(summary.get("run_status", "unknown")),
        "infra_profile": str(summary.get("infra_profile", "local")),
        "strict_model_backends": bool(summary.get("strict_model_backends", False)),
        "model_version": model_metrics.get("model_version"),
        "model_backend": model_metrics.get("model_backend"),
        "model_versions": model_metrics.get("model_versions"),
        "primary_kpi": primary_kpi,
        "primary_kpi_value": primary_kpi_value,
        "summary_path": str(summary_path.as_posix()) if summary_path else summary.get("summary_path"),
        "model_manifest_path": artifacts.get("model_manifest"),
        "monitoring_report_path": artifacts.get("monitoring_report"),
        "created_at_utc": created_at,
        "updated_at_utc": _utc_now(),
        "promotion_history": promotion_history,
    }


def _find_entry(entries: list[dict[str, Any]], *, use_case_id: str, run_id: str) -> dict[str, Any] | None:
    """Find one registry entry by `(use_case_id, run_id)`."""
    for row in entries:
        if _entry_key(row) == (use_case_id, run_id):
            return row
    return None


def _upsert_entry(entries: list[dict[str, Any]], entry: dict[str, Any]) -> None:
    """Replace or append registry entry in-place."""
    key = _entry_key(entry)
    for idx, row in enumerate(entries):
        if _entry_key(row) == key:
            entries[idx] = entry
            return
    entries.append(entry)


def _entry_key(entry: dict[str, Any]) -> tuple[str, str]:
    """Return stable key tuple from entry fields."""
    return str(entry.get("use_case_id", "")), str(entry.get("run_id", ""))


def _entry_sort_key(entry: dict[str, Any]) -> tuple[str, str]:
    """Sort entries newest-first using run ID and update timestamp."""
    run_id = str(entry.get("run_id", ""))
    updated = str(entry.get("updated_at_utc", ""))
    return run_id, updated


def _check_row(
    *,
    name: str,
    status: str,
    blocking: bool,
    actual: Any,
    expectation: str,
    message: str,
) -> dict[str, Any]:
    """Standardize one readiness-check row."""
    return {
        "name": name,
        "status": status,
        "blocking": blocking,
        "actual": actual,
        "expectation": expectation,
        "message": message,
    }


def _resolve_path(artifacts_root: Path, path_text: str) -> Path:
    """Resolve relative artifact path against artifacts root."""
    path = Path(path_text)
    if path.is_absolute():
        return path
    candidate = Path(artifacts_root) / path
    if candidate.exists():
        return candidate
    return path


def _read_deployment_status(*, artifacts_root: Path, monitoring_report_path: Any) -> str | None:
    """Read deployment readiness status from monitoring report file."""
    if not isinstance(monitoring_report_path, str):
        return None
    path = _resolve_path(artifacts_root, monitoring_report_path)
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    deployment = payload.get("deployment_readiness", {})
    if not isinstance(deployment, dict):
        return None
    status = deployment.get("status")
    return str(status) if status is not None else None


def _demote_other_prod_entries(
    entries: list[dict[str, Any]],
    *,
    use_case_id: str,
    keep_run_id: str,
) -> None:
    """Demote older prod entries for same use case to approved."""
    for row in entries:
        if str(row.get("use_case_id")) != use_case_id:
            continue
        if str(row.get("run_id")) == keep_run_id:
            continue
        if str(row.get("stage")) != "prod":
            continue
        row["stage"] = "approved"
        row["updated_at_utc"] = _utc_now()
        row.setdefault("promotion_history", [])
        row["promotion_history"].append(
            {
                "from_stage": "prod",
                "to_stage": "approved",
                "at_utc": _utc_now(),
                "forced": False,
                "require_strict_backend": False,
                "actor": "registry_auto_demote",
            }
        )


def _actor_name() -> str:
    """Resolve actor name for promotion audit metadata."""
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def _utc_now() -> str:
    """Return UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
