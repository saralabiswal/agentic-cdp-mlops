const state = {
  mode: "technical",
  data: null,
  selectedUseCaseId: null,
  currentJobId: null,
  controlsLocked: false,
  runStatusMessage: "",
  runStatusIsError: false,
  runStatusSticky: false,
  pollTimer: null,
  apiAvailable: false,
  runHistoryByUseCase: {},
  runHistoryMetaByUseCase: {},
  runSummaryByRunKey: {},
  runHistoryLoading: false,
  portfolioSummary: null,
  portfolioLoading: false,
  stageDetailsByRunKey: {},
  stageDetailsLoading: false,
  scenarioCatalog: [],
  ossInventory: null,
  enterpriseHardening: null,
  enterpriseProfile: "standalone",
  simulationSessionId: null,
  simulationState: null,
  simulationInfraProfile: "oss",
  artifactExplorerFilters: {
    stage: "all",
    exists: "all",
    query: "",
  },
  artifactExplorerRows: [],
  artifactExplorerVisibleRows: [],
  runHistoryFilters: {
    limit: 3,
    status: "all",
    infra: "all",
    baseline: "latest",
  },
  storyStageIndexByUseCase: {},
  presentationStep: "overview",
  evidenceView: "artifacts",
  runEvidenceView: "summary",
};

const els = {
  modeBusiness: document.getElementById("mode-business"),
  modeTechnical: document.getElementById("mode-technical"),
  useCaseSelect: document.getElementById("use-case-select"),
  enterpriseProfileSelect: document.getElementById("enterprise-profile-select"),
  runSelectedOnly: document.getElementById("run-selected-only"),
  runSeed: document.getElementById("run-seed"),
  runRuntimeMode: document.getElementById("run-runtime-mode"),
  runScenarioId: document.getElementById("run-scenario-id"),
  failureDq: document.getElementById("failure-dq"),
  failureSchema: document.getElementById("failure-schema"),
  failureBackend: document.getElementById("failure-backend"),
  runLocalBtn: document.getElementById("run-local-btn"),
  runOssBtn: document.getElementById("run-oss-btn"),
  simNextBtn: document.getElementById("sim-next-btn"),
  simPauseBtn: document.getElementById("sim-pause-btn"),
  simResumeBtn: document.getElementById("sim-resume-btn"),
  simResetBtn: document.getElementById("sim-reset-btn"),
  runStatus: document.getElementById("run-status"),
  runtimeBanner: document.getElementById("runtime-banner"),
  runHistoryLimit: document.getElementById("run-history-limit"),
  runHistoryStatus: document.getElementById("run-history-status"),
  runHistoryInfra: document.getElementById("run-history-infra"),
  runHistoryBaseline: document.getElementById("run-history-baseline"),
  runHistory: document.getElementById("run-history"),
  portfolioTiles: document.getElementById("portfolio-tiles"),
  architectureStory: document.getElementById("architecture-story"),
  archStorySubtitle: document.getElementById("arch-story-subtitle"),
  archStoryTitle: document.getElementById("arch-story-title"),
  archStoryProgress: document.getElementById("arch-story-progress"),
  archStoryRail: document.getElementById("arch-story-rail"),
  archStoryPrev: document.getElementById("arch-story-prev"),
  archStoryNext: document.getElementById("arch-story-next"),
  archStageTitle: document.getElementById("arch-stage-title"),
  archStoryStatus: document.getElementById("arch-story-status"),
  archStageSummary: document.getElementById("arch-stage-summary"),
  archStageWhat: document.getElementById("arch-stage-what"),
  archStageProof: document.getElementById("arch-stage-proof"),
  archStageInputs: document.getElementById("arch-stage-inputs"),
  archStageOutputs: document.getElementById("arch-stage-outputs"),
  archStageComponents: document.getElementById("arch-stage-components"),
  archStageEvidence: document.getElementById("arch-stage-evidence"),
  archStageSource: document.getElementById("arch-stage-source"),
  architectureFlow: document.getElementById("architecture-flow"),
  storyCaption: document.getElementById("story-caption"),
  runCaption: document.getElementById("run-caption"),
  storyContent: document.getElementById("story-content"),
  runContent: document.getElementById("run-content"),
  ossInventory: document.getElementById("oss-inventory"),
  enterpriseHardening: document.getElementById("enterprise-hardening"),
  presentationStepLinks: Array.from(document.querySelectorAll("[data-presentation-step]")),
  presentationPanels: Array.from(document.querySelectorAll("[data-presentation-panel]")),
  evidenceViewButtons: Array.from(document.querySelectorAll("[data-evidence-view]")),
  evidencePanels: Array.from(document.querySelectorAll("[data-evidence-panel]")),
};

const TECHNICAL_STAGE_STORY = {
  data_sources: {
    headline: "The platform starts from a contract, then creates or loads the exact source tables that use case expects.",
    why: "This proves the experience is not hard-coded to one dataset. Each use case declares its required sources, and the runtime can use deterministic synthetic data or real CSV inputs with the same downstream contract.",
    proof: "Show the source row counts and contract seed. A technical reviewer should see repeatability, source-table boundaries, and a clear handoff into ingestion.",
  },
  ingestion_event_bus: {
    headline: "Source records are normalized into topic-like event streams so every downstream stage receives the same shape of data.",
    why: "This is the integration boundary. In standalone mode it is file-backed and simple; in the integrated runtime it maps to Kafka-style producer/consumer behavior without changing use-case logic.",
    proof: "Review topic outputs and event counts. This is where the architecture demonstrates source decoupling and replayable ingestion.",
  },
  raw_curated_storage: {
    headline: "The runtime preserves raw evidence, then builds curated records for analytics and machine learning.",
    why: "Technical users should see the separation between auditability and usability: raw artifacts explain what arrived, curated artifacts explain what the platform is prepared to trust.",
    proof: "Show raw and curated artifact paths, record counts, and the warehouse-ready handoff into identity resolution.",
  },
  identity_customer_360: {
    headline: "The customer/entity layer resolves records into a stable analytical view before features are built.",
    why: "This is the Customer 360 control point. Today it is deterministic and inspectable; the Enterprise Integration Profile can replace or augment it with Splink-style probabilistic matching.",
    proof: "Show resolved record outputs and the upstream/downstream chain. The key question is whether every later decision traces back to a stable entity view.",
  },
  feature_layer: {
    headline: "Business signals become model-ready features with consistent names, types, and calculation rules.",
    why: "This is where reusable marketing science becomes practical. NBA, churn, MMM, and incrementality each need different features, but they all pass through the same feature-layer contract.",
    proof: "Show feature rows and fields. In the Enterprise Integration Profile this maps naturally to dbt/Feast without changing the stage contract.",
  },
  model_layer: {
    headline: "The model stage applies the selected science backend and writes predictions, metrics, and lineage artifacts.",
    why: "This is the evidence that the app is more than a mock UI. Each use case has model-specific behavior, validation metrics, and a versioned artifact trail.",
    proof: "Show model predictions, model metrics, manifest, backend metadata, and MLflow-compatible lineage.",
  },
  serving_activation: {
    headline: "Model outputs are converted into decision payloads that activation systems can consume.",
    why: "This is the operational handoff: a score or recommendation becomes an action-ready payload with policy fields, channels, and traceable model versioning.",
    proof: "Show activation payloads and output fields. This is the point where technical architecture meets a business workflow.",
  },
  monitoring_governance: {
    headline: "The final stage validates data quality, model checks, deployment readiness, and governance gates.",
    why: "This is the trust layer. It answers whether the run can be promoted, whether warnings are acceptable, and what evidence exists for audit or incident review.",
    proof: "Show validation gates, readiness status, DQ compatibility artifacts, monitoring summary, and Prometheus metrics.",
  },
};

async function init() {
  bindEvents();
  state.presentationStep = presentationStepFromLocation();

  try {
    state.data = await loadViewModel();
  } catch (err) {
    renderFatal(err);
    return;
  }

  await detectApiAvailability();
  await refreshScenarioCatalog();
  await refreshOssInventory();
  await refreshEnterpriseHardening();
  hydrateUseCaseSelector();
  hydrateScenarioSelector();
  hydrateRunHistoryFilters();
  state.runHistoryLoading = true;
  state.portfolioLoading = true;
  await refreshRunHistory();
  await refreshPortfolioSummary();
  render();
}

function bindEvents() {
  for (const link of els.presentationStepLinks) {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const step = String(link.getAttribute("data-presentation-step") || "overview");
      const href = String(link.getAttribute("href") || "");
      setPresentationStep(step, href);
    });
  }
  window.addEventListener("hashchange", () => {
    state.presentationStep = presentationStepFromLocation();
    renderPresentationPanels();
  });
  for (const button of els.evidenceViewButtons) {
    button.addEventListener("click", () => {
      state.evidenceView = String(button.getAttribute("data-evidence-view") || "history");
      renderEvidencePanels();
    });
  }
  if (els.modeBusiness) {
    els.modeBusiness.addEventListener("click", () => setMode("business"));
  }
  if (els.modeTechnical) {
    els.modeTechnical.addEventListener("click", () => setMode("technical"));
  }
  els.useCaseSelect.addEventListener("change", (event) => {
    state.selectedUseCaseId = event.target.value;
    state.runHistoryByUseCase[state.selectedUseCaseId] = [];
    state.runHistoryMetaByUseCase[state.selectedUseCaseId] = null;
    state.runHistoryLoading = true;
    state.stageDetailsLoading = false;
    state.simulationSessionId = null;
    state.simulationState = null;
    state.artifactExplorerRows = [];
    state.artifactExplorerVisibleRows = [];
    state.storyStageIndexByUseCase[state.selectedUseCaseId] = 0;
    clearRunStatus();
    hydrateScenarioSelector();
    render();
    void refreshRunHistory();
  });
  if (els.enterpriseProfileSelect) {
    els.enterpriseProfileSelect.addEventListener("change", async (event) => {
      state.enterpriseProfile = String(event.target.value || "standalone");
      await refreshEnterpriseHardening();
      renderEnterpriseHardening();
    });
  }

  if (els.archStoryPrev) {
    els.archStoryPrev.addEventListener("click", () => {
      shiftArchitectureStoryIndex(-1);
    });
  }
  if (els.archStoryNext) {
    els.archStoryNext.addEventListener("click", () => {
      shiftArchitectureStoryIndex(1);
    });
  }
  if (els.archStoryRail) {
    els.archStoryRail.addEventListener("click", (event) => {
      handleArchitectureStoryRailClick(event);
    });
  }

  if (els.runHistoryLimit) {
    els.runHistoryLimit.addEventListener("change", () => {
      void handleRunHistoryFilterChange();
    });
  }
  if (els.runHistoryStatus) {
    els.runHistoryStatus.addEventListener("change", () => {
      void handleRunHistoryFilterChange();
    });
  }
  if (els.runHistoryInfra) {
    els.runHistoryInfra.addEventListener("change", () => {
      void handleRunHistoryFilterChange();
    });
  }
  if (els.runHistoryBaseline) {
    els.runHistoryBaseline.addEventListener("change", () => {
      void handleRunHistoryFilterChange();
    });
  }

  if (els.runLocalBtn) {
    els.runLocalBtn.addEventListener("click", () => {
      state.simulationInfraProfile = "local";
      void startRun("local");
    });
  }
  if (els.runOssBtn) {
    els.runOssBtn.addEventListener("click", () => {
      state.simulationInfraProfile = "oss";
      void startRun("oss");
    });
  }
  if (els.simNextBtn) {
    els.simNextBtn.addEventListener("click", () => {
      void runSimulationNext();
    });
  }
  if (els.simPauseBtn) {
    els.simPauseBtn.addEventListener("click", () => {
      void pauseSimulation();
    });
  }
  if (els.simResumeBtn) {
    els.simResumeBtn.addEventListener("click", () => {
      void resumeSimulation();
    });
  }
  if (els.simResetBtn) {
    els.simResetBtn.addEventListener("click", () => {
      void resetSimulation();
    });
  }
  if (els.runContent) {
    els.runContent.addEventListener("change", (event) => {
      handleArtifactExplorerControlChange(event);
    });
    els.runContent.addEventListener("input", (event) => {
      handleArtifactExplorerControlChange(event);
    });
    els.runContent.addEventListener("click", (event) => {
      handleRunEvidenceTabClick(event);
      handleArtifactExplorerClick(event);
    });
  }
}

