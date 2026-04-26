(() => {
  "use strict";

  const FLOWS = [
    {
      id: "nba",
      label: "TensorFlow Next Best Action Model",
      useCaseId: "UC-NBA-RET-001",
      detailHref: "workbench.html?scenario=nba&persona=business&step=1",
      decisionText: "Approve the model-ranked action pack for highest-value eligible customers.",
      kpiFromSummary(summary, latest) {
        const uplift = asNumber(summary.model_metrics?.avg_expected_uplift);
        const confidence = asNumber(summary.model_metrics?.avg_confidence);
        return [
          { label: "Expected Uplift", value: uplift !== null ? `+${toPercent(uplift, 1)}` : "n/a" },
          { label: "Decision Confidence", value: confidence !== null ? toPercent(confidence, 0) : "n/a" },
          { label: "Run Status", value: labelRunStatus(latest.run_status) },
        ];
      },
    },
    {
      id: "churn",
      label: "TensorFlow Churn Propensity Model",
      useCaseId: "UC-CHURN-RET-002",
      detailHref: "workbench.html?scenario=churn&persona=business&step=1",
      decisionText: "Prioritize model-recommended save treatments for high-risk subscribers.",
      kpiFromSummary(summary, latest) {
        const avgRisk = asNumber(summary.model_metrics?.avg_churn_risk_score);
        const uplift = asNumber(summary.model_metrics?.avg_expected_uplift);
        return [
          { label: "Average Churn Risk", value: avgRisk !== null ? toPercent(avgRisk, 1) : "n/a" },
          { label: "Expected Save Lift", value: uplift !== null ? `+${toPercent(uplift, 1)}` : "n/a" },
          { label: "Run Status", value: labelRunStatus(latest.run_status) },
        ];
      },
    },
    {
      id: "mmm",
      label: "Bayesian Media Mix Optimization",
      useCaseId: "UC-MMM-PLN-003",
      detailHref: "workbench.html?scenario=mmm&persona=business&step=1",
      decisionText: "Approve Bayesian budget shifts toward channels with the strongest marginal return.",
      kpiFromSummary(summary, latest) {
        const mape = asNumber(summary.model_metrics?.revenue_mape);
        const rows = asNumber(summary.records?.model_rows);
        return [
          { label: "Forecast Error (MAPE)", value: mape !== null ? toPercent(mape, 1) : "n/a" },
          { label: "Channels Planned", value: rows !== null ? String(Math.round(rows)) : "n/a" },
          { label: "Run Status", value: labelRunStatus(latest.run_status) },
        ];
      },
    },
    {
      id: "incrementality",
      label: "Causal Incrementality Model",
      useCaseId: "UC-INCR-MKT-004",
      detailHref: "workbench.html?scenario=incrementality&persona=business&step=1",
      decisionText: "Scale campaigns with measured causal lift and pause weak performers.",
      kpiFromSummary(summary, latest) {
        const lift = asNumber(summary.model_metrics?.avg_incremental_lift);
        const iroas = asNumber(summary.model_metrics?.avg_iROAS);
        return [
          { label: "Average True Lift", value: lift !== null ? `+${toPercent(lift, 1)}` : "n/a" },
          { label: "Average iROAS", value: iroas !== null ? `${iroas.toFixed(2)}x` : "n/a" },
          { label: "Run Status", value: labelRunStatus(latest.run_status) },
        ];
      },
    },
  ];

  function asNumber(value) {
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

  function toPercent(value, digits) {
    return `${(value * 100).toFixed(digits)}%`;
  }

  function labelRunStatus(status) {
    const normalized = String(status || "unknown").toLowerCase();
    if (normalized === "pass") {
      return "Pass";
    }
    if (normalized === "fail") {
      return "Fail";
    }
    return "Unknown";
  }

  function formatUtcNow() {
    return new Date().toISOString().replace(".000Z", "Z");
  }

  async function fetchJson(url) {
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`Request failed (${response.status}) for ${url}`);
    }
    return await response.json();
  }

  async function fetchLatestFlowSummary(useCaseId) {
    const history = await fetchJson(
      `/api/run-history?use_case_id=${encodeURIComponent(useCaseId)}&limit=1&status=all&infra=all&baseline=latest`
    );
    const latest = Array.isArray(history.runs) ? history.runs[0] : null;
    if (!latest?.run_id) {
      throw new Error(`No runs found for ${useCaseId}.`);
    }

    const summary = await fetchJson(
      `/api/runs/${encodeURIComponent(useCaseId)}/${encodeURIComponent(latest.run_id)}`
    );
    return { latest, summary };
  }

  function getPassRate(latest) {
    const passCount = asNumber(latest.stage_pass_count);
    const total = asNumber(latest.stage_total);
    if (passCount === null || total === null || total <= 0) {
      return null;
    }
    return passCount / total;
  }

  function cardTemplate(flow, latest, summary) {
    const passRate = getPassRate(latest);
    const runtime = String(summary.runtime_mode || "unknown");
    const scenario = String(summary.scenario_id || "default");
    const kpis = flow.kpiFromSummary(summary, latest);

    const kpiRows = kpis
      .map(
        (item) =>
          `<div class="exec-kpi-row"><span>${item.label}</span><strong>${item.value}</strong></div>`
      )
      .join("");

    return `
      <article class="exec-card">
        <div class="exec-card-head">
          <h3>${flow.label}</h3>
          <p class="exec-run">Run ${latest.run_id}</p>
        </div>
        <p class="exec-decision"><strong>Decision:</strong> ${flow.decisionText}</p>
        <p class="exec-context"><strong>Model Flow:</strong> Inputs -> Recommendation -> Impact -> Evidence</p>
        <div class="exec-kpi-list">${kpiRows}</div>
        <p class="exec-health">Pipeline health: ${passRate !== null ? toPercent(passRate, 0) : "n/a"} stages passed</p>
        <p class="exec-meta">Runtime: ${runtime} | Scenario Preset: ${scenario}</p>
        <a class="exec-link" href="${flow.detailHref}">Review Model Workflow</a>
      </article>
    `;
  }

  function setText(id, value) {
    const node = document.getElementById(id);
    if (node) {
      node.textContent = value;
    }
  }

  function wireControls() {
    const refreshBtn = document.getElementById("exec-refresh");
    const printBtn = document.getElementById("exec-print");

    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => {
        void render();
      });
    }

    if (printBtn) {
      printBtn.addEventListener("click", () => {
        window.print();
      });
    }
  }

  async function render() {
    const cardsNode = document.getElementById("exec-cards");
    if (!cardsNode) {
      return;
    }

    setText("exec-live-status", "Loading live AI impact summary...");

    try {
      const results = await Promise.all(
        FLOWS.map(async (flow) => {
          const data = await fetchLatestFlowSummary(flow.useCaseId);
          return { flow, ...data };
        })
      );

      const healthyCount = results.filter((item) => String(item.latest.run_status).toLowerCase() === "pass").length;
      const passRates = results
        .map((item) => getPassRate(item.latest))
        .filter((value) => typeof value === "number");
      const avgPass =
        passRates.length > 0 ? passRates.reduce((sum, value) => sum + value, 0) / passRates.length : null;

      cardsNode.innerHTML = results
        .map((item) => cardTemplate(item.flow, item.latest, item.summary))
        .join("");

      setText("exec-flows-reviewed", String(results.length));
      setText("exec-flows-healthy", `${healthyCount}/${results.length}`);
      setText("exec-avg-pass-rate", avgPass !== null ? toPercent(avgPass, 0) : "n/a");
      setText("exec-last-refresh", formatUtcNow());
      setText(
        "exec-live-status",
        "Live model evidence active: sourced from /api/run-history and /api/runs across all four AI/ML use cases."
      );
      setText(
        "exec-footnote",
        "AI impact summary loaded from latest model-run evidence. Use Print / Save PDF for stakeholder sharing."
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setText("exec-live-status", `Model evidence unavailable: ${message}`);
      setText("exec-footnote", "Model evidence could not be loaded; ensure standalone server is running and run history exists.");
      cardsNode.innerHTML =
        '<article class="exec-card exec-card-error"><h3>Model evidence unavailable</h3><p>Run at least one cycle for each AI/ML use case, then refresh this page.</p></article>';
      setText("exec-flows-healthy", "n/a");
      setText("exec-avg-pass-rate", "n/a");
      setText("exec-last-refresh", formatUtcNow());
    }
  }

  wireControls();
  void render();
})();
