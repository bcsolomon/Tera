# Load Committed Operations Reference

Comprehensive technical reference for Teradata Load Isolation, covering row versioning mechanics, SQL syntax, utility support, monitoring, and performance considerations.

> Source: 541-0010644 — Load Isolation User Guide

---

## Row Versioning Mechanics

### Commit Property

Every row in a load-isolated table carries an 8-byte **commit property** consisting of two 4-byte Load ID values:

| Field | Internal Name | Purpose |
|---|---|---|
| Insert Load ID | `TD_ROWLOADID_INS` | Load ID under which the row was inserted |
| Delete Load ID | `TD_ROWLOADID_DEL` | Load ID under which the row was logically deleted (0 if active) |

The system automatically adds LC (Load Committed) or LU (Load Uncommitted) conditions to queries:

```
-- LC condition (committed reads)
(TD_ROWLOADID_INS <= :ReadLoadID)
AND (TD_ROWLOADID_DEL = 0 OR TD_ROWLOADID_DEL > :ReadLoadID)

-- LU condition (dirty reads / uncommitted)
TD_ROWLOADID_DEL = 0
```

`:ReadLoadID` is the table's last committed Load ID captured at query preparation time.

> Source: 541-0010644, Sections 2, 3.3

### Row Versioning During CLDI Operations

When a CLDI modification occurs:

- **INSERT**: New row gets `TD_ROWLOADID_INS` = current Load ID, `TD_ROWLOADID_DEL` = 0.
- **UPDATE**: Existing row is **logically deleted** (`TD_ROWLOADID_DEL` set to current Load ID). A new row with modified values is inserted with the current Load ID.
- **DELETE**: Existing row is logically deleted by setting `TD_ROWLOADID_DEL` to the current Load ID. The row remains physically in the table.

This versioning enables concurrent readers using `LOAD COMMITTED` to see only the previously committed version of rows while a load transaction is in progress.

> Source: 541-0010644, Section 2

### Last Committed Load ID

Each load-isolated table maintains a **last committed Load ID** value in the data dictionary (`DBC.TVM`). This 4-byte integer:

- Starts at 0 when the table is created or reset
- Increments by 1 each time a CLDI modification commits
- Is used by readers to determine which rows are committed
- Wraps after approximately 2^31 increments (~68 years at one load/second)

NCLDI modifications do **not** change the last committed Load ID. Rows inserted during NCLDI operations have their commit property set to 0.

> Source: 541-0010644, Sections 2, 4.1

---

## CREATE / ALTER TABLE Syntax

### Creating a Load-Isolated Table

```sql
CREATE TABLE table_name, WITH CONCURRENT ISOLATED LOADING FOR level (
    column_definitions
)
PRIMARY INDEX (columns);
```

**DML Levels:**

| Level | Meaning | Logically Deleted Rows? | Use Case |
|---|---|---|---|
| `FOR ALL` | INSERT, UPDATE, DELETE can be CLDI (default) | Yes | Full concurrent access during any DML |
| `FOR INSERT` | Only INSERT is CLDI; UPDATE/DELETE are always NCLDI | No | Append-only load patterns with concurrent reads |
| `FOR NONE` | All modifications use NCLDI | No | Temporarily disable load isolation |

> Source: 541-0010644, Section 3.1

### Altering Load Isolation Properties

```sql
-- Convert a regular table to load-isolated
ALTER TABLE existing_table, WITH ISOLATED LOADING;

-- Change DML level
ALTER TABLE ldi_table, WITH CONCURRENT ISOLATED LOADING FOR INSERT;

-- Temporarily disable
ALTER TABLE ldi_table, WITH CONCURRENT ISOLATED LOADING FOR NONE;

-- Remove load isolation entirely
ALTER TABLE ldi_table, WITHOUT ISOLATED LOADING;
```

> Source: 541-0010644, Sections 3.1, 3.6

### Secondary Index Definitions

USI (Unique Secondary Index) on load-isolated tables automatically carries the commit property in the index row, enabling single-row committed reads via the index.

NUSI (Non-Unique Secondary Index) behavior is configurable:

