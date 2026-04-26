# Project Scope And Status

<!-- status:auto:start -->
## 0) Live Snapshot (Auto-Generated)

- Synced at (UTC): `2026-04-25T05:07:58.348360Z`
- Artifacts root: `artifacts`
- Baseline generated_at_utc: `2026-04-23T22:04:25.273029Z`
- Latest runs: pass=`4` fail=`0`

| Use Case | Run ID | Run Status | DQ | Deployment | Registry Stage | Backend | Approved By | Approved At (UTC) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| UC-CHURN-RET-002 | 20260423T032819Z | pass | pass | ready | prod | tensorflow | platform-admin | 2026-04-23T06:04:31Z |
| UC-INCR-MKT-004 | 20260423T220328Z | pass | pass | ready | prod | econml_dowhy | platform-admin | 2026-04-23T22:04:09.917960Z |
| UC-MMM-PLN-003 | 20260423T032828Z | pass | pass | ready | prod | pymc_marketing_adapter | platform-admin | 2026-04-23T06:04:31Z |
| UC-NBA-RET-001 | 20260423T032830Z | pass | pass | ready | prod | tensorflow | platform-admin | 2026-04-23T06:04:31Z |

_This section is auto-managed by `pipelines.cli sync-project-status`._
<!-- status:auto:end -->

Last updated (UTC): 2026-04-25T05:07:58.346691Z

## 1) Mission

Build a standalone, open-source Customer Data Platform simulation app that demonstrates four marketing science scenarios end-to-end with synthetic data and explainable architecture flow.

Use cases in scope:

1. `UC-NBA-RET-001` Next Best Action for Retention.
2. `UC-CHURN-RET-002` Churn Prediction and Retention Actioning.
3. `UC-MMM-PLN-003` Media Mix Modeling and Budget Optimization.
4. `UC-INCR-MKT-004` Campaign Incrementality Measurement.

## 2) Locked Product Scope

1. Keep the contract-driven 8-stage pipeline shape from ingestion through governance.
2. Support business and technical personas in one application flow.
3. Keep runtime open-source-only for demo path.
4. Keep runs deterministic and reproducible via synthetic scenario presets.

## 3) Delivered Capabilities (Current)

### 3.1 Runtime and Orchestration

1. `synthetic_only` runtime mode is implemented.
2. Scenario preset library is implemented with deterministic seeds.
3. Failure-injection controls are implemented (`dq_fail`, `schema_fail`, `backend_unavailable`).
4. One-command standalone launch is implemented (`make standalone`, `scripts/standalone_app.py`).
5. Standalone Make targets now prefer project venv Python when available.

### 3.2 API and Simulation Control Plane

1. Live API includes simulation session endpoints:
   - `POST /api/simulation/session`
   - `GET /api/simulation/session/<session_id>`
   - `POST /api/simulation/session/<session_id>/run-next`
   - `POST /api/simulation/session/<session_id>/run-all`
   - `POST /api/simulation/session/<session_id>/reset`
2. Existing run/inference/governance endpoints remain available.

### 3.3 UI Experience

1. Runtime mode selector, scenario preset selector, and failure injection controls are available.
2. Stage simulation controls are available in the UI (`run next`, `run all`, `reset`).
3. Business and technical walkthrough framing remains in place.
4. Business-first flow entry is available in `business-home`, and all 4 flows are delivered through Workbench scenario deep links.
5. Business pages now include a strict 3-step narrative (`Input -> Recommendation -> Impact`) with reduced on-screen elements and guided cross-flow navigation.
6. Executive summary page is available for one-page leadership readout with live data and print/PDF output.
7. Guided business flow is now consolidated in Workbench scenario/persona/step navigation for all 4 flows.
8. Unified left-navigator Workbench page is available with low-scroll scenario/persona/step navigation for both business and technical users.
9. `index.html` is now rewritten as `Architecture Story Mode` with a left-rail technical walkthrough (`stage rail -> data in/out -> components -> evidence`) powered by live run/simulation stage payloads.

### 3.4 OSS Transparency and Evidence

1. OSS inventory artifacts are generated in-repo:
   - `docs/OSS_INVENTORY.json`
   - `docs/OSS_LICENSE_SUMMARY.md`
2. OSS inventory API endpoint is available at `GET /api/oss-inventory`.
3. Stage telemetry/evidence is persisted in run outputs.

### 3.5 Product-Like Enterprise Hardening

1. Architecture Story Mode includes a visible `Standalone / Product-Like` app profile selector.
2. Enterprise hardening readiness is profile-aware via `GET /api/enterprise-hardening?profile=standalone|product_like`.
3. Lightweight hardening artifacts are generated for backend runs:
   - MLflow-compatible lineage export.
   - Great Expectations-compatible data-quality export.
   - Evidently-compatible monitoring summary export.
4. Prometheus-compatible runtime/run metrics are available at `GET /metrics`.
5. Feast, Splink, Airflow, and Keycloak remain optional and profile-driven.

## 4) Validation Snapshot

1. Latest full-suite test result: `113 passed, 4 skipped`.
2. New feature suites for synthetic mode, scenario library, simulation APIs, and UI assets are passing.
3. Test source currently contains `102` test functions (some are parametrized).
4. Standalone smoke validation passed: `make smoke-standalone` (`/api/health`, `/api/oss-inventory`, simulation `run-next`, `run-all`, `reset`).

