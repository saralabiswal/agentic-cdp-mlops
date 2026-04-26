# UI Experience

Static UI for communicating CDP flow to both business and technical audiences.
Includes run-history comparison for KPI/status/stage-health analysis plus `limit`/`status`/`infra` filters and baseline deltas.

## Structure

1. `contracts/view_model.schema.json` - stable UI data contract
2. `adapter/build_view_model.py` - generates data from contracts + latest artifacts
3. `config/runtime.yaml` - runtime mode config (`latest_artifacts` or `execute_backend`) plus execution settings (`default` or `synthetic_only`)
4. `data/view_model.json` - generated snapshot consumed by UI
5. `experience/` - static frontend (HTML/CSS/JS)

## Run

```bash
make ui-build-data
make ui-serve
```

Run backend first, then build UI data:

```bash
make ui-build-data-live
```

Run backend first using synthetic-only execution mode:

```bash
python3 ui/adapter/build_view_model.py --runtime-mode execute_backend --execution-mode synthetic_only
```

Run backend with scenario preset + failure injection:

```bash
python3 ui/adapter/build_view_model.py --runtime-mode execute_backend --execution-mode synthetic_only --scenario-id nba_high_risk_save --failure-injection dq_fail
```

Run backend in strict model-backend mode (fails if advanced backend libs are missing):

```bash
python3 ui/adapter/build_view_model.py --runtime-mode execute_backend --strict-model-backends
```

Run backend with required real source datasets:

```bash
python3 ui/adapter/build_view_model.py --runtime-mode execute_backend --source-data-root data/production --require-real-data
```

Run live UI with browser-triggered backend execution:

```bash
make ui-live
```

Live UI includes:

1. `Run Local` / `Run OSS` execution.
2. Stage simulation controls: `Run Next Stage` and `Reset Simulation`.
3. Scenario selector and failure-injection toggles.
4. OSS component/license inventory panel.

Open: `http://localhost:8080/ui/experience/`
