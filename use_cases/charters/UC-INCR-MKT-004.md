# Use Case Charter

## 1) Metadata
- Use case name: Campaign Incrementality Measurement
- Use case ID: UC-INCR-MKT-004
- Owner (business): Lifecycle Marketing Lead
- Owner (data science): Causal Inference Lead
- Owner (engineering): Experimentation Platform Lead
- Version: v0.1
- Status: Draft

## 2) Business Problem
- Problem statement: Existing attribution over-credits campaigns that would have converted anyway.
- Why now: Budget pressure requires evidence of true causal lift before scaling spend.
- Decision that this use case should improve: Whether to scale, pause, or redesign a campaign based on incremental impact.
- Current baseline process: Last-touch or heuristic attribution with limited holdouts.

## 3) Scope
- In-scope customers/channels/regions: US lifecycle campaigns and paid retargeting pilots.
- Out-of-scope: Global rollout and channels without controlled exposure logging.
- Assumptions: Randomization can be operationalized at customer or geo level.
- Dependencies: Experiment assignment service, clean exposure logs, conversion events.

## 4) Success Metrics
- Primary KPI: Incremental conversions per campaign.
- Secondary KPI(s): Incremental revenue, incremental ROAS, cost per incremental conversion.
- Guardrail KPI(s): Negative lift risk, cannibalization signals, customer experience impact.
- Baseline value: inferred lift from non-causal attribution only.
- Target value: decision-quality lift estimates with confidence intervals for at least 80% of pilot campaigns.
- Decision cadence: campaign-level readout weekly and end-of-test.

## 5) Data Requirements
- Entities needed: exposure, assignment, conversion, order, campaign metadata, suppression logs.
- Required fields: customer_id, campaign_id, assignment_group, exposure_ts, conversion_ts, order_value, channel, creative_id.
- Source systems: campaign orchestration platform, ad platform logs, transaction system, identity graph.
- Data freshness SLA: exposure and conversion logs <= 1 hour for active tests.
- Data quality thresholds: sample ratio mismatch checks pass, timestamp integrity pass, <= 0.5% unmatched IDs post-identity mapping.

## 6) Model/Analytics Output
- Output type: causal attribution and decision recommendation.
- Output schema: campaign_id, test_window, incremental_lift, ci_low, ci_high, p_value, iROAS, decision_recommendation, analysis_version.
- Explainability fields: segment-level lift decomposition and sensitivity diagnostics.
- Confidence/uncertainty required: 95% confidence interval and power report.
- Output refresh cadence: interim weekly reads and final post-test readout.
- Max serving latency: read API <= 2 seconds for standard report queries.

## 7) Decision Policy
- Business rules: scale only if lift is positive and significant with acceptable cost profile.
- Eligibility rules: campaigns must meet minimum sample size and experiment design criteria.
- Suppression rules: exclude campaigns with broken randomization or logging anomalies.
- Compliance/consent checks: assignment and exposure must respect privacy and channel consent policy.
- Fallback behavior if model unavailable: hold baseline spend and defer scaling decision.

## 8) Activation Plan
- Destination channels/tools: campaign decision dashboard and recommendation API for planners.
- Trigger conditions: test reaches minimum power or planned end date.
- Payload contract: campaign_id, recommendation, incremental_lift, confidence_interval, iROAS, approval_required.
- Frequency caps: weekly recommendation updates unless severe negative lift alert triggers immediate update.
- Rollback plan: freeze new scaling actions and revert to prior approved campaign settings.

## 9) Experimentation Plan
- Hypothesis: controlled campaign exposure produces measurable positive incremental lift.
- Experiment design: randomized holdout test at customer or geo cluster level with pre-registration.
- Randomization unit: customer_id (default) or geo_cluster_id (if channel constraints require).
- Control/treatment split: 20% control, 80% treatment unless power analysis dictates otherwise.
- Duration: 4 to 8 weeks depending on traffic.
- Minimum detectable effect (MDE): 5% relative conversion lift.
- Significance/confidence rules: 95% confidence and power >= 80%.
- Stop/go criteria: stop early for severe negative lift; promote only when significance and guardrails pass.

## 10) Validation and Governance
- Offline validation tests: randomization integrity, pre-period balance, leakage checks, placebo tests.
- Online validation tests: sample ratio mismatch, exposure logging completeness, conversion lag stability.
- Promotion gates: statistical quality checks passed and scientific review approved.
- Model registry/versioning: versioned causal analysis pipeline and assumptions package.
- Audit artifacts required: pre-analysis plan, balance report, final causal report, approval log.

## 11) Monitoring
- Data drift checks: traffic mix and audience composition shift across test/control.
- Performance drift checks: campaign lift trend and confidence interval widening alerts.
- Business KPI monitoring: iROAS, incremental conversions, incremental revenue.
- Alert thresholds: SRM detected, power below threshold near planned end, negative lift with high confidence.
- On-call owner: Experimentation and Causal Science Ops.

## 12) Delivery Plan
- Milestones: M1 experiment design library, M2 assignment and logging, M3 pilot campaigns, M4 weekly reads, M5 final recommendations.
- Target dates: 2026-05-25 to 2026-07-24.
- Risks: contamination between groups, delayed conversions, inconsistent exposure tracking.
- Mitigations: strict assignment enforcement, conversion lag models, platform-side logging contracts.

## 13) Acceptance Criteria
- Business acceptance criteria: at least one campaign scaled or paused based on validated incrementality.
- Technical acceptance criteria: experiment integrity checks pass and report API SLA met.
- Sign-off approvers: Marketing owner, Causal Science owner, Platform owner, Compliance.

