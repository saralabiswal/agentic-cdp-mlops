from __future__ import annotations

"""CLI entrypoint for model-only and full-stack architecture runs."""

import argparse
import json
from pathlib import Path

from pipelines.contract_loader import DEFAULT_CONFIG_DIR, list_config_paths, load_contract
from pipelines.run_use_case import DEFAULT_OUTPUT_DIR, run_all_use_cases, run_use_case
from scripts.ui_live_server import (
    load_portfolio_summary,
    load_run_data_quality_details,
    load_run_stage_details,
)
from stack.baseline_report import write_baseline_report
from stack.governance import approve_run_governance
from stack.orchestrator import run_full_stack, run_full_stack_all
from stack.model_registry import (
    evaluate_model_promotion_readiness,
    list_model_registry_entries,
    promote_model_version,
)
from stack.project_status import sync_project_scope_status
from stack.run_registry import (
    build_run_registry_index,
    get_run_summary,
    list_run_summaries,
    prune_run_artifacts,
)


def _build_parser() -> argparse.ArgumentParser:
    """Define CLI contract for config listing and execution modes."""
    parser = argparse.ArgumentParser(
        prog="cdp-platform",
        description="Run reusable CDP use cases from YAML contracts.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_cmd = subparsers.add_parser("list-configs", help="List available use case configs")
    list_cmd.add_argument("--config-dir", default=str(DEFAULT_CONFIG_DIR))

    run_cmd = subparsers.add_parser("run", help="Run a single use case")
    run_cmd.add_argument("--use-case", required=True, help="Use case ID, for example UC-NBA-RET-001")
    run_cmd.add_argument("--config-dir", default=str(DEFAULT_CONFIG_DIR))
    run_cmd.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    run_cmd.add_argument("--seed", type=int, default=7)

    run_all_cmd = subparsers.add_parser("run-all", help="Run every use case config")
    run_all_cmd.add_argument("--config-dir", default=str(DEFAULT_CONFIG_DIR))
    run_all_cmd.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    run_all_cmd.add_argument("--seed", type=int, default=7)

    stack_cmd = subparsers.add_parser(
        "run-stack", help="Run full architecture stack for one use case"
    )
    stack_cmd.add_argument("--use-case", required=True, help="Use case ID")
    stack_cmd.add_argument("--config-dir", default=str(DEFAULT_CONFIG_DIR))
    stack_cmd.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    stack_cmd.add_argument("--seed", type=int, default=7)
    stack_cmd.add_argument("--infra-profile", choices=["local", "oss"], default="local")
    stack_cmd.add_argument(
        "--oss-compose-file", default="infra/docker-compose.oss.yml"
    )
    stack_cmd.add_argument(
        "--strict-model-backends",
        action="store_true",
        help="Fail run when required advanced backend libraries are unavailable.",
    )
    stack_cmd.add_argument(
        "--source-data-root",
        default=None,
        help="Root directory for production CSV source datasets (use_case_id subfolders).",
    )
    stack_cmd.add_argument(
        "--require-real-data",
        action="store_true",
        help="Fail run if production source dataset files are missing.",
    )
    stack_cmd.add_argument(
        "--runtime-mode",
        choices=["default", "synthetic_only"],
        default="default",
        help="Runtime mode for source data execution.",
    )
    stack_cmd.add_argument(
        "--scenario-id",
        default=None,
        help="Optional deterministic scenario preset id for synthetic runs.",
    )
    stack_cmd.add_argument(
        "--failure-injection",
        action="append",
        default=[],
        help="Optional failure injection toggle (repeatable).",
    )

    stack_all_cmd = subparsers.add_parser(
        "run-stack-all", help="Run full architecture stack for all use cases"
    )
    stack_all_cmd.add_argument("--config-dir", default=str(DEFAULT_CONFIG_DIR))
    stack_all_cmd.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    stack_all_cmd.add_argument("--seed", type=int, default=7)
    stack_all_cmd.add_argument("--infra-profile", choices=["local", "oss"], default="local")
    stack_all_cmd.add_argument(
        "--oss-compose-file", default="infra/docker-compose.oss.yml"
    )
    stack_all_cmd.add_argument(
        "--strict-model-backends",
        action="store_true",
        help="Fail run when required advanced backend libraries are unavailable.",
    )
    stack_all_cmd.add_argument(
        "--source-data-root",
        default=None,
        help="Root directory for production CSV source datasets (use_case_id subfolders).",
    )
    stack_all_cmd.add_argument(
        "--require-real-data",
        action="store_true",
        help="Fail run if production source dataset files are missing.",
    )
    stack_all_cmd.add_argument(
        "--runtime-mode",
        choices=["default", "synthetic_only"],
        default="default",
        help="Runtime mode for source data execution.",
    )
    stack_all_cmd.add_argument(
        "--scenario-id",
        default=None,
        help="Optional deterministic scenario preset id for synthetic runs.",
    )
    stack_all_cmd.add_argument(
        "--failure-injection",
        action="append",
        default=[],
        help="Optional failure injection toggle (repeatable).",
    )

    list_runs_cmd = subparsers.add_parser(
        "list-runs", help="List full-stack run summaries from artifacts"
    )
    list_runs_cmd.add_argument("--artifacts-root", default=str(DEFAULT_OUTPUT_DIR))
    list_runs_cmd.add_argument("--use-case", default=None)
    list_runs_cmd.add_argument("--status", choices=["all", "pass", "fail"], default="all")
    list_runs_cmd.add_argument("--infra", choices=["all", "local", "oss"], default="all")
    list_runs_cmd.add_argument("--seed", type=int, default=None)
    list_runs_cmd.add_argument("--q", default=None, help="Search token across run fields")
    list_runs_cmd.add_argument("--sort", choices=["asc", "desc"], default="desc")
    list_runs_cmd.add_argument("--limit", type=int, default=50)
    list_runs_cmd.add_argument("--offset", type=int, default=0)

    show_run_cmd = subparsers.add_parser(
        "show-run", help="Show one full-stack run summary by use-case and run ID"
    )
    show_run_cmd.add_argument("--use-case", required=True)
    show_run_cmd.add_argument("--run-id", required=True)
    show_run_cmd.add_argument("--artifacts-root", default=str(DEFAULT_OUTPUT_DIR))

    show_stages_cmd = subparsers.add_parser(
        "show-stages",
        help="Show stage-level technical details for one run",
    )
    show_stages_cmd.add_argument("--use-case", required=True)
    show_stages_cmd.add_argument("--run-id", required=True)
    show_stages_cmd.add_argument("--artifacts-root", default=str(DEFAULT_OUTPUT_DIR))

    show_data_quality_cmd = subparsers.add_parser(
        "show-data-quality",
        help="Show compact data-quality blockers and warnings for one run",
    )
    show_data_quality_cmd.add_argument("--use-case", required=True)
    show_data_quality_cmd.add_argument("--run-id", required=True)
    show_data_quality_cmd.add_argument("--artifacts-root", default=str(DEFAULT_OUTPUT_DIR))

    portfolio_cmd = subparsers.add_parser(
        "portfolio-summary",
        help="Show cross-use-case KPI and run-health portfolio summary",
    )
    portfolio_cmd.add_argument("--artifacts-root", default=str(DEFAULT_OUTPUT_DIR))
    portfolio_cmd.add_argument("--status", choices=["all", "pass", "fail"], default="all")
    portfolio_cmd.add_argument("--infra", choices=["all", "local", "oss"], default="all")
    portfolio_cmd.add_argument("--sort", choices=["asc", "desc"], default="desc")
    portfolio_cmd.add_argument("--limit-per-use-case", type=int, default=1)

    baseline_cmd = subparsers.add_parser(
        "baseline-report",
        help="Generate baseline_report.json from latest run per use case",
    )
    baseline_cmd.add_argument("--artifacts-root", default=str(DEFAULT_OUTPUT_DIR))
    baseline_cmd.add_argument(
        "--output",
        default=None,
        help="Optional output path. Default: <artifacts-root>/baseline_report.json",
    )

    reindex_cmd = subparsers.add_parser(
        "reindex-runs",
        help="Force rebuild run-registry index cache",
    )
    reindex_cmd.add_argument("--artifacts-root", default=str(DEFAULT_OUTPUT_DIR))

    prune_runs_cmd = subparsers.add_parser(
        "prune-runs",
        help="Apply run retention policy (dry-run by default)",
    )
    prune_runs_cmd.add_argument("--artifacts-root", default=str(DEFAULT_OUTPUT_DIR))
    prune_runs_cmd.add_argument("--keep-per-use-case", type=int, default=20)
    prune_runs_cmd.add_argument("--max-age-days", type=int, default=None)
    prune_runs_cmd.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete planned run directories. Without this flag, command is dry-run.",
    )

    model_registry_list_cmd = subparsers.add_parser(
        "model-registry-list",
        help="List model-registry lifecycle entries",
    )
    model_registry_list_cmd.add_argument("--artifacts-root", default=str(DEFAULT_OUTPUT_DIR))
    model_registry_list_cmd.add_argument("--use-case", default=None)
    model_registry_list_cmd.add_argument(
        "--stage",
        choices=["candidate", "approved", "prod"],
        default=None,
    )
    model_registry_list_cmd.add_argument("--limit", type=int, default=100)

    model_readiness_cmd = subparsers.add_parser(
        "model-readiness",
        help="Evaluate promotion-readiness checks for one run",
    )
    model_readiness_cmd.add_argument("--artifacts-root", default=str(DEFAULT_OUTPUT_DIR))
    model_readiness_cmd.add_argument("--use-case", required=True)
    model_readiness_cmd.add_argument("--run-id", required=True)
    model_readiness_cmd.add_argument(
        "--require-strict-backend",
        action="store_true",
        help="Treat advanced backend mismatch as blocking failure.",
    )

    model_promote_cmd = subparsers.add_parser(
        "model-promote",
        help="Promote one run to approved/prod stage in model registry",
    )
    model_promote_cmd.add_argument("--artifacts-root", default=str(DEFAULT_OUTPUT_DIR))
    model_promote_cmd.add_argument("--use-case", required=True)
    model_promote_cmd.add_argument("--run-id", required=True)
    model_promote_cmd.add_argument("--to", required=True, choices=["approved", "prod"])
    model_promote_cmd.add_argument(
        "--require-strict-backend",
        action="store_true",
        help="Require strict advanced backend readiness before promotion.",
    )
    model_promote_cmd.add_argument(
        "--force",
        action="store_true",
        help="Override readiness blockers and force promotion.",
    )

    governance_approve_cmd = subparsers.add_parser(
        "governance-approve",
        help="Approve monitoring/governance deployment readiness for one run",
    )
    governance_approve_cmd.add_argument("--artifacts-root", default=str(DEFAULT_OUTPUT_DIR))
    governance_approve_cmd.add_argument("--use-case", required=True)
    governance_approve_cmd.add_argument("--run-id", required=True)
    governance_approve_cmd.add_argument("--approved-by", default=None)
    governance_approve_cmd.add_argument(
        "--note",
        default=None,
        help="Optional approval note stored in monitoring governance artifact.",
    )
    governance_approve_cmd.add_argument(
        "--accept-warning",
        action="append",
        default=[],
        help="Warning check name to accept (repeatable), e.g. table_name.check_name.",
    )
    governance_approve_cmd.add_argument(
        "--accept-all-warnings",
        action="store_true",
        help="Accept all currently listed warning_data_quality_checks.",
    )
    governance_approve_cmd.add_argument(
        "--warning-rationale",
        default=None,
        help="Optional rationale persisted for accepted warnings.",
    )
    governance_approve_cmd.add_argument(
        "--force",
        action="store_true",
        help="Override blockers or unknown warning names.",
    )

    sync_project_status_cmd = subparsers.add_parser(
        "sync-project-status",
        help="Refresh auto-generated live snapshot in PROJECT_SCOPE_AND_STATUS.md",
    )
    sync_project_status_cmd.add_argument(
        "--artifacts-root",
        default="artifacts",
        help="Artifacts root used for live status snapshot data.",
    )
    sync_project_status_cmd.add_argument(
        "--status-file",
        default="PROJECT_SCOPE_AND_STATUS.md",
        help="Markdown status file to update.",
    )

    return parser


