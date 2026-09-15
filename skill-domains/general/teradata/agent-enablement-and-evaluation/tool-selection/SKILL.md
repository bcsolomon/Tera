---
name: teradata-skill-index
description: 'Navigator and routing table for all Teradata skills. Use this skill FIRST to determine which specific Teradata skill(s) to load for any given task. Maps topics, keywords, and common questions to the correct skill.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Skill Index

Use this index to find the right skill for any Teradata task. Load the matching skill's SKILL.md for detailed guidance.

## When to Use

- Use this skill FIRST when unsure which Teradata skill to load
- Routing any Teradata question to the correct skill
- Tasks that span multiple Teradata domains
- DO NOT use for direct task execution — load the specific skill instead

## Skill Routing Table

| If the task involves... | Load skill |
|---|---|
| SELECT, INSERT, UPDATE, DELETE, MERGE, QUALIFY, SAMPLE, TOP, CTEs, window functions, volatile tables, locking modifiers, SHOW/HELP | `teradata-sql-fundamentals` |
| CREATE/DROP TABLE DDL, SET vs MULTISET, primary index choice, ALTER TABLE | `teradata-sql-fundamentals` + `teradata-architecture` |
| UPI, NUPI, NoPI, data distribution, hash distribution, data skew, secondary indexes (USI/NUSI), join indexes, hash indexes | `teradata-architecture` |
| MPP architecture, AMPs, PEs, BYNET, nodes, cliques, FSG cache, cylinders, fallback, journaling, MAPS | `teradata-architecture` |
| Partitioned Primary Index (PPI), RANGE_N, CASE_N, multi-level PPI, column partitioning, sliding window | `teradata-partitioning` |
| COLLECT STATISTICS, HELP STATISTICS, histograms, stale stats, optimizer statistics | `teradata-statistics` |
| Data types, BYTEINT, INTEGER, DECIMAL, NUMBER, VARCHAR, CLOB, DATE, TIMESTAMP, PERIOD, JSON, XML, INTERVAL, geospatial | `teradata-data-types` |
| User-defined functions (UDF), C/C++ UDFs, Java UDFs, table functions, aggregate UDFs, sqltypes_td.h | `teradata-udf` |
| Stored procedures, SQL stored procedures, Java stored procedures, external stored procedures | `teradata-stored-procedures` |
| Native Object Store (NOS), READ_NOS, WRITE_NOS, foreign tables, S3/Azure/GCS access, AUTHORIZATION, semi-structured data | `teradata-native-object-store` |
| Script Table Operator (STO), analytic functions, nPath, ML functions, XGBoost, DecisionTree, KMeans, text analytics | `teradata-analytics` |
| Workload management, TASM, priority scheduling, throttles, system filters, exception handling, AWT management, DBQL monitoring | `teradata-workload-management` |
| GRANT, REVOKE, CREATE USER, roles, profiles, row-level security, access logging | `teradata-security` |
| Query banding, SET QUERY_BAND, proxy users, WLM classification by query band | `teradata-query-banding` |
| VantageCloud Lake, OFS, compute clusters, compute groups, elastic scaling, Flow Service | `teradata-vantagecloud-lake` |
| Space management, PERM/SPOOL/TEMP, DBS Control, sessions, EXPLAIN, monitoring, backup, ResUsage, system health | `teradata-system-admin` |
| IPE, DPE, adaptive optimizer, cost estimation feedback, plan reoptimization | `teradata-adaptive-optimizer` |
| Character sets, LATIN, UNICODE, locale, collation, NLS, encoding conversion, KANJISJIS | `teradata-internationalization` |
| NoPI tables, staging tables, Fastload with NoPI, ETL staging design | `teradata-nopi-tables` |
| Intelligent Memory, TIM, TVS, SSD tiering, hot/cold data, temperature-based caching | `teradata-intelligent-memory` |
| Load isolation, LOAD COMMITTED, concurrent loading and querying, isolated loading | `teradata-load-isolation` |
| Elastic scaling, COD, scale-up, scale-out, compute cluster auto-scaling, capacity on demand | `teradata-elasticity` |
| ML Engine, Graph Engine, FFE, in-database ML training/scoring, graph analytics, function aliases | `teradata-ml-graph-engines` |
| TCore, consumption pricing, capacity limiting, usage metering, Vantage Units | `teradata-capacity-consumption` |

## All Skills