async function loadViewModel() {
  const candidates = ["/api/view-model", "../data/view_model.json", "/ui/data/view_model.json"];
  let lastError = null;

  for (const path of candidates) {
    try {
      const response = await fetch(path, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      if (!Array.isArray(data.use_cases)) {
        throw new Error("Invalid view model payload.");
      }
      return data;
    } catch (err) {
      lastError = err;
    }
  }

  throw new Error(
    `Unable to load UI data. Run 'make ui-build-data' then serve with 'make ui-serve'.\n${String(lastError)}`
  );
}

async function detectApiAvailability() {
  try {
    const response = await fetch("/api/health", { cache: "no-store" });
    state.apiAvailable = response.ok;
  } catch (_) {
    state.apiAvailable = false;
  }
}

async function refreshScenarioCatalog() {
  if (state.apiAvailable) {
    try {
      const response = await fetch("/api/scenarios", { cache: "no-store" });
      const body = await response.json();
      if (response.ok && Array.isArray(body.scenarios)) {
        state.scenarioCatalog = body.scenarios;
        return;
      }
    } catch (_) {
      // Fall through to local metadata fallback.
    }
  }
  const metaLibrary = state.data && state.data.meta && Array.isArray(state.data.meta.scenario_library)
    ? state.data.meta.scenario_library
    : [];
  state.scenarioCatalog = metaLibrary;
}

function hydrateScenarioSelector() {
  if (!els.runScenarioId) {
    return;
  }
  const useCaseId = state.selectedUseCaseId;
  const scenarios = Array.isArray(state.scenarioCatalog)
    ? state.scenarioCatalog.filter((row) => !useCaseId || row.use_case_id === useCaseId)
    : [];
  const options = [{ value: "", label: "none" }].concat(
    scenarios.map((row) => ({
      value: String(row.scenario_id || ""),
      label: `${String(row.scenario_id || "")} - ${String(row.title || "scenario")}`,
    }))
  );
  els.runScenarioId.innerHTML = options
    .map((row) => `<option value="${escapeHtml(row.value)}">${escapeHtml(row.label)}</option>`)
    .join("");
}

async function refreshOssInventory() {
  if (state.apiAvailable) {
    try {
      const response = await fetch("/api/oss-inventory", { cache: "no-store" });
      const body = await response.json();
      if (response.ok) {
        state.ossInventory = body;
        return;
      }
    } catch (_) {
      // Fallback below.
    }
  }
  state.ossInventory = null;
}

async function refreshEnterpriseHardening() {
  if (state.apiAvailable) {
    try {
      const profile = encodeURIComponent(state.enterpriseProfile || "standalone");
      const response = await fetch(`/api/enterprise-hardening?profile=${profile}`, {
        cache: "no-store",
      });
      const body = await response.json();
      if (response.ok) {
        state.enterpriseHardening = body;
        return;
      }
    } catch (_) {
      // Fallback below.
    }
  }
  state.enterpriseHardening = null;
}

async function startRun(infraProfile) {
  if (!state.apiAvailable) {
    setRunStatus("Live service unavailable. Start with `make ui-live`.", true);
    return;
  }

  const payload = {
    infra_profile: infraProfile,
    seed: Number(els.runSeed && els.runSeed.value ? els.runSeed.value : 101),
    use_case_id: (els.runSelectedOnly && els.runSelectedOnly.checked) ? state.selectedUseCaseId : null,
    runtime_mode: String((els.runRuntimeMode && els.runRuntimeMode.value) || "default"),
    scenario_id: String((els.runScenarioId && els.runScenarioId.value) || "").trim() || null,
    failure_injection: getFailureInjectionFlags(),
  };

  setRunButtonsDisabled(true);
  setRunStatus(`Submitting ${infraProfileLabel(infraProfile)} run...`, false);

  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      const err = body && body.error ? body.error : "run submission failed";
      throw new Error(err);
    }

    state.currentJobId = body.job_id;
    setRunStatus(`Job ${body.job_id} started (${infraProfileLabel(infraProfile)}).`, false);
    pollRunStatus();
  } catch (err) {
    setRunButtonsDisabled(false);
    setRunStatus(`Run failed to start: ${String(err.message || err)}`, true);
  }
}

function pollRunStatus() {
  if (!state.currentJobId) {
    setRunButtonsDisabled(false);
    return;
  }

  fetch(`/api/jobs/${state.currentJobId}`, { cache: "no-store" })
    .then((res) => res.json().then((body) => ({ ok: res.ok, body })))
    .then(async ({ ok, body }) => {
      if (!ok) {
        throw new Error((body && body.error) || "status check failed");
      }

      const status = body.status || "unknown";
      setRunStatus(`Job ${body.job_id}: ${status}`, status === "failed");

      if (status === "queued" || status === "running") {
        state.pollTimer = window.setTimeout(pollRunStatus, 1500);
        return;
      }

      state.currentJobId = null;
      setRunButtonsDisabled(false);

      if (status === "succeeded") {
        state.simulationSessionId = null;
        state.simulationState = null;
        state.data = await loadViewModel();
        await refreshOssInventory();
        await refreshEnterpriseHardening();
        state.runHistoryLoading = true;
        await refreshRunHistory();
        await refreshPortfolioSummary();
        render();
        setRunStatus(`Run completed successfully. UI refreshed from latest artifacts.`, false);
        return;
      }

      const output = body.output_tail ? ` | ${String(body.output_tail).slice(-280)}` : "";
      setRunStatus(`Run failed.${output}`, true);
    })
    .catch((err) => {
      state.currentJobId = null;
      setRunButtonsDisabled(false);
      setRunStatus(`Run polling error: ${String(err.message || err)}`, true);
    });
}

function setRunButtonsDisabled(disabled) {
  state.controlsLocked = Boolean(disabled);
  setSimulationPauseResumeState();
}

function setSimulationPauseResumeState() {
  const simulation = getActiveSimulationState(getSelectedUseCase());
  const paused = Boolean(simulation && simulation.paused);
  const controlsLocked = Boolean(state.controlsLocked || state.currentJobId);
  const liveExecutionEnabled = Boolean(state.apiAvailable);
  const simulationEnabled = Boolean(liveExecutionEnabled && state.selectedUseCaseId);
  const hasSession = Boolean(state.simulationSessionId || simulation);

  if (els.runLocalBtn) {
    els.runLocalBtn.disabled = controlsLocked || !liveExecutionEnabled;
  }
  if (els.runOssBtn) {
    els.runOssBtn.disabled = controlsLocked || !liveExecutionEnabled;
  }
  if (els.simNextBtn) {
    els.simNextBtn.disabled = controlsLocked || !simulationEnabled || paused;
  }
  if (els.simPauseBtn) {
    els.simPauseBtn.disabled = controlsLocked || !simulationEnabled || paused;
  }
  if (els.simResumeBtn) {
    els.simResumeBtn.disabled = controlsLocked || !simulationEnabled || !paused;
  }
  if (els.simResetBtn) {
    els.simResetBtn.disabled = controlsLocked || !liveExecutionEnabled || !hasSession;
  }
}

function clearRunStatus() {
  state.runStatusMessage = "";
  state.runStatusIsError = false;
  state.runStatusSticky = false;
}

function renderRunStatus() {
  if (!els.runStatus) {
    return;
  }
  let message = state.runStatusMessage;
  let isError = state.runStatusIsError;
  if (!message || (!state.currentJobId && !state.runStatusSticky)) {
    message = state.apiAvailable
      ? "Model execution available. Recommended path: Integrated AI Runtime."
      : "Model execution requires `make ui-live`. Static mode is active.";
    isError = false;
  }
  els.runStatus.textContent = message;
  els.runStatus.style.color = isError ? "#a93b3b" : "#3c556e";
}

function setRunStatus(message, isError, options) {
  const config = options && typeof options === "object" ? options : {};
  state.runStatusMessage = String(message || "");
  state.runStatusIsError = Boolean(isError);
  state.runStatusSticky = config.sticky !== false;
  renderRunStatus();
}

function getFailureInjectionFlags() {
  const flags = [];
  if (els.failureDq && els.failureDq.checked) {
    flags.push("dq_fail");
  }
  if (els.failureSchema && els.failureSchema.checked) {
    flags.push("schema_fail");
  }
  if (els.failureBackend && els.failureBackend.checked) {
    flags.push("backend_unavailable");
  }
  return flags;
}

async function runSimulationNext() {
  if (!state.apiAvailable) {
    setRunStatus("Simulation controls require `make ui-live`.", true);
    return;
  }
  if (!state.selectedUseCaseId) {
    setRunStatus("Select a use case before running simulation.", true);
    return;
  }

  setRunButtonsDisabled(true);
  try {
    const sessionId = await ensureSimulationSession();
    const response = await fetch(`/api/simulation/session/${encodeURIComponent(sessionId)}/run-next`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error((body && body.error) || "simulation run-next failed");
    }
    state.simulationState = body;
    setRunStatus(
      `Simulation advanced to stage ${body.stage_cursor}/${body.stage_total}.`,
      false
    );
    render();
  } catch (err) {
    setRunStatus(`Simulation step failed: ${String(err.message || err)}`, true);
  } finally {
    setRunButtonsDisabled(false);
  }
}

async function resetSimulation() {
  if (!state.apiAvailable) {
    setRunStatus("Simulation controls require `make ui-live`.", true);
    return;
  }
  if (!state.simulationSessionId) {
    state.simulationState = null;
    render();
    return;
  }
  setRunButtonsDisabled(true);
  try {
    const response = await fetch(
      `/api/simulation/session/${encodeURIComponent(state.simulationSessionId)}/reset`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      }
    );
    const body = await response.json();
    if (!response.ok) {
      throw new Error((body && body.error) || "simulation reset failed");
    }
    state.simulationState = body;
    setRunStatus("Simulation reset to stage 0.", false);
    render();
  } catch (err) {
    setRunStatus(`Simulation reset failed: ${String(err.message || err)}`, true);
  } finally {
    setRunButtonsDisabled(false);
  }
}

async function pauseSimulation() {
  if (!state.apiAvailable) {
    setRunStatus("Simulation controls require `make ui-live`.", true);
    return;
  }
  if (!state.selectedUseCaseId) {
    setRunStatus("Select a use case before pausing simulation.", true);
    return;
  }
  setRunButtonsDisabled(true);
  try {
    const sessionId = await ensureSimulationSession();
    const response = await fetch(
      `/api/simulation/session/${encodeURIComponent(sessionId)}/pause`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      }
    );
    const body = await response.json();
    if (!response.ok) {
      throw new Error((body && body.error) || "simulation pause failed");
    }
    state.simulationState = body;
    setRunStatus("Simulation paused.", false);
    render();
  } catch (err) {
    setRunStatus(`Simulation pause failed: ${String(err.message || err)}`, true);
  } finally {
    setRunButtonsDisabled(false);
  }
}

async function resumeSimulation() {
  if (!state.apiAvailable) {
    setRunStatus("Simulation controls require `make ui-live`.", true);
    return;
  }
  if (!state.selectedUseCaseId) {
    setRunStatus("Select a use case before resuming simulation.", true);
    return;
  }
  setRunButtonsDisabled(true);
  try {
    const sessionId = await ensureSimulationSession();
    const response = await fetch(
      `/api/simulation/session/${encodeURIComponent(sessionId)}/resume`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      }
    );
    const body = await response.json();
    if (!response.ok) {
      throw new Error((body && body.error) || "simulation resume failed");
    }
    state.simulationState = body;
    setRunStatus("Simulation resumed.", false);
    render();
  } catch (err) {
    setRunStatus(`Simulation resume failed: ${String(err.message || err)}`, true);
  } finally {
    setRunButtonsDisabled(false);
  }
}

async function ensureSimulationSession() {
  if (state.simulationSessionId && state.simulationState) {
    return state.simulationSessionId;
  }
  const payload = {
    use_case_id: state.selectedUseCaseId,
    infra_profile: state.simulationInfraProfile || "oss",
    seed: Number(els.runSeed && els.runSeed.value ? els.runSeed.value : 101),
    runtime_mode: String((els.runRuntimeMode && els.runRuntimeMode.value) || "default"),
    scenario_id: String((els.runScenarioId && els.runScenarioId.value) || "").trim() || null,
    failure_injection: getFailureInjectionFlags(),
  };
  const response = await fetch("/api/simulation/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error((body && body.error) || "simulation session creation failed");
  }
  state.simulationSessionId = body.session_id;
  state.simulationState = body;
  return body.session_id;
}

async function refreshRunHistory() {
  const useCaseId = state.selectedUseCaseId;
  const filters = getRunHistoryFilters();
  if (!useCaseId) {
    state.runHistoryLoading = false;
    return;
  }

  let runs = [];
  let meta = null;
  let loadedFromApi = false;
  if (state.apiAvailable) {
    try {
      const payload = await fetchRunHistory(useCaseId, filters);
      runs = Array.isArray(payload.runs) ? payload.runs : [];
      meta = {
        filters: payload.filters || null,
        baseline: payload.baseline || null,
      };
      loadedFromApi = true;
    } catch (_) {
      runs = [];
      meta = null;
    }
  }
  if (!loadedFromApi) {
    runs = fallbackRunHistory(useCaseId, filters);
    const fallbackBaselineRunId = runs.length ? String(runs[0].run_id || "") : null;
    meta = {
      filters: {
        limit: filters.limit,
        status: filters.status,
        infra: filters.infra,
        baseline: filters.baseline,
      },
      baseline: {
        requested: filters.baseline,
        resolved_run_id: fallbackBaselineRunId,
        strategy: "local_fallback",
      },
    };
  }

  state.runHistoryByUseCase[useCaseId] = runs;
  state.runHistoryMetaByUseCase[useCaseId] = meta;
  hydrateRunHistoryBaselineOptions(runs);
  await Promise.all([
    refreshStageDetailsForSelectedUseCase(),
    refreshRunSummaryForSelectedUseCase(),
  ]);
  state.runHistoryLoading = false;
  render();
}

async function fetchRunHistory(useCaseId, filters) {
  const query = new URLSearchParams({
    use_case_id: useCaseId,
    limit: String(filters.limit),
    status: filters.status,
    infra: filters.infra,
    baseline: filters.baseline,
  });
  const response = await fetch(`/api/run-history?${query.toString()}`, { cache: "no-store" });
  const body = await response.json();
  if (!response.ok) {
    throw new Error((body && body.error) || "run history fetch failed");
  }
  return body || {};
}

async function refreshRunSummaryForSelectedUseCase() {
  if (!state.apiAvailable) {
    return;
  }
  const selectedUseCase = getSelectedUseCase();
  const activeRun = resolveActiveRunForUseCase(selectedUseCase);
  if (!selectedUseCase || !activeRun || !activeRun.run_id) {
    return;
  }

  const runKey = buildRunKey(selectedUseCase.use_case_id, activeRun.run_id);
  if (Object.prototype.hasOwnProperty.call(state.runSummaryByRunKey, runKey)) {
    return;
  }

  try {
    const payload = await fetchRunSummary(selectedUseCase.use_case_id, activeRun.run_id);
    state.runSummaryByRunKey[runKey] = payload;
  } catch (_) {
    state.runSummaryByRunKey[runKey] = null;
  }
}

