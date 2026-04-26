# Technical README: AI/ML Architecture

This document explains the technical architecture through an AI/ML lens. It is intended for architects, ML engineers, data engineers, platform engineers, and technical reviewers who need to understand how the app runs, how evidence is produced, and how the standalone runtime can evolve into an enterprise MLOps architecture.

## Architecture Thesis

The platform uses one governed AI/ML runtime for multiple decision models. Each model workflow is selected through metadata and YAML contracts, not page-specific logic.

The runtime is designed around four principles:

1. **Contract-driven AI**: each use case declares entities, source tables, features, outputs, KPIs, and validation expectations.
2. **Reusable ML pipeline**: all use cases pass through the same eight-stage execution path.
3. **Inspectable evidence**: every run writes artifacts, metrics, manifests, validation gates, and governance summaries.
4. **Profile-driven integration**: standalone execution works locally; optional integrations can be enabled without changing model contracts.

## AI/ML Use Cases

| Use Case | Model Lens | Decision Output |
| --- | --- | --- |
| `UC-NBA-RET-001` | TensorFlow next-best-action uplift decisioning | Ranked retention action pack |
| `UC-CHURN-RET-002` | TensorFlow churn propensity and save strategy | Prioritized retention treatment plan |
| `UC-MMM-PLN-003` | Bayesian media mix optimization | Channel budget reallocation plan |
| `UC-INCR-MKT-004` | Causal incrementality measurement | Campaign scale, pause, or retest decision |

## Runtime Flow

```text
Data Sources
-> Ingestion + Event Bus
-> Raw Storage + Curated Warehouse
-> Identity Resolution + Customer 360
-> Feature Layer
-> Model Layer
-> Serving + Activation
-> Monitoring + Governance
```

## Component Mapping

```text
use_cases/configs/*.yaml
  -> stack/layers/data_sources.py
  -> stack/layers/ingestion_event_bus.py
  -> stack/layers/storage.py
  -> stack/layers/identity_360.py
  -> stack/layers/features.py
  -> stack/layers/modeling.py
  -> stack/layers/serving_activation.py
  -> stack/layers/monitoring_governance.py
  -> stack/orchestrator.py
  -> artifacts/<use_case_id>/<run_id>/*
```

## Eight ML Stages

### 1. Data Sources

Loads or generates the source records declared by the selected use-case contract. The standalone path can run synthetic data; production-style runs can require real CSV datasets from `data/production`.

Evidence produced:

1. Source table counts
2. Source metadata
3. Contract seed and runtime mode

### 2. Ingestion + Event Bus

Normalizes source records into topic-like event streams. In standalone mode this is file-backed. In integrated runtime mode the same boundary can mirror Kafka-style behavior.

Evidence produced:

1. Topic JSONL artifacts
2. Event counts
3. Source-to-topic traceability

### 3. Raw Storage + Curated Warehouse

Persists raw evidence and creates curated records for downstream ML stages. This separates auditability from model-ready usability.

Evidence produced:

1. Raw event artifacts
2. Curated record artifacts
3. Warehouse-ready canonical shape

### 4. Identity Resolution + Customer 360

Resolves source records into a stable analytical entity view before features are built. Standalone mode uses deterministic logic; the enterprise path can introduce Splink-style probabilistic resolution.

Evidence produced:

1. Identity map
2. Resolved records
3. Entity-level traceability

### 5. Feature Layer

Builds model-ready features with consistent names, types, and calculation rules. The enterprise path can map this stage to dbt and Feast-style feature store artifacts.

Evidence produced:

1. Feature rows
2. Feature schema
3. Offline feature-store export path

### 6. Model Layer

Runs the selected model backend and writes predictions, metrics, diagnostics, and model manifest artifacts.

Supported model strategy:

1. TensorFlow-first path for next-best-action and churn.
2. PyMC-style Bayesian path for media mix optimization.
3. EconML/DoWhy-style causal path for incrementality.
4. Deterministic fallback paths for standalone portability.

Evidence produced:

1. Model predictions
2. Model metrics
3. Model manifest
4. Training report
5. MLflow-compatible lineage artifact

### 7. Serving + Activation

Converts model outputs into activation-ready payloads that downstream decisioning or campaign systems can consume.

Evidence produced:

1. Activation payloads
2. Decision policy fields
3. Model version and run trace

### 8. Monitoring + Governance

Validates data quality, model checks, deployment readiness, scientific governance metadata, and runtime health.

