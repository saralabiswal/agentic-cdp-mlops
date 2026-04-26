# Scope Lock (Context Recovery Anchor)

Last updated (UTC): 2026-04-25T15:25:00Z  
Version: 1.19  
Status: Locked; baseline implementation complete, enhancement waves tracked

## 1) Purpose

This file is the canonical scope anchor for this project.  
If context is lost, restart from this document first.

## 2) Product Objective (Locked)

Build a standalone, open-source CDP simulation app that:

1. Runs 4 end-to-end marketing science scenarios with synthetic data.
2. Explains flow and outcomes clearly for business users.
3. Explains technical architecture stage-by-stage with inspectable artifacts.

## 3) Non-Negotiable Requirements (Locked)

1. All runtime components in the app path must be open source.
2. The app must run in standalone mode without external enterprise systems.
3. The app must support both:
   - business walkthrough mode
   - technical step-by-step simulation mode
4. Flows must be deterministic/reproducible from scenario seed.

## 4) Scenarios and ML Backend Choices (Locked)

1. `UC-NBA-RET-001` (Next Best Action): `tensorflow` backend (with deterministic fallback only when strict mode is off).
2. `UC-CHURN-RET-002` (Churn): `tensorflow` backend (with deterministic fallback only when strict mode is off).
3. `UC-MMM-PLN-003` (MMM): `pymc_marketing_adapter` backend.
4. `UC-INCR-MKT-004` (Incrementality): `econml_dowhy` backend.

## 5) Architecture Shape (Locked)

Keep the 8-stage contract-driven pipeline:

1. Data Sources
2. Ingestion + Event Bus
3. Raw Storage + Curated Warehouse
4. Identity Resolution + Customer 360
5. Feature Layer
6. Model Layer
7. Serving + Activation
8. Monitoring + Governance

## 6) Runtime Profiles (Locked)

1. Profile A (default): standalone synthetic simulation, no external infra required.
2. Profile B (optional): product-like OSS simulation using Kafka + Postgres + MinIO with same contracts and flows.

## 7) What Is Already Accepted As Implemented

1. 4 scenarios wired through shared orchestration.
2. 8-stage pipeline runnable with inspectable artifacts.
3. Live API and UI business/technical views.
4. OSS profile support (`local` and `oss`).
5. Automated tests and OSS integration coverage.

## 8) Implementation Status (Completed)

Phase 1 (Standalone Synthetic Product Mode):

1. `synthetic_only` runtime mode implemented and validated.
2. One-command standalone launcher delivered (`make standalone`, `scripts/standalone_app.py`).
3. Seeded deterministic scenario presets implemented for all 4 scenarios.
4. Synthetic-only determinism and runtime tests added.

Phase 2 (Guided Simulation UX):

1. Simulation session APIs implemented: create/get session, `run-next`, `run-all`, `reset`.
2. UI controls delivered for runtime mode, scenario preset, failure injection, and stage simulation control.
3. Business + technical walkthrough framing preserved in the same app shell.
4. Stage evidence/telemetry surfaced through artifacts and API payloads.

Phase 3 (OSS Transparency and Hardening):

1. OSS component/license inventory generation implemented.
2. In-app OSS inventory endpoint (`/api/oss-inventory`) implemented.
3. Failure-injection toggles implemented (`dq_fail`, `schema_fail`, `backend_unavailable`).
4. Demo telemetry hardening implemented with stage-level outputs.
5. Regression coverage added for new runtime/API/UI behaviors.

Validation snapshot:

1. Latest full-suite execution result: `113 passed, 4 skipped`.
2. Targeted synthetic/OSS feature tests passing.

## 9) Next Enhancements (Post-Lock Backlog)

