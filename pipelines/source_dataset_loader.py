from __future__ import annotations

"""Dataset loader for production-style source tables.

This module loads CSV tables for each use case from a filesystem root,
enforces typed required fields, and emits structured data-quality checks
covering null/range/enum/uniqueness/business-rule validation.
"""

import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_DATA_ROOT = Path("data/production")
DATASET_VERSION_SCHEMA = "v1"

# Minimum row-volume guardrails for real-dataset readiness by use case.
# These thresholds are intentionally conservative for local/CI reproducibility.
USE_CASE_MIN_ROW_RULES: dict[str, dict[str, int]] = {
    "UC-NBA-RET-001": {
        "crm_customers": 3,
        "behavior_signals": 3,
        "contact_history": 3,
    },
    "UC-CHURN-RET-002": {
        "crm_customers": 3,
        "usage_signals": 3,
        "support_events": 3,
    },
    "UC-MMM-PLN-003": {
        "media_spend": 5,
    },
    "UC-INCR-MKT-004": {
        "campaign_experiments": 6,
    },
}

USE_CASE_TABLE_SPECS: dict[str, dict[str, dict[str, Any]]] = {
    "UC-NBA-RET-001": {
        "crm_customers": {
            "file": "crm_customers.csv",
            "required": [
                "customer_id",
                "consent_status",
                "profile_completeness",
                "no_critical_service_case",
                "do_not_contact",
            ],
            "int_fields": [],
            "float_fields": ["profile_completeness"],
            "bool_fields": [
                "consent_status",
                "no_critical_service_case",
                "do_not_contact",
            ],
            "unique_key": ["customer_id"],
            "range_checks": {
                "profile_completeness": {"min": 0.0, "max": 1.0, "severity": "fail"},
            },
        },
        "behavior_signals": {
            "file": "behavior_signals.csv",
            "required": ["customer_id", "risk_score", "value_score", "score_ts"],
            "int_fields": ["retained_30d"],
            "float_fields": ["risk_score", "value_score", "observed_uplift"],
            "bool_fields": [],
            "optional": ["historical_action_id", "observed_uplift", "retained_30d"],
            "unique_key": ["customer_id"],
            "range_checks": {
                "risk_score": {"min": 0.0, "max": 1.0, "severity": "fail"},
                "value_score": {"min": 0.0, "max": 1.0, "severity": "fail"},
                "observed_uplift": {"min": 0.0, "max": 1.0, "severity": "warn"},
                "retained_30d": {"min": 0, "max": 1, "severity": "fail"},
            },
            "enum_checks": {
                "historical_action_id": {
                    "allowed": [
                        "offer_10pct_discount",
                        "free_shipping_offer",
                        "loyalty_bonus_points",
                        "retargeting_creative_a",
                    ],
                    "severity": "warn",
                }
            },
        },
        "contact_history": {
            "file": "contact_history.csv",
            "required": [
                "customer_id",
                "last_marketing_contact_hours",
                "contacts_last_7d",
            ],
            "int_fields": ["last_marketing_contact_hours", "contacts_last_7d"],
            "float_fields": [],
            "bool_fields": [],
            "unique_key": ["customer_id"],
            "range_checks": {
                "last_marketing_contact_hours": {"min": 0, "severity": "fail"},
                "contacts_last_7d": {"min": 0, "max": 50, "severity": "fail"},
            },
        },
    },
    "UC-CHURN-RET-002": {
        "crm_customers": {
            "file": "crm_customers.csv",
            "required": [
                "customer_id",
                "consent_status",
                "profile_completeness",
                "no_active_fraud_flag",
                "active_retention_journey",
                "last_marketing_contact_hours",
            ],
            "int_fields": ["last_marketing_contact_hours"],
            "float_fields": ["profile_completeness"],
            "bool_fields": [
                "consent_status",
                "no_active_fraud_flag",
                "active_retention_journey",
            ],
            "unique_key": ["customer_id"],
            "range_checks": {
                "profile_completeness": {"min": 0.0, "max": 1.0, "severity": "fail"},
                "last_marketing_contact_hours": {"min": 0, "severity": "fail"},
            },
        },
        "usage_signals": {
            "file": "usage_signals.csv",
            "required": ["customer_id", "recency_norm", "engagement_norm", "score_ts"],
            "int_fields": ["churned_60d"],
            "float_fields": ["recency_norm", "engagement_norm"],
            "bool_fields": [],
            "optional": ["churned_60d"],
            "unique_key": ["customer_id"],
            "range_checks": {
                "recency_norm": {"min": 0.0, "max": 1.0, "severity": "fail"},
                "engagement_norm": {"min": 0.0, "max": 1.0, "severity": "fail"},
                "churned_60d": {"min": 0, "max": 1, "severity": "fail"},
            },
        },
        "support_events": {
            "file": "support_events.csv",
            "required": ["customer_id", "support_ticket_norm"],
            "int_fields": [],
            "float_fields": ["support_ticket_norm"],
            "bool_fields": [],
            "unique_key": ["customer_id"],
            "range_checks": {
                "support_ticket_norm": {"min": 0.0, "max": 1.0, "severity": "fail"},
            },
        },
    },
    "UC-MMM-PLN-003": {
        "media_spend": {
            "file": "media_spend.csv",
            "required": [
                "period",
                "channel",
                "weekly_spend",
                "impressions",
                "clicks",
                "promo_index",
            ],
            "int_fields": ["impressions", "clicks"],
            "float_fields": [
                "weekly_spend",
                "promo_index",
                "observed_revenue",
                "seasonality_index",
                "macro_index",
            ],
            "bool_fields": [],
            "optional": ["observed_revenue", "seasonality_index", "macro_index"],
            "unique_key": ["period", "channel"],
            "range_checks": {
                "weekly_spend": {"min": 0.0, "severity": "fail"},
                "impressions": {"min": 0, "severity": "fail"},
                "clicks": {"min": 0, "severity": "fail"},
                "promo_index": {"min": 0.0, "max": 3.0, "severity": "warn"},
                "observed_revenue": {"min": 0.0, "severity": "warn"},
                "seasonality_index": {"min": 0.0, "max": 2.0, "severity": "warn"},
                "macro_index": {"min": 0.0, "max": 2.0, "severity": "warn"},
            },
            "enum_checks": {
                "channel": {
                    "allowed": ["search", "social", "display", "affiliate", "email"],
                    "severity": "fail",
                }
            },
            "row_rules": [
                {
                    "name": "clicks_le_impressions",
                    "left": "clicks",
                    "op": "<=",
                    "right": "impressions",
                    "severity": "fail",
                }
            ],
        }
    },
    "UC-INCR-MKT-004": {
        "campaign_experiments": {
            "file": "campaign_experiments.csv",
            "required": [
                "campaign_id",
                "test_window",
                "treated_customers",
                "control_customers",
                "treated_conversions",
                "control_conversions",
                "aov",
                "campaign_cost",
            ],
            "int_fields": [
                "treated_customers",
                "control_customers",
                "treated_conversions",
                "control_conversions",
            ],
            "float_fields": ["aov", "campaign_cost", "pre_period_conversion_rate"],
            "bool_fields": [],
            "optional": ["pre_period_conversion_rate", "audience_tier"],
            "unique_key": ["campaign_id", "test_window"],
            "range_checks": {
                "treated_customers": {"min": 1, "severity": "fail"},
                "control_customers": {"min": 1, "severity": "fail"},
                "treated_conversions": {"min": 0, "severity": "fail"},
                "control_conversions": {"min": 0, "severity": "fail"},
                "aov": {"min": 0.0, "severity": "fail"},
                "campaign_cost": {"min": 0.0, "severity": "fail"},
                "pre_period_conversion_rate": {"min": 0.0, "max": 1.0, "severity": "warn"},
            },
            "enum_checks": {
                "audience_tier": {
                    "allowed": [
                        "tier_1",
                        "tier_2",
                        "tier_3",
                        "tier_4",
                        "high_value",
                        "mid_value",
                        "low_value",
                    ],
                    "severity": "warn",
                }
            },
            "row_rules": [
                {
                    "name": "treated_conversions_le_treated_customers",
                    "left": "treated_conversions",
                    "op": "<=",
                    "right": "treated_customers",
                    "severity": "fail",
                },
                {
                    "name": "control_conversions_le_control_customers",
                    "left": "control_conversions",
                    "op": "<=",
                    "right": "control_customers",
                    "severity": "fail",
                },
            ],
        }
    },
}


