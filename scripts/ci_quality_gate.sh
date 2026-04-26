#!/usr/bin/env bash
set -euo pipefail

# CI quality gate runner.
# Usage:
#   ./scripts/ci_quality_gate.sh
#   ./scripts/ci_quality_gate.sh --with-oss

WITH_OSS=0
for arg in "$@"; do
  case "$arg" in
    --with-oss)
      WITH_OSS=1
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Supported: --with-oss"
      exit 2
      ;;
  esac
done

echo "[1/3] Unit and integration test suite"
python3 -m pytest -q

echo "[2/3] Documentation freshness"
python3 docs/generate_tech_docs.py --check
python3 docs/generate_api_contracts.py --check

if [[ "$WITH_OSS" == "1" ]]; then
  echo "[3/3] Optional OSS integration checks"
  ./scripts/infra_smoke_test.sh
  RUN_OSS_TESTS=1 python3 -m pytest -q tests/test_oss_integration.py
else
  echo "[3/3] Optional OSS integration checks skipped (use --with-oss to enable)"
fi

echo "CI quality gate passed."