```sql
-- NUSI with commit property (can act as covering index)
CREATE INDEX (col1, col2) WITH LOAD IDENTITY
ON ldi_table;

-- NUSI without commit property (base table must be read)
CREATE INDEX (col1, col2) WITH NO LOAD IDENTITY
ON ldi_table;
```

An NUSI `WITH LOAD IDENTITY` records 8 additional bytes per base table ROWID and is maintained even when the index column is not modified. Design indexes considering this overhead vs. the benefit of covering-index access.

> Source: 541-0010644, Sections 3.1.1, 4.1

### Join Indexes

A join index defined on a load-isolated table **automatically becomes load-isolated** and maintains its own independent last committed Load ID.

```sql
CREATE JOIN INDEX BranchSummary AS
    SELECT Branch_No, SUM(Account_Balance) AS BranchBalance
    FROM AccountBalance
    GROUP BY 1
    WHERE Account_Status = 'ACTV';
```

- The join index DML level is system-defined based on its definition.
- CLDI modifications on the base table propagate as CLDI on the join index; NCLDI propagates as NCLDI.
- Garbage cleanup does **not** cascade from base table to join index automatically — use `SYSLIB.LDI_Clean`.

> Source: 541-0010644, Sections 3.1.2, 3.5

---

## Isolation Levels and Read Behavior

### Locking Modifier Usage

The `LOAD COMMITTED` locking modifier uses ACCESS lock internally but applies LC conditions to filter out uncommitted rows:

```sql
-- Non-blocking committed read
LOCKING table_name FOR LOAD COMMITTED
SELECT columns FROM table_name WHERE conditions;

-- Recommended: encapsulate in a view
CREATE VIEW table_v AS
    LOCKING table_name FOR LOAD COMMITTED
    SELECT * FROM table_name;
```

> Source: 541-0010644, Section 3.3

### Isolation Level Behavior Matrix

The lock type and condition applied depend on the isolation level setting, locking modifier, and DBS Control setting `AccessLockForUncomRead` (General Field 54):

| Isolation Level | Locking Modifier | DBS Field 54 | Lock Applied | Condition |
|---|---|---|---|---|
| SERIALIZABLE | (none) | N/A | READ | LC |
| SERIALIZABLE | `FOR ACCESS` | N/A | ACCESS | LU |
| SERIALIZABLE | `FOR LOAD COMMITTED` | N/A | ACCESS | LC |
| SERIALIZABLE | `FOR READ` | N/A | READ | LC |
| READ UNCOMMITTED | (none) | FALSE (default) | READ | LC |
| READ UNCOMMITTED | (none) | TRUE | ACCESS | LU |
| READ UNCOMMITTED | `FOR ACCESS` | N/A | ACCESS | LU |
| READ UNCOMMITTED | `FOR LOAD COMMITTED` | N/A | ACCESS | LC |
| READ UNCOMMITTED | `FOR READ` | N/A | READ | LC |

**Note:** If the reading transaction is also modifying the same LDI table, only the LU condition is applied regardless of the locking modifier.

> Source: 541-0010644, Section 3.3, Table 2

---

## Modification Operations

### CLDI Modification Rules

- Bulk (all-AMP, table/partition level lock) DML defaults to CLDI.
- Single-row DML defaults to NCLDI.
- Override with explicit syntax:

```sql
-- Force CLDI
INSERT WITH ISOLATED LOADING target_table
SELECT * FROM source_table;

-- Force NCLDI
INSERT WITH NO ISOLATED LOADING target_table
SELECT * FROM source_table;
```

- Within a single transaction on a given table, all modifications must be either CLDI or NCLDI — mixing is not allowed.
- A session can disable CLDI entirely:

```sql
SET SESSION FOR NO CONCURRENT ISOLATED LOADING;
```

> Source: 541-0010644, Section 3.2

### Implicit Load (Single Transaction)

The isolation boundary is a single database transaction. The first CLDI modification triggers a "Begin Isolated Load" step; transaction commit triggers "End Isolated Load" and increments the Load ID.

