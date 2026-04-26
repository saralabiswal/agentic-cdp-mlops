# Use Case Charter

## 1) Metadata
- Use case name: Next Best Action for Retention
- Use case ID: UC-NBA-RET-001
- Owner (business): CRM and Retention Lead
- Owner (data science): Marketing Science Lead
- Owner (engineering): CDP Platform Lead
- Version: v0.1
- Status: Draft

## 2) Business Problem
- Problem statement: Retention campaigns are rule-based and generic, which causes low lift and customer fatigue.
- Why now: Rising acquisition cost makes retained revenue and repeat usage more valuable.
- Decision that this use case should improve: Which action should be delivered to each at-risk customer at decision time.
- Current baseline process: Weekly static segments with fixed offers and no personalized action ranking.

## 3) Scope
- In-scope customers/channels/regions: US B2C customers; Email, Push, and Paid Retargeting.
- Out-of-scope: Call center scripts, in-store intervention, non-US rollout.
- Assumptions: Consent and channel permissions are available and trusted in source systems.
- Dependencies: Customer 360 profile, feature store, activation connectors.

## 4) Success Metrics
- Primary KPI: 30-day incremental retention lift vs control.
- Secondary KPI(s): Incremental revenue per targeted customer, offer acceptance rate.
- Guardrail KPI(s): Unsubscribe rate, complaint rate, contact fatigue index.
- Baseline value: 68.0% 30-day retention.
- Target value: +2.5 percentage points incremental lift.
- Decision cadence: Daily batch with event-triggered rescoring.

## 5) Data Requirements
- Entities needed: customer, event, campaign, transaction, consent.
- Required fields: customer_id, event_ts, channel, campaign_id, conversion_flag, order_value, consent_status, recency, frequency, tenure.
- Source systems: CRM, web/app events, messaging platform, order system.
- Data freshness SLA: events <= 15 minutes, CRM snapshot <= 24 hours.
- Data quality thresholds: >= 99% non-null customer_id, <= 1% schema violations, <= 0.5% duplicate event_id.

## 6) Model/Analytics Output
- Output type: recommendation.
- Output schema: customer_id, action_id, action_channel, expected_uplift, confidence, reason_codes, score_ts, model_version, policy_version.
- Explainability fields: top_3_drivers, risk_band, eligibility_flags.
- Confidence/uncertainty required: uplift confidence interval and calibrated probability.
- Output refresh cadence: nightly full scoring and near-real-time updates on high-signal events.
- Max serving latency: <= 200 ms p95 for online API.

## 7) Decision Policy
- Business rules: choose highest expected uplift action from eligible action catalog.
- Eligibility rules: active consent, minimum profile completeness, no unresolved critical service case.
- Suppression rules: contacted in last 72 hours, more than 4 marketing contacts in 7 days, do-not-contact flag.
- Compliance/consent checks: enforce channel-level consent at decision time.
- Fallback behavior if model unavailable: deterministic rules engine with conservative offer strategy.

## 8) Activation Plan
- Destination channels/tools: webhook adapter and campaign tools (Oracle/Salesforce adapters later).
- Trigger conditions: high-risk event or scheduled daily decision run.
- Payload contract: customer_id, action_id, channel, priority, expiry_ts, reason_code.
- Frequency caps: max 1 NBA action per day and max 4 per week per customer.
- Rollback plan: feature flag to disable model output and revert to rule-based path.

## 9) Experimentation Plan
- Hypothesis: NBA decisioning improves 30-day retention by at least 2.5 percentage points vs BAU.
- Experiment design: stratified randomized controlled trial by risk decile and value tier.
- Randomization unit: customer_id.
- Control/treatment split: 20% control, 80% treatment.
- Duration: 6 weeks.
- Minimum detectable effect (MDE): 1.5 percentage points.
- Significance/confidence rules: 95% confidence, two-sided testing.
- Stop/go criteria: promote only if primary KPI improves and guardrails stay within thresholds.

## 10) Validation and Governance
- Offline validation tests: uplift ranking quality, calibration, stability by segment.
- Online validation tests: holdout lift, policy compliance, payload contract pass rate.
- Promotion gates: all tests pass, KPI threshold met, governance approval recorded.
- Model registry/versioning: MLflow model registry with immutable data/model/version tags.
- Audit artifacts required: model card, training data snapshot ID, experiment report, approval log.

## 11) Monitoring
- Data drift checks: PSI and KS checks on top features.
- Performance drift checks: weekly uplift and calibration drift trend.
- Business KPI monitoring: retention lift, incremental revenue, unsubscribe and complaint trends.
- Alert thresholds: uplift below +0.5 points for 2 weeks, unsubscribe above baseline by 15%.
- On-call owner: Marketing ML Ops rotation.

## 12) Delivery Plan
- Milestones: M1 data contracts, M2 baseline model, M3 decision API, M4 experiment launch, M5 readout.
- Target dates: 2026-05-04 to 2026-06-19.
- Risks: sparse labels, channel delivery lag, consent mismatches.
- Mitigations: proxy labels, delayed-outcome handling, strict consent pre-checks.

## 13) Acceptance Criteria
- Business acceptance criteria: statistically significant lift with no guardrail breach.
- Technical acceptance criteria: p95 latency <= 200 ms, >= 99.5% scoring success, full lineage and audit completeness.
- Sign-off approvers: Business owner, Data Science owner, Platform owner, Compliance.