async function fetchRunSummary(useCaseId, runId) {
  const response = await fetch(`/api/runs/${encodeURIComponent(useCaseId)}/${encodeURIComponent(runId)}`, {
    cache: "no-store",
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error((body && body.error) || "run summary fetch failed");
  }
  return body || {};
}

async function refreshPortfolioSummary() {
  if (!state.apiAvailable) {
    state.portfolioSummary = null;
    state.portfolioLoading = false;
    return;
  }

  const filters = getRunHistoryFilters();
  state.portfolioLoading = true;
  try {
    const payload = await fetchPortfolioSummary(filters);
    state.portfolioSummary = payload;
  } catch (_) {
    state.portfolioSummary = null;
  } finally {
    state.portfolioLoading = false;
  }
}

async function fetchPortfolioSummary(filters) {
  const query = new URLSearchParams({
    status: filters.status,
    infra: filters.infra,
    sort: "desc",
    limit_per_use_case: "1",
  });
  const response = await fetch(`/api/portfolio/summary?${query.toString()}`, { cache: "no-store" });
  const body = await response.json();
  if (!response.ok) {
    throw new Error((body && body.error) || "portfolio summary fetch failed");
  }
  return body || {};
}

async function refreshStageDetailsForSelectedUseCase() {
  if (!state.apiAvailable) {
    return;
  }
  const selectedUseCase = getSelectedUseCase();
  const activeRun = resolveActiveRunForUseCase(selectedUseCase);
  if (!selectedUseCase || !activeRun || !activeRun.run_id) {
    return;
  }

  const runKey = buildRunKey(selectedUseCase.use_case_id, activeRun.run_id);
  if (Object.prototype.hasOwnProperty.call(state.stageDetailsByRunKey, runKey)) {
    return;
  }

  state.stageDetailsLoading = true;
  try {
    const payload = await fetchRunStageDetails(selectedUseCase.use_case_id, activeRun.run_id);
    state.stageDetailsByRunKey[runKey] = payload;
  } catch (_) {
    state.stageDetailsByRunKey[runKey] = null;
  } finally {
    state.stageDetailsLoading = false;
  }
}

async function fetchRunStageDetails(useCaseId, runId) {
  const response = await fetch(`/api/runs/${encodeURIComponent(useCaseId)}/${encodeURIComponent(runId)}/stages`, {
    cache: "no-store",
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error((body && body.error) || "run stage detail fetch failed");
  }
  return body || {};
}

function fallbackRunHistory(useCaseId, filters) {
  const useCases = (state.data && state.data.use_cases) || [];
  const selected = useCases.find((row) => row.use_case_id === useCaseId);
  if (!selected || !selected.latest_run) {
    return [];
  }

  const latest = selected.latest_run;
  const stageHealth = Array.isArray(latest.stage_health) ? latest.stage_health : [];
  const stagePassCount = stageHealth.filter((row) => row.status === "pass").length;
  const metricHighlights = Array.isArray(latest.metric_highlights) ? latest.metric_highlights : [];

  const run = {
    run_id: latest.run_id,
    run_status: latest.run_status,
    infra_profile: latest.infra_profile,
    seed: latest.seed,
    primary_kpi:
      (latest.model_metrics && latest.model_metrics.primary_kpi) ||
      selected.primary_kpi ||
      "n/a",
    kpi_values: metricHighlights,
    stage_health: stageHealth,
    stage_pass_count: stagePassCount,
    stage_total: stageHealth.length,
    summary_path: latest.summary_path || "",
  };

  if (!runMatchesFilters(run, filters)) {
    return [];
  }

  return [run].slice(0, filters.limit);
}

async function handleRunHistoryFilterChange() {
  state.runHistoryFilters = {
    limit: normalizeRunHistoryLimit(els.runHistoryLimit && els.runHistoryLimit.value),
    status: normalizeRunHistoryStatus(els.runHistoryStatus && els.runHistoryStatus.value),
    infra: normalizeRunHistoryInfra(els.runHistoryInfra && els.runHistoryInfra.value),
    baseline: normalizeRunHistoryBaseline(els.runHistoryBaseline && els.runHistoryBaseline.value),
  };
  if (state.selectedUseCaseId) {
    state.runHistoryByUseCase[state.selectedUseCaseId] = [];
    state.runHistoryMetaByUseCase[state.selectedUseCaseId] = null;
  }
  state.runHistoryLoading = true;
  state.portfolioLoading = true;
  render();
  await refreshRunHistory();
  await refreshPortfolioSummary();
  render();
}

function hydrateRunHistoryFilters() {
  state.runHistoryFilters = {
    limit: normalizeRunHistoryLimit(els.runHistoryLimit && els.runHistoryLimit.value),
    status: normalizeRunHistoryStatus(els.runHistoryStatus && els.runHistoryStatus.value),
    infra: normalizeRunHistoryInfra(els.runHistoryInfra && els.runHistoryInfra.value),
    baseline: normalizeRunHistoryBaseline(els.runHistoryBaseline && els.runHistoryBaseline.value),
  };

  if (els.runHistoryLimit) {
    els.runHistoryLimit.value = String(state.runHistoryFilters.limit);
  }
  if (els.runHistoryStatus) {
    els.runHistoryStatus.value = state.runHistoryFilters.status;
  }
  if (els.runHistoryInfra) {
    els.runHistoryInfra.value = state.runHistoryFilters.infra;
  }
  if (els.runHistoryBaseline) {
    els.runHistoryBaseline.value = state.runHistoryFilters.baseline;
  }
}

function getRunHistoryFilters() {
  return state.runHistoryFilters || { limit: 3, status: "all", infra: "all", baseline: "latest" };
}

function runMatchesFilters(run, filters) {
  const status = String(run.run_status || "unknown").toLowerCase();
  const infra = String(run.infra_profile || "local").toLowerCase();

  if (filters.status !== "all" && status !== filters.status) {
    return false;
  }
  if (filters.infra !== "all" && infra !== filters.infra) {
    return false;
  }
  return true;
}

function normalizeRunHistoryLimit(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return 3;
  }
  return Math.max(1, Math.min(12, Math.round(parsed)));
}

function normalizeRunHistoryStatus(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "pass" || normalized === "fail") {
    return normalized;
  }
  return "all";
}

function normalizeRunHistoryInfra(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "local" || normalized === "oss") {
    return normalized;
  }
  return "all";
}

function normalizeRunHistoryBaseline(value) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "latest";
  }
  if (normalized === "latest" || normalized === "previous") {
    return normalized;
  }
  return normalized;
}

function hydrateRunHistoryBaselineOptions(runs) {
  if (!els.runHistoryBaseline) {
    return;
  }

  const currentValue = normalizeRunHistoryBaseline(
    (state.runHistoryFilters && state.runHistoryFilters.baseline) || els.runHistoryBaseline.value
  );
  const options = [
    { value: "latest", label: "Latest Run" },
    { value: "previous", label: "Previous Run" },
  ];

  const seen = new Set(["latest", "previous"]);
  for (const run of runs) {
    const runId = String(run && run.run_id ? run.run_id : "").trim();
    if (!runId || seen.has(runId)) {
      continue;
    }
    options.push({ value: runId, label: `Run ${runId}` });
    seen.add(runId);
  }

  const hasCurrent = options.some((row) => row.value === currentValue);
  const selectedValue = hasCurrent ? currentValue : "latest";

  els.runHistoryBaseline.innerHTML = options
    .map((row) => `<option value="${escapeHtml(row.value)}">${escapeHtml(row.label)}</option>`)
    .join("");
  els.runHistoryBaseline.value = selectedValue;
  state.runHistoryFilters.baseline = selectedValue;
}

function setMode(mode) {
  if (state.mode === mode) {
    return;
  }
  state.mode = mode;
  render();
}

function hydrateUseCaseSelector() {
  const useCases = state.data.use_cases || [];
  els.useCaseSelect.innerHTML = "";

  for (const useCase of useCases) {
    const option = document.createElement("option");
    option.value = useCase.use_case_id;
    option.textContent = `${useCase.use_case_id} - ${useCase.name}`;
    els.useCaseSelect.appendChild(option);
  }

  const hasNba = useCases.find((row) => row.use_case_id === "UC-NBA-RET-001");
  state.selectedUseCaseId = hasNba ? hasNba.use_case_id : (useCases[0] && useCases[0].use_case_id);
  if (state.selectedUseCaseId) {
    els.useCaseSelect.value = state.selectedUseCaseId;
    if (!Object.prototype.hasOwnProperty.call(state.storyStageIndexByUseCase, state.selectedUseCaseId)) {
      state.storyStageIndexByUseCase[state.selectedUseCaseId] = 0;
    }
  }
}

function render() {
  if (!state.data) {
    return;
  }

  toggleModeButtons();
  renderPresentationPanels();

  const selectedUseCase = getSelectedUseCase();
  renderRuntimeBanner();
  renderRunHistory(selectedUseCase);
  renderPortfolioTiles(selectedUseCase);
  renderOssInventory();
  renderEnterpriseHardening();
  renderArchitecture(selectedUseCase);
  renderArchitectureStory(selectedUseCase);
  renderStory(selectedUseCase);
  renderRun(selectedUseCase);
  setSimulationPauseResumeState();
  renderRunStatus();
}

function setPresentationStep(step, hash) {
  state.presentationStep = step || "overview";
  if (hash && window.location.hash !== hash) {
    window.history.replaceState(null, "", hash);
  }
  renderPresentationPanels();
}

function presentationStepFromLocation() {
  const hash = String(window.location.hash || "").replace(/^#/, "");
  const map = {
    overview: "overview",
    configure: "configure",
    "architecture-story": "architecture",
    hardening: "hardening",
    evidence: "evidence",
  };
  return map[hash] || "overview";
}

function renderPresentationPanels() {
  const active = state.presentationStep || "overview";
  for (const link of els.presentationStepLinks) {
    const step = String(link.getAttribute("data-presentation-step") || "");
    link.classList.toggle("is-active", step === active);
  }
  for (const panel of els.presentationPanels) {
    const panelStep = String(panel.getAttribute("data-presentation-panel") || "");
    panel.classList.toggle("is-active", panelStep === active);
  }
  renderEvidencePanels();
}

function renderEvidencePanels() {
  const active = state.evidenceView || "history";
  for (const button of els.evidenceViewButtons) {
    const view = String(button.getAttribute("data-evidence-view") || "");
    const isActive = view === active;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-selected", isActive ? "true" : "false");
  }
  for (const panel of els.evidencePanels) {
    const view = String(panel.getAttribute("data-evidence-panel") || "");
    panel.classList.toggle("is-evidence-active", view === active);
  }
}

function renderRuntimeBanner() {
  if (!els.runtimeBanner) {
    return;
  }
  const runtime = (state.data.meta && state.data.meta.runtime) || {};
  const mode = runtime.mode || "latest_artifacts";
  const backendExecuted = Boolean(runtime.backend_executed);
  const scope = runtime.execution_scope || "none";
  const useCases = Array.isArray(runtime.executed_use_cases) ? runtime.executed_use_cases : [];
  const executedAt = runtime.executed_at_utc || "n/a";
  const executionMode = runtime.runtime_mode || "default";
  const scenarioId = runtime.scenario_id || "none";
  const failureInjection = Array.isArray(runtime.failure_injection) ? runtime.failure_injection : [];
  const simulation = getActiveSimulationState(getSelectedUseCase());
  const simulationText = simulation
    ? `| <strong>Simulation:</strong> ${escapeHtml(String(simulation.stage_cursor || 0))}/${escapeHtml(String(simulation.stage_total || 8))} ${simulation.paused ? "(paused)" : "(active)"}`
    : "";

  els.runtimeBanner.innerHTML = `
    <div>
      <strong>Data Mode:</strong> ${escapeHtml(mode)}
      | <strong>Backend Executed:</strong> ${backendExecuted ? "yes" : "no"}
      | <strong>Scope:</strong> ${escapeHtml(scope)}
      | <strong>Runtime:</strong> ${escapeHtml(infraProfileLabel(runtime.infra_profile || "local"))}
      | <strong>Seed:</strong> ${escapeHtml(String(runtime.seed ?? "n/a"))}
      | <strong>Execution Mode:</strong> ${escapeHtml(String(executionMode))}
      | <strong>Scenario:</strong> ${escapeHtml(String(scenarioId))}
      ${failureInjection.length ? `| <strong>Failure Injection:</strong> ${escapeHtml(failureInjection.join(", "))}` : ""}
      ${backendExecuted ? `| <strong>Executed At:</strong> ${escapeHtml(executedAt)}` : ""}
      ${useCases.length ? `| <strong>AI/ML Use Cases:</strong> ${escapeHtml(useCases.join(", "))}` : ""}
      ${simulationText}
    </div>
  `;
}

function toggleModeButtons() {
  const businessActive = state.mode === "business";
  if (els.modeBusiness) {
    els.modeBusiness.classList.toggle("is-active", businessActive);
    els.modeBusiness.setAttribute("aria-selected", businessActive ? "true" : "false");
  }
  if (els.modeTechnical) {
    els.modeTechnical.classList.toggle("is-active", !businessActive);
    els.modeTechnical.setAttribute("aria-selected", businessActive ? "false" : "true");
  }
}

function infraProfileLabel(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "oss") {
    return "Integrated AI Runtime";
  }
  if (normalized === "local") {
    return "Standalone AI Runtime";
  }
  if (normalized === "all") {
    return "All";
  }
  return normalized ? normalized.replaceAll("_", " ") : "n/a";
}

function getSelectedUseCase() {
  const useCases = state.data.use_cases || [];
  return useCases.find((row) => row.use_case_id === state.selectedUseCaseId) || useCases[0] || null;
}

function getActiveSimulationState(selectedUseCase) {
  if (!selectedUseCase || !state.simulationState) {
    return null;
  }
  return state.simulationState.use_case_id === selectedUseCase.use_case_id
    ? state.simulationState
    : null;
}

function resolveActiveRunForUseCase(selectedUseCase) {
  if (!selectedUseCase) {
    return null;
  }
  const useCaseId = selectedUseCase.use_case_id;
  const historyRuns = state.runHistoryByUseCase[useCaseId];
  let activeRun = null;
  if (Array.isArray(historyRuns) && historyRuns.length > 0) {
    activeRun = historyRuns[0];
  } else {
    activeRun = selectedUseCase.latest_run || null;
  }
  if (!activeRun || !activeRun.run_id) {
    return activeRun;
  }
  const fullSummary = getRunSummaryForRun(selectedUseCase, activeRun);
  if (!fullSummary) {
    return activeRun;
  }
  return {
    ...activeRun,
    ...fullSummary,
    comparison: activeRun.comparison || fullSummary.comparison,
  };
}

function buildRunKey(useCaseId, runId) {
  return `${String(useCaseId || "").trim()}::${String(runId || "").trim()}`;
}

