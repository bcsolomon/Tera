# Statistics & Optimizer Internals

## Why Statistics Matter for Performance

The Teradata optimizer uses statistics (histograms) to estimate row counts at each step of a plan. Without statistics, it uses heuristics (dynamic AMP sampling or defaults) that are often wildly wrong — causing product joins, wrong join orders, unnecessary full-table scans, and excessive spool consumption.

---

## COLLECT STATISTICS — Essential Patterns

### Which Columns Need Statistics

| Priority | Column Type | Why |
|---|---|---|
| **Critical** | Primary Index columns | Join row estimation, redistribution decisions |
| **Critical** | Partitioning columns + PARTITION pseudo-column | Partition elimination costing |
| **Critical** | Foreign key / join columns | Join strategy selection |
| **High** | WHERE clause filter columns | Selectivity estimation |
| **High** | GROUP BY columns | Aggregation spool estimation |
| **Medium** | NUSI columns | Decides full-table scan vs. index access |
| **Medium** | Multicolumn combinations used together | Correlated columns |

### Core Syntax

```sql
-- Single column
COLLECT STATISTICS COLUMN order_date ON mydb.orders;

-- Multicolumn (for correlated filters / composite join keys)
COLLECT STATISTICS COLUMN (customer_id, order_date) ON mydb.orders;

-- PARTITION pseudo-column (ALWAYS collect on PPI tables)
COLLECT STATISTICS COLUMN (PARTITION) ON mydb.orders;

-- Using sampling for large tables (>100M rows)
COLLECT STATISTICS USING SAMPLE 10 PERCENT COLUMN big_col ON mydb.huge_table;

-- Threshold to skip if data barely changed
COLLECT STATISTICS USING THRESHOLD 10 PERCENT AND THRESHOLD 7 DAYS
    COLUMN order_date ON mydb.orders;
```

### Finding Tables with Missing or Stale Statistics

```sql
-- Tables with NO statistics at all
SELECT t.DatabaseName, t.TableName, t.CreateTimeStamp
FROM DBC.TablesV t
LEFT JOIN DBC.StatsV s ON t.DatabaseName = s.DatabaseName AND t.TableName = s.TableName
WHERE t.TableKind = 'T'
  AND t.DatabaseName = 'mydb'
  AND s.TableName IS NULL;

-- Stale statistics (not collected in >30 days)
SELECT DatabaseName, TableName, ColumnName, LastCollectTimeStamp,
       CURRENT_TIMESTAMP - LastCollectTimeStamp AS age
FROM DBC.StatsV
WHERE DatabaseName = 'mydb'
  AND LastCollectTimeStamp < CURRENT_TIMESTAMP - INTERVAL '30' DAY
ORDER BY age DESC;

-- Statistics the optimizer WISHES it had (diagnostic query)
-- Check DBQL for plans with "no confidence" or low estimated rows
SELECT s.QueryID, s.StepNum,
       s.EstRowCount, s.ActRowCount,
       CASE WHEN ActRowCount > 0 THEN CAST(EstRowCount AS FLOAT) / ActRowCount END AS ratio
FROM DBC.QryLogStepsV s
WHERE s.StartTime > CURRENT_TIMESTAMP - INTERVAL '1' DAY
  AND ActRowCount > 1000
  AND (EstRowCount < ActRowCount / 10 OR EstRowCount > ActRowCount * 10)
ORDER BY ABS(CAST(EstRowCount AS FLOAT) / NULLIFZERO(ActRowCount) - 1) DESC
SAMPLE 50;
```

### Statistics on Volatile/Temporary Tables

- **Yes, collect statistics on volatile tables** if the optimizer will join them to other tables or use them in subqueries
- Without stats, the optimizer assumes 100 rows for volatile tables — if the actual row count is thousands, join plans will be wrong
- Statistics on volatile tables survive only for the session lifetime
- Cost: minimal if the table is small; critical if used in multiple downstream joins

```sql
CREATE VOLATILE TABLE vt_filtered AS (
    SELECT * FROM mydb.big_table WHERE region = 'WEST'
) WITH DATA ON COMMIT PRESERVE ROWS;

-- Collect stats so downstream joins get good estimates
COLLECT STATISTICS COLUMN customer_id ON vt_filtered;
```

---

## EXPLAIN Confidence Levels

EXPLAIN output includes confidence indicators about row estimates. These directly reveal statistics quality.

### Confidence Keywords in EXPLAIN

| Keyword | Meaning | Action |
|---|---|---|
| **"no confidence"** | No statistics exist for this column/combination | COLLECT STATISTICS immediately |
| **"low confidence"** | Statistics exist but are old/extrapolated or dynamic AMP sample used | Recollect statistics |
| **"high confidence"** | Fresh statistics with good histogram | No action needed |
| **"index join confidence"** | Join uses index statistics | Good — optimizer trusts the estimate |

### Reading Confidence in EXPLAIN Output

```
-- BAD: "no confidence" = optimizer guessing
"...the Optimizer has no confidence in the row estimate
 of the join step (1,433 rows estimated with no confidence)..."

-- CONCERNING: "low confidence" = stale stats or sampling
"...estimated with low confidence..."

-- GOOD: "high confidence" = fresh stats
"...estimated with high confidence..."
```

### What "No Confidence" Causes

When the optimizer has no confidence, it falls back to:
1. **Dynamic AMP sampling** — samples one AMP and extrapolates (often wrong by 10x–100x)
2. **Hardcoded heuristics** — assumes 10% selectivity for unknown predicates
3. **Default join assumptions** — may choose wrong join type (e.g., product join instead of merge)

