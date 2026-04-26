from __future__ import annotations

"""Stage 8: Monitoring + Governance.

Computes contract-coverage checks and emits a run report with validation gate
statuses. This keeps governance decisions traceable from run artifacts.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipelines.contract_loader import UseCaseContract

VALIDATION_STANDARD_VERSION = "v1"

# Use-case-specific metric validation rules to standardize deployment readiness checks.
USE_CASE_METRIC_RULES: dict[str, list[dict[str, Any]]] = {
    "UC-NBA-RET-001": [
        {"name": "avg_expected_uplift_range", "metric": "avg_expected_uplift", "min": 0.0, "max": 0.5},
        {"name": "avg_confidence_range", "metric": "avg_confidence", "min": 0.5, "max": 1.0},
    ],
    "UC-CHURN-RET-002": [
        {"name": "avg_churn_risk_score_range", "metric": "avg_churn_risk_score", "min": 0.0, "max": 1.0},
        {"name": "avg_expected_uplift_range", "metric": "avg_expected_uplift", "min": 0.0, "max": 0.5},
    ],
    "UC-MMM-PLN-003": [
        {"name": "avg_recommended_spend_positive", "metric": "avg_recommended_spend", "min": 0.0},
        {
            "name": "avg_expected_incremental_revenue_positive",
            "metric": "avg_expected_incremental_revenue",
            "min": 0.0,
        },
    ],
    "UC-INCR-MKT-004": [
        {"name": "avg_incremental_lift_range", "metric": "avg_incremental_lift", "min": -0.2, "max": 0.3},
        {"name": "avg_iROAS_positive", "metric": "avg_iROAS", "min": 0.0},
    ],
}


def run_monitoring_and_governance(
    contract: UseCaseContract,
    model_rows: list[dict[str, Any]],
    model_metrics: dict[str, Any],
    output_dir: Path,
    run_id: str | None = None,
    seed: int | None = None,
    source_data_metadata: dict[str, Any] | None = None,
    failure_injection: dict[str, bool] | None = None,
) -> tuple[dict[str, Any], str]:
    """Evaluate validation standards, governance gates, and deployment readiness."""
    required_fields = set(contract.output_contract.fields)
    valid_rows = sum(1 for row in model_rows if required_fields.issubset(row))
    coverage = valid_rows / max(len(model_rows), 1)

    gates = {
        gate: ("pass" if coverage == 1.0 else "fail")
        for gate in contract.governance.get("validation_gates", [])
    }
    model_validation = _build_model_validation(
        contract=contract,
        model_rows=model_rows,
        model_metrics=model_metrics,
        coverage=coverage,
    )
    data_quality = _build_data_quality_validation(source_data_metadata=source_data_metadata)

    gates_pass = all(result == "pass" for result in gates.values())
    checks_pass = model_validation["summary"]["failed_checks"] == 0
    data_quality_pass = data_quality["gates"]["fail_gate"] == "pass"
    run_status = "pass" if gates_pass and checks_pass and data_quality_pass else "fail"
    deployment_readiness = _build_deployment_readiness(
        gates=gates,
        model_validation=model_validation,
        data_quality=data_quality,
        approval_required=bool(contract.governance.get("approval_required", False)),
    )
    scientific_governance = _build_scientific_governance(
        contract=contract,
        model_rows=model_rows,
        run_id=run_id,
        seed=seed,
    )

    report = {
        "use_case_id": contract.use_case_id,
        "rows_scored": len(model_rows),
        "required_field_coverage": round(coverage, 4),
        "primary_kpi": contract.primary_kpi,
        "model_metrics": model_metrics,
        "validation_gates": gates,
        "run_status": run_status,
        "alert_channels": contract.monitoring.get("alert_channels", []),
        "model_validation": model_validation,
        "data_quality": data_quality,
        "deployment_readiness": deployment_readiness,
        "scientific_governance": scientific_governance,
    }
    _apply_failure_injection(report=report, failure_injection=failure_injection)

    target_dir = output_dir / "monitoring_governance"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "report.json"
    with target_file.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report, str(target_file)


def _build_model_validation(
    contract: UseCaseContract,
    model_rows: list[dict[str, Any]],
    model_metrics: dict[str, Any],
    coverage: float,
) -> dict[str, Any]:
    """Build repeatable model-validation checks with explicit pass/fail semantics."""
    checks: list[dict[str, Any]] = []

    checks.append(
        _boolean_check(
            name="rows_scored_positive",
            passed=len(model_rows) > 0,
            actual=len(model_rows),
            expectation="rows_scored > 0",
        )
    )
    checks.append(
        _boolean_check(
            name="required_field_coverage_full",
            passed=coverage == 1.0,
            actual=round(coverage, 4),
            expectation="required_field_coverage == 1.0",
        )
    )

    for rule in USE_CASE_METRIC_RULES.get(contract.use_case_id, []):
        checks.append(_metric_range_check(model_metrics=model_metrics, rule=rule))

    failed = sum(1 for row in checks if row["status"] != "pass")
    passed = len(checks) - failed
    return {
        "standard_version": VALIDATION_STANDARD_VERSION,
        "checks": checks,
        "summary": {
            "total_checks": len(checks),
            "passed_checks": passed,
            "failed_checks": failed,
            "pass_rate": round(passed / max(len(checks), 1), 4),
        },
    }


def _metric_range_check(model_metrics: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one numeric metric against optional min/max bounds."""
    metric_name = str(rule.get("metric", ""))
    check_name = str(rule.get("name", metric_name or "metric_check"))
    value = _to_float(model_metrics.get(metric_name))
    min_bound = _to_float(rule.get("min"))
    max_bound = _to_float(rule.get("max"))

    if value is None:
        return {
            "name": check_name,
            "status": "fail",
            "actual": None,
            "expectation": _range_text(metric_name=metric_name, min_bound=min_bound, max_bound=max_bound),
            "reason": f"Missing or non-numeric metric: {metric_name}",
        }

    passed = True
    if min_bound is not None and value < min_bound:
        passed = False
    if max_bound is not None and value > max_bound:
        passed = False

    return {
        "name": check_name,
        "status": "pass" if passed else "fail",
        "actual": round(value, 6),
        "expectation": _range_text(metric_name=metric_name, min_bound=min_bound, max_bound=max_bound),
        "reason": "within expected bounds" if passed else "outside expected bounds",
    }


