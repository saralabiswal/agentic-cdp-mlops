from __future__ import annotations

"""Governance sign-off helpers for monitoring/deployment readiness artifacts."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stack.run_registry import DEFAULT_ARTIFACTS_ROOT, get_run_summary

GOVERNANCE_APPROVALS_FILENAME = "governance_approvals.json"


def approve_run_governance(
    *,
    use_case_id: str,
    run_id: str,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    approved_by: str | None = None,
    note: str | None = None,
    accept_warnings: list[str] | None = None,
    accept_all_warnings: bool = False,
    warning_rationale: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Approve deployment readiness for one run and record audit metadata.

    This updates:
    1. `<run>/monitoring_governance/report.json` deployment readiness block.
    2. `<artifacts_root>/governance_approvals.json` ledger.
    """
    summary = get_run_summary(
        use_case_id=use_case_id,
        run_id=run_id,
        artifacts_root=artifacts_root,
    )
    if summary is None:
        raise ValueError(f"Run summary not found: use_case_id={use_case_id}, run_id={run_id}")

    report_path = _resolve_monitoring_report_path(
        summary=summary,
        artifacts_root=artifacts_root,
    )
    report = _read_json_object(report_path)
    if report is None:
        raise ValueError(f"Monitoring report not found or invalid JSON: {report_path.as_posix()}")

    deployment = report.get("deployment_readiness")
    if not isinstance(deployment, dict):
        deployment = {}

    blockers = _string_list(deployment.get("blockers"))
    warning_checks = _string_list(deployment.get("warning_data_quality_checks"))
    if blockers and not force:
        blocker_text = ", ".join(blockers)
        raise ValueError(
            "Governance approval blocked by deployment blockers: "
            + blocker_text
            + ". Use force=True only for exceptional overrides."
        )

    actor = (approved_by or "").strip() or _actor_name()
    approved_at_utc = _utc_now()
    note_text = (note or "").strip() or "Governance sign-off completed."
    rationale_text = (
        (warning_rationale or "").strip()
        or "Warning accepted for this release; remediation tracked in backlog."
    )

    approval = {
        "status": "approved",
        "approved_at_utc": approved_at_utc,
        "approved_by": actor,
        "method": "manual_signoff",
        "notes": note_text,
        "forced": bool(force),
        "blockers_at_approval": blockers,
    }
    history = deployment.get("approval_history")
    if not isinstance(history, list):
        history = []
    history.append(approval)

    accepted_warning_names = _resolve_accepted_warnings(
        warning_checks=warning_checks,
        accept_warnings=accept_warnings,
        accept_all_warnings=accept_all_warnings,
    )
    unknown_accepted = sorted(
        [name for name in accepted_warning_names if name not in warning_checks]
    )
    if unknown_accepted and not force:
        unknown_text = ", ".join(unknown_accepted)
        raise ValueError(
            "Unknown warning check(s) in approval request: "
            + unknown_text
            + ". Use force=True to override."
        )

    warning_dispositions = _normalize_warning_dispositions(
        deployment.get("warning_dispositions")
    )
    warning_disposition_map = {
        str(row.get("name")): row
        for row in warning_dispositions
        if isinstance(row, dict) and str(row.get("name", "")).strip()
    }
    for warning_name in accepted_warning_names:
        warning_disposition_map[warning_name] = {
            "name": warning_name,
            "decision": "accepted",
            "severity": "warn",
            "rationale": rationale_text,
            "decided_at_utc": approved_at_utc,
            "decided_by": actor,
        }

    deployment["status"] = "ready"
    deployment["approval"] = approval
    deployment["approval_history"] = history
    deployment["warning_dispositions"] = sorted(
        warning_disposition_map.values(),
        key=lambda row: str(row.get("name", "")),
    )

    report["deployment_readiness"] = deployment
    _write_json_object(report_path, report)

    approvals_meta = _upsert_governance_approvals(
        artifacts_root=artifacts_root,
        use_case_id=use_case_id,
        run_id=run_id,
        deployment_status=str(deployment.get("status", "ready")),
        approved_by=actor,
        approved_at_utc=approved_at_utc,
        note=note_text,
        accepted_warning_names=accepted_warning_names,
        warning_rationale=rationale_text,
    )

    return {
        "use_case_id": use_case_id,
        "run_id": run_id,
        "artifacts_root": str(Path(artifacts_root).as_posix()),
        "monitoring_report_path": str(report_path.as_posix()),
        "deployment_readiness": deployment,
        "accepted_warnings": accepted_warning_names,
        "unknown_accepted_warnings": unknown_accepted,
        "force": bool(force),
        "governance_approvals": approvals_meta,
    }


def _resolve_monitoring_report_path(
    *,
    summary: dict[str, Any],
    artifacts_root: Path,
) -> Path:
    """Resolve monitoring report path from run summary artifacts block."""
    artifacts = summary.get("artifacts")
    monitoring_path_text: str | None = None
    if isinstance(artifacts, dict):
        maybe_path = artifacts.get("monitoring_report")
        if isinstance(maybe_path, str) and maybe_path.strip():
            monitoring_path_text = maybe_path

    if monitoring_path_text:
        return _resolve_path(artifacts_root=artifacts_root, path_text=monitoring_path_text)

    summary_path_text = summary.get("summary_path")
    if isinstance(summary_path_text, str) and summary_path_text.strip():
        summary_path = _resolve_path(artifacts_root=artifacts_root, path_text=summary_path_text)
        return summary_path.parent / "monitoring_governance" / "report.json"

    use_case_id = str(summary.get("use_case_id", "")).strip()
    run_id = str(summary.get("run_id", "")).strip()
    if not use_case_id or not run_id:
        raise ValueError("Unable to resolve monitoring report path from summary payload.")
    return Path(artifacts_root) / use_case_id / run_id / "monitoring_governance" / "report.json"