```sql
BT;
MERGE INTO CustomerDetails
USING CustSrc AS Src ON Src.CustomerName = CustomerDetails.CustomerName
WHEN MATCHED THEN UPDATE SET Address = Src.Address;

INSERT WITH ISOLATED LOADING BranchDetails
SELECT * FROM BranchSrc WHERE BranchState = 'CA';
ET;  -- commits load, increments Load IDs for both tables
```

> Source: 541-0010644, Section 3.2.2

### Explicit Load (Multi-Transaction / Multi-Session)

Explicit loads span multiple transactions and sessions using `BEGIN/END ISOLATED LOADING` and a shared query band:

```sql
-- Master session starts the load
BEGIN ISOLATED LOADING ON table1, table2
USING QUERY_BAND 'LDILoadGroup=BatchLoad1;'
IN MULTIPLE SESSION;

-- Load sessions join via query band
SET QUERY_BAND='LDILoadGroup=BatchLoad1;' FOR SESSION;
INSERT INTO table1 SELECT * FROM staging1;

-- Optional: checkpoint to make loaded data visible while continuing
CHECKPOINT ISOLATED LOADING FOR QUERY_BAND 'LDILoadGroup=BatchLoad1;';

-- End the load (commits all changes, releases pending state)
END ISOLATED LOADING FOR QUERY_BAND 'LDILoadGroup=BatchLoad1;';
```

For single-session explicit loads, omit `IN MULTIPLE SESSION`. `END ISOLATED LOADING` can be issued from a different session using the `OVERRIDE` syntax.

> Source: 541-0010644, Sections 3.2.1, 3.2.3–3.2.6

### CHECKPOINT ISOLATED LOADING

`CHECKPOINT` is effectively `END ISOLATED LOADING` + `BEGIN ISOLATED LOADING` in one step. It commits the current load (increments Load ID, makes data visible to readers) and immediately begins a new load on the same tables.

```sql
CHECKPOINT ISOLATED LOADING FOR QUERY_BAND 'LDILoadGroup=BatchLoad1;';
```

> Source: 541-0010644, Sections 2, 3.2.3

---

## Utility Support

### FastLoad

- Supports inserting into **empty** load-isolated tables only.
- Always operates as NCLDI using EXCLUSIVE lock — blocks all readers.
- Cannot be used for concurrent loading scenarios.

> Source: 541-0010644, Table 1

### MultiLoad

- Supports modifications on load-isolated tables.
- **Without MLOADX**: Operates as NCLDI using EXCLUSIVE lock — blocks readers.
- **With MLOADX**: Operates as CLDI — permits concurrent readers.
- MLoad target tables may not contain secondary indexes with load identity (Error 9897).

> Source: 541-0010644, Table 1

### TPT Load Operator

- Supports load-isolated tables.
- Uses EXCLUSIVE lock (NCLDI operation) — blocks readers.
- For concurrent reader access during load, use the TPT Stream operator instead.

> Source: 541-0010644, Table 1

### TPT Stream Operator / TPump

TPump and TPT Stream perform single-row operations that default to NCLDI with EXCLUSIVE locks, but multiple sessions can load concurrently. For explicit load with TPump, issue `BEGIN ISOLATED LOADING` from a separate session, then add `SET QUERY_BAND` to the TPump script:

```
.LOGON localhost/user,password;
SET QUERY_BAND = 'LDILoadGroup=Grp1;' FOR SESSION;
.BEGIN LOAD
SESSIONS 4 1
PACK 500
...
INSERT INTO ldi_table VALUES (:col1, :col2, :col3);
.END LOAD;
.LOGOFF;
```

Issue `END ISOLATED LOADING` from the controlling session after TPump completes.

> Source: 541-0010644, Sections 3.2.4, 3.2.5

### TPT Stream Operator — Explicit Load Attributes

| Attribute | Values | Description |
|---|---|---|
| `LDILoadJob` | `Yes` / `No` | Start an LDI explicit load operation |
| `LDILoadGroup` | string | Query band group value for the load operation |
| `PauseLDI` | `Yes` / `No` | If `Yes`, TPT will not issue `END ISOLATED LOADING` after completion |

> Source: 541-0010644, Section 3.2.5

### FastExport

- Supports load-isolated tables.
- Can use `LOAD COMMITTED` locking modifier for committed reads.

