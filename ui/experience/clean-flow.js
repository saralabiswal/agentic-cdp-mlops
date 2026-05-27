(function () {
  const modelMeta = {
    "UC-NBA-RET-001": {
      title: "TensorFlow Next Best Action",
      description: "Ranks retention actions by expected uplift, confidence, policy limits, and contact fatigue.",
      output: "Ranked activation action pack",
    },
    "UC-CHURN-RET-002": {
      title: "TensorFlow Churn Propensity",
      description: "Scores churn risk, prioritizes save treatments, and estimates retention intervention impact.",
      output: "Prioritized retention treatment plan",
    },
    "UC-MMM-PLN-003": {
      title: "Bayesian Media Mix Optimization",
      description: "Evaluates channel response curves, saturation, seasonality, and budget movement.",
      output: "Channel reallocation plan",
    },
    "UC-INCR-MKT-004": {
      title: "Causal Incrementality Model",
      description: "Separates campaign lift from baseline demand and recommends scale, pause, or retest.",
      output: "Campaign decision policy",
    },
  };

  const state = {
    useCases: [],
    scenarios: [],
    selectedUseCaseId: null,
    simulationSessionId: null,
    simulationState: null,
  };

  const $ = (id) => document.getElementById(id);

  function titleCase(value) {
    const normalized = String(value || "n/a");
    if (normalized.toLowerCase() === "oss") {
      return "OSS";
    }
    return String(value || "n/a")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`${url} returned ${response.status}`);
    }
    return response.json();
  }

  async function load() {
    const [viewModel, runsPayload, scenarioPayload] = await Promise.all([
      fetchJson("/api/view-model").catch(() => fetchJson("/ui/data/view_model.json")),
      fetchJson("/api/runs?limit=20&status=all&infra=all"),
      fetchJson("/api/scenarios").catch(() => ({ scenarios: [] })),
    ]);

    state.useCases = Array.isArray(viewModel.use_cases) ? viewModel.use_cases : [];
    state.scenarios = Array.isArray(scenarioPayload.scenarios) ? scenarioPayload.scenarios : [];
    const latestRuns = Array.isArray(runsPayload.runs) ? runsPayload.runs : [];
    const latestByUseCase = new Map(latestRuns.map((run) => [run.use_case_id, run]));

    state.useCases = state.useCases.map((useCase) => ({
      ...useCase,
      latest_run: useCase.latest_run || latestByUseCase.get(useCase.use_case_id) || null,
    }));
    state.selectedUseCaseId = state.useCases[0]?.use_case_id || latestRuns[0]?.use_case_id || null;

    renderMetrics(latestRuns);
    renderSimulationControls();
    renderModels();
    renderSelected();
    updateActiveNav();
  }

  function renderMetrics(runs) {
    const latest = runs[0] || state.useCases.find((item) => item.latest_run)?.latest_run || {};
    $("metric-model-count").textContent = String(state.useCases.length || 4);
    $("metric-run-status").textContent = titleCase(latest.run_status || "unknown");
    $("metric-stage-count").textContent = "8";
    $("metric-runtime").textContent = titleCase(latest.infra_profile || "local");
  }

  function renderModels() {
    const grid = $("model-grid");
    grid.innerHTML = "";
    state.useCases.forEach((useCase) => {
      const meta = modelMeta[useCase.use_case_id] || {};
      const latest = useCase.latest_run || {};
      const card = document.createElement("article");
      card.className = "clean-model-card";
      card.innerHTML = `
        <h3>${meta.title || useCase.name}</h3>
        <span class="clean-badge">Latest run ${titleCase(latest.run_status || "unknown")}</span>
        <p>${meta.description || useCase.business_problem || ""}</p>
        <div class="clean-fields">
          <span>Output: ${meta.output || useCase.contract?.output_type || "Model decision output"}</span>
          <span>KPI: ${useCase.primary_kpi || latest.primary_kpi || "n/a"}</span>
          <span>Evidence: predictions, metrics, manifest, stage telemetry</span>
        </div>
        <button class="clean-button" type="button">Open evidence</button>
      `;
      card.querySelector("button").addEventListener("click", () => {
        state.selectedUseCaseId = useCase.use_case_id;
        renderSelected();
        document.getElementById("evidence").scrollIntoView({ behavior: "smooth", block: "start" });
      });
      grid.appendChild(card);
    });
  }

  function renderSelected() {
    const useCase = state.useCases.find((item) => item.use_case_id === state.selectedUseCaseId) || state.useCases[0];
    if (!useCase) {
      return;
    }
    const latest = useCase.latest_run || {};
    const registry = latest.model_registry || {};
    $("run-use-case").textContent = useCase.use_case_id;
    $("run-status").textContent = titleCase(latest.run_status || "unknown");
    $("run-infra").textContent = titleCase(latest.infra_profile || "local");
    $("run-stage-pass").textContent = latest.telemetry?.stage_count ? `${latest.telemetry.stage_count} / 8` : "8 / 8";
    $("run-registry").textContent = titleCase(registry.stage || "candidate");
    renderEvidence(latest.artifacts || {}, useCase.use_case_id, latest.run_id);
  }

  function renderSimulationControls() {
    const useCaseSelect = $("sim-use-case");
    if (!useCaseSelect) {
      return;
    }

    useCaseSelect.innerHTML = state.useCases
      .map((useCase) => `<option value="${useCase.use_case_id}">${modelMeta[useCase.use_case_id]?.title || useCase.name || useCase.use_case_id}</option>`)
      .join("");
    useCaseSelect.value = state.selectedUseCaseId || state.useCases[0]?.use_case_id || "";
    renderScenarioOptions();
    renderSimulationState();
  }

  function renderScenarioOptions() {
    const useCaseId = $("sim-use-case")?.value || state.selectedUseCaseId;
    const scenarioSelect = $("sim-scenario");
    if (!scenarioSelect) {
      return;
    }
    const scenarios = state.scenarios.filter((scenario) => !useCaseId || scenario.use_case_id === useCaseId);
    scenarioSelect.innerHTML = [
      `<option value="">none</option>`,
      ...scenarios.map((scenario) => `<option value="${scenario.scenario_id}">${scenario.scenario_id}</option>`),
    ].join("");
  }

  function renderSimulationState() {
    const sim = state.simulationState || {};
    const cursor = Number(sim.stage_cursor || 0);
    const total = Number(sim.stage_total || 8);
    $("sim-status").textContent = sim.paused ? "Paused" : state.simulationSessionId ? "Active" : "Ready";
    $("sim-session").textContent = state.simulationSessionId || "Not started";
    $("sim-progress").textContent = `${cursor} / ${total}`;
    document.querySelectorAll("#sim-stage-list li").forEach((row, index) => {
      row.classList.toggle("done", index < cursor);
    });
  }

  async function ensureSimulationSession() {
    if (state.simulationSessionId && state.simulationState) {
      return state.simulationSessionId;
    }
    const payload = {
      use_case_id: $("sim-use-case").value,
      scenario_id: $("sim-scenario").value || null,
      runtime_mode: $("sim-runtime").value || "synthetic_only",
      infra_profile: $("sim-infra").value || "local",
    };
    $("sim-status").textContent = "Creating session";
    const body = await postJson("/api/simulation/session", payload);
    state.simulationSessionId = body.session_id;
    state.simulationState = body;
    renderSimulationState();
    return state.simulationSessionId;
  }

  async function runSimulationAction(action) {
    try {
      const sessionId = action === "reset" ? state.simulationSessionId : await ensureSimulationSession();
      if (!sessionId) {
        $("sim-status").textContent = "No session";
        return;
      }
      $("sim-status").textContent = action === "run-all" ? "Running all stages" : action === "reset" ? "Resetting" : "Running next stage";
      const body = await postJson(`/api/simulation/session/${encodeURIComponent(sessionId)}/${action}`, {});
      state.simulationState = body;
      if (action === "reset") {
        state.simulationSessionId = body.session_id || state.simulationSessionId;
      }
      renderSimulationState();
    } catch (error) {
      $("sim-status").textContent = `Error: ${error.message}`;
    }
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.error || `${url} returned ${response.status}`);
    }
    return body;
  }

  function renderEvidence(artifacts, useCaseId, runId) {
    const evidence = $("evidence-list");
    const rows = [
      ["Stage telemetry", artifacts.stage_telemetry],
      ["Data quality gates", artifacts.data_quality_expectations],
      ["Model metrics", artifacts.model_metrics],
      ["Activation payload", artifacts.activation_payloads],
      ["Lineage manifest", artifacts.mlflow_lineage || artifacts.model_manifest],
    ].filter((row) => row[1]);

    if (!rows.length) {
      evidence.innerHTML = `<span class="clean-muted">No artifact links available for ${useCaseId} ${runId || ""}.</span>`;
      return;
    }

    evidence.innerHTML = rows
      .map(([label, path]) => {
        const href = `/api/artifacts/download?path=${encodeURIComponent(path)}`;
        return `<a href="${href}" target="_blank" rel="noreferrer"><span>${label}</span><span>Open</span></a>`;
      })
      .join("");
  }

  function updateActiveNav() {
    const hash = window.location.hash || "#overview";
    document.body.classList.toggle("simulation-mode", hash === "#simulation");
    document.querySelectorAll(".clean-nav a").forEach((item) => {
      const href = item.getAttribute("href") || "";
      item.classList.toggle("active", href === hash || (!hash && href === "#overview"));
    });
  }

  document.querySelectorAll(".clean-nav a").forEach((link) => {
    link.addEventListener("click", () => {
      document.querySelectorAll(".clean-nav a").forEach((item) => item.classList.remove("active"));
      if ((link.getAttribute("href") || "").startsWith("#")) {
        link.classList.add("active");
      }
    });
  });

  window.addEventListener("hashchange", updateActiveNav);

  $("sim-use-case").addEventListener("change", () => {
    state.simulationSessionId = null;
    state.simulationState = null;
    renderScenarioOptions();
    renderSimulationState();
  });
  $("sim-scenario").addEventListener("change", () => {
    state.simulationSessionId = null;
    state.simulationState = null;
    renderSimulationState();
  });
  $("sim-runtime").addEventListener("change", () => {
    state.simulationSessionId = null;
    state.simulationState = null;
    renderSimulationState();
  });
  $("sim-infra").addEventListener("change", () => {
    state.simulationSessionId = null;
    state.simulationState = null;
    renderSimulationState();
  });
  $("sim-run-next").addEventListener("click", () => runSimulationAction("run-next"));
  $("sim-run-all").addEventListener("click", () => runSimulationAction("run-all"));
  $("sim-reset").addEventListener("click", () => runSimulationAction("reset"));

  $("refresh-evidence").addEventListener("click", () => {
    $("metric-run-status").textContent = "Loading";
    load().catch(showError);
  });

  function showError(error) {
    $("model-grid").innerHTML = `<article class="clean-model-card"><h3>Unable to load live evidence</h3><p>${error.message}</p></article>`;
    $("metric-run-status").textContent = "Unavailable";
  }

  load().catch(showError);
})();
