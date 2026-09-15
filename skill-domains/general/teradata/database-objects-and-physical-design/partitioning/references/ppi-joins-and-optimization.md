# PPI Join Optimization & Secondary Index Access

## PI Access Degradation with PPI

When partitioning columns are **not** part of the PI, each combined partition must be probed for PI access. Performance degrades proportional to partition count.

### Benchmark: 300M row lineitem table, 7 years, date NOT in PI

| Query Type | NPPI | 7 Parts | 84 Parts | 2557 Parts |
|---|---|---|---|---|
| PI access, no date filter | 0.013s | 0.110s | 0.516s | 27.433s |
| PI access, date specified | 0.020s | 0.059s | 0.060s | 0.060s |
| PI access, USI on PI cols | 0.044s | 0.031s | 0.030s | 0.028s |
| 7-day range scan | 332s | 59s | 6s | 2s |
| 1-AMP tactical join | <1s | 1s | 4s | 66s |
| All-AMP tactical join (1 day) | 561s | 176s | 127s | 12s |

### Mitigation: USI on PI Columns

Creating a USI on the same columns as the PI restores single-AMP access independent of partition count. The USI subtable maps directly to the base row.

```sql
-- Restore fast PI access for PPI table where date is NOT in PI
CREATE UNIQUE INDEX (order_key) ON mydb.orders;
-- Now PI access is 2-AMP (USI subtable → base) regardless of partition count
```

### NUSI on Same Columns as NUPI (V2R6.0+)

When a NUSI is defined on the same columns as the NUPI, access becomes a **single-AMP operation** with rowhash locking instead of all-AMP with table lock.

```sql
-- Setup: NUPI on (customer_id), partitioned by date
-- Create NUSI on same columns as NUPI:
CREATE INDEX (customer_id) ON mydb.orders;

-- Query: SELECT * FROM mydb.orders WHERE customer_id = 839;
-- Without NUSI: single-AMP, probes ALL partitions (e.g., 100 block reads)
-- With enhanced NUSI: single-AMP, rowhash lock, ~11 block reads
```

**When beneficial:** occurrences of NUSI value < number of combined partitions.

---

## Secondary Index Access with PPI

### NUSI Rowid Partition Elimination (V2R6.0+)

Static partition elimination is applied to referencing rowids in a secondary index. Only rows in non-eliminated partitions of the base table are read.

**Works with:** NUSI equality, range, LIKE, OR processing, bitmap indexing, USI equality.

**Required statistics:**
```sql
COLLECT STATISTICS COLUMN (nusi_columns) ON mydb.table;
COLLECT STATISTICS COLUMN (partitioning_columns) ON mydb.table;
COLLECT STATISTICS COLUMN (PARTITION) ON mydb.table;  -- V2R6.1+
```

### Worked Example

```
-- 2-AMP system, 100 rows/block, 100 blocks/partition/AMP, 10 partitions
-- 200,000 rows total, 400 rows match NUSI=78, 20 rows/partition/AMP

SELECT * FROM t1 WHERE nusi_col=78 AND partition_col=5;
-- Result: 40 rows

-- Partition scan:        100 blocks/AMP × 2 AMPs = 200 reads
-- NUSI (no elimination): 1 index + 200 base reads/AMP = 402 reads
-- NUSI (with elimination): 1 index + 20 base reads/AMP = 42 reads ← CHOSEN
```

---

## PPI Join Types

### 1. Rowkey-Based Merge Join

**Conditions (all required):**
- Both tables have the **same PI columns**
- Both tables have **identical partitioning expressions**
- All PI columns AND all partitioning columns are equality join terms

Performance ≈ traditional NPPI merge join.

```sql
-- Both tables: PI(order_id), PARTITION BY RANGE_N(order_date ...)
SELECT a.*, b.detail
FROM mydb.orders a
JOIN mydb.order_details b
  ON a.order_id = b.order_id        -- PI columns
 AND a.order_date = b.order_date;   -- partitioning columns
-- → Rowkey-based merge join
```

### 2. Sliding-Window (Multicontext) Join

**Used when:** One table PPI, other NPPI, or both PPI with different partitioning. PI columns are equality join terms but partitioning columns are not.

#### Algorithm
1. First data block of NPPI table read
2. First data block of each non-eliminated, nonempty partition of PPI table read into memory (one per "context")
3. Rows compared across all blocks; as blocks exhausted, next block for that partition read
4. Each data block of each table read only once **if** all partitions fit in memory

#### Cost Formula

```
Let:
  d = data blocks in table
  p = non-eliminated, nonempty combined partitions  
  k = number of contexts (blocks in memory)

Neither partitioned:    d₁ + d₂
One PPI:               (p₂/k₂ × d₁) + d₂
Both PPI:              (p₂/k₂ × d₁) + (p₁/k₁ × d₂)

Rules:
  - If p/k < 1, use p/k = 1
  - One PPI table: p/k must be ≤ ~4 for attractive performance
  - Two PPI tables: both p₁/k₁ and p₂/k₂ must be ≤ ~2-3
```

#### PPICacheThrP Parameter (DBS Control, Performance Group)

| Setting | Description |
|---|---|
| **Default** | 10 (= 1.0% of FSG cache) |
| **Units** | Tenths of a percent |
| **Minimum contexts** | 8 (or fewer if <8 non-eliminated partitions) |
| **Maximum contexts** | 256, or number fitting in PPICacheThrP %, or non-eliminated partitions — whichever smallest |
| **Scope** | Per query step, per AMP |

### 3. Product Join Dynamic Partition Elimination (DPE) — V2R5.1+