1. Optional pause/resume control for long stage-by-stage walkthroughs.
2. Richer side-by-side scenario comparison view with KPI delta drilldowns.
3. Expanded artifact explorer UX (filters, download bundles, trace links).
4. Optional enterprise-hardening module surface (MLflow, Feast, Splink, Airflow, Keycloak).
5. Optional CI automation to refresh status docs after milestone test runs.
6. Business-first storyboard pages for all 4 flows with one consistent narrative layout.
7. Progressive live-data wiring for business storyboards (NBA, Churn, MMM, Incrementality).
8. Business UX refinement pass (decision-first summaries, guided flow navigation, plain-language copy).

Enhancement tracker:

1. `E1` Pause/Resume simulation controls — `done`
2. `E2` Scenario comparison KPI delta drilldown UX — `done`
3. `E3` Artifact explorer filters/download/trace links — `done`
4. `E4` Optional enterprise-hardening module surface — `done`
5. `E5` CI status-doc refresh automation — `done`

Business UI tracker:

1. `B1` Business home command center page — `done`
2. `B2` Next Best Action business storyboard page — `done`
3. `B3` Churn business storyboard page — `done`
4. `B4` MMM business storyboard page — `done`
5. `B5` Incrementality business storyboard page — `done`

Business live-data tracker:

1. `L1` NBA storyboard live API integration — `done`
2. `L2` Churn storyboard live API integration — `done`
3. `L3` MMM storyboard live API integration — `done`
4. `L4` Incrementality storyboard live API integration — `done`

Business UX refinement tracker:

1. `R1` Business home guided demo path and narrative sequencing — `done`
2. `R2` Decision summary cards on all 4 business flow pages — `done`
3. `R3` Guided journey navigation across all 4 business flow pages — `done`
4. `R4` Plain-language KPI/evidence copy cleanup for business audience — `done`
5. `R5` Live-data driven summary card copy across all 4 flows — `done`
6. `R6` Phase-2 strict 3-step business narrative layout across all 4 flow pages — `done`
7. `R7` Reduced page complexity by consolidating KPIs into step cards and simplifying action controls — `done`
8. `R8` Fixed churn storyboard live-data decision-summary hydration ordering bug — `done`
9. `R9` Business Exec mode page with one-screen summary + print/PDF export wired to live APIs — `done`
10. `R10` Guided Story Mode (`Guided/Show All`, step rail, Back/Next, autoplay, keyboard arrows) across business flow walkthroughs — `done`
11. `R11` Unified Workbench (`left navigator + low-scroll business/technical step view`) wired to live run/stage/data-quality APIs — `done`
12. `R12` Workbench cleanup pass (remove non-essential UI chrome and reduce scroll-heavy sections) — `done`
13. `R13` Workbench technical deep-dive pass (`contract + component matrix + stage I/O evidence + governance artifact explorer`) — `done`
14. `R14` Workbench-style visual harmonization for `Business Home`, `Executive Summary`, and `Technical App` pages — `done`
15. `R15` Navigation/deep-link consistency pass (business flow links routed to Workbench scenario query links) — `done`
16. `R16` Storytelling-first rewrite of `Technical App` to `Architecture Story Mode` with guided stage rail and plain-language technical walkthrough — `done`
17. `R17` UI consolidation cleanup: removed unused standalone per-flow storyboard HTML/JS files and standardized on Workbench + Architecture Story Mode — `done`
18. `R18` Artifact consolidation cleanup: removed extra `artifacts*` folders and retained a single baseline snapshot root at `artifacts/` — `done`

Enterprise hardening product-mode tracker:

1. `H1` Visible `Standalone / Product-Like` app profile selector — `done`
2. `H2` Lightweight integrations (`MLflow` lineage, DQ/monitoring compatibility artifacts, `/metrics`) — `done`
3. `H3` Heavier services (`Feast`, `Splink`, `Airflow`, `Keycloak`) optional and profile-driven — `done`

## 10) Out of Scope For Current Build

1. Vendor-specific managed services.
2. Production multi-tenant SLA commitments.
3. Full enterprise IAM rollout as a release blocker for local single-user mode.
4. Replacing current UI stack with a framework migration before backlog enhancements are delivered.