> Source: 541-0010644, Table 1

---

## Monitoring Active Isolated Loads

### DBC.LoadTablesInfoTbl / DBC.LoadTablesInfoV

Explicit load operations are tracked in `DBC.LoadTablesInfoTbl`. Rows are inserted when `BEGIN ISOLATED LOADING` is issued and deleted when `END ISOLATED LOADING` completes.

```sql
-- View all tables currently in explicit load state
SELECT * FROM DBC.LoadTablesInfoV;
```

> Source: 541-0010644, Sections 2, 3.2.1

### Data Dictionary Views

| View | Information |
|---|---|
| `DBC.TablesV[X]` | Load isolation attributes for tables |
| `DBC.IndicesV[X]` | Load identity attribute for secondary indexes |
| `DBC.LoadTablesInfoV` | Tables currently in explicit load (pending commit) state |
| `DBC.DBQLStepTbl` | Load ID value used in row versioning per step (CLDI operations) |

> Source: 541-0010644, Section 2.1, Table 1

### Counting Logically Deleted Rows

```sql
-- Count only logically deleted rows
SELECT WITH DELETED ROWS COUNT(*)
FROM ldi_table WHERE TD_ROWLOADID >= '100000000'xi8;

-- Total rows including logically deleted
SELECT WITH DELETED ROWS COUNT(*) FROM ldi_table;
```

Access to `SELECT WITH DELETED ROWS` requires additional privileges.

> Source: 541-0010644, Section 3.5

### EXPLAIN Output Indicators

EXPLAIN output shows load isolation operations with these markers: `(Load Committed)` — LC condition applied; `(Load Uncommitted)` — LU condition applied; `(concurrent load isolated)` — CLDI modification step; `(load isolated)` — modification on an LDI table; `Begin Isolated Load on <table>` — first CLDI operation in transaction; `End Isolated Load` — load commit; `Checkpoint Isolated Load` — data refresh point.

> Source: 541-0010644, Sections 3.2.2–3.2.6

---

## Garbage Cleanup

### Purpose

CLDI UPDATE and DELETE operations create logically deleted rows that remain in the table. Over time these rows:

- Consume disk space
- Degrade query performance (more rows to scan and prune)
- Increase modification overhead

Periodic cleanup is essential for maintaining performance.

> Source: 541-0010644, Section 3.5

### Cleanup Methods

**Single table cleanup** (requires EXCLUSIVE lock):

```sql
ALTER TABLE ldi_table RELEASE DELETED ROWS;
```

**Cascaded cleanup** (table + all associated join indexes):

```sql
-- BTET session mode
CALL SYSLIB.LDI_Clean('db_name', 'table_name', 'N', OutInfo, ErrInfo);

-- ANSI session mode
CALL SYSLIB.LDI_Clean_ANSI('db_name', 'table_name', 'N', OutInfo, ErrInfo);
```

**Reset Load ID** (to handle potential value wrap):

```sql
ALTER TABLE ldi_table RESET LOAD IDENTITY;
```

Schedule cleanup during production windows that can tolerate EXCLUSIVE locks. Use Teradata Query Scheduler to automate periodic cleanup.

> Source: 541-0010644, Section 3.5

### Statistics Collection

Collect summary statistics after garbage cleanup. The system tracks the count of logically deleted rows (`DelRowCount`) in table-level summary statistics, which the optimizer uses for better cost estimation.

```sql
COLLECT SUMMARY STATISTICS ON ldi_table;
```

> Source: 541-0010644, Section 3.4

---

## Restrictions and Limitations

### Table Type Restrictions

The following table types **cannot** be load-isolated: VOLATILE, ERROR, QUEUE, TEMPORARY, GLOBAL TEMPORARY TRACE, and column-partitioned tables.

> Source: 541-0010644, Section 3.1.3

### Feature Restrictions

| Restriction | Detail |
|---|---|
| Hash indexes | Not allowed on load-isolated tables |
| Compressed join indexes | Not allowed on load-isolated tables |
| Permanent journaling | Not supported on load-isolated tables |
| Replication groups | Load-isolated tables cannot participate |
| Archive/Restore during explicit load | Blocked while table is in pending commit state (Error 9733) |
| Mixed CLDI/NCLDI in one transaction | Not permitted on the same table |

