---
name: teradata-partitioning
description: 'Design and manage Teradata table partitioning including Partitioned Primary Index (PPI), multi-level partitioning (MLPPI), column partitioning (CP), and combined row+column partitioning (CRP). Use when creating partitioned tables with RANGE_N or CASE_N, implementing sliding window maintenance, altering partitions (ADD/DROP), optimizing partition elimination, choosing between row vs column partitioning, or querying DBC.PartitioningConstraintsV.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Partitioning

## When to Use

- Creating tables with date-range, numeric, or character partitioning
- Multi-level partitioning (MLPPI) for multiple dimensions
- Column partitioning for analytics/warehouse workloads
- Sliding window maintenance (DROP/ADD ranges monthly)
- Optimizing query performance with partition elimination
- Choosing between PPI, NPPI, column partitioning, or hybrid

## Partitioning Types

| Type | Syntax | Best For |
|---|---|---|
| **Row (PPI)** | `PARTITION BY RANGE_N(...)` | Date-range queries, sliding windows |
| **Multi-Level (MLPPI)** | `PARTITION BY (RANGE_N(...), RANGE_N(...))` | Multi-dimension filtering |
| **Column (CP)** | `PARTITION BY COLUMN` | Analytics on wide tables, autocompression |
| **Combined (CRP)** | `PARTITION BY (COLUMN, RANGE_N(...))` | Analytics + date filtering |

## RANGE_N Function

```sql
RANGE_N(expression BETWEEN start AND end EACH interval
        [, start2 AND end2 EACH interval2]...
        [, NO RANGE]
        [, UNKNOWN]
        [, NO RANGE OR UNKNOWN])
```

| Clause | Purpose |
|---|---|
| `NO RANGE` | Catches values outside all defined ranges |
| `UNKNOWN` | Catches NULL values |
| `NO RANGE OR UNKNOWN` | Single partition for both |

### Common Patterns

```sql
-- Daily
PARTITION BY RANGE_N(txn_date BETWEEN DATE '2020-01-01'
    AND DATE '2025-12-31' EACH INTERVAL '1' DAY);

-- Monthly
PARTITION BY RANGE_N(order_date BETWEEN DATE '2020-01-01'
    AND DATE '2025-12-31' EACH INTERVAL '1' MONTH);

-- Yearly
PARTITION BY RANGE_N(sale_date BETWEEN DATE '2015-01-01'
    AND DATE '2025-12-31' EACH INTERVAL '1' YEAR);

-- Mixed granularity (coarse old, fine recent)
PARTITION BY RANGE_N(order_date BETWEEN
    DATE '2015-01-01' AND DATE '2019-12-31' EACH INTERVAL '1' YEAR,
    DATE '2020-01-01' AND DATE '2024-12-31' EACH INTERVAL '1' MONTH,
    DATE '2025-01-01' AND DATE '2025-12-31' EACH INTERVAL '1' DAY,
    NO RANGE, UNKNOWN);

-- Numeric ranges
PARTITION BY RANGE_N(customer_id BETWEEN 1 AND 1000000 EACH 10000);
```

## CASE_N Function

```sql
PARTITION BY CASE_N(
    revenue < 10000,
    revenue < 100000,
    revenue < 1000000,
    NO CASE, UNKNOWN);
-- Partition 1: <10K, 2: 10K-100K, 3: 100K-1M, 4: ≥1M, 5: NULL
```

## Procedure: Create a Partitioned Table

### Single-Level PPI (Date)

```sql
CREATE TABLE mydb.sales (
    sale_id       INTEGER NOT NULL,
    sale_date     DATE NOT NULL,
    store_id      INTEGER,
    amount        DECIMAL(13,2)
) PRIMARY INDEX (sale_id)
  PARTITION BY RANGE_N(sale_date BETWEEN DATE '2020-01-01'
      AND DATE '2025-12-31' EACH INTERVAL '1' MONTH,
      NO RANGE, UNKNOWN);
```

### Multi-Level PPI

```sql
CREATE TABLE mydb.orders (
    order_id      INTEGER NOT NULL,
    order_date    DATE NOT NULL,
    region_id     INTEGER NOT NULL,
    product_id    INTEGER NOT NULL,
    quantity      INTEGER
) UNIQUE PRIMARY INDEX (order_id)
  PARTITION BY (
    RANGE_N(order_date BETWEEN DATE '2020-01-01'
        AND DATE '2025-12-31' EACH INTERVAL '1' MONTH),
    RANGE_N(region_id BETWEEN 1 AND 100 EACH 25)
  );
-- 72 months × 4 regions = 288 combined partitions
```

### Column Partitioned

```sql
CREATE TABLE mydb.wide_facts (
    id        INTEGER,
    txn_date  DATE,
    metric1   DECIMAL(10,2),
    metric2   DECIMAL(10,2),
    metric3   DECIMAL(10,2),
    dim1      VARCHAR(50),
    dim2      VARCHAR(50)
) NO PRIMARY INDEX
  PARTITION BY COLUMN;
```

### Combined Row + Column

```sql
CREATE TABLE mydb.hybrid_facts (
    id        INTEGER,
    txn_date  DATE,
    metric1   DECIMAL(10,2),
    metric2   DECIMAL(10,2)
) NO PRIMARY INDEX
  PARTITION BY (
    COLUMN,
    RANGE_N(txn_date BETWEEN DATE '2020-01-01'
        AND DATE '2025-12-31' EACH INTERVAL '1' DAY)
  );
```

## Procedure: Sliding Window Maintenance

