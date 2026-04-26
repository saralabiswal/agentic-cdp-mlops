from __future__ import annotations

from pipelines.contract_loader import list_config_paths, load_contract


def test_all_use_case_configs_load() -> None:
    config_paths = list_config_paths()
    assert len(config_paths) == 4

    use_case_ids = set()
    for path in config_paths:
        contract = load_contract(path)
        use_case_ids.add(contract.use_case_id)
        assert contract.output_contract.fields
        assert contract.output_contract.sla_latency_ms > 0

    assert use_case_ids == {
        "UC-NBA-RET-001",
        "UC-CHURN-RET-002",
        "UC-MMM-PLN-003",
        "UC-INCR-MKT-004",
    }

