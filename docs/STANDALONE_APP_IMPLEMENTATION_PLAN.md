# Standalone App Implementation Plan

This document captures the implementation plan and delivery status for the standalone, open-source simulation app.

## 1) Product Intent

Build a standalone app that runs end-to-end marketing science flows using synthetic data and explains value to two audiences:

1. Business users: understandable decision flow and KPI story.
2. Technical users: step-by-step component simulation with artifacts and traceability.

## 2) Non-Negotiable Requirements

1. All components used in the app must be open source.
2. The app must clearly explain business flow and outcomes.
3. The app must let technical users inspect how each stage runs in sequence.

## 3) Baseline Before This Implementation Wave

1. Contract-driven orchestration for 4 use cases.
2. 8-layer architecture execution pipeline.
3. Synthetic data generation fallback by use case.
4. Business/technical UI modes.
5. Live API server with run, run-history, inference, and governance endpoints.
6. OSS profile support (Kafka, Postgres, MinIO) for simulation.
7. Automated test suite with OSS integration coverage.

## 4) Gap Closure Status (As Of 2026-04-24)

Closed gaps:

1. `synthetic_only` runtime mode implemented.
2. Guided stage-by-stage execution controls implemented (`run-all`, `run-next`, `reset`).
3. In-app open-source component/license transparency implemented.
4. Deterministic scenario preset library implemented for the four use cases.
5. Failure-injection simulation controls implemented.
6. One-command standalone launcher implemented.
7. Stage evidence surfaced through simulation session telemetry and artifacts.

## 5) Phase Delivery Status

### Phase 1 - Standalone Synthetic Product Mode

Status: Completed.

Delivered:

1. Runtime mode `synthetic_only` with synthetic-data-first enforcement.
2. One-command standalone startup (`make standalone` and `make standalone-fast`).
3. Seeded scenario presets for all 4 use cases.
4. Tests validating synthetic-only behavior and deterministic scenario execution.

### Phase 2 - Guided Simulation UX

Status: Completed (baseline scope).

Delivered:

1. Stage runner API with session lifecycle and incremental execution.
2. UI simulation controls for run-next, run-all, reset.
3. Runtime/scenario/failure control panel in the experience UI.
4. Stage-level evidence payloads in simulation responses.

### Phase 3 - OSS Transparency and Demo Hardening

Status: Completed (baseline scope).

Delivered:

1. OSS component/license inventory generator and published artifacts.
2. API endpoint for OSS inventory and UI rendering support.
3. Failure-injection controls for DQ/schema/backend outage simulations.
4. Stage telemetry and governance evidence hardening.
5. Regression tests for the new API/UI/runtime surfaces.

## 6) Workstream Status

### A. Runtime and Orchestration

1. `synthetic_only` mode, scenario presets, and failure-injection plumbing are implemented.
2. Simulation sessions and deterministic stage execution are implemented.

### B. UI and Experience

1. Simulation controls and persona-oriented detail views are implemented in current UI stack.
2. Runtime mode and scenario preset selection are exposed in the app.

### C. OSS and Compliance

1. OSS component/license manifest generation is implemented.
2. In-app OSS inventory endpoint and UI panel are implemented.

### D. Quality and Testing

1. Tests were added for synthetic-only behavior, scenario presets, live-server simulation APIs, and UI assets.
2. Latest full-suite status: `113 passed, 4 skipped`.

## 7) Tracking Checklist

- [x] Phase 1 complete
- [x] Phase 2 complete
- [x] Phase 3 complete
- [x] Standalone synthetic app demo-ready
- [x] Persona walkthroughs demo-ready
- [x] OSS compliance artifacts published

## 8) Component Technology Matrix (Current vs Chosen)

This section defines technology choices to stay close to real product design while preserving standalone synthetic-first operation.

