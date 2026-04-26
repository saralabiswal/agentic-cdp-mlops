from __future__ import annotations

"""Project handoff status synchronization helpers."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STATUS_PATH = Path("PROJECT_SCOPE_AND_STATUS.md")
DEFAULT_STRICT_ARTIFACTS_ROOT = Path("artifacts")
AUTO_BLOCK_START = "<!-- status:auto:start -->"
AUTO_BLOCK_END = "<!-- status:auto:end -->"


def sync_project_scope_status(
    *,
    artifacts_root: Path = DEFAULT_STRICT_ARTIFACTS_ROOT,
    status_path: Path = DEFAULT_STATUS_PATH,
) -> dict[str, Any]:
    """Refresh auto-generated live snapshot block in project status markdown."""
    now_utc = _utc_now()
    snapshot_block, meta = _build_live_snapshot_block(artifacts_root=Path(artifacts_root))

    current = ""
    if Path(status_path).exists():
        current = Path(status_path).read_text(encoding="utf-8")
    if not current.strip():
        current = "# Project Scope And Status\n\n"

    updated = _replace_last_updated_line(content=current, now_utc=now_utc)
    updated = _upsert_auto_block(content=updated, block=snapshot_block)

    Path(status_path).write_text(updated, encoding="utf-8")
    return {
        "status_path": str(Path(status_path).as_posix()),
        "artifacts_root": str(Path(artifacts_root).as_posix()),
        "updated_at_utc": now_utc,
        **meta,
    }


def _build_live_snapshot_block(*, artifacts_root: Path) -> tuple[str, dict[str, Any]]:
    """Build auto-generated markdown block from artifacts root."""
    baseline_path = artifacts_root / "baseline_report.json"
    registry_path = artifacts_root / "model_registry" / "registry.json"
    approvals_path = artifacts_root / "governance_approvals.json"

    baseline = _read_json_object(baseline_path) or {}
    registry = _read_json_object(registry_path) or {}
    approvals = _read_json_object(approvals_path) or {}

    runs = baseline.get("runs", [])
    if not isinstance(runs, list):
        runs = []
    registry_entries = registry.get("entries", [])
    if not isinstance(registry_entries, list):
        registry_entries = []
    approvals_rows = approvals.get("approvals", [])
    if not isinstance(approvals_rows, list):
        approvals_rows = []

    stage_by_key: dict[tuple[str, str], str] = {}
    for row in registry_entries:
        if not isinstance(row, dict):
            continue
        use_case_id = str(row.get("use_case_id", "")).strip()
        run_id = str(row.get("run_id", "")).strip()
        stage = str(row.get("stage", "")).strip() or "unknown"
        if use_case_id and run_id:
            stage_by_key[(use_case_id, run_id)] = stage

    approved_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in approvals_rows:
        if not isinstance(row, dict):
            continue
        use_case_id = str(row.get("use_case_id", "")).strip()
        run_id = str(row.get("run_id", "")).strip()
        if use_case_id and run_id:
            approved_by_key[(use_case_id, run_id)] = row

    table_rows: list[str] = []
    for row in runs:
        if not isinstance(row, dict):
            continue
        use_case_id = str(row.get("use_case_id", "")).strip() or "n/a"
        run_id = str(row.get("run_id", "")).strip() or "n/a"
        run_status = str(row.get("run_status", "unknown")).strip()
        dq_status = str(row.get("data_quality_status", "unknown")).strip()
        deploy_status = str(row.get("deployment_readiness_status", "unknown")).strip()
        backend = str(row.get("model_backend", "unknown")).strip()
        stage = stage_by_key.get((use_case_id, run_id), "unknown")
        approval = approved_by_key.get((use_case_id, run_id), {})
        approved_by = str(approval.get("approved_by", "")).strip() or "-"
        approved_at = str(approval.get("approved_at_utc", "")).strip() or "-"

        table_rows.append(
            "| "
            + " | ".join(
                [
                    use_case_id,
                    run_id,
                    run_status,
                    dq_status,
                    deploy_status,
                    stage,
                    backend,
                    approved_by,
                    approved_at,
                ]
            )
            + " |"
        )

    baseline_generated = str(baseline.get("generated_at_utc", "n/a"))
    totals = baseline.get("totals", {})
    if not isinstance(totals, dict):
        totals = {}
    latest_pass = totals.get("latest_pass_count", 0)
    latest_fail = totals.get("latest_fail_count", 0)

    lines = [
        AUTO_BLOCK_START,
        "## 0) Live Snapshot (Auto-Generated)",
        "",
        f"- Synced at (UTC): `{_utc_now()}`",
        f"- Artifacts root: `{artifacts_root.as_posix()}`",
        f"- Baseline generated_at_utc: `{baseline_generated}`",
        f"- Latest runs: pass=`{latest_pass}` fail=`{latest_fail}`",
        "",
        "| Use Case | Run ID | Run Status | DQ | Deployment | Registry Stage | Backend | Approved By | Approved At (UTC) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if table_rows:
        lines.extend(table_rows)
    else:
        lines.append("| n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |")
    lines.extend(
        [
            "",
            "_This section is auto-managed by `pipelines.cli sync-project-status`._",
            AUTO_BLOCK_END,
        ]
    )
    block = "\n".join(lines)
    return block, {
        "baseline_path": str(baseline_path.as_posix()),
        "registry_path": str(registry_path.as_posix()),
        "approvals_path": str(approvals_path.as_posix()),
        "run_count": len(table_rows),
    }


def _replace_last_updated_line(*, content: str, now_utc: str) -> str:
    """Replace existing last-updated line or inject one near top."""
    lines = content.splitlines()
    replaced = False
    for idx, line in enumerate(lines):
        if line.startswith("Last updated (UTC):"):
            lines[idx] = f"Last updated (UTC): {now_utc}"
            replaced = True
            break
    if not replaced:
        insert_idx = 1 if lines and lines[0].startswith("# ") else 0
        lines.insert(insert_idx, f"Last updated (UTC): {now_utc}")
        if insert_idx + 1 < len(lines) and lines[insert_idx + 1].strip():
            lines.insert(insert_idx + 1, "")
    return "\n".join(lines).rstrip() + "\n"


def _upsert_auto_block(*, content: str, block: str) -> str:
    """Insert or replace auto-generated status block delimited by markers."""
    start_idx = content.find(AUTO_BLOCK_START)
    end_idx = content.find(AUTO_BLOCK_END)
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        end_idx = end_idx + len(AUTO_BLOCK_END)
        updated = content[:start_idx] + block + content[end_idx:]
        return updated.rstrip() + "\n"

    lines = content.splitlines()
    insert_at = 0
    for idx, line in enumerate(lines):
        if line.startswith("# "):
            insert_at = idx + 1
            break
    prefix = "\n".join(lines[:insert_at]).rstrip()
    suffix = "\n".join(lines[insert_at:]).lstrip()
    parts = [prefix, "", block]
    if suffix:
        parts.extend(["", suffix])
    return "\n".join(parts).rstrip() + "\n"


def _read_json_object(path: Path) -> dict[str, Any] | None:
    """Read JSON object from path."""
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _utc_now() -> str:
    """Return UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