def main() -> None:
    """Parse CLI args and execute the selected run path."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "list-configs":
        config_dir = Path(args.config_dir)
        for config_path in list_config_paths(config_dir=config_dir):
            contract = load_contract(config_path)
            print(f"{contract.use_case_id}: {contract.name} [{config_path}]")
        return

    if args.command == "run":
        summary = run_use_case(
            use_case_id=args.use_case,
            config_dir=Path(args.config_dir),
            output_dir=Path(args.output_dir),
            seed=args.seed,
        )
        print(json.dumps(summary, indent=2))
        return

    if args.command == "run-all":
        summaries = run_all_use_cases(
            config_dir=Path(args.config_dir),
            output_dir=Path(args.output_dir),
            seed=args.seed,
        )
        print(json.dumps(summaries, indent=2))
        return

    if args.command == "run-stack":
        summary = run_full_stack(
            use_case_id=args.use_case,
            config_dir=Path(args.config_dir),
            output_dir=Path(args.output_dir),
            seed=args.seed,
            infra_profile=args.infra_profile,
            oss_compose_file=Path(args.oss_compose_file),
            strict_model_backends=bool(args.strict_model_backends),
            source_data_root=Path(args.source_data_root) if args.source_data_root else None,
            require_real_data=bool(args.require_real_data),
            runtime_mode=str(args.runtime_mode),
            scenario_id=str(args.scenario_id).strip() if args.scenario_id else None,
            failure_injection=[str(item).strip() for item in args.failure_injection if str(item).strip()],
        )
        print(json.dumps(summary, indent=2))
        return

    if args.command == "run-stack-all":
        summaries = run_full_stack_all(
            config_dir=Path(args.config_dir),
            output_dir=Path(args.output_dir),
            seed=args.seed,
            infra_profile=args.infra_profile,
            oss_compose_file=Path(args.oss_compose_file),
            strict_model_backends=bool(args.strict_model_backends),
            source_data_root=Path(args.source_data_root) if args.source_data_root else None,
            require_real_data=bool(args.require_real_data),
            runtime_mode=str(args.runtime_mode),
            scenario_id=str(args.scenario_id).strip() if args.scenario_id else None,
            failure_injection=[str(item).strip() for item in args.failure_injection if str(item).strip()],
        )
        print(json.dumps(summaries, indent=2))
        return

    if args.command == "list-runs":
        payload = list_run_summaries(
            artifacts_root=Path(args.artifacts_root),
            use_case_id=args.use_case,
            run_status=args.status,
            infra_profile=args.infra,
            seed=args.seed,
            query=args.q,
            sort=args.sort,
            limit=args.limit,
            offset=args.offset,
        )
        print(json.dumps(payload, indent=2))
        return

    if args.command == "show-run":
        payload = get_run_summary(
            use_case_id=args.use_case,
            run_id=args.run_id,
            artifacts_root=Path(args.artifacts_root),
        )
        if payload is None:
            parser.error(
                f"Run not found for use_case_id={args.use_case}, run_id={args.run_id}"
            )
        print(json.dumps(payload, indent=2))
        return

    if args.command == "show-stages":
        payload = load_run_stage_details(
            use_case_id=args.use_case,
            run_id=args.run_id,
            artifacts_root=Path(args.artifacts_root),
        )
        if payload is None:
            parser.error(
                f"Run not found for use_case_id={args.use_case}, run_id={args.run_id}"
            )
        print(json.dumps(payload, indent=2))
        return

    if args.command == "show-data-quality":
        payload = load_run_data_quality_details(
            use_case_id=args.use_case,
            run_id=args.run_id,
            artifacts_root=Path(args.artifacts_root),
        )
        if payload is None:
            parser.error(
                f"Run not found for use_case_id={args.use_case}, run_id={args.run_id}"
            )
        print(json.dumps(payload, indent=2))
        return

    if args.command == "portfolio-summary":
        payload = load_portfolio_summary(
            artifacts_root=Path(args.artifacts_root),
            status_filter=args.status,
            infra_filter=args.infra,
            sort=args.sort,
            limit_per_use_case=args.limit_per_use_case,
        )
        print(json.dumps(payload, indent=2))
        return

    if args.command == "baseline-report":
        payload = write_baseline_report(
            artifacts_root=Path(args.artifacts_root),
            output_path=Path(args.output) if args.output else None,
        )
        print(json.dumps(payload, indent=2))
        return

    if args.command == "reindex-runs":
        payload = build_run_registry_index(artifacts_root=Path(args.artifacts_root))
        print(json.dumps(payload, indent=2))
        return

    if args.command == "prune-runs":
        payload = prune_run_artifacts(
            artifacts_root=Path(args.artifacts_root),
            keep_per_use_case=args.keep_per_use_case,
            max_age_days=args.max_age_days,
            apply=args.apply,
        )
        print(json.dumps(payload, indent=2))
        return

    if args.command == "model-registry-list":
        payload = list_model_registry_entries(
            artifacts_root=Path(args.artifacts_root),
            use_case_id=args.use_case,
            stage=args.stage,
            limit=args.limit,
        )
        print(json.dumps(payload, indent=2))
        return

    if args.command == "model-readiness":
        payload = evaluate_model_promotion_readiness(
            artifacts_root=Path(args.artifacts_root),
            use_case_id=args.use_case,
            run_id=args.run_id,
            require_strict_backend=bool(args.require_strict_backend),
        )
        print(json.dumps(payload, indent=2))
        return

    if args.command == "model-promote":
        payload = promote_model_version(
            artifacts_root=Path(args.artifacts_root),
            use_case_id=args.use_case,
            run_id=args.run_id,
            target_stage=args.to,
            require_strict_backend=bool(args.require_strict_backend),
            force=bool(args.force),
        )
        print(json.dumps(payload, indent=2))
        return

    if args.command == "governance-approve":
        payload = approve_run_governance(
            artifacts_root=Path(args.artifacts_root),
            use_case_id=args.use_case,
            run_id=args.run_id,
            approved_by=args.approved_by,
            note=args.note,
            accept_warnings=list(args.accept_warning or []),
            accept_all_warnings=bool(args.accept_all_warnings),
            warning_rationale=args.warning_rationale,
            force=bool(args.force),
        )
        print(json.dumps(payload, indent=2))
        return

    if args.command == "sync-project-status":
        payload = sync_project_scope_status(
            artifacts_root=Path(args.artifacts_root),
            status_path=Path(args.status_file),
        )
        print(json.dumps(payload, indent=2))
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