function getStageDetailsForRun(selectedUseCase, run) {
  if (!selectedUseCase || !run || !run.run_id) {
    return null;
  }
  const key = buildRunKey(selectedUseCase.use_case_id, run.run_id);
  return Object.prototype.hasOwnProperty.call(state.stageDetailsByRunKey, key)
    ? state.stageDetailsByRunKey[key]
    : null;
}

function getRunSummaryForRun(selectedUseCase, run) {
  if (!selectedUseCase || !run || !run.run_id) {
    return null;
  }
  const key = buildRunKey(selectedUseCase.use_case_id, run.run_id);
  return Object.prototype.hasOwnProperty.call(state.runSummaryByRunKey, key)
    ? state.runSummaryByRunKey[key]
    : null;
}

function renderOssInventory() {
  if (!els.ossInventory) {
    return;
  }
  const payload = state.ossInventory;
  if (!payload || !Array.isArray(payload.components) || payload.components.length === 0) {
    els.ossInventory.innerHTML = `<div class="note-empty">Integration inventory is unavailable in static mode.</div>`;
    return;
  }

  const components = payload.components;
  const generatedAt = payload.generated_at_utc || "n/a";
  const featured = components
    .filter((row) => ["optional_oss_profile", "optional_product_integration", "repo"].includes(String(row.source || "")))
    .slice(0, 8);
  els.ossInventory.innerHTML = `
    <div class="oss-summary-head">
      <div>
        <span class="label">Integration Inventory</span>
        <strong>${escapeHtml(String(components.length))} components cataloged</strong>
        <p>Generated ${escapeHtml(String(generatedAt))}. Displaying the technologies that support the architecture path.</p>
      </div>
    </div>
    <div class="oss-feature-grid">
      ${featured
        .map(
          (row) => `
            <article>
              <strong>${escapeHtml(String(row.component || "Component"))}</strong>
              <span>${escapeHtml(String(row.technology || "n/a"))}</span>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function renderEnterpriseHardening() {
  if (!els.enterpriseHardening) {
    return;
  }
  const payload = state.enterpriseHardening;
  if (!payload || !Array.isArray(payload.modules) || payload.modules.length === 0) {
    els.enterpriseHardening.innerHTML = `<div class="note-empty">Enterprise hardening details are unavailable in static mode.</div>`;
    return;
  }
  const summary = payload.summary || {};
  const normalizedModules = payload.modules.map((row) => ({
    ...row,
    display_status: normalizeHardeningStatus(row.status),
  }));
  const lightweightRows = normalizedModules.filter((row) => String(row.category || "") === "lightweight");
  const heavyRows = normalizedModules.filter((row) => String(row.category || "") === "heavy");
  const readyRows = normalizedModules.filter((row) => row.display_status === "implemented");
  const plannedRows = normalizedModules.filter((row) => row.display_status !== "implemented");
  els.enterpriseHardening.innerHTML = `
    <div class="hardening-kpis">
      ${renderHardeningKpi("Mode", hardeningProfileLabel(payload.profile))}
      ${renderHardeningKpi("Integration Paths", `${readyRows.length}/${summary.module_count ?? normalizedModules.length}`)}
      ${renderHardeningKpi("Built-In Evidence", String(lightweightRows.length))}
      ${renderHardeningKpi("Tool Connectors", String(heavyRows.length))}
    </div>
    <div class="module-showcase">
      <section class="module-section implemented">
        <h3>Evidence Available In This Mode</h3>
        <div class="module-card-grid">
          ${readyRows.map(renderHardeningModuleCard).join("") || `<div class="note-empty">No integration evidence is active for this profile.</div>`}
        </div>
      </section>
      <section class="module-section planned">
        <h3>Available When Enabled</h3>
        <div class="module-card-grid">
          ${plannedRows.map(renderHardeningModuleCard).join("") || `<div class="note-empty">All enterprise integration paths are represented in this mode.</div>`}
        </div>
      </section>
    </div>
  `;
}

function renderHardeningKpi(label, value) {
  return `
    <article>
      <span>${escapeHtml(String(label))}</span>
      <strong>${escapeHtml(String(value))}</strong>
    </article>
  `;
}

function renderHardeningModuleCard(row) {
  const status = normalizeHardeningStatus(row.display_status || row.status);
  const statusTone = status === "implemented" ? "pass" : status === "available" ? "warn" : "unknown";
  const technology = String(row.technology || "").trim();
  const moduleName = technology || String(row.name || row.module_id || "module");
  return `
    <article class="module-card">
      <div>
        <strong>${escapeHtml(moduleName)}</strong>
        <span class="status ${statusTone}">${escapeHtml(hardeningStatusLabel(status, row.runtime_status))}</span>
      </div>
      <p>${escapeHtml(hardeningModuleStory(row))}</p>
    </article>
  `;
}

function normalizeHardeningStatus(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "implemented" || normalized === "ready") {
    return "implemented";
  }
  if (normalized === "available" || normalized === "available_not_configured") {
    return "available";
  }
  if (
    normalized === "planned" ||
    normalized === "config_missing_dependency" ||
    normalized === "optional_not_enabled"
  ) {
    return "planned";
  }
  return "planned";
}

function hardeningProfileLabel(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "product_like") {
    return "Enterprise Integration Profile";
  }
  if (normalized === "standalone") {
    return "Standalone AI Runtime";
  }
  return normalized ? normalized.replaceAll("_", " ") : "n/a";
}

function hardeningStatusLabel(status, runtimeStatus) {
  if (status === "implemented") {
    return String(runtimeStatus || "").toLowerCase() === "adapter_ready_missing_dependency"
      ? "Ready"
      : "Live";
  }
  if (status === "available") {
    return "Available";
  }
  return "Profile Off";
}

function hardeningModuleStory(row) {
  const moduleId = String(row.module_id || "");
  const target = formatStageLabel(row.target_stage);
  const runtime = formatHardeningRuntimeStatus(row.runtime_status);
  const stories = {
    mlflow: `Model lineage and experiment tracking path for ${target}.`,
    data_quality_artifacts: `Validation evidence exported from built-in quality gates.`,
    monitoring_artifacts: `Model and governance health summarized for review.`,
    prometheus_metrics: `Runtime and run metrics exposed for observability.`,
    feast: `Feature-store contract and offline feature export for ${target}.`,
    splink: `Probabilistic identity-resolution path for Customer 360.`,
    airflow: `Workflow scheduling wrapper for pipeline orchestration.`,
    keycloak: `OIDC and role model readiness for secured access.`,
  };
  const base = stories[moduleId] || `${target} integration path.`;
  return `${base} ${runtime}`;
}

function formatHardeningRuntimeStatus(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "dependency_available") {
    return "Connected when selected.";
  }
  if (normalized === "adapter_ready_missing_dependency") {
    return "Adapter artifact is emitted; external service is optional.";
  }
  if (normalized === "dependency_available_not_enabled") {
    return "Available but not selected in this profile.";
  }
  if (normalized === "not_enabled") {
    return "Not selected in this profile.";
  }
  return normalized ? normalized.replaceAll("_", " ") : "Adapter artifact is emitted.";
}

