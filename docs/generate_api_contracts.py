#!/usr/bin/env python3
"""Generate OpenAPI-style and JSON-schema exports for inference contracts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ui_live_server import build_inference_contract_export, build_openapi_spec

CONTRACTS_DIR = PROJECT_ROOT / "docs" / "contracts"
INFERENCE_CONTRACTS_PATH = CONTRACTS_DIR / "inference_contracts.json"
INFERENCE_OPENAPI_PATH = CONTRACTS_DIR / "inference_openapi.json"
STATIC_GENERATED_AT_PLACEHOLDER = "1970-01-01T00:00:00Z"


def _parse_args() -> argparse.Namespace:
    """Parse CLI flags for generate/check modes."""
    parser = argparse.ArgumentParser(
        description="Generate inference contract schemas and OpenAPI-style export."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated files are stale instead of writing them.",
    )
    return parser.parse_args()


def _serialize(payload: dict[str, Any]) -> str:
    """Serialize payload deterministically for stable diffs/checks."""
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON payload to target file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_serialize(payload), encoding="utf-8")


def _is_outdated(path: Path, payload: dict[str, Any]) -> bool:
    """Return True when target file content differs from rendered payload."""
    if not path.exists():
        return True
    current = path.read_text(encoding="utf-8")
    return current != _serialize(payload)


def main() -> int:
    """Generate or check all inference schema export artifacts."""
    args = _parse_args()

    inference_contracts = build_inference_contract_export()
    # Keep generated artifacts stable for `--check` mode and CI diffs.
    inference_contracts["generated_at_utc"] = STATIC_GENERATED_AT_PLACEHOLDER
    openapi_spec = build_openapi_spec(base_url="http://127.0.0.1:8080")

    outputs = [
        (INFERENCE_CONTRACTS_PATH, inference_contracts),
        (INFERENCE_OPENAPI_PATH, openapi_spec),
    ]

    if args.check:
        stale_paths = [
            path
            for path, payload in outputs
            if _is_outdated(path=path, payload=payload)
        ]
        if stale_paths:
            for stale in stale_paths:
                print(f"Outdated generated contract: {stale.relative_to(PROJECT_ROOT)}")
            return 1
        for path, _ in outputs:
            print(f"Generated contract is up to date: {path.relative_to(PROJECT_ROOT)}")
        return 0

    for path, payload in outputs:
        _write_json(path=path, payload=payload)
        print(f"Wrote generated contract: {path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
