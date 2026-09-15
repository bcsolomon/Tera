---
name: create-table
description: 'Create Teradata tables using CREATE TABLE and CREATE TABLE AS DDL syntax including column definitions, data types, column attributes, constraints (PRIMARY KEY, FOREIGN KEY, CHECK), table options (FALLBACK, JOURNAL, CHECKSUM, FREESPACE, BLOCKCOMPRESSION, MERGEBLOCKRATIO, DATABLOCKSIZE), identity columns, derived period columns, and table preservation (ON COMMIT). Use when writing CREATE TABLE statements, defining column constraints, choosing table options like fallback protection or block compression, creating tables from subqueries with CREATE TABLE AS, copying table structures with or without data, or specifying SET vs MULTISET table kinds.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata CREATE TABLE

## When to Use

- Writing CREATE TABLE statements for permanent, volatile, or global temporary tables
- Defining columns with data types, defaults, nullability, and compression
- Adding table-level or column-level constraints (PRIMARY KEY, FOREIGN KEY, CHECK)
- Choosing table options: FALLBACK, journaling, checksum, freespace, block compression
- Creating tables from existing tables or subqueries (CREATE TABLE AS)
- Copying table structure with or without data and statistics
- Defining identity (auto-increment) columns
- Specifying SET vs MULTISET table semantics
- Creating queue tables for asynchronous processing

## Core Syntax

```sql
CREATE [SET | MULTISET] [VOLATILE | GLOBAL TEMPORARY] TABLE
  [database_name.]table_name
  [, table_option [,...]]
  ( column_definition [,...] )
  [index_clause [,...]]
  [ON COMMIT {DELETE | PRESERVE} ROWS]
;
```

### CREATE TABLE AS (Copy Form)

```sql
CREATE [SET | MULTISET] TABLE [database_name.]new_table
  [, table_option [,...]]
  AS ( subquery | source_table )
  WITH [NO] DATA
  [AND [NO] STATISTICS]
;
```

## Table Kinds (SET vs MULTISET)

| Kind | Keyword | Duplicate Rows | Default |
|------|---------|---------------|---------|
| SET | `SET TABLE` | Not allowed — every INSERT triggers a duplicate check against ALL existing rows | Teradata session mode default |
| MULTISET | `MULTISET TABLE` | Allowed — skips duplicate check, better INSERT performance | ANSI session mode default |
| Volatile | `VOLATILE TABLE` | Session-scoped, dropped at session end | — |
| Global Temporary | `GLOBAL TEMPORARY TABLE` | Materialized per session | — |

**SET vs MULTISET rules:**
- SET tables enforce row uniqueness via a full-row duplicate check on every INSERT — this adds significant overhead for large tables
- MULTISET tables skip this check entirely, offering substantially better INSERT performance
- NoPI tables and column-partitioned tables MUST be MULTISET
- **Best practice:** Always specify SET or MULTISET explicitly. Use MULTISET unless you specifically need duplicate rejection as a business rule

### Volatile vs Global Temporary Tables

| Aspect | Volatile Table | Global Temporary Table |
|--------|---------------|----------------------|
| **Privilege required** | NO CREATE TABLE privilege needed — only spool space | Requires CREATE TABLE privilege |
| **Definition persistence** | Exists only for session duration | Definition persists in data dictionary permanently |
| **Data scope** | Private to the session | Each session gets its own data instance |
| **Space used** | User's spool space | User's temporary space allocation |
| **ON COMMIT behavior** | Supports ON COMMIT DELETE ROWS (default) or ON COMMIT PRESERVE ROWS | Supports ON COMMIT DELETE ROWS (default) or ON COMMIT PRESERVE ROWS |
| **Logging** | No transient journal logging | No transient journal logging |
| **Statistics** | Cannot collect statistics | Can collect statistics on the definition |
| **Indexing** | Can define secondary indexes | Can define secondary indexes |

**ON COMMIT clause** (applies to BOTH volatile and global temporary tables):
- `ON COMMIT DELETE ROWS` (default) — all rows are deleted when a transaction commits
- `ON COMMIT PRESERVE ROWS` — rows are retained across transaction boundaries within the session

## Table Options

### FALLBACK Protection

FALLBACK maintains a duplicate copy of every row on a different AMP (Access Module Processor) than the primary copy. If an AMP fails, the system uses the fallback copy to continue operations without interruption.

- **FALLBACK** doubles the storage requirement for the table
- **NO FALLBACK** uses half the space but table data becomes unavailable if the AMP holding those rows fails (until AMP recovery)
- Use FALLBACK for production tables requiring high availability
- Consider NO FALLBACK for staging/temp tables, tables easily reloaded, or when space is critical and AMP failure risk is accepted