function formatStageLabel(value) {
  const raw = String(value || "n/a");
  if (raw === "n/a") {
    return raw;
  }
  return raw.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function renderRunHistory(selectedUseCase) {
  if (!els.runHistory) {
    return;
  }
  if (!selectedUseCase) {
    els.runHistory.innerHTML = `<div class="note-empty">Select a use case to view run history.</div>`;
    return;
  }

  const useCaseId = selectedUseCase.use_case_id;
  const runs = state.runHistoryByUseCase[useCaseId] || [];
  const filters = getRunHistoryFilters();
  const meta = state.runHistoryMetaByUseCase[useCaseId] || {};
  const baseline = meta.baseline || {};
  const baselineResolved = baseline.resolved_run_id || "n/a";

  if (state.runHistoryLoading && runs.length === 0) {
    els.runHistory.innerHTML = `<div class="note-empty">Loading run history...</div>`;
    return;
  }
  if (runs.length === 0) {
    els.runHistory.innerHTML = `
      <div class="note-empty">
        No run history available for ${escapeHtml(useCaseId)} with filters:
        limit=${escapeHtml(String(filters.limit))},
        status=${escapeHtml(filters.status)},
        runtime=${escapeHtml(infraProfileLabel(filters.infra))},
        baseline=${escapeHtml(filters.baseline)}.
      </div>
    `;
    return;
  }

  els.runHistory.innerHTML = `
    <div class="small" style="margin-bottom:8px;">
      Showing ${escapeHtml(String(runs.length))} run(s)
      | limit=${escapeHtml(String(filters.limit))}
      | status=${escapeHtml(filters.status)}
      | runtime=${escapeHtml(infraProfileLabel(filters.infra))}
      | baseline=${escapeHtml(filters.baseline)}
      | baseline_resolved=${escapeHtml(String(baselineResolved))}
    </div>
    <div class="run-history-scroll">
      ${runs.map((run) => renderRunHistoryCard(run)).join("")}
    </div>
  `;
}

function renderRunHistoryCard(run) {
  const stageRows = Array.isArray(run.stage_health) ? run.stage_health : [];
  const passCount = Number(
    run.stage_pass_count ?? stageRows.filter((stage) => stage.status === "pass").length
  );
  const stageTotal = Number(run.stage_total ?? stageRows.length);
  const kpiRows = Array.isArray(run.kpi_values) ? run.kpi_values : [];
  const kpiHtml = kpiRows.length
    ? kpiRows
        .slice(0, 2)
        .map(
          (kpi) =>
            `${escapeHtml(String(kpi.name || "metric"))}: ${escapeHtml(String(kpi.value ?? "n/a"))}`
        )
        .join("<br/>")
    : "No KPI values";

  return `
    <article class="history-card">
      <div class="history-head">
        <div class="history-run">${escapeHtml(String(run.run_id || "run"))}</div>
        <span class="status ${statusClass(run.run_status)}">${escapeHtml(String(run.run_status || "unknown"))}</span>
      </div>
      <div class="history-meta">
        <div><strong>Runtime:</strong> ${escapeHtml(infraProfileLabel(run.infra_profile || "local"))}</div>
        <div><strong>Primary KPI:</strong> ${escapeHtml(String(run.primary_kpi || "n/a"))}</div>
        <div class="small">${kpiHtml}</div>
        <div><strong>Pipeline Health:</strong> ${escapeHtml(String(passCount))}/${escapeHtml(String(stageTotal))} pass</div>
      </div>
      ${renderRunHistoryComparison(run.comparison)}
      <div class="history-stage-list">
        ${stageRows.map((stage) => `
          <div class="history-stage-row">
            <span>${escapeHtml(String(stage.label || stage.layer_id || "stage"))}</span>
            <span class="status ${statusClass(stage.status)}">${escapeHtml(String(stage.status || "unknown"))}</span>
          </div>
        `).join("")}
      </div>
    </article>
  `;
}

function renderRunHistoryComparison(comparison) {
  if (!comparison || !comparison.baseline_run_id) {
    return `
      <div class="history-compare">
        <div class="history-compare-row">
          <span>Comparison</span>
          <span class="delta-pill neutral">no baseline</span>
        </div>
      </div>
    `;
  }

  const stageDelta = Number.isFinite(Number(comparison.stage_pass_delta))
    ? Number(comparison.stage_pass_delta)
    : null;
  const stageDeltaClass = deltaClass(stageDelta);
  const stageDeltaText = stageDelta === null ? "n/a" : formatSigned(stageDelta, 0);
  const statusDeltaClass = statusTransitionClass(comparison.status_transition);

  const kpiRows = Array.isArray(comparison.kpi_deltas) ? comparison.kpi_deltas.slice(0, 2) : [];
  const kpiText = kpiRows.length
    ? kpiRows
        .map((row) => {
          const delta = Number.isFinite(Number(row.delta)) ? Number(row.delta) : null;
          const suffix = delta === null ? "n/a" : formatSigned(delta, 4);
          return `${row.name}: ${suffix}`;
        })
        .join(" | ")
    : "No comparable KPI delta";
  const kpiDrilldownRows = Array.isArray(comparison.kpi_deltas) ? comparison.kpi_deltas : [];
  const stageStatusRows = Array.isArray(comparison.stage_status_deltas)
    ? comparison.stage_status_deltas
    : [];
  const stageChangedRows = stageStatusRows.filter((row) => row && row.changed);

  const kpiDrilldownHtml = kpiDrilldownRows.length
    ? `
      <div class="table-wrap" style="margin-top:8px;">
        <table class="table">
          <thead>
            <tr>
              <th>KPI</th>
              <th>Baseline</th>
              <th>Current</th>
              <th>Delta</th>
            </tr>
          </thead>
          <tbody>
            ${kpiDrilldownRows
              .map((row) => {
                const delta = Number.isFinite(Number(row.delta)) ? Number(row.delta) : null;
                const deltaLabel = delta === null ? "n/a" : formatSigned(delta, 4);
                return `
                  <tr>
                    <td>${escapeHtml(String(row.name || "metric"))}</td>
                    <td>${escapeHtml(String(row.baseline ?? "n/a"))}</td>
                    <td>${escapeHtml(String(row.current ?? "n/a"))}</td>
                    <td><span class="delta-pill ${deltaClass(delta)}">${escapeHtml(deltaLabel)}</span></td>
                  </tr>
                `;
              })
              .join("")}
          </tbody>
        </table>
      </div>
    `
    : `<div class="small" style="margin-top:8px;">No KPI drilldown rows available.</div>`;

  const stageDrilldownHtml = stageStatusRows.length
    ? `
      <div class="table-wrap" style="margin-top:8px;">
        <table class="table">
          <thead>
            <tr>
              <th>Layer</th>
              <th>Baseline</th>
              <th>Current</th>
              <th>Changed</th>
            </tr>
          </thead>
          <tbody>
            ${stageStatusRows
              .map((row) => `
                <tr>
                  <td>${escapeHtml(String(row.layer_id || "unknown"))}</td>
                  <td><span class="status ${statusClass(row.baseline_status)}">${escapeHtml(String(row.baseline_status || "unknown"))}</span></td>
                  <td><span class="status ${statusClass(row.current_status)}">${escapeHtml(String(row.current_status || "unknown"))}</span></td>
                  <td><span class="delta-pill ${row.changed ? "down" : "neutral"}">${row.changed ? "yes" : "no"}</span></td>
                </tr>
              `)
              .join("")}
          </tbody>
        </table>
      </div>
    `
    : `<div class="small" style="margin-top:8px;">No stage comparison rows available.</div>`;

  return `
    <div class="history-compare">
      <div class="history-compare-row">
        <span>Baseline</span>
        <span class="small">${escapeHtml(String(comparison.baseline_run_id))}</span>
      </div>
      <div class="history-compare-row">
        <span>Status Transition</span>
        <span class="delta-pill ${statusDeltaClass}">${escapeHtml(String(comparison.status_transition || "n/a"))}</span>
      </div>
      <div class="history-compare-row">
        <span>Stage Pass Delta</span>
        <span class="delta-pill ${stageDeltaClass}">${escapeHtml(stageDeltaText)}</span>
      </div>
      <div class="history-compare-row">
        <span>KPI Delta</span>
        <span class="small">${escapeHtml(kpiText)}</span>
      </div>
      <details class="history-drilldown">
        <summary>Delta Drilldown (${escapeHtml(String(kpiDrilldownRows.length))} KPI, ${escapeHtml(String(stageChangedRows.length))}/${escapeHtml(String(stageStatusRows.length))} stage changes)</summary>
        <div class="small" style="margin-top:6px;">
          Baseline run: ${escapeHtml(String(comparison.baseline_run_id))}
        </div>
        ${kpiDrilldownHtml}
        ${stageDrilldownHtml}
      </details>
    </div>
  `;
}

function renderPortfolioTiles(selectedUseCase) {
  const snapshot = state.data.portfolio_snapshot || {};
  const portfolio = state.portfolioSummary;
  const totals = (portfolio && portfolio.totals) || {};
  const latestByUseCase = Array.isArray(portfolio && portfolio.latest_by_use_case)
    ? portfolio.latest_by_use_case
    : [];
  const selectedPortfolioRun = selectedUseCase
    ? latestByUseCase.find((row) => row.use_case_id === selectedUseCase.use_case_id) || null
    : null;
  const latestRun = resolveActiveRunForUseCase(selectedUseCase);
  const selectedRunStatus = selectedPortfolioRun
    ? `${String(selectedPortfolioRun.run_status || "unknown").toUpperCase()} / ${infraProfileLabel(selectedPortfolioRun.infra_profile || "local")}`
    : latestRun
      ? `${String(latestRun.run_status || "unknown").toUpperCase()} / ${infraProfileLabel(latestRun.infra_profile || "local")}`
      : "NO RUN";
  const avgStagePassRate = Number.isFinite(Number(totals.avg_stage_pass_rate))
    ? `${(Number(totals.avg_stage_pass_rate) * 100).toFixed(1)}%`
    : "n/a";
  const sourceLabel = state.apiAvailable
    ? (state.portfolioLoading ? "LIVE API (loading)" : "LIVE API")
    : "SNAPSHOT";

  const tiles = [
    { label: "AI/ML Use Cases", value: totals.use_case_count ?? snapshot.use_cases_total ?? 0 },
    {
      label: "Latest Runs Available",
      value: totals.use_case_count ?? snapshot.use_cases_with_runs ?? 0,
    },
    { label: "Latest Pass", value: totals.latest_pass_count ?? snapshot.latest_runs_pass ?? 0 },
    { label: "Latest Fail", value: totals.latest_fail_count ?? snapshot.latest_runs_fail ?? 0 },
    {
      label: selectedUseCase ? `Selected ${selectedUseCase.use_case_id}` : "Selected AI/ML Use Case",
      value: selectedRunStatus,
    },
    { label: "Avg Pipeline Pass Rate", value: avgStagePassRate },
    { label: "Portfolio Feed", value: sourceLabel },
  ];

  els.portfolioTiles.innerHTML = tiles
    .map(
      (tile) => `
        <article class="tile">
          <div class="tile-label">${escapeHtml(String(tile.label))}</div>
          <div class="tile-value">${escapeHtml(String(tile.value))}</div>
        </article>
      `
    )
    .join("");
}

function renderArchitecture(selectedUseCase) {
  const layers = (state.data.platform_flow || []).slice().sort((a, b) => a.order - b.order);
  const stageByLayerId = buildStageStatusMap(selectedUseCase);

  els.architectureFlow.innerHTML = layers
    .map((layer, idx) => {
      const stage = stageByLayerId.get(layer.layer_id);
      const status = stage ? stage.status : "unknown";
      const statusLabel = status.toUpperCase();
      const copy = state.mode === "business" ? layer.business_summary : layer.technical_summary;

      const componentPills = state.mode === "business"
        ? [
            ...layer.upstream.map((v) => `U: ${v}`),
            ...layer.downstream.map((v) => `D: ${v}`),
          ]
        : [
            ...layer.components.current,
            ...layer.components.oss_profile,
          ];

      return `
        <article class="layer-card" style="--delay:${idx};">
          <div class="layer-head">
            <span class="layer-order">${layer.order}</span>
            <span class="status ${statusClass(status)}">${statusLabel}</span>
          </div>
          <div class="layer-title">${escapeHtml(layer.label)}</div>
          <p class="layer-copy">${escapeHtml(copy)}</p>
          <div class="pill-row">
            ${componentPills.slice(0, 4).map((pill) => `<span class="pill">${escapeHtml(pill)}</span>`).join("")}
          </div>
        </article>
      `;
    })
    .join("");
}

function buildStageStatusMap(selectedUseCase) {
  const map = new Map();
  const activeRun = resolveActiveRunForUseCase(selectedUseCase);
  const stageDetails = getStageDetailsForRun(selectedUseCase, activeRun);
  const stageRows = stageDetails && Array.isArray(stageDetails.stages)
    ? stageDetails.stages
    : activeRun && Array.isArray(activeRun.stage_health)
      ? activeRun.stage_health
      : null;
  if (!Array.isArray(stageRows)) {
    return map;
  }

  for (const stage of stageRows) {
    map.set(stage.layer_id, stage);
  }
  return map;
}

function shiftArchitectureStoryIndex(delta) {
  const selectedUseCase = getSelectedUseCase();
  if (!selectedUseCase) {
    return;
  }
  const current = Number(state.storyStageIndexByUseCase[selectedUseCase.use_case_id] || 0);
  setArchitectureStoryIndex(current + Number(delta || 0));
}

function setArchitectureStoryIndex(nextIndex) {
  const selectedUseCase = getSelectedUseCase();
  if (!selectedUseCase) {
    return;
  }
  const activeRun = resolveActiveRunForUseCase(selectedUseCase);
  const stageDetails = getStageDetailsForRun(selectedUseCase, activeRun);
  const simulationState = getActiveSimulationState(selectedUseCase);
  const storyData = buildArchitectureStoryData(
    selectedUseCase,
    activeRun,
    stageDetails,
    simulationState
  );
  if (!Array.isArray(storyData.stages) || storyData.stages.length === 0) {
    return;
  }
  const clamped = Math.max(
    0,
    Math.min(storyData.stages.length - 1, Math.round(Number(nextIndex) || 0))
  );
  state.storyStageIndexByUseCase[selectedUseCase.use_case_id] = clamped;
  render();
}

function handleArchitectureStoryRailClick(event) {
  const target = event && event.target;
  if (!target || typeof target.closest !== "function") {
    return;
  }
  const button = target.closest("[data-story-index]");
  if (!button) {
    return;
  }
  const index = Number(button.getAttribute("data-story-index"));
  if (!Number.isFinite(index)) {
    return;
  }
  setArchitectureStoryIndex(index);
}

function renderArchitectureStory(selectedUseCase) {
  if (!els.architectureStory) {
    return;
  }
  if (state.mode !== "technical") {
    els.architectureStory.style.display = "none";
    return;
  }
  els.architectureStory.style.display = "";

  if (!selectedUseCase) {
    if (els.archStoryRail) {
      els.archStoryRail.innerHTML = "";
    }
    if (els.archStorySubtitle) {
      els.archStorySubtitle.textContent = "Select a use case to start technical walkthrough.";
    }
    if (els.archStageTitle) {
      els.archStageTitle.textContent = "No stage selected";
    }
    if (els.archStageSummary) {
      els.archStageSummary.textContent = "";
    }
    if (els.archStageWhat) {
      els.archStageWhat.textContent = "";
    }
    if (els.archStageProof) {
      els.archStageProof.innerHTML = "";
    }
    return;
  }

  const activeRun = resolveActiveRunForUseCase(selectedUseCase);
  const stageDetails = getStageDetailsForRun(selectedUseCase, activeRun);
  const simulationState = getActiveSimulationState(selectedUseCase);
  const storyData = buildArchitectureStoryData(
    selectedUseCase,
    activeRun,
    stageDetails,
    simulationState
  );

  const stages = Array.isArray(storyData.stages) ? storyData.stages : [];
  if (!stages.length) {
    if (els.archStorySubtitle) {
      els.archStorySubtitle.textContent = "No stage walkthrough data is available for this use case.";
    }
    if (els.archStoryRail) {
      els.archStoryRail.innerHTML = `<li class="note-empty">No stage rows found.</li>`;
    }
    return;
  }

  const useCaseId = selectedUseCase.use_case_id;
  const currentIndex = Number(
    Object.prototype.hasOwnProperty.call(state.storyStageIndexByUseCase, useCaseId)
      ? state.storyStageIndexByUseCase[useCaseId]
      : 0
  );
  const index = Math.max(0, Math.min(stages.length - 1, currentIndex));
  state.storyStageIndexByUseCase[useCaseId] = index;
  const stage = stages[index];

  if (els.archStoryTitle) {
    els.archStoryTitle.textContent = `${selectedUseCase.use_case_id} - ${selectedUseCase.name}`;
  }
  if (els.archStorySubtitle) {
    const runPart = storyData.runId ? `Run ${storyData.runId}. ` : "";
    els.archStorySubtitle.textContent = `${runPart}${storyData.sourceLabel}. ${storyData.sourceDetail}`;
  }
  if (els.archStoryProgress) {
    els.archStoryProgress.textContent = `${index + 1} / ${stages.length}`;
  }
  if (els.archStoryRail) {
    els.archStoryRail.innerHTML = stages
      .map((row, rowIdx) => {
        const activeClass = rowIdx === index ? " is-active" : "";
        return `
          <li>
            <button type="button" class="architecture-story-step${activeClass}" data-story-index="${rowIdx}">
              <span class="architecture-story-step-order">${row.order}</span>
              <span class="architecture-story-step-text">
                <span class="architecture-story-step-label">${escapeHtml(row.label)}</span>
                <span class="architecture-story-step-meta">${escapeHtml(String(row.status || "unknown").toUpperCase())}</span>
              </span>
            </button>
          </li>
        `;
      })
      .join("");
  }

  if (els.archStoryPrev) {
    els.archStoryPrev.disabled = index <= 0;
  }
  if (els.archStoryNext) {
    els.archStoryNext.disabled = index >= stages.length - 1;
  }

  if (els.archStageTitle) {
    els.archStageTitle.textContent = `${stage.order}. ${stage.label}`;
  }
  if (els.archStoryStatus) {
    els.archStoryStatus.innerHTML = `
      <span class="status ${statusClass(stage.status)}">${escapeHtml(String(stage.status || "unknown"))}</span>
    `;
  }
  if (els.archStageSummary) {
    els.archStageSummary.textContent = stage.summary;
  }
  if (els.archStageWhat) {
    els.archStageWhat.textContent = stage.headline || stage.what;
  }
  if (els.archStageProof) {
    els.archStageProof.innerHTML = renderStagePresentationProof(stage);
  }
  if (els.archStageInputs) {
    els.archStageInputs.innerHTML = renderStoryInputsCompact(stage);
  }
  if (els.archStageOutputs) {
    els.archStageOutputs.innerHTML = renderStoryOutputsCompact(stage);
  }
  if (els.archStageComponents) {
    els.archStageComponents.innerHTML = renderStoryComponents(stage);
  }
  if (els.archStageEvidence) {
    els.archStageEvidence.innerHTML = renderStoryEvidence(stage);
  }
  if (els.archStageSource) {
    els.archStageSource.textContent = storyData.sourceDetail;
  }
}

function buildArchitectureStoryData(selectedUseCase, activeRun, stageDetails, simulationState) {
  const fallbackGuidedSteps = activeRun && Array.isArray(activeRun.guided_steps)
    ? activeRun.guided_steps
    : [];
  const simulationStages = simulationState && simulationState.stage_details && Array.isArray(simulationState.stage_details.stages)
    ? simulationState.stage_details.stages
    : null;
  const liveStages = stageDetails && Array.isArray(stageDetails.stages)
    ? stageDetails.stages
    : null;

  let sourceRows = fallbackGuidedSteps;
  let sourceLabel = "Snapshot guided stage metadata";
  let sourceDetail = "Using `ui/data/view_model.json` stage guidance because no live stage API payload is active.";
  if (simulationStages) {
    sourceRows = simulationStages;
    sourceLabel = "Simulation session stage feed";
    sourceDetail = `Live simulation telemetry is active at stage ${Number(simulationState.stage_cursor || 0)}/${Number(simulationState.stage_total || 8)}.`;
  } else if (liveStages) {
    sourceRows = liveStages;
    sourceLabel = "Live stage API feed";
    sourceDetail = "Using `/api/runs/<use_case>/<run_id>/stages` as the active stage evidence source.";
  }

  const mergedRows = mergeGuidedSteps(sourceRows, fallbackGuidedSteps);
  const stageByLayerId = new Map(
    mergedRows
      .filter((row) => row && row.layer_id)
      .map((row) => [String(row.layer_id), row])
  );
  const flowRows = Array.isArray(state.data && state.data.platform_flow)
    ? state.data.platform_flow.slice().sort((a, b) => a.order - b.order)
    : [];
  const fileChecks = activeRun && Array.isArray(activeRun.artifact_file_checks)
    ? activeRun.artifact_file_checks
    : [];
  const monitoringGates = activeRun && activeRun.monitoring_report && activeRun.monitoring_report.validation_gates
    ? activeRun.monitoring_report.validation_gates
    : null;

  const stages = flowRows.map((layer) => {
    const stageRow = stageByLayerId.get(String(layer.layer_id)) || {};
    const inputs = Array.isArray(stageRow.inputs) ? stageRow.inputs : [];
    const outputs = Array.isArray(stageRow.outputs) ? stageRow.outputs : [];
    const componentsCurrent = Array.isArray(layer.components && layer.components.current)
      ? layer.components.current
      : [];
    const componentsOss = Array.isArray(layer.components && layer.components.oss_profile)
      ? layer.components.oss_profile
      : [];
    const componentsSwap = Array.isArray(layer.components && layer.components.scalable_swap_ins)
      ? layer.components.scalable_swap_ins
      : [];
    return {
      order: Number(layer.order || 0),
      layer_id: String(layer.layer_id || ""),
      label: String(stageRow.label || layer.label || layer.layer_id || "Stage"),
      status: String(stageRow.status || "unknown"),
      headline: String(
        (TECHNICAL_STAGE_STORY[layer.layer_id] && TECHNICAL_STAGE_STORY[layer.layer_id].headline) ||
        layer.technical_summary ||
        "This stage advances the platform contract."
      ),
      why: String(
        (TECHNICAL_STAGE_STORY[layer.layer_id] && TECHNICAL_STAGE_STORY[layer.layer_id].why) ||
        "This stage keeps the architecture reusable and inspectable."
      ),
      proof: String(
        (TECHNICAL_STAGE_STORY[layer.layer_id] && TECHNICAL_STAGE_STORY[layer.layer_id].proof) ||
        "Use the inputs, outputs, components, and evidence panels to validate the stage."
      ),
      summary: String(
        stageRow.explanation ||
        layer.technical_summary ||
        "Technical summary is not available for this stage."
      ),
      what: String(
        stageRow.detail ||
        layer.technical_summary ||
        "Stage detail is not available for this step."
      ),
      inputs,
      outputs,
      upstream: Array.isArray(layer.upstream) ? layer.upstream : [],
      downstream: Array.isArray(layer.downstream) ? layer.downstream : [],
      components_current: componentsCurrent,
      components_oss: componentsOss,
      components_swaps: componentsSwap,
      evidence_rows: buildStoryEvidenceRows(layer.layer_id, outputs, fileChecks),
      gates: layer.layer_id === "monitoring_governance" ? monitoringGates : null,
    };
  });

  return {
    stages,
    sourceLabel,
    sourceDetail,
    runId: activeRun && activeRun.run_id ? String(activeRun.run_id) : null,
  };
}

function renderStagePresentationProof(stage) {
  return `
    <div class="proof-card">
      <span class="label">Why This Stage Matters</span>
      <p>${escapeHtml(String(stage.why || ""))}</p>
    </div>
    <div class="proof-card">
      <span class="label">Evidence To Review</span>
      <p>${escapeHtml(String(stage.proof || ""))}</p>
    </div>
  `;
}

function renderStoryInputsCompact(stage) {
  const rows = Array.isArray(stage.inputs) ? stage.inputs : [];
  if (!rows.length) {
    return `<div class="small">No inputs captured.</div>`;
  }
  return `
    <div class="compact-list">
      ${rows.slice(0, 5).map((row) => `
        <div>
          <strong>${escapeHtml(String(row.name || "input"))}</strong>
          <span>${escapeHtml(formatStoryValue(row))}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function renderStoryOutputsCompact(stage) {
  const rows = Array.isArray(stage.outputs) ? stage.outputs : [];
  if (!rows.length) {
    return `<div class="small">No outputs captured.</div>`;
  }
  if (String(stage.layer_id || "") === "model_layer") {
    return renderModelLayerOutputsCompact(rows);
  }
  const artifactRows = rows.filter((row) => row && !String(row.name || "").startsWith("metric:"));
  const metricRows = rows.filter((row) => row && String(row.name || "").startsWith("metric:"));
  const artifactHtml = artifactRows.slice(0, 6).map((row) => `
    <div>
      <strong>${escapeHtml(formatStoryOutputName(row.name))}</strong>
      <span>${escapeHtml(formatStoryValue(row))}</span>
    </div>
  `).join("");
  const metricHtml = metricRows.length
    ? `
      <div class="metric-chip-row">
        ${metricRows.slice(0, 6).map((row) => `
          <span>${escapeHtml(formatStoryOutputName(row.name))}: ${escapeHtml(formatStoryValue(row))}</span>
        `).join("")}
      </div>
    `
    : "";
  return `
    <div class="compact-list">${artifactHtml}</div>
    ${metricHtml}
  `;
}

function renderModelLayerOutputsCompact(rows) {
  const artifactNames = ["model_predictions", "model_metrics", "model_manifest", "mlflow_lineage"];
  const metricNames = [
    "metric:model_backend",
    "metric:model_version",
    "metric:avg_confidence",
    "metric:avg_expected_uplift",
    "metric:train_row_count",
    "metric:holdout_ratio",
  ];
  const rowByName = new Map(rows.map((row) => [String(row && row.name ? row.name : ""), row]));
  const artifacts = artifactNames
    .map((name) => rowByName.get(name))
    .filter(Boolean);
  const metrics = metricNames
    .map((name) => rowByName.get(name))
    .filter(Boolean);

  return `
    <div class="model-output-brief">
      <div>
        <span class="label">Artifacts</span>
        <strong>Predictions, metrics, manifest, lineage</strong>
        <p>Model evidence is versioned as files, including MLflow-compatible lineage for enterprise review.</p>
      </div>
      <div>
        <span class="label">Runtime Signal</span>
        <strong>${escapeHtml(formatMetricBrief(metrics))}</strong>
        <p>Enough science detail to prove the backend ran, without turning the slide into a raw artifact dump.</p>
      </div>
    </div>
    <div class="compact-list model-artifact-list">
      ${artifacts.map((row) => `
        <div>
          <strong>${escapeHtml(formatStoryOutputName(row.name))}</strong>
          <span>${escapeHtml(formatStoryValue(row))}</span>
        </div>
      `).join("")}
    </div>
    <div class="metric-chip-row">
      ${metrics.map((row) => `
        <span>${escapeHtml(formatStoryOutputName(row.name))}: ${escapeHtml(formatStoryValue(row))}</span>
      `).join("")}
    </div>
  `;
}

function formatMetricBrief(rows) {
  const backend = rows.find((row) => String(row.name || "") === "metric:model_backend");
  const version = rows.find((row) => String(row.name || "") === "metric:model_version");
  const backendValue = backend ? formatStoryValue(backend) : "model backend";
  const versionValue = version ? formatStoryValue(version) : "versioned model";
  return `${backendValue} / ${versionValue}`;
}

function formatStoryOutputName(name) {
  return String(name || "output").replace(/^metric:/, "").replaceAll("_", " ");
}

function formatStoryValue(row) {
  if (!row || typeof row !== "object") {
    return "n/a";
  }
  if (Object.prototype.hasOwnProperty.call(row, "row_count")) {
    return `${String(row.row_count)} row(s)`;
  }
  if (Object.prototype.hasOwnProperty.call(row, "value")) {
    const value = row.value;
    if (value && typeof value === "object") {
      const keys = Object.keys(value);
      return keys.length ? `${keys.length} item(s): ${keys.slice(0, 3).join(", ")}` : "object";
    }
    if (typeof value === "number") {
      return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)));
    }
    return String(value ?? "n/a");
  }
  if (Object.prototype.hasOwnProperty.call(row, "path")) {
    return row.exists === false ? "artifact missing" : "artifact present";
  }
  return "captured";
}

