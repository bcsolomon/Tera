---
name: teradata-load-isolation
description: 'Configure and use Teradata Load Isolation (LOAD COMMITTED) for concurrent loading and querying without lock conflicts. Use when designing ETL pipelines that need concurrent read access during loads, understanding load-committed isolation semantics, configuring isolated loading for Fastload/MLoad/TPT, or troubleshooting load contention issues.'
metadata:
  author: teradata-expert
  version: "1.0"
---

# Teradata Load Isolation

## When to Use

- Designing ETL pipelines that require concurrent read access while data is being loaded
- Enabling readers to query only committed data during active load operations
- Configuring tables for load isolation using `WITH ISOLATED LOADING`
- Choosing between CLDI (concurrent) and NCLDI (non-concurrent) modification modes
- Setting up explicit multi-transaction, multi-session load operations with `BEGIN/END ISOLATED LOADING`
- Using `CHECKPOINT ISOLATED LOADING` to make intermediate data visible to readers during long loads
- Configuring TPT Stream, TPump, FastLoad, or MultiLoad scripts for load-isolated tables
- Migrating existing tables to load isolation with `ALTER TABLE`
- Scheduling garbage cleanup to reclaim space from logically deleted rows
- Troubleshooting lock contention between writers and readers on the same tables
- Migrating applications from other databases that use READ COMMITTED isolation level
- Deciding between `FOR ALL`, `FOR INSERT`, and `FOR NONE` DML levels
- Defining secondary indexes with or without load identity (`WITH LOAD IDENTITY` / `WITH NO LOAD IDENTITY`)
- Understanding the storage and CPU overhead of row versioning on load-isolated tables
- Grouping related tables in a single explicit load for cross-table read consistency
- Monitoring tables in pending commit state via `DBC.LoadTablesInfoV`
- Interpreting EXPLAIN output markers for load isolation (Load Committed, Load Uncommitted, CLDI steps)

## Core Concepts

### Load Isolation vs Traditional Locking

Traditional Teradata locking forces a choice: use ACCESS locks for non-blocking dirty reads, or use READ locks for committed-only data that blocks writers. Load Isolation eliminates this trade-off by introducing a `LOAD COMMITTED` locking modifier that provides non-blocking reads of committed-only data.

> Source: 541-0010644, Section 1.2

| Method | Lock Type | Blocks Writers? | Sees Uncommitted Data? |
|---|---|---|---|
| `LOCKING ... FOR ACCESS` | ACCESS | No | Yes (dirty reads) |
| `LOCKING ... FOR READ` | READ | Yes | No |
| `LOCKING ... FOR LOAD COMMITTED` | ACCESS | No | No |

### LOAD COMMITTED Semantics

Load Isolation uses **row versioning** to separate committed from uncommitted data:

- Each row carries an 8-byte **commit property** containing a Load ID for insert and (if logically deleted) for delete.
- Each table maintains a **last committed Load ID** in the data dictionary.
- Readers using `LOAD COMMITTED` compare the row's Load ID against the table's last committed Load ID to filter out uncommitted rows.
- Non-repeatable reads and phantom rows are possible, as with standard READ COMMITTED isolation.

> Source: 541-0010644, Section 2

### CLDI vs NCLDI Operations

| Aspect | CLDI (Concurrent Load Isolated) | NCLDI (Non-Concurrent Load Isolated) |
|---|---|---|
| Row versioning | Yes — rows are logically deleted and new versions inserted | No — rows are physically modified in place |
| Lock type | WRITE lock | EXCLUSIVE lock |
| Concurrent readers | Allowed (LOAD COMMITTED sees committed data) | Blocked (including ACCESS lock readers) |
| Load ID change | Incremented on commit | Unchanged |
| Default for | Bulk (all-AMP) DML operations | Single-row DML, FastLoad, standard MLoad |

Override the default behavior per statement:

```sql
-- Force CLDI
INSERT WITH ISOLATED LOADING target_table SELECT * FROM source;

-- Force NCLDI
INSERT WITH NO ISOLATED LOADING target_table SELECT * FROM source;
```

Within a single transaction on a given table, all modifications must be either all CLDI or all NCLDI — mixing is not allowed.

> Source: 541-0010644, Section 3.2

### Implicit vs Explicit Loads

- **Implicit load**: CLDI operations within a single database transaction. The load commits when the transaction commits.
- **Explicit load**: CLDI operations spanning multiple transactions and/or sessions, managed with `BEGIN ISOLATED LOADING`, optional `CHECKPOINT ISOLATED LOADING`, and `END ISOLATED LOADING`. Uses a `LDILoadGroup` query band to associate load sessions.

> Source: 541-0010644, Sections 3.2.1–3.2.3

## Procedures

### Creating a Load-Isolated Table

```sql
CREATE TABLE AccountBalance, WITH CONCURRENT ISOLATED LOADING FOR ALL (
    Account_No    INTEGER NOT NULL,
    Branch_No     INTEGER NOT NULL,
    Account_Balance DECIMAL(18,2),
    Account_Status CHAR(4)
)
UNIQUE PRIMARY INDEX (Account_No);
```

