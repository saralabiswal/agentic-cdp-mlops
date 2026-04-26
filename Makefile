.PHONY: install install-ml list run-all run-stack-all run-stack-all-strict run-stack-all-real run-stack-all-oss run-nba run-churn run-mmm run-incr run-stack-nba run-stack-churn run-stack-mmm run-stack-incr run-stack-nba-strict run-stack-nba-real demo-nba-oss demo-nba-oss-compact infra-up infra-down infra-logs infra-ps infra-smoke docs-gen docs-check docs-contracts-gen docs-contracts-check ui-build-data ui-build-data-live ui-build-data-live-oss ui-serve ui-live standalone standalone-fast smoke-standalone oss-inventory portfolio-summary baseline-report baseline-report-real show-stages show-data-quality model-registry-list model-readiness model-promote-approved model-promote-prod governance-approve sync-project-status ci-refresh-status-docs reindex-runs prune-runs-dry prune-runs-apply ui-live-docker-build ui-live-docker-dev ui-live-docker-demo ui-live-docker-prod ci-quality ci-quality-ml test test-oss clean

PYTHON_STANDALONE := $(if $(wildcard ./.venv311/bin/python),./.venv311/bin/python,python3)

install:
	python3 -m pip install -r requirements.txt

install-ml:
	python3 -m pip install -r requirements-ml.txt

list:
	python3 -m pipelines.cli list-configs

run-all:
	python3 -m pipelines.cli run-all

run-stack-all:
	python3 -m pipelines.cli run-stack-all

run-stack-all-strict:
	python3 -m pipelines.cli run-stack-all --strict-model-backends

run-stack-all-real:
	python3 -m pipelines.cli run-stack-all --source-data-root data/production --require-real-data

run-stack-all-oss:
	python3 -m pipelines.cli run-stack-all --infra-profile oss

run-nba:
	python3 -m pipelines.cli run --use-case UC-NBA-RET-001

run-churn:
	python3 -m pipelines.cli run --use-case UC-CHURN-RET-002

run-mmm:
	python3 -m pipelines.cli run --use-case UC-MMM-PLN-003

run-incr:
	python3 -m pipelines.cli run --use-case UC-INCR-MKT-004

run-stack-nba:
	python3 -m pipelines.cli run-stack --use-case UC-NBA-RET-001

run-stack-nba-strict:
	python3 -m pipelines.cli run-stack --use-case UC-NBA-RET-001 --strict-model-backends

run-stack-nba-real:
	python3 -m pipelines.cli run-stack --use-case UC-NBA-RET-001 --source-data-root data/production --require-real-data

run-stack-churn:
	python3 -m pipelines.cli run-stack --use-case UC-CHURN-RET-002

run-stack-mmm:
	python3 -m pipelines.cli run-stack --use-case UC-MMM-PLN-003

run-stack-incr:
	python3 -m pipelines.cli run-stack --use-case UC-INCR-MKT-004

demo-nba-oss: infra-smoke
	python3 scripts/demo_nba_oss.py

demo-nba-oss-compact: infra-smoke
	python3 scripts/demo_nba_oss.py --compact

infra-up:
	./scripts/compose.sh -f infra/docker-compose.oss.yml up -d

infra-down:
	./scripts/compose.sh -f infra/docker-compose.oss.yml down

infra-logs:
	./scripts/compose.sh -f infra/docker-compose.oss.yml logs -f --tail=200

infra-ps:
	./scripts/compose.sh -f infra/docker-compose.oss.yml ps

infra-smoke:
	./scripts/infra_smoke_test.sh

docs-gen:
	python3 docs/generate_tech_docs.py
	python3 docs/generate_api_contracts.py

docs-check:
	python3 docs/generate_tech_docs.py --check
	python3 docs/generate_api_contracts.py --check

docs-contracts-gen:
	python3 docs/generate_api_contracts.py

docs-contracts-check:
	python3 docs/generate_api_contracts.py --check

ui-build-data:
	python3 ui/adapter/build_view_model.py

ui-build-data-live:
	python3 ui/adapter/build_view_model.py --runtime-mode execute_backend

ui-build-data-live-oss:
	python3 ui/adapter/build_view_model.py --runtime-mode execute_backend --infra-profile oss

ui-serve: ui-build-data
	@echo "Serving UI at http://localhost:8080/ui/experience/"
	python3 -m http.server 8080

