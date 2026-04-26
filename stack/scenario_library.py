from __future__ import annotations

"""Scenario presets for deterministic synthetic simulation runs."""

from dataclasses import dataclass
from copy import deepcopy
from typing import Any

FAILURE_INJECTION_KEYS = {"dq_fail", "schema_fail", "backend_unavailable"}


@dataclass(frozen=True)
class ScenarioPreset:
    """Scenario metadata used by runtime and UI explainability flows."""

    scenario_id: str
    use_case_id: str
    title: str
    description: str
    default_seed: int
    failure_injection: tuple[str, ...] = ()


SCENARIO_PRESETS: dict[str, ScenarioPreset] = {
    "nba_high_risk_save": ScenarioPreset(
        scenario_id="nba_high_risk_save",
        use_case_id="UC-NBA-RET-001",
        title="NBA High-Risk Save",
        description=(
            "Pushes risk scores upward and contact pressure upward to explain "
            "retention rescue actioning."
        ),
        default_seed=111,
    ),
    "churn_support_surge": ScenarioPreset(
        scenario_id="churn_support_surge",
        use_case_id="UC-CHURN-RET-002",
        title="Churn Support Surge",
        description=(
            "Simulates rising support burden and engagement decline to show "
            "churn intervention prioritization."
        ),
        default_seed=222,
    ),
    "mmm_budget_rebalance": ScenarioPreset(
        scenario_id="mmm_budget_rebalance",
        use_case_id="UC-MMM-PLN-003",
        title="MMM Budget Rebalance",
        description=(
            "Shifts channel spend mix so technical users can inspect response "
            "changes and optimization recommendations."
        ),
        default_seed=333,
    ),
    "incrementality_negative_lift": ScenarioPreset(
        scenario_id="incrementality_negative_lift",
        use_case_id="UC-INCR-MKT-004",
        title="Incrementality Negative Lift",
        description=(
            "Introduces campaigns with weaker treated conversion outcomes to "
            "demonstrate scale/pause/retest decisions."
        ),
        default_seed=444,
    ),
    "nba_dq_failure_demo": ScenarioPreset(
        scenario_id="nba_dq_failure_demo",
        use_case_id="UC-NBA-RET-001",
        title="NBA DQ Failure Demo",
        description="For governance walkthroughs: injects data-quality gate failure.",
        default_seed=515,
        failure_injection=("dq_fail",),
    ),
}


def list_scenario_presets(*, use_case_id: str | None = None) -> list[dict[str, Any]]:
    """Return scenario preset catalog for API/UI consumption."""
    rows: list[dict[str, Any]] = []
    for preset in sorted(SCENARIO_PRESETS.values(), key=lambda row: row.scenario_id):
        if use_case_id and preset.use_case_id != use_case_id:
            continue
        rows.append(
            {
                "scenario_id": preset.scenario_id,
                "use_case_id": preset.use_case_id,
                "title": preset.title,
                "description": preset.description,
                "default_seed": preset.default_seed,
                "failure_injection": list(preset.failure_injection),
            }
        )
    return rows


def resolve_scenario_preset(
    *,
    scenario_id: str | None,
    use_case_id: str | None = None,
) -> ScenarioPreset | None:
    """Resolve one scenario preset and validate use-case alignment."""
    if not scenario_id:
        return None
    preset = SCENARIO_PRESETS.get(str(scenario_id).strip())
    if preset is None:
        known = ", ".join(sorted(SCENARIO_PRESETS))
        raise ValueError(f"Unknown scenario_id '{scenario_id}'. Known: {known}")
    if use_case_id and preset.use_case_id != use_case_id:
        raise ValueError(
            f"scenario_id '{scenario_id}' is for {preset.use_case_id}, not {use_case_id}."
        )
    return preset


def to_failure_injection_flags(
    *,
    flags: list[str] | tuple[str, ...] | None = None,
    scenario_id: str | None = None,
    use_case_id: str | None = None,
) -> dict[str, bool]:
    """Normalize failure-injection flags from explicit inputs + scenario defaults."""
    normalized: set[str] = set()
    for raw in flags or []:
        text = str(raw).strip().lower()
        if not text:
            continue
        if text not in FAILURE_INJECTION_KEYS:
            known = ", ".join(sorted(FAILURE_INJECTION_KEYS))
            raise ValueError(f"Unknown failure injection '{text}'. Known: {known}")
        normalized.add(text)

    preset = resolve_scenario_preset(scenario_id=scenario_id, use_case_id=use_case_id)
    if preset is not None:
        normalized.update(preset.failure_injection)

    return {key: (key in normalized) for key in sorted(FAILURE_INJECTION_KEYS)}


