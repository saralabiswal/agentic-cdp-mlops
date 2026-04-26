from __future__ import annotations

import json
from pathlib import Path

from stack.orchestrator import run_full_stack
from scripts import ui_live_server


def test_synthetic_only_runtime_mode_skips_real_dataset(tmp_path: Path) -> None:
    summary = run_full_stack(
        use_case_id="UC-NBA-RET-001",
        output_dir=tmp_path,
        seed=101,
        runtime_mode="synthetic_only",
        source_data_root=Path("data/production"),
    )
    assert summary["runtime_mode"] == "synthetic_only"
    assert summary["source_data"]["mode"] == "synthetic_only"


def test_scenario_preset_runs_are_deterministic(tmp_path: Path) -> None:
    summary_a = run_full_stack(
        use_case_id="UC-MMM-PLN-003",
        output_dir=tmp_path / "run_a",
        seed=333,
        runtime_mode="synthetic_only",
        scenario_id="mmm_budget_rebalance",
    )
    summary_b = run_full_stack(
        use_case_id="UC-MMM-PLN-003",
        output_dir=tmp_path / "run_b",
        seed=333,
        runtime_mode="synthetic_only",
        scenario_id="mmm_budget_rebalance",
    )

    assert summary_a["records"] == summary_b["records"]
    assert summary_a["model_metrics"] == summary_b["model_metrics"]


def test_failure_injection_forces_run_fail_and_updates_report(tmp_path: Path) -> None:
    summary = run_full_stack(
        use_case_id="UC-NBA-RET-001",
        output_dir=tmp_path,
        seed=77,
        runtime_mode="synthetic_only",
        failure_injection=["dq_fail"],
    )
    assert summary["run_status"] == "fail"
    report_path = Path(summary["artifacts"]["monitoring_report"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["run_status"] == "fail"
    assert "dq_fail" in report["failure_injection"]["active"]
    assert report["data_quality"]["status"] == "fail"


def test_simulation_session_run_next_and_reset(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ui_live_server, "ROOT", tmp_path)
    payload = ui_live_server.create_simulation_session(
        payload={
            "use_case_id": "UC-NBA-RET-001",
            "infra_profile": "local",
            "seed": 101,
            "runtime_mode": "synthetic_only",
        }
    )
    session_id = payload["session_id"]

    state = ui_live_server.get_simulation_session_state(session_id=session_id)
    assert state is not None
    assert state["stage_cursor"] == 0

    after_next, error_next = ui_live_server.run_simulation_step(
        session_id=session_id,
        action="run_next",
        payload={},
    )
    assert error_next is None
    assert after_next is not None
    assert after_next["stage_cursor"] == 1
    assert after_next["run_id"]

    after_reset, error_reset = ui_live_server.run_simulation_step(
        session_id=session_id,
        action="reset",
        payload={},
    )
    assert error_reset is None
    assert after_reset is not None
    assert after_reset["stage_cursor"] == 0
    assert after_reset["paused"] is False


def test_simulation_session_pause_and_resume(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ui_live_server, "ROOT", tmp_path)
    payload = ui_live_server.create_simulation_session(
        payload={
            "use_case_id": "UC-NBA-RET-001",
            "infra_profile": "local",
            "seed": 101,
            "runtime_mode": "synthetic_only",
        }
    )
    session_id = payload["session_id"]

    paused_state, pause_error = ui_live_server.run_simulation_step(
        session_id=session_id,
        action="pause",
        payload={},
    )
    assert pause_error is None
    assert paused_state is not None
    assert paused_state["paused"] is True

    blocked_state, blocked_error = ui_live_server.run_simulation_step(
        session_id=session_id,
        action="run_next",
        payload={},
    )
    assert blocked_state is None
    assert blocked_error == "Simulation is paused. Resume before running stages."

    resumed_state, resume_error = ui_live_server.run_simulation_step(
        session_id=session_id,
        action="resume",
        payload={},
    )
    assert resume_error is None
    assert resumed_state is not None
    assert resumed_state["paused"] is False

    after_next, error_next = ui_live_server.run_simulation_step(
        session_id=session_id,
        action="run_next",
        payload={},
    )
    assert error_next is None
    assert after_next is not None
    assert after_next["stage_cursor"] == 1
