# Use Case Charter

## 1) Metadata
- Use case name: Churn Prediction and Retention Actioning
- Use case ID: UC-CHURN-RET-002
- Owner (business): Retention Marketing Lead
- Owner (data science): Customer Analytics Lead
- Owner (engineering): CDP Platform Lead
- Version: v0.1
- Status: Draft

## 2) Business Problem
- Problem statement: High-value customers churn before intervention and current targeting is reactive.
- Why now: Budget pressure requires protecting existing revenue efficiently.
- Decision that this use case should improve: Who is likely to churn and which intervention should be prioritized.
- Current baseline process: Heuristic churn flags and manual campaign lists.

## 3) Scope
- In-scope customers/channels/regions: US B2C; Email, Push, and Paid Retargeting.
- Out-of-scope: Inbound service intervention and non-US geographies.
- Assumptions: Historical churn labels and transaction history are sufficiently complete.
- Dependencies: Customer 360 profile, feature pipelines, action catalog, activation adapters.

## 4) Success Metrics
- Primary KPI: 60-day incremental churn reduction vs control.
- Secondary KPI(s): Retained revenue, save-rate.
- Guardrail KPI(s): Discount cost per save, unsubscribe rate, complaint rate.
- Baseline value: 60-day churn at 12.0%.
- Target value: 1.8 percentage points absolute churn reduction.
- Decision cadence: Daily scoring and weekly retention action refresh.

## 5) Data Requirements
- Entities needed: customer, transaction, event, support_case, consent.
- Required fields: customer_id, tenure_days, last_purchase_ts, purchase_frequency, support_tickets_30d, campaign_response, consent_status.
- Source systems: CRM, order history, web/app event stream, support platform, campaign platform.
- Data freshness SLA: behavioral events <= 30 minutes, customer master <= 24 hours.
- Data quality thresholds: >= 99% key completeness, <= 1% duplicate customer keys after identity merge.

## 6) Model/Analytics Output
- Output type: score and recommendation.
- Output schema: customer_id, churn_risk_score, risk_band, recommended_action, expected_uplift, reason_codes, score_ts, model_version.
- Explainability fields: top_3_drivers, monotonic risk factors.
- Confidence/uncertainty required: calibrated churn probability and expected uplift interval.
- Output refresh cadence: nightly scoring with optional event-triggered refresh for high-risk state changes.
- Max serving latency: <= 250 ms p95 for on-demand API.

## 7) Decision Policy
- Business rules: prioritize highest expected retained value under contact and incentive constraints.
- Eligibility rules: active consent, no active dispute/fraud flag, profile completeness threshold met.
- Suppression rules: contacted in last 72 hours, active retention journey already running.
- Compliance/consent checks: channel-level consent and legal suppression lists enforced pre-activation.
- Fallback behavior if model unavailable: risk-decile rule list based on most recent stable model snapshot.

## 8) Activation Plan
- Destination channels/tools: webhook adapter to campaign orchestration tool.
- Trigger conditions: nightly scoring publish or risk escalation event.
- Payload contract: customer_id, churn_risk_score, action_id, channel, priority, validity_window.
- Frequency caps: max 1 retention intervention per day and 3 per week.
- Rollback plan: disable model flag and route to baseline suppression-safe rule campaign.

## 9) Experimentation Plan
- Hypothesis: model-driven retention intervention reduces 60-day churn by at least 1.8 points.
- Experiment design: stratified RCT by value tier and churn-risk decile.
- Randomization unit: customer_id.
- Control/treatment split: 20% control, 80% treatment.
- Duration: 8 weeks.
- Minimum detectable effect (MDE): 1.0 percentage point.
- Significance/confidence rules: 95% confidence with pre-registered analysis.
- Stop/go criteria: promote if churn reduction is significant and cost guardrails are within bounds.

## 10) Validation and Governance
- Offline validation tests: AUC/PR, calibration, stability by segment and time.
- Online validation tests: holdout lift, action policy compliance, score availability SLA.
- Promotion gates: metric thresholds passed, experiment readout approved, compliance check completed.
- Model registry/versioning: MLflow registry with versioned feature snapshot and code hash.
- Audit artifacts required: model card, feature lineage report, experimental analysis, approval ticket.

## 11) Monitoring
- Data drift checks: PSI by key features and drift alerts by segment.
- Performance drift checks: weekly calibration error and uplift decay tracking.
- Business KPI monitoring: churn rate, retained revenue, cost per save.
- Alert thresholds: calibration error > 0.05 or uplift drops below +0.3 points for 2 weeks.
- On-call owner: Marketing ML Ops rotation.

## 12) Delivery Plan
- Milestones: M1 labeled dataset, M2 baseline model, M3 action policy integration, M4 experiment run, M5 decision review.
- Target dates: 2026-05-11 to 2026-07-03.
- Risks: label delay, policy leakage, channel saturation.
- Mitigations: delayed-outcome evaluation windows, strict leakage tests, channel caps.

## 13) Acceptance Criteria
- Business acceptance criteria: significant churn reduction and retained revenue uplift.
- Technical acceptance criteria: >= 99.5% batch scoring success and full audit lineage.
- Sign-off approvers: Business owner, Data Science owner, Platform owner, Compliance.