## 5) Pending / Next Enhancements

All requested enhancements `E1..E5` are completed in the current wave.

### 5.1 Enhancement Backlog Tracker

1. `E1` Pause/Resume simulation controls — `done`
2. `E2` Scenario comparison KPI delta drilldown UX — `done`
3. `E3` Artifact explorer filters/download/trace links — `done`
4. `E4` Optional enterprise-hardening modules surface (MLflow/Feast/Splink/Airflow/Keycloak) — `done`
5. `E5` CI automation for status-doc refresh after milestone runs — `done`

### 5.2 Business UI Simplification Tracker

All requested business-first flow storyboard capabilities are completed in the current wave.

1. `B1` Business home command center page — `done`
2. `B2` Next Best Action storyboard page (`Input -> Recommendation -> Impact`) — `done`
3. `B3` Churn storyboard page (`Input -> Recommendation -> Impact`) — `done`
4. `B4` MMM storyboard page (`Input -> Recommendation -> Impact`) — `done`
5. `B5` Incrementality storyboard page (`Input -> Recommendation -> Impact`) — `done`
6. Consolidation note: standalone per-flow storyboard pages were retired in favor of a single Workbench shell (`R17` cleanup).

### 5.3 Business Live-Data Wiring Tracker

Progressive wiring of business storyboard pages to live API data (`/api/run-history`, `/api/runs`, `/api/artifacts/download`) one flow at a time.

1. `L1` NBA storyboard live API integration — `done`
2. `L2` Churn storyboard live API integration — `done`
3. `L3` MMM storyboard live API integration — `done`
4. `L4` Incrementality storyboard live API integration — `done`

### 5.4 Business UX Refinement Tracker

Decision-first simplification wave for business users across home + all flow pages.

1. `R1` Business home guided demo path and narrative sequencing — `done`
2. `R2` Decision summary cards (`Decision Now`, `Why This Matters`, `How To Read`) on all 4 flow pages — `done`
3. `R3` Guided journey navigation (`Back` / `Next`) across all 4 flow pages — `done`
4. `R4` Plain-language KPI and evidence copy cleanup for non-technical audience — `done`
5. `R5` Live-data driven business copy integration for summary cards across all 4 flows — `done`
6. `R6` Phase-2 page simplification to strict one-page business narrative (`Step 1 -> Step 2 -> Step 3`) across all 4 flow pages — `done`
7. `R7` Reduced visual clutter by consolidating KPIs into step cards and simplifying action controls — `done`
8. `R8` Fixed churn storyboard live-data decision-summary hydration bug (`highShare` initialization order) — `done`
9. `R9` Business Exec mode page (`single-screen summary + printable export view`) wired to live APIs across all 4 flows — `done`
10. `R10` Guided self-navigation mode + modern storytelling shell across all 4 business flow pages — `done`
11. `R11` Unified Workbench page (`left navigator + low-scroll business/technical step view`) wired to live API run/stage/data-quality endpoints — `done`
12. `R12` Workbench cleanup pass to remove non-essential UI chrome and reduce content density/scroll load — `done`
13. `R13` Technical deep-dive expansion in Workbench (`contract + component matrix + stage I/O evidence + governance artifact explorer`) — `done`
14. `R14` Visual style harmonization (`Business Home`, `Executive Summary`, `Technical App`) to match Workbench design language — `done`
15. `R15` Navigation and deep-link consistency pass (all business flow CTAs route to Workbench scenario links) — `done`
16. `R16` Technical app rewrite to storytelling-first `Architecture Story Mode` (`index.html`) with guided stage narrative and plain-language under-the-hood flow — `done`
17. `R17` Legacy UI cleanup: removed unused per-flow storyboard pages/scripts and kept Workbench + Architecture Story Mode as canonical surfaces — `done`
18. `R18` Artifact snapshot cleanup: consolidated `artifacts*` folders into a single baseline snapshot at `artifacts/` — `done`

### 5.5 Enterprise Hardening Product Mode Tracker

1. `H1` Visible `Standalone / Product-Like` app profile selector — `done`
2. `H2` Lightweight integrations (`MLflow` lineage, DQ/monitoring compatibility artifacts, `/metrics`) — `done`
3. `H3` Heavier services (`Feast`, `Splink`, `Airflow`, `Keycloak`) optional and profile-driven — `done`

## 6) Context Recovery Pointers

If context window is lost, restore in this order:

1. `docs/SCOPE_LOCK.md`
2. `docs/STANDALONE_APP_IMPLEMENTATION_PLAN.md`
3. `PROJECT_SCOPE_AND_STATUS.md`
4. `docs/OSS_INVENTORY.json`
5. `docs/OSS_LICENSE_SUMMARY.md`

## 7) Quick Command Cheat Sheet

```bash
make standalone
make standalone-fast
make smoke-standalone
RUN_OSS_TESTS=1 ./.venv311/bin/python -m pytest -q
./.venv311/bin/python -m pipelines.cli sync-project-status --artifacts-root artifacts --status-file PROJECT_SCOPE_AND_STATUS.md
```

## 8) Notes

1. This workspace currently has no `.git` directory at the project root, so commit history/branch state cannot be reconstructed here.
2. The auto-managed snapshot section should only be changed via `pipelines.cli sync-project-status`.
3. Completed-task ledger confirmed and recorded: `E1..E5`, `B1..B5`, `L1..L4`, `R1..R18` are all `done`.