> Source: 541-0010644, Sections 3.1.3, 3.2.1, 4.2

### Multi-Table Join Index Consideration

A multi-table join index between a non-load-isolated and load-isolated table becomes load-isolated. However, modifications on the non-load-isolated base table cause NCLDI operations on the join index, which block readers with EXCLUSIVE locks. Account for this when designing multi-table join indexes.

> Source: 541-0010644, Section 4.2

---

## Performance Considerations

### Storage Overhead

Each row in a load-isolated table occupies **8 additional bytes** for the commit property. NUSI `WITH LOAD IDENTITY` adds 8 bytes per base table ROWID. CLDI UPDATE/DELETE creates logically deleted row versions, approximately doubling storage for modified rows until garbage cleanup.

> Source: 541-0010644, Sections 3.1.4, 4.1

### CPU Overhead

- LC/LU conditions are applied to every scan, consuming additional CPU for row pruning.
- Unconstrained `COUNT(*)` cannot use cylinder index scan on LDI tables — full table/partition scan required.
- Full table/partition DELETE does not use fast-path delete due to logically deleted rows.
- CLDI modifications perform row versioning (logical delete + insert), more expensive than in-place modification.

> Source: 541-0010644, Section 4.1

### Design Guidelines

1. **Define tables as load-isolated only when concurrent read/write is required.** Unnecessary load isolation wastes space and CPU.
2. **Use `FOR INSERT` when only append loads occur concurrently with reads.** Avoids logically deleted rows; more consistent read performance.
3. **Group related tables in a single explicit load** so `LOAD COMMITTED` readers see consistent data across joined tables.
4. **Schedule regular garbage cleanup** to prevent degradation. Monitor `DelRowCount` in summary statistics.
5. **Use NUSI `WITH LOAD IDENTITY` only when covering-index access is needed.** Maintenance cost applies even when index column is not modified.
6. **Collect statistics after garbage cleanup** to give the optimizer accurate row counts.

> Source: 541-0010644, Sections 3.1.4, 3.4, 4.1

---

## Error Codes

| Error | Text | Common Cause |
|---|---|---|
| 9728 | Retry later as currently a load operation is in progress on the table | Concurrent load conflict |
| 9730 | Table is in load state | Table has pending explicit load |
| 9732 | Invalid RowLoadID value in the row | Data corruption — run CheckTable |
| 9733 | Operation not allowed: one or more tables is in isolated load operation | Archive/restore during pending commit |
| 9761 | Dictionary load isolation information does not match | Dictionary inconsistency — run CheckTable |
| 9762 | RowLoadID value in index and base-row does not match | Index/base mismatch — run CheckTable |
| 9883 | Specified table is already a Load Isolated table | Table already has LDI property |
| 9884 | Cannot add load isolation property for table with feature defined | Incompatible feature (hash index, compressed JI, etc.) |
| 9885 | Cannot drop load isolation property of the table with feature defined | Dependent feature exists |
| 9886 | Specified DML level is already set | Redundant ALTER TABLE |
| 9890 | Table is not load isolated | LDI syntax used on non-LDI table |
| 9891 | Concurrent load operations are disabled in session | `SET SESSION FOR NO CONCURRENT ISOLATED LOADING` active |
| 9892 | Specified load isolated operations are disabled | DML level does not permit this operation |
| 9893 | Invalid operation on load isolated table | Unsupported operation on LDI table |
| 9894 | Cannot define feature for a load isolated table | Attempting to create hash index or compressed JI |
| 9895 | Cannot define load isolation on a table with permanent journal | Permanent journaling conflict |
| 9896 | Load operation cannot occur as CurrLoadID reached upper limit | Load ID wrap — reset with `ALTER TABLE ... RESET LOAD IDENTITY` |
| 9897 | MLoad target table may not contain secondary indexes with load identity | Remove load identity indexes before MLoad |
| 9898 | Table cannot be loaded as the related table is already in a different load operation | Table already in another explicit load group |

> Source: 541-0010644, Appendix A
