# API Reference

This document describes the live API exposed by:

`python3 scripts/ui_live_server.py --host 127.0.0.1 --port 8080`

Base URL:

`http://127.0.0.1:8080`

## Error Contract

All API errors use this JSON shape:

```json
{
  "error": "Human-readable message",
  "error_code": "stable_machine_code",
  "details": {}
}
```

Notes:

1. `details` is optional and only included when extra context is available.
2. Unknown API routes return `404` with `error_code: "not_found"`.

## Health + View Model

### `GET /api/health`

Returns service health and UTC server time.

```json
{
  "status": "ok",
  "server_time_utc": "2026-04-22T20:30:00.000000+00:00"
}
```

### `GET /api/view-model`

Returns UI view-model JSON (`ui/data/view_model.json`) and auto-builds it if missing.

Common errors:

1. `500 view_model_unavailable`

## Run Execution + Jobs

### `POST /api/run`

Triggers backend execution in a background job.

Body:

```json
{
  "use_case_id": "UC-NBA-RET-001",
  "infra_profile": "local",
  "seed": 101,
  "output_dir": "artifacts",
  "oss_compose_file": "infra/docker-compose.oss.yml",
  "strict_model_backends": false,
  "source_data_root": "data/production",
  "require_real_data": false
}
```

Returns `202 Accepted`:

```json
{
  "job_id": "8f68...",
  "status": "queued",
  "status_url": "/api/jobs/8f68...",
  "request": {
    "use_case_id": "UC-NBA-RET-001",
    "infra_profile": "local",
    "seed": 101,
    "output_dir": "artifacts",
    "oss_compose_file": "infra/docker-compose.oss.yml",
    "strict_model_backends": false,
    "source_data_root": "data/production",
    "require_real_data": false
  }
}
```

Common errors:

1. `400 invalid_body`
2. `404 not_found` (wrong route)

### `GET /api/jobs`

Lists recent jobs in reverse chronological order.

### `GET /api/jobs/<job_id>`

Returns one job status payload.

Common errors:

1. `404 job_not_found`

## Governance Approval

### `POST /api/governance/approve`

Approves deployment readiness for one run and persists audit metadata in monitoring artifacts.

Body:

```json
{
  "use_case_id": "UC-INCR-MKT-004",
  "run_id": "20260423T032826Z",
  "approved_by": "platform-admin",
  "note": "Governance sign-off completed after strict-run review.",
  "accept_all_warnings": true,
  "warning_rationale": "Non-blocking warning accepted for this release.",
  "force": false
}
```

Response highlights:

1. Returns updated `deployment_readiness` block.
2. Includes accepted warning names and monitoring report path.
3. Writes/updates `artifacts/governance_approvals.json` audit ledger.

Common errors:

1. `400 invalid_body` for schema/validation issues (unknown fields, missing IDs, blockers)
2. `500 governance_approval_failed` for unexpected write/runtime failures

## Inference Serving

### `POST /api/inference/online`

Runs one-record scoring and activation mapping with strict request validation.

Body:

```json
{
  "use_case_id": "UC-NBA-RET-001",
  "registry_stage": "auto",
  "seed": 101,
  "record": {
    "customer_id": "CUST-001",
    "risk_score": 0.72,
    "value_score": 0.64,
    "score_ts": "2026-04-22T10:30:00Z"
  }
}
```

Response highlights:

1. Includes top-level `model_version`, `model_backend`, `registry_stage`, and `registry_run_id`.
2. Returns `prediction` and `activation` objects plus contract metadata.
3. `registry_stage` supports `auto|candidate|approved|prod`.

Common errors:

1. `400 invalid_body` for schema/type/field validation failures
2. `500 inference_failed` for runtime execution errors

### `POST /api/inference/batch`

Runs multi-record scoring and activation mapping with strict request validation.

Body:

```json
{
  "use_case_id": "UC-INCR-MKT-004",
  "registry_stage": "auto",
  "seed": 101,
  "records": [
    {
      "campaign_id": "CMP-001",
      "test_window": "2026-W10",
      "treated_customers": 2400,
      "control_customers": 800,
      "treated_conversions": 312,
      "control_conversions": 92,
      "aov": 104.5,
      "campaign_cost": 18500.0
    }
  ]
}
```

Response highlights:

