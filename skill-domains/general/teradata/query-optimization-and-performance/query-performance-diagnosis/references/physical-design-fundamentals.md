# Physical Design Fundamentals for Performance

## Primary Index Selection

The Primary Index (PI) determines how rows are distributed across AMPs. It is the single most important performance decision for any Teradata table.

### Trade-offs

| Goal | PI Choice | Risk |
|---|---|---|
| Even distribution | High-cardinality, unique column | Poor join locality if not a join key |
| Fast joins | Same column(s) as frequently joined table | Possible skew if column is skewed |
| Fast single-row access | Unique value column (UPI) | 1-AMP access for equality WHERE |
| Fast known-value access | Non-unique (NUPI) | Multiple rows per hash — still 1-AMP |

### How to Choose a PI

1. **Identify the dominant join pattern** — which tables are joined together most often and on which columns?
2. **Check distribution** of candidate columns:
   ```sql
   -- Distribution analysis for candidate PI column
   SELECT candidate_col, COUNT(*) AS row_cnt
   FROM mydb.table_name
   GROUP BY candidate_col
   ORDER BY row_cnt DESC
   SAMPLE 20;
   
   -- Check skew factor
   SELECT (MAX(row_cnt) - AVG(row_cnt)) * 100.0 / NULLIFZERO(AVG(row_cnt)) AS skew_pct
   FROM (
       SELECT candidate_col, COUNT(*) AS row_cnt
       FROM mydb.table_name
       GROUP BY candidate_col
   ) t;
   -- If skew_pct > 10%, consider a different PI or composite PI
   ```
3. **Check join alignment** — tables joined frequently should share the same PI columns so rows co-locate on the same AMP (no redistribution needed)
4. **Consider composite PI** — `PRIMARY INDEX (col1, col2)` gives better distribution than single column but requires both columns in WHERE for 1-AMP access

### Changing the Primary Index

```sql
-- CANNOT be altered in place. Must recreate the table:
CREATE TABLE mydb.new_table AS mydb.old_table WITH DATA
    PRIMARY INDEX (new_pi_column);

-- Or use ALTER TABLE ... MODIFY PRIMARY INDEX (16.20+):
ALTER TABLE mydb.orders MODIFY PRIMARY INDEX (order_id);
-- WARNING: This rebuilds the entire table (moves all data). Requires double space temporarily.
```

### PRIMARY AMP INDEX (Single-AMP Table)

Forces all rows to a single AMP. Used for:
- Small reference/lookup tables (<100K rows)
- Tables that must guarantee single-AMP joins

```sql
CREATE TABLE mydb.lookup (
    code CHAR(3),
    description VARCHAR(50)
) PRIMARY AMP INDEX (code);
-- ALL rows go to the AMP determined by hashing the first row's code value
```

**When to use:** Only when table is tiny AND single-AMP access is required. NOT for any table that could grow.

---

## Secondary Indexes (USI / NUSI)

### USI (Unique Secondary Index)

- **Architecture:** Separate subtable distributed across all AMPs by hash of index value
- **Access:** 2-AMP operation (1 AMP for subtable lookup → 1 AMP for base table row)
- **Use when:** Need fast single-row lookup on a non-PI unique column (e.g., email, SSN)
- **Penalty:** Extra storage + maintenance on INSERT/UPDATE/DELETE

### NUSI (Non-Unique Secondary Index)

- **Architecture:** Local subtable on each AMP containing index entries for that AMP's rows
- **Access:** All-AMP operation (every AMP checks its local subtable)
- **Use when:** Equality access on a non-PI column with moderate selectivity (<10% of rows)
- **When optimizer IGNORES a NUSI:**
  - No statistics collected on the NUSI columns — optimizer doesn't know selectivity
  - Selectivity too low (>5-15% of rows) — full-table scan is cheaper
  - Data type mismatch in WHERE clause prevents index use
  - Function applied to indexed column: `WHERE UPPER(name) = 'SMITH'`

```sql
-- Collect statistics so optimizer knows about NUSI selectivity
COLLECT STATISTICS COLUMN department_id ON mydb.employees;
COLLECT STATISTICS INDEX (department_id) ON mydb.employees;
```

### USI vs NUSI Comparison

| Characteristic | USI | NUSI |
|---|---|---|
| AMPs involved | 2 (subtable + base) | ALL AMPs |
| Best for | Point lookups (= value) | Moderate selectivity filters |
| Equality lookup speed | Fastest (2 I/O) | Depends on selectivity |
| Range queries | Not useful | Use value-ordered NUSI |
| DML maintenance cost | One remote AMP update | One local AMP update |
| Can be covering? | Yes | Yes |
| Null handling | Only one NULL allowed | Multiple NULLs OK |

### Value-Ordered NUSI

```sql
CREATE INDEX idx_amount ORDER BY VALUES (amount) ON mydb.transactions (amount);
```

