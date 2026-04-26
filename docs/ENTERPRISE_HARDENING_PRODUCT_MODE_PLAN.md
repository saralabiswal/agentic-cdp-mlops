# Enterprise Hardening Product Mode Plan

This plan turns the existing enterprise-hardening readiness surface into an optional
product-like mode without making the standalone demo depend on external systems.

## Recommendation

Keep `standalone` as the default product experience and add a progressive
`product_like` mode. In `product_like`, each enterprise technology has an
implemented optional adapter. The adapter activates live package/service
behavior only when its package/configuration is present; otherwise the app
records adapter-ready artifacts and a clear dependency/configuration reason.

This keeps the current one-command demo reliable while letting technical users
see how the same architecture can graduate into a production-style stack.

## Current Implementation Status

1. Visible `Standalone / Product-Like` app profile selector is implemented in Architecture Story Mode.
2. `/api/enterprise-hardening` is profile-aware and separates lightweight built-ins from heavier profile-driven services.
3. Lightweight MLflow-compatible lineage, data-quality compatibility, and monitoring compatibility artifacts are generated with backend runs.
4. Prometheus-compatible metrics are exposed at `/metrics`.
5. Feast, Splink, Airflow, and Keycloak optional adapters are implemented and profile-driven.
6. Standalone runs do not require any of these optional dependencies.

## Existing Foundation

1. `/api/enterprise-hardening` already reports optional module readiness.
2. `ui/config/enterprise_hardening.json` already controls whether modules are enabled.
3. Architecture Story Mode already renders configured/installed/readiness state.
4. OSS profile already exercises Kafka, Postgres, and MinIO for a product-like path.

## Build Strategy

### Phase H1 - Architecture Toggle

Status: implemented.

1. Add a visible `Standalone / Product-Like` profile switch in Architecture Story Mode.
2. Call `/api/enterprise-hardening?profile=product_like` when product-like mode is selected.
3. Show each module as one of:
   - `implemented`
   - `planned`
   - `available`
4. Link each module to the pipeline stage it strengthens.

### Phase H2 - Lightweight Runtime Integrations

Status: implemented.

1. MLflow: log model metrics/artifacts when `mlflow` is installed and enabled.
2. Great Expectations-style DQ: keep current gates, but emit a compatibility artifact that mirrors expectation-suite output.
3. Evidently-style monitoring: emit drift/quality summary artifacts from existing validation metrics before requiring a live service.
4. Prometheus: expose a simple `/metrics` endpoint from the live UI/API server.

These add real value while keeping local setup small.

### Phase H3 - Product-Like Service Integrations

Status: implemented as optional adapters.

1. Feast: add feature definitions and an offline feature-store export path.
2. Splink: add optional identity-resolution adapter for Customer 360 when sample identity data is available.
3. Airflow: generate DAG wrappers for the existing CLI/orchestrator commands.
4. Keycloak: generate OIDC readiness/configuration artifacts.

These are useful architecture demonstrations, but they should remain optional.

### Phase H4 - Enterprise Deployment Controls

Status: partially implemented; defer enforcement until there is a multi-user deployment target.

1. Keycloak OIDC readiness and role model artifacts are implemented; request enforcement remains optional.
2. SBOM generation and stronger license policy gates.
3. Grafana dashboards backed by Prometheus metrics.

These should not block the standalone app.

## Suggested Priority

1. Build H1 first so users can turn product-like architecture visibility on in the app.
2. Build H2 next because MLflow-style lineage, DQ artifacts, monitoring summaries, and `/metrics` are lightweight and demo well.
3. Keep H3/H4 as opt-in profiles with clear setup instructions.

## Committed Build Order

1. Add visible `Standalone / Product-Like` mode in the app.
2. Wire lightweight real integrations first: MLflow lineage, DQ/monitoring artifacts, and `/metrics`.
3. Keep heavier services like Feast, Splink, Airflow, and Keycloak optional and profile-driven.

## Non-Goals

1. Do not require enterprise dependencies for `make standalone`.
2. Do not replace the current deterministic synthetic flow.
3. Do not make auth, external schedulers, or service meshes mandatory for local demos.

## How To Turn Product-Like Integrations On

The app has two layers of activation:

1. **Profile visibility:** controls what the UI and readiness API report.
2. **External tool execution:** uses real third-party packages/services when they are installed and configured.

Standalone remains dependency-free. If a package/service is missing, the run still succeeds and writes adapter artifacts that describe the integration path.

### Turn On The Product-Like Profile

Edit `ui/config/enterprise_hardening.json` and enable the modules under `profiles.product_like.modules`:

```json
{
  "profiles": {
    "product_like": {
      "modules": {
        "mlflow": true,
        "data_quality_artifacts": true,
        "monitoring_artifacts": true,
        "prometheus_metrics": true,
        "feast": true,
        "splink": true,
        "airflow": true,
        "keycloak": true
      }
    }
  }
}
```

Then start the app:

```bash
./.venv311/bin/python scripts/ui_live_server.py --host 127.0.0.1 --port 8091
```

Open Architecture Story Mode and select **Product-Like** in the App Profile dropdown.

### Run After Turning It On

Use the UI button **Run Open-Source Stack**, or run from the command line:

```bash
./.venv311/bin/python ui/adapter/build_view_model.py \
  --mode execute_backend \
  --use-case-id UC-NBA-RET-001 \
  --infra-profile oss \
  --seed 101
```

The run writes product-like artifacts under the run directory:

```text
artifacts/<use_case_id>/<run_id>/enterprise_hardening/product_like_integrations.json
artifacts/<use_case_id>/<run_id>/enterprise_hardening/mlflow_lineage.json
artifacts/<use_case_id>/<run_id>/enterprise_hardening/splink_identity_resolution.json
artifacts/<use_case_id>/<run_id>/feature_store/feast_registry.json
artifacts/<use_case_id>/<run_id>/orchestration/*_dag.py
artifacts/<use_case_id>/<run_id>/security/keycloak_oidc_readiness.json
```

### Optional Tool-Specific Activation

**MLflow**

Install/configure MLflow only if you want live MLflow logging. Without it, the app still writes `mlflow_lineage.json`.

```bash
./.venv311/bin/python -m pip install mlflow
```

Then run the app/run command again. If MLflow is available, the adapter attempts to log params, metrics, and artifacts.

**Feast**

Install Feast only if you want to move beyond the emitted offline feature-store contract.

```bash
./.venv311/bin/python -m pip install feast
```

The app always writes offline feature-store artifacts; Feast installation makes the dependency available for deeper product-like workflows.

**Splink**

Install Splink only if you want to execute real probabilistic identity matching later. The current adapter records the Splink-ready identity contract and keeps deterministic identity as the standalone fallback.

```bash
./.venv311/bin/python -m pip install splink
```

**Airflow**

Install/run Airflow only if you want to load the generated DAG into an Airflow deployment. The app does not require Airflow to run.

```bash
./.venv311/bin/python -m pip install apache-airflow
```

Use the generated DAG artifact from:

```text
artifacts/<use_case_id>/<run_id>/orchestration/
```

**Keycloak**

Set these environment variables only if you want to connect the readiness artifact to a real OIDC provider:

```bash
export CDP_KEYCLOAK_ISSUER="http://localhost:8080/realms/cdp"
export CDP_KEYCLOAK_CLIENT_ID="customer-data-platform"
```

The app continues to run without these variables; the artifact reports whether OIDC configuration is present.
