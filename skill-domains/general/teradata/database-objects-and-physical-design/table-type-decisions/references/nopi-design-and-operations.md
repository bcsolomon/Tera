# NoPI Design and Operations Reference

Comprehensive reference for Teradata NoPI (No Primary Index) table internals, syntax, load optimization, query behavior, conversion strategies, and operational considerations.

> Source: 541-0007565-B02 — "No Primary Index (NoPI) Table User Guide" (Teradata Orange Book)

---

## NoPI Storage Internals

### Row Distribution and Hash Mechanics

In a PI table, each row's hashcode is derived from its primary index columns, determining which AMP owns and stores the row. In a NoPI table, there is **no primary index** — the system internally selects a hash bucket from the AMP's hash map and assigns it to each row. Rows are appended to the end of the table in arrival order rather than inserted at a sorted position within a hash sequence.

Key internal details:

- Each row still has a **rowid** (hashcode + uniqueness) — the hashcode is internally generated, not derived from data columns.
- The uniqueness portion is extended to use **44 bits** out of the available 64 bits in a rowid (vs. 32 bits for PI tables).
- Normally **one hash bucket per AMP** is used for all rows in a NoPI table. This means a NoPI table behaves like a very highly non-unique NUPI table from a hash-bucket perspective.
- Reconfig and Restore/Copy operations may increase the number of hash buckets per AMP.

> Source: 541-0007565-B02, §1.2, §2.6.2

### Row Insertion Strategy

For single-statement and multi-statement INSERT, rows are sent to AMPs via a **random generator** designed to distribute data across AMPs evenly:

- Each new request generally targets a **different AMP** from the previous request.
- For INSERT-SELECT into a NoPI target, data is **locally appended** — no redistribution occurs regardless of the source table type.
- Constrained INSERT-SELECT can cause skew if the selected data is unevenly distributed across source AMPs.

> Source: 541-0007565-B02, §2.6.2

### Cylinder Packing and Append Behavior

Since rows are always appended to the end of a NoPI table:

- New data blocks fill sequentially — no need to find insertion points within sorted hash sequences.
- Cylinder packing is straightforward: blocks fill in order, yielding efficient sequential I/O during full-table scans.
- No row movement or splitting occurs during inserts (unlike PI tables where rows must be placed at their hash-sorted position).

---

## CREATE TABLE Syntax and Options

### Explicit NO PRIMARY INDEX

```sql
CREATE MULTISET TABLE staging_db.sales_stage, FALLBACK,
     NO BEFORE JOURNAL,
     NO AFTER JOURNAL,
     CHECKSUM = DEFAULT
     (
      item_nbr    INTEGER NOT NULL,
      sale_date   DATE FORMAT 'YYYY-MM-DD' NOT NULL,
      item_count  INTEGER,
      amount      DECIMAL(13,2)
     )
NO PRIMARY INDEX;
```

### CREATE TABLE AS with NO PRIMARY INDEX

```sql
CREATE MULTISET TABLE staging_db.sales_copy
AS (SELECT * FROM prod_db.sales)
WITH DATA
NO PRIMARY INDEX;
```

The source table can be either a PI or NoPI table.

> Source: 541-0007565-B02, §2.1

### PrimaryIndexDefault DBSControl Field

Controls default behavior when no PI/NoPI clause is specified:

| Setting | Behavior |
|---|---|
| `D` | Default — same as `P` |
| `P` | First column becomes NUPI (legacy behavior) |
| `N` | Table created as NoPI |

```sql
-- With PrimaryIndexDefault = N, this creates a NoPI table
CREATE MULTISET TABLE staging_db.auto_nopi
     (col1 INTEGER, col2 VARCHAR(100));
```

> When neither `PRIMARY INDEX`, `NO PRIMARY INDEX`, `PRIMARY KEY`, nor `UNIQUE` constraint is specified, the PrimaryIndexDefault setting determines table type. If PRIMARY KEY or UNIQUE constraint is specified (but not PI/NoPI), that constraint becomes the UPI regardless of PrimaryIndexDefault.

> Source: 541-0007565-B02, §2.1

### Supported Table Attributes