```sql
-- Drop oldest month, add future month, delete dropped rows
ALTER TABLE mydb.sales MODIFY PRIMARY INDEX
  DROP RANGE BETWEEN DATE '2020-01-01' AND DATE '2020-01-31'
      EACH INTERVAL '1' DAY
   ADD RANGE BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'
      EACH INTERVAL '1' DAY
  WITH DELETE;

-- Archive dropped rows to another table instead of deleting
ALTER TABLE mydb.sales MODIFY PRIMARY INDEX
  DROP RANGE BETWEEN DATE '2020-01-01' AND DATE '2020-01-31'
      EACH INTERVAL '1' DAY
   ADD RANGE BETWEEN DATE '2026-01-01' AND DATE '2026-01-31'
      EACH INTERVAL '1' DAY
  WITH INSERT INTO mydb.sales_archive;
```

### Sliding Window Best Practices

- Define ~10% extra partitions for future dates
- Automate ALTER TABLE on a monthly schedule
- Drop statistics on PARTITION column before ALTER, recollect after
- Delete rows before ALTER if secondary indexes exist (reduces lock time)
- Dropping empty partitions is nearly instantaneous

## Partition Elimination

The optimizer skips partitions that cannot contain matching rows:

### Static Elimination (Compile Time)

```sql
WHERE sale_date = DATE '2025-01-15'           -- single partition
WHERE sale_date BETWEEN DATE '2025-01-01' AND DATE '2025-03-31'  -- 3 months
WHERE sale_date IN (DATE '2025-01-01', DATE '2025-02-01')        -- 2 partitions
```

### Dynamic Elimination (Runtime)

Occurs during joins when one side supplies partition-filtering values.

### Elimination Killers

- Functions on the partition column: `WHERE EXTRACT(YEAR FROM sale_date) = 2025`
- Arithmetic on the partition column: `WHERE sale_date + 1 = DATE '2025-01-16'`
- Missing partition column in WHERE clause

### Verify with EXPLAIN

```sql
EXPLAIN SELECT * FROM mydb.sales WHERE sale_date = DATE '2025-06-15';
-- Look for: "...accessing N partitions..."
```

## Performance: PPI vs NPPI

| Operation | NPPI | PPI (2557 parts) |
|---|---|---|
| PI access (no date filter) | 0.013s | 27s |
| PI access (with date) | 0.02s | 0.06s |
| 7-day range scan | 332s | 2s |
| Tactical join (1 AMP) | <1s | 66s |

**Row overhead:** 2 bytes/row (2-byte), 8 bytes/row (8-byte partitioning)

## 2-Byte vs 8-Byte Partitioning

| Feature | 2-Byte | 8-Byte |
|---|---|---|
| Max combined partitions | 65,535 | 9.2 quintillion |
| Max levels | 15 | 62 |
| Row overhead | 2 bytes | 8 bytes |
| Triggered when | ≤65,535 combined | >65,535 combined |

## Catalog Discovery

```sql
-- List all partitioned tables
SELECT DatabaseName, TableName, PartitioningLevels,
       ColumnPartitioningLevel, DefinedCombinedPartitions
FROM DBC.PartitioningConstraintsV
ORDER BY DatabaseName, TableName;

-- Show partition expression
SELECT DatabaseName, TableName, ConstraintText
FROM DBC.IndexConstraintsV
WHERE ConstraintType = 'Q'
ORDER BY DatabaseName, TableName;

-- Count rows per partition
SELECT PARTITION, COUNT(*) AS row_count
FROM mydb.sales
GROUP BY PARTITION
ORDER BY PARTITION;
```

## Column Partitioning Storage

| Format | Storage | Best For |
|---|---|---|
| COLUMN (container) | Multiple values packed into ~8KB containers | Most CP tables; autocompression |
| ROW (subrow) | Each value as separate physical row | UPI tables; in-place updates |

### Autocompression Techniques (System-Selected)

- Null compression
- Run-length compression
- Local value-list (dictionary per container)
- Trim compression (high-order zeros, trailing pads)
- Delta from mean
- Unicode to UTF8

## Common Errors and Solutions

| Error | Cause | Fix |
|---|---|---|
| `Row out of partition range` | Data outside defined ranges | Add NO RANGE or extend range |
| `Too many partitions` | Combined count exceeds 2-byte limit | Use 8-byte partitioning or reduce levels |
| `ALTER TABLE failed` | Statistics on PARTITION column | Drop stats before ALTER, recollect after |
| Poor PI access performance | Missing date in WHERE | Always include partition column in query |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-partitioning", path="references/FILENAME")` — do NOT call `list`.

- [PPI Joins & Optimization](./references/ppi-joins-and-optimization.md) — Sliding-window joins, DPE, rowkey merge, SI access with PPI, PPICacheThrP, EXPLAIN interpretation
- [Column Partitioning](./references/column-partitioning.md) — PARTITION BY COLUMN syntax, PRIMARY AMP INDEX, COLUMN ALL BUT, container internals, autocompression, loading CP tables, CP join indexes
- [ALTER TABLE & Expression Rules](./references/alter-and-expression-rules.md) — ALTER TABLE DROP/ADD RANGE, multilevel ALTER, REVALIDATE PRIMARY INDEX, expression restrictions, PARTITION system columns, load utilities, backup/restore partitions, locking
- [8-Byte Partitioning](./references/8-byte-partitioning.md) — BIGINT/TIMESTAMP partitioning, >65K partitions, row/index overhead, 8-byte limitations (no exclusion DPE, no full outer rowkey merge), ADD option, design methodology
- [Columnar Production Patterns](./references/columnar-production-patterns.md) — Real-world CP deployments (event capture, marketing, analytics), PA vs PI vs NoPI decision guide, staged INSERT-SELECT loading, n-way join optimization, mirror table pattern for updates, IntelliFlex benchmarks
