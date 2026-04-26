from __future__ import annotations

"""Model registry for use-case to implementation binding."""

from models.base import UseCaseModel
from models.churn import ChurnRetentionModel
from models.incrementality import CampaignIncrementalityModel
from models.mmm import MMMPlanningModel
from models.nba import NBARetentionModel

# This map is the extension point for onboarding additional use cases.
USE_CASE_TO_MODEL: dict[str, type[UseCaseModel]] = {
    "UC-NBA-RET-001": NBARetentionModel,
    "UC-CHURN-RET-002": ChurnRetentionModel,
    "UC-MMM-PLN-003": MMMPlanningModel,
    "UC-INCR-MKT-004": CampaignIncrementalityModel,
}


def get_model_for_use_case(use_case_id: str) -> UseCaseModel:
    """Return model instance associated with the contract use_case_id."""
    model_cls = USE_CASE_TO_MODEL.get(use_case_id)
    if model_cls is None:
        known = ", ".join(sorted(USE_CASE_TO_MODEL))
        raise ValueError(f"Unsupported use_case_id '{use_case_id}'. Known: {known}")
    return model_cls()
