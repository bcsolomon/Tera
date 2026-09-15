# Skill Routing — Role × Goal Index

Use this file after the survey completes to identify the primary skills and lead SME for the user's role and goal combination. For per-prompt routing on follow-on questions, rely on the skill system's own description-based discovery — each domain skill's description is its routing signal.

Goal labels match the survey option text exactly (from the Welcome and Survey procedure in SKILL.md).

---

## Layer 1: Role × Goal → Primary Skills

Skill names below are the frontmatter `name:` values, not directory slugs.

| Role | Goal | Primary Skills | Secondary Skills |
|------|------|----------------|-----------------|
| Data Analyst | Explore data and create reports | `teradata-sql-fundamentals` | `teradata-adaptive-optimizer` · `teradata-data-types` |
| Data Analyst | Solve a specific business problem | `teradata-sql-fundamentals` | `teradata-data-types` · `teradata-adaptive-optimizer` |
| Business Analyst | Explore data and create reports | `teradata-sql-fundamentals` | `teradata-data-types` |
| Business Analyst | Solve a specific business problem | `teradata-sql-fundamentals` | `teradata-data-types` |
| Data Engineer | Build data pipelines or ETL processes | `teradata-native-object-store` · `teradata-load-isolation` | `teradata-sql-fundamentals` · `teradata-statistics` |
| Data Engineer | Optimize query performance | `teradata-adaptive-optimizer` | `teradata-statistics` · `teradata-partitioning` · `teradata-system-admin` |
| Data Engineer | Secure and govern data | `teradata-security` | `teradata-sql-fundamentals` |
| Data Engineer | Monitor and fix pipelines | `teradata-system-admin` | `teradata-internationalization` · `teradata-elasticity` |
| Data Scientist | Deploy models or analytics | `teradata-analytics` | `teradata-ml-graph-engines` · `teradata-byom` |
| Data Scientist | Explore data and create reports | `teradata-analytics` | `teradata-sql-fundamentals` · `teradata-native-object-store` |
| Data Scientist | Build data pipelines or ETL processes | `teradata-analytics` · `teradata-data-preparation` | `teradata-sql-fundamentals` · `teradata-ml-graph-engines` |
| DBA / Administrator | Optimize query performance | `teradata-adaptive-optimizer` · `teradata-system-admin` | `teradata-statistics` · `teradata-partitioning` · `teradata-intelligent-memory` |
| DBA / Administrator | Monitor and fix pipelines | `teradata-system-admin` | `teradata-elasticity` · `teradata-workload-management` |
| DBA / Administrator | Solve a specific business problem | `teradata-workload-management` | `teradata-elasticity` · `teradata-capacity-consumption` |
| DBA / Administrator | Secure and govern data | `teradata-security` | `teradata-sql-fundamentals` |
| Developer | Learn the platform | `teradata-sql-fundamentals` · `teradata-architecture` | `teradata-data-types` · `teradata-internationalization` |
| Developer | Solve a specific business problem | `teradata-sql-fundamentals` | `teradata-stored-procedures` · `teradata-sql-udf` · `teradata-load-isolation` |
| Any | Secure and govern data (or PII mentioned) | `teradata-security` | — |
| Skip / Other | — | `teradata-sql-fundamentals` | `teradata-adaptive-optimizer` · `teradata-system-admin` |

---

## SME Routing Map

| Condition | Recommended SME |
|-----------|----------------|
| Data Analyst · Business Analyst · Developer + SQL or reporting | QueryBot |
| Data Engineer + pipelines · ETL · loading · CDC | PipelineBot |
| Data Scientist + ML · models · analytics · scoring | AnalyticsBot |
| Any role + schema design · table structure · PRIMARY INDEX | ModelBot |
| DBA / Admin + system health · workload · cost · TASM | OpsBot |
| DBA / Admin + optimize performance | QueryBot (query analysis) + OpsBot (workload context) |
| Any role + PII · security · access control · compliance | GuardBot (always takes priority) |
