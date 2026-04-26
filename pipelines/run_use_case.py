from __future__ import annotations

"""Model-only pipeline runner.

This path executes contract loading + synthetic data + model scoring without
running the full multi-layer architecture stack. It is kept for fast unit runs.
"""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import get_model_for_use_case
from pipelines.contract_loader import (
    DEFAULT_CONFIG_DIR,
    list_config_paths,
    load_contract,
    load_contract_by_id,
)
from pipelines.data_factory import build_synthetic_input

DEFAULT_OUTPUT_DIR = Path("artifacts")


def run_use_case(
    use_case_id: str,
    config_dir: Path = DEFAULT_CONFIG_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    seed: int = 7,
) -> dict[str, Any]:
    """Run one use case through the compact model pipeline and write artifact JSON."""
    contract = load_contract_by_id(use_case_id=use_case_id, config_dir=config_dir)
    records = build_synthetic_input(contract=contract, seed=seed)

    model = get_model_for_use_case(contract.use_case_id)
    rows, metrics = model.run(records=records, contract=contract, seed=seed)
    _validate_output_schema(rows=rows, required_fields=contract.output_contract.fields)

    artifact_path = _write_artifact(
        use_case_id=use_case_id,
        output_dir=output_dir,
        payload={
            "run_ts": datetime.now(timezone.utc).isoformat(),
            "seed": seed,
            "contract": asdict(contract),
            "metrics": metrics,
            "rows": rows,
        },
    )

    return {
        "use_case_id": use_case_id,
        "name": contract.name,
        "rows_scored": len(rows),
        "metrics": metrics,
        "artifact_path": str(artifact_path),
    }


def run_all_use_cases(
    config_dir: Path = DEFAULT_CONFIG_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    seed: int = 7,
) -> list[dict[str, Any]]:
    """Run model-only pipeline for all configured use cases."""
    summaries: list[dict[str, Any]] = []
    for path in list_config_paths(config_dir):
        contract = load_contract(path)
        summaries.append(
            run_use_case(
                use_case_id=contract.use_case_id,
                config_dir=config_dir,
                output_dir=output_dir,
                seed=seed,
            )
        )
    return summaries


def _write_artifact(use_case_id: str, output_dir: Path, payload: dict[str, Any]) -> Path:
    """Persist model-only run payload under a timestamped artifact path."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target_dir = output_dir / use_case_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"run_{ts}.json"
    with target_file.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return target_file


def _validate_output_schema(rows: list[dict[str, Any]], required_fields: list[str]) -> None:
    """Guardrail to ensure model outputs respect the contract schema."""
    if not rows:
        raise ValueError("Model produced zero rows")
    for idx, row in enumerate(rows):
        missing = [field for field in required_fields if field not in row]
        if missing:
            raise ValueError(f"Row {idx} missing required output fields: {missing}")
