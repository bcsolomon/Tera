---
name: teradata-statistics
description: 'Collect, manage, and diagnose Teradata optimizer statistics including COLLECT STATISTICS (full/sampled/summary), multi-column statistics, expression statistics, histogram interpretation, HELP/SHOW STATISTICS, DROP STATISTICS, threshold-based recollection, stale statistics detection, DBC.StatsV/TableStatsV views, DIAGNOSTIC HELPSTATS, and statistics feedback (IPE/Adaptive Optimizer). Use when collecting stats, diagnosing query plan issues, checking stale statistics, or setting up automated statistics management.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Statistics

## When to Use

- Collecting statistics on tables/columns for optimizer accuracy
- Diagnosing poor query plans (missing or stale statistics)
- Setting up threshold-based recollection strategies
- Using sampled statistics for large tables
- Collecting expression statistics for complex predicates
- Interpreting histogram output from SHOW STATISTICS
- Automating statistics management

## COLLECT STATISTICS — Syntax

```sql
COLLECT [SUMMARY] STATISTICS
    [USING options]
    COLUMN expr [[AS] stats_name]
    [, COLUMN (expr [, expr]) [[AS] stats_name]]
    ON [TEMPORARY] table_name;
```

### USING Options

| Option | Description |
|---|---|
| `SAMPLE` | System-determined sample percentage |
| `SYSTEM SAMPLE` | Same as SAMPLE |
| `SAMPLE n PERCENT` | User-specified sample (2–100%) |
| `MAXINTERVALS n` | Histogram intervals (0–500, default 250) |
| `MAXVALUELENGTH n` | Max value length stored (default 25 bytes) |
| `THRESHOLD n PERCENT` | Skip if data changed < n% |
| `THRESHOLD n DAYS` | Skip if collected < n days ago |
| `SYSTEM THRESHOLD` | System-determined threshold |
| `NO THRESHOLD` | Always recollect |

Combine with `AND`: `USING SAMPLE AND THRESHOLD 10 PERCENT`

## Procedure: Collect Statistics

### Essential Statistics for Any Table

```sql
-- 1. Single columns used in WHERE, JOIN, GROUP BY
COLLECT STATISTICS COLUMN customer_id ON mydb.orders;
COLLECT STATISTICS COLUMN order_date ON mydb.orders;

-- 2. PARTITION column (critical for partitioned tables)
COLLECT STATISTICS COLUMN PARTITION ON mydb.orders;

-- 3. Primary index columns
COLLECT STATISTICS COLUMN (customer_id, order_date) ON mydb.orders;

-- 4. Summary statistics (fast, provides row count)
COLLECT SUMMARY STATISTICS ON mydb.orders;
```

### Multiple Statistics in One Statement (Recommended)

```sql
COLLECT STATISTICS
    COLUMN (order_date, customer_id)
   ,COLUMN order_date
   ,COLUMN customer_id
   ,COLUMN PARTITION
    ON mydb.orders;
-- Single table scan → rollup aggregations for efficiency
```

### Sampled Statistics (Large Tables)

```sql
-- System-determined sampling (recommended)
COLLECT STATISTICS USING SAMPLE COLUMN order_date ON mydb.orders;

-- Explicit percentage
COLLECT STATISTICS USING SAMPLE 20 PERCENT COLUMN order_date ON mydb.orders;
```

### Expression Statistics (14.10+)

```sql
-- Functions on columns
COLLECT STATISTICS COLUMN EXTRACT(MONTH FROM order_date) AS order_month
    ON mydb.orders;

-- Computed expressions
COLLECT STATISTICS COLUMN (price * quantity) AS line_total
    ON mydb.order_lines;

-- CASE expressions
COLLECT STATISTICS COLUMN CASE WHEN status IN ('A','B') THEN 'Active'
                               ELSE 'Inactive' END AS status_group
    ON mydb.accounts;
```

### Recollect with Thresholds

```sql
-- System-determined (recommended)
COLLECT STATISTICS USING SYSTEM THRESHOLD COLUMN order_date ON mydb.orders;

-- Skip if <10% change AND <15 days old
COLLECT STATISTICS USING THRESHOLD 10 PERCENT AND THRESHOLD 15 DAYS
    COLUMN order_date ON mydb.orders;

-- Always recollect (no skip)
COLLECT STATISTICS USING NO THRESHOLD ON mydb.orders;

-- Recollect ALL statistics on a table (uses saved options)
COLLECT STATISTICS ON mydb.orders;
```

## Procedure: Inspect Statistics

### HELP STATISTICS

```sql
HELP STATISTICS ON mydb.orders;
-- Output: Date, Time, Unique Values, Column Names

HELP CURRENT STATISTICS ON mydb.orders;
-- Shows extrapolated current values (row count, unique values)
```

### SHOW STATISTICS

