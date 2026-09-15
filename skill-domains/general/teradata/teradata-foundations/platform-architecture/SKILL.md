---
name: teradata-architecture
description: 'Teradata Vantage architecture including shared-nothing MPP, AMPs, PEs, BYNET, primary indexes (PI/UPI/NUPI), secondary indexes (USI/NUSI), join indexes, hash indexes, data distribution, storage (FSG cache, cylinder packing), fallback, journaling, and AMP architecture. Use when designing tables with proper primary indexes, understanding data distribution and skew, choosing between UPI/NUPI, creating secondary or join indexes, or diagnosing performance related to architecture.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Architecture

## When to Use

- Designing tables with proper primary indexes for data distribution
- Understanding shared-nothing MPP architecture
- Diagnosing data skew
- Choosing between UPI, NUPI, NoPI
- Creating secondary indexes (USI/NUSI) and join indexes
- Understanding storage architecture (FSG cache, cylinders)
- Configuring fallback and journaling

## Core Architecture: Shared-Nothing MPP

```
Client Applications
        │
   ┌────▼────┐
   │   PE    │  Parsing Engine — parses SQL, generates plans
   │  (CLI)  │  distributes work to AMPs
   └────┬────┘
        │  BYNET (high-speed interconnect)
   ┌────┼────┬────┬────┐
   │AMP1│AMP2│AMP3│AMPN│  Access Module Processors
   │ D1 │ D2 │ D3 │ DN │  Each AMP owns exclusive data (vdisks)
   └────┴────┴────┴────┘
```

### Key Components

| Component | Role |
|---|---|
| **PE** (Parsing Engine) | Parses SQL, optimizes, dispatches |
| **AMP** (Access Module Processor) | Stores and retrieves data; each owns vdisks |
| **BYNET** | Dual redundant interconnect for PE↔AMP and AMP↔AMP |
| **Vdisk** | Virtual disk — logical storage unit owned by one AMP |
| **Node** | Physical server with multiple AMPs |
| **Clique** | Group of nodes sharing disk arrays (for failover) |

## Primary Index and Data Distribution

### Hash Distribution

```
Row → PI columns → Hash Function → Hash Bucket → AMP
```

Every row is distributed to exactly one AMP based on its Primary Index hash value. **Good distribution = even row counts across AMPs.**

### Primary Index Types

| Type | Syntax | Duplicates | Best For |
|---|---|---|---|
| **UPI** (Unique PI) | `UNIQUE PRIMARY INDEX (col)` | No | Lookup tables, dimension tables |
| **NUPI** (Non-Unique PI) | `PRIMARY INDEX (col)` | Yes | Fact tables, natural keys |
| **NoPI** | `NO PRIMARY INDEX` | N/A | Staging, column-partitioned |

### Choosing a Primary Index

1. **Even distribution** — Choose columns with many distinct values
2. **Access pattern** — Choose columns frequently used in WHERE/JOIN
3. **Uniqueness** — UPI if possible (eliminates duplicate row checks)
4. **Multi-column** — Combine columns for uniqueness: `PRIMARY INDEX (col1, col2)`

```sql
-- Check distribution
SELECT HASHAMP(HASHBUCKET(HASHROW(pi_col))) AS amp_number,
       COUNT(*) AS row_count
FROM mydb.large_table
GROUP BY 1
ORDER BY 2 DESC;

-- Check skew factor
SELECT (MAX(row_count) - AVG(row_count)) / NULLIFZERO(AVG(row_count)) * 100 AS skew_pct
FROM (SELECT COUNT(*) AS row_count
      FROM mydb.large_table
      GROUP BY HASHAMP(HASHBUCKET(HASHROW(pi_col)))) t;
```

### Data Skew Impact

| Skew % | Impact |
|---|---|
| 0-5% | Acceptable |
| 5-20% | Monitor; may cause hotspot AMPs |
| >20% | Redesign PI; consider multi-column PI |

## Secondary Indexes

### USI (Unique Secondary Index)

```sql
CREATE UNIQUE INDEX (email) ON mydb.customers;
```

- 2-AMP operation: hash to subtable AMP → follow pointer to base AMP
- No data redistribution
- Excellent for point lookups on non-PI columns

### NUSI (Non-Unique Secondary Index)

```sql
CREATE INDEX (region_code) ON mydb.orders;
```

- All-AMP operation (subtable on every AMP)
- Best for low-selectivity conditions with many matching rows
- Can use bit mapping for AND/OR combinations

### When to Use Secondary Indexes

| Use Case | Index Type |
|---|---|
| Unique lookup on non-PI column | USI |
| Range scan on non-PI column | NUSI (with value-ordered) |
| Covering queries (avoid base table) | NUSI with included columns |
| Infrequent queries | Don't index — overhead not justified |

