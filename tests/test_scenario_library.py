from __future__ import annotations

import pytest

from stack.scenario_library import (
    apply_scenario_to_source_tables,
    resolve_scenario_preset,
    to_failure_injection_flags,
)


def test_resolve_scenario_preset_validates_use_case_alignment() -> None:
    preset = resolve_scenario_preset(
        scenario_id="nba_high_risk_save",
        use_case_id="UC-NBA-RET-001",
    )
    assert preset is not None
    assert preset.use_case_id == "UC-NBA-RET-001"

    with pytest.raises(ValueError):
        resolve_scenario_preset(
            scenario_id="nba_high_risk_save",
            use_case_id="UC-MMM-PLN-003",
        )


def test_apply_scenario_to_source_tables_mutates_expected_fields() -> None:
    source_tables = {
        "behavior_signals": [
            {"risk_score": 0.2, "value_score": 0.1, "observed_uplift": 0.0},
            {"risk_score": 0.3, "value_score": 0.1, "observed_uplift": 0.0},
        ],
        "contact_history": [
            {"contacts_last_7d": 1},
            {"contacts_last_7d": 1},
        ],
    }
    mutated = apply_scenario_to_source_tables(
        use_case_id="UC-NBA-RET-001",
        source_tables=source_tables,
        scenario_id="nba_high_risk_save",
    )
    assert mutated["behavior_signals"][0]["risk_score"] >= 0.7
    assert mutated["behavior_signals"][1]["risk_score"] >= 0.7
    assert mutated["contact_history"][0]["contacts_last_7d"] >= 1


def test_failure_injection_flags_include_scenario_defaults() -> None:
    flags = to_failure_injection_flags(
        scenario_id="nba_dq_failure_demo",
        use_case_id="UC-NBA-RET-001",
    )
    assert flags["dq_fail"] is True
    assert flags["schema_fail"] is False
