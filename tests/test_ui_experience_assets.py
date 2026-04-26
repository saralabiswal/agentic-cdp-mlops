from __future__ import annotations

from pathlib import Path


def test_run_history_baseline_selector_exists() -> None:
    html = Path("ui/experience/index.html").read_text(encoding="utf-8")
    assert 'id="run-history-baseline"' in html
    assert '<option value="3" selected>3</option>' in html
    assert "Run Integrated AI Runtime" in html
    assert "Run Standalone AI Runtime" in html
    assert html.index('data-evidence-view="artifacts"') < html.index('data-evidence-view="flow"')
    assert html.index('data-evidence-view="flow"') < html.index('data-evidence-view="history"')
    assert 'data-evidence-view="history"' in html
    assert 'data-evidence-panel="portfolio"' in html
    assert "Run history baseline selector" in html
    assert 'id="run-runtime-mode"' in html
    assert 'id="run-scenario-id"' in html
    assert 'id="enterprise-profile-select"' in html
    assert "Enterprise Integration Profile" in html
    assert 'id="sim-next-btn"' in html
    assert 'id="sim-pause-btn"' in html
    assert 'id="sim-resume-btn"' in html
    assert 'id="sim-reset-btn"' in html
    assert 'id="enterprise-hardening"' in html
    assert 'id="architecture-story"' in html
    assert 'id="arch-story-rail"' in html
    assert 'id="arch-story-prev"' in html
    assert 'id="arch-story-next"' in html
    assert 'id="arch-stage-proof"' in html
    assert 'id="arch-stage-inputs"' in html
    assert 'id="arch-stage-outputs"' in html
    assert "AI/ML Platform Architecture" in html
    assert "AI/ML Decision Intelligence Architecture" in html
    assert "business-home.html" in html
    assert "business-exec-summary.html" in html
    nav = html[html.index('<nav class="wb-theme-top-nav"') : html.index("</nav>")]
    assert nav.index("AI Decision Portfolio") < nav.index("AI Impact Summary")
    assert nav.index("AI Impact Summary") < nav.index("Model Decision Workbench")
    assert nav.index("Model Decision Workbench") < nav.index("AI/ML Platform Architecture")
    assert "What This Proves" in html
    assert "Architecture &amp; Design" in html
    assert "Backend Model Runtime" in html
    assert '<svg' in html
    assert 'class="backend-architecture-svg"' in html
    assert "backend-svg-title" in html
    assert 'class="stage-architecture-svg"' in html
    assert "stage-svg-title" in html
    assert "8-Stage Technical Component Diagram" in html
    assert "Data Sources to Monitoring + Governance" in html
    assert "Experience Layer" in html
    assert "Run Orchestrator" in html
    assert "Evidence Plane" in html
    assert "Ingestion +" in html
    assert "Event Bus" in html
    assert "Raw + Curated" in html
    assert "Storage" in html
    assert "Identity + 360" in html
    assert "Feature Layer" in html
    assert "Model Layer" in html
    assert "Serving + Activation" in html
    assert "Monitoring +" in html
    assert "Governance" in html
    assert "Architecture Summary For Technical Reviewers" in html
    assert "one reusable AI/ML backend pipeline" in html
    assert "Enterprise Integration Path" in html
    assert "Architecture Message" in html
    assert "The platform keeps one model contract" in html
    assert "Presentation Steps" in html
    assert 'href="#architecture-story"' in html
    assert "Business View" not in html
    assert "Business audience?" not in html
    css = Path("ui/experience/styles.css").read_text(encoding="utf-8")
    assert "#use-case-select" in css
    assert "data:image/svg+xml" in css
    assert ".backend-diagram" in css
    assert ".backend-architecture-svg" in css
    assert ".stage-architecture-svg" in css
    assert ".architecture-summary" in css


def test_run_history_comparison_rendering_is_wired() -> None:
    js = Path("ui/experience/app.js").read_text(encoding="utf-8")
    assert "renderRunHistoryComparison" in js
    assert "comparison.status_transition" in js
    assert "stage_pass_delta" in js
    assert "kpi_deltas" in js
    assert "stage_status_deltas" in js
    assert "Delta Drilldown" in js


def test_ui_stage_detail_and_portfolio_api_wiring_exists() -> None:
    js = Path("ui/experience/app.js").read_text(encoding="utf-8")
    assert "runSummaryByRunKey" in js
    assert "refreshRunSummaryForSelectedUseCase" in js
    assert "getRunSummaryForRun" in js
    assert "/api/runs/${encodeURIComponent(useCaseId)}/${encodeURIComponent(runId)}" in js
    assert "/api/runs/${encodeURIComponent(useCaseId)}/${encodeURIComponent(runId)}/stages" in js
    assert "/api/portfolio/summary?" in js
    assert "mergeGuidedSteps" in js
    assert "/api/scenarios" in js
    assert "/api/oss-inventory" in js
    assert "/api/enterprise-hardening?profile=${profile}" in js
    assert "enterpriseProfile" in js
    assert "TECHNICAL_STAGE_STORY" in js
    assert "Why This Stage Matters" in js
    assert "renderHardeningModuleCard" in js
    assert "renderEvidencePanels" in js
    assert "runEvidenceView" in js
    assert "data-run-evidence-view" in js
    assert "formatArtifactPathForDisplay" in js
    assert "infraProfileLabel" in js
    assert "row.license" not in js
    assert "/api/simulation/session" in js
    assert "/pause" in js
    assert "/resume" in js
    assert "artifact-filter-stage" in js
    assert "artifact-download-visible" in js
    assert "/api/artifacts/download?path=" in js
    assert "stageTraceId" in js