function buildStoryEvidenceRows(layerId, outputs, fileChecks) {
  const outputRows = Array.isArray(outputs) ? outputs : [];
  const checks = Array.isArray(fileChecks) ? fileChecks : [];
  const outputPaths = new Set(
    outputRows
      .map((row) => (row && row.path ? String(row.path) : ""))
      .filter((path) => path)
  );
  const rows = checks
    .filter((row) => {
      const path = String((row && row.path) || "");
      const rowLayerId = resolveArtifactLayerIdByLabel(row && row.label);
      if (rowLayerId && String(rowLayerId) === String(layerId)) {
        return true;
      }
      return Boolean(path && outputPaths.has(path));
    })
    .map((row) => ({
      label: String((row && row.label) || "artifact"),
      path: String((row && row.path) || ""),
      exists: Boolean(row && row.exists),
    }));

  return rows.slice(0, 8);
}

function renderStoryComponents(stage) {
  const current = Array.isArray(stage.components_current) ? stage.components_current : [];
  const oss = Array.isArray(stage.components_oss) ? stage.components_oss : [];
  const swaps = Array.isArray(stage.components_swaps) ? stage.components_swaps : [];
  const sections = [];

  if (current.length) {
    sections.push(`
      <div>
        <strong>Current</strong>
        <div class="pill-row">${current.map((item) => `<span class="pill">${escapeHtml(String(item))}</span>`).join("")}</div>
      </div>
    `);
  }
  if (oss.length) {
    sections.push(`
      <div style="margin-top:8px;">
        <strong>Integrated Runtime</strong>
        <div class="pill-row">${oss.map((item) => `<span class="pill">${escapeHtml(String(item))}</span>`).join("")}</div>
      </div>
    `);
  }
  if (swaps.length) {
    sections.push(`
      <div style="margin-top:8px;">
        <strong>Enterprise Swap-Ins</strong>
        <div class="small">${swaps.map((item) => escapeHtml(String(item))).join(" | ")}</div>
      </div>
    `);
  }
  return sections.join("") || `<div class="small">No component metadata available.</div>`;
}

function renderStoryEvidence(stage) {
  const upstream = Array.isArray(stage.upstream) ? stage.upstream : [];
  const downstream = Array.isArray(stage.downstream) ? stage.downstream : [];
  const evidenceRows = Array.isArray(stage.evidence_rows) ? stage.evidence_rows : [];
  const gateEntries = stage.gates && typeof stage.gates === "object"
    ? Object.entries(stage.gates).sort((a, b) => String(a[0]).localeCompare(String(b[0])))
    : [];

  const evidenceTable = evidenceRows.length
    ? `
      <div class="evidence-chip-list">
        ${evidenceRows
          .slice(0, 6)
          .map(
            (row) => `
              <div>
                <strong>${escapeHtml(String(row.label || "artifact"))}</strong>
                <span class="status ${row.exists ? "pass" : "fail"}">${row.exists ? "Present" : "Missing"}</span>
              </div>
            `
          )
          .join("")}
      </div>
    `
    : `<div class="small" style="margin-top:8px;">No artifact checks mapped to this stage.</div>`;

  const gatesHtml = gateEntries.length
    ? `
      <div style="margin-top:10px;">
        <strong>Governance Gates</strong>
        <div class="small">${gateEntries.map(([gate, status]) => `${escapeHtml(String(gate))}: ${escapeHtml(String(status))}`).join(" | ")}</div>
      </div>
    `
    : "";

  return `
    <div class="small"><strong>Upstream:</strong> ${upstream.length ? upstream.map((row) => escapeHtml(String(row))).join(" | ") : "n/a"}</div>
    <div class="small" style="margin-top:4px;"><strong>Downstream:</strong> ${downstream.length ? downstream.map((row) => escapeHtml(String(row))).join(" | ") : "n/a"}</div>
    ${evidenceTable}
    ${gatesHtml}
  `;
}

function renderStory(selectedUseCase) {
  if (!selectedUseCase) {
    els.storyCaption.textContent = "No use case selected.";
    els.storyContent.innerHTML = `<div class="note-empty">No use-case metadata available.</div>`;
    return;
  }

  els.storyCaption.textContent = `${selectedUseCase.use_case_id} - ${selectedUseCase.name}`;
  if (state.mode === "business") {
    els.storyContent.innerHTML = renderBusinessStory(selectedUseCase);
    return;
  }
  els.storyContent.innerHTML = renderTechnicalStory(selectedUseCase);
}

function renderBusinessStory(useCase) {
  const contract = useCase.contract || {};
  const decisionPolicy = contract.decision_policy || {};

  return `
    <dl class="kv">
      <dt>Primary KPI</dt>
      <dd>${escapeHtml(useCase.primary_kpi || "n/a")}</dd>
      <dt>Baseline / Target</dt>
      <dd>${formatNullable(contract.baseline)} / ${formatNullable(contract.target)}</dd>
      <dt>Output Type</dt>
      <dd>${escapeHtml(contract.output_type || "n/a")}</dd>
      <dt>Refresh</dt>
      <dd>${escapeHtml(contract.refresh || "n/a")}</dd>
    </dl>

    <ul class="row-list">
      <li class="row-item">
        <strong>Business Problem</strong>
        <div class="small">${escapeHtml(useCase.business_problem || "")}</div>
      </li>
      <li class="row-item">
        <strong>Expected Outcome</strong>
        <div class="small">${escapeHtml(useCase.business_outcome || "")}</div>
      </li>
      <li class="row-item">
        <strong>Eligibility Rules</strong>
        ${renderSimpleList(decisionPolicy.eligibility_rules)}
      </li>
      <li class="row-item">
        <strong>Suppression Rules</strong>
        ${renderSimpleList(decisionPolicy.suppression_rules)}
      </li>
    </ul>
  `;
}

function renderTechnicalStory(useCase) {
  const contract = useCase.contract || {};
  const governance = contract.governance || {};
  const experiment = contract.experiment || {};

  return `
    <dl class="kv">
      <dt>Entities</dt>
      <dd>${Array.isArray(contract.entities) ? contract.entities.length : 0}</dd>
      <dt>Features</dt>
      <dd>${Array.isArray(contract.features) ? contract.features.length : 0}</dd>
      <dt>Output Fields</dt>
      <dd>${Array.isArray(contract.output_fields) ? contract.output_fields.length : 0}</dd>
      <dt>SLA Latency</dt>
      <dd>${formatNullable(contract.sla_latency_ms)} ms</dd>
      <dt>Experiment Unit</dt>
      <dd>${escapeHtml(String(experiment.unit || "n/a"))}</dd>
      <dt>Split</dt>
      <dd>${escapeHtml(String(experiment.split || "n/a"))}</dd>
    </dl>

    <ul class="row-list">
      <li class="row-item">
        <strong>Output Fields</strong>
        <div class="pill-row">
          ${(contract.output_fields || []).slice(0, 10).map((field) => `<span class="pill">${escapeHtml(field)}</span>`).join("")}
        </div>
      </li>
      <li class="row-item">
        <strong>Governance Gates</strong>
        ${renderSimpleList(governance.validation_gates)}
      </li>
      <li class="row-item">
        <strong>Feature Columns</strong>
        <div class="small">${escapeHtml((contract.features || []).join(", "))}</div>
      </li>
    </ul>
  `;
}

