# Use Case Pack

This folder contains reusable business and technical definitions for the first four use cases:

1. `UC-NBA-RET-001` - Next Best Action for Retention
2. `UC-CHURN-RET-002` - Churn Prediction and Retention Actioning
3. `UC-MMM-PLN-003` - Media Mix Modeling and Budget Optimization
4. `UC-INCR-MKT-004` - Campaign Incrementality Measurement

Each use case is provided in two formats:

1. `charters/*.md` for business, science, and governance alignment
2. `configs/*.yaml` for code, orchestration, and automation inputs

Structure:

```text
use_cases/
  README.md
  template/
    use_case_charter_template.md
    use_case_contract_template.yaml
  charters/
    UC-NBA-RET-001.md
    UC-CHURN-RET-002.md
    UC-MMM-PLN-003.md
    UC-INCR-MKT-004.md
  configs/
    UC-NBA-RET-001.yaml
    UC-CHURN-RET-002.yaml
    UC-MMM-PLN-003.yaml
    UC-INCR-MKT-004.yaml
```
