# Index Selection Guide & Join Strategies

## Index Selection Decision Matrix

### Choosing a Primary Index

```
Is there a natural unique key used in most queries?
├── Yes → Use UPI on that key
│         ├── Also used in joins? → Optimal
│         └── Not used in joins? → Consider if NUPI on join column performs better
└── No → Use NUPI on most-queried column(s)
         ├── Even distribution? → Good
         └── Skewed? → Add column(s) for uniqueness or consider NoPI
```

### PI Selection Criteria (Ranked)

1. **Even distribution** (most important) — high distinct values, no dominant value
2. **Frequent access** — columns used in WHERE/JOIN >80% of queries
3. **Uniqueness** — UPI eliminates SET table duplicate checking overhead
4. **Volatility** — avoid columns that are frequently updated (PI update = delete + reinsert)

### When to Use NoPI

| Scenario | Recommendation |
|---|---|
| Staging tables loaded by FastLoad | NoPI (block-level load, no hash distribution) |
| Column-partitioned tables | NoPI or PA (Primary AMP Index) |
| Tables never joined on any column | NoPI acceptable |
| Temporary ETL holding tables | NoPI |

---

## Secondary Index Decision Guide

### USI (Unique Secondary Index)

- **2-AMP operation**: hash to subtable AMP → follow pointer to base AMP
- **Space overhead**: Subtable on one AMP per value
- **Locking**: Rowhash lock (lightweight)

```sql
CREATE UNIQUE INDEX (email) ON mydb.customers;
-- Point lookup: SELECT * FROM customers WHERE email = 'a@b.com'
-- → 2 I/Os (1 subtable + 1 base table)
```

**Use when:**
- Column requires unique constraint but is not the PI
- Frequent point lookups on non-PI column
- Acceptable to add 2-AMP overhead to inserts

### NUSI (Non-Unique Secondary Index)

- **All-AMP operation**: Subtable stored locally on every AMP
- **Space overhead**: Proportional to base table rows (one subtable entry per row)

```sql
CREATE INDEX (region_code) ON mydb.orders;
-- Query: SELECT * FROM orders WHERE region_code = 'EAST'
-- → All-AMP scan of local subtable + base table rows
```

**Use when:**
- Low selectivity (many rows match) — reading all AMPs is acceptable
- Column used in AND conditions (bit-mapped NUSI combination)
- Covering queries (all needed columns in NUSI + base PI)

### NUSI Ordering

| Type | Syntax | Behavior |
|---|---|---|
| Hash-ordered (default) | `CREATE INDEX (col) ON t` | Subtable ordered by hash of index col |
| Value-ordered | `CREATE INDEX (col) ORDER BY VALUES ON t` | Subtable ordered by index col value |

**Value-ordered NUSI** benefits:
- Range conditions: `WHERE order_date BETWEEN ...`
- Group by / aggregate on the index column
- Covering index range scans

### Secondary Index Space Estimation

```sql
-- Estimate SI subtable size
SELECT 'USI' AS idx_type,
       COUNT(DISTINCT email) * 30 / 1e6 AS est_mb  -- ~30 bytes per USI entry
FROM mydb.customers;

SELECT 'NUSI' AS idx_type,
       COUNT(*) * 20 / 1e6 AS est_mb  -- ~20 bytes per NUSI entry, per AMP
FROM mydb.orders;
```

---

## Join Index Design Patterns

### Single-Table Join Index (STJI)

Redistributed copy of selected columns from one table:

```sql
-- Redistribute customer for store_id joins
CREATE JOIN INDEX mydb.ji_cust_by_store AS
  SELECT customer_id, store_id, customer_name, region
  FROM mydb.customers
  PRIMARY INDEX (store_id);
-- Optimizer uses JI when query joins on store_id
```

### Multi-Table Aggregate Join Index

Pre-materialized star schema aggregation:

```sql
CREATE JOIN INDEX mydb.ji_daily_sales AS
  SELECT s.sale_date, p.category, r.region_name,
         SUM(s.amount) AS total_sales,
         COUNT(*) AS txn_count
  FROM mydb.sales s
  JOIN mydb.products p ON s.product_id = p.product_id
  JOIN mydb.regions r ON s.region_id = r.region_id
  GROUP BY s.sale_date, p.category, r.region_name
  PRIMARY INDEX (sale_date);
```

### Join Index Restrictions

| Feature | Supported? |
|---|---|
| PI / NUPI / UPI | Yes |
| PPI (RANGE_N/CASE_N) | Yes (noncompressed JI only) |
| Column partitioning | Yes (single-table, nonaggregate, noncompressed) |
| Fallback | Yes |
| Secondary indexes on JI | No |
| Join index on join index | No |
| Triggers on JI | No |
| Foreign keys referencing JI | No |

