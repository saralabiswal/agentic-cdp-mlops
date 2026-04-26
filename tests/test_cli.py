from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pipelines.cli import _build_parser


def test_cli_parser_accepts_strict_model_backend_flags() -> None:
    parser = _build_parser()
    single_args = parser.parse_args(
        [
            "run-stack",
            "--use-case",
            "UC-NBA-RET-001",
            "--strict-model-backends",
            "--runtime-mode",
            "synthetic_only",
            "--scenario-id",
            "nba_high_risk_save",
            "--failure-injection",
            "dq_fail",
            "--source-data-root",
            "data/production",
            "--require-real-data",
        ]
    )
    all_args = parser.parse_args(
        [
            "run-stack-all",
            "--strict-model-backends",
            "--runtime-mode",
            "synthetic_only",
            "--source-data-root",
            "data/production",
            "--require-real-data",
        ]
    )
    assert single_args.strict_model_backends is True
    assert all_args.strict_model_backends is True
    assert single_args.source_data_root == "data/production"
    assert all_args.source_data_root == "data/production"
    assert single_args.require_real_data is True
    assert all_args.require_real_data is True
    assert single_args.runtime_mode == "synthetic_only"
    assert all_args.runtime_mode == "synthetic_only"
    assert single_args.scenario_id == "nba_high_risk_save"
    assert single_args.failure_injection == ["dq_fail"]


def test_cli_run_command(tmp_path: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "run",
        "--use-case",
        "UC-NBA-RET-001",
        "--output-dir",
        str(tmp_path),
        "--seed",
        "17",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["use_case_id"] == "UC-NBA-RET-001"
    assert Path(payload["artifact_path"]).exists()


def test_cli_run_stack_command(tmp_path: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "run-stack",
        "--use-case",
        "UC-MMM-PLN-003",
        "--output-dir",
        str(tmp_path),
        "--seed",
        "29",
        "--runtime-mode",
        "synthetic_only",
        "--scenario-id",
        "mmm_budget_rebalance",
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["use_case_id"] == "UC-MMM-PLN-003"
    assert Path(payload["summary_path"]).exists()
    assert payload["runtime_mode"] == "synthetic_only"
    assert payload["scenario_id"] == "mmm_budget_rebalance"


def test_cli_run_stack_oss_profile(tmp_path: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "run-stack",
        "--use-case",
        "UC-NBA-RET-001",
        "--infra-profile",
        "oss",
        "--oss-compose-file",
        str(tmp_path / "missing-compose.yml"),
        "--output-dir",
        str(tmp_path),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["infra_profile"] == "oss"
    assert payload["oss_runtime"]["status"] == "fallback_local"


def test_cli_list_runs_command(tmp_path: Path) -> None:
    run_stack_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "run-stack",
        "--use-case",
        "UC-NBA-RET-001",
        "--output-dir",
        str(tmp_path),
        "--seed",
        "31",
    ]
    subprocess.run(run_stack_cmd, check=True, capture_output=True, text=True)

    list_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "list-runs",
        "--artifacts-root",
        str(tmp_path),
        "--use-case",
        "UC-NBA-RET-001",
        "--limit",
        "5",
    ]
    result = subprocess.run(list_cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["total"] >= 1
    assert payload["count"] >= 1
    assert payload["runs"][0]["use_case_id"] == "UC-NBA-RET-001"


def test_cli_show_run_command(tmp_path: Path) -> None:
    run_stack_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "run-stack",
        "--use-case",
        "UC-MMM-PLN-003",
        "--output-dir",
        str(tmp_path),
        "--seed",
        "37",
    ]
    run_result = subprocess.run(run_stack_cmd, check=True, capture_output=True, text=True)
    run_payload = json.loads(run_result.stdout)
    run_id = run_payload["run_id"]

    show_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "show-run",
        "--artifacts-root",
        str(tmp_path),
        "--use-case",
        "UC-MMM-PLN-003",
        "--run-id",
        run_id,
    ]
    result = subprocess.run(show_cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["use_case_id"] == "UC-MMM-PLN-003"
    assert payload["run_id"] == run_id
    assert Path(payload["summary_path"]).exists()


def test_cli_show_stages_command(tmp_path: Path) -> None:
    run_stack_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "run-stack",
        "--use-case",
        "UC-NBA-RET-001",
        "--output-dir",
        str(tmp_path),
        "--seed",
        "41",
    ]
    run_result = subprocess.run(run_stack_cmd, check=True, capture_output=True, text=True)
    run_payload = json.loads(run_result.stdout)
    run_id = run_payload["run_id"]

    show_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "show-stages",
        "--artifacts-root",
        str(tmp_path),
        "--use-case",
        "UC-NBA-RET-001",
        "--run-id",
        run_id,
    ]
    result = subprocess.run(show_cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["use_case_id"] == "UC-NBA-RET-001"
    assert payload["run_id"] == run_id
    assert payload["stage_total"] == 8


def test_cli_show_data_quality_command(tmp_path: Path) -> None:
    run_stack_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "run-stack",
        "--use-case",
        "UC-NBA-RET-001",
        "--output-dir",
        str(tmp_path),
        "--seed",
        "42",
    ]
    run_result = subprocess.run(run_stack_cmd, check=True, capture_output=True, text=True)
    run_payload = json.loads(run_result.stdout)
    run_id = run_payload["run_id"]

    show_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "show-data-quality",
        "--artifacts-root",
        str(tmp_path),
        "--use-case",
        "UC-NBA-RET-001",
        "--run-id",
        run_id,
    ]
    result = subprocess.run(show_cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["use_case_id"] == "UC-NBA-RET-001"
    assert payload["run_id"] == run_id
    assert "data_quality_status" in payload
    assert isinstance(payload["blocker_count"], int)
    assert isinstance(payload["warning_count"], int)
    assert isinstance(payload["blocker_names"], list)
    assert isinstance(payload["warning_names"], list)


def test_cli_portfolio_summary_command(tmp_path: Path) -> None:
    for use_case_id in ["UC-NBA-RET-001", "UC-MMM-PLN-003"]:
        run_stack_cmd = [
            sys.executable,
            "-m",
            "pipelines.cli",
            "run-stack",
            "--use-case",
            use_case_id,
            "--output-dir",
            str(tmp_path),
            "--seed",
            "43",
        ]
        subprocess.run(run_stack_cmd, check=True, capture_output=True, text=True)

    summary_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "portfolio-summary",
        "--artifacts-root",
        str(tmp_path),
        "--limit-per-use-case",
        "1",
    ]
    result = subprocess.run(summary_cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert payload["totals"]["use_case_count"] >= 2
    assert len(payload["use_cases"]) >= 2


def test_cli_baseline_report_command(tmp_path: Path) -> None:
    run_stack_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "run-stack",
        "--use-case",
        "UC-NBA-RET-001",
        "--output-dir",
        str(tmp_path),
        "--seed",
        "53",
    ]
    subprocess.run(run_stack_cmd, check=True, capture_output=True, text=True)

    report_path = tmp_path / "baseline_report.json"
    cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "baseline-report",
        "--artifacts-root",
        str(tmp_path),
        "--output",
        str(report_path),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)

    assert Path(payload["report_path"]).exists()
    assert payload["totals"]["use_case_count"] >= 1
    assert any(row["use_case_id"] == "UC-NBA-RET-001" for row in payload["runs"])