| Attribute | Supported? | Notes |
|---|---|---|
| FALLBACK | Yes | Works same as PI table |
| Secondary Indexes (USI/NUSI) | Yes | Same access paths as PI table |
| Join Indexes | Yes | Maintained same as PI table |
| Reference Indexes | Yes | |
| Primary Key constraint | Yes | Creates unique index, not a PI |
| Foreign Key constraint | Yes | |
| Global Temporary table | Yes | |
| Volatile table | Yes | |
| LOBs (Large Objects) | Yes | ~64K row limit per AMP (single hashcode) |
| MULTISET | Yes (always) | NoPI tables are always MULTISET |

### Not Supported on NoPI

| Attribute | Reason |
|---|---|
| SET table | NoPI requires MULTISET |
| Partitioned Primary Index (PPI) | No PI to partition |
| Identity Column | Requires PI distribution |
| Hash Index | Requires PI |
| Queue Table | Requires PI ordering |
| Error Table | Requires PI |
| Permanent Journals | Not supported |

> Source: 541-0007565-B02, §2.1.1, §2.1.2

---

## FastLoad with NoPI: Performance Gains

### Acquisition Phase

In a PI FastLoad, rows are redistributed to their hash-owning AMPs via **4 KB redistribution buffers**. For NoPI:

- Rows are sent in **64 KB blocks** to a randomly selected AMP.
- No per-row hashing or redistribution — the entire block goes to one AMP.
- The random AMP selection ensures data is eventually balanced across AMPs (even when FastLoad sessions < number of AMPs).

### Sort Phase — Eliminated

The FastLoad sort phase typically consumes **10-30% of total elapsed time**. For NoPI targets, this phase is **completely eliminated** — rows are already in final form after acquisition.

> Source: 541-0007565-B02, §2.10, §3.1

### Duplicate Row Handling

- PI FastLoad: Duplicate rows from input source are discarded (sort eliminates all duplicates, including legitimate ones).
- **NoPI FastLoad**: Duplicate rows **are loaded** — no sort means true duplicates from the data source are preserved. Only restart-related resend duplicates are removed via a separate recovery scheme.

> Source: 541-0007565-B02, §2.10.2

### Table Accessibility During Load

- PI table: Cannot be read until sort phase completes.
- **NoPI table**: Can be read with an **ACCESS lock** while FastLoad is running, because rows are appended in final position during acquisition.

### Error Tables

Two error tables are created for every FastLoad job:
1. **Error table 1** — constraint violations, conversion errors (acquisition phase). Same for PI and NoPI.
2. **Error table 2** — unique PI violations (sort phase). Created for NoPI but **never populated** since there is no UPI. Dropped when the job completes.

> Source: 541-0007565-B02, §2.10.2

---

## TPump Array INSERT with NoPI

### Packing Optimization

On a PI table, rows in an Array INSERT are split across multiple AMP steps based on hash distribution. The number of rows per step depends on:
1. PACK factor (rows per request)
2. Number of AMPs (more AMPs → fewer rows per step)
3. Data clustering (NUPI with many duplicates → more rows per step)

On a **NoPI table**, ALL rows in a request are packed into a **single AMP step** sent to one randomly selected AMP. This is independent of system size and data clustering.

> The performance advantage of NoPI is greatest when comparing against UPI tables on large systems with many AMPs.

> Source: 541-0007565-B02, §2.11, §2.11.2

### SERIALIZE Option

| Setting | PI Table | NoPI Table |
|---|---|---|
| ON | Forces same-PI rows to same session; reduces hash lock contention | Not needed — no PI-based contention |
| OFF | Default | **Recommended** — always use OFF for NoPI |

> Source: 541-0007565-B02, §2.11.2.1

### Session Count Recommendation

A NoPI table typically has **one hashcode per AMP**. A rowhash lock covers many (potentially all) rows on that AMP. Multiple TPump sessions writing to the same AMP will block each other.

**Recommendation:** Number of TPump sessions ≤ number of AMPs.

> Source: 541-0007565-B02, §2.11.2.2

---

## Query Performance on NoPI Tables

### Full-Table Scans

Without a primary index, there is **no single-AMP access path**. Every query on a NoPI table results in an all-AMP full-table scan unless a secondary index provides an access path.

```sql
-- This requires full-table scan on NoPI
SELECT * FROM staging_db.sales_stage WHERE item_nbr = 100;

-- Add NUSI to enable index-based access
CREATE INDEX (item_nbr) ON staging_db.sales_stage;
SELECT * FROM staging_db.sales_stage WHERE item_nbr = 100;
-- Now uses NUSI access path
```