## 11) Definition of Success (Locked)

1. A fresh environment can launch demo flow with one command.
2. All 4 scenarios complete using synthetic-only mode.
3. Business and technical personas can complete a guided end-to-end walkthrough without external docs.
4. Open-source compliance is auditable in app + repo.
5. Demo outcomes are reproducible by seed and scenario preset.

## 12) Change Control

Scope changes must be recorded in this file by:

1. Updating version number.
2. Updating `Last updated` timestamp.
3. Adding a one-line entry in the change log.

## 13) Change Log

1. v1.19 (2026-04-25 UTC): Added completed enterprise hardening product-mode tracker (`H1..H3`) with profile toggle, lightweight artifacts, `/metrics`, and profile-driven heavy services.
2. v1.18 (2026-04-25 UTC): Added `R18` artifact consolidation cleanup to keep one canonical baseline snapshot root (`artifacts/`).
3. v1.17 (2026-04-25 UTC): Added `R17` UI consolidation cleanup removing unused standalone storyboard files and standardizing on Workbench + Architecture Story Mode.
4. v1.16 (2026-04-25 UTC): Added `R16` to reframe `Technical App` as storytelling-first `Architecture Story Mode` with guided technical flow and live evidence mapping.
5. v1.15 (2026-04-24 UTC): Added navigation/deep-link consistency enhancement (`R15`) so business flow links resolve to Workbench scenario routes.
6. v1.14 (2026-04-24 UTC): Added visual harmonization enhancement (`R14`) to align `Business Home`, `Executive Summary`, and `Technical App` with Workbench style.
7. v1.13 (2026-04-24 UTC): Added technical deep-dive enhancement (`R13`) to complete Workbench technical persona coverage.
8. v1.12 (2026-04-24 UTC): Added workbench cleanup enhancement (`R12`) for cleaner low-scroll UI presentation.
9. v1.11 (2026-04-24 UTC): Added unified workbench enhancement (`R11`) for left-navigator, low-scroll business + technical UX.
10. v1.10 (2026-04-24 UTC): Added guided story-mode enhancement (`R10`) for self-navigated business storytelling UX across all flow pages.
11. v1.9 (2026-04-24 UTC): Recorded consolidated completed-task ledger snapshot (`E1..E5`, `B1..B5`, `L1..L4`, `R1..R9` all `done`).
12. v1.8 (2026-04-24 UTC): Added business exec-mode enhancement (`R9`) for one-screen leadership summary and print/PDF export.
13. v1.7 (2026-04-24 UTC): Completed business UX Phase-2 refinement (`R6..R8`) for strict 3-step pages, lower visual density, and churn live-hydration fix.
14. v1.6 (2026-04-24 UTC): Completed business UX refinement tracker (`R1..R5`) for business-flow-first simplification.
15. v1.5 (2026-04-24 UTC): Completed business live-data tracker (`L1..L4`) for all four storyboard flows.
16. v1.4 (2026-04-24 UTC): Added business live-data tracker (`L1..L4`) and marked NBA (`L1`) done.
17. v1.3 (2026-04-24 UTC): Added business-first storyboard wave tracker (`B1..B5`) and marked all items done.
18. v1.2 (2026-04-24 UTC): Expanded enhancement backlog to 5 items and recorded all `E1..E5` statuses as done.
19. v1.1 (2026-04-24 UTC): Updated scope lock to reflect completed implementation and moved remaining work to post-lock enhancements.
20. v1.0 (2026-04-24 UTC): Initial scope lock created as persistent context anchor.

## 14) Related References

1. `PROJECT_SCOPE_AND_STATUS.md`
2. `docs/STANDALONE_APP_IMPLEMENTATION_PLAN.md`
3. `docs/OSS_INVENTORY.json`
4. `docs/OSS_LICENSE_SUMMARY.md`
5. `architecture/open_source_component_selection.md`
