# Production Source Datasets

Place real CSV source tables in this directory when running with:

1. `--source-data-root data/production`
2. `--require-real-data`

Directory structure:

```text
data/production/
  UC-NBA-RET-001/
    crm_customers.csv
    behavior_signals.csv
    contact_history.csv
  UC-CHURN-RET-002/
    crm_customers.csv
    usage_signals.csv
    support_events.csv
  UC-MMM-PLN-003/
    media_spend.csv
  UC-INCR-MKT-004/
    campaign_experiments.csv
```

## Required Columns

### UC-NBA-RET-001

1. `crm_customers.csv`
   - `customer_id,consent_status,profile_completeness,no_critical_service_case,do_not_contact`
2. `behavior_signals.csv`
   - `customer_id,risk_score,value_score,score_ts`
   - Optional labels: `historical_action_id,observed_uplift,retained_30d`
3. `contact_history.csv`
   - `customer_id,last_marketing_contact_hours,contacts_last_7d`

### UC-CHURN-RET-002

1. `crm_customers.csv`
   - `customer_id,consent_status,profile_completeness,no_active_fraud_flag,active_retention_journey,last_marketing_contact_hours`
2. `usage_signals.csv`
   - `customer_id,recency_norm,engagement_norm,score_ts`
   - Optional label: `churned_60d`
3. `support_events.csv`
   - `customer_id,support_ticket_norm`

### UC-MMM-PLN-003

1. `media_spend.csv`
   - `period,channel,weekly_spend,impressions,clicks,promo_index`
   - Optional supervision: `observed_revenue,seasonality_index,macro_index`

### UC-INCR-MKT-004

1. `campaign_experiments.csv`
   - `campaign_id,test_window,treated_customers,control_customers,treated_conversions,control_conversions,aov,campaign_cost`
   - Optional covariates: `pre_period_conversion_rate,audience_tier`

## Runtime Behavior

1. If all required files exist for a use case, Stage 1 loads real datasets.
2. If files are missing:
   - Default mode: falls back to synthetic sources.
   - Strict mode (`--require-real-data`): run fails immediately.