| Component | Current Technology | Chosen Technology (Target Design) | Why This Choice | Delivery Phase |
| --- | --- | --- | --- | --- |
| 1. Data Sources | Python synthetic generators + optional CSV loader | Keep Python generators as primary in `synthetic_only`; optional Airbyte OSS connectors for non-synthetic mode | Deterministic demos first, realistic connector path later | Completed baseline + optional Phase 3 extension |
| 2. Ingestion + Event Bus | In-memory LocalEventBus, optional Kafka mirror | Apache Kafka as canonical bus in product-like mode; keep LocalEventBus for standalone fallback | Supports both local simulation and enterprise event-driven design | Completed baseline + optional infra-hardening extension |
| 3. Raw Storage | JSON/JSONL artifacts, optional MinIO snapshot | MinIO object storage + Parquet artifacts (retain JSON for demo readability) | Product-like object storage with developer-friendly inspectability | Completed baseline + optional storage extension |
| 4. Curated Warehouse | JSON curated files + Postgres JSONB mirror | PostgreSQL as primary curated store + dbt for transforms | Mature OSS SQL warehouse path without over-complexity | Completed baseline + optional dbt extension |
| 5. Identity + Customer 360 | Deterministic mapper | Splink (DuckDB backend) with deterministic + probabilistic matching modes | Realistic identity-resolution design for technical demos | Optional enhancement |
| 6. Feature Layer | Python feature builders | Feast (offline-first) + dbt-produced feature tables | Standard OSS feature-store pattern close to production ML platforms | Optional enhancement |
| 7. Model Training Runtime | Python model modules; TensorFlow/PyMC/EconML optional backends | Keep existing model modules; add MLflow tracking/artifacts and registry integration | Preserves current domain logic while adding product-grade experiment lineage | Completed baseline + optional MLflow extension |
| 8. Pipeline Orchestration | Custom orchestrator in Python | Keep orchestrator for stage simulation; add optional Airflow DAG wrapper for scheduled product-like runs | Stage-by-stage simulation remains simple; scheduled operations become realistic | Completed baseline + optional Airflow extension |
| 9. Serving + Activation | Custom API handler + payload file generation | FastAPI service layer + connector adapters (webhook/queue); keep file payload sink for demo mode | Production-style API boundary with demo-safe fallback output | Completed baseline + optional connector extension |
| 10. Model Serving Interface | In-process model execution in API | Keep in-process for standalone; optional BentoML deployment profile for isolated model services | Supports demo simplicity and real-service topology when needed | Completed baseline + optional BentoML extension |
| 11. Monitoring + Governance | Custom validation gates + governance ledger JSON | Keep existing gates; augment with Great Expectations (DQ), Evidently (drift), Prometheus/Grafana (ops metrics) | Extends current governance foundation with product-grade observability | Completed baseline + optional observability extension |
| 12. Run Metadata + Registry | File-based run summaries + custom registry JSON | Keep custom registry as system of record; mirror key metadata into Postgres for query APIs | Minimal migration risk and better operational queryability | Completed baseline + optional metadata extension |
| 13. UI Experience | Static HTML/CSS/JS | Keep current UI stack; continue incremental enhancements in same app shell | Fastest path to value without frontend rewrite risk | Completed baseline |
| 14. Auth + Access Control | None | Keycloak (OIDC) + role-based API guards for multi-user environments | Needed for real product posture; not required for local single-user mode | Optional enhancement |
| 15. OSS Compliance | Generated OSS inventory + license summary docs | Keep generated docs plus API/UI inventory view; optionally add SBOM toolchain | Enforces open-source-only requirement with auditability | Completed baseline + optional SBOM extension |

## 9) Deployment Profiles (Design Contract)

### Profile A: Standalone Simulation (Default)

1. Synthetic-only mode.
2. LocalEventBus + local artifacts.
3. Single command startup for UI + API.
4. No external infra required.

### Profile B: Product-Like OSS Simulation (Optional)

1. Kafka + Postgres + MinIO enabled.
2. Same flows, same contracts, same UI.
3. Stage-by-stage evidence still visible.
4. Used for technical architecture demonstrations.

## 10) Decision Rules For Future Component Choices

1. Must be open-source with compatible license.
2. Must preserve reproducible local standalone mode.
3. Must support contract-driven architecture and stage evidence.
4. Must include fallback path for demos when external service is unavailable.

## 11) Next Enhancements (Post-Baseline)

1. Add pause/resume controls and deeper scenario comparison UX.
2. Add richer artifact explorer interactions and cross-stage trace linking.
3. Add optional enterprise-hardening modules (MLflow, Feast, Splink, Airflow, Keycloak).
4. Add CI pipeline that auto-refreshes status docs after milestone test runs.
5. Add business-first storyboard pages for all 4 flows with one consistent page narrative.

