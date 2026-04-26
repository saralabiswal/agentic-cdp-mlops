from __future__ import annotations

"""Stage 1: Data Sources.

This layer simulates source-system extracts for each use case, returning
source tables that mirror what real connectors would provide (CRM, events,
support, spend, experiment logs, and related entities).
"""

import random
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pipelines.source_dataset_loader import (
    DEFAULT_SOURCE_DATA_ROOT,
    dataset_available_for_use_case,
    load_source_tables_for_use_case,
)
from pipelines.contract_loader import UseCaseContract
from stack.scenario_library import apply_scenario_to_source_tables


def collect_source_data(
    contract: UseCaseContract,
    seed: int = 7,
    sample_size: int = 100,
    source_data_root: Path | None = None,
    require_real_data: bool = False,
    runtime_mode: str = "default",
    scenario_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Build source datasets keyed by table name for the selected use case.

    Returns real dataset tables when configured and available, otherwise falls
    back to synthetic generators unless `require_real_data=True`.
    """
    tables, _ = collect_source_data_with_metadata(
        contract=contract,
        seed=seed,
        sample_size=sample_size,
        source_data_root=source_data_root,
        require_real_data=require_real_data,
        runtime_mode=runtime_mode,
        scenario_id=scenario_id,
    )
    return tables


def collect_source_data_with_metadata(
    contract: UseCaseContract,
    seed: int = 7,
    sample_size: int = 100,
    source_data_root: Path | None = None,
    require_real_data: bool = False,
    runtime_mode: str = "default",
    scenario_id: str | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Build source datasets and return metadata describing source mode."""
    resolved_root = _resolve_source_data_root(source_data_root=source_data_root)
    use_case_id = contract.use_case_id
    normalized_runtime_mode = _normalize_runtime_mode(runtime_mode=runtime_mode)

    if normalized_runtime_mode == "synthetic_only":
        if require_real_data:
            raise ValueError("runtime_mode=synthetic_only cannot be combined with require_real_data=True.")
        synthetic = _collect_synthetic_source_data(
            contract=contract,
            seed=seed,
            sample_size=sample_size,
        )
        synthetic = apply_scenario_to_source_tables(
            use_case_id=use_case_id,
            source_tables=synthetic,
            scenario_id=scenario_id,
        )
        return (
            synthetic,
            {
                "mode": "synthetic_only",
                "runtime_mode": normalized_runtime_mode,
                "use_case_id": use_case_id,
                "source_data_root": str(resolved_root.as_posix()),
                "dataset_dir": str((resolved_root / use_case_id).as_posix()),
                "scenario_id": scenario_id,
                "warning": "Synthetic-only runtime mode enabled; real dataset path skipped.",
            },
        )

    if dataset_available_for_use_case(use_case_id=use_case_id, data_root=resolved_root):
        tables, metadata = load_source_tables_for_use_case(
            use_case_id=use_case_id,
            data_root=resolved_root,
        )
        metadata["runtime_mode"] = normalized_runtime_mode
        metadata["scenario_id"] = scenario_id
        return tables, metadata

    if require_real_data:
        raise FileNotFoundError(
            "Real dataset required but missing for use_case_id="
            f"{use_case_id}. Expected under {resolved_root.as_posix()}/{use_case_id}/"
        )

    synthetic_tables = _collect_synthetic_source_data(
        contract=contract,
        seed=seed,
        sample_size=sample_size,
    )
    synthetic_tables = apply_scenario_to_source_tables(
        use_case_id=use_case_id,
        source_tables=synthetic_tables,
        scenario_id=scenario_id,
    )
    return (
        synthetic_tables,
        {
            "mode": "synthetic_fallback",
            "runtime_mode": normalized_runtime_mode,
            "use_case_id": use_case_id,
            "source_data_root": str(resolved_root.as_posix()),
            "dataset_dir": str((resolved_root / use_case_id).as_posix()),
            "scenario_id": scenario_id,
            "warning": "Real dataset not found; synthetic source generation used.",
        },
    )


def _resolve_source_data_root(source_data_root: Path | None) -> Path:
    """Resolve source data root from function arg, env var, or default."""
    if source_data_root is not None:
        return Path(source_data_root)
    env_root = os.environ.get("CDP_SOURCE_DATA_ROOT")
    if env_root:
        return Path(env_root)
    return DEFAULT_SOURCE_DATA_ROOT


def _normalize_runtime_mode(*, runtime_mode: str) -> str:
    """Normalize runtime mode to supported values."""
    normalized = str(runtime_mode or "default").strip().lower()
    if normalized in {"default", "auto"}:
        return "default"
    if normalized == "synthetic_only":
        return "synthetic_only"
    raise ValueError(f"Unsupported runtime_mode '{runtime_mode}'. Allowed: default, synthetic_only.")


def _collect_synthetic_source_data(
    contract: UseCaseContract,
    seed: int = 7,
    sample_size: int = 100,
) -> dict[str, list[dict[str, Any]]]:
    """Generate synthetic source tables for local/demo execution."""
    if contract.use_case_id == "UC-NBA-RET-001":
        return _collect_nba_sources(seed=seed, sample_size=sample_size)
    if contract.use_case_id == "UC-CHURN-RET-002":
        return _collect_churn_sources(seed=seed, sample_size=sample_size)
    if contract.use_case_id == "UC-MMM-PLN-003":
        return _collect_mmm_sources(seed=seed)
    if contract.use_case_id == "UC-INCR-MKT-004":
        return _collect_incrementality_sources(seed=seed)
    raise ValueError(f"Unsupported use_case_id '{contract.use_case_id}'")


def _collect_nba_sources(seed: int, sample_size: int) -> dict[str, list[dict[str, Any]]]:
    """Generate synthetic customer, behavior, and contact tables for NBA."""
    rng = random.Random(seed)
    now = _synthetic_timestamp(seed=seed)

    crm_customers = []
    behavior_signals = []
    contact_history = []

    for idx in range(sample_size):
        customer_id = f"CUST-{idx:04d}"
        crm_customers.append(
            {
                "customer_id": customer_id,
                "consent_status": True,
                "profile_completeness": round(rng.uniform(0.70, 1.00), 4),
                "no_critical_service_case": True,
                "do_not_contact": False,
            }
        )
        behavior_signals.append(
            {
                "customer_id": customer_id,
                "risk_score": round(rng.uniform(0.10, 0.95), 4),
                "value_score": round(rng.uniform(0.15, 0.90), 4),
                "historical_action_id": rng.choice(
                    [
                        "offer_10pct_discount",
                        "free_shipping_offer",
                        "loyalty_bonus_points",
                        "retargeting_creative_a",
                    ]
                ),
                "observed_uplift": round(rng.uniform(0.0, 0.30), 4),
                "retained_30d": rng.choice([0, 1]),
                "score_ts": now,
            }
        )
        contact_history.append(
            {
                "customer_id": customer_id,
                "last_marketing_contact_hours": rng.randint(24, 240),
                "contacts_last_7d": rng.randint(0, 6),
            }
        )

    return {
        "crm_customers": crm_customers,
        "behavior_signals": behavior_signals,
        "contact_history": contact_history,
    }


def _collect_churn_sources(seed: int, sample_size: int) -> dict[str, list[dict[str, Any]]]:
    """Generate synthetic customer, usage, and support tables for churn."""
    rng = random.Random(seed)
    now = _synthetic_timestamp(seed=seed + 31)

    crm_customers = []
    usage_signals = []
    support_events = []

    for idx in range(sample_size):
        customer_id = f"CUST-{idx:04d}"
        crm_customers.append(
            {
                "customer_id": customer_id,
                "consent_status": True,
                "profile_completeness": round(rng.uniform(0.70, 1.00), 4),
                "no_active_fraud_flag": True,
                "active_retention_journey": False,
                "last_marketing_contact_hours": rng.randint(24, 240),
            }
        )
        usage_signals.append(
            {
                "customer_id": customer_id,
                "recency_norm": round(rng.uniform(0.00, 1.00), 4),
                "engagement_norm": round(rng.uniform(0.00, 1.00), 4),
                "churned_60d": rng.choice([0, 1]),
                "score_ts": now,
            }
        )
        support_events.append(
            {
                "customer_id": customer_id,
                "support_ticket_norm": round(rng.uniform(0.00, 1.00), 4),
            }
        )

    return {
        "crm_customers": crm_customers,
        "usage_signals": usage_signals,
        "support_events": support_events,
    }


def _collect_mmm_sources(seed: int) -> dict[str, list[dict[str, Any]]]:
    """Generate weekly channel spend and response signals for MMM."""
    rng = random.Random(seed)
    channels = ["search", "social", "display", "affiliate", "email"]
    media_spend = []
    for channel in channels:
        impressions = rng.randint(50_000, 300_000)
        clicks = min(impressions, rng.randint(3_000, 25_000))
        media_spend.append(
            {
                "period": "2026-W16",
                "channel": channel,
                "weekly_spend": round(rng.uniform(15_000, 80_000), 2),
                "impressions": impressions,
                "clicks": clicks,
                "promo_index": round(rng.uniform(0.0, 2.0), 4),
                "observed_revenue": round(rng.uniform(40_000, 240_000), 2),
                "seasonality_index": round(rng.uniform(0.8, 1.2), 4),
                "macro_index": round(rng.uniform(0.7, 1.3), 4),
            }
        )
    return {"media_spend": media_spend}


def _collect_incrementality_sources(seed: int) -> dict[str, list[dict[str, Any]]]:
    """Generate treatment/control campaign test logs for incrementality."""
    rng = random.Random(seed)
    campaign_experiments = []
    for idx in range(1, 7):
        treated_customers = rng.randint(20_000, 60_000)
        control_customers = rng.randint(8_000, 20_000)
        base_rate = rng.uniform(0.02, 0.08)
        lift = rng.uniform(-0.005, 0.02)
        treated_rate = max(0.001, base_rate + lift)
        control_rate = max(0.001, base_rate)

        campaign_experiments.append(
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

    return {"campaign_experiments": campaign_experiments}


def _synthetic_timestamp(*, seed: int) -> str:
    """Return deterministic synthetic timestamp for reproducible simulation outputs."""
    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    offset = timedelta(hours=int(seed) % 24, days=int(seed) % 27)
    return (base + offset).isoformat().replace("+00:00", "Z")