def _resolve_accepted_warnings(
    *,
    warning_checks: list[str],
    accept_warnings: list[str] | None,
    accept_all_warnings: bool,
) -> list[str]:
    """Build deduplicated accepted-warning list from request flags."""
    accepted: set[str] = set()
    for name in accept_warnings or []:
        text = str(name).strip()
        if text:
            accepted.add(text)
    if accept_all_warnings:
        accepted.update(warning_checks)
    return sorted(accepted)


def _normalize_warning_dispositions(raw: Any) -> list[dict[str, Any]]:
    """Normalize warning disposition rows to dictionaries."""
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in raw:
        if isinstance(row, dict):
            rows.append(dict(row))
    return rows


def _upsert_governance_approvals(
    *,
    artifacts_root: Path,
    use_case_id: str,
    run_id: str,
    deployment_status: str,
    approved_by: str,
    approved_at_utc: str,
    note: str,
    accepted_warning_names: list[str],
    warning_rationale: str,
) -> dict[str, Any]:
    """Upsert governance approval and warning decisions in approvals ledger."""
    ledger_path = Path(artifacts_root) / GOVERNANCE_APPROVALS_FILENAME
    payload = _load_approvals_payload(ledger_path=ledger_path)
    payload["artifacts_root"] = str(Path(artifacts_root).as_posix())

    approval_row = {
        "use_case_id": use_case_id,
        "run_id": run_id,
        "deployment_readiness_status": deployment_status,
        "approved_by": approved_by,
        "approved_at_utc": approved_at_utc,
        "method": "manual_signoff",
        "notes": note,
    }

    approvals = payload["approvals"]
    _upsert_keyed_row(
        rows=approvals,
        key_fields=("use_case_id", "run_id"),
        row=approval_row,
    )

    warning_decisions = payload["warning_decisions"]
    for warning_name in accepted_warning_names:
        _upsert_keyed_row(
            rows=warning_decisions,
            key_fields=("use_case_id", "run_id", "name"),
            row={
                "use_case_id": use_case_id,
                "run_id": run_id,
                "name": warning_name,
                "decision": "accepted",
                "severity": "warn",
                "rationale": warning_rationale,
                "decided_by": approved_by,
                "decided_at_utc": approved_at_utc,
            },
        )

    payload["recorded_at_utc"] = approved_at_utc
    _write_json_object(ledger_path, payload)
    return {
        "path": str(ledger_path.as_posix()),
        "approval_count": len(approvals),
        "warning_decision_count": len(warning_decisions),
    }


def _upsert_keyed_row(
    *,
    rows: list[dict[str, Any]],
    key_fields: tuple[str, ...],
    row: dict[str, Any],
) -> None:
    """Insert or replace row keyed by one or more stable fields."""
    key = tuple(str(row.get(field, "")) for field in key_fields)
    for idx, existing in enumerate(rows):
        existing_key = tuple(str(existing.get(field, "")) for field in key_fields)
        if existing_key == key:
            rows[idx] = row
            return
    rows.append(row)


def _load_approvals_payload(ledger_path: Path) -> dict[str, Any]:
    """Load approvals ledger or return default payload schema."""
    payload = _read_json_object(ledger_path)
    if not isinstance(payload, dict):
        return _default_approvals_payload()

    approvals = payload.get("approvals")
    warning_decisions = payload.get("warning_decisions")
    if not isinstance(approvals, list):
        approvals = []
    if not isinstance(warning_decisions, list):
        warning_decisions = []

    return {
        "version": 1,
        "recorded_at_utc": str(payload.get("recorded_at_utc", _utc_now())),
        "artifacts_root": str(payload.get("artifacts_root", "")),
        "approvals": [row for row in approvals if isinstance(row, dict)],
        "warning_decisions": [
            row for row in warning_decisions if isinstance(row, dict)
        ],
    }


def _default_approvals_payload() -> dict[str, Any]:
    """Return default approvals-ledger schema."""
    return {
        "version": 1,
        "recorded_at_utc": _utc_now(),
        "artifacts_root": "",
        "approvals": [],
        "warning_decisions": [],
    }


def _read_json_object(path: Path) -> dict[str, Any] | None:
    """Read JSON object from disk, returning None for invalid payloads."""
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_json_object(path: Path, payload: dict[str, Any]) -> None:
    """Persist JSON object to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _resolve_path(*, artifacts_root: Path, path_text: str) -> Path:
    """Resolve relative paths against artifacts root when possible."""
    path = Path(path_text)
    if path.is_absolute():
        return path
    candidate = Path(artifacts_root) / path
    if candidate.exists():
        return candidate
    return path


def _string_list(value: Any) -> list[str]:
    """Normalize payload value to list[str]."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _actor_name() -> str:
    """Resolve actor name from environment."""
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def _utc_now() -> str:
    """Return UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