### 11.1 Execution Tracker

1. `E1` Pause/Resume simulation controls — `done`
2. `E2` Scenario comparison KPI delta drilldown UX — `done`
3. `E3` Artifact explorer filters/download/trace links — `done`
4. `E4` Optional enterprise-hardening module surface — `done`
5. `E5` CI status-doc refresh automation — `done`

### 11.2 Business UI Storyboard Tracker

1. `B1` Business home command center page — `done`
2. `B2` Next Best Action business storyboard page — `done`
3. `B3` Churn business storyboard page — `done`
4. `B4` MMM business storyboard page — `done`
5. `B5` Incrementality business storyboard page — `done`

### 11.3 Business Live-Data Wiring Tracker

1. `L1` NBA storyboard live API integration — `done`
2. `L2` Churn storyboard live API integration — `done`
3. `L3` MMM storyboard live API integration — `done`
4. `L4` Incrementality storyboard live API integration — `done`

### 11.4 Business UX Refinement Tracker

1. `R1` Business home guided demo path and narrative sequencing — `done`
2. `R2` Decision summary cards on all 4 business flow pages — `done`
3. `R3` Guided journey navigation across all 4 business flow pages — `done`
4. `R4` Plain-language KPI/evidence copy cleanup for business audience — `done`
5. `R5` Live-data driven summary card copy across all 4 flows — `done`
6. `R6` Phase-2 strict 3-step business narrative layout across all 4 flow pages — `done`
7. `R7` Reduced page complexity by consolidating KPIs into step cards and simplifying action controls — `done`
8. `R8` Fixed churn storyboard live-data decision-summary hydration ordering bug — `done`
9. `R9` Business Exec mode page with single-screen summary + print/PDF export wired to live APIs — `done`
10. `R10` Guided Story Mode (`Guided/Show All`, step rail, Back/Next, autoplay, arrow-key navigation) across business-flow walkthroughs — `done`
11. `R11` Unified Workbench page (`left navigator + low-scroll business/technical step view`) wired to live run/stage/data-quality APIs — `done`
12. `R12` Workbench cleanup pass (remove non-essential UI chrome and reduce scroll-heavy sections) — `done`
13. `R13` Workbench technical deep-dive pass (`contract + component matrix + stage I/O evidence + governance artifact explorer`) — `done`
14. `R14` Workbench-style visual harmonization for `business-home`, `business-exec-summary`, and `index` pages — `done`
15. `R15` Navigation/deep-link consistency pass (scenario links standardized to Workbench query routes) — `done`
16. `R16` Storytelling-first rewrite of `index.html` into `Architecture Story Mode` with guided stage rail and plain-language technical narrative — `done`
17. `R17` UI consolidation cleanup: retired unused standalone per-flow storyboard pages/scripts and kept Workbench + Architecture Story Mode as canonical paths — `done`
18. `R18` Artifact consolidation cleanup: removed extra `artifacts*` folders and retained a single baseline snapshot root (`artifacts/`) — `done`

## 12) Completion Log