Only partitions matching lookup values participate in the join.

**Required conditions:**
```sql
-- Equality between partitioning column and lookup column:
WHERE ppi_table.partition_col = lookup_table.col
-- OR (13.0+):
WHERE ppi_table.partition_col = f(lookup_table.columns)
WHERE ppi_table.partition_col [NOT] IN (subquery)
```

**Required statistics:**
```sql
COLLECT STATISTICS COLUMN (pi_columns) ON ppi_table;
COLLECT STATISTICS COLUMN (pi_columns) ON lookup_table;
COLLECT STATISTICS COLUMN (partitioning_columns) ON ppi_table;
COLLECT STATISTICS COLUMN (PARTITION) ON ppi_table;  -- Required for subquery DPE
COLLECT STATISTICS COLUMN (cols_equated_to_partitioning) ON lookup_table;
COLLECT STATISTICS COLUMN (qualifying_cols) ON lookup_table;
```

**DPE guideline thresholds:**
- `n` (unique partitions from lookup) must be **significantly less** than nonempty partitions
- `m × r` (rows with same partition value × avg row size) should be **much less than 384KB**
- Data blocks per partition per AMP should be **>10, preferably >100**

**EXPLAIN indicator:** `"enhanced by dynamic partition elimination"`

### 4. Merge Join DPE (DB 12.0+, Single-Level Only)

**Conditions:**
- Inner merge join
- Right relation has PPI with direct geography (equality join on PI)
- Single partitioning column

**Acceptable partitioning expressions:**
```sql
PARTITION BY x;                                          -- direct column
PARTITION BY RANGE_N(x BETWEEN 1 AND 100 EACH 5);      -- single range + EACH
```

**NOT acceptable:**
```sql
PARTITION BY (x MOD 65535) + 1;                         -- modulo
PARTITION BY CASE_N(x<10, x<=50, NO CASE OR UNKNOWN);  -- CASE_N
PARTITION BY RANGE_N(x BETWEEN *, 1, 3, 6 AND 10, 11 AND *);  -- multiple ranges
```

**Binding types:**
- Equality → join on single partition
- Inequality → open range of partitions
- Range → closed range of partitions
- NO RANGE / UNKNOWN partitions → sliding-window used instead

---

## PPI Join Index (V2R6.2+)

Any **noncompressed** join index can have PPI. Compressed join indexes may NOT have PPI.

```sql
-- Aggregate join index with PPI (star schema optimization)
CREATE JOIN INDEX mydb.ji_sales_summary AS
  SELECT s.sale_date, p.prod_category, o.division,
         SUM(s.amount) AS daily_sales
  FROM mydb.calendar c, mydb.product p, mydb.org o, mydb.sales s
  WHERE c.dayofmth = s.sale_date
    AND p.prod_id = s.prod_id
    AND o.store_id = s.store_id
  GROUP BY s.sale_date, p.prod_category, o.division
  PRIMARY INDEX (sale_date, prod_category, division)
  PARTITION BY RANGE_N(sale_date BETWEEN DATE '2020-01-01'
      AND DATE '2030-12-31' EACH INTERVAL '1' MONTH);

-- Single-table join index with PPI
CREATE JOIN INDEX mydb.ji_sales_by_date AS
  SELECT sale_date, prod_id, SUM(amount) AS sales_amount
  FROM mydb.sales
  GROUP BY sale_date, prod_id
  PRIMARY INDEX (sale_date, prod_id)
  PARTITION BY RANGE_N(sale_date BETWEEN DATE '2020-01-01'
      AND DATE '2030-12-31' EACH INTERVAL '1' MONTH);
```

Partition elimination and rowkey-based merge join optimizations apply to PPI join indexes.

---

## EXPLAIN Interpretation for PPI

| EXPLAIN Phrase | Meaning |
|---|---|
| `"n partitions of"` | Static partition elimination — n partitions accessed |
| `"a single partition of"` | Eliminated to exactly one partition |
| `"all partitions of"` | No elimination — all partitions probed |
| `"of n partitions"` | Optimized whole-partition delete (n partitions) |
| `"of a single partition"` | Optimized whole-partition delete (1 partition) |
| `"SORT to partition by rowkey"` | Lookup rows sorted for DPE |
| `"enhanced by dynamic partition elimination"` | Product join DPE active |

### EXPLAIN Examples

```sql
-- Static elimination (8 of 10 partitions)
EXPLAIN SELECT * FROM t1 WHERE b > 2;
-- "all-AMPs RETRIEVE step from 8 partitions of PLS.t1"

-- PI access, all partitions probed (no partition column)
EXPLAIN SELECT * FROM t1 WHERE a=49;
-- "single-AMP RETRIEVE step from all partitions of PLS.t1
--  by way of the primary index"

-- PI access with partition range
EXPLAIN SELECT * FROM t1 WHERE a=49 AND b BETWEEN 4 AND 6;
-- "single-AMP RETRIEVE step from 3 partitions of PLS.t1
--  by way of the primary index"

-- PI access, single partition
EXPLAIN SELECT * FROM t1 WHERE a=49 AND b=5;
-- "single-AMP RETRIEVE step from a single partition of PLS.t1"
```

### Optimized Whole-Partition Delete

Conditions:
1. DELETE must be last statement in transaction/request causing commit
2. Table must NOT have JI, HI, referential integrity, or replication

```sql
EXPLAIN DELETE FROM t2 WHERE b BETWEEN 4 AND 7;
-- Step 3: "DELETE from 2 partitions of PLS.t2" (partial partition)
-- Step 4: "DELETE of a single partition from PLS.t2" (whole-partition)
```
