# Dynamic Partition Elimination (DPE)

> Source: TDN0009599-B01.1 — Incremental Planning and Execution in the Teradata Adaptive Optimizer; general Teradata DPE documentation

## Overview

Dynamic Partition Elimination (DPE) is a Teradata execution-time optimization that prunes partitions from a Partitioned Primary Index (PPI) table during a join operation. Unlike static partition elimination (where the optimizer eliminates partitions at plan time using literal values), DPE defers partition pruning to execution time when the filtering values come from another table or spool.

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

```
Spool 6 and TPCDS.store_sales are joined using a product join,
with a join condition of ("TPCDS.store_sales.ss_sold_date_sk = d_date_sk")
enhanced by dynamic partition elimination.
```

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

## Query Patterns That Benefit from DPE

### Date Dimension Joins

The most common DPE pattern involves date dimension tables joined to date-partitioned fact tables:

```sql
-- Filter by quarter, month, or custom date range
SELECT SUM(cs_sales_price)
FROM   catalog_sales, date_dim
WHERE  cs_sold_date_sk = d_date_sk
  AND  d_year = 2001 AND d_qoy = 2;
```

### Subquery-Driven Filtering

When filtering values come from a subquery rather than literals, DPE applies at execution time:

```sql
-- Date keys from subquery drive partition elimination
SELECT SUM(inv_quantity_on_hand)
FROM   inventory, date_dim
WHERE  inv_date_sk = d_date_sk
  AND  d_date BETWEEN '2000-05-25' AND '2000-06-08';
```

### Multi-Table Joins with Cascading DPE

DPE can cascade through multiple joins when intermediate spools carry partitioning column values:

```sql
SELECT s_store_name, SUM(ss_net_profit)
FROM   store_sales, date_dim, store, derived_table_V1
WHERE  ss_store_sk = s_store_sk
  AND  ss_sold_date_sk = d_date_sk
  AND  d_qoy = 2 AND d_year = 1998
  AND  SUBSTR(s_zip, 1, 2) = SUBSTR(V1.ca_zip, 1, 2)
GROUP BY s_store_name;
```

## EXPLAIN Indicators

### DPE Annotation

Look for this key phrase in EXPLAIN output:

```
enhanced by dynamic partition elimination
```

Full example from EXPLAIN:

```
17) We do an all-AMPs JOIN step from Spool 6 (Last Use) by way of an
    all-rows scan, which is joined to TPCDS.web_sales with a condition
    of ("NOT (TPCDS.web_sales.ws_bill_customer_sk IS NULL)").
    Spool 6 and TPCDS.web_sales are joined using a product join, with
    a join condition of ("TPCDS.web_sales.ws_sold_date_sk = d_date_sk")
    enhanced by dynamic partition elimination.  The result goes into
    Spool 7 (all_amps), which is built locally on the AMPs.
```

### What to Look For

| EXPLAIN Element | Indicates |
|---|---|
| `"enhanced by dynamic partition elimination"` | DPE is active on this join |
| `"product join"` with DPE | Small dimension spool drives partition access |
| `"duplicated on all AMPs"` on the dimension spool | Dimension data prepared for DPE join |
| `"SORT to partition by rowkey"` | Dimension spool sorted for partition-aligned access |

### Static vs Dynamic Partition Elimination in EXPLAIN

**Static elimination** (literal values):
```
We do an all-AMPs RETRIEVE step from TPCDS.inventory
by way of an all-rows scan with a condition of
("(inv_date_sk >= 2451861) AND (inv_date_sk <= 2451875)")
-- Only matching partitions are accessed
```

**Dynamic elimination** (runtime values):
```
Spool 3 and TPCDS.inventory are joined using a product join,
with a join condition of ("d_date_sk = inv_date_sk")
enhanced by dynamic partition elimination.
```

## DPE vs IPE Results Feedback

Both DPE and IPE results feedback can achieve partition elimination, but through different mechanisms:

### Comparison

| Aspect | DPE | IPE Results Feedback |
|---|---|---|
| **When pruning occurs** | During join execution | Before join planning (values substituted) |
| **Join required?** | Yes — dimension spool joined to fact | No — join may be eliminated entirely |
| **Dimension spool** | Must be materialized and duplicated | Not needed if join is eliminated |
| **Network overhead** | Spool duplication on large systems | Minimal — only feedback values sent |
| **Partition count accuracy** | Exact at runtime | Exact — literal values used |
| **Applicability** | Any join with partitioning column | Only eligible IPE constructs (UJT, subqueries, etc.) |

### Example: Unique-Join Table

```sql
SELECT i_item_id, i_item_desc, i_current_price
FROM   item, inventory, date_dim, store_sales
WHERE  inv_item_sk = i_item_sk
  AND  d_date_sk = inv_date_sk
  AND  d_date BETWEEN '2000-05-25' AND '2000-06-08'
  AND  i_manufact_id IN ('129', '270', '821', '423')
  AND  inv_quantity_on_hand BETWEEN 100 AND 500
  AND  ss_item_sk = i_item_sk;
```

**Static plan (DPE):**
- `date_dim` spool duplicated on all AMPs, sorted for partition alignment
- Product join with `inventory` using DPE — accesses 15 partitions
- `date_dim` spool materialization + duplication overhead

**Dynamic plan (IPE):**
- Fragment 1: Retrieve 15 `d_date_sk` values from `date_dim` as results feedback
- Fragment 2: `inv_date_sk IN (:*, ..., :*)` — accesses 15 partitions directly
- No `date_dim` spool needed; join eliminated

Static plan estimated time: 48.92 seconds. Dynamic plan: significantly faster due to eliminated spool overhead.

