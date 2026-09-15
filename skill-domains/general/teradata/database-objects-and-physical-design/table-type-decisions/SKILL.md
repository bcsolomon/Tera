---
name: teradata-nopi-tables
description: 'Design and manage Teradata NoPI (No Primary Index) tables for staging, ETL, and bulk load scenarios. Use when choosing between PI and NoPI table designs, optimizing Fastload/TPT bulk ingestion, building staging area architectures, or understanding NoPI storage mechanics and query performance implications.'
metadata:
  author: teradata-expert
  version: "1.0"
---

# Teradata NoPI (No Primary Index) Tables

## When to Use

- Creating staging tables for FastLoad, TPT, or Mini-Batch ETL pipelines
- Choosing between PI and NoPI table designs for data ingestion
- Optimizing bulk load performance (eliminating sort phase, reducing redistribution)
- Building ELT staging areas where index design is deferred
- Using sandbox/exploratory tables before determining a proper PI
- Understanding query access-path trade-offs on NoPI tables
- Converting NoPI staging data into PI target tables

## Core Concepts

### What Is a NoPI Table?

A NoPI table has **no primary index**. Rows are not hash-distributed by any column. Instead, the system assigns an internally generated hashcode and appends rows to the end of the table on whichever AMP receives them. This eliminates redistribution and sorting during loads.

| Aspect | PI Table | NoPI Table |
|---|---|---|
| Row distribution | Hash of PI columns → owning AMP | Random AMP assignment, rows appended |
| Sort requirement | Rows sorted by rowhash within AMP | No sort — rows appended in arrival order |
| Duplicate rows | SET tables reject dupes; MULTISET allows | Always MULTISET — duplicates allowed |
| Single-AMP access | PI equality → single AMP | Not possible — always all-AMP scan |
| FastLoad sort phase | Required (10-30% of elapsed time) | Eliminated entirely |
| INSERT-SELECT target | Redistributes to PI-owning AMPs | Local append — no redistribution |

### When to Use PI vs NoPI

| Scenario | Recommendation |
|---|---|
| OLTP / frequent equality lookups | PI table (single-AMP access) |
| Staging for FastLoad / TPT | **NoPI** — fastest ingestion |
| Sandbox / exploratory analysis | **NoPI** — defer PI decision |
| Log / audit trail table | **NoPI** — append-only writes |
| Join-heavy analytics on large tables | PI table (AMP-local joins) |
| Mini-Batch ELT staging | **NoPI** staging → INSERT-SELECT to PI target |

## Procedure: Create a NoPI Table

### Explicit NO PRIMARY INDEX

```sql
CREATE MULTISET TABLE staging_db.sales_stage, FALLBACK,
     NO BEFORE JOURNAL, NO AFTER JOURNAL,
     CHECKSUM = DEFAULT
     (
      item_nbr   INTEGER NOT NULL,
      sale_date   DATE FORMAT 'YYYY-MM-DD' NOT NULL,
      item_count  INTEGER,
      amount      DECIMAL(13,2)
     )
NO PRIMARY INDEX;
```

### CREATE TABLE AS … NO PRIMARY INDEX

```sql
CREATE MULTISET TABLE staging_db.sales_copy
AS (SELECT * FROM prod_db.sales)
WITH DATA
NO PRIMARY INDEX;
```

### Using PrimaryIndexDefault DBSControl

When `PrimaryIndexDefault = N`, omitting the PI clause creates a NoPI table:

```sql
-- With PrimaryIndexDefault = N, this creates a NoPI table
CREATE MULTISET TABLE staging_db.auto_nopi
     (col1 INTEGER, col2 VARCHAR(100));
```

Settings: `D` (default = P), `P` (first column as NUPI), `N` (NoPI).

## Procedure: Optimize Bulk Loads into NoPI

### FastLoad into NoPI

FastLoad eliminates the sort phase entirely for NoPI targets. Rows are sent in 64 KB blocks (vs 4 KB redistribution buffers for PI tables) and appended directly.

Key advantages:
- **Sort phase eliminated** — saves 10-30% of total elapsed time
- **Duplicate rows allowed** — unlike FastLoad into PI tables
- **Table readable during load** — use ACCESS lock to query while loading
- **64 KB redistribution buffers** — vs 4 KB for PI tables

> Source: 541-0007565-B02, §2.10, §3.1

### TPump Array INSERT into NoPI

All rows in a request are packed into a **single AMP step** regardless of system size or data clustering. On PI tables, rows scatter across AMPs, reducing packing efficiency.

```sql
-- TPump PACK factor applies; all rows go to one AMP step on NoPI
-- SERIALIZE should be OFF for NoPI (no PI-based hash lock contention)
```

