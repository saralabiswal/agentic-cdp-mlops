#!/usr/bin/env bash
set -euo pipefail

# Refresh PROJECT_SCOPE_AND_STATUS live snapshot from a milestone artifacts root.
# Usage:
#   ./scripts/ci_refresh_status_docs.sh
#   ./scripts/ci_refresh_status_docs.sh --artifacts-root artifacts_ci_ml --status-file PROJECT_SCOPE_AND_STATUS.md

ARTIFACTS_ROOT="${ARTIFACTS_ROOT:-artifacts_ci_ml}"
STATUS_FILE="${STATUS_FILE:-PROJECT_SCOPE_AND_STATUS.md}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --artifacts-root)
      ARTIFACTS_ROOT="${2:-}"
      shift 2
      ;;
    --status-file)
      STATUS_FILE="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Supported: --artifacts-root <path> --status-file <path>"
      exit 2
      ;;
  esac
done

if [[ -z "$ARTIFACTS_ROOT" || -z "$STATUS_FILE" ]]; then
  echo "Both artifacts root and status file must be non-empty."
  exit 2
fi

if [[ ! -d "$ARTIFACTS_ROOT" ]]; then
  echo "Artifacts root does not exist; skipping status refresh: $ARTIFACTS_ROOT"
  exit 0
fi

python3 -m pipelines.cli sync-project-status \
  --artifacts-root "$ARTIFACTS_ROOT" \
  --status-file "$STATUS_FILE" >/dev/null

echo "Refreshed status snapshot in $STATUS_FILE from $ARTIFACTS_ROOT"