def load_source_tables_for_use_case(
    *,
    use_case_id: str,
    data_root: Path = DEFAULT_SOURCE_DATA_ROOT,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Load all required source tables for one use case from CSV files."""
    table_specs = USE_CASE_TABLE_SPECS.get(use_case_id)
    if table_specs is None:
        known = ", ".join(sorted(USE_CASE_TABLE_SPECS))
        raise ValueError(f"Unsupported use_case_id '{use_case_id}'. Known: {known}")

    use_case_dir = Path(data_root) / use_case_id
    tables: dict[str, list[dict[str, Any]]] = {}
    file_map: dict[str, str] = {}
    row_counts: dict[str, int] = {}
    table_summaries: dict[str, dict[str, Any]] = {}
    quality_checks: list[dict[str, Any]] = []

    for table_name, spec in table_specs.items():
        filename = str(spec["file"])
        path = use_case_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Missing dataset file for {use_case_id}:{table_name}: {path.as_posix()}"
            )
        rows = _load_csv_with_spec(path=path, table_name=table_name, spec=spec)
        if not rows:
            raise ValueError(
                f"Dataset table must contain at least one row: {path.as_posix()}"
            )
        table_checks = _evaluate_table_data_quality(
            table_name=table_name,
            rows=rows,
            spec=spec,
            path=path,
        )
        quality_checks.extend(table_checks)
        table_summaries[table_name] = _summarize_quality_checks(table_checks)

        tables[table_name] = rows
        file_map[table_name] = str(path.as_posix())
        row_counts[table_name] = len(rows)

    quality_summary = _summarize_quality_checks(quality_checks)
    data_quality = {
        "status": quality_summary["status"],
        "summary": quality_summary,
        "table_summaries": table_summaries,
        "checks": quality_checks,
    }
    dataset_versioning = _build_dataset_versioning(
        use_case_id=use_case_id,
        file_map=file_map,
        row_counts=row_counts,
    )
    volume_validation = _build_volume_validation(
        use_case_id=use_case_id,
        row_counts=row_counts,
    )
    readiness = _build_real_data_readiness(
        data_quality=data_quality,
        volume_validation=volume_validation,
    )
    metadata = {
        "mode": "real_dataset",
        "use_case_id": use_case_id,
        "source_data_root": str(Path(data_root).as_posix()),
        "dataset_dir": str(use_case_dir.as_posix()),
        "loaded_at_utc": _utc_now(),
        "table_files": file_map,
        "table_row_counts": row_counts,
        "data_quality": data_quality,
        "dataset_versioning": dataset_versioning,
        "volume_validation": volume_validation,
        "readiness": readiness,
    }
    return tables, metadata


def dataset_available_for_use_case(*, use_case_id: str, data_root: Path) -> bool:
    """Return whether all expected CSV files exist for the use case."""
    table_specs = USE_CASE_TABLE_SPECS.get(use_case_id)
    if table_specs is None:
        return False
    use_case_dir = Path(data_root) / use_case_id
    if not use_case_dir.exists():
        return False
    for spec in table_specs.values():
        if not (use_case_dir / str(spec["file"])).exists():
            return False
    return True


def _load_csv_with_spec(
    *,
    path: Path,
    table_name: str,
    spec: dict[str, Any],
) -> list[dict[str, Any]]:
    """Load one CSV table and normalize required typed fields."""
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            _validate_header(table_name=table_name, header=header, spec=spec, path=path)
            rows: list[dict[str, Any]] = []
            for idx, raw_row in enumerate(reader, start=2):
                row = _normalize_row(
                    raw_row=raw_row,
                    table_name=table_name,
                    row_number=idx,
                    spec=spec,
                    path=path,
                )
                rows.append(row)
    except OSError as exc:
        raise OSError(f"Failed reading CSV file {path.as_posix()}: {exc}") from exc
    return rows


def _validate_header(
    *,
    table_name: str,
    header: list[str],
    spec: dict[str, Any],
    path: Path,
) -> None:
    """Validate required columns are present in CSV header."""
    required = {str(col) for col in spec.get("required", [])}
    present = {str(col) for col in header if col}
    missing = sorted(required - present)
    if missing:
        raise ValueError(
            f"CSV header missing required column(s) for {table_name} in "
            f"{path.as_posix()}: {missing}"
        )


def _normalize_row(
    *,
    raw_row: dict[str, str | None],
    table_name: str,
    row_number: int,
    spec: dict[str, Any],
    path: Path,
) -> dict[str, Any]:
    """Normalize one CSV row into typed dictionary fields."""
    normalized: dict[str, Any] = {}
    required = [str(col) for col in spec.get("required", [])]
    optional = [str(col) for col in spec.get("optional", [])]
    int_fields = {str(col) for col in spec.get("int_fields", [])}
    float_fields = {str(col) for col in spec.get("float_fields", [])}
    bool_fields = {str(col) for col in spec.get("bool_fields", [])}
    ordered_columns = required + [col for col in optional if col not in required]

    for column in ordered_columns:
        raw_value = raw_row.get(column)
        text = (raw_value or "").strip()
        if not text:
            if column in required:
                raise ValueError(
                    f"Empty required value for {table_name}.{column} at "
                    f"{path.as_posix()} line {row_number}"
                )
            continue

        if column in int_fields:
            try:
                normalized[column] = int(text)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid int for {table_name}.{column} at {path.as_posix()} "
                    f"line {row_number}: {text}"
                ) from exc
        elif column in float_fields:
            try:
                normalized[column] = float(text)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid float for {table_name}.{column} at {path.as_posix()} "
                    f"line {row_number}: {text}"
                ) from exc
        elif column in bool_fields:
            normalized[column] = _parse_bool(
                value=text,
                table_name=table_name,
                column=column,
                row_number=row_number,
                path=path,
            )
        else:
            normalized[column] = text

    return normalized


def _evaluate_table_data_quality(
    *,
    table_name: str,
    rows: list[dict[str, Any]],
    spec: dict[str, Any],
    path: Path,
) -> list[dict[str, Any]]:
    """Build business-rule quality checks for one normalized table."""
    checks: list[dict[str, Any]] = []
    required = [str(col) for col in spec.get("required", [])]
    for column in required:
        missing_count = sum(
            1 for row in rows if column not in row or row.get(column) in {"", None}
        )
        checks.append(
            _build_quality_check(
                name=f"required_non_null_{column}",
                table_name=table_name,
                expectation=f"{column} is non-null for all rows",
                severity="fail",
                violation_count=missing_count,
                evaluated_rows=len(rows),
                sample_values=[],
            )
        )

    unique_key = spec.get("unique_key", [])
    if isinstance(unique_key, list) and unique_key:
        checks.append(
            _unique_key_check(
                table_name=table_name,
                rows=rows,
                key_fields=[str(field) for field in unique_key],
            )
        )

    range_checks = spec.get("range_checks", {})
    if isinstance(range_checks, dict):
        for field_name, rule in sorted(range_checks.items()):
            if not isinstance(rule, dict):
                continue
            checks.append(
                _range_check(
                    table_name=table_name,
                    rows=rows,
                    field=str(field_name),
                    rule=rule,
                )
            )

    enum_checks = spec.get("enum_checks", {})
    if isinstance(enum_checks, dict):
        for field_name, rule in sorted(enum_checks.items()):
            if not isinstance(rule, dict):
                continue
            checks.append(
                _enum_check(
                    table_name=table_name,
                    rows=rows,
                    field=str(field_name),
                    rule=rule,
                )
            )

    row_rules = spec.get("row_rules", [])
    if isinstance(row_rules, list):
        for rule in row_rules:
            if not isinstance(rule, dict):
                continue
            checks.append(
                _row_rule_check(
                    table_name=table_name,
                    rows=rows,
                    rule=rule,
                )
            )

    # Keep table path visible for traceability in downstream monitoring metadata.
    for check in checks:
        check["source_path"] = str(path.as_posix())
    return checks


def _unique_key_check(
    *,
    table_name: str,
    rows: list[dict[str, Any]],
    key_fields: list[str],
) -> dict[str, Any]:
    """Validate uniqueness of a table key (single or composite)."""
    seen: set[tuple[Any, ...]] = set()
    duplicates: list[str] = []
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        if key in seen:
            duplicates.append("|".join(str(value) for value in key))
        else:
            seen.add(key)
    return _build_quality_check(
        name=f"unique_key_{'_'.join(key_fields)}",
        table_name=table_name,
        expectation="unique key values",
        severity="fail",
        violation_count=len(duplicates),
        evaluated_rows=len(rows),
        sample_values=duplicates[:5],
    )


def _range_check(
    *,
    table_name: str,
    rows: list[dict[str, Any]],
    field: str,
    rule: dict[str, Any],
) -> dict[str, Any]:
    """Validate numeric field values against min/max bounds."""
    min_bound = _to_float(rule.get("min"))
    max_bound = _to_float(rule.get("max"))
    severity = _normalize_severity(rule.get("severity"))

    violations = 0
    evaluated = 0
    samples: list[str] = []

    for row in rows:
        if field not in row:
            continue
        numeric = _to_float(row.get(field))
        evaluated += 1
        if numeric is None:
            violations += 1
            if len(samples) < 5:
                samples.append(str(row.get(field)))
            continue
        if min_bound is not None and numeric < min_bound:
            violations += 1
            if len(samples) < 5:
                samples.append(str(numeric))
            continue
        if max_bound is not None and numeric > max_bound:
            violations += 1
            if len(samples) < 5:
                samples.append(str(numeric))

    expectation = _range_expectation(field=field, min_bound=min_bound, max_bound=max_bound)
    return _build_quality_check(
        name=f"range_{field}",
        table_name=table_name,
        expectation=expectation,
        severity=severity,
        violation_count=violations,
        evaluated_rows=evaluated,
        sample_values=samples,
    )


def _enum_check(
    *,
    table_name: str,
    rows: list[dict[str, Any]],
    field: str,
    rule: dict[str, Any],
) -> dict[str, Any]:
    """Validate enum-like values for one field."""
    raw_allowed = rule.get("allowed", [])
    if not isinstance(raw_allowed, list) or not raw_allowed:
        return _build_quality_check(
            name=f"enum_{field}",
            table_name=table_name,
            expectation=f"{field} has configured enum values",
            severity=_normalize_severity(rule.get("severity")),
            violation_count=0,
            evaluated_rows=0,
            sample_values=[],
        )
    allowed = {str(value).strip().lower() for value in raw_allowed}
    severity = _normalize_severity(rule.get("severity"))

    violations = 0
    evaluated = 0
    samples: list[str] = []
    for row in rows:
        if field not in row:
            continue
        value = str(row.get(field, "")).strip()
        evaluated += 1
        if value.lower() not in allowed:
            violations += 1
            if len(samples) < 5:
                samples.append(value)

    return _build_quality_check(
        name=f"enum_{field}",
        table_name=table_name,
        expectation=f"{field} in {sorted(allowed)}",
        severity=severity,
        violation_count=violations,
        evaluated_rows=evaluated,
        sample_values=samples,
    )


def _row_rule_check(
    *,
    table_name: str,
    rows: list[dict[str, Any]],
    rule: dict[str, Any],
) -> dict[str, Any]:
    """Validate row-level cross-field numeric comparison rule."""
    name = str(rule.get("name", "row_rule")).strip() or "row_rule"
    left = str(rule.get("left", "")).strip()
    right = str(rule.get("right", "")).strip()
    op = str(rule.get("op", "<=")).strip() or "<="
    severity = _normalize_severity(rule.get("severity"))

    violations = 0
    evaluated = 0
    samples: list[str] = []
    for row in rows:
        if left not in row or right not in row:
            continue
        left_value = _to_float(row.get(left))
        right_value = _to_float(row.get(right))
        evaluated += 1
        if left_value is None or right_value is None:
            violations += 1
            if len(samples) < 5:
                samples.append(f"{left}={row.get(left)}, {right}={row.get(right)}")
            continue
        if not _compare(left_value, right_value, op):
            violations += 1
            if len(samples) < 5:
                samples.append(f"{left_value} {op} {right_value}")

    return _build_quality_check(
        name=name,
        table_name=table_name,
        expectation=f"{left} {op} {right}",
        severity=severity,
        violation_count=violations,
        evaluated_rows=evaluated,
        sample_values=samples,
    )


def _build_quality_check(
    *,
    name: str,
    table_name: str,
    expectation: str,
    severity: str,
    violation_count: int,
    evaluated_rows: int,
    sample_values: list[str],
) -> dict[str, Any]:
    """Standardize one data-quality check payload."""
    normalized_severity = _normalize_severity(severity)
    if violation_count <= 0:
        status = "pass"
        reason = "within expected constraints"
    elif normalized_severity == "warn":
        status = "warn"
        reason = "warning threshold breached"
    else:
        status = "fail"
        reason = "blocking threshold breached"
    return {
        "name": name,
        "table": table_name,
        "severity": normalized_severity,
        "status": status,
        "expectation": expectation,
        "evaluated_rows": evaluated_rows,
        "violation_count": int(max(0, violation_count)),
        "sample_values": sample_values,
        "reason": reason,
    }


def _summarize_quality_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize pass/warn/fail totals across data-quality checks."""
    total = len(checks)
    pass_checks = sum(1 for row in checks if str(row.get("status")) == "pass")
    warn_checks = sum(1 for row in checks if str(row.get("status")) == "warn")
    fail_checks = sum(1 for row in checks if str(row.get("status")) == "fail")
    if fail_checks > 0:
        status = "fail"
    elif warn_checks > 0:
        status = "warn"
    else:
        status = "pass"
    return {
        "status": status,
        "total_checks": total,
        "passed_checks": pass_checks,
        "warn_checks": warn_checks,
        "failed_checks": fail_checks,
    }


def _range_expectation(field: str, min_bound: float | None, max_bound: float | None) -> str:
    """Build human-readable bound text for range checks."""
    if min_bound is not None and max_bound is not None:
        return f"{field} in [{min_bound}, {max_bound}]"
    if min_bound is not None:
        return f"{field} >= {min_bound}"
    if max_bound is not None:
        return f"{field} <= {max_bound}"
    return f"{field} is numeric"


def _normalize_severity(value: Any) -> str:
    """Normalize configured check severity to fail|warn."""
    text = str(value).strip().lower()
    if text == "warn":
        return "warn"
    return "fail"


def _compare(left: float, right: float, op: str) -> bool:
    """Compare two numeric values for supported row-rule operators."""
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    return False


def _parse_bool(
    *,
    value: str,
    table_name: str,
    column: str,
    row_number: int,
    path: Path,
) -> bool:
    """Parse bool-like text values from CSV."""
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    raise ValueError(
        f"Invalid bool for {table_name}.{column} at {path.as_posix()} "
        f"line {row_number}: {value}"
    )


def _to_float(value: Any) -> float | None:
    """Parse numeric values into float when possible."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _build_dataset_versioning(
    *,
    use_case_id: str,
    file_map: dict[str, str],
    row_counts: dict[str, int],
) -> dict[str, Any]:
    """Build stable dataset fingerprint + version metadata."""
    table_fingerprints: dict[str, dict[str, Any]] = {}
    tokens: list[str] = []
    for table_name in sorted(file_map):
        path = Path(str(file_map[table_name]))
        sha = _sha256_file(path)
        row_count = int(row_counts.get(table_name, 0))
        table_fingerprints[table_name] = {
            "source_path": str(path.as_posix()),
            "sha256": sha,
            "row_count": row_count,
        }
        tokens.append(f"{table_name}:{sha}:{row_count}")

    fingerprint = hashlib.sha256("||".join(tokens).encode("utf-8")).hexdigest()
    version_prefix = use_case_id.lower().replace("-", "_")
    return {
        "schema_version": DATASET_VERSION_SCHEMA,
        "dataset_fingerprint_sha256": fingerprint,
        "dataset_version_id": f"{version_prefix}_{fingerprint[:12]}",
        "table_fingerprints": table_fingerprints,
    }


def _build_volume_validation(
    *,
    use_case_id: str,
    row_counts: dict[str, int],
) -> dict[str, Any]:
    """Evaluate minimum table row-volume checks for real-data readiness."""
    rules = USE_CASE_MIN_ROW_RULES.get(use_case_id, {})
    checks: list[dict[str, Any]] = []
    for table_name in sorted(rules):
        min_rows = int(rules[table_name])
        actual_rows = int(row_counts.get(table_name, 0))
        passed = actual_rows >= min_rows
        checks.append(
            {
                "name": f"min_rows_{table_name}",
                "table": table_name,
                "status": "pass" if passed else "fail",
                "severity": "fail",
                "expectation": f"rows >= {min_rows}",
                "actual_rows": actual_rows,
                "min_rows": min_rows,
                "reason": "within expected constraints" if passed else "blocking threshold breached",
            }
        )

    summary = _summarize_quality_checks(checks)
    return {
        "status": summary["status"],
        "summary": summary,
        "rules": {"table_min_rows": rules},
        "checks": checks,
    }


def _build_real_data_readiness(
    *,
    data_quality: dict[str, Any],
    volume_validation: dict[str, Any],
) -> dict[str, Any]:
    """Combine data-quality and volume checks into one readiness verdict."""
    blocking_checks: list[str] = []
    warning_checks: list[str] = []

    dq_checks = data_quality.get("checks", [])
    if isinstance(dq_checks, list):
        for row in dq_checks:
            if not isinstance(row, dict):
                continue
            status = str(row.get("status", "pass")).strip().lower()
            name = _quality_check_name(row=row)
            if status == "fail":
                blocking_checks.append(name)
            elif status == "warn":
                warning_checks.append(name)

    volume_checks = volume_validation.get("checks", [])
    if isinstance(volume_checks, list):
        for row in volume_checks:
            if not isinstance(row, dict):
                continue
            if str(row.get("status", "pass")).strip().lower() == "fail":
                blocking_checks.append(_quality_check_name(row=row))

    if blocking_checks:
        status = "fail"
    elif warning_checks:
        status = "warn"
    else:
        status = "pass"

    return {
        "status": status,
        "blocking_checks": sorted(set(blocking_checks)),
        "warning_checks": sorted(set(warning_checks)),
        "components": {
            "data_quality_status": data_quality.get("status"),
            "volume_status": volume_validation.get("status"),
        },
    }


def _quality_check_name(*, row: dict[str, Any]) -> str:
    """Build stable check identifier in `<table>.<name>` format."""
    table = str(row.get("table", "unknown_table")).strip() or "unknown_table"
    name = str(row.get("name", "unknown_check")).strip() or "unknown_check"
    return f"{table}.{name}"


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 hash for one dataset file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _utc_now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