DML level options:
- `FOR ALL` — INSERT, UPDATE, DELETE can all be CLDI (default). Creates logically deleted rows.
- `FOR INSERT` — Only INSERTs are CLDI; UPDATE/DELETE use NCLDI. No logically deleted rows.
- `FOR NONE` — Temporarily disables load isolation; all modifications use NCLDI.

> Source: 541-0010644, Section 3.1

### Reading with LOAD COMMITTED

```sql
-- Direct query
LOCKING AccountBalance FOR LOAD COMMITTED
SELECT Branch_No, SUM(Account_Balance)
FROM AccountBalance
GROUP BY 1;

-- View-based approach (recommended for applications)
CREATE VIEW AccountBalanceV AS
    LOCKING AccountBalance FOR LOAD COMMITTED
    SELECT * FROM AccountBalance;
```

> Source: 541-0010644, Section 3.3

### Explicit Load Operations

```sql
-- Session 1: Start the load
BEGIN ISOLATED LOADING ON ldi1, ldi2
USING QUERY_BAND 'LDILoadGroup=Grp1;'
IN MULTIPLE SESSION;

-- Session 2: Join the load group
SET QUERY_BAND='LDILoadGroup=Grp1;' FOR SESSION;
INSERT INTO ldi1 SELECT * FROM staging1;

-- Session 3: Join the load group
SET QUERY_BAND='LDILoadGroup=Grp1;' FOR SESSION;
UPDATE ldi2 SET col2 = 100;

-- Optional: Make intermediate results visible to readers
CHECKPOINT ISOLATED LOADING FOR QUERY_BAND 'LDILoadGroup=Grp1;';

-- Commit the entire load
END ISOLATED LOADING FOR QUERY_BAND 'LDILoadGroup=Grp1;';
```

> Source: 541-0010644, Sections 3.2.3–3.2.4

### Garbage Cleanup

```sql
-- Single table
ALTER TABLE AccountBalance RELEASE DELETED ROWS;

-- Cascaded cleanup (table + join indexes), BTET mode
CALL SYSLIB.LDI_Clean('AccountDB', 'AccountBalance', 'N', OutInfo, ErrInfo);

-- Count logically deleted rows
SELECT WITH DELETED ROWS COUNT(*)
FROM AccountBalance
WHERE TD_ROWLOADID >= '100000000'xi8;
```

> Source: 541-0010644, Section 3.5

### Migrating Existing Tables

```sql
ALTER TABLE existing_table, WITH ISOLATED LOADING;
```

After migration, update views to use `LOAD COMMITTED` and modify load jobs to use implicit or explicit load operations.

> Source: 541-0010644, Section 3.6

### DBS Control Setting

The `AccessLockForUncomRead` setting (General Field 54) affects how non-modified read statements behave under READ UNCOMMITTED isolation level on load-isolated tables:

| Setting | Effect on Non-Modification SELECT (no locking modifier) |
|---|---|
| FALSE (default) | READ lock with LC condition — committed data only |
| TRUE | ACCESS lock with LU condition — dirty reads |

This setting has no effect when an explicit locking modifier (`FOR ACCESS`, `FOR READ`, or `FOR LOAD COMMITTED`) is specified.

> Source: 541-0010644, Section 3.3, Table 2

## Troubleshooting

| Symptom | Likely Cause | Resolution |
|---|---|---|
| Readers blocked during loads | NCLDI operation using EXCLUSIVE lock | Ensure bulk DML defaults to CLDI, or use `WITH ISOLATED LOADING` clause |
| Inconsistent query results during load | Using ACCESS lock (dirty reads) | Switch to `LOAD COMMITTED` locking modifier |
| Growing disk usage on LDI tables | Logically deleted rows accumulating | Schedule periodic `ALTER TABLE ... RELEASE DELETED ROWS` or `SYSLIB.LDI_Clean` |
| Error 9728: load operation in progress | Concurrent load conflict on table | Retry after current load commits, or use explicit load with shared `LDILoadGroup` |
| Error 9890: table not load isolated | Applying LDI syntax to non-LDI table | `ALTER TABLE ... WITH ISOLATED LOADING` first |
| Error 9733: operation not allowed | Archive/restore attempted on table in pending commit state | `END ISOLATED LOADING` before archive operations |
| COUNT(*) not using cylinder index scan | LDI tables require LC/LU condition pruning | Expected behavior — full scan required for LDI tables |
| Load ID wrap concern | Extremely high-frequency commits (unlikely in practice) | `ALTER TABLE ... RESET LOAD IDENTITY` |

> Source: 541-0010644, Sections 4.1–4.2, Appendix A

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-load-isolation", path="references/FILENAME")` — do NOT call `list`.

For detailed technical reference including row versioning mechanics, utility configuration, DBS Control settings, isolation level behavior matrix, and complete error codes, see:

- [Load Committed Operations Reference](references/load-committed-operations.md)