## Interaction with PPI

### Prerequisites for DPE

For DPE to apply, the fact table must be partitioned (PPI or MLPPI) and the join must involve the partitioning expression:

```sql
-- DPE applies: join on partitioning column
CREATE TABLE store_sales (
    ss_sold_date_sk INTEGER,
    ss_sales_price DECIMAL(7,2),
    ...
) PRIMARY INDEX (ss_item_sk, ss_ticket_number)
  PARTITION BY RANGE_N(ss_sold_date_sk BETWEEN 2450816 AND 2453005
                       EACH 1);

-- Join on ss_sold_date_sk enables DPE
SELECT ... FROM store_sales, date_dim
WHERE ss_sold_date_sk = d_date_sk AND d_year = 2001;
```

### Multi-Level PPI (MLPPI)

DPE can eliminate partitions at any level of a multi-level partition:

```sql
-- Table partitioned by date and region
PARTITION BY (
    RANGE_N(sale_date BETWEEN DATE '2020-01-01' AND DATE '2025-12-31' EACH INTERVAL '1' MONTH),
    RANGE_N(region_id BETWEEN 1 AND 10 EACH 1)
);

-- DPE on sale_date from date_dim join
-- DPE on region_id from region_dim join (if also joined)
```

### Column-Partitioned Tables

DPE does not apply to column-partitioned (CP) tables directly, since CP partitioning is by column groups, not row values. For combined row+column partitioned (CRP) tables, DPE applies to the row partitioning level.

## Statistics Requirements

DPE effectiveness depends on the optimizer choosing a plan that places the dimension table on the outer side of the join. This decision relies on accurate statistics:

### Critical Statistics

| Object | Statistics Needed | Why |
|---|---|---|
| Dimension table | Row count, filter column stats | Optimizer must know dimension is small |
| Fact table (partitioned) | Partition-level stats, join column stats | Optimizer estimates per-partition cost |
| Join columns | NUV, HMF on both sides | Determines join strategy and DPE viability |

### When Statistics Are Missing

- If the optimizer overestimates the dimension size, it may choose a hash join instead of a product join with DPE
- If the dimension table has no statistics on filter columns, cardinality estimates may be wrong
- Remote tables in UDA environments often lack statistics — IPE statistics feedback helps here

```sql
-- Collect statistics to support DPE decisions
COLLECT STATISTICS ON date_dim COLUMN (d_date_sk);
COLLECT STATISTICS ON date_dim COLUMN (d_year);
COLLECT STATISTICS ON date_dim COLUMN (d_qoy);
COLLECT STATISTICS ON store_sales COLUMN (ss_sold_date_sk);
COLLECT STATISTICS ON store_sales COLUMN (PARTITION);
```

## Performance Monitoring

### Identifying DPE in DBQL

```sql
-- Find queries using DPE by searching explain text
SELECT QueryId, QueryText
FROM   DBC.DBQLExplainTbl
WHERE  ExplainText LIKE '%dynamic partition elimination%';
```

### Measuring DPE Effectiveness

Compare the number of partitions accessed vs total partitions:

```sql
-- Check partition access in step-level DBQL
SELECT QueryId, StepNum, NumPartitions, TotalPartitions
FROM   DBC.DBQLStepTbl
WHERE  QueryId = <query_id>
  AND  NumPartitions IS NOT NULL;
```

### DPE vs Full Table Scan Cost

The benefit of DPE is proportional to the selectivity of the dimension filter. If the dimension returns values spanning most partitions, DPE overhead (spool duplication, partition-by-partition access) may exceed a sequential full-table scan.

| Dimension Selectivity | DPE Benefit |
|---|---|
| < 5% of partitions | High — significant I/O reduction |
| 5-30% of partitions | Moderate — depends on table size |
| > 30% of partitions | Low — full scan may be faster |

## Troubleshooting DPE

### DPE Not Applied

**Symptom:** EXPLAIN shows a hash join or merge join instead of a product join with DPE.

**Possible causes:**
1. Dimension table estimated too large — collect statistics on filter columns
2. Join is not on the partitioning column — verify the PPI expression matches
3. Table is not partitioned — check DDL for PARTITION BY clause
4. Optimizer chose a different strategy — try `DIAGNOSTIC HELPSTATS` to identify missing statistics

### DPE Applied but Slow

**Symptom:** Query uses DPE but is slower than expected.

**Possible causes:**
1. Dimension filter returns too many distinct partition values — DPE overhead exceeds sequential scan
2. Dimension spool is large and duplicated across many AMPs — high network overhead
3. Partitions are very small — per-partition overhead dominates

### DPE vs IPE Decision

When both DPE and IPE results feedback could apply:
- IPE eliminates the join entirely (lower overhead) but requires IPE eligibility and qualification
- DPE always works for partition-aligned joins regardless of IPE settings
- If IPE is disabled (`DYNAMICPLAN=OFF`), the optimizer falls back to DPE
- For Unique-Join Tables, IPE is generally superior due to eliminated spool overhead

## Best Practices

1. **Collect statistics** on dimension filter columns and fact table partitioning columns
2. **Use `COLLECT STATISTICS ON ... COLUMN (PARTITION)`** to give the optimizer per-partition row counts
3. **Keep dimension tables small** — filter early to reduce the DPE spool size
4. **Verify DPE in EXPLAIN** before assuming partition elimination is occurring
5. **Compare static and dynamic EXPLAIN** — IPE may provide a better plan than DPE alone
6. **Monitor with DBQL** — track `NumPartitions` accessed vs total for ongoing workload tuning
7. **Consider IPE for UJT patterns** — when `date_dim` has a UPI and range conditions, IPE can eliminate the join entirely