ui-live:
	python3 scripts/ui_live_server.py --host 127.0.0.1 --port 8080

standalone:
	$(PYTHON_STANDALONE) scripts/standalone_app.py

standalone-fast:
	$(PYTHON_STANDALONE) scripts/standalone_app.py --skip-bootstrap

smoke-standalone:
	$(PYTHON_STANDALONE) scripts/standalone_smoke_test.py --skip-bootstrap

oss-inventory:
	python3 scripts/generate_oss_inventory.py

portfolio-summary:
	python3 -m pipelines.cli portfolio-summary

baseline-report:
	python3 -m pipelines.cli baseline-report

baseline-report-real:
	python3 -m pipelines.cli baseline-report --artifacts-root artifacts --output artifacts/baseline_report.json

show-stages:
	python3 -m pipelines.cli show-stages --use-case UC-NBA-RET-001 --run-id $$(python3 -m pipelines.cli list-runs --use-case UC-NBA-RET-001 --limit 1 | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload['runs'][0]['run_id'] if payload.get('runs') else 'missing')")

show-data-quality:
	python3 -m pipelines.cli show-data-quality --use-case UC-NBA-RET-001 --run-id $$(python3 -m pipelines.cli list-runs --use-case UC-NBA-RET-001 --limit 1 | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload['runs'][0]['run_id'] if payload.get('runs') else 'missing')")

model-registry-list:
	python3 -m pipelines.cli model-registry-list

model-readiness:
	python3 -m pipelines.cli model-readiness --use-case UC-NBA-RET-001 --run-id $$(python3 -m pipelines.cli list-runs --use-case UC-NBA-RET-001 --limit 1 | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload['runs'][0]['run_id'] if payload.get('runs') else 'missing')")

model-promote-approved:
	python3 -m pipelines.cli model-promote --use-case UC-NBA-RET-001 --run-id $$(python3 -m pipelines.cli list-runs --use-case UC-NBA-RET-001 --limit 1 | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload['runs'][0]['run_id'] if payload.get('runs') else 'missing')") --to approved

model-promote-prod:
	python3 -m pipelines.cli model-promote --use-case UC-NBA-RET-001 --run-id $$(python3 -m pipelines.cli list-runs --use-case UC-NBA-RET-001 --limit 1 | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload['runs'][0]['run_id'] if payload.get('runs') else 'missing')") --to prod

governance-approve:
	python3 -m pipelines.cli governance-approve --use-case UC-NBA-RET-001 --run-id $$(python3 -m pipelines.cli list-runs --use-case UC-NBA-RET-001 --limit 1 | python3 -c "import json,sys; payload=json.load(sys.stdin); print(payload['runs'][0]['run_id'] if payload.get('runs') else 'missing')")

sync-project-status:
	python3 -m pipelines.cli sync-project-status --artifacts-root artifacts --status-file PROJECT_SCOPE_AND_STATUS.md

ci-refresh-status-docs:
	./scripts/ci_refresh_status_docs.sh --artifacts-root artifacts_ci_ml --status-file PROJECT_SCOPE_AND_STATUS.md

reindex-runs:
	python3 -m pipelines.cli reindex-runs

prune-runs-dry:
	python3 -m pipelines.cli prune-runs --keep-per-use-case 20

prune-runs-apply:
	python3 -m pipelines.cli prune-runs --keep-per-use-case 20 --apply

ui-live-docker-build:
	docker build -f deploy/Dockerfile.ui-live -t cdp-ui-live:local .

ui-live-docker-dev:
	./scripts/compose.sh -f deploy/docker-compose.ui-live.yml --profile dev up -d

ui-live-docker-demo:
	./scripts/compose.sh -f deploy/docker-compose.ui-live.yml --profile demo up -d

ui-live-docker-prod:
	./scripts/compose.sh -f deploy/docker-compose.ui-live.yml --profile prod-sim up -d

ci-quality:
	./scripts/ci_quality_gate.sh

ci-quality-ml:
	./scripts/ci_quality_gate_ml.sh

test:
	python3 -m pytest -q

test-oss: infra-smoke
	RUN_OSS_TESTS=1 python3 -m pytest -q tests/test_oss_integration.py

clean:
	rm -rf artifacts .pytest_cache