def _boolean_check(name: str, passed: bool, actual: Any, expectation: str) -> dict[str, Any]:
    """Standardize simple boolean check payloads."""
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "actual": actual,
        "expectation": expectation,
        "reason": "ok" if passed else "failed",
    }


def _range_text(metric_name: str, min_bound: float | None, max_bound: float | None) -> str:
    """Build human-readable numeric expectation text."""
    if min_bound is not None and max_bound is not None:
        return f"{metric_name} in [{min_bound}, {max_bound}]"
    if min_bound is not None:
        return f"{metric_name} >= {min_bound}"
    if max_bound is not None:
        return f"{metric_name} <= {max_bound}"
    return f"{metric_name} is numeric"


def _build_data_quality_validation(
    *,
    source_data_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build fail/warn data-quality gate payload from source metadata."""
    if not isinstance(source_data_metadata, dict):
        return {
            "status": "not_available",
            "mode": "unknown",
            "summary": {
                "total_checks": 0,
                "passed_checks": 0,
                "warn_checks": 0,
                "failed_checks": 0,
            },
            "checks": [],
            "table_summaries": {},
            "gates": {
                "fail_gate": "pass",
                "warn_gate": "pass",
            },
            "reason": "Source data metadata unavailable.",
        }

    mode = str(source_data_metadata.get("mode", "unknown")).strip().lower()
    if mode != "real_dataset":
        return {
            "status": "not_applicable",
            "mode": mode,
            "summary": {
                "total_checks": 0,
                "passed_checks": 0,
                "warn_checks": 0,
                "failed_checks": 0,
            },
            "checks": [],
            "table_summaries": {},
            "gates": {
                "fail_gate": "pass",
                "warn_gate": "pass",
            },
            "reason": "Data-quality gates apply to real dataset mode only.",
        }

    data_quality = source_data_metadata.get("data_quality")
    if not isinstance(data_quality, dict):
        return {
            "status": "not_available",
            "mode": mode,
            "summary": {
                "total_checks": 0,
                "passed_checks": 0,
                "warn_checks": 0,
                "failed_checks": 0,
            },
            "checks": [],
            "table_summaries": {},
            "gates": {
                "fail_gate": "pass",
                "warn_gate": "pass",
            },
            "reason": "No data_quality payload found in source metadata.",
        }

    checks = data_quality.get("checks", [])
    if not isinstance(checks, list):
        checks = []
    normalized_checks: list[dict[str, Any]] = []
    for row in checks:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", "pass")).strip().lower()
        if status not in {"pass", "warn", "fail"}:
            status = "pass"
        normalized_checks.append(
            {
                "name": str(row.get("name", "unknown_check")),
                "table": str(row.get("table", "unknown_table")),
                "severity": str(row.get("severity", "fail")).strip().lower(),
                "status": status,
                "expectation": row.get("expectation"),
                "reason": row.get("reason"),
                "evaluated_rows": row.get("evaluated_rows"),
                "violation_count": row.get("violation_count"),
                "sample_values": row.get("sample_values", []),
                "source_path": row.get("source_path"),
            }
        )

    fail_count = sum(1 for row in normalized_checks if row["status"] == "fail")
    warn_count = sum(1 for row in normalized_checks if row["status"] == "warn")
    pass_count = sum(1 for row in normalized_checks if row["status"] == "pass")
    status = "pass"
    if fail_count > 0:
        status = "fail"
    elif warn_count > 0:
        status = "warn"

    return {
        "status": status,
        "mode": mode,
        "summary": {
            "total_checks": len(normalized_checks),
            "passed_checks": pass_count,
            "warn_checks": warn_count,
            "failed_checks": fail_count,
        },
        "checks": normalized_checks,
        "table_summaries": data_quality.get("table_summaries", {}),
        "gates": {
            "fail_gate": "pass" if fail_count == 0 else "fail",
            "warn_gate": "pass" if warn_count == 0 else "warn",
        },
        "reason": None,
    }


def _build_deployment_readiness(
    gates: dict[str, str],
    model_validation: dict[str, Any],
    data_quality: dict[str, Any] | None,
    approval_required: bool,
) -> dict[str, Any]:
    """Compute deployment-readiness score and blockers from checks + governance gates."""
    failed_gates = sorted([gate for gate, status in gates.items() if status != "pass"])
    checks = model_validation.get("checks", [])
    failed_checks = sorted(
        [
            str(row.get("name"))
            for row in checks
            if isinstance(row, dict) and str(row.get("status", "fail")) != "pass"
        ]
    )

    dq_checks = []
    if isinstance(data_quality, dict):
        raw_dq_checks = data_quality.get("checks", [])
        if isinstance(raw_dq_checks, list):
            dq_checks = [row for row in raw_dq_checks if isinstance(row, dict)]
    failed_dq_checks = sorted(
        [
            _dq_check_name(row)
            for row in dq_checks
            if str(row.get("status", "pass")).strip().lower() == "fail"
        ]
    )
    warning_dq_checks = sorted(
        [
            _dq_check_name(row)
            for row in dq_checks
            if str(row.get("status", "pass")).strip().lower() == "warn"
        ]
    )

    blockers = failed_gates + failed_checks + failed_dq_checks
    total = len(gates) + len(checks) + len(dq_checks)
    passed = total - len(blockers)
    readiness_score = round(passed / max(total, 1), 4)

    if blockers:
        readiness_status = "blocked"
    elif approval_required:
        readiness_status = "pending_approval"
    else:
        readiness_status = "ready"

    return {
        "status": readiness_status,
        "score": readiness_score,
        "approval_required": approval_required,
        "blockers": blockers,
        "failed_gates": failed_gates,
        "failed_model_checks": failed_checks,
        "failed_data_quality_checks": failed_dq_checks,
        "warning_data_quality_checks": warning_dq_checks,
    }


def _dq_check_name(row: dict[str, Any]) -> str:
    """Build stable data-quality check name for blocker/warning lists."""
    table = str(row.get("table", "unknown_table")).strip() or "unknown_table"
    name = str(row.get("name", "unknown_check")).strip() or "unknown_check"
    return f"{table}.{name}"


def _build_scientific_governance(
    contract: UseCaseContract,
    model_rows: list[dict[str, Any]],
    run_id: str | None,
    seed: int | None,
) -> dict[str, Any]:
    """Emit reproducibility and scientific governance metadata for each run."""
    model_versions = _collect_model_versions(model_rows)
    return {
        "standard_version": VALIDATION_STANDARD_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "seed": seed,
        "contract_fingerprint_sha256": _contract_fingerprint(contract),
        "model_versions": model_versions,
        "reproducibility": {
            "row_count": len(model_rows),
            "seed_provided": seed is not None,
            "contract_hash_present": True,
        },
    }


def _collect_model_versions(model_rows: list[dict[str, Any]]) -> list[str]:
    """Collect unique model/analysis version identifiers from model output rows."""
    versions = set()
    for row in model_rows:
        if "model_version" in row:
            versions.add(str(row["model_version"]))
        if "analysis_version" in row:
            versions.add(str(row["analysis_version"]))
    return sorted(versions)


def _contract_fingerprint(contract: UseCaseContract) -> str:
    """Create deterministic fingerprint for contract-driven governance tracking."""
    canonical = json.dumps(contract.raw, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _to_float(value: Any) -> float | None:
    """Parse numeric values into floats; return None for non-numeric inputs."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _apply_failure_injection(
    *,
    report: dict[str, Any],
    failure_injection: dict[str, bool] | None,
) -> None:
    """Apply simulation-only failure toggles to governance report."""
    if not isinstance(failure_injection, dict):
        return
    active = [key for key, enabled in sorted(failure_injection.items()) if bool(enabled)]
    if not active:
        return

    report["failure_injection"] = {
        "active": active,
        "note": "Failure injection enabled for simulation.",
    }

    if "dq_fail" in active:
        data_quality = report.setdefault("data_quality", {})
        checks = data_quality.setdefault("checks", [])
        if isinstance(checks, list):
            checks.append(
                {
                    "name": "dq_fail_injected",
                    "table": "injected",
                    "severity": "fail",
                    "status": "fail",
                    "expectation": "simulation_fail_toggle == false",
                    "reason": "Injected data-quality failure for demo flow.",
                }
            )
        _recompute_data_quality_summary(data_quality=data_quality)

    if "schema_fail" in active:
        gates = report.setdefault("validation_gates", {})
        if isinstance(gates, dict):
            gates["schema_contract_injected"] = "fail"
        model_validation = report.setdefault("model_validation", {})
        checks = model_validation.setdefault("checks", [])
        if isinstance(checks, list):
            checks.append(
                {
                    "name": "schema_contract_injected",
                    "status": "fail",
                    "actual": 0.0,
                    "expectation": "required_field_coverage == 1.0",
                    "reason": "Injected schema validation failure for demo flow.",
                }
            )
        report["required_field_coverage"] = 0.0
        _recompute_model_validation_summary(model_validation=model_validation)

    if "backend_unavailable" in active:
        deployment_readiness = report.setdefault("deployment_readiness", {})
        blockers = deployment_readiness.setdefault("blockers", [])
        failed_model_checks = deployment_readiness.setdefault("failed_model_checks", [])
        if isinstance(blockers, list):
            blockers.append("injected.backend_unavailable")
            deployment_readiness["blockers"] = sorted(set(str(item) for item in blockers))
        if isinstance(failed_model_checks, list):
            failed_model_checks.append("injected.backend_unavailable")
            deployment_readiness["failed_model_checks"] = sorted(
                set(str(item) for item in failed_model_checks)
            )
        deployment_readiness["status"] = "blocked"

    report["run_status"] = "fail"


