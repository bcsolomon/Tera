# DML Performance & Data Operations

## UPDATE Performance

### Why Large UPDATEs Are Slow

In Teradata, UPDATE is implemented as:
1. **Read** the target row(s)
2. **Write before-image** to transient journal (for rollback)
3. **Delete** the old row
4. **Insert** the new row (same row hash location)
5. If PI column is updated: **redistribute** row to new AMP

Each step involves I/O. For millions of rows, this multiplies to enormous I/O cost.

### Strategies for Large UPDATEs

| Strategy | When to Use | How |
|---|---|---|
| **Partition-level UPDATE** | Updating all rows in a partition | `UPDATE ... WHERE partition_col = value` — optimizer can use partition elimination |
| **MERGE instead of UPDATE** | Conditional updates with source data | MERGE is optimized for set-based operations |
| **INSERT-SELECT + rename** | Updating >50% of rows | Create new table with corrected data, swap names |
| **Staged mini-batches** | Avoid running out of journal space | Loop UPDATE with `SAMPLE 100000` |
| **NO LOG tables** | Staging tables where recovery not needed | `CREATE TABLE ... NO LOG` eliminates journal writes |

```sql
-- INSERT-SELECT approach for massive updates (faster than UPDATE)
CREATE TABLE mydb.orders_new AS (
    SELECT order_id, customer_id,
           CASE WHEN status = 'PENDING' THEN 'CANCELLED' ELSE status END AS status,
           order_date
    FROM mydb.orders
) WITH DATA PRIMARY INDEX (order_id);
-- Then: DROP TABLE mydb.orders; RENAME TABLE mydb.orders_new TO mydb.orders;
```

### Transient Journal Impact

Every DML statement writes before-images to the transient journal (TJ) for rollback capability. For large operations:
- TJ can consume significant spool space
- Multiple concurrent DML on same table: TJ contention
- Long-running transactions hold TJ space until COMMIT/ROLLBACK

**Mitigation:**
- Use `BEGIN TRANSACTION ... END TRANSACTION` with explicit COMMIT for batch control
- Use `NO LOG` tables for staging where recovery is not needed
- Break large DML into smaller transactions

---

## MERGE (UPSERT) Performance

### Common MERGE Problem: Error 3944

Error 3944: "Duplicate unique prime index value" — occurs when MERGE INSERT would create a row with the same UPI value as an existing row.

**Root Cause:** The MERGE source data contains duplicate keys, or the WHEN NOT MATCHED clause fires for a row that already exists due to a concurrent INSERT.

### MERGE Requirements for Good Performance

1. **PI alignment:** Source and target tables should have the same PI so rows are co-located
2. **Statistics on join columns:** COLLECT STATISTICS on the ON clause columns of both tables
3. **One-to-one join:** The ON clause must uniquely identify target rows (otherwise error 7547)
4. **Source deduplication:** If source has duplicate keys, deduplicate BEFORE the MERGE

```sql
-- Efficient MERGE pattern
MERGE INTO mydb.target t
USING mydb.source s
ON t.pk_col = s.pk_col
WHEN MATCHED THEN UPDATE SET t.value = s.value, t.updated = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN INSERT (pk_col, value, updated) VALUES (s.pk_col, s.value, CURRENT_TIMESTAMP);

-- Fix error 3944: deduplicate source first
CREATE VOLATILE TABLE vt_deduped AS (
    SELECT * FROM mydb.source QUALIFY ROW_NUMBER() OVER (PARTITION BY pk_col ORDER BY load_ts DESC) = 1
) WITH DATA ON COMMIT PRESERVE ROWS;
```

### MERGE vs INSERT + UPDATE

| Scenario | Best Approach |
|---|---|
| <10% new rows, rest updates | MERGE — single pass |
| Mostly new rows (>90% INSERT) | INSERT with error handling, then UPDATE mismatches |
| Very large source (>100M rows) | Staged MERGE in batches by partition |
| Source has duplicates | Deduplicate first, then MERGE |

---

## Volatile Tables vs Global Temporary Tables vs CTEs

### Performance Comparison

| Type | Persistence | Statistics | Indexes | Spool Cost | Best For |
|---|---|---|---|---|---|
| **Volatile table** | Session only | Can collect | Can create SI | Spool space | Multi-use temp results |
| **Global temp table** | Structure permanent, data per-session | Can collect | Pre-defined | Perm space (0 when empty) | Shared ETL patterns |
| **CTE (WITH clause)** | Query only | None (spooled) | None | Spool | Single-use in one query |
| **Derived table** | Query only | None | None | Spool | Subquery replacement |

### When Volatile Tables Outperform CTEs

- Result is used **multiple times** in subsequent queries (CTE is re-evaluated per reference in some cases)
- You need to **collect statistics** on the temp result for downstream join optimization
- You need to **add an index** for selective access in a subsequent join
- Result set is large and you want to **control distribution** via PI choice

### When CTEs Are Better

- Single-use subquery factoring (readability)
- Small result sets (<10K rows)
- No need for statistics or indexing

### Volatile Table Pitfalls

- **Spool limits:** Volatile tables consume spool space from your user's spool allocation
- **Disappearing tables:** Volatile tables vanish at session end (or on disconnect)
- **No fallback:** Cannot have FALLBACK protection
- **No cross-session sharing:** Each session has its own instance