> Source: 541-0007565-B02, §2.7, §3.3

### Joins with NoPI Tables

Joining a PI table to a NoPI table **cannot** be AMP-local. The Optimizer must:
1. Retrieve rows from the NoPI table via all-rows scan
2. **Redistribute** by the join column's hash
3. Sort the redistributed spool
4. Merge join with the PI table

```sql
-- PI-to-PI join (same PI column): AMP-local merge join
EXPLAIN SELECT * FROM t1, t2 WHERE t1.c1 = t2.c1;
-- → merge join, built locally on the AMPs

-- PI-to-NoPI join: redistribute + sort + merge join
EXPLAIN SELECT * FROM t1, t3_nopi WHERE t1.c1 = t3_nopi.c1;
-- → RETRIEVE from t3_nopi, redistribute by hash(c1), SORT, then merge join
```

> Source: 541-0007565-B02, §2.5

### Statistics on NoPI Tables

COLLECT STATISTICS helps the Optimizer choose efficient join plans when NoPI tables are involved:

```sql
COLLECT STATISTICS ON staging_db.sales_stage INDEX (item_nbr);
COLLECT STATISTICS ON staging_db.sales_stage COLUMN (sale_date);

DROP STATISTICS ON staging_db.sales_stage INDEX (item_nbr);
```

Statistics are especially important for applications that join or union staging NoPI tables with PI base tables to view near-real-time data.

> Source: 541-0007565-B02, §2.5, §2.5.2

---

## Converting NoPI to PI Tables

### Method 1: CREATE TABLE AS

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
      item_nbr    INTEGER NOT NULL,
      sale_date   DATE FORMAT 'YYYY-MM-DD' NOT NULL,
      item_count  INTEGER,
      amount      DECIMAL(13,2)
     )
PRIMARY INDEX (item_nbr);