### BLOCKCOMPRESSION Options

| Option | Behavior |
|--------|----------|
| `AUTOTEMP` | **(Recommended)** System compresses based on access temperature — frequently accessed (hot) blocks remain uncompressed for fast access; infrequently accessed (cold) blocks are compressed to save space |
| `MANUAL` | Only blocks explicitly compressed via utilities are compressed |
| `ALWAYS` | All data blocks are compressed regardless of access pattern — maximizes space savings but may impact query performance on frequently accessed data |
| `NEVER` | No block compression is applied |
| `DEFAULT` | Inherits the setting from the parent database or system-level DBS Control parameter |

Best practice: Use AUTOTEMP for most tables to get automatic space savings on cold data without impacting hot data performance.

### Other Table Options

| Option | Purpose | Syntax |
|--------|---------|--------|
| JOURNAL | Before/after image journaling | `BEFORE JOURNAL` / `NO BEFORE JOURNAL` / `AFTER JOURNAL` |
| LOG | Transaction journaling | `LOG` / `NO LOG` |
| CHECKSUM | Data integrity verification | `CHECKSUM = {DEFAULT \| ON \| OFF}` |
| FREESPACE | Percentage of free space per cylinder | `FREESPACE = integer [PERCENT]` |
| MERGEBLOCKRATIO | Controls cylinder merge threshold | `DEFAULT MERGEBLOCKRATIO` / `NO MERGEBLOCKRATIO` |
| DATABLOCKSIZE | Row block size range | `DATABLOCKSIZE = data_block_size` |
| MAP | Assigns table to a contiguous/sparse map | `MAP = map_name [COLOCATE USING colocation_name]` |
| ISOLATED LOADING | Controls concurrent load isolation | `WITH [NO] [CONCURRENT] ISOLATED LOADING [FOR {ALL \| INSERT \| NONE}]` |

## Column Definition

```sql
column_name data_type [NOT NULL] [DEFAULT value] [CHARACTER SET {LATIN|UNICODE}]
  [COMPRESS [value_list]] [constraint_clause]
```

### Identity Columns (Auto-Increment)

```sql
column_name INTEGER GENERATED {ALWAYS | BY DEFAULT} AS IDENTITY
  (START WITH n INCREMENT BY n [MINVALUE n] [MAXVALUE n] [NO CYCLE | CYCLE])
```

### Compression Attributes

Value-list compression stores frequently occurring values in the table header rather than in each row, replacing them with presence bits (about 1 bit per compressed value per row):

| Type | Syntax | Details |
|------|--------|---------|
| NULL only | `col INTEGER COMPRESS` | Compresses NULL values |
| Value-list | `col VARCHAR(20) COMPRESS ('ACTIVE', 'CLOSED', 'PENDING')` | Up to 255 values; NULL is always implicitly compressible when COMPRESS is specified |
| Algorithmic (ALC) | `COMPRESS USING TD_LZ_COMPRESS DECOMPRESS USING TD_LZ_DECOMPRESS` | Large VARCHAR/BLOB |
| Block-level | Table option `BLOCKCOMPRESSION = AUTOTEMP` | Entire data blocks |

Best for columns with low cardinality or dominant values. Cannot use value-list compression on PI columns.

## Partitioning

Teradata supports multi-level partitioning with up to 62 levels. Specify multiple levels in the PARTITION BY clause separated by commas.

### RANGE_N (Range Partitioning)

```sql
PARTITION BY RANGE_N(order_date BETWEEN DATE '2020-01-01'
    AND DATE '2025-12-31' EACH INTERVAL '1' MONTH,
    NO RANGE OR UNKNOWN)
```

### CASE_N (List Partitioning)

```sql
PARTITION BY CASE_N(region = 'EAST', region = 'WEST', region = 'NORTH',
    NO CASE OR UNKNOWN)
```

### Multi-Level Partitioning Example

```sql
CREATE TABLE orders (
  order_id INTEGER NOT NULL,
  order_date DATE,
  region VARCHAR(10)
)
PRIMARY INDEX (order_id)
PARTITION BY (
  RANGE_N(order_date BETWEEN DATE '2020-01-01' AND DATE '2025-12-31' EACH INTERVAL '1' MONTH, NO RANGE OR UNKNOWN),
  CASE_N(region = 'EAST', region = 'WEST', region = 'NORTH', NO CASE OR UNKNOWN)
);
```