```sql
-- Create with PI for good join alignment
CREATE VOLATILE TABLE vt_active_customers AS (
    SELECT customer_id, region, last_order_date
    FROM mydb.customers
    WHERE last_order_date > CURRENT_DATE - 90
) WITH DATA
PRIMARY INDEX (customer_id)  -- align with fact table PI
ON COMMIT PRESERVE ROWS;

-- Collect stats for downstream joins
COLLECT STATISTICS COLUMN customer_id ON vt_active_customers;
```

---

## Load Utility Selection

### Which Utility for What

| Utility | Speed | Locks | Best For |
|---|---|---|---|
| **FastLoad** | Fastest bulk | WRITE lock on empty table only | Initial load of empty tables |
| **MultiLoad** | Fast bulk + DML | Table-level write lock | UPDATE/DELETE/UPSERT on large tables |
| **TPump** | Row-at-a-time | Row-hash locks | Near-real-time trickle feed, no blocking |
| **BTEQ/INSERT-SELECT** | Moderate | Standard locks | Small-to-medium loads, SQL-based |
| **Teradata Parallel Transporter (TPT)** | All of above | Depends on operator | Universal framework (replaces above) |

### Load Utility Impact on Query Performance

| Scenario | Problem | Fix |
|---|---|---|
| FastLoad running | Table locked exclusively — all queries blocked | Schedule during maintenance window |
| MultiLoad running | Table locked — SELECTs blocked | Use TPump for non-blocking loads |
| Post-load, no stats | Optimizer uses stale/missing statistics | COLLECT STATISTICS immediately after load |
| Post-load, fragmented | Table may have cylinder fragmentation | Consider `ALTER TABLE ... RELEASE FALLBACK` + rebuild if needed |

---

## Stored Procedures — Performance Patterns

### Why Cursor Loops Are Slow

```sql
-- BAD: Row-at-a-time cursor processing
FOR rec IN cursor_name DO
    UPDATE target SET col = rec.val WHERE pk = rec.pk;
END FOR;
-- Each iteration: parse, lock, journal, execute, unlock = massive overhead for N rows
```

### Set-Based Alternative (10x–1000x Faster)

```sql
-- GOOD: Single set-based statement replaces the loop
UPDATE mydb.target
SET col = (SELECT s.val FROM mydb.source s WHERE s.pk = target.pk)
WHERE EXISTS (SELECT 1 FROM mydb.source s WHERE s.pk = target.pk);

-- Or use MERGE
MERGE INTO mydb.target t
USING mydb.source s ON t.pk = s.pk
WHEN MATCHED THEN UPDATE SET t.col = s.val;
```

### When You Must Use a Cursor

- Dynamic SQL (table names determined at runtime)
- Complex conditional logic that cannot be expressed in CASE/MERGE
- Error handling per-row (retry specific failures)

**Optimization for unavoidable cursors:**
- Process in batches: fetch 1000 rows into a temp table, process as set
- Use `FOR REQUEST` or multi-statement requests to reduce round trips
- Minimize commits (once per batch, not per row)

---

## Macros vs Stored Procedures vs Views — Overhead

| Object | Overhead | When Fastest |
|---|---|---|
| **View** | Zero runtime overhead — expanded inline into calling query | Pure SQL transformation, read-only |
| **Macro** | Minimal — parsed and executed as a unit | Multiple SQL statements run together, parameter substitution |
| **Stored procedure** | Higher — procedural engine, separate optimization per statement | Complex logic, IF/ELSE, cursor processing, error handling |

### Performance Rules

- **Views have NO performance penalty** — the optimizer merges the view definition into the outer query and optimizes as one plan
- **Nested views** (view on view on view): also no inherent penalty — optimizer flattens them. But complex nesting can confuse the optimizer into suboptimal plans if predicates don't push down properly.
- **Macros** are slightly faster than equivalent stored procedures because there's no procedural interpreter overhead
- **Stored procedures** should be used for logic that cannot be expressed in pure SQL — not as wrappers around single SELECT statements

---

## Multi-Statement Requests

### What They Are

Multiple SQL statements sent as a single request (separated by semicolons in BTEQ or as a multi-statement request in JDBC/ODBC).

```sql
-- Multi-statement request (all execute as one transaction in Teradata mode)
INSERT INTO mydb.log VALUES (CURRENT_TIMESTAMP, 'start');
UPDATE mydb.target SET status = 'PROCESSING' WHERE batch_id = 123;
INSERT INTO mydb.log VALUES (CURRENT_TIMESTAMP, 'end');
```

### Performance Benefit

- **Fewer round trips** between client and database
- **Single parse** of the request group
- **Single commit** at end (Teradata mode) — less journal overhead
- **All-or-nothing** semantics in Teradata mode

### When It Does NOT Help

- Statements are independent (no data dependency) — parallel submission might be faster
- Very large individual statements — bundling adds parsing memory
- ANSI mode — each statement is its own transaction anyway

### Guideline

For INSERT-heavy ETL scripts, group 5–10 related INSERTs into one multi-statement request. Beyond 10 statements, parse overhead may increase.
