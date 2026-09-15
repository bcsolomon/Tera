---
name: slow-query-analysis
description: 'Diagnose and tune slow Teradata Vantage queries or pipeline bottlenecks. Use when a query is running slow, missing SLAs, high spool, high skew, full table scans, product joins, stale statistics, workload contention, NOS/OTF latency, or DBQL analysis is needed. Operates in two phases: Diagnose (read-only DBQL analysis) then Tune (corrective actions with user confirmation). For explain plan interpretation and optimizer behavior, see explain-interpretation.'
argument-hint: "Paste the slow SQL, provide a DBQL QueryID, or describe the performance issue"
metadata:
  author: teradata
  version: "1.0"
  license: Proprietary
  copyright: "© 2026 Teradata Corporation. All rights reserved."
---

> **Tool Usage:**
> - Use `base_readQuery` (teradata-base group) for all Phase 1 diagnostic SELECT queries: DBQL lookups, step decomposition, statistics checks, NOS metrics, and all other read-only data retrieval
> - Use `execute_sql` (teradata-sql-query-executor group) for EXPLAIN statements and all Phase 2 tuning actions: COLLECT STATISTICS, CREATE INDEX, ALTER TABLE, SET QUERY_BAND, REPLACE QUERY LOGGING
> - Other useful teradata-base tools: `base_tableDDL`, `base_tableList`, `base_databaseList`, `base_columnDescription`, `base_tablePreview`, `base_tableAffinity`, `base_tableUsage`, `base_db_info`
>
> **Tool Discovery & Management:**
> - `teradata_tool_help` — Get general help and orientation on available tools
> - `teradata_list_patterns` — List available tool groups/patterns
> - `teradata_search_tools` — Search and discover tools by pattern
> - `teradata_get_tool_schema` — Get the full parameter schema for a specific tool
> - `teradata_tool_call` — Execute a native Teradata tool directly
> - `teradata_cleanup_jobs` — Clean up long-running jobs

# Slow Query Analysis

Diagnose why a Teradata Vantage query or pipeline is slow, then apply targeted tuning to reduce runtime and free resources. Operates in two phases: **Diagnose** (read-only) then **Tune** (corrective actions with user confirmation).

## When to Use

- A query is running slow or missing SLAs
- Pipeline jobs are taking longer than expected
- High spool usage, high skew, or full table scans appear in explain plans
- Need to validate whether statistics are current
- Need to analyze DBQL query logs for bottleneck identification
- NOS/OTF external data queries have high I/O wait times
- Workload contention or priority demotion is suspected

> **Not this skill:** For interpreting EXPLAIN output, understanding optimizer plan choices, IPE (Incremental Planning & Execution), or Dynamic Partition Elimination behavior, see **explain-interpretation** in `query-optimization-and-performance/explain-interpretation/`.

## Prerequisites

- Connection to Teradata Vantage (via MCP server or teradataml)
- DBQL logging should be enabled for the target user. If not, this skill will detect it and provide the enable statement
- For Phase 2 tuning: appropriate DDL privileges on target objects

## Phase 1: Diagnose (Read-Only)

All steps in this phase are read-only queries against DBQL and system views. No database objects are modified.

### Step 1: Verify DBQL Logging

Check that query logging is active with the required options.

```sql
SELECT * FROM DBC.DBQLRulesV;
```

If logging is not enabled or flags are 'F' for the target user, recommend:

```sql
REPLACE QUERY LOGGING WITH EXPLAIN, OBJECTS, STEPINFO, SQL ON {username};
FLUSH QUERY LOGGING WITH ALL;
```

### Step 2: Identify the Slow Query

Locate the query in DBQL. Use one of these approaches based on what the user provides:

**By QueryID** (if known):
```sql
SELECT SessionId, QueryID, StartTime, QueryText,
  NumSteps, AmpCPUTime, TotalIOCount, SpoolUsage,
  CAST((FirstRespTime - StartTime SECOND(4)) AS DECIMAL(8,2)) AS ElapsedSecs
FROM DBC.DBQLogTbl
WHERE QueryID = {query_id};
```

