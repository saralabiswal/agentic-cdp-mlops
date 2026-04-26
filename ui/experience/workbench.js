(() => {
  "use strict";

  const SCENARIOS = {
    nba: {
      key: "nba",
      label: "TensorFlow Next Best Action Model",
      useCaseId: "UC-NBA-RET-001",
      storyboardHref: "workbench.html?scenario=nba&persona=business&step=1",
      businessSteps: ["Model Inputs", "Model Recommendation", "Impact Forecast", "Decision Evidence"],
      technicalSteps: ["Data + Model Contract", "Model Runtime + Activation", "Responsible AI Evidence"],
    },
    churn: {
      key: "churn",
      label: "TensorFlow Churn Propensity Model",
      useCaseId: "UC-CHURN-RET-002",
      storyboardHref: "workbench.html?scenario=churn&persona=business&step=1",
      businessSteps: ["Model Inputs", "Risk Recommendation", "Retention Forecast", "Decision Evidence"],
      technicalSteps: ["Data + Model Contract", "Model Runtime + Activation", "Responsible AI Evidence"],
    },
    mmm: {
      key: "mmm",
      label: "Bayesian Media Mix Optimization",
      useCaseId: "UC-MMM-PLN-003",
      storyboardHref: "workbench.html?scenario=mmm&persona=business&step=1",
      businessSteps: ["Model Inputs", "Budget Recommendation", "ROI Forecast", "Decision Evidence"],
      technicalSteps: ["Data + Model Contract", "Model Runtime + Activation", "Responsible AI Evidence"],
    },
    incrementality: {
      key: "incrementality",
      label: "Causal Incrementality Model",
      useCaseId: "UC-INCR-MKT-004",
      storyboardHref: "workbench.html?scenario=incrementality&persona=business&step=1",
      businessSteps: ["Model Inputs", "Lift Recommendation", "Incrementality Forecast", "Decision Evidence"],
      technicalSteps: ["Data + Model Contract", "Model Runtime + Activation", "Responsible AI Evidence"],
    },
  };

  const TECH_STAGE_GROUPS = [
    ["data_sources", "ingestion_event_bus", "raw_curated_storage"],
    ["identity_customer_360", "feature_layer", "model_layer", "serving_activation"],
    ["monitoring_governance"],
  ];

  const LAYER_LABELS = {
    data_sources: "Data Sources",
    ingestion_event_bus: "Ingestion + Event Bus",
    raw_curated_storage: "Raw Storage + Curated Warehouse",
    identity_customer_360: "Identity Resolution + Customer 360",
    feature_layer: "Feature Layer",
    model_layer: "Model Layer",
    serving_activation: "Serving + Activation",
    monitoring_governance: "Monitoring + Governance",
  };

  const state = {
    scenarioKey: "nba",
    persona: "business",
    step: 0,
    loading: false,
    error: null,
    cache: new Map(),
    artifactFilters: {
      stage: "all",
      exists: "all",
      query: "",
    },
  };

  const els = {
    scenarioButtons: Array.from(document.querySelectorAll("[data-scenario]")),
    personaButtons: Array.from(document.querySelectorAll("[data-persona]")),
    stepButtons: Array.from(document.querySelectorAll("[data-step-index]")),
    refresh: document.getElementById("wb-refresh"),
    prev: document.getElementById("wb-prev-step"),
    next: document.getElementById("wb-next-step"),
    modeKicker: document.getElementById("wb-mode-kicker"),
    pageTitle: document.getElementById("wb-page-title"),
    stepTitle: document.getElementById("wb-step-title"),
    stepSubtitle: document.getElementById("wb-step-subtitle"),
    content: document.getElementById("wb-content"),
    liveStatus: document.getElementById("wb-live-status"),
    progress: document.getElementById("wb-progress-fill"),
    runId: document.getElementById("wb-run-id"),
    runStatus: document.getElementById("wb-run-status"),
    passRate: document.getElementById("wb-pass-rate"),
    runtime: document.getElementById("wb-runtime"),
    openStoryboard: document.getElementById("wb-open-storyboard"),
    techCard: document.getElementById("wb-tech-card"),
    techComponents: document.getElementById("wb-tech-components"),
    techArtifacts: document.getElementById("wb-tech-artifacts"),
    techDq: document.getElementById("wb-tech-dq"),
    techBackend: document.getElementById("wb-tech-backend"),
  };

  function toNumber(value) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string" && value.trim() !== "") {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
    return null;
  }

  function formatPercent(value, digits = 1) {
    const numeric = toNumber(value);
    if (numeric === null) {
      return "n/a";
    }
    return `${(numeric * 100).toFixed(digits)}%`;
  }

  function formatSignedPercent(value, digits = 1) {
    const numeric = toNumber(value);
    if (numeric === null) {
      return "n/a";
    }
    const prefix = numeric > 0 ? "+" : "";
    return `${prefix}${formatPercent(numeric, digits)}`;
  }

  function formatCompact(value) {
    const numeric = toNumber(value);
    if (numeric === null) {
      return "n/a";
    }
    const rounded = Math.round(numeric);
    if (Math.abs(rounded) >= 1_000_000) {
      return `${(rounded / 1_000_000).toFixed(1)}M`;
    }
    if (Math.abs(rounded) >= 1_000) {
      return `${(rounded / 1_000).toFixed(1)}K`;
    }
    return String(rounded);
  }

  function formatCurrency(value) {
    const numeric = toNumber(value);
    if (numeric === null) {
      return "n/a";
    }
    const abs = Math.abs(numeric);
    if (abs >= 1_000_000_000) {
      return `$${(numeric / 1_000_000_000).toFixed(1)}B`;
    }
    if (abs >= 1_000_000) {
      return `$${(numeric / 1_000_000).toFixed(1)}M`;
    }
    if (abs >= 1_000) {
      return `$${(numeric / 1_000).toFixed(1)}K`;
    }
    return `$${numeric.toFixed(0)}`;
  }

  function formatDurationMs(value) {
    const numeric = toNumber(value);
    if (numeric === null) {
      return "n/a";
    }
    if (numeric >= 1000) {
      return `${(numeric / 1000).toFixed(2)}s`;
    }
    return `${numeric.toFixed(1)}ms`;
  }

  function formatValue(value) {
    if (value === null || value === undefined) {
      return "n/a";
    }
    if (typeof value === "number") {
      if (Math.abs(value) >= 1000) {
        return formatCompact(value);
      }
      return Number.isInteger(value) ? String(value) : value.toFixed(4);
    }
    if (typeof value === "boolean") {
      return value ? "true" : "false";
    }
    if (Array.isArray(value)) {
      if (value.length === 0) {
        return "[]";
      }
      const compact = value.map((row) => String(row)).slice(0, 6).join(", ");
      return value.length > 6 ? `${compact}, +${value.length - 6} more` : compact;
    }
    if (typeof value === "object") {
      return JSON.stringify(value);
    }
    return String(value);
  }

  function escapeHtml(text) {
    return String(text)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function pickScenarioFromQuery(value) {
    const key = String(value || "").trim().toLowerCase();
    return SCENARIOS[key] ? key : "nba";
  }

  function pickPersonaFromQuery(value) {
    const persona = String(value || "").trim().toLowerCase();
    return persona === "technical" ? "technical" : "business";
  }

  function pickStepFromQuery(value) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      const index = Math.round(parsed) - 1;
      return Math.max(0, Math.min(currentMaxStepIndex(), index));
    }
    return 0;
  }

  function updateQueryString() {
    const params = new URLSearchParams(window.location.search);
    params.set("scenario", state.scenarioKey);
    params.set("persona", state.persona);
    params.set("step", String(state.step + 1));
    const nextUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState(null, "", nextUrl);
  }

  function stepTitlesForCurrentPersona() {
    const scenario = SCENARIOS[state.scenarioKey];
    return state.persona === "technical" ? scenario.technicalSteps : scenario.businessSteps;
  }

  function currentMaxStepIndex() {
    return Math.max(0, stepTitlesForCurrentPersona().length - 1);
  }

  function statusClass(status) {
    const normalized = String(status || "unknown").toLowerCase();
    if (
      normalized === "pass" ||
      normalized === "executed" ||
      normalized === "true" ||
      normalized === "ready" ||
      normalized === "success" ||
      normalized === "succeeded"
    ) {
      return "wb-status-pass";
    }
    if (
      normalized === "warn" ||
      normalized.includes("warn") ||
      normalized === "queued" ||
      normalized === "running" ||
      normalized === "pending" ||
      normalized === "in_progress"
    ) {
      return "wb-status-warn";
    }
    if (
      normalized === "fail" ||
      normalized === "failed" ||
      normalized === "error" ||
      normalized === "false" ||
      normalized === "blocked"
    ) {
      return "wb-status-fail";
    }
    if (normalized === "unknown" || normalized === "n/a" || normalized === "not_available") {
      return "wb-status-neutral";
    }
    return "wb-status-neutral";
  }

  function fetchJson(url) {
    return fetch(url, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    }).then(async (response) => {
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        const message = body && typeof body.error === "string" ? body.error : `HTTP ${response.status}`;
        throw new Error(message);
      }
      return body;
    });
  }

  function extractRows(payload) {
    if (Array.isArray(payload)) {
      return payload;
    }
    if (payload && typeof payload === "object" && Array.isArray(payload.rows)) {
      return payload.rows;
    }
    return [];
  }

  function aggregateReasonCodes(rows) {
    const counts = new Map();
    rows.forEach((row) => {
      const reasonCodes = Array.isArray(row.reason_codes) ? row.reason_codes : [];
      reasonCodes.forEach((reason) => {
        const key = String(reason || "unknown");
        counts.set(key, (counts.get(key) || 0) + 1);
      });
    });
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }

  function buildRecommendationRows(scenarioKey, rows) {
    if (!Array.isArray(rows) || rows.length === 0) {
      return [];
    }

    if (scenarioKey === "nba") {
      return rows
        .map((row) => ({
          col1: String(row.action_id || "unknown"),
          col2: String(row.action_channel || "unknown"),
          col3: toNumber(row.expected_uplift) !== null ? `+${formatPercent(row.expected_uplift, 1)}` : "n/a",
        }))
        .slice(0, 5);
    }

    if (scenarioKey === "churn") {
      return rows
        .map((row) => ({
          col1: String(row.recommended_action || "unknown"),
          col2: `${String(row.risk_band || "unknown")} risk`,
          col3: toNumber(row.expected_uplift) !== null ? `+${formatPercent(row.expected_uplift, 1)}` : "n/a",
        }))
        .slice(0, 5);
    }

    if (scenarioKey === "mmm") {
      return rows
        .map((row) => ({
          col1: String(row.channel || "unknown"),
          col2: formatCurrency(row.recommended_spend),
          col3: formatCurrency(row.expected_incremental_revenue),
        }))
        .slice(0, 5);
    }

    return rows
      .map((row) => ({
        col1: String(row.campaign_id || "unknown"),
        col2: String(row.decision_recommendation || "unknown"),
        col3: toNumber(row.incremental_lift) !== null ? `+${formatPercent(row.incremental_lift, 1)}` : "n/a",
      }))
      .slice(0, 5);
  }

  function stagePassRate(data) {
    const passCount = toNumber(data && data.latestRun && data.latestRun.stage_pass_count);
    const total = toNumber(data && data.latestRun && data.latestRun.stage_total);
    if (passCount === null || total === null || total <= 0) {
      return null;
    }
    return passCount / total;
  }

  function resolveUseCaseFromViewModel(viewModel, useCaseId) {
    if (!viewModel || typeof viewModel !== "object") {
      return null;
    }
    const useCases = Array.isArray(viewModel.use_cases) ? viewModel.use_cases : [];
    return useCases.find((row) => row && row.use_case_id === useCaseId) || null;
  }

  function flattenContractList(value) {
    if (!Array.isArray(value)) {
      return [];
    }
    return value.map((row) => String(row)).filter((row) => row.trim() !== "");
  }

  function getStageRows(data) {
    return data && data.stages && Array.isArray(data.stages.stages) ? data.stages.stages : [];
  }

  function getLayerLabel(layerId) {
    const key = String(layerId || "").trim();
    return LAYER_LABELS[key] || key || "Unknown Layer";
  }

  function inferLayerIdFromArtifactLabel(label) {
    const token = String(label || "").toLowerCase();
    if (token.includes("topic") || token.includes("ingestion_event_bus")) {
      return "ingestion_event_bus";
    }
    if (token.includes("raw_events") || token.includes("curated_records")) {
      return "raw_curated_storage";
    }
    if (token.includes("identity") || token.includes("resolved_records")) {
      return "identity_customer_360";
    }
    if (token.includes("feature_rows")) {
      return "feature_layer";
    }
    if (token.includes("model_")) {
      return "model_layer";
    }
    if (token.includes("activation")) {
      return "serving_activation";
    }
    if (token.includes("monitoring") || token.includes("telemetry")) {
      return "monitoring_governance";
    }
    return "unknown";
  }

  function buildArtifactRows({ summary, stages }) {
    const artifactRows = [];
    const seen = new Set();
    const stageRows = Array.isArray(stages && stages.stages) ? stages.stages : [];

    const stagePathMap = new Map();
    stageRows.forEach((stage) => {
      const layerId = String(stage.layer_id || "unknown");
      const stageLabel = String(stage.label || getLayerLabel(layerId));
      const outputs = Array.isArray(stage.outputs) ? stage.outputs : [];
      outputs.forEach((output) => {
        const path = output && typeof output.path === "string" ? output.path : "";
        if (!path) {
          return;
        }
        stagePathMap.set(path, {
          layerId,
          layerLabel: stageLabel,
          exists: Object.prototype.hasOwnProperty.call(output, "exists") ? Boolean(output.exists) : null,
          label: String(output.name || "artifact"),
        });
      });
    });

    const artifacts = summary && typeof summary.artifacts === "object" ? summary.artifacts : {};

    function pushRow({ label, path, exists = null, layerId = "unknown", layerLabel = "unknown" }) {
      const safePath = typeof path === "string" ? path : "";
      if (!safePath) {
        return;
      }
      const key = `${label}::${safePath}`;
      if (seen.has(key)) {
        return;
      }
      seen.add(key);
      const stageHint = stagePathMap.get(safePath);
      const resolvedLayerId = stageHint ? stageHint.layerId : layerId;
      const resolvedLayerLabel = stageHint ? stageHint.layerLabel : layerLabel || getLayerLabel(resolvedLayerId);
      const resolvedExists = stageHint && stageHint.exists !== null ? stageHint.exists : exists;
      artifactRows.push({
        label,
        path: safePath,
        exists: resolvedExists,
        layer_id: resolvedLayerId,
        layer_label: resolvedLayerLabel,
        download_url: `/api/artifacts/download?path=${encodeURIComponent(safePath)}`,
      });
    }

    Object.entries(artifacts).forEach(([key, value]) => {
      if (key === "ingestion_event_bus" && value && typeof value === "object") {
        Object.entries(value).forEach(([topic, topicPath]) => {
          if (typeof topicPath === "string") {
            pushRow({
              label: `topic:${topic}`,
              path: topicPath,
              layerId: "ingestion_event_bus",
              layerLabel: getLayerLabel("ingestion_event_bus"),
            });
          }
        });
        return;
      }

      if (typeof value === "string") {
        const guessedLayerId = inferLayerIdFromArtifactLabel(key);
        pushRow({
          label: key,
          path: value,
          layerId: guessedLayerId,
          layerLabel: getLayerLabel(guessedLayerId),
        });
      }
    });

    stagePathMap.forEach((row, path) => {
      pushRow({
        label: row.label,
        path,
        exists: row.exists,
        layerId: row.layerId,
        layerLabel: row.layerLabel,
      });
    });

    artifactRows.sort((a, b) => {
      if (a.layer_label !== b.layer_label) {
        return a.layer_label.localeCompare(b.layer_label);
      }
      if (a.label !== b.label) {
        return a.label.localeCompare(b.label);
      }
      return a.path.localeCompare(b.path);
    });

    return artifactRows;
  }

  function applyArtifactFilters(rows) {
    const sourceRows = Array.isArray(rows) ? rows : [];
    const stage = String(state.artifactFilters.stage || "all");
    const exists = String(state.artifactFilters.exists || "all");
    const query = String(state.artifactFilters.query || "").trim().toLowerCase();

    return sourceRows.filter((row) => {
      if (stage !== "all" && String(row.layer_id) !== stage) {
        return false;
      }
      if (exists === "present" && row.exists !== true) {
        return false;
      }
      if (exists === "missing" && row.exists !== false) {
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

  function predictionColumnsForScenario(scenarioKey) {
    if (scenarioKey === "nba") {
      return [
        { key: "customer_id", label: "Customer" },
        { key: "action_id", label: "Action" },
        { key: "action_channel", label: "Channel" },
        { key: "expected_uplift", label: "Uplift", formatter: (v) => formatPercent(v, 1) },
        { key: "confidence", label: "Confidence", formatter: (v) => formatPercent(v, 1) },
      ];
    }
    if (scenarioKey === "churn") {
      return [
        { key: "customer_id", label: "Customer" },
        { key: "churn_risk_score", label: "Risk", formatter: (v) => formatPercent(v, 1) },
        { key: "risk_band", label: "Band" },
        { key: "recommended_action", label: "Action" },
        { key: "expected_uplift", label: "Uplift", formatter: (v) => formatPercent(v, 1) },
      ];
    }
    if (scenarioKey === "mmm") {
      return [
        { key: "period", label: "Period" },
        { key: "channel", label: "Channel" },
        { key: "recommended_spend", label: "Recommended Spend", formatter: (v) => formatCurrency(v) },
        { key: "expected_incremental_revenue", label: "Incr Revenue", formatter: (v) => formatCurrency(v) },
      ];
    }
    return [
      { key: "campaign_id", label: "Campaign" },
      { key: "decision_recommendation", label: "Decision" },
      { key: "incremental_lift", label: "Lift", formatter: (v) => formatPercent(v, 1) },
      { key: "iROAS", label: "iROAS", formatter: (v) => formatValue(v) },
      { key: "p_value", label: "P-Value", formatter: (v) => formatValue(v) },
    ];
  }

  function activationColumnsForScenario(scenarioKey) {
    if (scenarioKey === "nba") {
      return [
        { key: "destination", label: "Destination" },
        { key: "customer_id", label: "Customer" },
        { key: "action_id", label: "Action" },
        { key: "action_channel", label: "Channel" },
        { key: "priority", label: "Priority" },
      ];
    }
    if (scenarioKey === "churn") {
      return [
        { key: "destination", label: "Destination" },
        { key: "customer_id", label: "Customer" },
        { key: "recommended_action", label: "Action" },
        { key: "risk_band", label: "Risk Band" },
        { key: "priority", label: "Priority" },
      ];
    }
    if (scenarioKey === "mmm") {
      return [
        { key: "destination", label: "Destination" },
        { key: "channel", label: "Channel" },
        { key: "recommended_spend", label: "Spend", formatter: (v) => formatCurrency(v) },
        { key: "expected_incremental_revenue", label: "Incr Revenue", formatter: (v) => formatCurrency(v) },
      ];
    }
    return [
      { key: "destination", label: "Destination" },
      { key: "campaign_id", label: "Campaign" },
      { key: "decision_recommendation", label: "Decision" },
      { key: "incremental_lift", label: "Lift", formatter: (v) => formatPercent(v, 1) },
      { key: "iROAS", label: "iROAS", formatter: (v) => formatValue(v) },
    ];
  }

  function renderRowValue(row, column) {
    if (!column || typeof column !== "object") {
      return "n/a";
    }
    const rawValue = row && Object.prototype.hasOwnProperty.call(row, column.key) ? row[column.key] : null;
    if (typeof column.formatter === "function") {
      return column.formatter(rawValue);
    }
    return formatValue(rawValue);
  }

  function renderPreviewTable({ title, subtitle, rows, columns, emptyText }) {
    const safeRows = Array.isArray(rows) ? rows.slice(0, 6) : [];
    const safeColumns = Array.isArray(columns) ? columns : [];
    const header = safeColumns.map((column) => `<th>${escapeHtml(column.label || column.key)}</th>`).join("");

    const body = safeRows
      .map((row) => {
        const cells = safeColumns
          .map((column) => `<td>${escapeHtml(renderRowValue(row, column))}</td>`)
          .join("");
        return `<tr>${cells}</tr>`;
      })
      .join("");

    return `
      <h4 class="wb-section-title">${escapeHtml(title)}</h4>
      <p class="wb-section-sub">${escapeHtml(subtitle)}</p>
      <table class="wb-data-table">
        <thead><tr>${header}</tr></thead>
        <tbody>${body || `<tr><td colspan="${Math.max(1, safeColumns.length)}">${escapeHtml(emptyText)}</td></tr>`}</tbody>
      </table>
    `;
  }

  function renderContractChips(title, values, maxItems = 12) {
    const rows = Array.isArray(values) ? values : [];
    const shown = rows.slice(0, maxItems);
    const moreCount = rows.length > shown.length ? rows.length - shown.length : 0;
    const pills = shown.map((item) => `<span class="wb-chip-inline">${escapeHtml(String(item))}</span>`).join("");
    return `
      <div class="wb-tech-card">
        <h5>${escapeHtml(title)}</h5>
        <div class="wb-chip-inline-wrap">
          ${pills || '<span class="wb-chip-inline">none</span>'}
          ${moreCount > 0 ? `<span class="wb-chip-inline">+${moreCount} more</span>` : ""}
        </div>
      </div>
    `;
  }

  function renderComponentMatrix(data, stepIndex) {
    const layerIds = TECH_STAGE_GROUPS[stepIndex] || [];
    const platformRows = Array.isArray(data.platformFlow) ? data.platformFlow : [];
    const selected = platformRows.filter((row) => layerIds.includes(String(row.layer_id || "")));

    if (!selected.length) {
      return `<p class="wb-section-sub">No component matrix available for this step.</p>`;
    }

    return `
      <div class="wb-tech-grid two">
        ${selected
          .map((row) => {
            const current = Array.isArray(row.components && row.components.current)
              ? row.components.current
              : [];
            const ossProfile = Array.isArray(row.components && row.components.oss_profile)
              ? row.components.oss_profile
              : [];
            const swaps = Array.isArray(row.components && row.components.scalable_swap_ins)
              ? row.components.scalable_swap_ins
              : [];

            return `
              <article class="wb-tech-card">
                <h5>${escapeHtml(String(row.label || getLayerLabel(row.layer_id)))}</h5>
                <p class="wb-tiny wb-muted">${escapeHtml(String(row.technical_summary || ""))}</p>
                <div class="wb-chip-inline-wrap">
                  ${current.map((item) => `<span class="wb-chip-inline">Current: ${escapeHtml(String(item))}</span>`).join("")}
                </div>
                <div class="wb-chip-inline-wrap">
                  ${ossProfile.map((item) => `<span class="wb-chip-inline">Integrated: ${escapeHtml(String(item))}</span>`).join("")}
                </div>
                <div class="wb-chip-inline-wrap">
                  ${swaps.slice(0, 5).map((item) => `<span class="wb-chip-inline">Swap: ${escapeHtml(String(item))}</span>`).join("")}
                </div>
              </article>
            `;
          })
          .join("")}
      </div>
    `;
  }

  function renderIoList(rows, kind) {
    const safeRows = Array.isArray(rows) ? rows : [];
    if (!safeRows.length) {
      return `<ul class="wb-io-list"><li>No ${escapeHtml(kind)} captured.</li></ul>`;
    }

    const displayRows = safeRows.slice(0, 8);
    const rowHtml = displayRows
      .map((row) => {
        const name = String(row.name || "item");
        const hasPath = typeof row.path === "string" && row.path.trim() !== "";
        const hasValue = Object.prototype.hasOwnProperty.call(row, "value");
        const hasCount = Object.prototype.hasOwnProperty.call(row, "row_count");
        const valueText = hasValue ? formatValue(row.value) : hasCount ? formatValue(row.row_count) : "";
        const existsBadge = Object.prototype.hasOwnProperty.call(row, "exists")
          ? `<span class="wb-status-pill ${statusClass(row.exists ? "pass" : "fail")}">${row.exists ? "exists" : "missing"}</span>`
          : "";
        const pathText = hasPath
          ? `<div class="wb-io-sub wb-mono">${escapeHtml(String(row.path))}</div>
             <div class="wb-io-sub"><a class="wb-link" href="/api/artifacts/download?path=${encodeURIComponent(String(row.path))}">Download</a></div>`
          : "";

        return `
          <li>
            <div class="wb-io-title">${escapeHtml(name)} ${existsBadge}</div>
            ${valueText ? `<div class="wb-io-sub">Value: ${escapeHtml(valueText)}</div>` : ""}
            ${pathText}
          </li>
        `;
      })
      .join("");

    const moreCount = safeRows.length > displayRows.length ? safeRows.length - displayRows.length : 0;

    return `
      <ul class="wb-io-list">
        ${rowHtml}
        ${moreCount > 0 ? `<li class="wb-muted">+${moreCount} additional ${escapeHtml(kind)} omitted in compact view.</li>` : ""}
      </ul>
    `;
  }

  function renderTechnicalStageCards(data, stepIndex) {
    const stageRows = getStageRows(data).filter((row) =>
      (TECH_STAGE_GROUPS[stepIndex] || []).includes(String(row.layer_id || ""))
    );

    if (!stageRows.length) {
      return '<p class="wb-section-sub">No stage detail payload available for this step.</p>';
    }

    return `
      <div class="wb-tech-grid">
        ${stageRows
          .map((row) => {
            const status = String(row.status || "unknown");
            const inputs = Array.isArray(row.inputs) ? row.inputs : [];
            const outputs = Array.isArray(row.outputs) ? row.outputs : [];
            return `
              <article class="wb-stage-card">
                <div class="wb-stage-head">
                  <h5>${escapeHtml(String(row.label || row.layer_id || "stage"))}</h5>
                  <span class="wb-status-pill ${statusClass(status)}">${escapeHtml(status)}</span>
                </div>
                <p class="wb-tiny wb-muted">${escapeHtml(String(row.detail || "No stage detail provided."))}</p>
                <div class="wb-io-grid">
                  <section class="wb-io-box">
                    <h6>Inputs (${inputs.length})</h6>
                    ${renderIoList(inputs, "inputs")}
                  </section>
                  <section class="wb-io-box">
                    <h6>Outputs (${outputs.length})</h6>
                    ${renderIoList(outputs, "outputs")}
                  </section>
                </div>
              </article>
            `;
          })
          .join("")}
      </div>
    `;
  }

  function renderTelemetryTable(data, stepIndex) {
    const stageIds = new Set(TECH_STAGE_GROUPS[stepIndex] || []);
    const rows = Array.isArray(data.summary && data.summary.telemetry && data.summary.telemetry.stages)
      ? data.summary.telemetry.stages.filter((row) => stageIds.has(String(row.layer_id || "")))
      : [];

    if (!rows.length) {
      return "";
    }

    const totalMs = rows.reduce((sum, row) => sum + (toNumber(row.duration_ms) || 0), 0);
    const body = rows
      .map(
        (row) => `
          <tr>
            <td>${escapeHtml(getLayerLabel(row.layer_id))}</td>
            <td>${escapeHtml(formatDurationMs(row.duration_ms))}</td>
            <td>${escapeHtml(String(row.detail || ""))}</td>
          </tr>
        `
      )
      .join("");

    return `
      <h4 class="wb-section-title">Telemetry (Step Runtime)</h4>
      <p class="wb-section-sub">Per-stage execution runtime from latest run telemetry. Group total: <strong>${escapeHtml(formatDurationMs(totalMs))}</strong>.</p>
      <table class="wb-data-table">
        <thead><tr><th>Stage</th><th>Duration</th><th>Detail</th></tr></thead>
        <tbody>${body}</tbody>
      </table>
    `;
  }

  function renderApiTrace(endpoints) {
    const rows = Array.isArray(endpoints) ? endpoints : [];
    const body = rows.map((row) => `<span class="wb-chip-inline wb-mono">${escapeHtml(row)}</span>`).join("");
    return `
      <h4 class="wb-section-title">Evidence API Trace</h4>
      <p class="wb-section-sub">Runtime services used to hydrate this model evidence view.</p>
      <div class="wb-chip-inline-wrap">
        ${body || '<span class="wb-chip-inline">No API trace.</span>'}
      </div>
    `;
  }

  function renderBusinessInputStep(data) {
    const records = data.summary && typeof data.summary.records === "object" ? data.summary.records : {};
    const sourceTables = records && typeof records.source_tables === "object" ? records.source_tables : {};
    const reasonCounts = aggregateReasonCodes(data.predictionRows || []);

    const insightRows = [];
    if (reasonCounts.length > 0) {
      const [topReason, topCount] = reasonCounts[0];
      insightRows.push(`Top observed reason: ${topReason} (${topCount} rows).`);
    }
    if (toNumber(records.feature_rows) !== null) {
      insightRows.push(`${formatCompact(records.feature_rows)} feature rows prepared for scoring.`);
    }
    if (toNumber(records.model_rows) !== null) {
      insightRows.push(`${formatCompact(records.model_rows)} rows entered model stage in latest run.`);
    }

    const insights = (insightRows.length ? insightRows : ["Live row-level signals will appear after scenario runs complete."])
      .map((text) => `<li>${escapeHtml(text)}</li>`)
      .join("");

    return `
      <h4 class="wb-section-title">Model Input Readiness</h4>
      <p class="wb-section-sub">Confirm whether governed source volume, features, and scorable rows are ready before reviewing recommendations.</p>

      <div class="wb-kpi-grid">
        <article class="wb-kpi">
          <p class="wb-kpi-label">Source Tables</p>
          <p class="wb-kpi-value">${escapeHtml(String(Object.keys(sourceTables).length || 0))}</p>
          <p class="wb-kpi-sub">Contract inputs available</p>
        </article>
        <article class="wb-kpi">
          <p class="wb-kpi-label">Feature Rows</p>
          <p class="wb-kpi-value">${escapeHtml(formatCompact(records.feature_rows))}</p>
          <p class="wb-kpi-sub">Prepared for model stage</p>
        </article>
        <article class="wb-kpi">
          <p class="wb-kpi-label">Model Rows</p>
          <p class="wb-kpi-value">${escapeHtml(formatCompact(records.model_rows))}</p>
          <p class="wb-kpi-sub">Scorable population</p>
        </article>
      </div>

      <ul class="wb-list">${insights}</ul>
    `;
  }

  function renderBusinessRecommendationStep(data) {
    const rows = buildRecommendationRows(state.scenarioKey, data.predictionRows || []);

    const tableRows = rows
      .map(
        (row, index) =>
          `<tr><td>${index + 1}</td><td>${escapeHtml(row.col1)}</td><td>${escapeHtml(row.col2)}</td><td>${escapeHtml(row.col3)}</td></tr>`
      )
      .join("");

    return `
      <h4 class="wb-section-title">Model Recommendation</h4>
      <p class="wb-section-sub">Review the model-ranked actions that best match value, risk, policy constraints, and activation readiness.</p>
      <table class="wb-data-table">
        <thead><tr><th>Rank</th><th>Recommendation</th><th>Context</th><th>Expected Value</th></tr></thead>
        <tbody>${tableRows || '<tr><td colspan="4">No recommendation rows available yet.</td></tr>'}</tbody>
      </table>
    `;
  }

  function renderBusinessImpactStep(data) {
    const metrics = data.summary && typeof data.summary.model_metrics === "object" ? data.summary.model_metrics : {};
    const latest = data.latestRun || {};
    const passRate = stagePassRate(data);
    const kpiName = String(metrics.primary_kpi || "primary_kpi");
    const kpiValue = metrics[kpiName];

    const splitValidation = metrics.split_validation && typeof metrics.split_validation === "object"
      ? metrics.split_validation
      : null;
    const splitStatus = splitValidation && splitValidation.status ? String(splitValidation.status) : "not_available";

    return `
      <h4 class="wb-section-title">Impact Forecast + Model Readiness</h4>
      <p class="wb-section-sub">Validate forecasted outcomes, stage reliability, and model checks before approving the decision path.</p>

      <div class="wb-kpi-grid">
        <article class="wb-kpi">
          <p class="wb-kpi-label">Primary KPI</p>
          <p class="wb-kpi-value">${escapeHtml(formatValue(kpiValue))}</p>
          <p class="wb-kpi-sub">${escapeHtml(kpiName)}</p>
        </article>
        <article class="wb-kpi">
          <p class="wb-kpi-label">Run Status</p>
          <p class="wb-kpi-value">${escapeHtml(String(latest.run_status || "unknown"))}</p>
          <p class="wb-kpi-sub">Latest execution state</p>
        </article>
        <article class="wb-kpi">
          <p class="wb-kpi-label">Stage Pass</p>
          <p class="wb-kpi-value">${escapeHtml(passRate !== null ? formatPercent(passRate, 0) : "n/a")}</p>
          <p class="wb-kpi-sub">${escapeHtml(formatValue(latest.stage_pass_count))}/${escapeHtml(formatValue(latest.stage_total))} stages</p>
        </article>
      </div>

      <ul class="wb-list">
        <li><span class="wb-tag">Split Validation</span> <span class="wb-status-pill ${statusClass(splitStatus)}">${escapeHtml(splitStatus)}</span></li>
        <li><span class="wb-tag">Run ID</span> ${escapeHtml(String(latest.run_id || "n/a"))}</li>
        <li><span class="wb-tag">Infra</span> ${escapeHtml(String(latest.infra_profile || data.summary.infra_profile || "local"))}</li>
      </ul>
    `;
  }

  function renderBusinessResultsStep(data) {
    const summary = data.summary || {};
    const metrics = summary.model_metrics && typeof summary.model_metrics === "object" ? summary.model_metrics : {};
    const latest = data.latestRun || {};
    const expectedUplift = metrics.avg_expected_uplift ?? metrics.expected_uplift;
    const confidence = metrics.avg_confidence ?? metrics.confidence;
    const activationCount = Array.isArray(data.activationRows) ? data.activationRows.length : 0;
    const predictionCount = Array.isArray(data.predictionRows) ? data.predictionRows.length : 0;

    const activationPreview = renderPreviewTable({
      title: "Activation-Ready Output",
      subtitle: "Sample rows that can be handed to the downstream campaign or decisioning workflow.",
      rows: data.activationRows,
      columns: activationColumnsForScenario(state.scenarioKey),
      emptyText: "No activation payload rows available.",
    });

    return `
      <h4 class="wb-section-title">Decision Evidence</h4>
      <p class="wb-section-sub">Close the model workflow with lift, confidence, and activation-ready evidence from the latest run.</p>

      <div class="wb-kpi-grid">
        <article class="wb-kpi">
          <p class="wb-kpi-label">Expected Uplift</p>
          <p class="wb-kpi-value">${escapeHtml(formatSignedPercent(expectedUplift, 1))}</p>
          <p class="wb-kpi-sub">Average predicted business lift</p>
        </article>
        <article class="wb-kpi">
          <p class="wb-kpi-label">Decision Confidence</p>
          <p class="wb-kpi-value">${escapeHtml(formatPercent(confidence, 0))}</p>
          <p class="wb-kpi-sub">Average model confidence</p>
        </article>
        <article class="wb-kpi">
          <p class="wb-kpi-label">Activation Records</p>
          <p class="wb-kpi-value">${escapeHtml(formatCompact(activationCount || predictionCount))}</p>
          <p class="wb-kpi-sub">Rows ready for downstream use</p>
        </article>
      </div>

      <ul class="wb-list">
        <li><span class="wb-tag">Run Status</span> <span class="wb-status-pill ${statusClass(latest.run_status)}">${escapeHtml(String(latest.run_status || "unknown"))}</span></li>
        <li><span class="wb-tag">Run ID</span> ${escapeHtml(String(latest.run_id || "n/a"))}</li>
        <li><span class="wb-tag">Decision Guidance</span> Use the result when model evidence and governance checks are acceptable for the operating team.</li>
      </ul>

      <hr class="wb-divider" />
      ${activationPreview}
    `;
  }

  function renderTechnicalInputStep(data) {
    const summary = data.summary || {};
    const records = summary.records && typeof summary.records === "object" ? summary.records : {};
    const contract = data.contract && typeof data.contract === "object" ? data.contract : {};
    const entities = flattenContractList(contract.entities);
    const features = flattenContractList(contract.features);
    const outputFields = flattenContractList(contract.output_fields);
    const sourceTables = records.source_tables && typeof records.source_tables === "object" ? records.source_tables : {};

    const policy = contract.decision_policy && typeof contract.decision_policy === "object"
      ? contract.decision_policy
      : {};

    const policyEligibility = Array.isArray(policy.eligibility_rules) ? policy.eligibility_rules : [];
    const policySuppression = Array.isArray(policy.suppression_rules) ? policy.suppression_rules : [];

    const sourceTableRows = Object.entries(sourceTables)
      .map(([name, value]) => `<tr><td>${escapeHtml(name)}</td><td>${escapeHtml(formatCompact(value))}</td></tr>`)
      .join("");

    return `
      <h4 class="wb-section-title">Data Contract + Stage Inputs</h4>
      <p class="wb-section-sub">Inspect the product contract, source readiness, and component stack before model execution.</p>

      <div class="wb-kpi-grid">
        <article class="wb-kpi">
          <p class="wb-kpi-label">Entities</p>
          <p class="wb-kpi-value">${escapeHtml(String(entities.length || 0))}</p>
          <p class="wb-kpi-sub">Business entities in contract</p>
        </article>
        <article class="wb-kpi">
          <p class="wb-kpi-label">Features</p>
          <p class="wb-kpi-value">${escapeHtml(String(features.length || 0))}</p>
          <p class="wb-kpi-sub">Model input columns</p>
        </article>
        <article class="wb-kpi">
          <p class="wb-kpi-label">Output Fields</p>
          <p class="wb-kpi-value">${escapeHtml(String(outputFields.length || 0))}</p>
          <p class="wb-kpi-sub">Activation payload schema</p>
        </article>
      </div>

      <div class="wb-tech-grid two">
        <article class="wb-tech-card">
          <h5>Contract Controls</h5>
          <dl class="wb-kv">
            <dt>AI/ML Use Case</dt><dd class="wb-mono">${escapeHtml(String(summary.use_case_id || "n/a"))}</dd>
            <dt>Scenario Preset</dt><dd class="wb-mono">${escapeHtml(String(summary.scenario_id || "none"))}</dd>
            <dt>Runtime Mode</dt><dd>${escapeHtml(String(summary.runtime_mode || "default"))}</dd>
            <dt>Source Mode</dt><dd>${escapeHtml(String((summary.source_data && summary.source_data.mode) || "unknown"))}</dd>
            <dt>SLA (ms)</dt><dd>${escapeHtml(formatValue(contract.sla_latency_ms))}</dd>
            <dt>Refresh</dt><dd>${escapeHtml(String(contract.refresh || "n/a"))}</dd>
            <dt>Baseline</dt><dd>${escapeHtml(formatValue(contract.baseline))}</dd>
            <dt>Target</dt><dd>${escapeHtml(formatValue(contract.target))}</dd>
            <dt>Seed</dt><dd>${escapeHtml(formatValue(summary.seed))}</dd>
          </dl>
        </article>

        <article class="wb-tech-card">
          <h5>Policy Rules</h5>
          <p class="wb-tiny wb-muted">Eligibility + suppression rules from the use-case decision policy.</p>
          <ul class="wb-list">
            <li><strong>Eligibility:</strong> ${escapeHtml(policyEligibility.length ? policyEligibility.join(" | ") : "n/a")}</li>
            <li><strong>Suppression:</strong> ${escapeHtml(policySuppression.length ? policySuppression.join(" | ") : "n/a")}</li>
            <li><strong>Fallback:</strong> ${escapeHtml(String(policy.fallback || "n/a"))}</li>
          </ul>
        </article>
      </div>

      <div class="wb-tech-grid two">
        ${renderContractChips("Entities", entities, 10)}
        ${renderContractChips("Feature Columns", features, 10)}
      </div>

      <h4 class="wb-section-title">Source Table Volumes</h4>
      <p class="wb-section-sub">Raw source coverage that feeds ingestion and curated stages.</p>
      <table class="wb-data-table">
        <thead><tr><th>Source Table</th><th>Rows</th></tr></thead>
        <tbody>${sourceTableRows || '<tr><td colspan="2">No source table counts present.</td></tr>'}</tbody>
      </table>

      <hr class="wb-divider" />
      <h4 class="wb-section-title">Architecture Components (Input Group)</h4>
      ${renderComponentMatrix(data, 0)}

      <hr class="wb-divider" />
      <h4 class="wb-section-title">Stage Evidence (Input Group)</h4>
      ${renderTechnicalStageCards(data, 0)}

      <hr class="wb-divider" />
      ${renderTelemetryTable(data, 0)}

      <hr class="wb-divider" />
      ${renderApiTrace([
        "/api/run-history",
        "/api/runs/<use_case_id>/<run_id>",
        "/api/runs/<use_case_id>/<run_id>/stages",
        "/api/view-model",
      ])}
    `;
  }

  function renderSplitValidation(metrics) {
    const splitValidation = metrics && typeof metrics.split_validation === "object" ? metrics.split_validation : null;
    if (!splitValidation) {
      return `
        <h4 class="wb-section-title">Split Validation</h4>
        <p class="wb-section-sub">No split validation payload available for this run.</p>
      `;
    }

    const checks = Array.isArray(splitValidation.checks) ? splitValidation.checks : [];
    const rows = checks
      .map(
        (check) => `
          <tr>
            <td>${escapeHtml(String(check.name || "check"))}</td>
            <td><span class="wb-status-pill ${statusClass(check.status)}">${escapeHtml(String(check.status || "unknown"))}</span></td>
            <td>${escapeHtml(formatValue(check.actual))}</td>
            <td>${escapeHtml(String(check.expectation || ""))}</td>
          </tr>
        `
      )
      .join("");

    const summary = splitValidation.summary && typeof splitValidation.summary === "object" ? splitValidation.summary : {};

    return `
      <h4 class="wb-section-title">Split Validation</h4>
      <p class="wb-section-sub">
        Status: <span class="wb-status-pill ${statusClass(splitValidation.status)}">${escapeHtml(String(splitValidation.status || "unknown"))}</span>
        | Checks: ${escapeHtml(formatValue(summary.passed_checks))}/${escapeHtml(formatValue(summary.total_checks))} passed.
      </p>
      <table class="wb-data-table">
        <thead><tr><th>Check</th><th>Status</th><th>Actual</th><th>Expectation</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="4">No split checks present.</td></tr>'}</tbody>
      </table>
    `;
  }

  function renderModelArtifactTable(artifacts) {
    const keys = [
      "model_predictions",
      "model_metrics",
      "model_manifest",
      "model_training_report",
      "model_binary",
      "activation_payloads",
    ];

    const rows = keys
      .map((key) => {
        const value = artifacts && typeof artifacts[key] === "string" ? artifacts[key] : "";
        if (!value) {
          return `<tr><td>${escapeHtml(key)}</td><td>missing</td><td>n/a</td></tr>`;
        }
        return `
          <tr>
            <td>${escapeHtml(key)}</td>
            <td><span class="wb-status-pill ${statusClass("pass")}">present</span></td>
            <td>
              <a class="wb-link" href="/api/artifacts/download?path=${encodeURIComponent(value)}">Download</a>
              <div class="wb-tiny wb-mono">${escapeHtml(value)}</div>
            </td>
          </tr>
        `;
      })
      .join("");

    return `
      <h4 class="wb-section-title">Model + Activation Artifacts</h4>
      <p class="wb-section-sub">Evidence pointers for model lineage and activation output.</p>
      <table class="wb-data-table">
        <thead><tr><th>Artifact</th><th>Status</th><th>Link</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  }

  function renderTechnicalModelStep(data) {
    const summary = data.summary || {};
    const metrics = summary.model_metrics && typeof summary.model_metrics === "object" ? summary.model_metrics : {};
    const backend = String(metrics.model_backend || "n/a");
    const modelVersion = String(metrics.model_version || "n/a");
    const trainRows = metrics.train_row_count ?? metrics.train_rows;
    const holdoutRows = metrics.holdout_row_count ?? metrics.holdout_rows;

    const primitiveMetricRows = Object.entries(metrics)
      .filter(([, value]) => value === null || ["string", "number", "boolean"].includes(typeof value))
      .slice(0, 14)
      .map(([key, value]) => `<tr><td>${escapeHtml(key)}</td><td>${escapeHtml(formatValue(value))}</td></tr>`)
      .join("");

    const predictionPreview = renderPreviewTable({
      title: "Prediction Sample",
      subtitle: "First rows from model prediction artifact to verify output contract fields.",
      rows: data.predictionRows,
      columns: predictionColumnsForScenario(state.scenarioKey),
      emptyText: "No prediction rows available.",
    });

    const activationPreview = renderPreviewTable({
      title: "Activation Payload Sample",
      subtitle: "First rows from activation payloads to confirm downstream-ready schema.",
      rows: data.activationRows,
      columns: activationColumnsForScenario(state.scenarioKey),
      emptyText: "No activation payload rows available.",
    });

    return `
      <h4 class="wb-section-title">Model + Activation Detail</h4>
      <p class="wb-section-sub">Inspect model backend, training split reliability, and activation-ready records.</p>

      <div class="wb-kpi-grid">
        <article class="wb-kpi">
          <p class="wb-kpi-label">Model Backend</p>
          <p class="wb-kpi-value">${escapeHtml(backend)}</p>
          <p class="wb-kpi-sub">Configured runtime backend</p>
        </article>
        <article class="wb-kpi">
          <p class="wb-kpi-label">Model Version</p>
          <p class="wb-kpi-value wb-mono">${escapeHtml(modelVersion)}</p>
          <p class="wb-kpi-sub">Versioned model lineage</p>
        </article>
        <article class="wb-kpi">
          <p class="wb-kpi-label">Train/Holdout</p>
          <p class="wb-kpi-value">${escapeHtml(formatValue(trainRows))}/${escapeHtml(formatValue(holdoutRows))}</p>
          <p class="wb-kpi-sub">Data split row counts</p>
        </article>
      </div>

      <h4 class="wb-section-title">Model Metrics (Primitive)</h4>
      <p class="wb-section-sub">Compact metric table from latest summary payload.</p>
      <table class="wb-data-table">
        <thead><tr><th>Metric</th><th>Value</th></tr></thead>
        <tbody>${primitiveMetricRows || '<tr><td colspan="2">No primitive metrics found.</td></tr>'}</tbody>
      </table>

      <hr class="wb-divider" />
      ${renderSplitValidation(metrics)}

      <hr class="wb-divider" />
      ${predictionPreview}

      <hr class="wb-divider" />
      ${activationPreview}

      <hr class="wb-divider" />
      ${renderModelArtifactTable(summary.artifacts && typeof summary.artifacts === "object" ? summary.artifacts : {})}

      <hr class="wb-divider" />
      <h4 class="wb-section-title">Architecture Components (Model Group)</h4>
      ${renderComponentMatrix(data, 1)}

      <hr class="wb-divider" />
      <h4 class="wb-section-title">Stage Evidence (Model Group)</h4>
      ${renderTechnicalStageCards(data, 1)}

      <hr class="wb-divider" />
      ${renderTelemetryTable(data, 1)}

      <hr class="wb-divider" />
      ${renderApiTrace([
        "/api/artifacts/download?path=<model_predictions>",
        "/api/artifacts/download?path=<activation_payloads>",
        "/api/runs/<use_case_id>/<run_id>/stages",
      ])}
    `;
  }

  function renderValidationGateTable(monitoringReport) {
    const gates = monitoringReport && typeof monitoringReport.validation_gates === "object"
      ? monitoringReport.validation_gates
      : {};
    const rows = Object.entries(gates)
      .map(
        ([name, status]) =>
          `<tr><td>${escapeHtml(name)}</td><td><span class="wb-status-pill ${statusClass(status)}">${escapeHtml(String(status))}</span></td></tr>`
      )
      .join("");

    return `
      <h4 class="wb-section-title">Validation Gates</h4>
      <p class="wb-section-sub">Governance checks emitted by monitoring layer.</p>
      <table class="wb-data-table">
        <thead><tr><th>Gate</th><th>Status</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="2">No validation gates found.</td></tr>'}</tbody>
      </table>
    `;
  }

  function renderDataQualityIssues(data) {
    const dq = data.dataQuality || {};
    const blockers = Array.isArray(dq.blockers) ? dq.blockers : [];
    const warnings = Array.isArray(dq.warnings) ? dq.warnings : [];
    const rows = blockers
      .map((row) => ({ ...row, severity: "blocker" }))
      .concat(warnings.map((row) => ({ ...row, severity: "warning" })));

    const tableRows = rows
      .map(
        (row) => `
          <tr>
            <td>${escapeHtml(String(row.table || "n/a"))}</td>
            <td>${escapeHtml(String(row.name || "n/a"))}</td>
            <td><span class="wb-status-pill ${statusClass(row.severity === "warning" ? "warn" : "fail")}">${escapeHtml(String(row.severity))}</span></td>
            <td>${escapeHtml(formatValue(row.violation_count))}</td>
            <td>${escapeHtml(String(row.reason || ""))}</td>
          </tr>
        `
      )
      .join("");

    return `
      <h4 class="wb-section-title">Data Quality Issues</h4>
      <p class="wb-section-sub">Blockers and warnings from <code>/api/runs/&lt;use_case&gt;/&lt;run_id&gt;/data-quality</code>.</p>
      <table class="wb-data-table">
        <thead><tr><th>Table</th><th>Check</th><th>Severity</th><th>Violations</th><th>Reason</th></tr></thead>
        <tbody>${tableRows || '<tr><td colspan="5">No blocker or warning checks found.</td></tr>'}</tbody>
      </table>
    `;
  }

  function renderArtifactExplorer(rows) {
    const allRows = Array.isArray(rows) ? rows : [];
    const filtered = applyArtifactFilters(allRows);
    const stageOptions = [{ value: "all", label: "All Stages" }];
    const seen = new Set(["all"]);

    allRows.forEach((row) => {
      const value = String(row.layer_id || "").trim();
      if (!value || seen.has(value)) {
        return;
      }
      stageOptions.push({ value, label: String(row.layer_label || getLayerLabel(value)) });
      seen.add(value);
    });

    const body = filtered
      .map(
        (row) => `
          <tr>
            <td class="wb-tiny">${escapeHtml(String(row.label || "artifact"))}</td>
            <td>${escapeHtml(String(row.layer_label || row.layer_id || "n/a"))}</td>
            <td><span class="wb-status-pill ${statusClass(row.exists === true ? "pass" : row.exists === false ? "fail" : "unknown")}">${row.exists === true ? "present" : row.exists === false ? "missing" : "unknown"}</span></td>
            <td><a class="wb-link" href="${escapeHtml(String(row.download_url || "#"))}">Download</a></td>
            <td class="wb-tiny wb-mono">${escapeHtml(String(row.path || ""))}</td>
          </tr>
        `
      )
      .join("");

    return `
      <h4 class="wb-section-title">Artifact Evidence Explorer</h4>
      <p class="wb-section-sub">Filter by stage, existence, and path to inspect reproducible run evidence.</p>

      <div class="wb-output-filter">
        <label>
          Stage
          <select id="wb-artifact-filter-stage" aria-label="Artifact stage filter">
            ${stageOptions
              .map(
                (option) =>
                  `<option value="${escapeHtml(option.value)}"${
                    option.value === state.artifactFilters.stage ? " selected" : ""
                  }>${escapeHtml(option.label)}</option>`
              )
              .join("")}
          </select>
        </label>

        <label>
          Exists
          <select id="wb-artifact-filter-exists" aria-label="Artifact exists filter">
            <option value="all"${state.artifactFilters.exists === "all" ? " selected" : ""}>All</option>
            <option value="present"${state.artifactFilters.exists === "present" ? " selected" : ""}>Present</option>
            <option value="missing"${state.artifactFilters.exists === "missing" ? " selected" : ""}>Missing</option>
          </select>
        </label>

        <label>
          Search
          <input id="wb-artifact-filter-query" type="text" value="${escapeHtml(state.artifactFilters.query)}" placeholder="artifact name / path" />
        </label>

        <button id="wb-download-visible" class="wb-btn wb-btn-secondary" type="button">Download Visible Bundle</button>
      </div>

      <p class="wb-count-note">Showing ${escapeHtml(String(filtered.length))} of ${escapeHtml(String(allRows.length))} artifacts.</p>

      <table class="wb-data-table">
        <thead><tr><th>Artifact</th><th>Stage</th><th>Exists</th><th>Link</th><th>Path</th></tr></thead>
        <tbody>${body || '<tr><td colspan="5">No artifacts match current filters.</td></tr>'}</tbody>
      </table>
    `;
  }

  function downloadVisibleArtifactBundle(data) {
    const allRows = Array.isArray(data.artifactRows) ? data.artifactRows : [];
    const filtered = applyArtifactFilters(allRows);

    const payload = {
      generated_at_utc: new Date().toISOString(),
      use_case_id: data.summary && data.summary.use_case_id ? data.summary.use_case_id : null,
      run_id: data.latestRun && data.latestRun.run_id ? data.latestRun.run_id : null,
      filters: { ...state.artifactFilters },
      artifact_rows: filtered,
    };

    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const useCase = payload.use_case_id || "use_case";
    const runId = payload.run_id || "run";
    link.href = url;
    link.download = `workbench_artifacts_${useCase}_${runId}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function renderTechnicalGovernanceStep(data) {
    const summary = data.summary || {};
    const dq = data.dataQuality || {};
    const monitoringReport = data.monitoringReport && typeof data.monitoringReport === "object" ? data.monitoringReport : {};
    const modelRegistry = summary.model_registry && typeof summary.model_registry === "object" ? summary.model_registry : {};

    return `
      <h4 class="wb-section-title">Governance + Evidence</h4>
      <p class="wb-section-sub">Review readiness gates, data-quality outcomes, and artifact auditability before sign-off.</p>

      <div class="wb-kpi-grid">
        <article class="wb-kpi">
          <p class="wb-kpi-label">Data Quality Status</p>
          <p class="wb-kpi-value">${escapeHtml(String(dq.data_quality_status || "not_available"))}</p>
          <p class="wb-kpi-sub">Mode: ${escapeHtml(String(dq.data_quality_mode || "unknown"))}</p>
        </article>
        <article class="wb-kpi">
          <p class="wb-kpi-label">Blockers / Warnings</p>
          <p class="wb-kpi-value">${escapeHtml(formatValue(dq.blocker_count))}/${escapeHtml(formatValue(dq.warning_count))}</p>
          <p class="wb-kpi-sub">Must-fix vs review-only issues</p>
        </article>
        <article class="wb-kpi">
          <p class="wb-kpi-label">Registry Stage</p>
          <p class="wb-kpi-value">${escapeHtml(String(modelRegistry.stage || "candidate"))}</p>
          <p class="wb-kpi-sub">Model lifecycle state</p>
        </article>
      </div>

      <div class="wb-tech-grid two">
        <article class="wb-tech-card">
          <h5>Governance Meta</h5>
          <dl class="wb-kv">
            <dt>Run Status</dt><dd>${escapeHtml(String(summary.run_status || "unknown"))}</dd>
            <dt>Infra</dt><dd>${escapeHtml(String(summary.infra_profile || "local"))}</dd>
            <dt>Run ID</dt><dd class="wb-mono">${escapeHtml(String(summary.run_id || "n/a"))}</dd>
            <dt>Monitoring Report</dt><dd>${dq.monitoring_report_path ? `<a class="wb-link" href="/api/artifacts/download?path=${encodeURIComponent(String(dq.monitoring_report_path))}">download</a>` : "n/a"}</dd>
          </dl>
        </article>

        <article class="wb-tech-card">
          <h5>Issue Names</h5>
          <ul class="wb-list">
            <li><strong>Blockers:</strong> ${escapeHtml(Array.isArray(dq.blocker_names) && dq.blocker_names.length ? dq.blocker_names.join(" | ") : "none")}</li>
            <li><strong>Warnings:</strong> ${escapeHtml(Array.isArray(dq.warning_names) && dq.warning_names.length ? dq.warning_names.join(" | ") : "none")}</li>
            <li><strong>Data Quality Reason:</strong> ${escapeHtml(String(dq.data_quality_reason || "n/a"))}</li>
          </ul>
        </article>
      </div>

      <hr class="wb-divider" />
      ${renderValidationGateTable(monitoringReport)}

      <hr class="wb-divider" />
      ${renderDataQualityIssues(data)}

      <hr class="wb-divider" />
      ${renderArtifactExplorer(data.artifactRows)}

      <hr class="wb-divider" />
      <h4 class="wb-section-title">Architecture Components (Governance Group)</h4>
      ${renderComponentMatrix(data, 2)}

      <hr class="wb-divider" />
      <h4 class="wb-section-title">Stage Evidence (Governance Group)</h4>
      ${renderTechnicalStageCards(data, 2)}

      <hr class="wb-divider" />
      ${renderTelemetryTable(data, 2)}

      <hr class="wb-divider" />
      ${renderApiTrace([
        "/api/runs/<use_case_id>/<run_id>/data-quality",
        "/api/artifacts/download?path=<monitoring_report>",
        "/api/runs/<use_case_id>/<run_id>/stages",
      ])}
    `;
  }

  async function loadScenarioData({ force = false } = {}) {
    const scenario = SCENARIOS[state.scenarioKey];
    if (!scenario) {
      throw new Error("Unknown scenario.");
    }

    if (!force && state.cache.has(scenario.useCaseId)) {
      return state.cache.get(scenario.useCaseId);
    }

    const historyPayload = await fetchJson(
      `/api/run-history?use_case_id=${encodeURIComponent(scenario.useCaseId)}&limit=1&status=all&infra=all&baseline=latest`
    );
    const latestRun = Array.isArray(historyPayload && historyPayload.runs) ? historyPayload.runs[0] : null;
    if (!latestRun || !latestRun.run_id) {
      throw new Error(`No runs found for ${scenario.useCaseId}. Execute the scenario first.`);
    }

    const summary = await fetchJson(
      `/api/runs/${encodeURIComponent(scenario.useCaseId)}/${encodeURIComponent(latestRun.run_id)}`
    );

    const artifacts = summary && typeof summary.artifacts === "object" ? summary.artifacts : {};
    const predictionPath = typeof artifacts.model_predictions === "string" ? artifacts.model_predictions : "";
    const activationPath = typeof artifacts.activation_payloads === "string" ? artifacts.activation_payloads : "";
    const monitoringPath = typeof artifacts.monitoring_report === "string" ? artifacts.monitoring_report : "";
    const manifestPath = typeof artifacts.model_manifest === "string" ? artifacts.model_manifest : "";

    const settled = await Promise.allSettled([
      fetchJson(`/api/runs/${encodeURIComponent(scenario.useCaseId)}/${encodeURIComponent(latestRun.run_id)}/stages`),
      fetchJson(`/api/runs/${encodeURIComponent(scenario.useCaseId)}/${encodeURIComponent(latestRun.run_id)}/data-quality`),
      predictionPath ? fetchJson(`/api/artifacts/download?path=${encodeURIComponent(predictionPath)}`) : Promise.resolve([]),
      activationPath ? fetchJson(`/api/artifacts/download?path=${encodeURIComponent(activationPath)}`) : Promise.resolve([]),
      monitoringPath ? fetchJson(`/api/artifacts/download?path=${encodeURIComponent(monitoringPath)}`) : Promise.resolve({}),
      manifestPath ? fetchJson(`/api/artifacts/download?path=${encodeURIComponent(manifestPath)}`) : Promise.resolve({}),
      fetchJson("/api/view-model"),
      fetchJson("/api/contracts/inference"),
    ]);

    const stages = settled[0].status === "fulfilled" ? settled[0].value : null;
    const dataQuality = settled[1].status === "fulfilled" ? settled[1].value : null;
    const predictionRows = settled[2].status === "fulfilled" ? extractRows(settled[2].value) : [];
    const activationRows = settled[3].status === "fulfilled" ? extractRows(settled[3].value) : [];
    const monitoringReport = settled[4].status === "fulfilled" && settled[4].value && typeof settled[4].value === "object"
      ? settled[4].value
      : null;
    const modelManifest = settled[5].status === "fulfilled" && settled[5].value && typeof settled[5].value === "object"
      ? settled[5].value
      : null;
    const viewModel = settled[6].status === "fulfilled" && settled[6].value && typeof settled[6].value === "object"
      ? settled[6].value
      : null;
    const inferenceContracts = settled[7].status === "fulfilled" && settled[7].value && typeof settled[7].value === "object"
      ? settled[7].value
      : null;

    const useCaseViewModel = resolveUseCaseFromViewModel(viewModel, scenario.useCaseId);
    const contract = useCaseViewModel && typeof useCaseViewModel.contract === "object" ? useCaseViewModel.contract : null;

    const payload = {
      scenario,
      latestRun,
      summary,
      stages,
      dataQuality,
      predictionRows,
      activationRows,
      monitoringReport,
      modelManifest,
      viewModel,
      inferenceContracts,
      useCaseViewModel,
      contract,
      platformFlow: viewModel && Array.isArray(viewModel.platform_flow) ? viewModel.platform_flow : [],
      artifactRows: buildArtifactRows({ summary, stages }),
      loadedAtUtc: new Date().toISOString().replace(".000Z", "Z"),
    };

    state.cache.set(scenario.useCaseId, payload);
    return payload;
  }

  function renderRunSnapshot(data) {
    const passRate = stagePassRate(data);
    const runStatus = String((data.latestRun && data.latestRun.run_status) || "unknown");
    const runtimeMode = String((data.summary && data.summary.runtime_mode) || "default");

    els.runId.textContent = String((data.latestRun && data.latestRun.run_id) || "n/a");
    els.runStatus.innerHTML = `<span class="wb-status-pill ${statusClass(runStatus)}">${escapeHtml(runStatus)}</span>`;
    els.passRate.textContent = passRate !== null ? formatPercent(passRate, 0) : "n/a";
    els.runtime.textContent = runtimeMode;

    renderTechnicalSnapshot(data);
  }

  function renderTechnicalSnapshot(data) {
    if (!els.techCard) {
      return;
    }

    const stageRows = getStageRows(data);
    const passCount = stageRows.filter((row) => String(row.status || "").toLowerCase() === "pass").length;
    const warnCount = stageRows.filter((row) => String(row.status || "").toLowerCase().includes("warn")).length;
    const failCount = stageRows.filter((row) => {
      const token = String(row.status || "").toLowerCase();
      return token && token !== "pass" && !token.includes("warn") && token !== "unknown";
    }).length;

    const artifacts = Array.isArray(data.artifactRows) ? data.artifactRows : [];
    const present = artifacts.filter((row) => row.exists === true).length;
    const missing = artifacts.filter((row) => row.exists === false).length;

    const dq = data.dataQuality || {};
    const backend = data.summary && data.summary.model_metrics ? data.summary.model_metrics.model_backend : null;

    if (els.techComponents) {
      els.techComponents.textContent = `${passCount}/${stageRows.length || 0} pass`;
      if (warnCount > 0 || failCount > 0) {
        els.techComponents.textContent += ` (${warnCount} warn, ${failCount} fail)`;
      }
    }
    if (els.techArtifacts) {
      els.techArtifacts.textContent = `${present}/${artifacts.length || 0} present`;
      if (missing > 0) {
        els.techArtifacts.textContent += `, ${missing} missing`;
      }
    }
    if (els.techDq) {
      const status = String(dq.data_quality_status || "not_available");
      const blockers = formatValue(dq.blocker_count);
      const warnings = formatValue(dq.warning_count);
      els.techDq.textContent = `${status} (${blockers}/${warnings})`;
    }
    if (els.techBackend) {
      els.techBackend.textContent = backend ? String(backend) : "n/a";
    }
  }

  function renderTechnicalStep(data) {
    if (state.step === 0) {
      return renderTechnicalInputStep(data);
    }
    if (state.step === 1) {
      return renderTechnicalModelStep(data);
    }
    return renderTechnicalGovernanceStep(data);
  }

  function renderContent(data) {
    if (!data) {
      els.content.innerHTML = "<p>Loading scenario data...</p>";
      return;
    }

    if (state.persona === "technical") {
      els.content.innerHTML = renderTechnicalStep(data);
      return;
    }

    if (state.step === 0) {
      els.content.innerHTML = renderBusinessInputStep(data);
      return;
    }

    if (state.step === 1) {
      els.content.innerHTML = renderBusinessRecommendationStep(data);
      return;
    }

    if (state.step === 2) {
      els.content.innerHTML = renderBusinessImpactStep(data);
      return;
    }

    els.content.innerHTML = renderBusinessResultsStep(data);
  }

  function renderError(message) {
    els.content.innerHTML = `
      <h4 class="wb-section-title">Model evidence unavailable</h4>
      <p class="wb-section-sub">${escapeHtml(message)}</p>
      <ul class="wb-list">
        <li>Make sure standalone server is running: <code>make standalone</code> or <code>make ui-live</code>.</li>
        <li>Run at least one cycle for the selected scenario.</li>
        <li>Use <strong>Refresh Model Evidence</strong> to retry.</li>
      </ul>
    `;
  }

  function updateStepButtons() {
    const labels = stepTitlesForCurrentPersona();
    els.stepButtons.forEach((button, index) => {
      const title = labels[index] || `Step ${index + 1}`;
      button.textContent = `${index + 1}. ${title}`;
      button.hidden = index >= labels.length;
      button.classList.toggle("is-active", index === state.step);
    });
  }

  function renderHeader() {
    const scenario = SCENARIOS[state.scenarioKey];
    const stepLabels = stepTitlesForCurrentPersona();

    els.modeKicker.textContent = state.persona === "technical" ? "Model Evidence View" : "Decision View";
    els.pageTitle.textContent = scenario.label;
    els.stepTitle.textContent = `Step ${state.step + 1}: ${stepLabels[state.step] || "Step"}`;

    const subtitle = state.persona === "technical"
      ? "Deep technical walkthrough: contracts, stage evidence, model lineage, and governance artifacts."
      : "AI decision narrative with model inputs, recommendations, forecasts, and evidence in sequence.";
    els.stepSubtitle.textContent = subtitle;

    const progress = ((state.step + 1) / stepLabels.length) * 100;
    els.progress.style.width = `${progress}%`;

    els.prev.disabled = state.step <= 0;
    els.next.disabled = state.step >= currentMaxStepIndex();

    els.openStoryboard.href = scenario.storyboardHref;

    els.scenarioButtons.forEach((button) => {
      button.classList.toggle("is-active", button.getAttribute("data-scenario") === state.scenarioKey);
    });

    els.personaButtons.forEach((button) => {
      button.classList.toggle("is-active", button.getAttribute("data-persona") === state.persona);
    });

    if (els.techCard) {
      els.techCard.hidden = state.persona !== "technical";
    }

    updateStepButtons();
  }

  async function refreshData({ force = false } = {}) {
    state.loading = true;
    state.error = null;
    renderHeader();
    els.liveStatus.textContent = `Loading model evidence for ${SCENARIOS[state.scenarioKey].label}...`;

    try {
      const data = await loadScenarioData({ force });
      state.loading = false;
      state.error = null;
      renderHeader();
      renderRunSnapshot(data);
      renderContent(data);
      els.liveStatus.textContent = `Model evidence active from run, stage, governance, and artifact APIs.`;
    } catch (error) {
      state.loading = false;
      state.error = error instanceof Error ? error.message : String(error);
      renderHeader();
      renderError(state.error);
      els.runId.textContent = "n/a";
      els.runStatus.textContent = "n/a";
      els.passRate.textContent = "n/a";
      els.runtime.textContent = "n/a";
      if (els.techComponents) {
        els.techComponents.textContent = "n/a";
      }
      if (els.techArtifacts) {
        els.techArtifacts.textContent = "n/a";
      }
      if (els.techDq) {
        els.techDq.textContent = "n/a";
      }
      if (els.techBackend) {
        els.techBackend.textContent = "n/a";
      }
      els.liveStatus.textContent = `Model evidence unavailable: ${state.error}`;
    }
  }

  function currentData() {
    const scenario = SCENARIOS[state.scenarioKey];
    return scenario ? state.cache.get(scenario.useCaseId) : null;
  }

  function rerenderFromCache() {
    renderHeader();
    const data = currentData();
    if (data) {
      renderRunSnapshot(data);
      renderContent(data);
    }
  }

  function handleScenarioChange(nextScenario) {
    if (!SCENARIOS[nextScenario]) {
      return;
    }
    state.scenarioKey = nextScenario;
    state.step = 0;
    updateQueryString();
    void refreshData({ force: false });
  }

  function handlePersonaChange(nextPersona) {
    state.persona = nextPersona === "technical" ? "technical" : "business";
    state.step = Math.min(state.step, currentMaxStepIndex());
    updateQueryString();
    rerenderFromCache();
  }

  function handleStepChange(nextStep) {
    state.step = Math.max(0, Math.min(currentMaxStepIndex(), Number(nextStep) || 0));
    updateQueryString();
    rerenderFromCache();
  }

  function handleWorkbenchContentChange(event) {
    const target = event && event.target;
    if (!target || !target.id) {
      return;
    }

    if (target.id === "wb-artifact-filter-stage") {
      state.artifactFilters.stage = String(target.value || "all");
      rerenderFromCache();
      return;
    }

    if (target.id === "wb-artifact-filter-exists") {
      state.artifactFilters.exists = String(target.value || "all");
      rerenderFromCache();
      return;
    }

    if (target.id === "wb-artifact-filter-query") {
      state.artifactFilters.query = String(target.value || "");
      rerenderFromCache();
    }
  }

  function handleWorkbenchContentClick(event) {
    const target = event && event.target;
    if (!target || target.id !== "wb-download-visible") {
      return;
    }
    event.preventDefault();
    const data = currentData();
    if (!data) {
      return;
    }
    downloadVisibleArtifactBundle(data);
  }

  function bindEvents() {
    els.scenarioButtons.forEach((button) => {
      button.addEventListener("click", () => {
        handleScenarioChange(String(button.getAttribute("data-scenario") || ""));
      });
    });

    els.personaButtons.forEach((button) => {
      button.addEventListener("click", () => {
        handlePersonaChange(String(button.getAttribute("data-persona") || "business"));
      });
    });

    els.stepButtons.forEach((button) => {
      button.addEventListener("click", () => {
        handleStepChange(Number(button.getAttribute("data-step-index")));
      });
    });

    els.prev.addEventListener("click", () => {
      handleStepChange(state.step - 1);
    });

    els.next.addEventListener("click", () => {
      handleStepChange(state.step + 1);
    });

    els.refresh.addEventListener("click", () => {
      void refreshData({ force: true });
    });

    if (els.content) {
      els.content.addEventListener("change", handleWorkbenchContentChange);
      els.content.addEventListener("input", handleWorkbenchContentChange);
      els.content.addEventListener("click", handleWorkbenchContentClick);
    }

    document.addEventListener("keydown", (event) => {
      const tag = event.target && event.target.tagName ? String(event.target.tagName).toLowerCase() : "";
      if (tag === "input" || tag === "textarea" || tag === "select") {
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        handleStepChange(state.step - 1);
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        handleStepChange(state.step + 1);
      }
    });
  }

  function hydrateFromQuery() {
    const params = new URLSearchParams(window.location.search);
    state.scenarioKey = pickScenarioFromQuery(params.get("scenario"));
    state.persona = pickPersonaFromQuery(params.get("persona"));
    state.step = pickStepFromQuery(params.get("step"));
  }

  function init() {
    bindEvents();
    hydrateFromQuery();
    updateQueryString();
    renderHeader();
    void refreshData({ force: false });
  }

  init();
})();