def test_cli_reindex_and_prune_runs_dry_run_commands(tmp_path: Path) -> None:
    run_stack_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "run-stack",
        "--use-case",
        "UC-CHURN-RET-002",
        "--output-dir",
        str(tmp_path),
        "--seed",
        "47",
    ]
    subprocess.run(run_stack_cmd, check=True, capture_output=True, text=True)

    reindex_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "reindex-runs",
        "--artifacts-root",
        str(tmp_path),
    ]
    reindex_result = subprocess.run(reindex_cmd, check=True, capture_output=True, text=True)
    reindex_payload = json.loads(reindex_result.stdout)
    assert reindex_payload["rows_indexed"] >= 1

    prune_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "prune-runs",
        "--artifacts-root",
        str(tmp_path),
        "--keep-per-use-case",
        "0",
    ]
    prune_result = subprocess.run(prune_cmd, check=True, capture_output=True, text=True)
    prune_payload = json.loads(prune_result.stdout)
    assert prune_payload["apply"] is False
    assert len(prune_payload["planned_deletions"]) >= 1


def test_cli_governance_approve_and_sync_project_status_commands(tmp_path: Path) -> None:
    run_stack_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "run-stack",
        "--use-case",
        "UC-NBA-RET-001",
        "--output-dir",
        str(tmp_path),
        "--seed",
        "59",
    ]
    run_result = subprocess.run(run_stack_cmd, check=True, capture_output=True, text=True)
    run_payload = json.loads(run_result.stdout)
    run_id = run_payload["run_id"]

    approve_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "governance-approve",
        "--artifacts-root",
        str(tmp_path),
        "--use-case",
        "UC-NBA-RET-001",
        "--run-id",
        run_id,
        "--approved-by",
        "test-user",
        "--note",
        "test approval",
    ]
    approve_result = subprocess.run(approve_cmd, check=True, capture_output=True, text=True)
    approve_payload = json.loads(approve_result.stdout)
    readiness = approve_payload["deployment_readiness"]
    assert readiness["status"] == "ready"
    assert readiness["approval"]["status"] == "approved"
    assert readiness["approval"]["approved_by"] == "test-user"

    baseline_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "baseline-report",
        "--artifacts-root",
        str(tmp_path),
    ]
    subprocess.run(baseline_cmd, check=True, capture_output=True, text=True)

    status_file = tmp_path / "PROJECT_SCOPE_AND_STATUS.md"
    status_file.write_text(
        "# Project Scope And Status\n\nLast updated (UTC): 2000-01-01T00:00:00Z\n",
        encoding="utf-8",
    )
    sync_cmd = [
        sys.executable,
        "-m",
        "pipelines.cli",
        "sync-project-status",
        "--artifacts-root",
        str(tmp_path),
        "--status-file",
        str(status_file),
    ]
    sync_result = subprocess.run(sync_cmd, check=True, capture_output=True, text=True)
    sync_payload = json.loads(sync_result.stdout)

    assert sync_payload["run_count"] >= 1
    content = status_file.read_text(encoding="utf-8")
    assert "<!-- status:auto:start -->" in content
    assert "<!-- status:auto:end -->" in content
    assert "Live Snapshot (Auto-Generated)" in content