**By SessionID** (pipeline diagnosis — find slowest queries):
```sql
SELECT QueryID, StartTime, QueryText, NumSteps, AmpCPUTime, TotalIOCount,
  CAST((FirstRespTime - StartTime SECOND(4)) AS DECIMAL(8,2)) AS ElapsedSecs
FROM DBC.QryLog
WHERE SessionId = {session_id}
ORDER BY ElapsedSecs DESC;
```

**By QueryBand** (isolate an application or pipeline):
```sql
SELECT SessionId, QueryID, StartTime, QueryText,
  CAST((FirstRespTime - StartTime SECOND(4)) AS DECIMAL(8,2)) AS ElapsedSecs
FROM DBC.QryLog
WHERE QueryBand LIKE '%{band_value}%'
  AND StartTime >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
ORDER BY ElapsedSecs DESC;
```

### Step 3: Query-Level Profile

Extract the top-level performance metrics for the target query.

```sql
SELECT QueryID, NumSteps,
  AmpCPUTime,
  TotalIOCount,
  SpoolUsage,
  CAST((FirstRespTime - StartTime SECOND(4)) AS DECIMAL(8,2)) AS ElapsedSecs
FROM DBC.DBQLogTbl
WHERE QueryID = {query_id};
```

Report: elapsed time, CPU, I/O count, spool usage, step count.

### Step 4: Step-Level Decomposition and Skew Analysis

Join DBQLogTbl with DBQLStepTbl to break the query into execution steps. Compute derived metrics for each step.

```sql
SELECT
  qls.StepLev1Num + .1 * qls.StepLev2Num AS StepNum,
  qls.StepName,
  -- Duration
  CAST((qls.StepStopTime - qls.StepStartTime SECOND(4)) AS DECIMAL(8,2)) AS StepSecs,
  -- CPU: estimated vs actual
  CAST(qls.EstCPUCost AS DECIMAL(38,1)) AS EstCPU,
  CAST(qls.CPUTime AS DECIMAL(38,1)) AS ActCPU,
  -- I/O: estimated vs actual
  ZEROIFNULL(qls.EstIOCost) AS EstIO,
  qls.IOCount AS ActIO,
  -- Spool
  qls.SpoolUsage / 1000000 AS StepSpoolMB,
  qls.MaxAmpSpool * qls.NumOfActiveAmps / 1000000 AS ImpactSpoolMB,
  -- Row estimate accuracy (values far from 1.0 = stale statistics)
  qls.EstRowCount,
  qls.RowCount AS ActRowCount,
  qls.RowCount / NULLIFZERO(qls.EstRowCount) AS RowAccuracy,
  -- Parallel efficiency
  ZEROIFNULL(qls.CPUTime / NULLIFZERO(qls.NumOfActiveAmps * qls.MaxAmpCpuTime)) AS ParallelEff,
  -- PJI ratio (CPU per I/O — high = CPU-bound)
  CAST(qls.CPUTime * 1000.0 / NULLIFZERO(qls.IOCount) AS DECIMAL(38,1)) AS PJI,
  -- Skew percentages
  (1 - qls.CPUTime / NULLIFZERO(qls.NumOfActiveAmps * qls.MaxAmpCpuTime)) * 100 AS CPUSkewPct,
  (1 - qls.IOCount / NULLIFZERO(qls.NumOfActiveAmps * qls.MaxAmpIO)) * 100 AS IOSkewPct,
  (1 - qls.SpoolUsage / NULLIFZERO(qls.NumOfActiveAmps * qls.MaxAmpSpool)) * 100 AS SpoolSkewPct
FROM DBC.DBQLogTbl ql
JOIN DBC.DBQLStepTbl qls
  ON ql.QueryID = qls.QueryID AND ql.ProcID = qls.ProcID
WHERE ql.QueryID = {query_id}
ORDER BY StepNum;
```

**Flag these conditions:**
- CPU skew > 20% → data distribution problem or single-AMP operation
- I/O skew > 20% → uneven data placement across AMPs
- Spool skew > 20% → skewed intermediate results
- RowAccuracy < 0.1 or > 10.0 → missing or stale statistics
- ParallelEff < 0.5 → poor parallelism, possible single-AMP step