def apply_scenario_to_source_tables(
    *,
    use_case_id: str,
    source_tables: dict[str, list[dict[str, Any]]],
    scenario_id: str | None,
) -> dict[str, list[dict[str, Any]]]:
    """Apply deterministic scenario transformation over synthetic source tables."""
    if not scenario_id:
        return source_tables
    preset = resolve_scenario_preset(scenario_id=scenario_id, use_case_id=use_case_id)
    if preset is None:
        return source_tables

    tables = deepcopy(source_tables)
    if preset.scenario_id == "nba_high_risk_save":
        return _apply_nba_high_risk_save(tables)
    if preset.scenario_id == "churn_support_surge":
        return _apply_churn_support_surge(tables)
    if preset.scenario_id == "mmm_budget_rebalance":
        return _apply_mmm_budget_rebalance(tables)
    if preset.scenario_id == "incrementality_negative_lift":
        return _apply_incrementality_negative_lift(tables)
    if preset.scenario_id == "nba_dq_failure_demo":
        return _apply_nba_high_risk_save(tables)
    return tables


def _apply_nba_high_risk_save(
    tables: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    behavior = tables.get("behavior_signals", [])
    for idx, row in enumerate(behavior):
        base_risk = float(row.get("risk_score", 0.5) or 0.5)
        row["risk_score"] = round(min(0.99, max(base_risk, 0.7) + ((idx % 5) * 0.03)), 4)
        row["value_score"] = round(max(0.2, float(row.get("value_score", 0.4) or 0.4)), 4)
        row["observed_uplift"] = round(max(0.01, float(row.get("observed_uplift", 0.0) or 0.0)), 4)
    contact = tables.get("contact_history", [])
    for idx, row in enumerate(contact):
        row["contacts_last_7d"] = min(10, int(row.get("contacts_last_7d", 0) or 0) + (idx % 3))
    return tables


def _apply_churn_support_surge(
    tables: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    usage = tables.get("usage_signals", [])
    for idx, row in enumerate(usage):
        recency = float(row.get("recency_norm", 0.5) or 0.5)
        engagement = float(row.get("engagement_norm", 0.5) or 0.5)
        row["recency_norm"] = round(min(1.0, recency + 0.15 + (idx % 4) * 0.02), 4)
        row["engagement_norm"] = round(max(0.01, engagement - 0.12 - (idx % 4) * 0.01), 4)
    support = tables.get("support_events", [])
    for idx, row in enumerate(support):
        ticket = float(row.get("support_ticket_norm", 0.3) or 0.3)
        row["support_ticket_norm"] = round(min(1.0, ticket + 0.35 + (idx % 5) * 0.03), 4)
    return tables


def _apply_mmm_budget_rebalance(
    tables: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    media = tables.get("media_spend", [])
    for row in media:
        channel = str(row.get("channel", "")).strip().lower()
        spend = float(row.get("weekly_spend", 0.0) or 0.0)
        if channel in {"search", "affiliate"}:
            row["weekly_spend"] = round(spend * 1.22, 2)
        elif channel in {"display", "social"}:
            row["weekly_spend"] = round(spend * 0.82, 2)
        row["promo_index"] = round(min(2.5, float(row.get("promo_index", 1.0) or 1.0) + 0.12), 4)
    return tables


def _apply_incrementality_negative_lift(
    tables: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    experiments = tables.get("campaign_experiments", [])
    for idx, row in enumerate(experiments):
        treated = int(row.get("treated_customers", 0) or 0)
        control = int(row.get("control_customers", 0) or 0)
        control_conv = int(row.get("control_conversions", 0) or 0)
        if treated <= 0 or control <= 0:
            continue
        control_rate = control_conv / max(control, 1)
        penalty = 0.005 + (idx % 4) * 0.002
        treated_rate = max(0.001, control_rate - penalty)
        row["treated_conversions"] = int(round(treated * treated_rate))
    return tables