def test_business_experience_pages_exist_and_are_linked() -> None:
    home = Path("ui/experience/business-home.html").read_text(encoding="utf-8")
    exec_summary = Path("ui/experience/business-exec-summary.html").read_text(encoding="utf-8")
    workbench = Path("ui/experience/workbench.html").read_text(encoding="utf-8")
    css = Path("ui/experience/business-storyboard.css").read_text(encoding="utf-8")
    workbench_css = Path("ui/experience/workbench.css").read_text(encoding="utf-8")
    exec_live_js = Path("ui/experience/business-exec-live.js").read_text(encoding="utf-8")
    workbench_js = Path("ui/experience/workbench.js").read_text(encoding="utf-8")

    assert "Enterprise AI Decision Portfolio" in home
    assert "<span>01</span> Next Best Action" not in home
    assert "<span>02</span> Churn Prevention" not in home
    assert "<span>03</span> Media Mix" not in home
    assert "<span>04</span> Incrementality" not in home
    assert "TensorFlow Next Best Action Model" in home
    assert "TensorFlow Churn Propensity Model" in home
    assert "Bayesian Media Mix Optimization" in home
    assert "Causal Incrementality Model" in home
    assert "workbench.html?scenario=nba&persona=business&step=1" in home
    assert "workbench.html?scenario=churn&persona=business&step=1" in home
    assert "workbench.html?scenario=mmm&persona=business&step=1" in home
    assert "workbench.html?scenario=incrementality&persona=business&step=1" in home
    assert "Open Model Workbench" in home
    assert "Open AI Impact Summary" in home
    assert "Model evidence: Latest run" in home
    assert "Recommended AI/ML Presentation Sequence" in home
    assert "Start With AI Decisioning" in home
    assert home.index("How To Present The AI/ML Story") < home.index("TensorFlow Next Best Action")
    assert home.index("How To Present The AI/ML Story") < home.index("Recommended AI/ML Presentation Sequence")

    assert "AI Impact Summary" in exec_summary
    assert "<span>01</span> Next Best Action" not in exec_summary
    assert "<span>02</span> Churn Prevention" not in exec_summary
    assert "<span>03</span> Media Mix" not in exec_summary
    assert "<span>04</span> Incrementality" not in exec_summary
    assert 'id="exec-live-status"' in exec_summary
    assert 'id="exec-cards"' in exec_summary
    assert "Print / Save PDF" in exec_summary
    assert "business-exec-live.js" in exec_summary
    assert "workbench.html?scenario=nba&persona=business&step=1" not in exec_summary

    assert "Model Decision Workbench" in workbench
    assert 'data-scenario="nba"' in workbench
    assert 'data-persona="business"' in workbench
    assert 'data-step-index="2"' in workbench
    assert 'data-step-index="3"' in workbench
    assert 'id="wb-content"' in workbench
    assert "workbench.js" in workbench
    assert "Decision Evidence" in workbench_js
    assert "Expected Uplift" in workbench_js
    assert "Decision Confidence" in workbench_js
    assert "renderBusinessResultsStep" in workbench_js

    assert ".flow-card-grid" in css
    assert ".support-actions" in css
    assert ".pipeline" in css
    assert ".hero-live-status" in css
    assert ".hero-steps" in css
    assert ".story-intro" in css
    assert ".exec-grid" in css
    assert ".guided-shell" in css
    assert ".guided-step-btn" in css
    assert ".story-guided-mode .pipeline" in css
    assert "@media print" in css
    assert ".wb-layout" in workbench_css
    assert ".wb-left-rail" in workbench_css
    assert ".wb-center-panel" in workbench_css
    assert ".wb-right-panel" in workbench_css

    assert "workbench.html" in exec_summary

    assert "UC-NBA-RET-001" in exec_live_js
    assert "UC-CHURN-RET-002" in exec_live_js
    assert "UC-MMM-PLN-003" in exec_live_js
    assert "UC-INCR-MKT-004" in exec_live_js
    assert "/api/run-history" in exec_live_js
    assert "/api/runs/" in exec_live_js
    assert "window.print()" in exec_live_js
    assert "workbench.html?scenario=nba&persona=business&step=1" in exec_live_js
    assert "workbench.html?scenario=churn&persona=business&step=1" in exec_live_js
    assert "workbench.html?scenario=mmm&persona=business&step=1" in exec_live_js
    assert "workbench.html?scenario=incrementality&persona=business&step=1" in exec_live_js

    assert "UC-NBA-RET-001" in workbench_js
    assert "UC-CHURN-RET-002" in workbench_js
    assert "UC-MMM-PLN-003" in workbench_js
    assert "UC-INCR-MKT-004" in workbench_js
    assert "/api/run-history" in workbench_js
    assert "/api/runs/" in workbench_js
    assert "/stages" in workbench_js
    assert "/data-quality" in workbench_js
    assert "workbench.html?scenario=nba&persona=business&step=1" in workbench_js

    assert not Path("ui/experience/nba-business-storyboard.html").exists()
    assert not Path("ui/experience/churn-business-storyboard.html").exists()
    assert not Path("ui/experience/mmm-business-storyboard.html").exists()
    assert not Path("ui/experience/incrementality-business-storyboard.html").exists()
    assert not Path("ui/experience/business-storyboard-live.js").exists()
    assert not Path("ui/experience/business-storyboard-guided.js").exists()
