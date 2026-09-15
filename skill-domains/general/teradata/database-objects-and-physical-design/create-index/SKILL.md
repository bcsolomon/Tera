---
name: create-index
description: 'Create and manage Teradata secondary indexes using CREATE INDEX and DROP INDEX DDL including unique secondary indexes (USI), non-unique secondary indexes (NUSI), value-ordered and hash-ordered secondary indexes, and named indexes. Use when adding secondary indexes to improve query performance, creating unique constraints via USI, choosing between USI and NUSI, ordering indexes by value or hash, dropping indexes, or querying DBC.IndicesV for index metadata.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata CREATE INDEX and DROP INDEX

## When to Use

- Adding secondary indexes (USI/NUSI) to existing tables for query performance
- Creating unique secondary indexes to enforce uniqueness on non-PI columns
- Choosing between USI and NUSI based on query patterns
- Using value-ordered or hash-ordered secondary indexes
- Dropping secondary indexes that are no longer needed
- Creating indexes on join indexes
- Understanding index naming and metadata in DBC.IndicesV

## Core Concepts

### Index Types in Teradata

| Index Type | Created By | Distribution | Access |
|------------|-----------|--------------|--------|
| **UPI** (Unique Primary Index) | `CREATE TABLE ... PRIMARY INDEX` | Hash-distributed, one row per value per AMP | Direct single-AMP lookup |
| **NUPI** (Non-Unique Primary Index) | `CREATE TABLE ... PRIMARY INDEX` | Hash-distributed, multiple rows per value | Single-AMP, may scan multiple rows |
| **USI** (Unique Secondary Index) | `CREATE [UNIQUE] INDEX` | Subtable on all AMPs | Two-AMP operation (subtable → base) |
| **NUSI** (Non-Unique Secondary Index) | `CREATE INDEX` | Subtable on each AMP, local to base rows | All-AMP operation with bit mapping |

### When to Use Each

| Scenario | Recommended Index |
|----------|-------------------|
| Exact-match lookups on non-PI column | USI |
| Range scans on non-PI column | NUSI (value-ordered) |
| Enforce uniqueness on non-PI column | USI |
| Covering index for specific queries | NUSI with all needed columns |
| Aggregate queries needing pre-sorted data | Value-ordered NUSI |

## CREATE INDEX Syntax

```sql
CREATE [UNIQUE] INDEX [index_name] [ALL]
    (column_name [,...])
    [ORDER BY [VALUES | HASH] [(order_column)]]
    [WITH [NO] LOAD IDENTITY]
    ON [database_name.]table_name
;
```

### Key Syntax Elements

| Element | Description |
|---------|-------------|
| `UNIQUE` | Creates a USI — no two rows can have the same index value |
| `index_name` | Optional name for the index (useful for DROP by name) |
| `ALL` | For NUSI on join indexes — maintains row ID pointers for all logical rows |
| `ORDER BY VALUES` | Value-ordered NUSI — rows stored sorted by column value |
| `ORDER BY HASH` | Hash-ordered NUSI — rows stored sorted by hash (default) |
| `WITH LOAD IDENTITY` | Assigns a load identity for concurrent load isolation |

## Common Patterns

### Unique Secondary Index (USI)

```sql
-- Single column USI
CREATE UNIQUE INDEX idx_email ON mydb.employees (email);

-- Multi-column USI
CREATE UNIQUE INDEX idx_order_line
    ON mydb.order_details (order_id, line_number);
```

### Non-Unique Secondary Index (NUSI)

```sql
-- Basic NUSI for equality lookups
CREATE INDEX idx_dept ON mydb.employees (department_id);

-- Named NUSI
CREATE INDEX idx_status ON mydb.orders (order_status);
```

### Value-Ordered NUSI

```sql
-- Ordered by column value for range queries
CREATE INDEX idx_amount
    ORDER BY VALUES (amount)
    ON mydb.transactions (amount);

-- Ordered by a different column
CREATE INDEX idx_cust_date
    ORDER BY VALUES (order_date)
    ON mydb.orders (customer_id);
```

### Hash-Ordered NUSI

```sql
CREATE INDEX idx_hash
    ORDER BY HASH (lookup_key)
    ON mydb.lookup_table (lookup_key);
```

## DROP INDEX Syntax

```sql
-- Drop by index name
DROP INDEX index_name ON [database_name.]table_name;

-- Drop by column definition
DROP INDEX (column_name [,...]) ON [database_name.]table_name;

-- Drop value-ordered index by definition
DROP INDEX (column_name) ORDER BY VALUES (order_column)
    ON [database_name.]table_name;
```

### Examples

```sql
-- Drop named index
DROP INDEX idx_email ON mydb.employees;

-- Drop by column definition
DROP INDEX (department_id) ON mydb.employees;

-- Drop from join index
DROP INDEX idx_ji_col ON mydb.my_join_index;
```

## Querying Index Metadata

```sql
-- List all indexes on a table
SELECT IndexNumber, IndexType, UniqueFlag, IndexName, ColumnName
FROM DBC.IndicesV
WHERE DatabaseName = 'mydb'
  AND TableName = 'employees'
ORDER BY IndexNumber, ColumnPosition;
```

### IndexType Values

| Value | Meaning |
|-------|---------|
| `P` | Primary Index |
| `S` | Secondary Index |
| `K` | Primary Key (constraint-based) |
| `Q` | Partitioning |
| `J` | Join Index |
| `H` | Hash Index |

## Performance Considerations

| Factor | USI | NUSI |
|--------|-----|------|
| **Lookup cost** | 2-AMP (subtable + base) | All-AMP (bit-mapped scan) |
| **Best for** | High-selectivity point lookups | Low-to-medium selectivity, covering queries |
| **Storage overhead** | Subtable on all AMPs | Subtable on each AMP (local) |
| **Maintenance cost** | Moderate (INSERT/UPDATE/DELETE updates subtable) | Moderate |
| **Stale stats impact** | Low — optimizer usually picks USI | High — optimizer may skip NUSI without stats |

### When NOT to Create Indexes

- On very small tables (full-table scan is faster)
- When the column is rarely used in WHERE clauses
- When INSERT/UPDATE/DELETE performance is more critical than SELECT
- On columns with very low cardinality for USI (wastes space)

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| 5312: Duplicate unique index value | INSERT violates USI uniqueness | Fix data or use NUSI |
| 2652: Index already exists | Duplicate CREATE INDEX | Check existing indexes first |
| 3524: Invalid column type for index | LOB/XML/JSON in index | Use a different column |
| 5495: Cannot create USI on NOPI table | NoPI tables don't support USI | Use NUSI or add a PI |

## Privileges Required

- `INDEX` privilege on the table, or
- `DROP TABLE` privilege on the table (grants INDEX implicitly)

## References


> **Access:** `skill_resource_read(action="read", skill="create-index", path="references/FILENAME")` — do NOT call `list`.

- [Secondary Index Internals](./references/secondary-index-internals.md) — USI/NUSI subtable structure, covering indexes, bit mapping, and optimizer interaction

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 5
