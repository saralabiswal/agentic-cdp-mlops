# OSS Infra Profile

This profile provides an open-source infrastructure stack for this platform:

1. Kafka (event bus)
2. PostgreSQL (curated warehouse sink)
3. MinIO (object storage sink)
4. MinIO Client (`mc`) helper container

Compose file:

`infra/docker-compose.oss.yml`

Compose command compatibility:

1. `scripts/compose.sh` automatically uses `docker compose` when available.
2. It falls back to `docker-compose` when compose plugin is not installed.

## Start and stop

```bash
make infra-up
make infra-ps
make infra-smoke
make infra-down
```

## Run full stack with OSS profile

```bash
make run-stack-all-oss
```

Behavior:

1. Local adapters remain the default and always produce local artifacts.
2. For `UC-NBA-RET-001`, `--infra-profile oss` uses a golden runtime path:
   - source tables -> Kafka topics (direct publish)
   - consumed topic values -> curated rows -> Postgres
   - raw/curated snapshots -> MinIO
3. For other use cases, `--infra-profile oss` mirrors local artifacts to OSS services.
4. If OSS services are not running, the run gracefully falls back to local mode and reports warnings in `summary.json`.

## Smoke test coverage

`make infra-smoke` validates end-to-end connectivity with write/read probes:

1. Kafka topic create + produce + consume
2. Postgres table create + insert + select
3. MinIO bucket create + object write + object read

## OSS integration test

Run a full NBA OSS integration assertion (Kafka + Postgres + MinIO verification):

```bash
make test-oss
```

Notes:

1. Requires `make infra-up` first.
2. Test is gated by `RUN_OSS_TESTS=1` (set automatically by `make test-oss`).

## OSS demo command

Run a demo flow that executes NBA on OSS profile and prints a readable
summary with KPIs, OSS runtime counters, and artifact paths:

```bash
make demo-nba-oss
make demo-nba-oss-compact
```

## Legacy mirror behavior

For non-NBA use cases the OSS path remains mirror-first:

1. event topic files -> Kafka
2. curated JSONL rows -> PostgreSQL table `cdp_curated_rows`
3. raw and curated JSONL artifacts -> MinIO bucket `cdp-artifacts`

## Access points

1. Kafka bootstrap: `localhost:9092`
2. Postgres: `localhost:5432` (`cdp/cdp`, db: `cdp`)
3. MinIO API: `http://localhost:9000`
4. MinIO console: `http://localhost:9001`