1. Includes top-level `model_version`, `model_backend`, `registry_stage`, and `registry_run_id`.
2. Returns `predictions` and `activations` arrays with per-use-case output contracts.
3. Includes contract metadata in `output_contract.fields` and `activation_contract.fields`.

Common errors:

1. `400 invalid_body` for schema/type/field validation failures
2. `500 inference_failed` for runtime execution errors

### `GET /api/contracts/inference`

Exports use-case-specific JSON schemas for:

1. online request payloads
2. batch request payloads
3. online response payloads
4. batch response payloads

Useful for frontend/backend contract-driven integration without parsing server code.

### `GET /api/openapi.json`

Exports an OpenAPI-style spec for inference and schema endpoints.

Notes:

1. Includes `oneOf` request/response schemas for all four use cases.
2. Includes shared `ApiError` schema used by error responses.

## Run History + Registry

### `GET /api/run-history`

Use-case-specific run comparisons for KPI/status/stage deltas.

Query params:

1. `use_case_id` (required)
2. `limit` (default: `6`, max internally bounded)
3. `status` (`all|pass|fail`)
4. `infra` (`all|local|oss`)
5. `baseline` (`latest|previous|<run_id>`)

Common errors:

1. `400 missing_query_param` when `use_case_id` is missing
2. `400 invalid_query` for invalid `limit/status/infra`

### `GET /api/runs`

Run-registry listing backed by `artifacts/.run_registry_index.json`.

Query params:

1. `use_case_id` (optional)
2. `limit` (default `50`)
3. `offset` (default `0`)
4. `status` (`all|pass|fail`)
5. `infra` (`all|local|oss`)
6. `seed` (optional integer)
7. `sort` (`asc|desc`)
8. `q` (optional text search)

Common errors:

1. `400 invalid_query` for invalid typed/enum filters

### `GET /api/runs/<use_case_id>/<run_id>`

Returns one run summary (`summary.json`) for business/technical drilldown.

Common errors:

1. `400 invalid_path`
2. `404 run_not_found`

### `GET /api/runs/<use_case_id>/<run_id>/stages`

Returns detailed stage-level technical evidence (inputs, outputs, artifact existence).

Common errors:

1. `400 invalid_path`
2. `404 run_not_found`

### `GET /api/runs/<use_case_id>/<run_id>/data-quality`

Returns a compact governance view for one run with only data-quality blockers and warnings.

Response focus:

1. `data_quality_status` and `data_quality_mode`
2. `blocker_count` / `warning_count`
3. `blocker_names` / `warning_names`
4. compact `blockers` / `warnings` rows (`table`, `name`, `reason`, `violation_count`, `severity`)

Common errors:

1. `400 invalid_path`
2. `404 run_not_found`

## Portfolio Rollup

### `GET /api/portfolio/summary`

Cross-use-case KPI and stage-health rollup for business portfolio views.

Query params:

1. `status` (`all|pass|fail`)
2. `infra` (`all|local|oss`)
3. `sort` (`asc|desc`)
4. `limit_per_use_case` (default `1`, max internally bounded)

Common errors:

1. `400 invalid_query`

## Quick Curl Examples

```bash
curl -s http://127.0.0.1:8080/api/health
curl -s "http://127.0.0.1:8080/api/runs?use_case_id=UC-NBA-RET-001&status=all&infra=all&limit=5"
curl -s "http://127.0.0.1:8080/api/runs/UC-NBA-RET-001/<run_id>/stages"
curl -s "http://127.0.0.1:8080/api/runs/UC-NBA-RET-001/<run_id>/data-quality"
curl -s "http://127.0.0.1:8080/api/portfolio/summary?status=all&infra=all&sort=desc&limit_per_use_case=1"
curl -s -X POST http://127.0.0.1:8080/api/inference/online -H "Content-Type: application/json" -d '{"use_case_id":"UC-NBA-RET-001","record":{"customer_id":"CUST-001","risk_score":0.72,"value_score":0.64,"score_ts":"2026-04-22T10:30:00Z"}}'
curl -s -X POST http://127.0.0.1:8080/api/inference/batch -H "Content-Type: application/json" -d '{"use_case_id":"UC-CHURN-RET-002","records":[{"customer_id":"CUST-002","recency_norm":0.67,"engagement_norm":0.32,"support_ticket_norm":0.24,"score_ts":"2026-04-22T10:40:00Z"}]}'
curl -s http://127.0.0.1:8080/api/contracts/inference
curl -s http://127.0.0.1:8080/api/openapi.json
```