def _recompute_model_validation_summary(*, model_validation: dict[str, Any]) -> None:
    """Recompute model-validation summary after dynamic check mutations."""
    checks = model_validation.get("checks", [])
    if not isinstance(checks, list):
        checks = []
    failed = sum(1 for row in checks if isinstance(row, dict) and str(row.get("status")) != "pass")
    total = len(checks)
    passed = max(total - failed, 0)
    model_validation["summary"] = {
        "total_checks": total,
        "passed_checks": passed,
        "failed_checks": failed,
        "pass_rate": round(passed / max(total, 1), 4),
    }


def _recompute_data_quality_summary(*, data_quality: dict[str, Any]) -> None:
    """Recompute data-quality summary/gates after injected check mutations."""
    checks = data_quality.get("checks", [])
    if not isinstance(checks, list):
        checks = []
    fail_count = sum(
        1 for row in checks if isinstance(row, dict) and str(row.get("status", "")).strip().lower() == "fail"
    )
    warn_count = sum(
        1 for row in checks if isinstance(row, dict) and str(row.get("status", "")).strip().lower() == "warn"
    )
    pass_count = sum(
        1 for row in checks if isinstance(row, dict) and str(row.get("status", "")).strip().lower() == "pass"
    )

    status = "pass"
    if fail_count > 0:
        status = "fail"
    elif warn_count > 0:
        status = "warn"

    data_quality["status"] = status
    data_quality["summary"] = {
        "total_checks": len(checks),
        "passed_checks": pass_count,
        "warn_checks": warn_count,
        "failed_checks": fail_count,
    }
    data_quality["gates"] = {
        "fail_gate": "pass" if fail_count == 0 else "fail",
        "warn_gate": "pass" if warn_count == 0 else "warn",
    }
