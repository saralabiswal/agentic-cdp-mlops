from __future__ import annotations

"""Run registry utilities for querying persisted full-stack run summaries."""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_ARTIFACTS_ROOT = Path("artifacts")
INDEX_FILENAME = ".run_registry_index.json"
INDEX_VERSION = 1


def list_run_summaries(
    *,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    use_case_id: str | None = None,
    run_status: str | None = None,
    infra_profile: str | None = None,
    seed: int | None = None,
    query: str | None = None,
    sort: str = "desc",
    limit: int = 50,
    offset: int = 0,
    use_index: bool = True,
) -> dict[str, Any]:
    """List compact run summaries with filtering, sorting, and pagination."""
    root = Path(artifacts_root)
    rows, index_meta = _load_registry_rows(
        artifacts_root=root,
        use_index=use_index,
        force_rebuild=False,
    )

    filtered_rows: list[dict[str, Any]] = []
    for row in rows:
        if not _matches_filters(
            row=row,
            use_case_id=use_case_id,
            run_status=run_status,
            infra_profile=infra_profile,
            seed=seed,
            query=query,
        ):
            continue
        filtered_rows.append(row)

    reverse = sort != "asc"
    filtered_rows.sort(key=_row_sort_key, reverse=reverse)

    safe_offset = max(0, offset)
    safe_limit = max(1, limit)
    total = len(filtered_rows)
    paged = filtered_rows[safe_offset : safe_offset + safe_limit]

    return {
        "runs": paged,
        "total": total,
        "count": len(paged),
        "limit": safe_limit,
        "offset": safe_offset,
        "index": index_meta,
    }


def build_run_registry_index(
    *,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
) -> dict[str, Any]:
    """Build or refresh run-registry index file and return index metadata."""
    rows, index_meta = _load_registry_rows(
        artifacts_root=Path(artifacts_root),
        use_index=True,
        force_rebuild=True,
    )
    return {
        "rows_indexed": len(rows),
        **index_meta,
    }