---

## Dynamic AMP Sampling

When statistics are missing, the optimizer reads a small sample from one or two AMPs to estimate:
- Row count
- Distinct values
- Value distribution

### Why It's Not Good Enough

| Problem | Impact |
|---|---|
| Samples only 1–2 AMPs | Skewed data gives wrong extrapolation |
| No histogram | Cannot estimate range selectivity |
| No multicolumn correlation | Assumes column independence |
| Cost: extra I/O at parse time | Adds latency to every query parse |
| Cache invalidation | Sample results cached but invalidated by any DDL |
| Only triggered below threshold | Large tables may not be sampled at all |

### When Dynamic AMP Sampling Is Used

- Column has no collected statistics
- Table has fewer rows than the AMP sampling threshold (configurable)
- Query is parsed (not just EXPLAINed)

### How to Detect It's Being Used

```sql
-- In EXPLAIN output, look for:
-- "estimated with no confidence" — means no stats, AMP sampling likely used
-- "dynamic AMP sampling" — explicit mention in some versions

-- In DBQL, compare EstRowCount vs ActRowCount on steps with missing stats:
SELECT QueryID, StepNum, EstRowCount, ActRowCount
FROM DBC.QryLogStepsV
WHERE StartTime > CURRENT_TIMESTAMP - INTERVAL '1' DAY
  AND ActRowCount > 0
  AND (EstRowCount * 100 < ActRowCount OR EstRowCount > ActRowCount * 100);
-- Large mismatches (>100x off) indicate missing/bad stats
```

---

## Estimated Time in EXPLAIN

The "estimated time" shown in EXPLAIN output is **not real wall-clock time**. Key facts:

- Based on a **cost model** using I/O counts, CPU costs, and network transfers
- Calibrated to a reference system — NOT the actual hardware running the query
- **Only useful for relative comparison** between alternative plans for the same query
- Absolute value is meaningless — "3 seconds" in EXPLAIN can run 40 minutes
- Does NOT account for: concurrency, lock waits, spool exhaustion, AMP worker task scheduling

### How to Use Estimated Time Correctly

- Compare EXPLAIN of two SQL formulations — lower estimate = likely faster
- Compare EXPLAIN before/after adding an index or collecting statistics
- Do NOT use the number to predict actual runtime or set SLAs

---

## Histogram Internals

### Key Concepts

- **Equal-height histogram**: Divides data into intervals each containing approximately the same number of rows
- **Biased values**: High-frequency values extracted for separate tracking (skew handling)
- **MAXINTERVALS** (default 250): Number of histogram intervals — more = finer granularity but more storage
- **MAXVALUELENGTH** (default 25): Bytes stored per value in histogram — increase for wide columns with common prefixes

### Extrapolation (Stale Statistics)

When statistics are not recollected after data changes, the optimizer **extrapolates** based on:
- Original histogram shape
- Known insert/delete/update counts (from system counters)
- Assumes data grows linearly

**When extrapolation breaks down:**
- New value ranges appear (e.g., new dates beyond original max)
- Distribution shifts (seasonal patterns)
- Bulk deletes remove entire value ranges
- Table was truncated and reloaded with different distribution

```sql
-- Check current extrapolated values vs collected values
SHOW CURRENT STATISTICS VALUES COLUMN order_date ON mydb.orders;
-- Compare MaxVal, NumOfDistinctVals, NumOfRows against SHOW STATISTICS VALUES
```

---

## Data Type Mismatches — Implicit Casts Kill Indexes

When a WHERE clause or JOIN compares columns of different data types, Teradata inserts an implicit CAST operation. This:

1. Prevents index access (optimizer cannot use index on a casted column)
2. Forces full-table scan
3. Creates CPU overhead for the conversion

### Common Mismatches

| Left Type | Right Type | Problem |
|---|---|---|
| `INTEGER` | `DECIMAL(18,2)` | Implicit cast of INT to DECIMAL |
| `CHAR(10)` | `VARCHAR(50)` | Implicit cast and pad/trim |
| `DATE` | `TIMESTAMP` | Implicit cast of DATE to TIMESTAMP |
| `VARCHAR(50) LATIN` | `VARCHAR(50) UNICODE` | Character set translation |
| `BIGINT` | `SMALLINT` | Widening cast on one side |

### Detection

```sql
-- In EXPLAIN output, look for:
-- "CAST" operations that you did not write
-- "translated to UNICODE" or "converted from LATIN"

-- In DBQL: queries with unexpected FTS on indexed columns
SELECT q.QueryText, s.StepName
FROM DBC.QryLogV q
JOIN DBC.QryLogStepsV s ON q.QueryID = s.QueryID
WHERE s.StepName LIKE '%FTS%'  -- Full Table Scan
  AND q.StartTime > CURRENT_TIMESTAMP - INTERVAL '1' DAY;
```

### Fix

1. Make column types match in the DDL (ALTER TABLE to fix permanently)
2. Explicitly CAST the smaller/lookup side (not the large table column)
3. Never compare `CHAR` to `VARCHAR` on join keys — standardize to one type

```sql
-- BAD: implicit cast on large table's indexed column
SELECT * FROM big_table WHERE int_column = 12345.00;  -- literal is DECIMAL

-- GOOD: explicit cast on the literal
SELECT * FROM big_table WHERE int_column = 12345;     -- integer literal
```
