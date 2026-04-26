#!/usr/bin/env bash
set -euo pipefail

# Advanced model-backend quality gates.
# Assumes optional ML dependencies are already installed.

OUTPUT_DIR="artifacts_ci_ml"

echo "[1/4] Strict model-backend tests"
python3 -m pytest -q tests/test_model_backend_runtime.py tests/test_model_backend_strict_mode.py tests/test_model_registry_workflow.py

echo "[2/4] Strict full-stack run across all use cases"
python3 -m pipelines.cli run-stack-all --strict-model-backends --output-dir "$OUTPUT_DIR" --seed 123

echo "[3/4] Model lifecycle workflow smoke checks"
RUN_ID=$(python3 -m pipelines.cli list-runs --artifacts-root "$OUTPUT_DIR" --use-case UC-NBA-RET-001 --limit 1 | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload['runs'][0]['run_id'])")
python3 -m pipelines.cli model-readiness --artifacts-root "$OUTPUT_DIR" --use-case UC-NBA-RET-001 --run-id "$RUN_ID" --require-strict-backend >/dev/null
python3 -m pipelines.cli model-promote --artifacts-root "$OUTPUT_DIR" --use-case UC-NBA-RET-001 --run-id "$RUN_ID" --to approved --require-strict-backend >/dev/null

echo "[4/5] Documentation freshness"
python3 docs/generate_tech_docs.py --check
python3 docs/generate_api_contracts.py --check

echo "[5/5] Refresh project status snapshot from milestone artifacts"
./scripts/ci_refresh_status_docs.sh --artifacts-root "$OUTPUT_DIR" --status-file PROJECT_SCOPE_AND_STATUS.md

echo "Advanced model-backend quality gate passed."