### Step 5: Retrieve Explain Plan

Get the optimizer's execution plan for the query.

**Historical (from DBQL):**
```sql
SELECT ExplainText
FROM DBC.DBQLExplainTbl
WHERE QueryID = {query_id};
```

**Prospective (for live SQL without executing):**
```sql
EXPLAIN {sql_text};
```

**Parse the explain text for these red flags:**
- "all-AMPs RETRIEVE" + "by way of an all-rows scan" → full table scan (FTS)
- "product join" → missing join condition or missing statistics
- "confidence level is low" → optimizer lacks statistics
- "no partition elimination" or "all partitions" → PPI not leveraged
- Large spool estimates → candidate for join index or restructuring

### Step 6: Retrieve Full SQL Text

If the query text was truncated in DBQLogTbl (>200 chars):

```sql
SELECT SQLTextInfo
FROM DBC.DBQLSQLTbl
WHERE QueryID = {query_id}
ORDER BY SqlRowNo;
```

### Step 7: Check Referenced Objects

Identify all tables/views accessed by the query:

```sql
SELECT ObjectDatabaseName, ObjectTableName, ObjectType, FreqOfUse
FROM DBC.DBQLObjTbl
WHERE QueryID = {query_id};
```

### Step 8: Statistics Assessment

For each table identified in Step 7, check collected statistics:

```sql
HELP STATISTICS {database_name}.{table_name};
```

Cross-reference with the query predicates (WHERE, JOIN, GROUP BY, ORDER BY columns). Identify:
- Columns in predicates with **no** collected statistics
- Statistics with old collection dates (stale)
- Missing multicolumn statistics for composite predicates

### Step 9: NOS/OTF Diagnosis (if applicable)

If the query accesses external object store data, extract OTF-specific metrics:

```sql
SELECT
  NosFiles, NosFilesSkipped,
  NosRecordsReturned, NosRecordsSkipped,
  NosRecordsReturnedKB, NosPhysReadIOKB,
  NosMaxIOWaitTime, NosTotalIOWaitTime,
  NosCPUTime, NosTables
FROM DBC.DBQLogTbl
WHERE QueryID = {query_id};
```

**Interpret:**
- High NosFilesSkipped / NosFiles ratio → poor external data partitioning
- High NosRecordsSkipped / NosRecordsReturned → filter should be pushed closer to source
- NosMaxIOWaitTime dominates ElapsedSecs → bottleneck is object store latency, not Vantage

### Step 10: Compile Diagnosis Summary

Present findings as a structured report:
1. **Query profile**: elapsed, CPU, I/O, spool, steps
2. **Bottleneck steps**: steps with highest elapsed time, skew, or poor row accuracy
3. **Root cause(s)**: missing statistics, FTS, product join, skew, OTF latency, contention
4. **Tuning recommendations**: prioritized list (proceed to Phase 2)

---

## Phase 2: Tune (Corrective Actions)

Each action below requires user confirmation before execution. Present the SQL, explain the expected impact, and wait for approval.

### Step 11: Collect Missing Statistics

For each column/expression identified as missing or stale in Step 8:

```sql
COLLECT STATISTICS COLUMN ({column_name}) ON {database}.{table_name};
```

For expression statistics (computed predicates):
```sql
COLLECT STATISTICS USING SAMPLE ON (expression) FROM {database}.{table_name};
```

For multicolumn statistics:
```sql
COLLECT STATISTICS COLUMN ({col1}, {col2}) ON {database}.{table_name};
```

**Expected impact:** Improved optimizer estimates → better join order, access path, and parallelism. Row accuracy (Step 4) should move closer to 1.0.

**Reference:** [Statistics Enhancements](./references/statistics.md)

### Step 12: Create or Modify Indexes

**NUSI** — when a non-PI column is frequently used in WHERE clauses on large tables:
```sql
CREATE INDEX ({column_name}) ON {database}.{table_name};
```

**AJI** — when repeated aggregation queries hit the same large table:
```sql
CREATE JOIN INDEX {index_name} AS
  SELECT {group_cols}, SUM({measure}) AS {alias}
  FROM {database}.{table_name}
  GROUP BY {group_cols};
```

