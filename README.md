<!--
  Author: Sarala Biswal
  github.com/saralabiswal
-->

# CDP AI/ML Platform — Reference Architecture for Production ML Governance

**Author:** [Sarala Biswal](https://github.com/saralabiswal) · [LinkedIn](https://linkedin.com/in/saralabiswal) · [nlpml.ai](https://nlpml.ai)

[![Python](https://img.shields.io/badge/Python-3.11-3b82f6?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-ML-ff6f00?style=flat-square&logo=tensorflow&logoColor=white)](https://tensorflow.org)
[![PyMC](https://img.shields.io/badge/PyMC--Marketing-Bayesian-a855f7?style=flat-square)](https://pymc-marketing.io)
[![EconML](https://img.shields.io/badge/EconML-Causal-10b981?style=flat-square)](https://econml.azurewebsites.net)
[![MLflow](https://img.shields.io/badge/MLflow-registry-0194e2?style=flat-square)](https://mlflow.org)
[![Feast](https://img.shields.io/badge/Feast-feature--store-f59e0b?style=flat-square)](https://feast.dev)
[![License](https://img.shields.io/badge/license-MIT-64748b?style=flat-square)](LICENSE)
[![No Deploy](https://img.shields.io/badge/runs%20locally-no%20cloud%20required-22c55e?style=flat-square)](#quick-start)

---

> Reference architecture for governed enterprise ML — four production use cases,
> eight pipeline stages, contract-driven workflows, tiered runtime profiles, and
> evidence-first governance in one inspectable, standalone platform.

> *"The failure mode in enterprise ML is not building the model — it is everything
> around the model. Feature drift, data quality gaps, registry without evidence,
> governance without audit, and the inability to trace a decision back to its data
> source are what break enterprise ML deployments at scale. This platform names and
> solves each of those problems as a contract-backed, independently inspectable
> pipeline layer."*

Reference architecture of the CDP AI/ML platform architecture that shipped six production models.

---

## Reference Architecture

This repo is a reference implementation of three architectural patterns that
most enterprise ML platforms skip in favor of getting to model training faster.

**Pattern 1 — Contract-Driven ML Workflows**
Every use case is defined by a contract (`UC-NBA-RET-001`, `UC-CHURN-RET-002`,
`UC-MMM-PLN-003`, `UC-INCR-MKT-004`). The contract specifies inputs, outputs,
runtime model selection, fallback behavior, and governance requirements. The
pipeline implements the contract — not the other way around. This is how you
build ML systems that survive model swaps, team changes, and production incidents.

**Pattern 2 — Tiered Runtime Architecture**
The same codebase runs in three progressive tiers without code changes:
- **Standalone** — local execution, file-backed artifacts, zero external dependencies
- **OSS Integrated** — Kafka, PostgreSQL, MinIO for production-shaped data paths
- **Enterprise** — MLflow, Feast, Splink, Airflow, Keycloak, Prometheus, monitoring

Each tier produces the same artifacts, the same audit evidence, and the same
governance outputs. Infrastructure is injected — not coupled.

**Pattern 3 — Evidence-First Governance**
Every pipeline run produces inspectable artifacts: source tables, event-bus topics,
storage outputs, identity and feature snapshots, model predictions, activation
payloads, validation gates, lineage outputs, model-registry entries, and stage
telemetry. Governance is not a checkbox at the end — it is an output of every run.

---

## The Business Problem

Enterprise marketing, retention, and revenue teams operate in a gap between data availability and decision confidence. Customer data exists. Campaign data exists. Experiment results exist. Model outputs exist. What is missing is the governed, evidence-backed infrastructure that connects those signals to commercially accountable decisions.

The result is four specific failures that repeat across almost every enterprise ML deployment:

| Failure | What it looks like in practice | Business consequence |
|---|---|---|
| **Model outputs without context** | Data scientists present churn scores. Business teams ask: which customers? what actions? what confidence? No answer. | Decisions delayed or ignored — model adoption stalls |
| **Attribution without causality** | Marketing measures channel performance using last-touch or even multi-touch attribution. True incrementality — what actually caused conversion — is never measured. | Budget allocated to channels that correlate with conversion but don't cause it. Millions misspent. |
| **ML recommendations without activation** | The model produces a Next Best Action output. Nobody knows how to turn it into a campaign, a CRM update, or a customer communication. | ML lives in a dashboard. It never reaches the customer. |
| **Governance as a final checkpoint** | Data quality, model readiness, and lineage are reviewed once — right before deployment. Problems surface late, fixes are expensive. | Slow release cycles, production incidents, compliance exposure |

**What makes this hard at enterprise scale:**

The data, models, features, experiments, and activation systems are owned by different teams, running on different platforms, with different quality standards and release cadences. A churn model trained by the data science team cannot easily reach the CRM system owned by the marketing operations team, governed by a compliance team with its own approval process.

Most organizations solve this by building point-to-point pipelines — one script for churn, another for NBA, another for attribution. Each one breaks differently. None share a governance model. Audit trails exist per team, not per decision.

---

## How This Architecture Solves It

**Problem 1 — Model outputs without context → Contract-driven evidence artifacts**

Every pipeline run produces a complete artifact set: source data snapshot, feature vector, model input, prediction, confidence metrics, activation mapping, and governance validation. Business users do not see a score — they see a recommendation backed by traceable evidence. The `Model Decision Workbench` turns those artifacts into a stakeholder-ready presentation that answers: what is recommended, why, with what confidence, and what action does it map to.

**Problem 2 — Attribution without causality → Causal ML as a first-class layer**

The platform runs EconML + DoWhy for `UC-INCR-MKT-004` (Campaign Incrementality) and PyMC-Marketing for `UC-MMM-PLN-003` (Media Mix Modeling). These are not correlation-based attribution models. They measure true incremental lift — what would have happened without this campaign, this channel, this spend — using causal inference methodology. This is the difference between knowing what correlated with conversion and knowing what caused it.

**Problem 3 — Recommendations without activation → Eight-stage pipeline ending in activation**

Stage 7 of the pipeline is Serving + Activation. Every model output is mapped to a business action: a CRM update, a campaign segment, a retention offer, a budget reallocation. The pipeline does not stop at prediction. It continues through to the output that a marketing operations team, a CRM admin, or a finance team can act on without interpretation.

**Problem 4 — Governance as a checkpoint → Evidence-first governance at every stage**

Every stage produces governance artifacts. Data quality blockers are caught at Stage 2 before any model runs. Feature validation happens at Stage 5 before training. Model readiness is evaluated and registered before serving. Governance approval is required before promotion. By the time a model reaches production, there are eight stages of evidence behind it — not a single pre-release review.

**The architectural outcome:**

```
Before this platform:
  Churn score exists in a notebook
  Attribution lives in a dashboard
  NBA outputs require manual interpretation
  Governance happens at the end
  Point-to-point pipelines, different standards, no shared audit

After this platform:
  Churn score → evidence artifact → CRM activation payload
  Attribution → causal lift measurement → budget reallocation
  NBA → ranked action list → campaign segment → customer communication
  Governance runs at every stage → artifacts prove every decision
  One contract-driven pipeline → four use cases → one audit trail
```



| Contract ID | Use Case | ML Approach | Fallback |
|---|---|---|---|
| `UC-NBA-RET-001` | Next Best Action for retention | TensorFlow uplift + action ranking | Deterministic heuristic |
| `UC-CHURN-RET-002` | Churn prediction + retention actioning | TensorFlow classifier | Deterministic heuristic |
| `UC-MMM-PLN-003` | Media mix modeling + budget optimization | PyMC-Marketing Bayesian | Bayesian-surrogate fallback |
| `UC-INCR-MKT-004` | Campaign incrementality measurement | EconML + DoWhy causal inference | Statistical fallback |

Three distinct ML paradigms in one governed platform:
- **Discriminative** (TensorFlow) — supervised classification and ranking
- **Bayesian** (PyMC-Marketing) — probabilistic marketing mix attribution
- **Causal** (EconML + DoWhy) — true lift measurement, not correlation

---

## Eight-Stage ML Pipeline

```
Stage 1 — Data Sources           CRM · campaign · experiment · usage data
          ↓
Stage 2 — Ingestion + Event Bus  Kafka (OSS) or file-backed (standalone)
          ↓
Stage 3 — Raw + Curated Storage  MinIO + PostgreSQL (OSS) or local artifacts
          ↓
Stage 4 — Identity Resolution    Splink probabilistic entity matching
          + Customer 360          Unified customer profile per use case
          ↓
Stage 5 — Feature Layer          Feast feature store (OSS) or computed features
                                  Versioned feature snapshots per run
          ↓
Stage 6 — Model Layer            TensorFlow · PyMC-Marketing · EconML · DoWhy
                                  Model registry · champion/challenger · readiness
          ↓
Stage 7 — Serving + Activation   Online inference · batch scoring
                                  Activation mapping to business actions
          ↓
Stage 8 — Monitoring + Governance MLflow · Prometheus · data quality
                                  Artifact manifests · lineage · audit trail
```

Every stage produces versioned artifacts under `artifacts/<use_case_id>/<run_id>/`.
Every run is inspectable, replayable, and governance-approved before promotion.

---

## MLOps Lifecycle — Model Governance

Models move through a governed promotion lifecycle — not just trained and deployed:

```
generate synthetic data
  → train versioned artifacts
  → evaluate baseline vs challenger
  → model-readiness check
  → register in model registry
  → governance review (approve warnings)
  → promote to approved
  → deploy to serving layer
```

**Model registry commands:**
```bash
python3 -m pipelines.cli model-registry-list
python3 -m pipelines.cli model-readiness --use-case UC-NBA-RET-001 --run-id <id>
python3 -m pipelines.cli model-promote --use-case UC-NBA-RET-001 --run-id <id> --to approved
```

**What the registry tracks:** model version · training data snapshot · evaluation
metrics · approval status · checksums · feature schema version · policy version

---

## Platform Modules

| Module | Architectural purpose |
|---|---|
| **AI Decision Portfolio** | Model portfolio view with recommended evaluation sequence |
| **AI Impact Summary** | Portfolio-level business impact, model health, latest run status |
| **Model Decision Workbench** | Model inputs, recommendations, forecasts, decision evidence |
| **Simulation Flow** | Stage-by-stage pipeline execution with failure injection |
| **Architecture Reference** | 8-stage diagram, runtime profiles, enterprise integration paths |

---

## Tiered Runtime Profiles

| Profile | Command | Infrastructure |
|---|---|---|
| **Standalone** (default) | `make standalone` | Local Python, file-backed artifacts — no external services |
| **Synthetic-only** | `--runtime-mode synthetic_only` | Generated source data, deterministic scenario presets |
| **Real Dataset** | `--source-data-root data/production` | Production-style CSV fixtures |
| **OSS Integrated** | `make infra-up && --infra-profile oss` | Kafka · PostgreSQL · MinIO |
| **Advanced ML** | `make install-ml` | TensorFlow · PyMC-Marketing · EconML · DoWhy |
| **Enterprise** | `enterprise_hardening.json` | MLflow · Feast · Splink · Airflow · Keycloak · Prometheus |

**The invariant:** every profile produces the same contract outputs and governance
artifacts. Infrastructure scales up — the decision interface does not change.

---

## Failure Injection + Scenario Presets

Built-in failure injection for governance walkthroughs and resilience demos:

```bash
# Inject data quality failure
python3 -m pipelines.cli run-stack --use-case UC-NBA-RET-001 \
  --runtime-mode synthetic_only --failure-injection dq_fail

# Run deterministic scenario preset
python3 -m pipelines.cli run-stack --use-case UC-NBA-RET-001 \
  --runtime-mode synthetic_only --scenario-id nba_high_risk_save
```

Every failure injection is observable in the governance artifacts — data quality
blockers, stage telemetry, and run summaries show exactly what failed and why.

---

## Enterprise Integration Paths

Optional paths that connect to enterprise infrastructure without coupling the core pipeline:

| Integration | Purpose | Activation |
|---|---|---|
| **MLflow** | Model registry, experiment tracking | `--infra-profile oss` |
| **Feast** | Feature store, feature versioning | `--infra-profile oss` |
| **Splink** | Probabilistic identity resolution | `--infra-profile oss` |
| **Airflow** | Workflow orchestration | `--infra-profile oss` |
| **Keycloak** | Access control, identity | Enterprise profile |
| **Prometheus** | Runtime metrics, model monitoring | `GET /metrics` |
| **Kafka** | Event bus for ingestion layer | `make infra-up` |
| **PostgreSQL + MinIO** | Curated storage and data lake | `make infra-up` |

All integrations are profile-driven and produce fallback evidence when unavailable.
The platform never fails silently — missing integrations are recorded in the artifact manifest.

---

## Live API Surface

```
GET  /api/health                                Server health
GET  /api/view-model                            Current UI view model
POST /api/run                                   Start full-stack pipeline run
GET  /api/jobs, /api/jobs/<id>                  Job status
POST /api/simulation/session                    Stage-by-stage simulation
GET  /api/runs, /api/runs/<uc>/<run_id>         Run registry and summary
GET  /api/runs/<uc>/<run_id>/stages             Stage telemetry
GET  /api/runs/<uc>/<run_id>/data-quality       Data quality blockers
GET  /api/portfolio/summary                     Cross-use-case KPI rollup
POST /api/inference/online                      Single-record scoring
POST /api/inference/batch                       Batch scoring
GET  /api/contracts/inference                   Generated inference contracts
GET  /api/openapi.json                          OpenAPI schema
POST /api/governance/approve                    Approve governance warnings
GET  /metrics                                   Prometheus-compatible metrics
```

---

## Technology Stack

| Layer | Technology | Design note |
|---|---|---|
| **Discriminative ML** | TensorFlow · scikit-learn | Supervised classification + uplift ranking |
| **Bayesian ML** | PyMC-Marketing | Probabilistic MMM — not correlation-based attribution |
| **Causal ML** | EconML · DoWhy | True incrementality — not lift proxy |
| **Feature Store** | Feast | Versioned features, point-in-time correctness |
| **Model Registry** | MLflow | Governed promotion lifecycle, experiment tracking |
| **Identity Resolution** | Splink | Probabilistic entity matching for Customer 360 |
| **Orchestration** | Airflow | Enterprise workflow scheduling |
| **Event Bus** | Kafka | Ingestion layer for real-time data paths |
| **Storage** | PostgreSQL · MinIO | Curated warehouse + object store |
| **Access Control** | Keycloak | Enterprise identity and authorization |
| **Metrics** | Prometheus | Runtime and model health monitoring |
| **E2E Testing** | Playwright | UI workflow coverage |

---

## Quick Start

**Standalone — one command:**

```bash
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -r requirements.txt
make standalone
```

Open `http://127.0.0.1:8080/ui/experience/`

**With full ML backends:**

```bash
python3 -m pip install -r requirements-ml.txt
make standalone
```

**OSS integrated runtime (Kafka + PostgreSQL + MinIO):**

```bash
make infra-up
python3 -m pipelines.cli run-stack-all --infra-profile oss
```

**Run individual use cases:**

```bash
# List configured use cases
python3 -m pipelines.cli list-configs

# Run all
python3 -m pipelines.cli run-stack-all

# Run one use case
python3 -m pipelines.cli run-stack --use-case UC-NBA-RET-001

# Synthetic mode with scenario preset
python3 -m pipelines.cli run-stack --use-case UC-NBA-RET-001 \
  --runtime-mode synthetic_only --scenario-id nba_high_risk_save
```

**UI pages:**

```
AI Decision Portfolio:  http://127.0.0.1:8080/ui/experience/business-home.html
AI Impact Summary:      http://127.0.0.1:8080/ui/experience/business-exec-summary.html
Model Workbench:        http://127.0.0.1:8080/ui/experience/workbench.html
Simulation Flow:        http://127.0.0.1:8080/ui/experience/index.html#simulate
Architecture:           http://127.0.0.1:8080/ui/experience/index.html#overview
```

---

## Run History + Governance

```bash
# Inspect runs
python3 -m pipelines.cli list-runs
python3 -m pipelines.cli show-run --use-case UC-NBA-RET-001 --run-id <id>
python3 -m pipelines.cli show-stages --use-case UC-NBA-RET-001 --run-id <id>
python3 -m pipelines.cli show-data-quality --use-case UC-NBA-RET-001 --run-id <id>

# Portfolio and baseline
python3 -m pipelines.cli portfolio-summary
python3 -m pipelines.cli baseline-report

# Model lifecycle
python3 -m pipelines.cli model-registry-list
python3 -m pipelines.cli model-promote --use-case UC-NBA-RET-001 --run-id <id> --to approved

# Governance approval
python3 -m pipelines.cli governance-approve --use-case UC-NBA-RET-001 \
  --run-id <id> --accept-all-warnings
```

---

## Key Commands

```bash
make install              # Install core dependencies
make install-ml           # Install ML backends (TensorFlow, PyMC, EconML)
make standalone           # Full standalone setup + launch
make standalone-fast      # Launch only (artifacts already exist)
make ui-live              # Live UI/API with backend interaction
make run-stack-all        # Run all 4 use cases
make run-stack-all-oss    # Run all use cases with OSS infrastructure
make infra-up             # Start Kafka + PostgreSQL + MinIO
make model-registry-list  # Inspect model registry
make portfolio-summary    # Cross-use-case KPI summary
make ci-quality           # Lint + type checks + tests
make test                 # Full test suite
make smoke-standalone     # Standalone smoke test
```

---

## Repository Map

```
use_cases/configs/         AI/ML use-case contracts — source of truth
stack/layers/              Eight-stage runtime implementation
models/                    Model implementations and registry
pipelines/                 CLI and contract helpers
scripts/ui_live_server.py  Live UI/API server
ui/experience/             Enterprise presentation UI
ui/adapter/                View-model generation
artifacts/                 Run outputs · metrics · manifests · evidence
docs/                      User · technical · API documentation
tests/                     Unit and integration tests
```

---

## Documentation

| Document | Purpose |
|---|---|
| [User Guide](docs/USER_GUIDE.md) | Business and technical walkthrough |
| [Technical README](docs/TECHNICAL_README.md) | Architecture, runtime, data flow |
| [API Reference](docs/API_REFERENCE.md) | Endpoints, contracts, error payloads |
| [Technical Architecture](docs/TECHNICAL_ARCHITECTURE.md) | Auto-generated code architecture |
| [Enterprise Integration Plan](docs/ENTERPRISE_HARDENING_PRODUCT_MODE_PLAN.md) | Production hardening roadmap |
| [ML Model Card](docs/ML_CARD.md) | Model intent, limitations, promotion requirements |

---

## Troubleshooting

```bash
# Stale artifacts after model change
make standalone

# Infrastructure not starting
make infra-down && make infra-up

# ML backends unavailable
make install-ml

# Reset run registry
python3 -m pipelines.cli reindex-runs
python3 -m pipelines.cli prune-runs --keep-per-use-case 20 --apply
```

---

## Portfolio Context

This repo demonstrates the ML platform layer of a production AI portfolio:

| Pattern | Repo |
|---|---|
| Cross-vendor MCP integration · live context assembly | [agentic-mcp-quote-to-cash](https://github.com/saralabiswal/agentic-mcp-quote-to-cash) |
| 6-layer governed agentic pipeline · regulatory replay | [agentic-banking-llmops](https://github.com/saralabiswal/agentic-banking-llmops) |
| LLM agent evaluation · judge/SUT separation | [agentops-eval-llmops](https://github.com/saralabiswal/agentops-eval-llmops) |
| LLMOps control plane · token cost · quality · drift | [agentic-llm-observability](https://github.com/saralabiswal/agentic-llm-observability) |
| Hybrid ML + Rules · validator-gated LLM renewal | [agentic-saas-renewal](https://github.com/saralabiswal/agentic-saas-renewal) |
| **8-stage ML platform · governed model promotion** | **this repo** |

---

*Built by [Sarala Biswal](https://linkedin.com/in/saralabiswal) — Director of AI Engineering,
AI/ML Platforms at Oracle. Production Agentic AI · MLOps · CPQ · Quote-to-Cash.*