- Set `SERIALIZE = OFF` — no PI-based hash lock contention on NoPI
- Keep TPump sessions ≤ number of AMPs — rowhash locks on NoPI lock many rows per AMP

> Source: 541-0007565-B02, §2.11

## Procedure: Convert NoPI to PI Table

### Method 1: CREATE TABLE AS with PI

```sql
CREATE MULTISET TABLE prod_db.sales_final
AS (SELECT * FROM staging_db.sales_stage)
WITH DATA
PRIMARY INDEX (item_nbr);
```

### Method 2: CREATE + INSERT-SELECT

```sql
CREATE MULTISET TABLE prod_db.sales_final, FALLBACK
     (
      item_nbr   INTEGER NOT NULL,
      sale_date   DATE FORMAT 'YYYY-MM-DD' NOT NULL,
      item_count  INTEGER,
      amount      DECIMAL(13,2)
     )
PRIMARY INDEX (item_nbr);

INSERT INTO prod_db.sales_final SELECT * FROM staging_db.sales_stage;
```

Both methods redistribute and sort data by the target PI. The redistribution cost is the trade-off for faster NoPI ingestion.

> Source: 541-0007565-B02, §2.2.2, §3.5.1

## NoPI Table Limitations

| Not Supported | Reason |
|---|---|
| SET tables | NoPI is always MULTISET |
| Partitioned Primary Index (PPI) | No PI to partition |
| Identity columns | Require PI-based distribution |
| Hash indexes | Require PI |
| Queue tables | Require PI ordering |
| Error tables | Require PI |
| Permanent journals | Not supported on NoPI |
| MultiLoad | Use FastLoad or TPump instead |
| UPSERT | Requires fully specified PI |
| MERGE-INTO (NoPI target) | Requires PI for UPSERT variant |

> Source: 541-0007565-B02, §2.1.1, §2.12

## What IS Supported on NoPI

- FALLBACK, secondary indexes (USI/NUSI), join indexes, reference indexes
- Primary key and foreign key constraints
- Global temporary and volatile tables
- LOBs (limit ~64K rows per AMP due to single hashcode)
- COLLECT/DROP STATISTICS
- UPDATE, DELETE (full-table scan without secondary index)
- Restore/Copy, FastExport, CheckTable, Table Rebuild, Reconfig

## Query Performance on NoPI Tables

- **No single-AMP access** — all SELECTs do full-table scans unless a secondary index exists
- **Joins require redistribution** — NoPI rows must be redistributed by join column before merge join
- **Add NUSI/USI** for selective queries on staging tables that are also queried
- **COLLECT STATISTICS** on NoPI columns used in joins to help Optimizer choose efficient plans

> Source: 541-0007565-B02, §2.7, §3.3

## Common Patterns

### Mini-Batch ELT Pipeline

```sql
-- 1. FastLoad into NoPI staging
-- (FastLoad script targets staging_db.sales_stage)

-- 2. Apply to PI target
INSERT INTO prod_db.sales SELECT * FROM staging_db.sales_stage;
-- or MERGE INTO prod_db.sales USING staging_db.sales_stage ...

-- 3. Clean staging
DELETE FROM staging_db.sales_stage;
-- Alternative: DROP and recreate
```

### Union Staging + Base for Real-Time View

```sql
SELECT * FROM prod_db.sales
UNION ALL
SELECT * FROM staging_db.sales_stage;
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Data skew after Reconfig/Restore | NoPI has ~1 hash bucket per AMP; expanding AMPs leaves some empty | INSERT-SELECT into PI table, then back to new NoPI |
| Slow SELECT on staging table | Full-table scan — no PI access path | Add NUSI on frequently filtered columns |
| TPump sessions blocking each other | Rowhash lock covers many rows per AMP | Limit sessions ≤ number of AMPs |
| INSERT-SELECT into NoPI is skewed | Constrained SELECT returns imbalanced data, locally appended | Use unconstrained SELECT or rebalance afterward |
| CheckTable slow on NoPI with USI | Single hashcode per AMP makes duplicate check expensive | Expected for NoPI; avoid USI on large staging tables |
| Error 9107 | MultiLoad attempted on NoPI table | Use FastLoad or TPump instead |
| Error 9252 | Invalid operation on NoPI (e.g., UPSERT) | Use separate UPDATE + INSERT instead |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-nopi-tables", path="references/FILENAME")` — do NOT call `list`.

- [NoPI Design and Operations](references/nopi-design-and-operations.md) — storage internals, syntax, load optimization, conversion, data skew scenarios
