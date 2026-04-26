#!/usr/bin/env bash
set -euo pipefail

# Compatibility wrapper:
# - prefers `docker compose`
# - falls back to `docker-compose`

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  exec docker compose "$@"
fi

if command -v docker-compose >/dev/null 2>&1; then
  exec docker-compose "$@"
fi

echo "ERROR: Docker Compose is not available."
echo "Install either:"
echo "1) Docker compose plugin (`docker compose`), or"
echo "2) docker-compose binary."
exit 127