function renderRun(selectedUseCase) {
  if (!selectedUseCase) {
    els.runCaption.textContent = "No run metadata.";
    els.runContent.innerHTML = `<div class="note-empty">No run selected.</div>`;
    return;
  }

  const activeRun = resolveActiveRunForUseCase(selectedUseCase);
  if (!activeRun) {
    els.runCaption.textContent = "No run artifact detected.";
    els.runContent.innerHTML = `<div class="note-empty">Run the pipeline first, then regenerate UI data.</div>`;
    return;
  }

  const stageDetails = getStageDetailsForRun(selectedUseCase, activeRun);
  const simulationState = getActiveSimulationState(selectedUseCase);
  const hasSimulationStages = simulationState && simulationState.stage_details;
  const stageSource = hasSimulationStages ? "Simulation Session" : stageDetails ? "Live Stage API" : "Snapshot";
  const simProgress = hasSimulationStages
    ? ` | Simulation ${simulationState.stage_cursor}/${simulationState.stage_total}`
    : "";
  els.runCaption.textContent = `Run ${activeRun.run_id} | ${infraProfileLabel(activeRun.infra_profile)} | Stage Source: ${stageSource}${simProgress}`;
  if (state.mode === "business") {
    els.runContent.innerHTML = renderBusinessRun(activeRun);
    return;
  }
  els.runContent.innerHTML = renderTechnicalRun(
    activeRun,
    stageDetails,
    state.stageDetailsLoading,
    simulationState
  );
}

function renderBusinessRun(run) {
  state.artifactExplorerRows = [];
  state.artifactExplorerVisibleRows = [];
  const records = run.records || {};
  const highlights = Array.isArray(run.metric_highlights)
    ? run.metric_highlights
    : normalizeKpiRows(run.kpi_values);

  return `
    <dl class="kv">
      <dt>Run Status</dt>
      <dd><span class="status ${statusClass(run.run_status)}">${escapeHtml(String(run.run_status || "unknown"))}</span></dd>
      <dt>Curated Rows</dt>
      <dd>${formatNullable(records.curated_rows)}</dd>
      <dt>Feature Rows</dt>
      <dd>${formatNullable(records.feature_rows)}</dd>
      <dt>Activation Rows</dt>
      <dd>${formatNullable(records.activation_rows)}</dd>
    </dl>

    <div class="table-wrap" style="margin-top:10px;">
      <table class="table">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Value</th>
          </tr>
        </thead>
        <tbody>
          ${highlights.map((row) => `<tr><td>${escapeHtml(row.name)}</td><td>${escapeHtml(String(row.value))}</td></tr>`).join("") || "<tr><td colspan='2'>No metrics available.</td></tr>"}
        </tbody>
      </table>
    </div>

    ${renderOssSummary(run.oss_runtime, "Integrated AI Runtime")}
    ${renderOssSummary(run.oss_mirror, "Integrated Runtime Mirror")}
  `;
}

function renderTechnicalRun(run, stageDetails, stageLoading, simulationState) {
  const monitoring = run.monitoring_report || {};
  const simulationStages = simulationState && simulationState.stage_details && Array.isArray(simulationState.stage_details.stages)
    ? simulationState.stage_details.stages
    : null;
  const stageRows = simulationStages
    ? simulationStages.slice(0, Number(simulationState.stage_cursor || 0))
    : stageDetails && Array.isArray(stageDetails.stages)
    ? stageDetails.stages
    : Array.isArray(run.stage_health)
      ? run.stage_health
      : [];
  const fileChecks = Array.isArray(run.artifact_file_checks) ? run.artifact_file_checks : [];
  const fallbackGuidedSteps = Array.isArray(run.guided_steps) ? run.guided_steps : [];
  const guidedSteps = simulationStages
    ? mergeGuidedSteps(
        simulationStages.slice(0, Number(simulationState.stage_cursor || 0)),
        fallbackGuidedSteps
      )
    : stageDetails && Array.isArray(stageDetails.stages)
    ? mergeGuidedSteps(stageDetails.stages, fallbackGuidedSteps)
    : fallbackGuidedSteps;
  const stageSourceNote = simulationStages
    ? `<div class="small" style="margin-top:8px;">Simulation session active: stage ${escapeHtml(String(simulationState.stage_cursor || 0))}/${escapeHtml(String(simulationState.stage_total || 8))}.</div>`
    : stageDetails
    ? `<div class="small" style="margin-top:8px;">Stage details loaded from <strong>/api/runs/&lt;use_case&gt;/&lt;run_id&gt;/stages</strong>.</div>`
    : stageLoading
      ? `<div class="small" style="margin-top:8px;">Loading live stage details...</div>`
      : `<div class="small" style="margin-top:8px;">Using snapshot stage details from view model.</div>`;
  const artifactRows = buildArtifactExplorerRows({
    fileChecks,
    stageRows,
    guidedSteps,
  });
  const visibleArtifactRows = applyArtifactExplorerFilters(
    artifactRows,
    state.artifactExplorerFilters
  );
  state.artifactExplorerRows = artifactRows;
  state.artifactExplorerVisibleRows = visibleArtifactRows;
  const activeEvidenceView = normalizeRunEvidenceView(state.runEvidenceView);
  state.runEvidenceView = activeEvidenceView;

  return `
    <div class="run-evidence-tabs" role="tablist" aria-label="Run evidence detail views">
      ${renderRunEvidenceTab("summary", "Model Summary", activeEvidenceView)}
      ${renderRunEvidenceTab("stages", "Pipeline Health", activeEvidenceView)}
      ${renderRunEvidenceTab("gates", "Responsible AI Gates", activeEvidenceView)}
      ${renderRunEvidenceTab("artifacts", "Model Artifacts", activeEvidenceView)}
      ${renderRunEvidenceTab("trace", "Model Lineage Trace", activeEvidenceView)}
      ${renderRunEvidenceTab("runtime", "Runtime Evidence", activeEvidenceView)}
    </div>
    <div class="run-evidence-pane">
      ${renderRunEvidencePane("summary", activeEvidenceView, renderRunEvidenceSummary(run, stageRows, monitoring, artifactRows))}
      ${renderRunEvidencePane("stages", activeEvidenceView, renderRunStageHealth(stageRows, stageSourceNote))}
      ${renderRunEvidencePane("gates", activeEvidenceView, renderGateTable(monitoring.validation_gates) || `<div class="note-empty">No governance gates found.</div>`)}
      ${renderRunEvidencePane("artifacts", activeEvidenceView, renderArtifactExplorer(artifactRows, visibleArtifactRows))}
      ${renderRunEvidencePane("trace", activeEvidenceView, renderGuidedSteps(guidedSteps))}
      ${renderRunEvidencePane("runtime", activeEvidenceView, `${renderOssSummary(run.oss_runtime, "Integrated AI Runtime")}${renderOssSummary(run.oss_mirror, "Integrated Runtime Mirror")}` || `<div class="note-empty">No runtime evidence details found.</div>`)}
    </div>
  `;
}

function renderRunEvidenceTab(view, label, activeView) {
  const selected = view === activeView;
  return `
    <button
      type="button"
      class="run-evidence-tab${selected ? " is-active" : ""}"
      data-run-evidence-view="${escapeHtml(view)}"
      aria-selected="${selected ? "true" : "false"}"
    >${escapeHtml(label)}</button>
  `;
}

function renderRunEvidencePane(view, activeView, body) {
  return `
    <section class="run-evidence-subpanel${view === activeView ? " is-active" : ""}" data-run-evidence-panel="${escapeHtml(view)}">
      ${body}
    </section>
  `;
}

function renderRunEvidenceSummary(run, stageRows, monitoring, artifactRows) {
  const records = run.records && typeof run.records === "object" ? run.records : {};
  const passCount = Array.isArray(stageRows)
    ? stageRows.filter((row) => String(row.status || "").toLowerCase() === "pass").length
    : 0;
  const gateRows = monitoring && monitoring.validation_gates && typeof monitoring.validation_gates === "object"
    ? Object.values(monitoring.validation_gates)
    : [];
  const gatePassCount = gateRows.filter((status) => String(status || "").toLowerCase() === "pass").length;
  const artifactPresentCount = Array.isArray(artifactRows)
    ? artifactRows.filter((row) => row.exists).length
    : 0;
  return `
    <div class="run-evidence-summary-grid">
      ${renderEvidenceSummaryCard("Run Status", `<span class="status ${statusClass(run.run_status)}">${escapeHtml(String(run.run_status || "unknown"))}</span>`)}
      ${renderEvidenceSummaryCard("Runtime", escapeHtml(infraProfileLabel(run.infra_profile || "local")))}
      ${renderEvidenceSummaryCard("Pipeline Health", `${escapeHtml(String(passCount))}/${escapeHtml(String(Array.isArray(stageRows) ? stageRows.length : 0))} pass`)}
      ${renderEvidenceSummaryCard("Responsible AI Gates", `${escapeHtml(String(gatePassCount))}/${escapeHtml(String(gateRows.length))} pass`)}
      ${renderEvidenceSummaryCard("Model Artifacts", `${escapeHtml(String(artifactPresentCount))}/${escapeHtml(String(Array.isArray(artifactRows) ? artifactRows.length : 0))} present`)}
      ${renderEvidenceSummaryCard("Seed", escapeHtml(formatNullable(run.seed)))}
    </div>
    <dl class="kv run-evidence-kv">
      <dt>Summary Artifact</dt>
      <dd class="small">${escapeHtml(formatArtifactPathForDisplay(run.summary_path || "n/a"))}</dd>
      <dt>Curated Rows</dt>
      <dd>${formatNullable(records.curated_rows)}</dd>
      <dt>Feature Rows</dt>
      <dd>${formatNullable(records.feature_rows)}</dd>
      <dt>Model Rows</dt>
      <dd>${formatNullable(records.model_rows)}</dd>
      <dt>Activation Rows</dt>
      <dd>${formatNullable(records.activation_rows)}</dd>
    </dl>
  `;
}

function renderEvidenceSummaryCard(label, valueHtml) {
  return `
    <article>
      <span>${escapeHtml(label)}</span>
      <strong>${valueHtml}</strong>
    </article>
  `;
}

function renderRunStageHealth(stageRows, stageSourceNote) {
  return `
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Layer</th>
            <th>Status</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          ${stageRows.map((row) => `
            <tr>
              <td>${escapeHtml(row.label)}</td>
              <td><span class="status ${statusClass(row.status)}">${escapeHtml(row.status)}</span></td>
              <td>${escapeHtml(row.detail || "")}</td>
            </tr>
          `).join("") || "<tr><td colspan='3'>No stage health found.</td></tr>"}
        </tbody>
      </table>
    </div>
    ${stageSourceNote}
  `;
}

function normalizeRunEvidenceView(view) {
  const normalized = String(view || "summary");
  return ["summary", "stages", "gates", "artifacts", "trace", "runtime"].includes(normalized)
    ? normalized
    : "summary";
}

function handleRunEvidenceTabClick(event) {
  const target = event && event.target;
  if (!target || typeof target.closest !== "function") {
    return;
  }
  const button = target.closest("[data-run-evidence-view]");
  if (!button) {
    return;
  }
  state.runEvidenceView = normalizeRunEvidenceView(button.getAttribute("data-run-evidence-view"));
  renderRun(getSelectedUseCase());
}