INSERT INTO prod_db.sales_final SELECT * FROM staging_db.sales_stage;
```

### Converting PI to NoPI

The same approaches work in reverse:

```sql
CREATE MULTISET TABLE staging_db.archive_nopi
AS (SELECT * FROM prod_db.sales)
WITH DATA
NO PRIMARY INDEX;
```

### INSERT-SELECT Performance Trade-Off

When moving data from NoPI staging → PI target:
- Data **must be redistributed** by the target PI and sorted.
- This redistribution cost is the trade-off for faster NoPI ingestion.
- When both staging and target are PI tables with the **same PI**, no redistribution occurs.

When the target is NoPI:
- Data is **locally appended** — no redistribution under any scenario.
- Efficient but can cause **skew** if the source data is unevenly distributed.

> Source: 541-0007565-B02, §3.5.1, §3.5.2

---

## Locking Behavior

NoPI tables typically have **one hash bucket per AMP**. This has significant locking implications:

| Operation | Lock Behavior |
|---|---|
| Single-row INSERT / TPump | Rowhash lock — may lock all rows on that AMP |
| FastLoad | Table-level lock (same as PI) |
| SELECT during FastLoad | ACCESS lock allowed on NoPI (not on PI) |
| Multiple concurrent writers | Serialized per AMP — one writer at a time |
| Reader during writes | Use ACCESS lock to avoid conflicts |

**Recommendation:** Avoid multiple concurrent writers to the same NoPI table on the same AMP. Keep TPump sessions ≤ number of AMPs.

> Source: 541-0007565-B02, §4.1

---

## Data Skew Scenarios

### Normal Ingestion

Under normal FastLoad or TPump ingestion, the random AMP selection generator distributes data evenly. **Skew is not a problem** for normal loading.

### Reconfig (System Expansion)

When expanding to more AMPs, a NoPI table with ~1 hash bucket per AMP may leave new AMPs without data:

- Not enough hash buckets to distribute to all new AMPs.
- Some AMPs may receive multiple hash buckets; others receive none.
- **Workaround:** INSERT-SELECT from skewed NoPI → PI table → new NoPI table.

> Source: 541-0007565-B02, §4.2.2

### Restore/Copy to Different Configuration

Same issue as Reconfig — when target system has more AMPs than source:
- Hash buckets from the source system may not cover all target AMPs.
- No rehash occurs for NoPI (no PI to rehash by).

> Source: 541-0007565-B02, §4.2.1

### INSERT-SELECT with Constrained Source

```sql
-- If this SELECT returns data skewed across AMPs,
-- the NoPI target inherits the skew (local append, no redistribution)
INSERT INTO staging_db.nopi_target
SELECT * FROM source_table WHERE region = 'WEST';
```

> Source: 541-0007565-B02, §4.2.3

### Down-AMP Recovery

When an AMP is down during NoPI inserts:
- Data intended for the down AMP is rerouted to **one fallback AMP** (not multiple).
- When the down AMP recovers, data is copied back.
- With >2 AMPs per cluster, this can cause temporary skew.
- With exactly 2 AMPs per cluster, no skew problem occurs.

> Source: 541-0007565-B02, §4.2.4

---

## Operations and Utilities Compatibility

| Feature | NoPI Support | Notes |
|---|---|---|
| ALTER TABLE | Yes | Add/drop FALLBACK, columns, etc. Cannot add PI or PPI. |
| DROP TABLE | Yes | Same as PI table |
| SHOW TABLE | Yes | Shows `NO PRIMARY INDEX` in DDL |
| HELP TABLE | Yes | Same output format as PI table |
| COLLECT STATISTICS | Yes | Important for joins involving NoPI tables |
| INSERT (single/multi) | Yes | Rows sent to random AMPs |
| SELECT | Yes | Full-table scan without secondary index |
| UPDATE | Yes | Full-table scan without secondary index |
| DELETE | Yes | Unconstrained DELETE uses fastpath optimization |
| FastLoad | Yes | Sort phase eliminated; duplicate rows allowed |
| TPump Array INSERT | Yes | All rows packed into single AMP step |
| FastExport | Yes | Same as PI table |
| CheckTable | Yes | LEVEL HASH verifies hash bucket ownership (slow with USI) |
| Table Rebuild | Yes | Requires FALLBACK; same process as PI |
| Reconfig | Yes | Can cause skew — see Data Skew section |
| Restore/Copy | Yes | Can cause skew on different configurations |
| MultiLoad | **No** | Error 9107 — use FastLoad or TPump |
| UPSERT | **No** | Requires fully specified PI |
| MERGE-INTO (target) | **No** | Error 9252 — use separate UPDATE + INSERT |

> Source: 541-0007565-B02, §2.12

---

## Use Cases

### Staging for Mini-Batch ELT

The primary use case for NoPI tables. FastLoad data into NoPI staging, then apply to PI target:

```sql
-- 1. FastLoad into NoPI staging (fastest ingestion)
-- 2. Transform and apply to target
INSERT INTO prod_db.sales SELECT * FROM staging_db.sales_stage;
-- 3. Clean up staging
DELETE FROM staging_db.sales_stage;
```

### Sandbox / Exploratory Tables

Create a NoPI table when the appropriate primary index is unknown:

```sql
CREATE MULTISET TABLE sandbox.raw_data
AS (SELECT * FROM external_source)
WITH DATA
NO PRIMARY INDEX;

-- Analyze data patterns, then create final PI table
CREATE MULTISET TABLE prod_db.final_data
AS (SELECT * FROM sandbox.raw_data)
WITH DATA
PRIMARY INDEX (discovered_key);
```

### Log / Audit Trail Tables

Append-only workloads benefit from NoPI — no sort overhead:

```sql
CREATE MULTISET TABLE audit_db.event_log, FALLBACK
     (
      event_ts    TIMESTAMP(6) NOT NULL,
      user_id     VARCHAR(50),
      action      VARCHAR(200),
      detail      JSON(32000)
     )
NO PRIMARY INDEX;
```

### Real-Time Data View (Union Staging + Base)

```sql
CREATE VIEW prod_db.sales_realtime AS
SELECT * FROM prod_db.sales
UNION ALL
SELECT * FROM staging_db.sales_stage;
```

### Temporary / Volatile NoPI Tables

```sql
CREATE VOLATILE TABLE vt_temp_data
     (id INTEGER, val VARCHAR(100))
NO PRIMARY INDEX
ON COMMIT PRESERVE ROWS;
```

---

## NoPI Error Codes

| Error | Message | Resolution |
|---|---|---|
| 9107 | MultiLoad not allowed: table does not have a primary index | Use FastLoad or TPump instead of MultiLoad |
| 9252 | An invalid statement was attempted on a table without a primary index | Avoid UPSERT / MERGE-INTO on NoPI targets; use separate DML |

> Source: 541-0007565-B02, §6
