from __future__ import annotations

"""Stage 7: Serving + Activation.

Converts model outputs into downstream-ready payloads. This intentionally keeps
payload mapping logic explicit so connector adapters can be replaced later
without changing model contracts.
"""

import json
from pathlib import Path
from typing import Any

from pipelines.contract_loader import UseCaseContract

ACTIVATION_CONTRACT_FIELDS: dict[str, list[str]] = {
    "UC-NBA-RET-001": [
        "destination",
        "customer_id",
        "action_id",
        "action_channel",
        "priority",
        "reason_code",
    ],
    "UC-CHURN-RET-002": [
        "destination",
        "customer_id",
        "recommended_action",
        "risk_band",
        "priority",
    ],
    "UC-MMM-PLN-003": [
        "destination",
        "channel",
        "recommended_spend",
        "expected_incremental_revenue",
        "uncertainty_interval",
    ],
    "UC-INCR-MKT-004": [
        "destination",
        "campaign_id",
        "decision_recommendation",
        "incremental_lift",
        "iROAS",
    ],
}


def run_serving_and_activation(
    contract: UseCaseContract, model_rows: list[dict[str, Any]], output_dir: Path
) -> tuple[list[dict[str, Any]], str]:
    """Transform model rows into activation payloads and persist them."""
    payloads = build_activation_payloads(
        use_case_id=contract.use_case_id,
        model_rows=model_rows,
    )

    target_dir = output_dir / "serving_activation"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / "activation_payloads.json"
    with target_file.open("w", encoding="utf-8") as f:
        json.dump(payloads, f, indent=2)

    return payloads, str(target_file)


def build_activation_payloads(
    *,
    use_case_id: str,
    model_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build activation payload rows without writing artifacts to disk."""
    if use_case_id == "UC-NBA-RET-001":
        return _nba_payloads(model_rows)
    if use_case_id == "UC-CHURN-RET-002":
        return _churn_payloads(model_rows)
    if use_case_id == "UC-MMM-PLN-003":
        return _mmm_payloads(model_rows)
    if use_case_id == "UC-INCR-MKT-004":
        return _incrementality_payloads(model_rows)
    raise ValueError(f"Unsupported use_case_id '{use_case_id}'")


def get_activation_contract_fields(use_case_id: str) -> list[str]:
    """Return stable activation payload contract fields for one use case."""
    fields = ACTIVATION_CONTRACT_FIELDS.get(use_case_id)
    if fields is None:
        known = ", ".join(sorted(ACTIVATION_CONTRACT_FIELDS))
        raise ValueError(f"Unsupported use_case_id '{use_case_id}'. Known: {known}")
    return list(fields)


def _nba_payloads(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build customer-level NBA actions for campaign orchestration."""
    return [
        {
            "destination": "campaign_orchestrator",
            "customer_id": row["customer_id"],
            "action_id": row["action_id"],
            "action_channel": row["action_channel"],
            "priority": "high" if row["expected_uplift"] >= 0.2 else "normal",
            "reason_code": row["reason_codes"][0],
        }
        for row in rows
    ]


def _churn_payloads(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build retention-journey payloads from churn scoring output."""
    return [
        {
            "destination": "retention_journey",
            "customer_id": row["customer_id"],
            "recommended_action": row["recommended_action"],
            "risk_band": row["risk_band"],
            "priority": "high" if row["risk_band"] == "high" else "normal",
        }
        for row in rows
    ]


def _mmm_payloads(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build channel budget recommendations for planning APIs."""
    return [
        {
            "destination": "budget_planning_api",
            "channel": row["channel"],
            "recommended_spend": row["recommended_spend"],
            "expected_incremental_revenue": row["expected_incremental_revenue"],
            "uncertainty_interval": row["uncertainty_interval"],
        }
        for row in rows
    ]


def _incrementality_payloads(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build campaign scale/pause/retest recommendations from causal output."""
    return [
        {
            "destination": "campaign_decisioning",
            "campaign_id": row["campaign_id"],
            "decision_recommendation": row["decision_recommendation"],
            "incremental_lift": row["incremental_lift"],
            "iROAS": row["iROAS"],
        }
        for row in rows
    ]
