from __future__ import annotations

"""Base model interface for use-case model implementations."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pipelines.contract_loader import UseCaseContract


class UseCaseModel(ABC):
    """Contract that all model modules implement for pipeline interoperability."""

    @abstractmethod
    def run(
        self, records: list[dict[str, Any]], contract: UseCaseContract, seed: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Run model logic and return (rows, metrics)."""

    def run_with_context(
        self,
        records: list[dict[str, Any]],
        contract: UseCaseContract,
        seed: int,
        artifact_dir: Path,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
        """Run model logic with optional artifact outputs.

        By default, delegates to `run` and returns no extra model artifacts.
        Advanced models can override this to persist fitted-model artifacts
        (e.g., TensorFlow SavedModel, Bayesian trace summaries, causal reports).
        """
        del artifact_dir
        rows, metrics = self.run(records=records, contract=contract, seed=seed)
        return rows, metrics, {}