1. 2026-04-24: Implemented standalone synthetic mode, scenario preset library, failure-injection controls, simulation session APIs, standalone launcher, OSS inventory generation/endpoint, and UI wiring.
2. 2026-04-24: Implemented enhancement wave `E1..E5` (pause/resume, KPI drilldown comparison UX, artifact explorer upgrades, enterprise-hardening surface, CI status-doc refresh automation).
3. 2026-04-24: Regression coverage extended; latest full suite reported `111 passed, 4 skipped`.
4. 2026-04-24: Implemented business-first storyboard wave `B1..B5` (business home + NBA/Churn/MMM/Incrementality one-page flow storyboards).
5. 2026-04-24: Wired NBA business storyboard to live API data (`L1`) using latest run + artifact endpoints.
6. 2026-04-24: Wired Churn/MMM/Incrementality business storyboards to live API data (`L2..L4`) using latest run + artifact endpoints.
7. 2026-04-24: Completed business UX refinement wave (`R1..R5`) with decision-first summaries, guided flow navigation, and business-language copy improvements.
8. 2026-04-24: Completed business UX Phase-2 simplification (`R6..R8`) with strict 3-step page layouts, lower visual density, and churn live-hydration fix.
9. 2026-04-24: Added business executive summary view (`R9`) with one-page live portfolio readout and printable export workflow.
10. 2026-04-24: Recorded consolidated completed-task ledger snapshot confirming `E1..E5`, `B1..B5`, `L1..L4`, and `R1..R9` are all `done`.
11. 2026-04-24: Added guided storytelling mode (`R10`) for self-navigated, modern business walkthroughs across all four flow pages.
12. 2026-04-24: Added unified Workbench experience (`R11`) with left navigation and low-scroll business/technical mode switching.
13. 2026-04-24: Completed workbench cleanup (`R12`) by removing non-essential panels and reducing technical-content density.
14. 2026-04-24: Expanded Workbench technical mode (`R13`) with detailed contract context, component matrix, stage input/output evidence, and governance artifact exploration.
15. 2026-04-24: Harmonized `Business Home`, `Executive Summary`, and `Technical App` visual styling (`R14`) to the Workbench design language using shared theme overrides.
16. 2026-04-24: Standardized business flow navigation/deep links (`R15`) so flow CTAs and executive cards consistently open Workbench scenario routes.
17. 2026-04-25: Reworked `Technical App` into `Architecture Story Mode` (`R16`) with a guided stage-by-stage technical walkthrough (`what happens`, `data in/out`, `components`, `evidence`) driven by live run/simulation payloads.
18. 2026-04-25: Completed UI consolidation cleanup (`R17`) by removing unused per-flow storyboard HTML/JS files and updating tests/docs to the Workbench-first flow.
19. 2026-04-25: Completed artifact cleanup (`R18`) by consolidating generated `artifacts*` folders into a single baseline snapshot at `artifacts/` and updating defaults/docs.
20. 2026-04-25: Completed enterprise hardening product-mode build (`H1..H3`) with `Standalone / Product-Like` profile selection, profile-aware readiness, lightweight lineage/DQ/monitoring artifacts, `/metrics`, and profile-driven heavy services.

## 13) Change Log

1. 2026-04-24: Converted plan from forward-looking gaps to delivered status + post-baseline enhancement backlog.
2. 2026-04-24: Added component technology matrix and deployment profile contract.
3. 2026-04-24: Added business-first storyboard tracker and completion log for all four flow pages.
4. 2026-04-24: Added business live-data wiring tracker (`L1..L4`) and marked NBA (`L1`) complete.
5. 2026-04-24: Completed business live-data wiring tracker (`L1..L4`) for all four storyboard flows.
6. 2026-04-24: Added business UX refinement tracker (`R1..R5`) and marked all items complete.
7. 2026-04-24: Completed business UX Phase-2 refinement (`R6..R8`) for strict three-step narrative pages and reduced UI clutter.
8. 2026-04-24: Added business exec-mode enhancement (`R9`) for leadership one-page summary and print/PDF export.
9. 2026-04-24: Recorded completed-task ledger snapshot across enhancement, business storyboard, live-data, and refinement trackers.
10. 2026-04-24: Added guided story-mode enhancement (`R10`) for self-navigated business storytelling UX.
11. 2026-04-24: Added unified workbench enhancement (`R11`) for single-shell business + technical low-scroll navigation.
12. 2026-04-24: Added workbench cleanup enhancement (`R12`) for cleaner, lower-noise UI presentation.
13. 2026-04-24: Added technical deep-dive enhancement (`R13`) to make Workbench technical persona complete and self-guided.
14. 2026-04-24: Added Workbench-style visual harmonization enhancement (`R14`) for top-level business and technical entry pages.
15. 2026-04-24: Added navigation/deep-link consistency enhancement (`R15`) to route business flow links into Workbench scenario deep links.
16. 2026-04-25: Added `R16` to make `index.html` a storytelling-first technical architecture walkthrough (`Architecture Story Mode`) while preserving existing controls and API wiring.
17. 2026-04-25: Added `R17` to consolidate UI surfaces and remove unused legacy storyboard files.
18. 2026-04-25: Added `R18` to consolidate generated artifact folders into one canonical baseline snapshot root.