## Join Indexes

Pre-materialized joins stored on disk:

```sql
CREATE JOIN INDEX mydb.ji_order_customer AS
SELECT o.order_id, o.order_date, o.amount,
       c.customer_name, c.region
FROM mydb.orders o
INNER JOIN mydb.customers c ON o.customer_id = c.customer_id
PRIMARY INDEX (order_id);
```

- Automatically maintained on DML
- Optimizer uses transparently when it matches a query
- Can include aggregations (aggregate join index)

### Aggregate Join Index

```sql
CREATE JOIN INDEX mydb.ji_daily_sales AS
SELECT store_id, sale_date, SUM(amount) AS total_amount, COUNT(*) AS txn_count
FROM mydb.sales
GROUP BY store_id, sale_date
PRIMARY INDEX (store_id);
```

## Hash Index

Single-table materialized index:

```sql
CREATE HASH INDEX mydb.hi_customer_region ON mydb.customers
ORDER BY (region_code);
```

## Storage Architecture

### FSG Cache (File Segment Cache)

- In-memory cache of disk blocks
- Configurable size per AMP
- LRU replacement policy
- Critical for read performance

### Cylinder Packing

Data stored in cylinders on vdisks. Full cylinders = fewer I/Os.

### Fallback

```sql
-- Table with fallback (second copy on different AMP)
CREATE TABLE mydb.critical_data (...) WITH FALLBACK;

-- No fallback (default)
CREATE TABLE mydb.staging_data (...) NO FALLBACK;
```

- Doubles storage but provides AMP-level fault tolerance
- Fallback copy always on a different AMP (different clique preferred)

### Journaling

```sql
CREATE TABLE mydb.audit_table (...)
WITH JOURNAL TABLE = mydb.journal_tbl;
```

| Journal Type | Purpose |
|---|---|
| Before Image | Recovery of rolled-back transactions |
| After Image | Forward recovery after restore |
| Dual | Both before and after images |

## Table Types

```sql
CREATE SET TABLE ...        -- No duplicate rows (default pre-14.0)
CREATE MULTISET TABLE ...   -- Allows duplicate rows (default 14.0+)
```

| Type | Duplicates | Performance |
|---|---|---|
| SET | Rejected | Slower INSERT (duplicate check) |
| MULTISET | Allowed | Faster INSERT |

## Key Dictionary Views

| View | Content |
|---|---|
| `DBC.TablesV` | All tables, views, macros |
| `DBC.ColumnsV` | Column definitions |
| `DBC.IndicesV` | Index definitions |
| `DBC.AllSpaceV` | Space usage per database |
| `DBC.TableSizeV` | Table sizes |
| `DBC.DiskSpaceV` | Disk space by AMP |
| `DBC.AMPUsage` | AMP-level metrics |

```sql
-- Table size by AMP (check for skew)
SELECT Vproc AS amp, CurrentPerm / 1e6 AS perm_mb
FROM DBC.TableSizeV
WHERE DatabaseName = 'mydb' AND TableName = 'orders'
ORDER BY perm_mb DESC;
```

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-architecture", path="references/FILENAME")` — do NOT call `list`.

- [MAPS & Hash Distribution](./references/maps-and-distribution.md) — Hash map internals (20-bit buckets), contiguous/sparse maps, CREATE MAP, ALTER TABLE MAP, colocation, TDMaps stored procedures, cross-map join rules, DBQL MAPS columns, DBS Control settings, elasticity (TCore, WM COD, Elastic TCore)
- [MAPS Architecture Deep Dive](./references/maps-architecture-deep-dive.md) — Contiguous vs sparse map concepts, system expansion procedures (Reconfig options), map migration strategies (ALTER TABLE MAP, TDMaps procedures, Viewpoint workflow), space management during expansion, DSA backup/restore with maps, legacy ARCMain limitations, data dictionary map expansion tradeoffs, sparse map candidate selection, colocation, cross-map join/skew behavior, MAPS administration checklist
- [Storage and Cache Architecture](./references/storage-and-cache-architecture.md) — Physical storage hierarchy (vdisks, cylinders, data blocks), FSG cache internals (LRU, cache hit/miss), Master Index and Cylinder Index, block-level compression, WAL (Write-Ahead Logging), PE/AMP/BYNET internals, clique architecture, cylinder packing
- [Index Selection & Join Strategies](./references/indexes-and-joins.md) — PI selection criteria, USI/NUSI decision guide, value-ordered NUSI, SI space estimation, join index patterns (STJI, aggregate JI), JI restrictions, merge/hash/product join strategies, redistribution options, storage hierarchy (Master Index, cylinders, data blocks, FSG cache, Extent IDs)