- Sorts subtable by column value instead of row hash
- Enables efficient range scans: `WHERE amount BETWEEN 100 AND 500`
- Good for: date ranges on non-PI/non-partition columns, TOP N queries

---

## Hash Indexes

A hash index is a **persistent materialized subset** of a base table, stored in its own subtable distributed by a different hash than the base table's PI.

```sql
CREATE HASH INDEX hi_custid ON mydb.orders
    BY (customer_id)    -- distribution column
    ORDER BY (customer_id);  -- storage order
```

### How It Differs from a Single-Table Join Index

| Feature | Hash Index | Single-Table Join Index |
|---|---|---|
| Storage | Subset of base table rows | Full materialized copy (can aggregate/filter) |
| PI | Must differ from base table PI | Can be any PI |
| Aggregation | No (raw rows only) | Yes (can include GROUP BY) |
| Column subset | Any columns from base | Any columns from base |
| Partition | Inherits base table PPI | Can have its own PPI |
| Maintenance | Automatic on base DML | Automatic on base DML |
| Use case | Fast access path on different PI | Pre-joined/aggregated fast access |

### When to Use Hash Index vs NUSI

- **Hash index:** When you need single-AMP access on a different distribution key AND the column is high-cardinality
- **NUSI:** When you need all-AMP access on a moderate-selectivity column
- **Join index:** When you need aggregated/pre-joined data or want to store only certain columns

---

## Partitioned Primary Index (PPI)

### When PPI Helps

- Range queries on the partition column (date ranges on fact tables)
- Efficient deletes of old partitions (DROP PARTITION vs row-by-row DELETE)
- Reducing full-table scan to partition scan for filtered queries

### When PPI Hurts

- Point access on PI without specifying partition: probes ALL partitions
- Too many partitions (>500): PI access degrades linearly
- Joins between PPI tables with different partitioning: sliding-window join overhead

### Mitigation for PI Access Degradation

```sql
-- If PI access without partition filter is slow, create a USI on PI columns:
CREATE UNIQUE INDEX (order_id) ON mydb.orders;
-- Restores 2-AMP access regardless of partition count
```

### How Many Partitions?

| Partition Count | Impact |
|---|---|
| 1–50 | Minimal PI access overhead |
| 50–200 | Moderate — acceptable for range-query-heavy workloads |
| 200–500 | Significant PI point-access cost; require partition filter in most queries |
| >500 | Severe — PI access without partition filter becomes very expensive |

### Partition Elimination in EXPLAIN

```
"from 3 partitions of"   → static elimination worked (3 of N accessed)
"a single partition of"  → best case: only 1 partition accessed
"all partitions of"      → NO elimination — partition column not in WHERE
```

---

## Table Types: SET vs MULTISET

| Type | Duplicate Rows | INSERT Speed |
|---|---|---|
| **SET** | Not allowed (duplicate check on every INSERT) | Slower — must verify uniqueness |
| **MULTISET** | Allowed | Faster — no duplicate check |

### When SET Tables Cause Problems

- Staging/ETL tables with duplicate-heavy loads: INSERT checks cause I/O amplification
- Bulk loads into SET tables: each row compared against existing rows on the AMP
- If you have a UPI, SET vs MULTISET doesn't matter (UPI enforces uniqueness already)

### Fix for Slow Inserts on SET Tables

```sql
-- Change to MULTISET if duplicates are acceptable
ALTER TABLE mydb.staging_table MODIFY SET TO MULTISET;

-- Or use MULTISET from the start for staging
CREATE MULTISET TABLE mydb.staging (...) PRIMARY INDEX (load_key);
```

---

## NoPI Tables

A No Primary Index table has NO hash distribution — rows are appended sequentially to AMPs in round-robin fashion.

### When to Use

- Staging/landing tables for bulk loads (no distribution overhead on INSERT)
- Tables that will always be full-table-scanned and never point-accessed
- Intermediate load tables before redistributing into a final PI table

### What You Give Up

- No single-AMP access (every query is all-AMP full scan)
- Cannot create secondary indexes on NoPI tables
- Cannot be the inner table of a merge join
- No rowhash-based join locality

```sql
CREATE MULTISET TABLE mydb.staging_load, NO PRIMARY INDEX (
    col1 INTEGER,
    col2 VARCHAR(100),
    col3 DATE
);
```

---

## Column Ordering and Performance

Column order in `CREATE TABLE` **does not affect query performance** in Teradata. The storage engine places columns by:
1. Fixed-length columns first (sorted by descending size)
2. Variable-length columns after

This is internal — DDL column order is irrelevant to I/O patterns, compression, or access paths.

The only performance-relevant column choices are:
- Data types (affects storage size and implicit cast issues)
- Compression attributes (VALUE COMPRESSION on low-cardinality columns)
- Which columns are in the PI, partition expression, and indexes
