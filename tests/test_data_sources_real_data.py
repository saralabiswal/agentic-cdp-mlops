from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pipelines.contract_loader import load_contract_by_id
from stack.layers.data_sources import collect_source_data_with_metadata
from stack.orchestrator import run_full_stack


def test_collect_source_data_with_real_dataset_and_metadata(tmp_path: Path) -> None:
    _write_nba_dataset(tmp_path)
    contract = load_contract_by_id("UC-NBA-RET-001")

    tables, metadata = collect_source_data_with_metadata(
        contract=contract,
        source_data_root=tmp_path,
        require_real_data=True,
    )

    assert metadata["mode"] == "real_dataset"
    assert tables["crm_customers"][0]["customer_id"] == "CUST-0001"
    assert tables["behavior_signals"][0]["observed_uplift"] == 0.22


def test_collect_source_data_require_real_data_raises_when_missing(tmp_path: Path) -> None:
    contract = load_contract_by_id("UC-NBA-RET-001")
    with pytest.raises(FileNotFoundError, match="Real dataset required"):
        collect_source_data_with_metadata(
            contract=contract,
            source_data_root=tmp_path,
            require_real_data=True,
        )


def test_collect_source_data_falls_back_to_synthetic_when_allowed(tmp_path: Path) -> None:
    contract = load_contract_by_id("UC-NBA-RET-001")
    tables, metadata = collect_source_data_with_metadata(
        contract=contract,
        source_data_root=tmp_path,
        require_real_data=False,
    )
    assert metadata["mode"] == "synthetic_fallback"
    assert "warning" in metadata
    assert tables["crm_customers"]


def test_collect_source_data_real_dataset_under_min_volume_marks_readiness_fail(
    tmp_path: Path,
) -> None:
    _write_nba_dataset(tmp_path, row_count=2)
    contract = load_contract_by_id("UC-NBA-RET-001")

    _, metadata = collect_source_data_with_metadata(
        contract=contract,
        source_data_root=tmp_path,
        require_real_data=True,
    )
    assert metadata["mode"] == "real_dataset"
    assert metadata["volume_validation"]["status"] == "fail"
    assert metadata["readiness"]["status"] == "fail"
    assert "behavior_signals.min_rows_behavior_signals" in metadata["readiness"]["blocking_checks"]


def test_run_full_stack_uses_real_data_in_summary(tmp_path: Path) -> None:
    data_root = tmp_path / "datasets"
    _write_nba_dataset(data_root, row_count=3)

    summary = run_full_stack(
        use_case_id="UC-NBA-RET-001",
        output_dir=tmp_path / "artifacts",
        source_data_root=data_root,
        require_real_data=True,
        seed=19,
    )
    assert summary["source_data"]["mode"] == "real_dataset"
    assert summary["records"]["source_tables"]["crm_customers"] == 3


def test_run_full_stack_require_real_data_blocks_under_min_volume(tmp_path: Path) -> None:
    data_root = tmp_path / "datasets"
    _write_nba_dataset(data_root, row_count=2)

    with pytest.raises(RuntimeError, match="Real-data readiness gate failed"):
        run_full_stack(
            use_case_id="UC-NBA-RET-001",
            output_dir=tmp_path / "artifacts",
            source_data_root=data_root,
            require_real_data=True,
            seed=19,
        )


def _write_nba_dataset(root: Path, row_count: int = 3) -> None:
    use_case_root = root / "UC-NBA-RET-001"
    crm_rows = [
        ["CUST-0001", "true", "0.95", "true", "false"],
        ["CUST-0002", "true", "0.90", "true", "false"],
        ["CUST-0003", "true", "0.87", "true", "false"],
    ][:row_count]
    behavior_rows = [
        [
            "CUST-0001",
            "0.70",
            "0.80",
            "2026-04-22T01:00:00Z",
            "offer_10pct_discount",
            "0.22",
            "1",
        ],
        [
            "CUST-0002",
            "0.40",
            "0.60",
            "2026-04-22T01:00:00Z",
            "loyalty_bonus_points",
            "0.12",
            "0",
        ],
        [
            "CUST-0003",
            "0.55",
            "0.72",
            "2026-04-22T01:00:00Z",
            "free_shipping_offer",
            "0.18",
            "1",
        ],
    ][:row_count]
    contact_rows = [
        ["CUST-0001", "96", "2"],
        ["CUST-0002", "120", "1"],
        ["CUST-0003", "72", "3"],
    ][:row_count]

    _write_csv(
        use_case_root / "crm_customers.csv",
        [
            "customer_id",
            "consent_status",
            "profile_completeness",
            "no_critical_service_case",
            "do_not_contact",
        ],
        crm_rows,
    )
    _write_csv(
        use_case_root / "behavior_signals.csv",
        [
            "customer_id",
            "risk_score",
            "value_score",
            "score_ts",
            "historical_action_id",
            "observed_uplift",
            "retained_30d",
        ],
        behavior_rows,
    )
    _write_csv(
        use_case_root / "contact_history.csv",
        ["customer_id", "last_marketing_contact_hours", "contacts_last_7d"],
        contact_rows,
    )


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