def prune_run_artifacts(
    *,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
    keep_per_use_case: int = 20,
    max_age_days: int | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    """Apply retention policy for run artifacts with dry-run by default.

    Policy:
    1. Keep the latest `keep_per_use_case` runs per use case.
    2. Optionally prune runs older than `max_age_days`.
    """
    root = Path(artifacts_root)
    if not root.exists():
        return {
            "artifacts_root": str(root.as_posix()),
            "apply": apply,
            "planned_deletions": [],
            "deleted_count": 0,
            "reason": "artifacts_root_missing",
        }

    now_utc = datetime.now(timezone.utc)
    cutoff_ts = None
    if max_age_days is not None:
        cutoff_ts = now_utc.timestamp() - (max(0, int(max_age_days)) * 86400)

    planned: list[dict[str, Any]] = []
    use_case_dirs = _discover_use_case_dirs(root=root, use_case_id=None)
    for use_case_dir in use_case_dirs:
        runs: list[dict[str, Any]] = []
        for run_dir in sorted([path for path in use_case_dir.iterdir() if path.is_dir()]):
            summary_path = run_dir / "summary.json"
            stat = _safe_stat(summary_path if summary_path.exists() else run_dir)
            if stat is None:
                continue
            run_id = run_dir.name
            run_ts = _parse_run_id_timestamp(run_id=run_id)
            run_epoch = (
                run_ts.timestamp()
                if run_ts is not None
                else float(stat.st_mtime)
            )
            runs.append(
                {
                    "use_case_id": use_case_dir.name,
                    "run_id": run_id,
                    "run_dir": run_dir,
                    "run_timestamp_epoch": run_epoch,
                }
            )

        runs.sort(
            key=lambda row: (float(row["run_timestamp_epoch"]), str(row["run_id"])),
            reverse=True,
        )
        keep_count = max(0, int(keep_per_use_case))
        keep_ids = {str(row["run_id"]) for row in runs[:keep_count]}

        for run in runs:
            run_id = str(run["run_id"])
            should_delete = run_id not in keep_ids
            reason = "exceeds_keep_per_use_case"
            if cutoff_ts is not None and float(run["run_timestamp_epoch"]) < cutoff_ts:
                should_delete = True
                reason = "older_than_max_age_days"
            if not should_delete:
                continue
            run_dir = run["run_dir"]
            if not isinstance(run_dir, Path):
                continue
            planned.append(
                {
                    "use_case_id": str(run["use_case_id"]),
                    "run_id": run_id,
                    "run_dir": str(run_dir.as_posix()),
                    "reason": reason,
                }
            )

    deleted_count = 0
    if apply:
        for row in planned:
            run_dir = Path(str(row["run_dir"]))
            if run_dir.exists() and run_dir.is_dir():
                shutil.rmtree(run_dir)
                deleted_count += 1
        # Rebuild index after deletions.
        build_run_registry_index(artifacts_root=root)

    return {
        "artifacts_root": str(root.as_posix()),
        "apply": apply,
        "keep_per_use_case": max(0, int(keep_per_use_case)),
        "max_age_days": max_age_days,
        "planned_deletions": planned,
        "deleted_count": deleted_count,
    }


def get_run_summary(
    *,
    use_case_id: str,
    run_id: str,
    artifacts_root: Path = DEFAULT_ARTIFACTS_ROOT,
) -> dict[str, Any] | None:
    """Load one full run summary by use-case and run ID."""
    summary_path = Path(artifacts_root) / use_case_id / run_id / "summary.json"
    payload = _read_json_object(summary_path)
    if payload is None:
        return None
    payload["summary_path"] = str(summary_path.as_posix())
    return payload


def _discover_use_case_dirs(root: Path, use_case_id: str | None) -> list[Path]:
    """Return use-case directories under artifacts root."""
    if use_case_id:
        target = root / use_case_id
        return [target] if target.exists() and target.is_dir() else []
    return sorted([path for path in root.iterdir() if path.is_dir()])


def _compact_row(payload: dict[str, Any], summary_path: Path) -> dict[str, Any]:
    """Build compact run row used by list query responses."""
    model_metrics = payload.get("model_metrics", {})
    records = payload.get("records", {})
    if not isinstance(model_metrics, dict):
        model_metrics = {}
    if not isinstance(records, dict):
        records = {}

    run_id = str(payload.get("run_id", summary_path.parent.name))
    use_case_id = str(payload.get("use_case_id", summary_path.parent.parent.name))
    monitoring_report = payload.get("monitoring_report", {})
    if not isinstance(monitoring_report, dict):
        monitoring_report = {}
    deployment_readiness = monitoring_report.get("deployment_readiness", {})
    if not isinstance(deployment_readiness, dict):
        deployment_readiness = {}

    primary_kpi_name = model_metrics.get("primary_kpi")
    primary_kpi_value: Any = None
    if isinstance(primary_kpi_name, str) and primary_kpi_name:
        primary_kpi_value = model_metrics.get(primary_kpi_name)

    row = {
        "use_case_id": use_case_id,
        "run_id": run_id,
        "name": payload.get("name"),
        "run_status": str(payload.get("run_status", "unknown")).lower(),
        "infra_profile": str(payload.get("infra_profile", "local")).lower(),
        "seed": payload.get("seed"),
        "primary_kpi": primary_kpi_name,
        "primary_kpi_value": primary_kpi_value,
        "summary_path": str(summary_path.as_posix()),
        "records": {
            "curated_rows": records.get("curated_rows"),
            "feature_rows": records.get("feature_rows"),
            "model_rows": records.get("model_rows"),
            "activation_rows": records.get("activation_rows"),
        },
        "deployment_readiness_status": deployment_readiness.get("status"),
    }
    parsed_ts = _parse_run_id_timestamp(run_id=run_id)
    row["run_timestamp_utc"] = (
        parsed_ts.isoformat().replace("+00:00", "Z")
        if parsed_ts is not None
        else _file_mtime_utc(path=summary_path)
    )
    return row


def _matches_filters(
    *,
    row: dict[str, Any],
    use_case_id: str | None,
    run_status: str | None,
    infra_profile: str | None,
    seed: int | None,
    query: str | None,
) -> bool:
    """Apply list query filters to one row."""
    if use_case_id:
        if str(row.get("use_case_id", "")).strip() != use_case_id:
            return False

    if run_status and run_status != "all":
        if str(row.get("run_status", "")).lower() != run_status:
            return False

    if infra_profile and infra_profile != "all":
        if str(row.get("infra_profile", "")).lower() != infra_profile:
            return False

    if seed is not None:
        row_seed = row.get("seed")
        if row_seed != seed:
            return False

    token = (query or "").strip().lower()
    if token:
        haystack = " ".join(
            [
                str(row.get("use_case_id", "")),
                str(row.get("run_id", "")),
                str(row.get("run_status", "")),
                str(row.get("infra_profile", "")),
                str(row.get("name", "")),
                str(row.get("primary_kpi", "")),
            ]
        ).lower()
        if token not in haystack:
            return False

    return True


def _row_sort_key(row: dict[str, Any]) -> tuple[int, str]:
    """Sort rows by timestamp/run-id deterministically."""
    run_ts = row.get("run_timestamp_utc")
    if isinstance(run_ts, str):
        parsed = _parse_iso_utc(run_ts)
        if parsed is not None:
            return int(parsed.timestamp()), str(row.get("run_id", ""))
    return 0, str(row.get("run_id", ""))


def _read_json_object(path: Path) -> dict[str, Any] | None:
    """Load JSON file as object; return None when not readable/object."""
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _parse_run_id_timestamp(run_id: str) -> datetime | None:
    """Parse canonical run_id format to datetime."""
    try:
        return datetime.strptime(run_id, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_iso_utc(value: str) -> datetime | None:
    """Parse ISO UTC string into datetime."""
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _file_mtime_utc(path: Path) -> str:
    """Fallback timestamp from file modification time in UTC ISO format."""
    ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return ts.isoformat().replace("+00:00", "Z")


def _load_registry_rows(
    *,
    artifacts_root: Path,
    use_index: bool,
    force_rebuild: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load all compact rows, optionally using an auto-refreshed index cache."""
    root = Path(artifacts_root)
    index_path = root / INDEX_FILENAME

    if not root.exists():
        return (
            [],
            {
                "used": False,
                "path": str(index_path.as_posix()),
                "updated": False,
                "entry_count": 0,
                "reason": "artifacts_root_missing",
            },
        )

    summary_paths = _discover_summary_paths(root=root)
    if not use_index:
        rows = _scan_summary_rows(summary_paths=summary_paths)
        return (
            rows,
            {
                "used": False,
                "path": str(index_path.as_posix()),
                "updated": False,
                "entry_count": len(rows),
                "reason": "index_disabled",
            },
        )

    cached_entries = _load_cached_index_entries(index_path=index_path, force_rebuild=force_rebuild)
    cached_map = {row["summary_rel_path"]: row for row in cached_entries}

    rows: list[dict[str, Any]] = []
    next_entries: list[dict[str, Any]] = []
    updated = force_rebuild or (not index_path.exists())

    for summary_path in summary_paths:
        stat = _safe_stat(summary_path)
        if stat is None:
            continue

        rel_path = _summary_rel_path(root=root, path=summary_path)
        mtime_ns = int(stat.st_mtime_ns)
        size = int(stat.st_size)

        cached = cached_map.get(rel_path)
        row: dict[str, Any] | None = None
        if cached is not None:
            cached_mtime = _coerce_int(cached.get("summary_mtime_ns"))
            cached_size = _coerce_int(cached.get("summary_size"))
            cached_row = cached.get("row")
            if (
                cached_mtime == mtime_ns
                and cached_size == size
                and isinstance(cached_row, dict)
            ):
                row = dict(cached_row)

        if row is None:
            payload = _read_json_object(summary_path)
            if payload is None:
                updated = True
                continue
            row = _compact_row(payload=payload, summary_path=summary_path)
            updated = True

        rows.append(row)
        next_entries.append(
            {
                "summary_rel_path": rel_path,
                "summary_mtime_ns": mtime_ns,
                "summary_size": size,
                "row": row,
            }
        )

    if len(cached_entries) != len(next_entries):
        updated = True

    if updated:
        _write_index_file(index_path=index_path, entries=next_entries)

    return (
        rows,
        {
            "used": True,
            "path": str(index_path.as_posix()),
            "updated": updated,
            "entry_count": len(next_entries),
            "version": INDEX_VERSION,
        },
    )


def _load_cached_index_entries(
    *,
    index_path: Path,
    force_rebuild: bool,
) -> list[dict[str, Any]]:
    """Load cached index entries if the file exists and is valid."""
    if force_rebuild:
        return []

    payload = _read_json_object(index_path)
    if payload is None:
        return []
    if _coerce_int(payload.get("version")) != INDEX_VERSION:
        return []

    entries = payload.get("entries")
    if not isinstance(entries, list):
        return []

    valid_entries: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        rel_path = entry.get("summary_rel_path")
        if not isinstance(rel_path, str) or not rel_path:
            continue
        valid_entries.append(entry)
    return valid_entries


def _write_index_file(*, index_path: Path, entries: list[dict[str, Any]]) -> None:
    """Persist index file to artifacts root."""
    payload = {
        "version": INDEX_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "entries": entries,
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _scan_summary_rows(*, summary_paths: list[Path]) -> list[dict[str, Any]]:
    """Read all summary JSON files and convert them to compact rows."""
    rows: list[dict[str, Any]] = []
    for summary_path in summary_paths:
        payload = _read_json_object(summary_path)
        if payload is None:
            continue
        rows.append(_compact_row(payload=payload, summary_path=summary_path))
    return rows


def _discover_summary_paths(*, root: Path) -> list[Path]:
    """Discover all summary files under artifacts root."""
    return sorted([path for path in root.glob("*/*/summary.json") if path.is_file()])


def _summary_rel_path(*, root: Path, path: Path) -> str:
    """Return summary path relative to artifacts root when possible."""
    try:
        return str(path.relative_to(root).as_posix())
    except ValueError:
        return str(path.as_posix())


def _safe_stat(path: Path) -> Any | None:
    """Return path stat or None when not accessible."""
    try:
        return path.stat()
    except OSError:
        return None


def _coerce_int(value: Any) -> int | None:
    """Parse int-like values safely."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None
