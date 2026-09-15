# Dynamic Partition Elimination (DPE)

> Source: TDN0009599-B01.1 — Incremental Planning and Execution in the Teradata Adaptive Optimizer

## Overview

Dynamic Partition Elimination (DPE) is a Teradata execution-time optimization that prunes
partitions from a Partitioned Primary Index (PPI) table during a join operation. Unlike
static partition elimination (where the optimizer eliminates partitions at plan time using
literal values), DPE defers partition pruning to execution time when the filtering values
come from another table or spool.

DPE is identified in EXPLAIN output by the phrase:

```
enhanced by dynamic partition elimination
```

## How DPE Works

### Mechanics

1. The optimizer identifies a join between a **small dimension table** and a **partitioned fact table**
2. The dimension table is read first and its values are materialized in a spool
3. During the join, only partitions of the fact table that match values from the dimension spool are accessed
4. Partitions with no matching rows are skipped entirely at the AMP level

### Join Structure

DPE applies to product joins where:
- The **inner table** (fact) is partitioned (PPI)
- The **outer table** (dimension spool) provides the partition-pruning values
- The join condition involves the partitioning column of the fact table

### Typical Pattern

```sql
-- Dimension filter produces a small set of date keys
-- DPE prunes store_sales partitions at execution time
SELECT SUM(ss_sales_price)
FROM   store_sales, date_dim
WHERE  ss_sold_date_sk = d_date_sk
  AND  d_year = 2001
  AND  d_qoy = 2;
```

In this example:
- `date_dim` is filtered to ~91 rows (one quarter)
- `store_sales` is partitioned by `ss_sold_date_sk`
- Only partitions matching those ~91 date keys are scanned

## Static vs Dynamic Partition Elimination

| Aspect | Static Elimination | Dynamic Elimination |
|---|---|---|
| **When pruning occurs** | Parse time (plan compilation) | Execution time (during join) |
| **Filter source** | Literal values in WHERE clause | Values from joined table or spool |
| **Reliability** | High — always applied when literals match partitions | Lower — depends on optimizer choosing correct join strategy |
| **EXPLAIN indicator** | Partition-qualified RETRIEVE | `"enhanced by dynamic partition elimination"` |
| **Recommended design** | Design for this when possible | Fallback when literals are not available |

**Static elimination** (literal values):
```sql
-- Optimizer prunes at parse time — only matching partitions accessed
SELECT * FROM store_sales
WHERE ss_sold_date_sk BETWEEN 2451861 AND 2451875;
```

**Dynamic elimination** (runtime values from join):
```sql
-- DPE prunes at execution time from dimension join
SELECT * FROM store_sales, date_dim
WHERE ss_sold_date_sk = d_date_sk
  AND d_year = 2001 AND d_qoy = 2;
```

## EXPLAIN Indicators

### DPE Annotation

Look for this key phrase in EXPLAIN output:

```
enhanced by dynamic partition elimination
```

Full example:
```
We do an all-AMPs JOIN step from Spool 6 (Last Use) by way of an
all-rows scan, which is joined to TPCDS.web_sales with a condition of
("NOT (TPCDS.web_sales.ws_bill_customer_sk IS NULL)").
Spool 6 and TPCDS.web_sales are joined using a product join, with
a join condition of ("TPCDS.web_sales.ws_sold_date_sk = d_date_sk")
enhanced by dynamic partition elimination.
```

### What to Look For

| EXPLAIN Element | Indicates |
|---|---|
| `"enhanced by dynamic partition elimination"` | DPE is active on this join |
| `"product join"` with DPE | Small dimension spool drives partition access |
| `"duplicated on all AMPs"` on the dimension spool | Dimension data prepared for DPE join |

## Statistics Requirements

DPE effectiveness depends on the optimizer choosing a plan that places the dimension table
on the outer side of the join. This decision relies on accurate statistics.

### Critical Statistics

| Object | Statistics Needed | Why |
|---|---|---|
| Dimension table | Row count, filter column stats | Optimizer must know dimension is small |
| Fact table (partitioned) | Partition-level stats, join column stats | Optimizer estimates per-partition cost |
| Join columns | NUV, HMF on both sides | Determines join strategy and DPE viability |

```sql
-- Collect statistics to support DPE decisions
COLLECT STATISTICS ON date_dim COLUMN (d_date_sk);
COLLECT STATISTICS ON date_dim COLUMN (d_year);
COLLECT STATISTICS ON date_dim COLUMN (d_qoy);
COLLECT STATISTICS ON store_sales COLUMN (ss_sold_date_sk);
COLLECT STATISTICS ON store_sales COLUMN (PARTITION);
```

> **PARTITION statistics are a prerequisite** for the optimizer to consider DPE at all.
> Without them, the optimizer cannot estimate per-partition costs.

## DPE Effectiveness

The benefit of DPE is proportional to the selectivity of the dimension filter:

| Dimension Selectivity | DPE Benefit |
|---|---|
| < 5% of partitions | High — significant I/O reduction |
| 5–30% of partitions | Moderate — depends on table size |
| > 30% of partitions | Low — full scan may be faster |

## When DPE Does Not Occur

**Symptom:** EXPLAIN shows a hash join or merge join instead of a product join with DPE.

**Possible causes:**
1. **Dimension table estimated too large** — collect statistics on filter columns
2. **Join is not on the partitioning column** — verify the PPI expression matches the join condition
3. **Table is not partitioned** — check DDL for `PARTITION BY` clause
4. **Missing PARTITION statistics** — run `COLLECT STATISTICS ON fact_table COLUMN (PARTITION)`
5. **Optimizer chose a different strategy** — use `DIAGNOSTIC HELPSTATS` to identify missing statistics

### Workaround: Materialize as Literals

When DPE does not occur, the practical technique is to convert the join-based filter to
literal values:

1. Query the driving (dimension) table first to get the boundary values
2. Build the second statement with explicit `BETWEEN` bounds
3. Or pre-collect boundary values into variables in a stored procedure

```sql
-- Step 1: Get the date key range
SELECT MIN(d_date_sk), MAX(d_date_sk)
FROM date_dim WHERE d_year = 2001 AND d_qoy = 2;
-- Returns e.g. 2451911, 2452001

-- Step 2: Use literal values for static partition elimination
SELECT SUM(ss_sales_price)
FROM store_sales
WHERE ss_sold_date_sk BETWEEN 2451911 AND 2452001;
```

## DPE vs IPE Results Feedback

Both DPE and IPE results feedback can achieve partition elimination, but through different mechanisms:

| Aspect | DPE | IPE Results Feedback |
|---|---|---|
| **When pruning occurs** | During join execution | Before join planning (values substituted) |
| **Join required?** | Yes — dimension spool joined to fact | No — join may be eliminated entirely |
| **Dimension spool** | Must be materialized and duplicated | Not needed if join is eliminated |
| **Applicability** | Any join with partitioning column | Only eligible IPE constructs |

When both could apply: IPE is generally superior due to eliminated spool overhead.
If IPE is disabled (`DYNAMICPLAN=OFF`), the optimizer falls back to DPE.

## Performance Monitoring

### Identifying DPE in DBQL

```sql
-- Find queries using DPE by searching explain text
SELECT QueryId, QueryText
FROM   DBC.DBQLExplainTbl
WHERE  ExplainText LIKE '%dynamic partition elimination%';
```

### Measuring DPE Effectiveness

```sql
-- Check partition access in step-level DBQL
SELECT QueryId, StepNum, NumPartitions, TotalPartitions
FROM   DBC.DBQLStepTbl
WHERE  QueryId = <query_id>
  AND  NumPartitions IS NOT NULL;
```