```sql
-- DDL form (resubmittable SQL)
SHOW STATISTICS ON mydb.orders;

-- Detailed histogram values
SHOW STATISTICS VALUES COLUMN order_date ON mydb.orders;

-- Extrapolated current values
SHOW CURRENT STATISTICS VALUES COLUMN order_date ON mydb.orders;
```

### Key Histogram Fields

| Field | Meaning |
|---|---|
| `NumOfRows` | Row count at collection time |
| `NumOfDistinctVals` | Unique values |
| `NumOfNulls` | NULL count |
| `MinVal` / `MaxVal` | Value range |
| `ModeVal` / `HighModeFreq` | Most frequent value and its count |
| `SamplePercent` | Sample % used (100 = full) |
| `StatsSkipCount` | Times recollection was skipped |

## DROP STATISTICS

```sql
-- Drop specific column stats
DROP STATISTICS COLUMN customer_id ON mydb.orders;

-- Drop by name
DROP STATISTICS COLUMN order_month ON mydb.orders;

-- Drop ALL stats (including SUMMARY)
DROP STATISTICS ON mydb.orders;
```

**Warning:** Don't drop and recollect — you lose history records needed for trend-based extrapolation. Use recollect instead.

## Stale Statistics Detection

### Symptoms

- Unexpected full-table scans
- Wrong join strategies (product join instead of merge/hash)
- Excessive spool usage
- Plans that worked well before suddenly slow

### Diagnosis

```sql
-- Check last collection date and skip count
SELECT DatabaseName, TableName, ColumnName,
       CAST(LastCollectTimeStamp AS DATE) AS collected_date,
       StatsSkipCount
FROM DBC.TableStatsV
WHERE DatabaseName = 'mydb'
ORDER BY collected_date;

-- Get optimizer's missing stats recommendations
DIAGNOSTIC HELPSTATS ON FOR SESSION;
-- Then run the query — recommendations appear in output
```

### DBQL Statistics Usage Logging

```sql
-- Enable stats usage logging
BEGIN QUERY LOGGING WITH STATSUSAGE ON mydb;

-- Check logged stats usage (XML format in DBQLXMLTbl)
SELECT QueryID, XMLTextInfo
FROM DBC.DBQLXMLTbl
WHERE XMLType = 'StatsUsage';
```

## When to Collect

| Situation | Action |
|---|---|
| New table with data | Collect on PI, WHERE, JOIN, GROUP BY columns |
| Partitioned table | Always collect on PARTITION column |
| After large data load | COLLECT SUMMARY + key column stats |
| After partition sliding window | Drop stats on PARTITION, recollect |
| Missing stats in EXPLAIN | Use DIAGNOSTIC HELPSTATS |
| After schema changes | Recollect affected statistics |

## When NOT to Collect

- Columns never used in predicates, joins, or grouping
- Very small tables (<100 rows) — optimizer estimates are adequate
- Don't over-collect — unnecessary stats consume cache and maintenance time

## Optimizer Impact

| Stats Available | Optimizer Behavior |
|---|---|
| Full stats (high confidence) | Uses histogram for accurate estimates |
| Partial stats | Extrapolates from available info |
| No stats | Default selectivity: 10% equality, 20% range |
| Stale stats | Trend-based or heuristic extrapolation |

## Catalog Views

| View | Content |
|---|---|
| `DBC.StatsV` | StatsId, ValidStats, StatsName |
| `DBC.TableStatsV` | Per-table stats with collection timestamps |
| `DBC.ColumnStatsV` | Column-level statistics summary |
| `DBC.MultiColumnStatsV` | Multi-column stats |
| `DBC.StatUseCountV` | Access counts for used statistics |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-statistics", path="references/FILENAME")` — do NOT call `list`.

- [Statistics Collection Deep Dive](./references/statistics-collection.md) — Full USING options (SAMPLE/MAXINTERVALS/MAXVALUELENGTH/THRESHOLD), collection performance optimizations (rollup, pre-aggregation, cost-based paths), SUMMARY stats, named stats, expression stats rules, copy/transfer stats, privileges, cache config, statistics versions
- [Histogram & Extrapolation](./references/histogram-and-extrapolation.md) — SHOW STATISTICS VALUES output structure, equal-height histogram fields, RPV calculations, selectivity estimation, stale stats extrapolation (rolling/static), trend-based extrapolation, UDI counts, PARTITION stats details, statistics recommendations (STATSUSAGE/USECOUNT), threshold tracking, system sample downgrade, IPE feedback
- [UDI Counts & Advanced Optimization](./references/udi-and-optimization.md) — Enable/disable UDI logging (BEGIN QUERY LOGGING WITH USECOUNT), OUC cache mechanics, UDI vs sampling row count estimation, staleness detection improvements, THRESHOLD skip decision algorithm, EXPLAIN indicators for skip/collect, FOR CURRENT override, identifying used/unused/missing statistics