| # | Skill | Key Topics | Depth |
|---|---|---|---|
| 1 | `teradata-sql-fundamentals` | DDL, DML, QUALIFY, SAMPLE, CTEs, window functions, locking | SKILL.md + 2 refs |
| 2 | `teradata-architecture` | MPP, PI/UPI/NUPI, secondary indexes, join indexes, MAPS, storage, cache | SKILL.md + 4 refs |
| 3 | `teradata-data-types` | Numeric, character, date/time, PERIOD, LOB, spatial, time series | SKILL.md + 7 refs |
| 4 | `teradata-partitioning` | PPI, RANGE_N, CASE_N, MLPPI, column partitioning, 8-byte | SKILL.md + 5 refs + template |
| 5 | `teradata-statistics` | COLLECT/SHOW/HELP STATISTICS, histograms, UDI, optimizer | SKILL.md + 3 refs |
| 6 | `teradata-udf` | C/C++/Java/Python UDFs, table/aggregate/scalar, FNC API | SKILL.md + 7 refs + 3 templates |
| 7 | `teradata-stored-procedures` | SQL/Java/external SPs, dynamic SQL, cursors, result sets | SKILL.md + 5 refs + 2 templates |
| 8 | `teradata-native-object-store` | NOS, READ_NOS, WRITE_NOS, foreign tables, auth, JSON/XML | SKILL.md + 5 refs + 2 templates |
| 9 | `teradata-analytics` | STO, 150+ analytic functions, ML train/predict, nPath | SKILL.md + 5 refs + 2 templates |
| 10 | `teradata-workload-management` | TASM, priorities, throttles, AWTs, exceptions, classification | SKILL.md + 9 refs |
| 11 | `teradata-security` | Users, roles, GRANT/REVOKE, RLS, LDAP/TDGSS, secure zones | SKILL.md + 2 refs |
| 12 | `teradata-query-banding` | SET QUERY_BAND, proxy users, WLM classification, client APIs | SKILL.md + 3 refs |
| 13 | `teradata-vantagecloud-lake` | OFS, compute clusters/groups, elastic scaling, cost | SKILL.md + 2 refs |
| 14 | `teradata-system-admin` | Space, DBS Control, EXPLAIN, monitoring, BLC, utilities | SKILL.md + 4 refs |
| 15 | `teradata-adaptive-optimizer` | IPE, DPE, plan reoptimization, cost feedback | SKILL.md + 2 refs |
| 16 | `teradata-internationalization` | Character sets, locale, collation, NLS, encoding | SKILL.md + 2 refs |
| 17 | `teradata-nopi-tables` | NoPI design, staging, Fastload optimization, ETL | SKILL.md + 1 ref |
| 18 | `teradata-intelligent-memory` | TIM, TVS, SSD tiering, temperature caching | SKILL.md + 2 refs |
| 19 | `teradata-load-isolation` | LOAD COMMITTED, concurrent load/query, row versioning | SKILL.md + 1 ref |
| 20 | `teradata-elasticity` | COD, scale-up/out, compute cluster scaling, capacity | SKILL.md + 1 ref |
| 21 | `teradata-ml-graph-engines` | ML Engine, Graph Engine, FFE, function aliases | SKILL.md + 2 refs |
| 22 | `teradata-capacity-consumption` | TCore, consumption pricing, usage metering | SKILL.md + 1 ref |

## Multi-Skill Tasks

Some tasks require loading multiple skills:

| Task | Skills to Load |
|---|---|
| Design a new table | `sql-fundamentals` + `architecture` + `partitioning` + `statistics` |
| Performance tuning | `architecture` + `statistics` + `system-admin` + `workload-management` + `adaptive-optimizer` |
| Set up NOS with analytics | `native-object-store` + `analytics` |
| Migrate to Lake | `vantagecloud-lake` + `architecture` + `elasticity` |
| Secure a new application | `security` + `query-banding` + `workload-management` |
| Build ETL pipeline | `nopi-tables` + `load-isolation` + `sql-fundamentals` + `partitioning` |
| In-database ML workflow | `ml-graph-engines` + `analytics` + `sql-fundamentals` |
| Capacity planning | `capacity-consumption` + `elasticity` + `workload-management` |
| Internationalization setup | `internationalization` + `data-types` + `sql-fundamentals` |
| Memory/storage optimization | `intelligent-memory` + `architecture` + `system-admin` |
