from __future__ import annotations

import json
from pathlib import Path

import pytest

from stack.orchestrator import run_full_stack


@pytest.mark.parametrize(
    ("use_case_id", "expected_backends"),
    [
        ("UC-NBA-RET-001", {"tensorflow", "heuristic_fallback"}),
        ("UC-CHURN-RET-002", {"tensorflow", "heuristic_fallback"}),
        ("UC-MMM-PLN-003", {"pymc_marketing_adapter", "bayesian_surrogate_fallback"}),
        ("UC-INCR-MKT-004", {"econml_dowhy", "heuristic_fallback"}),
    ],
)
def test_model_runtime_backend_metadata_and_artifacts(
    use_case_id: str,
    expected_backends: set[str],
    tmp_path: Path,
) -> None:
    summary = run_full_stack(use_case_id=use_case_id, output_dir=tmp_path, seed=73)

    model_metrics = summary["model_metrics"]
    assert model_metrics["model_backend"] in expected_backends
    assert "model_version" in model_metrics

    artifacts = summary["artifacts"]
    assert Path(artifacts["model_predictions"]).exists()
    assert Path(artifacts["model_metrics"]).exists()
    assert Path(artifacts["model_manifest"]).exists()
    assert Path(artifacts["model_training_report"]).exists()

    manifest_payload = json.loads(Path(artifacts["model_manifest"]).read_text(encoding="utf-8"))
    runtime_artifacts = manifest_payload["artifacts"]["runtime"]
    assert "model_training_report" in runtime_artifacts
    assert runtime_artifacts["model_training_report"]["exists"] is True
