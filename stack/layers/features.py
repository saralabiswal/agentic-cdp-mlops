from __future__ import annotations

"""Stage 5: Feature Layer.

Transforms resolved/curated records into model-ready feature rows while
keeping a stable output contract per use case.
"""

import json
from pathlib import Path
from typing import Any


def build_feature_layer(
    use_case_id: str, resolved_rows: list[dict[str, Any]], output_dir: Path
) -> tuple[list[dict[str, Any]], str]:
    """Build and persist feature rows for the selected use case."""
    if use_case_id == "UC-NBA-RET-001":
        features = _nba_features(resolved_rows)
    elif use_case_id == "UC-CHURN-RET-002":
        features = _churn_features(resolved_rows)
    elif use_case_id == "UC-MMM-PLN-003":
        features = _mmm_features(resolved_rows)
    elif use_case_id == "UC-INCR-MKT-004":
        features = _incrementality_features(resolved_rows)
    else:
        raise ValueError(f"Unsupported use_case_id '{use_case_id}'")

    target_dir = output_dir / "features"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "feature_rows.json"
    with target_file.open("w", encoding="utf-8") as f:
        json.dump(features, f, indent=2)

    return features, str(target_file)


def _nba_features(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive NBA features from customer 360 and behavior attributes."""
    feature_rows: list[dict[str, Any]] = []
    for row in rows:
        value_score = (row["value_score"] + row["profile_completeness"]) / 2
        payload = {
            "customer_id": row["unified_customer_id"],
            "risk_score": row["risk_score"],
            "value_score": round(value_score, 4),
            "score_ts": row["score_ts"],
        }
        # Optional supervised labels available in production datasets.
        for optional in ["historical_action_id", "observed_uplift", "retained_30d"]:
            if optional in row:
                payload[optional] = row[optional]
        feature_rows.append(payload)
    return feature_rows


def _churn_features(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map churn-relevant normalized signals into model input shape."""
    feature_rows: list[dict[str, Any]] = []
    for row in rows:
        payload = {
            "customer_id": row["unified_customer_id"],
            "recency_norm": row["recency_norm"],
            "engagement_norm": row["engagement_norm"],
            "support_ticket_norm": row["support_ticket_norm"],
            "score_ts": row["score_ts"],
        }
        if "churned_60d" in row:
            payload["churned_60d"] = row["churned_60d"]
        feature_rows.append(payload)
    return feature_rows


def _mmm_features(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expose channel-level weekly spend/response features for MMM."""
    feature_rows: list[dict[str, Any]] = []
    for row in rows:
        payload = {
            "period": row["period"],
            "channel": row["channel"],
            "weekly_spend": row["weekly_spend"],
            "impressions": row["impressions"],
            "clicks": row["clicks"],
            "promo_index": row["promo_index"],
        }
        for optional in ["observed_revenue", "seasonality_index", "macro_index"]:
            if optional in row:
                payload[optional] = row[optional]
        feature_rows.append(payload)
    return feature_rows


def _incrementality_features(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expose experiment treatment/control aggregates for causal measurement."""
    return [
        {
            "campaign_id": row["campaign_id"],
            "test_window": row["test_window"],
            "treated_customers": row["treated_customers"],
            "control_customers": row["control_customers"],
            "treated_conversions": row["treated_conversions"],
            "control_conversions": row["control_conversions"],
            "aov": row["aov"],
            "campaign_cost": row["campaign_cost"],
        }
        for row in rows
    ]
