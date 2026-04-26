from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pipelines.contract_loader import load_contract_by_id
from stack.layers import modeling


class _DummyNBAModelFallback:
    def run_with_context(
        self,
        records: list[dict[str, Any]],
        contract: Any,
        seed: int,
        artifact_dir: Path,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
        del records, seed, artifact_dir
        return (
            [
                {
                    "customer_id": "U-CUST-001",
                    "action_id": "offer_10pct_discount",
                    "action_channel": "email",
                    "expected_uplift": 0.2,
                    "confidence": 0.8,
                    "reason_codes": ["high_churn_risk"],
                    "score_ts": "2026-04-22T18:00:00Z",
                    "model_version": "nba_retention_heuristic_v1",
                    "policy_version": "policy_v1",
                }
            ],
            {
                "primary_kpi": contract.primary_kpi,
                "model_backend": "heuristic_fallback",
                "backend_warnings": ["TensorFlow unavailable"],
            },
            {},
        )


class _DummyNBAModelTensorFlow:
    def run_with_context(
        self,
        records: list[dict[str, Any]],
        contract: Any,
        seed: int,
        artifact_dir: Path,
    ) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
        del records, seed, artifact_dir
        return (
            [
                {
                    "customer_id": "U-CUST-001",
                    "action_id": "offer_10pct_discount",
                    "action_channel": "email",
                    "expected_uplift": 0.21,
                    "confidence": 0.84,
                    "reason_codes": ["high_churn_risk"],
                    "score_ts": "2026-04-22T18:00:00Z",
                    "model_version": "nba_retention_tf_v1",
                    "policy_version": "policy_tf_v2",
                }
            ],
            {
                "primary_kpi": contract.primary_kpi,
                "model_backend": "tensorflow",
            },
            {},
        )


def test_run_model_layer_strict_backend_mode_blocks_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contract = load_contract_by_id("UC-NBA-RET-001")
    monkeypatch.setattr(modeling, "get_model_for_use_case", lambda _: _DummyNBAModelFallback())

    with pytest.raises(RuntimeError, match="Strict model backend mode blocked run"):
        modeling.run_model_layer(
            contract=contract,
            feature_rows=[{"customer_id": "U-CUST-001"}],
            output_dir=tmp_path,
            seed=7,
            strict_model_backends=True,
        )


def test_run_model_layer_non_strict_allows_fallback_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contract = load_contract_by_id("UC-NBA-RET-001")
    monkeypatch.setattr(modeling, "get_model_for_use_case", lambda _: _DummyNBAModelFallback())

    _, metrics, artifacts = modeling.run_model_layer(
        contract=contract,
        feature_rows=[{"customer_id": "U-CUST-001"}],
        output_dir=tmp_path,
        seed=7,
        strict_model_backends=False,
    )

    assert metrics["model_backend"] == "heuristic_fallback"
    assert Path(artifacts["model_predictions"]).exists()


def test_run_model_layer_strict_backend_mode_accepts_required_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    contract = load_contract_by_id("UC-NBA-RET-001")
    monkeypatch.setattr(modeling, "get_model_for_use_case", lambda _: _DummyNBAModelTensorFlow())

    _, metrics, artifacts = modeling.run_model_layer(
        contract=contract,
        feature_rows=[{"customer_id": "U-CUST-001"}],
        output_dir=tmp_path,
        seed=7,
        strict_model_backends=True,
    )

    assert metrics["model_backend"] == "tensorflow"
    assert Path(artifacts["model_manifest"]).exists()
