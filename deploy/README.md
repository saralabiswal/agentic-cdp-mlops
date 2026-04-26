# Deployment Packaging

This directory contains packaging assets for running the live UI/API service in containers.

## Files

1. `deploy/Dockerfile.ui-live`
2. `deploy/docker-compose.ui-live.yml`

## Build Image

```bash
make ui-live-docker-build
```

Equivalent:

```bash
docker build -f deploy/Dockerfile.ui-live -t cdp-ui-live:local .
```

## Compose Profiles

Use the compatibility wrapper (`scripts/compose.sh`) so both `docker compose` and `docker-compose` work.

### Dev Profile (`dev`)

Mounted source tree for fast iteration.

```bash
make ui-live-docker-dev
```

Endpoint: `http://localhost:8080/ui/experience/`

### Demo Profile (`demo`)

Uses mounted `artifacts/` and `ui/data/` for reproducible demos.

```bash
make ui-live-docker-demo
```

Endpoint: `http://localhost:8081/ui/experience/`

### Prod-Sim Profile (`prod-sim`)

Read-only mounted artifacts for production-like behavior.

```bash
make ui-live-docker-prod
```

Endpoint: `http://localhost:8082/ui/experience/`

## Stop Containers

```bash
./scripts/compose.sh -f deploy/docker-compose.ui-live.yml --profile dev down
./scripts/compose.sh -f deploy/docker-compose.ui-live.yml --profile demo down
./scripts/compose.sh -f deploy/docker-compose.ui-live.yml --profile prod-sim down
```

## Notes

1. The container entrypoint runs `python3 scripts/ui_live_server.py --host 0.0.0.0 --port 8080`.
2. API contracts are documented in `docs/API_REFERENCE.md`.