function renderArtifactExplorer(allRows, visibleRows) {
  const rows = Array.isArray(allRows) ? allRows : [];
  const filtered = Array.isArray(visibleRows) ? visibleRows : [];
  const filters = state.artifactExplorerFilters || { stage: "all", exists: "all", query: "" };
  const stageOptions = [{ value: "all", label: "All Stages" }];
  const seen = new Set(["all"]);
  for (const row of rows) {
    const value = String(row.layer_id || "").trim();
    if (!value || seen.has(value)) {
      continue;
    }
    stageOptions.push({ value, label: String(row.layer_label || value) });
    seen.add(value);
  }

  return `
    <div style="margin-top:10px;">
      <strong>Artifact Explorer</strong>
      <div class="history-filters" style="margin-top:8px;">
        <label class="small-inline">
          Stage
          <select id="artifact-filter-stage" aria-label="Artifact stage filter">
            ${stageOptions
              .map((option) => `<option value="${escapeHtml(option.value)}"${option.value === filters.stage ? " selected" : ""}>${escapeHtml(option.label)}</option>`)
              .join("")}
          </select>
        </label>
        <label class="small-inline">
          Exists
          <select id="artifact-filter-exists" aria-label="Artifact existence filter">
            <option value="all"${filters.exists === "all" ? " selected" : ""}>All</option>
            <option value="present"${filters.exists === "present" ? " selected" : ""}>Present</option>
            <option value="missing"${filters.exists === "missing" ? " selected" : ""}>Missing</option>
          </select>
        </label>
        <label class="small-inline">
          Search
          <input id="artifact-filter-query" type="text" value="${escapeHtml(String(filters.query || ""))}" placeholder="path / label" />
        </label>
        <button id="artifact-download-visible" class="action-btn" type="button">Download Visible Bundle</button>
      </div>
      <div class="small" style="margin:6px 0 8px;">
        Showing ${escapeHtml(String(filtered.length))} of ${escapeHtml(String(rows.length))} artifact row(s).
      </div>
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Artifact</th>
              <th>Stage Trace</th>
              <th>Exists</th>
              <th>Download</th>
            </tr>
          </thead>
          <tbody>
            ${filtered
              .map(
                (row) => `
                  <tr>
                    <td class="small">${escapeHtml(String(row.label || "artifact"))}<br/>${escapeHtml(formatArtifactPathForDisplay(row.path || ""))}</td>
                    <td class="small">
                      ${
                        row.trace_href
                          ? `<a href="${escapeHtml(row.trace_href)}">${escapeHtml(String(row.layer_label || row.layer_id || "trace"))}</a>`
                          : escapeHtml(String(row.layer_label || row.layer_id || "n/a"))
                      }
                    </td>
                    <td><span class="status ${row.exists ? "pass" : "fail"}">${row.exists ? "true" : "false"}</span></td>
                    <td class="small">
                      ${
                        row.download_url
                          ? `<a href="${escapeHtml(row.download_url)}">download</a>`
                          : "n/a"
                      }
                    </td>
                  </tr>
                `
              )
              .join("") || "<tr><td colspan='4'>No artifacts match current filters.</td></tr>"}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function buildArtifactExplorerRows({ fileChecks, stageRows, guidedSteps }) {
  const checkRows = Array.isArray(fileChecks) ? fileChecks : [];
  const stages = Array.isArray(stageRows) ? stageRows : [];
  const guided = Array.isArray(guidedSteps) ? guidedSteps : [];
  const stageById = new Map(
    stages
      .filter((row) => row && row.layer_id)
      .map((row) => [String(row.layer_id), String(row.label || row.layer_id)])
  );
  const stageByPath = new Map();
  for (const step of guided) {
    if (!step || !step.layer_id || !Array.isArray(step.outputs)) {
      continue;
    }
    for (const output of step.outputs) {
      const path = output && output.path ? String(output.path) : "";
      if (!path) {
        continue;
      }
      stageByPath.set(path, String(step.layer_id));
    }
  }

  const rows = checkRows.map((row) => {
    const path = String((row && row.path) || "");
    const label = String((row && row.label) || "artifact");
    const explicitLayerId = stageByPath.get(path) || resolveArtifactLayerIdByLabel(label);
    const layerId = explicitLayerId || "unknown";
    const layerLabel = stageById.get(layerId) || layerId;
    const traceHref = explicitLayerId ? `#${stageTraceId(explicitLayerId)}` : "";
    const downloadUrl = path
      ? `/api/artifacts/download?path=${encodeURIComponent(path)}`
      : "";
    return {
      label,
      path,
      exists: Boolean(row && row.exists),
      layer_id: layerId,
      layer_label: layerLabel,
      trace_href: traceHref,
      download_url: downloadUrl,
    };
  });

  rows.sort((a, b) => {
    if (a.layer_label !== b.layer_label) {
      return a.layer_label.localeCompare(b.layer_label);
    }
    return a.label.localeCompare(b.label);
  });
  return rows;
}

function applyArtifactExplorerFilters(rows, filters) {
  const allRows = Array.isArray(rows) ? rows : [];
  const active = filters || { stage: "all", exists: "all", query: "" };
  const stage = String(active.stage || "all");
  const exists = String(active.exists || "all");
  const query = String(active.query || "").trim().toLowerCase();

  return allRows.filter((row) => {
    if (stage !== "all" && String(row.layer_id) !== stage) {
      return false;
    }
    if (exists === "present" && !row.exists) {
      return false;
    }
    if (exists === "missing" && row.exists) {
      return false;
    }
    if (query) {
      const haystack = `${String(row.label)} ${String(row.path)} ${String(row.layer_label)}`.toLowerCase();
      if (!haystack.includes(query)) {
        return false;
      }
    }
    return true;
  });
}

function resolveArtifactLayerIdByLabel(label) {
  const token = String(label || "").toLowerCase();
  if (token.startsWith("topic::")) {
    return "ingestion_event_bus";
  }
  if (token.includes("raw_events") || token.includes("curated_records")) {
    return "raw_curated_storage";
  }
  if (token.includes("identity_map") || token.includes("resolved_records") || token === "note") {
    return "identity_customer_360";
  }
  if (token.includes("feature_rows")) {
    return "feature_layer";
  }
  if (token.includes("model_")) {
    return "model_layer";
  }
  if (token.includes("activation_payloads")) {
    return "serving_activation";
  }
  if (token.includes("monitoring_report")) {
    return "monitoring_governance";
  }
  return null;
}

function stageTraceId(layerId) {
  return `trace-stage-${String(layerId || "stage")
    .toLowerCase()
    .replace(/[^a-z0-9_-]/g, "-")}`;
}

function handleArtifactExplorerControlChange(event) {
  const target = event && event.target;
  if (!target || !target.id) {
    return;
  }
  if (target.id === "artifact-filter-stage") {
    state.artifactExplorerFilters.stage = String(target.value || "all");
    render();
    return;
  }
  if (target.id === "artifact-filter-exists") {
    state.artifactExplorerFilters.exists = String(target.value || "all");
    render();
    return;
  }
  if (target.id === "artifact-filter-query") {
    state.artifactExplorerFilters.query = String(target.value || "");
    render();
  }
}

function handleArtifactExplorerClick(event) {
  const target = event && event.target;
  if (!target || target.id !== "artifact-download-visible") {
    return;
  }
  event.preventDefault();
  downloadVisibleArtifactBundle();
}

function downloadVisibleArtifactBundle() {
  const selectedUseCase = getSelectedUseCase();
  const activeRun = resolveActiveRunForUseCase(selectedUseCase);
  const payload = {
    generated_at_utc: new Date().toISOString(),
    use_case_id: selectedUseCase ? selectedUseCase.use_case_id : null,
    run_id: activeRun ? activeRun.run_id : null,
    filters: {
      ...(state.artifactExplorerFilters || {}),
    },
    artifact_rows: Array.isArray(state.artifactExplorerVisibleRows)
      ? state.artifactExplorerVisibleRows
      : [],
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const useCaseId = selectedUseCase ? selectedUseCase.use_case_id : "use_case";
  const runId = activeRun && activeRun.run_id ? activeRun.run_id : "run";
  link.href = url;
  link.download = `artifact_bundle_${useCaseId}_${runId}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function renderGuidedSteps(steps) {
  if (!steps.length) {
    return `<div class="note-empty" style="margin-top:10px;">No guided stage breakdown available.</div>`;
  }

  const body = steps
    .map((step, idx) => {
      const inputs = Array.isArray(step.inputs) ? step.inputs : [];
      const outputs = Array.isArray(step.outputs) ? step.outputs : [];
      return `
        <details id="${escapeHtml(stageTraceId(step.layer_id || `stage-${idx + 1}`))}" class="guided-step" ${idx === 0 ? "open" : ""}>
          <summary>
            <span>${escapeHtml(step.label || step.layer_id || "stage")}</span>
            <span class="status ${statusClass(step.status)}">${escapeHtml(String(step.status || "unknown"))}</span>
          </summary>
          <div class="guided-step-body">
            <div class="small">${escapeHtml(step.explanation || "")}</div>
            <div class="small" style="margin-top:6px;"><strong>Stage Detail:</strong> ${escapeHtml(step.detail || "")}</div>
            <div style="margin-top:8px;">
              <strong>Inputs</strong>
              ${renderGuidedKv(inputs)}
            </div>
            <div style="margin-top:8px;">
              <strong>Outputs</strong>
              ${renderGuidedOutputs(outputs)}
            </div>
          </div>
        </details>
      `;
    })
    .join("");

  return `
    <div style="margin-top:10px;">
      <strong>Guided Step-by-Step</strong>
      ${body}
    </div>
  `;
}

function renderGuidedKv(rows) {
  if (!rows.length) {
    return `<div class="small">No inputs captured.</div>`;
  }
  return `
    <div class="table-wrap" style="margin-top:6px;">
      <table class="table">
        <thead>
          <tr><th>Name</th><th>Value</th></tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (row) => {
                const value = row && Object.prototype.hasOwnProperty.call(row, "value")
                  ? row.value
                  : row && Object.prototype.hasOwnProperty.call(row, "path")
                    ? `${formatArtifactPathForDisplay(row.path || "")} (${row.exists ? "exists" : "missing"})`
                    : "";
                return `<tr><td>${escapeHtml(String(row.name ?? ""))}</td><td>${escapeHtml(String(value ?? ""))}</td></tr>`;
              }
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderGuidedOutputs(rows) {
  if (!rows.length) {
    return `<div class="small">No outputs captured.</div>`;
  }
  return `
    <div class="table-wrap" style="margin-top:6px;">
      <table class="table">
        <thead>
          <tr><th>Output</th><th>Exists</th><th>Value</th><th>Fields</th></tr>
        </thead>
        <tbody>
          ${rows
            .map((row) => {
              const fields = Array.isArray(row.sample_fields) ? row.sample_fields.join(", ") : "";
              const hasExists = Object.prototype.hasOwnProperty.call(row || {}, "exists");
              const exists = hasExists ? Boolean(row.exists) : null;
              const existsClass = exists === null ? "unknown" : exists ? "pass" : "fail";
              const existsLabel = exists === null ? "n/a" : exists ? "true" : "false";
              const value = Object.prototype.hasOwnProperty.call(row || {}, "value")
                ? row.value
                : row.row_count;
              return `
                <tr>
                  <td class="small">
                    ${escapeHtml(String(row.name || ""))}
                    ${row.path ? `<br/>${escapeHtml(formatArtifactPathForDisplay(row.path))}` : ""}
                    ${row.note ? `<br/>${escapeHtml(String(row.note))}` : ""}
                  </td>
                  <td><span class="status ${existsClass}">${escapeHtml(existsLabel)}</span></td>
                  <td>${escapeHtml(String(value ?? "n/a"))}</td>
                  <td class="small">${escapeHtml(fields || "n/a")}</td>
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderGateTable(gates) {
  if (!gates || typeof gates !== "object") {
    return "";
  }

  const rows = Object.keys(gates)
    .sort()
    .map(
      (gate) => `
      <tr>
        <td>${escapeHtml(gate)}</td>
        <td><span class="status ${statusClass(gates[gate])}">${escapeHtml(String(gates[gate]))}</span></td>
      </tr>
    `
    )
    .join("");

  return `
    <div class="table-wrap" style="margin-top:10px;">
      <table class="table">
        <thead>
          <tr>
            <th>Validation Gate</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${rows || "<tr><td colspan='2'>No governance gates found.</td></tr>"}
        </tbody>
      </table>
    </div>
  `;
}

function renderOssSummary(section, title) {
  if (!section) {
    return "";
  }

  const warnings = Array.isArray(section.warnings) ? section.warnings : [];
  return `
    <ul class="row-list" style="margin-top:10px;">
      <li class="row-item">
        <strong>${escapeHtml(title)}</strong>
        <div class="small">status: ${escapeHtml(String(section.status || "unknown"))}</div>
        <div class="small">kafka_topics_published: ${formatNullable(section.kafka_topics_published)}</div>
        <div class="small">kafka_messages_consumed: ${formatNullable(section.kafka_messages_consumed)}</div>
        <div class="small">postgres_rows_loaded: ${formatNullable(section.postgres_rows_loaded)}</div>
        <div class="small">minio_objects_uploaded: ${formatNullable(section.minio_objects_uploaded)}</div>
        ${warnings.length ? `<div class="small">warnings: ${escapeHtml(warnings.join(" | "))}</div>` : ""}
      </li>
    </ul>
  `;
}

function renderSimpleList(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return `<div class="small">No entries.</div>`;
  }
  return `<div class="small">${values.map((v) => escapeHtml(String(v))).join(" | ")}</div>`;
}

function normalizeKpiRows(rows) {
  if (!Array.isArray(rows)) {
    return [];
  }
  return rows
    .filter((row) => row && typeof row === "object")
    .map((row) => ({
      name: row.name,
      value: row.value,
    }));
}

function mergeGuidedSteps(stageSteps, fallbackSteps) {
  const fallbackByLayer = new Map();
  for (const step of fallbackSteps) {
    if (!step || typeof step !== "object") {
      continue;
    }
    const key = String(step.layer_id || "").trim();
    if (!key) {
      continue;
    }
    fallbackByLayer.set(key, step);
  }
  return stageSteps.map((step) => {
    const key = String((step && step.layer_id) || "").trim();
    const fallback = key ? fallbackByLayer.get(key) : null;
    return {
      ...step,
      explanation: step && step.explanation ? step.explanation : (fallback && fallback.explanation) || "",
    };
  });
}

function formatNullable(value) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return String(value);
}

function formatArtifactPathForDisplay(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  const marker = "/artifacts/";
  const markerIndex = text.indexOf(marker);
  if (markerIndex >= 0) {
    return `artifacts/${text.slice(markerIndex + marker.length)}`;
  }
  return text;
}

function deltaClass(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "neutral";
  }
  if (Number(value) > 0) {
    return "up";
  }
  if (Number(value) < 0) {
    return "down";
  }
  return "neutral";
}

function formatSigned(value, precision) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "n/a";
  }
  const amount = Number(value);
  const prefix = amount > 0 ? "+" : "";
  return `${prefix}${amount.toFixed(precision)}`;
}

function statusTransitionClass(transition) {
  const token = String(transition || "").toLowerCase();
  if (token.endsWith("->pass")) {
    return "up";
  }
  if (token.endsWith("->fail")) {
    return "down";
  }
  return "neutral";
}

function statusClass(status) {
  if (!status) {
    return "unknown";
  }
  const token = String(status).toLowerCase();
  if (token === "pass" || token === "executed" || token === "true") {
    return "pass";
  }
  if (token === "fail" || token === "false") {
    return "fail";
  }
  if (token.includes("fallback") || token.includes("warn")) {
    return "warn";
  }
  return "unknown";
}

function renderFatal(err) {
  els.portfolioTiles.innerHTML = "";
  els.architectureFlow.innerHTML = "";
  if (els.architectureStory) {
    els.architectureStory.style.display = "none";
  }
  if (els.runHistory) {
    els.runHistory.innerHTML = "";
  }
  els.storyCaption.textContent = "UI data unavailable";
  els.runCaption.textContent = "";

  const msg = escapeHtml(err && err.message ? err.message : String(err));
  const fallback = `<div class="note-empty">${msg}</div>`;
  els.storyContent.innerHTML = fallback;
  els.runContent.innerHTML = fallback;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

init();