### Join Index Maintenance Cost

JI is automatically maintained on every INSERT/UPDATE/DELETE to base table(s). Consider:
- Write-heavy tables → JI maintenance overhead may exceed query benefit
- Multiple JI on same table → cumulative overhead

---

## Join Strategies (Optimizer)

### Merge Join

Both inputs sorted by join columns. Matched by walking through both in order.

**Conditions:** Join columns = PI of both tables, or data redistributed/duplicated to achieve this.

**Variants:**
- **Inclusion merge join**: Standard equijoin
- **Exclusion merge join**: NOT IN / anti-join
- **Rowkey-based merge join**: Both tables same PI + same PPI

### Hash Join

One input hashed into memory, other probed against it.

**Conditions:** Smaller input fits in memory (or spills to spool).

### Product Join

Nested-loop: every row of one input compared to every row of other.

**Warning:** Usually bad (O(n×m)). Acceptable only when one side has very few rows.

### Redistribution Strategies

| Strategy | Description |
|---|---|
| Direct | Both tables same PI on join columns → no redistribution |
| Redistribute one | Smaller table redistributed to match larger table's PI |
| Redistribute both | Both tables redistributed to new common PI |
| Duplicate one | Small table duplicated to all AMPs (broadcast) |
| Local (same AMP) | Both tables already on same AMP (e.g., colocated sparse map) |

---

## Teradata Vantage Storage Hierarchy

```
Master Index (per AMP)
├── Cylinder Index [1..n]
│   ├── Data Block [1..m]
│   │   └── Rows [1..k] (sorted by row hash within block)
│   └── Data Block [...]
└── Cylinder Index [...]
```

### Data Block

- Minimum: 1 sector (512 bytes for HDD, 4 KB for SSD)
- Maximum: 127.5 KB (255 sectors × 512 bytes) or 1 MB in some configurations
- Rows within a block are sorted by row hash (unique within partition)

### Cylinder

- Logical grouping of contiguous data blocks on a vdisk
- Cylinder packing: fill cylinders fully → fewer random I/Os
- Full cylinder read = one I/O operation (sequential)

### Extent IDs

Modern TVS (Teradata Virtual Storage) uses Extent IDs instead of physical addresses:
- Decouples logical from physical placement
- Enables temperature-based placement (hot data on SSD, cold on HDD)
- pdisks: physical disk abstraction
- Subpools: groups of 3 AMPs + TVS vproc (unit of migration for folding/unfolding)

### FSG Cache (File Segment Cache)

- In-memory cache of disk blocks per AMP
- LRU replacement policy
- `FSGCacheSize` in DBS Control controls size
- Critical for read performance — reduces physical I/O

---

## Key Dictionary Views

| View | Content | Key Columns |
|---|---|---|
| `DBC.TablesV` | All tables, views, macros | TableKind, MapName, PartitioningLevels |
| `DBC.ColumnsV` | Column definitions | ColumnType, Nullable, DefaultValue |
| `DBC.IndicesV` | All indexes | IndexType, UniqueFlag, IndexName |
| `DBC.AllSpaceV` | Space by database | CurrentPerm, MaxPerm, PeakSpool |
| `DBC.TableSizeV` | Table sizes by AMP | CurrentPerm, PeakPerm, Vproc |
| `DBC.DiskSpaceV` | Disk space by AMP | CurrentPerm, MaxPerm, CurrentSpool |
| `DBC.AMPUsage` | AMP metrics | CPUTime, DiskIO |
| `DBC.Maps` | Map definitions | MapName, MapKind, SystemDefault |

### Quick Diagnostic Queries

```sql
-- Data skew for a table
SELECT Vproc AS amp,
       CurrentPerm / 1e6 AS perm_mb
FROM DBC.TableSizeV
WHERE DatabaseName = 'mydb' AND TableName = 'orders'
ORDER BY perm_mb DESC;

-- Skew factor (%)
SELECT (MAX(cp) - AVG(cp)) / NULLIFZERO(AVG(cp)) * 100 AS skew_pct
FROM (SELECT SUM(CurrentPerm) AS cp
      FROM DBC.TableSizeV
      WHERE DatabaseName = 'mydb' AND TableName = 'orders'
      GROUP BY Vproc) t;

-- All indexes on a table
SELECT IndexNumber, IndexType, UniqueFlag, IndexName, ColumnName
FROM DBC.IndicesV
WHERE DatabaseName = 'mydb' AND TableName = 'orders'
ORDER BY IndexNumber, ColumnPosition;

-- Space trending (if ResUsage enabled)
SELECT TheDate, SUM(CurrentPerm) / 1e9 AS total_perm_gb
FROM DBC.DiskSpaceV
WHERE DatabaseName = 'mydb'
GROUP BY TheDate
ORDER BY TheDate;
```
