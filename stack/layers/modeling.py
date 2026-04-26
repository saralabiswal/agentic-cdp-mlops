from __future__ import annotations

"""Stage 6: Model Layer.

Loads the configured model implementation, executes scoring/training logic
for the current run, validates output schema compliance, and persists
versioned model artifacts.
"""

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import get_model_for_use_case
from pipelines.contract_loader import UseCaseContract

MODEL_ARTIFACT_SCHEMA_VERSION = "1.0"
STRICT_BACKEND_REQUIREMENTS: dict[str, set[str]] = {
    "UC-NBA-RET-001": {"tensorflow"},
    "UC-CHURN-RET-002": {"tensorflow"},
    "UC-MMM-PLN-003": {"pymc_marketing_adapter"},
    "UC-INCR-MKT-004": {"econml_dowhy"},
}
SPLIT_VALIDATION_RULES: dict[str, dict[str, float]] = {
    "UC-NBA-RET-001": {
        "min_train_rows": 80,
        "min_holdout_rows": 10,
        "min_holdout_ratio": 0.05,
        "max_holdout_ratio": 0.35,
    },
    "UC-CHURN-RET-002": {
        "min_train_rows": 80,
        "min_holdout_rows": 10,
        "min_holdout_ratio": 0.05,
        "max_holdout_ratio": 0.35,
    },
    "UC-MMM-PLN-003": {
        "min_train_rows": 30,
        "min_holdout_rows": 8,
        "min_holdout_ratio": 0.05,
        "max_holdout_ratio": 0.4,
    },
    "UC-INCR-MKT-004": {
        "min_train_rows": 10,
        "min_holdout_rows": 2,
        "min_holdout_ratio": 0.05,
        "max_holdout_ratio": 0.45,
    },
}
DEFAULT_SPLIT_VALIDATION_RULES: dict[str, float] = {
    "min_train_rows": 1,
    "min_holdout_rows": 1,
    "min_holdout_ratio": 0.0,
    "max_holdout_ratio": 1.0,
}


