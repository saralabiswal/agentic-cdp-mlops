from __future__ import annotations

"""Synthetic data factory used by the model-only pipeline runner."""

import random
from datetime import datetime, timezone
from typing import Any

from pipelines.contract_loader import UseCaseContract


def build_synthetic_input(
    contract: UseCaseContract, seed: int = 7, sample_size: int = 100
) -> list[dict[str, Any]]:
    """Return use-case specific synthetic records for fast local runs/tests."""
    if contract.use_case_id == "UC-NBA-RET-001":
        return _nba_records(seed=seed, sample_size=sample_size)
    if contract.use_case_id == "UC-CHURN-RET-002":
        return _churn_records(seed=seed, sample_size=sample_size)
    if contract.use_case_id == "UC-MMM-PLN-003":
        return _mmm_records(seed=seed)
    if contract.use_case_id == "UC-INCR-MKT-004":
        return _incrementality_records(seed=seed)
    raise ValueError(f"No synthetic input generator for '{contract.use_case_id}'")


def _nba_records(seed: int, sample_size: int) -> list[dict[str, Any]]:
    """Synthetic customer records for NBA model input."""
    rng = random.Random(seed)
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for idx in range(sample_size):
        rows.append(
            {
                "customer_id": f"CUST-{idx:04d}",
                "risk_score": round(rng.uniform(0.10, 0.95), 4),
                "value_score": round(rng.uniform(0.15, 0.90), 4),
                "score_ts": now,
            }
        )
    return rows


def _churn_records(seed: int, sample_size: int) -> list[dict[str, Any]]:
    """Synthetic customer records for churn model input."""
    rng = random.Random(seed)
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for idx in range(sample_size):
        rows.append(
            {
                "customer_id": f"CUST-{idx:04d}",
                "recency_norm": round(rng.uniform(0.0, 1.0), 4),
                "engagement_norm": round(rng.uniform(0.0, 1.0), 4),
                "support_ticket_norm": round(rng.uniform(0.0, 1.0), 4),
                "score_ts": now,
            }
        )
    return rows


def _mmm_records(seed: int) -> list[dict[str, Any]]:
    """Synthetic channel records for MMM model input."""
    rng = random.Random(seed)
    channels = ["search", "social", "display", "affiliate", "email"]
    rows: list[dict[str, Any]] = []
    for channel in channels:
        impressions = rng.randint(50_000, 300_000)
        clicks = rng.randint(3_000, 25_000)
        rows.append(
            {
                "period": "2026-W16",
                "channel": channel,
                "weekly_spend": round(rng.uniform(15_000, 80_000), 2),
                "impressions": impressions,
                "clicks": min(clicks, impressions),
                "promo_index": round(rng.uniform(0.0, 2.0), 4),
            }
        )
    return rows


def _incrementality_records(seed: int) -> list[dict[str, Any]]:
    """Synthetic treatment/control records for incrementality model input."""
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    for idx in range(1, 7):
        treated_customers = rng.randint(20_000, 60_000)
        control_customers = rng.randint(8_000, 20_000)
        base_rate = rng.uniform(0.02, 0.08)
        lift = rng.uniform(-0.005, 0.02)
        treated_rate = max(0.001, base_rate + lift)
        control_rate = max(0.001, base_rate)

        rows.append(
            {
                "campaign_id": f"CMP-{idx:03d}",
                "test_window": "2026-03-01_to_2026-04-12",
                "treated_customers": treated_customers,
                "control_customers": control_customers,
                "treated_conversions": int(treated_customers * treated_rate),
                "control_conversions": int(control_customers * control_rate),
                "aov": round(rng.uniform(50, 180), 2),
                "campaign_cost": round(rng.uniform(10_000, 40_000), 2),
            }
        )
    return rows