The combined number of partitions across all levels must not exceed the system limit.

## JSON Data Type

Define a JSON column with `JSON(max_size)`:

```sql
CREATE TABLE events (
  event_id INTEGER,
  payload JSON(16776192) CHARACTER SET LATIN
);
```

- Maximum size: 16,776,192 bytes for LATIN character set, 8,388,096 characters for UNICODE
- If no size is specified, the default is 16,776,192
- JSON data is validated on insert (must be well-formed)
- For smaller JSON values, consider `JSON(32000)` to avoid LOB storage overhead
- JSON columns support dot-notation access in queries: `payload.key`

## Constraints

```sql
-- Column-level
column_name INTEGER NOT NULL PRIMARY KEY
column_name INTEGER REFERENCES other_table(col)
column_name INTEGER CHECK (column_name > 0)

-- Table-level
CONSTRAINT pk_name PRIMARY KEY (col1, col2),
FOREIGN KEY (col3) REFERENCES ref_table(ref_col) [WITH NO CHECK OPTION],
CHECK (col1 <> col2),
CONSTRAINT uq_name UNIQUE (col3)
```

## Common Patterns

### Volatile Table

```sql
CREATE VOLATILE TABLE vt_temp_results (
    id       INTEGER,
    val      VARCHAR(100)
)
PRIMARY INDEX (id)
ON COMMIT PRESERVE ROWS;
```

### Global Temporary Table

```sql
CREATE GLOBAL TEMPORARY TABLE gt_session_data (
    session_key VARCHAR(64),
    payload     JSON(16776192)
)
PRIMARY INDEX (session_key)
ON COMMIT PRESERVE ROWS;
```

### CREATE TABLE AS with Data

```sql
CREATE TABLE mydb.orders_backup AS (
    SELECT * FROM mydb.orders
) WITH DATA AND STATISTICS;
```

- `WITH DATA` — creates the new table and copies all rows from the source query/table immediately
- `WITH NO DATA` — creates the table structure (columns, data types) but inserts no rows
- `AND STATISTICS` — copies column statistics from the source (useful for optimizer)
- `AND NO STATISTICS` (default) — skips statistics copying

### Queue Table

Queue tables support first-in-first-out (FIFO) row consumption using `SELECT AND CONSUME`. Rows retrieved via SELECT AND CONSUME are atomically read and deleted in FIFO order within each AMP.

```sql
CREATE MULTISET TABLE mydb.work_queue, QUEUE (
    task_id    INTEGER NOT NULL,
    payload    VARCHAR(4000),
    priority   SMALLINT DEFAULT 5,
    insert_ts  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
PRIMARY INDEX (task_id);

-- Consume rows in FIFO order:
SELECT AND CONSUME TOP 1 * FROM mydb.work_queue ORDER BY insert_ts;
```

## Common Errors

### Error 3706: Syntax Error

Common causes in CREATE TABLE:
1. Missing comma between column definitions
2. Table options placed after the column list instead of before it (FALLBACK, JOURNAL must come between table name and opening parenthesis)
3. Reserved words used as column names without double quotes: "date", "time", "user"
4. Wrong clause ordering: ON COMMIT must come after the closing parenthesis and PI
5. PARTITION BY placed inside the column list instead of after
6. Missing data type on a column definition
7. Unmatched parentheses

Fix: Check that option ordering is: `CREATE TABLE name, option, option (columns) PI PARTITION ON COMMIT;`

### Other Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| 2631: Table already exists | CREATE on existing table | Use `CREATE TABLE IF NOT EXISTS` or drop first |
| 5312: Duplicate row error | INSERT into SET table with duplicate PI values | Use MULTISET or adjust PI |
| 3524: LOB type in PI | LOB/XML/JSON used in primary index | Choose a different PI column |
| 2646: No space | Insufficient perm space in target database | Request space allocation or clean up |

## Privileges Required

- `CREATE TABLE` on the target database
- `UDTUSAGE` on SYSUDTLIB if UDT columns are used
- `CONSTRAINT ASSIGNMENT` if row-level security columns are included
- `INSERT` on journal table if journaling is specified

## References


> **Access:** `skill_resource_read(action="read", skill="create-table", path="references/FILENAME")` — do NOT call `list`.

- [Table Options Reference](./references/table-options.md) — FALLBACK, journaling, checksum, freespace, block compression, DATABLOCKSIZE, MERGEBLOCKRATIO
- [Column Attributes and Constraints Reference](./references/column-attributes-and-constraints.md) — Data types, compression, identity columns, CHECK/FK/PK constraints

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 3
