# Use Case Charter

## 1) Metadata
- Use case name: Media Mix Modeling and Budget Optimization
- Use case ID: UC-MMM-PLN-003
- Owner (business): Performance Marketing Director
- Owner (data science): Marketing Science Lead
- Owner (engineering): Analytics Platform Lead
- Version: v0.1
- Status: Draft

## 2) Business Problem
- Problem statement: Channel budget planning is based on heuristics, resulting in inefficient spend allocation.
- Why now: Planning cycles require defensible budget shifts under tighter ROI targets.
- Decision that this use case should improve: How next-period budget should be allocated across channels.
- Current baseline process: Last-period trend extrapolation and manual stakeholder overrides.

## 3) Scope
- In-scope customers/channels/regions: US paid channels (search, social, display, affiliate, email).
- Out-of-scope: Organic-only channels, offline media not currently tracked, non-US markets.
- Assumptions: Weekly spend and outcome data is available with sufficient history.
- Dependencies: Curated spend dataset, outcome metrics, external control variables.

## 4) Success Metrics
- Primary KPI: Forecasted incremental revenue at fixed budget.
- Secondary KPI(s): Marginal ROI by channel, payback period.
- Guardrail KPI(s): Brand channel minimum spend, spend volatility limits, channel cap constraints.
- Baseline value: Current plan marginal ROI index = 1.00.
- Target value: >= 1.15 marginal ROI index at same total budget.
- Decision cadence: Monthly planning with weekly refresh diagnostics.

## 5) Data Requirements
- Entities needed: channel_spend, campaign, conversion, revenue, seasonality, promotions, macro_factors.
- Required fields: week_start, channel, spend, impressions, clicks, conversions, revenue, promo_flag, holiday_flag.
- Source systems: ad platforms, campaign systems, ecommerce orders, finance ledger, calendar and macro sources.
- Data freshness SLA: weekly consolidated updates by T+2 business days.
- Data quality thresholds: >= 99% coverage of planned spend, <= 1% unexplained missing weeks.

## 6) Model/Analytics Output
- Output type: forecast and optimization recommendation.
- Output schema: period, channel, base_contribution, incremental_contribution, response_curve_params, saturation_point, recommended_spend, expected_incremental_revenue, uncertainty_interval.
- Explainability fields: contribution waterfall and diminishing returns diagnostics.
- Confidence/uncertainty required: channel and portfolio uncertainty intervals.
- Output refresh cadence: monthly full model refresh and weekly diagnostic re-run.
- Max serving latency: not real-time; scenario response <= 5 seconds from API.

## 7) Decision Policy
- Business rules: optimize incremental revenue under fixed budget and operational constraints.
- Eligibility rules: channel must have minimum historical data and stable tracking.
- Suppression rules: channels with unresolved tracking anomalies are excluded.
- Compliance/consent checks: ensure outputs do not violate channel-specific policy restrictions.
- Fallback behavior if model unavailable: previous approved budget plan and rule-based adjustments.

## 8) Activation Plan
- Destination channels/tools: planning dashboard and budget recommendation API.
- Trigger conditions: monthly planning cycle and approved re-forecast request.
- Payload contract: plan_id, channel, recommended_spend, expected_roi, uncertainty_band, model_version.
- Frequency caps: one approved plan per cycle with controlled re-plan windows.
- Rollback plan: revert to previous approved budget with change log retained.

## 9) Experimentation Plan
- Hypothesis: MMM-informed budget allocation improves incremental revenue at fixed budget.
- Experiment design: phased rollout where selected campaigns follow model recommendations and matched controls stay on baseline.
- Randomization unit: campaign group or geo cluster.
- Control/treatment split: 50% baseline planning, 50% model-informed planning where feasible.
- Duration: 8 to 12 weeks.
- Minimum detectable effect (MDE): 8% incremental revenue lift at portfolio level.
- Significance/confidence rules: 95% confidence plus practical significance threshold.
- Stop/go criteria: continue if observed lift aligns with uncertainty interval and guardrails hold.

## 10) Validation and Governance
- Offline validation tests: rolling backtests, MAPE, directional accuracy, coefficient sanity checks.
- Online validation tests: scenario replay and realized-vs-expected performance monitoring.
- Promotion gates: error threshold met, diagnostics pass, scientific review approved.
- Model registry/versioning: versioned model artifact, training window ID, and hyperparameter log.
- Audit artifacts required: model card, backtest report, scenario assumptions, approval record.

## 11) Monitoring
- Data drift checks: spend mix shift and channel metric distribution monitoring.
- Performance drift checks: forecast error drift and scenario calibration drift.
- Business KPI monitoring: realized incremental revenue, ROI, and budget efficiency.
- Alert thresholds: MAPE exceeds threshold for 2 consecutive cycles or channel anomaly flags rise.
- On-call owner: Marketing Science Ops.

## 12) Delivery Plan
- Milestones: M1 data mart, M2 baseline MMM, M3 scenario API, M4 pilot planning cycle, M5 readout.
- Target dates: 2026-05-18 to 2026-07-31.
- Risks: confounding macro events, sparse channel history, delayed revenue attribution.
- Mitigations: control variables, hierarchical priors, lag-sensitive evaluation windows.

## 13) Acceptance Criteria
- Business acceptance criteria: model-informed plan adopted for at least one planning cycle.
- Technical acceptance criteria: backtest thresholds met and scenario API meets SLA.
- Sign-off approvers: Performance Marketing, Data Science, Analytics Engineering, Finance.

