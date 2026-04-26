# Open-Source Component Selection

This project is constrained to open-source, platform-independent components and runnable-from-Git execution.

## Selected For Current Runnable Implementation

1. Data Sources: Python synthetic generators (`stack/layers/data_sources.py`)
2. Ingestion and Event Bus: local event bus adapter with optional Kafka mirror (`stack/layers/ingestion_event_bus.py`, `stack/oss_mirror.py`)
3. Raw and Curated Storage: file-based JSON/JSONL storage with optional Postgres/MinIO mirror (`stack/layers/storage.py`, `stack/oss_mirror.py`)
4. Identity Resolution and Customer 360: deterministic identity mapper (`stack/layers/identity_360.py`)
5. Feature Layer: Python feature builders (`stack/layers/features.py`)
6. Model Layer: use-case model registry and modules (`models/*.py`, `stack/layers/modeling.py`)
7. Serving and Activation: payload adapters (`stack/layers/serving_activation.py`)
8. Monitoring and Governance: validation gates and run report (`stack/layers/monitoring_governance.py`)

This keeps the stack zero-vendor and directly runnable from a fresh Git clone.

## OSS Infra Profile

Docker Compose profile:

`infra/docker-compose.oss.yml`

Services:

1. Kafka
2. PostgreSQL
3. MinIO
4. MinIO client (`mc`)

Runtime mode:

1. `infra_profile=local`: local adapters only.
2. `infra_profile=oss` for all use cases: direct OSS golden path (Kafka publish/consume, Postgres curated persistence, MinIO snapshots).
3. If OSS services are unavailable, runtime automatically falls back to local and records warnings.

## Planned Scalable OSS Swap-In Components

1. Ingestion and Event Bus: Apache Kafka
2. Raw Storage: MinIO object storage
3. Curated Warehouse: PostgreSQL or ClickHouse
4. Identity Resolution: Splink (deterministic + probabilistic)
5. Feature Layer: dbt + Feast
6. Model Ops: MLflow + Airflow
7. Serving and Activation: FastAPI + BentoML + webhook adapters
8. Monitoring and Governance: Great Expectations + Evidently + Prometheus + Grafana

## Selection Gate For Any New Component

1. Confirm open-source license compatibility.
2. Confirm platform portability (local, on-prem, cloud).
3. Confirm reproducible setup from Git (docker-compose or scripted bootstrap).
4. Document tradeoffs and fallback option before adoption.