Before creating: estimate maintenance cost (insert/update overhead) vs. query frequency.

**PPI** — when range or time-based filters are common. Verify partition elimination in EXPLAIN after creation:
```sql
-- Verify PPI is being used
EXPLAIN SELECT ... FROM {table} WHERE {partition_column} BETWEEN ... AND ...;
-- Look for "elimination" in the plan text
```

**Reference:** [PPI Strategy](./references/ppi-strategy.md)

### Step 13: Evaluate Columnar Partitioning

For wide tables where queries access a small column subset (< 20% of columns):

Assess whether column partitioning would reduce I/O. Compare current row-format I/O with projected columnar I/O based on the columns actually referenced.

**Reference:** [Columnar Design](./references/columnar.md)

### Step 14: Apply Compression

For I/O-bound queries on large, infrequently updated tables:

**Block-level compression:**
```sql
ALTER TABLE {database}.{table_name} WITH CONCURRENT BLOCKCOMPRESSION=ALWAYS;
```

**Temperature-based compression** (hot partitions uncompressed, cold compressed):
Evaluate based on access patterns from DBQL — partitions not queried in 30+ days are candidates.

**Reference:** [Compression Strategy](./references/compression.md)

### Step 15: Workload Management Adjustments

When diagnosis reveals resource contention, throttle delays, or priority demotions:

- Tag the pipeline with a QueryBand for consistent classification:
```sql
SET QUERY_BAND = 'ApplicationName={app};Pipeline={name};Priority=HIGH;' UPDATE FOR SESSION;
```

- Recommend WLM rule changes (via Viewpoint or TASM portlet):
  - Reclassify to higher-priority workload group
  - Adjust throttle concurrency limits
  - Set or modify hard limits on runaway queries

**Reference:** [Workload Management](./references/workload-management.md)

### Step 16: Verify Tuning Results

After applying any tuning action, verify improvement:

1. Re-run EXPLAIN on the same SQL — compare plan changes:
   - FTS eliminated?
   - Product join resolved?
   - Partition elimination now applied?
   - Confidence level improved?

2. If safe, re-execute the query and compare DBQL metrics:
   - Elapsed time reduction
   - CPU and I/O reduction
   - Spool usage reduction
   - Skew improvement
   - Row estimate accuracy improvement

3. Report before/after comparison to the user.

---

## References


> **Access:** `skill_resource_read(action="read", skill="slow-query-analysis", path="references/FILENAME")` — do NOT call `list`.

These reference files provide detailed guidance for each tuning category:

- [Statistics Enhancements](./references/statistics.md) — Expression stats, stale stats extrapolation, recollection optimization (source: 541-0010042)
- [Adaptive Optimizer / IPE](./references/adaptive-optimizer.md) — Incremental Planning & Execution, results feedback, join elimination (source: TDN0009599)
- [PPI Strategy](./references/ppi-strategy.md) — Partition elimination, DML optimization, multilevel partitioning (source: 541-0003869)
- [Columnar Design](./references/columnar.md) — Column partitioning, autocompression, I/O reduction (source: 541-0009036, TDN0009884)
- [Compression Strategy](./references/compression.md) — Block-level, temperature-based, multi-value compression (source: TDN0001167)
- [Workload Management](./references/workload-management.md) — Priority, throttles, hard limits, classification (source: WLM_Analytics_OB, TDN0001728, TDN0001776)
- [Query Banding](./references/query-banding.md) — Resource accounting, prioritization, pipeline tagging (source: 541-0007069)
- [Intelligent Memory](./references/intelligent-memory.md) — Hot data management, temperature reporting (source: 541-0009920)

### Related Skills

- [Explain Interpretation](../explain-interpretation/SKILL.md) — EXPLAIN output parsing, optimizer plan choices, IPE behavior, Dynamic Partition Elimination

## Reference Implementation

**Notebook:** `Vantage_Query_Log_Analysis/Vantage_Query_Log_Analysis_SQL.ipynb`
Demonstrates DBQL logging setup, session discovery, query profiling, step decomposition with skew/PE/PJI metrics, NOS metrics, explain plan retrieval, and SQL text lookup.
