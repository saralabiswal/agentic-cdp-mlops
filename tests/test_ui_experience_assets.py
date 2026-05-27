from __future__ import annotations

from pathlib import Path


def test_clean_experience_shell_is_wired() -> None:
    html = Path("ui/experience/index.html").read_text(encoding="utf-8")
    css = Path("ui/experience/clean-flow.css").read_text(encoding="utf-8")
    js = Path("ui/experience/clean-flow.js").read_text(encoding="utf-8")

    assert "clean-flow.css" in html
    assert "clean-flow.js" in html
    assert "Production ML Governance Platform" in html
    assert "Production ML governance, model evidence, and activation readiness." in html
    assert 'id="metric-model-count"' in html
    assert 'id="metric-run-status"' in html
    assert 'id="metric-stage-count"' in html
    assert 'id="metric-runtime"' in html
    assert 'id="model-grid"' in html
    assert 'id="evidence-list"' in html
    assert 'id="architecture"' in html
    assert 'id="simulation"' in html
    assert 'id="sim-use-case"' in html
    assert 'id="sim-scenario"' in html
    assert 'id="sim-runtime"' in html
    assert 'id="sim-infra"' in html
    assert 'id="sim-run-next"' in html
    assert 'id="sim-run-all"' in html
    assert 'id="sim-reset"' in html

    nav = html[html.index('<nav class="clean-nav"') : html.index("</nav>")]
    assert nav.index("About") < nav.index("Overview")
    assert nav.index("Overview") < nav.index("Model Portfolio")
    assert nav.index("Model Portfolio") < nav.index("Run Evidence")
    assert nav.index("Run Evidence") < nav.index("Simulation")
    assert nav.index("Simulation") < nav.index("Architecture")

    flow = html[html.index('id="presentation-flow"') : html.index('id="model-grid"')]
    assert flow.index("Portfolio health") < flow.index("Model decision")
    assert flow.index("Model decision") < flow.index("Run evidence")
    assert flow.index("Run evidence") < flow.index("Simulation")
    assert flow.index("Simulation") < flow.index("Architecture")
    assert "Latest run snapshot" in html
    assert "Evidence center" in html
    assert "Architecture path" in html

    assert "--nav: #20242b" in css
    assert "--primary: #1f5f8f" in css
    assert "overflow-x: hidden" in css
    assert "grid-template-columns: 272px minmax(0, 1fr)" in css
    assert "@media (max-width: 760px)" in css
    assert "body.simulation-mode .clean-static-overview" in css

    assert "/api/view-model" in js
    assert "/api/runs?limit=20&status=all&infra=all" in js
    assert "/api/artifacts/download?path=" in js
    assert "/api/scenarios" in js
    assert "/api/simulation/session" in js
    assert "run-next" in js
    assert "run-all" in js
    assert "simulation-mode" in js
    assert "TensorFlow Next Best Action" in js
    assert "Bayesian Media Mix Optimization" in js
    assert "OSS" in js


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
    about = Path("ui/experience/about.html").read_text(encoding="utf-8")
    about_css = Path("ui/experience/about.css").read_text(encoding="utf-8")
    about_js = Path("ui/experience/about.js").read_text(encoding="utf-8")
    home = Path("ui/experience/business-home.html").read_text(encoding="utf-8")
    exec_summary = Path("ui/experience/business-exec-summary.html").read_text(encoding="utf-8")
    workbench = Path("ui/experience/workbench.html").read_text(encoding="utf-8")
    css = Path("ui/experience/business-storyboard.css").read_text(encoding="utf-8")
    workbench_css = Path("ui/experience/workbench.css").read_text(encoding="utf-8")
    exec_live_js = Path("ui/experience/business-exec-live.js").read_text(encoding="utf-8")
    workbench_js = Path("ui/experience/workbench.js").read_text(encoding="utf-8")

    assert "CDP AI/ML Platform | About" in about
    assert "<h1>About the Platform</h1>" in about
    assert "The Problem" in about
    assert "How It Works" in about
    assert "Use Cases" in about
    assert "Governance" in about
    assert "Production Context" in about
    assert "Architecture" in about
    assert "Enterprise ML Has a Governance Gap" in about
    assert "UC-NBA-RET-001 - Next Best Action for Retention" in about
    assert "Evidence-First Governance" in about
    assert "Built From Production Experience at Oracle Scale" in about
    assert "Three ML Paradigms" in about
    about_nav = about[about.index('<nav class="top-nav story-nav"') : about.index("</nav>")]
    assert about_nav.index("About") < about_nav.index("AI Decision Portfolio")
    assert "about.css" in about
    assert "about.js" in about
    assert ".about-tab-list" in about_css
    assert "data-about-tab" in about_js

    for page_html in (home, exec_summary, workbench):
        nav = page_html[page_html.index("<nav") : page_html.index("</nav>")]
        assert nav.index("About") < nav.index("AI Decision Portfolio")
        assert 'href="about.html"' in nav

    assert "<h1>AI Decision Portfolio</h1>" in home
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