Evidence produced:

1. Monitoring report
2. Validation gates
3. Deployment-readiness score
4. Scientific-governance metadata
5. Prometheus-style metrics

## Runtime Profiles

| Profile | Purpose | External Services Required |
| --- | --- | --- |
| Standalone AI Runtime | Runs locally with file-backed artifacts and synthetic or CSV data. | None |
| Integrated AI Runtime | Mirrors selected boundaries into Kafka, Postgres, and MinIO through the OSS profile. | Optional |
| Enterprise Integration Profile | Emits or connects optional enterprise integration evidence for MLflow, Feast, Splink, Airflow, Keycloak, monitoring, and metrics. | Optional |

The default standalone app can run without deployment dependencies. Optional services are profile-driven and should be enabled only when the environment supports them.

## Model Evidence And Artifacts

Every full-stack run writes a run folder:

```text
artifacts/<use_case_id>/<run_id>/
```

Important artifacts include:

```text
summary.json
models/predictions.json
models/metrics.json
models/manifest.json
models/*_training_report.json
serving_activation/activation_payloads.json
monitoring_governance/report.json
enterprise_hardening/mlflow_lineage.json
telemetry/stage_events.jsonl
```

UI-facing paths are normalized to repo-relative strings such as:

```text
artifacts/UC-NBA-RET-001/20260425T214139Z/summary.json
```

## Live API Surface

The live server is implemented in `scripts/ui_live_server.py`.

Common endpoints:

```text
GET  /api/health
GET  /api/view-model
GET  /api/run-history
GET  /api/runs
GET  /api/runs/<use_case_id>/<run_id>
GET  /api/runs/<use_case_id>/<run_id>/stages
GET  /api/runs/<use_case_id>/<run_id>/data-quality
GET  /api/portfolio/summary
GET  /api/artifacts/download?path=...
GET  /metrics
POST /api/run
POST /api/simulation/session
POST /api/inference/online
POST /api/inference/batch
```

See [API Reference](API_REFERENCE.md) for request/response contracts.

## UI Architecture

The UI is in `ui/experience/` and uses browser-native HTML, CSS, and JavaScript.

Primary pages:

1. `business-home.html`: AI model portfolio and presentation entry.
2. `business-exec-summary.html`: portfolio-level AI impact summary.
3. `workbench.html`: model workflow and evidence workbench.
4. `index.html`: AI/ML architecture presentation.

Runtime data sources:

1. Live API through `/api/view-model`, `/api/run-history`, `/api/runs`, and `/api/portfolio/summary`.
2. Static snapshot fallback through `ui/data/view_model.json`.

## Model Registry And Lifecycle

Every full-stack run can register a candidate model entry under:

```text
artifacts/model_registry/registry.json
```

Lifecycle commands:

```bash
python3 -m pipelines.cli model-registry-list
python3 -m pipelines.cli model-readiness --use-case UC-NBA-RET-001 --run-id <run_id>
python3 -m pipelines.cli model-promote --use-case UC-NBA-RET-001 --run-id <run_id> --to approved
python3 -m pipelines.cli model-promote --use-case UC-NBA-RET-001 --run-id <run_id> --to prod
```

Readiness checks include run status, deployment readiness, artifact presence, model version, and optional strict-backend enforcement.

## Enterprise Integration Lens

The enterprise profile is intentionally optional. It is used to show architecture readiness without making standalone execution dependent on external services.

Integration paths:

1. **MLflow**: model lineage and experiment tracking artifact.
2. **Feast**: feature-store registry, feature view, and offline feature export.
3. **Splink**: probabilistic identity-resolution readiness path.
4. **Airflow**: orchestration metadata and DAG readiness.
5. **Keycloak**: OIDC and role model readiness.
6. **Prometheus**: metrics endpoint for runtime and run health.
7. **Data-quality artifacts**: validation expectations and monitoring summaries.

## Running Locally

```bash
make install
make standalone
```

Open:

```text
http://127.0.0.1:8080/ui/experience/index.html
```

Run tests:

```bash
make test
```

Run full quality checks:

```bash
make ci-quality
```

## Design Notes

1. Keep use-case behavior in contracts and model modules, not page-specific UI logic.
2. Keep artifact paths repo-relative for portability.
3. Keep standalone runtime dependency-light.
4. Treat enterprise services as optional adapters or integration targets.
5. Prefer adding evidence artifacts over adding presentation-only claims.
