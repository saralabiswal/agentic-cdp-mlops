from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipelines.contract_loader import load_contract_by_id
from pipelines.run_use_case import run_all_use_cases, run_use_case

USE_CASE_IDS = [
    "UC-NBA-RET-001",
    "UC-CHURN-RET-002",
    "UC-MMM-PLN-003",
    "UC-INCR-MKT-004",
]


@pytest.mark.parametrize("use_case_id", USE_CASE_IDS)
def test_use_case_run_writes_valid_artifact(use_case_id: str, tmp_path: Path) -> None:
    summary = run_use_case(use_case_id=use_case_id, output_dir=tmp_path, seed=11)
    assert summary["rows_scored"] > 0

    artifact_path = Path(summary["artifact_path"])
    assert artifact_path.exists()

    with artifact_path.open("r", encoding="utf-8") as f:
        artifact = json.load(f)

    contract = load_contract_by_id(use_case_id=use_case_id)
    required = set(contract.output_contract.fields)
    first_row_keys = set(artifact["rows"][0].keys())

    assert required.issubset(first_row_keys)
    assert artifact["metrics"]["primary_kpi"] == contract.primary_kpi


def test_run_all_executes_every_use_case(tmp_path: Path) -> None:
    summaries = run_all_use_cases(output_dir=tmp_path, seed=13)
    assert len(summaries) == 4
    assert {summary["use_case_id"] for summary in summaries} == set(USE_CASE_IDS)

