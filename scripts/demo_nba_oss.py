#!/usr/bin/env python3
"""Run NBA OSS demo flow and print a concise summary report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure repository root is importable when script is invoked as a file path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stack.orchestrator import run_full_stack


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NBA OSS demo and print summary.")
    parser.add_argument(
        "--output-dir",
        default="artifacts",
        help="Artifact output directory.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=101,
        help="Deterministic seed for repeatable demo values.",
    )
    parser.add_argument(
        "--compose-file",
        default="infra/docker-compose.oss.yml",
        help="Docker compose file for OSS profile.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print executive-friendly compact output (no raw JSON dump).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_full_stack(
        use_case_id="UC-NBA-RET-001",
        output_dir=Path(args.output_dir),
        seed=args.seed,
        infra_profile="oss",
        oss_compose_file=Path(args.compose_file),
    )

    if args.compact:
        _print_compact_summary(summary)
        return 0

    print("=== NBA OSS Demo Summary ===")
    print(f"Use case: {summary['use_case_id']} - {summary['name']}")
    print(f"Run ID: {summary['run_id']}")
    print(f"Infra profile: {summary['infra_profile']}")
    print(f"Run status: {summary['run_status']}")
    print("")

    records = summary["records"]
    print("Records:")
    print(f"- Source rows: {sum(records['source_tables'].values())}")
    print(f"- Curated rows: {records['curated_rows']}")
    print(f"- Feature rows: {records['feature_rows']}")
    print(f"- Model rows: {records['model_rows']}")
    print(f"- Activation rows: {records['activation_rows']}")
    print("")

    metrics = summary.get("model_metrics", {})
    print("Model KPIs:")
    for key in sorted(metrics.keys()):
        print(f"- {key}: {metrics[key]}")
    print("")

    oss_runtime = summary.get("oss_runtime")
    if oss_runtime:
        print("OSS Runtime:")
        print(f"- status: {oss_runtime.get('status')}")
        print(f"- kafka_topics_published: {oss_runtime.get('kafka_topics_published')}")
        print(f"- kafka_messages_consumed: {oss_runtime.get('kafka_messages_consumed')}")
        print(f"- postgres_rows_loaded: {oss_runtime.get('postgres_rows_loaded')}")
        print(f"- minio_objects_uploaded: {oss_runtime.get('minio_objects_uploaded')}")
        warnings = oss_runtime.get("warnings") or []
        if warnings:
            print("- warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        print("")

    oss_mirror = summary.get("oss_mirror")
    if oss_mirror:
        print("OSS Mirror:")
        print(f"- status: {oss_mirror.get('status')}")
        print(f"- kafka_topics_published: {oss_mirror.get('kafka_topics_published')}")
        print(f"- postgres_rows_loaded: {oss_mirror.get('postgres_rows_loaded')}")
        print(f"- minio_objects_uploaded: {oss_mirror.get('minio_objects_uploaded')}")
        warnings = oss_mirror.get("warnings") or []
        if warnings:
            print("- warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        print("")

    print("Artifacts:")
    print(f"- summary: {summary['summary_path']}")
    print(f"- monitoring: {summary['artifacts']['monitoring_report']}")
    print(f"- activation: {summary['artifacts']['activation_payloads']}")
    print("")

    print("Raw JSON summary:")
    print(json.dumps(summary, indent=2))
    return 0


def _print_compact_summary(summary: dict[str, Any]) -> None:
    """Print concise executive summary with key KPIs and OSS verification counters."""
    print("=== NBA OSS Demo (Compact) ===")
    print(f"Run: {summary['run_id']}")
    print(f"Status: {summary['run_status']} ({summary['infra_profile']})")
    print("")

    metrics = summary.get("model_metrics", {})
    primary_kpi = metrics.get("primary_kpi", "unknown")
    print("Key KPIs:")
    print(f"- primary_kpi: {primary_kpi}")
    for key in sorted(metrics.keys()):
        if key == "primary_kpi":
            continue
        print(f"- {key}: {metrics[key]}")
    print("")

    oss_runtime = summary.get("oss_runtime")
    if oss_runtime:
        print("OSS Runtime:")
        print(f"- status: {oss_runtime.get('status')}")
        print(f"- kafka_topics_published: {oss_runtime.get('kafka_topics_published')}")
        print(f"- kafka_messages_consumed: {oss_runtime.get('kafka_messages_consumed')}")
        print(f"- postgres_rows_loaded: {oss_runtime.get('postgres_rows_loaded')}")
        print(f"- minio_objects_uploaded: {oss_runtime.get('minio_objects_uploaded')}")
        warnings = oss_runtime.get("warnings") or []
        if warnings:
            print("- warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        print("")

    print("Artifacts:")
    print(f"- summary: {summary['summary_path']}")
    print(f"- monitoring: {summary['artifacts']['monitoring_report']}")
    print(f"- activation: {summary['artifacts']['activation_payloads']}")


if __name__ == "__main__":
    raise SystemExit(main())