def run_model_layer(
    contract: UseCaseContract,
    feature_rows: list[dict[str, Any]],
    output_dir: Path,
    seed: int,
    strict_model_backends: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    """Execute the selected model and persist predictions/metrics/manifest artifacts."""
    model = get_model_for_use_case(contract.use_case_id)
    model_artifact_dir = output_dir / "models"
    rows, raw_metrics, model_runtime_artifacts = model.run_with_context(
        records=feature_rows,
        contract=contract,
        seed=seed,
        artifact_dir=model_artifact_dir,
    )
    _validate_output_schema(rows=rows, required_fields=contract.output_contract.fields)

    split_metrics = _build_split_metrics(
        rows=rows,
        seed=seed,
        use_case_id=contract.use_case_id,
    )
    model_versions = _collect_model_versions(rows=rows)
    resolved_model_version = _resolve_model_version(
        use_case_id=contract.use_case_id,
        model_versions=model_versions,
    )

    # Keep base model metrics intact while adding standard metadata for governance.
    metrics = dict(raw_metrics)
    metrics["model_version"] = resolved_model_version
    metrics["model_versions"] = model_versions
    metrics.update(split_metrics)
    metrics["split_validation"] = _build_split_validation(
        use_case_id=contract.use_case_id,
        split_metrics=split_metrics,
    )
    _enforce_backend_requirements(
        use_case_id=contract.use_case_id,
        model_metrics=metrics,
        strict_model_backends=strict_model_backends,
    )

    model_artifact_dir.mkdir(parents=True, exist_ok=True)
    predictions_file = model_artifact_dir / "predictions.json"
    with predictions_file.open("w", encoding="utf-8") as f:
        json.dump({"metrics": metrics, "rows": rows}, f, indent=2)

    metrics_file = model_artifact_dir / "metrics.json"
    metrics_payload = {
        "artifact_schema_version": MODEL_ARTIFACT_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "use_case_id": contract.use_case_id,
        "primary_kpi": contract.primary_kpi,
        "model_version": resolved_model_version,
        "model_versions": model_versions,
        "model_metrics": metrics,
        "split_metrics": split_metrics,
    }
    with metrics_file.open("w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)

    manifest_file = model_artifact_dir / "manifest.json"
    runtime_artifact_manifest = _build_runtime_artifact_manifest(model_runtime_artifacts)
    manifest_payload = {
        "artifact_schema_version": MODEL_ARTIFACT_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "use_case_id": contract.use_case_id,
        "primary_kpi": contract.primary_kpi,
        "seed": seed,
        "row_count": len(rows),
        "output_contract_fields": contract.output_contract.fields,
        "resolved_model_version": resolved_model_version,
        "model_versions": model_versions,
        "split_metrics": split_metrics,
        "artifacts": {
            "predictions": {
                "path": str(predictions_file.as_posix()),
                "sha256": _sha256_file(predictions_file),
            },
            "metrics": {
                "path": str(metrics_file.as_posix()),
                "sha256": _sha256_file(metrics_file),
            },
            "runtime": runtime_artifact_manifest,
        },
    }
    with manifest_file.open("w", encoding="utf-8") as f:
        json.dump(manifest_payload, f, indent=2)

    return (
        rows,
        metrics,
        {
            "model_predictions": str(predictions_file.as_posix()),
            "model_metrics": str(metrics_file.as_posix()),
            "model_manifest": str(manifest_file.as_posix()),
            **model_runtime_artifacts,
        },
    )


def _validate_output_schema(rows: list[dict[str, Any]], required_fields: list[str]) -> None:
    """Enforce output contract fields so serving/governance stay stable."""
    if not rows:
        raise ValueError("Model layer produced zero rows.")
    for idx, row in enumerate(rows):
        missing = [field for field in required_fields if field not in row]
        if missing:
            raise ValueError(f"Model output row {idx} missing required fields: {missing}")


def _build_split_metrics(
    *,
    rows: list[dict[str, Any]],
    seed: int,
    use_case_id: str,
) -> dict[str, Any]:
    """Build deterministic train/holdout diagnostics for validation readiness."""
    train_scores: list[float] = []
    holdout_scores: list[float] = []
    holdout_indices = _select_holdout_indices(
        rows=rows,
        seed=seed,
        use_case_id=use_case_id,
    )
    holdout_index_set = set(holdout_indices)

    for idx, row in enumerate(rows):
        score = _row_signal_score(row=row)
        if idx in holdout_index_set:
            holdout_scores.append(score)
        else:
            train_scores.append(score)

    train_mean = _mean_or_none(train_scores)
    holdout_mean = _mean_or_none(holdout_scores)
    drift = None
    if train_mean is not None and holdout_mean is not None:
        drift = round(abs(train_mean - holdout_mean), 6)

    total = len(rows)
    holdout_count = len(holdout_scores)
    return {
        "train_row_count": len(train_scores),
        "holdout_row_count": holdout_count,
        "holdout_ratio": round(holdout_count / max(total, 1), 4),
        "train_signal_mean": train_mean,
        "holdout_signal_mean": holdout_mean,
        "signal_drift_abs": drift,
    }


def _row_signal_score(row: dict[str, Any]) -> float:
    """Compute a generic numeric signal from any model row for diagnostics."""
    numeric_values: list[float] = []
    for value in row.values():
        parsed = _to_float(value)
        if parsed is not None:
            numeric_values.append(parsed)
    if not numeric_values:
        return 0.0
    return round(sum(numeric_values) / len(numeric_values), 6)


def _select_holdout_indices(
    *,
    rows: list[dict[str, Any]],
    seed: int,
    use_case_id: str,
) -> list[int]:
    """Pick deterministic holdout indices while honoring split-validation bounds."""
    total = len(rows)
    if total <= 1:
        return []

    rules = _get_split_validation_rules(use_case_id=use_case_id)
    min_train_rows = max(0, int(rules["min_train_rows"]))
    min_holdout_rows = max(0, int(rules["min_holdout_rows"]))
    min_holdout_ratio = max(0.0, float(rules["min_holdout_ratio"]))
    max_holdout_ratio = max(0.0, float(rules["max_holdout_ratio"]))

    ranked = sorted(
        (
            (_split_rank_for_row(row=row, seed=seed, idx=idx), idx)
            for idx, row in enumerate(rows)
        ),
        key=lambda row: (row[0], row[1]),
    )
    ranked_indices = [idx for _, idx in ranked]

    default_holdout_count = sum(
        1
        for idx, row in enumerate(rows)
        if _is_holdout_row(row=row, seed=seed, idx=idx)
    )
    lower_bound = max(
        min_holdout_rows,
        int(math.ceil(min_holdout_ratio * total)),
    )
    upper_bound = min(
        int(math.floor(max_holdout_ratio * total)),
        max(0, total - min_train_rows),
    )

    if lower_bound <= upper_bound:
        target_holdout_count = min(max(default_holdout_count, lower_bound), upper_bound)
    else:
        # Best-effort fallback when strict bounds are infeasible for tiny datasets.
        target_holdout_count = min(default_holdout_count, max(0, total - min_train_rows))
        if target_holdout_count <= 0 and total > 1:
            target_holdout_count = 1

    target_holdout_count = min(max(0, target_holdout_count), total - 1)
    return ranked_indices[:target_holdout_count]


def _split_rank_for_row(row: dict[str, Any], seed: int, idx: int) -> int:
    """Compute deterministic ranking hash used for split assignment."""
    canonical = json.dumps(row, sort_keys=True, separators=(",", ":"))
    token = f"{seed}:{idx}:{canonical}".encode("utf-8")
    return int(hashlib.sha256(token).hexdigest()[:8], 16)


def _is_holdout_row(row: dict[str, Any], seed: int, idx: int) -> bool:
    """Split rows into holdout set via deterministic hash bucketing."""
    bucket = _split_rank_for_row(row=row, seed=seed, idx=idx) % 100
    return bucket < 20


def _collect_model_versions(rows: list[dict[str, Any]]) -> list[str]:
    """Collect stable model/analysis version identifiers from output rows."""
    versions: set[str] = set()
    for row in rows:
        for key in ("model_version", "analysis_version"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                versions.add(value.strip())
    if not versions:
        return ["unknown"]
    return sorted(versions)


def _resolve_model_version(use_case_id: str, model_versions: list[str]) -> str:
    """Resolve one version string for deployment metadata and indexing."""
    if len(model_versions) == 1 and model_versions[0] != "unknown":
        return model_versions[0]

    normalized_id = use_case_id.lower().replace("-", "_")
    if model_versions == ["unknown"]:
        return f"{normalized_id}_heuristic_v1"

    digest = hashlib.sha256("||".join(model_versions).encode("utf-8")).hexdigest()[:10]
    return f"{normalized_id}_ensemble_{digest}"


def _mean_or_none(values: list[float]) -> float | None:
    """Return rounded mean for non-empty lists, else None."""
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _to_float(value: Any) -> float | None:
    """Parse floats from ints/floats/strings."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 hash for file content."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _utc_now() -> str:
    """Return UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_runtime_artifact_manifest(runtime_artifacts: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Build hash metadata for model-specific runtime artifacts."""
    manifest: dict[str, dict[str, Any]] = {}
    for key, path_text in sorted(runtime_artifacts.items()):
        path = Path(path_text)
        artifact_row: dict[str, Any] = {
            "path": path_text,
            "exists": path.exists(),
            "is_dir": path.exists() and path.is_dir(),
        }
        if path.exists() and path.is_file():
            artifact_row["sha256"] = _sha256_file(path)
        manifest[key] = artifact_row
    return manifest


def _build_split_validation(
    *,
    use_case_id: str,
    split_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Build deterministic train/holdout split validation checks."""
    rules = _get_split_validation_rules(use_case_id=use_case_id)
    train_rows = _to_int(split_metrics.get("train_row_count"))
    holdout_rows = _to_int(split_metrics.get("holdout_row_count"))
    holdout_ratio = _to_float(split_metrics.get("holdout_ratio")) or 0.0

    checks = [
        _validation_check(
            name="train_rows_min",
            actual=train_rows,
            expectation=f"train_row_count >= {int(rules['min_train_rows'])}",
            passed=train_rows >= int(rules["min_train_rows"]),
        ),
        _validation_check(
            name="holdout_rows_min",
            actual=holdout_rows,
            expectation=f"holdout_row_count >= {int(rules['min_holdout_rows'])}",
            passed=holdout_rows >= int(rules["min_holdout_rows"]),
        ),
        _validation_check(
            name="holdout_ratio_range",
            actual=round(holdout_ratio, 6),
            expectation=(
                "holdout_ratio in "
                f"[{float(rules['min_holdout_ratio'])}, {float(rules['max_holdout_ratio'])}]"
            ),
            passed=(
                float(rules["min_holdout_ratio"])
                <= holdout_ratio
                <= float(rules["max_holdout_ratio"])
            ),
        ),
    ]
    failed = sum(1 for row in checks if row["status"] != "pass")
    passed = len(checks) - failed
    return {
        "status": "pass" if failed == 0 else "fail",
        "rules": rules,
        "checks": checks,
        "summary": {
            "total_checks": len(checks),
            "passed_checks": passed,
            "failed_checks": failed,
        },
    }


def _validation_check(
    *,
    name: str,
    actual: Any,
    expectation: str,
    passed: bool,
) -> dict[str, Any]:
    """Standardize one split-validation check row."""
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "actual": actual,
        "expectation": expectation,
        "reason": "within expected constraints" if passed else "blocking threshold breached",
    }


def _enforce_backend_requirements(
    *,
    use_case_id: str,
    model_metrics: dict[str, Any],
    strict_model_backends: bool,
) -> None:
    """Validate backend selection when strict mode requires advanced libraries."""
    if not strict_model_backends:
        return

    required_backends = STRICT_BACKEND_REQUIREMENTS.get(use_case_id, set())
    if not required_backends:
        return

    actual_backend = str(model_metrics.get("model_backend", "unknown")).strip()
    if actual_backend in required_backends:
        return

    warnings = model_metrics.get("backend_warnings", [])
    if not isinstance(warnings, list):
        warnings = [str(warnings)]
    warning_text = "; ".join(str(item) for item in warnings) if warnings else "none"
    required_text = ", ".join(sorted(required_backends))
    raise RuntimeError(
        "Strict model backend mode blocked run for "
        f"{use_case_id}: required backend(s)=({required_text}), "
        f"actual backend='{actual_backend}', warnings={warning_text}"
    )


def _get_split_validation_rules(*, use_case_id: str) -> dict[str, float]:
    """Resolve split validation rule bundle for one use case."""
    return SPLIT_VALIDATION_RULES.get(use_case_id, DEFAULT_SPLIT_VALIDATION_RULES)


def _to_int(value: Any) -> int:
    """Parse integer-like values and default to zero when invalid."""
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
