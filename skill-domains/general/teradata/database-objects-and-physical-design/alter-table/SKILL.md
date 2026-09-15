---
name: alter-table
description: 'Modify Teradata tables using ALTER TABLE DDL including adding, dropping, and modifying columns, changing table attributes (FALLBACK, JOURNAL, CHECKSUM, BLOCKCOMPRESSION, MERGEBLOCKRATIO, FREESPACE, DATABLOCKSIZE), adding and dropping constraints (PRIMARY KEY, FOREIGN KEY, CHECK, UNIQUE), converting between SET and MULTISET, renaming tables, and using ALTER TABLE TO CURRENT for temporal tables. Use when modifying existing table structures, changing table properties, adding or removing columns, altering constraints, or converting table types.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata ALTER TABLE

## When to Use

- Adding, dropping, or modifying columns on existing tables
- Changing table options (FALLBACK, JOURNAL, CHECKSUM, etc.)
- Adding or dropping constraints (PK, FK, CHECK, UNIQUE)
- Converting between SET and MULTISET table types
- Renaming tables
- Altering table map or colocation assignments
- Using ALTER TABLE TO CURRENT for temporal table schema evolution

## ALTER TABLE Syntax

```sql
ALTER TABLE [database_name.]table_name
  [, table_option_change [,...]]
  { ADD column_definition
  | DROP column_name
  | ADD constraint_definition
  | DROP CONSTRAINT constraint_name
  | MODIFY column_name new_attributes
  | RENAME new_table_name
  }
;
```

## Column Operations

### ADD Column

```sql
-- Add a simple column
ALTER TABLE mydb.employees ADD email VARCHAR(100);

-- Add with NOT NULL and DEFAULT
ALTER TABLE mydb.employees ADD status CHAR(1) NOT NULL DEFAULT 'A';

-- Add with compression
ALTER TABLE mydb.orders ADD channel VARCHAR(20) COMPRESS ('WEB','STORE','MOBILE');

-- Add identity column
ALTER TABLE mydb.events ADD event_id INTEGER GENERATED ALWAYS AS IDENTITY
    (START WITH 1 INCREMENT BY 1);
```

### DROP Column

```sql
ALTER TABLE mydb.employees DROP email;
ALTER TABLE mydb.employees DROP COLUMN email;
```

> **Restriction:** Cannot drop a column that is part of the primary index, a partitioning expression, or referenced by a secondary index, join index, or hash index.

### MODIFY Column (Rename or Change Attributes)

```sql
-- Rename a column
ALTER TABLE mydb.employees RENAME emp_name TO employee_name;

-- Change data type (widen VARCHAR)
ALTER TABLE mydb.employees MODIFY employee_name VARCHAR(200);

-- Add NOT NULL constraint
ALTER TABLE mydb.employees MODIFY email NOT NULL;

-- Change default
ALTER TABLE mydb.orders MODIFY status DEFAULT 'PENDING';

-- Add/change compression
ALTER TABLE mydb.orders MODIFY channel COMPRESS ('WEB','STORE','MOBILE','APP');

-- Change FORMAT
ALTER TABLE mydb.employees MODIFY hire_date FORMAT 'YYYY-MM-DD';
```

### Column Modification Rules

| Change | Allowed | Notes |
|--------|---------|-------|
| Widen VARCHAR | Yes | Always safe |
| Narrow VARCHAR | Yes | Data truncation risk |
| Change CHAR to VARCHAR | Yes | Compatible conversion |
| Change INT to BIGINT | Yes | Widening numeric |
| Narrow numeric | Conditional | May lose data |
| Change between incompatible types | No | Drop and re-add column |
| Add NOT NULL | Yes | Existing NULLs cause error |
| Remove NOT NULL | Yes | Always safe |
| Change DEFAULT | Yes | Affects new rows only |
| Add/change compression | Yes | Table rebuild required |

## Table Option Changes

### FALLBACK

```sql
-- Enable fallback (doubles storage, copies all rows)
ALTER TABLE mydb.orders FALLBACK [PROTECTION];

-- Remove fallback (frees fallback copies)
ALTER TABLE mydb.orders NO FALLBACK [PROTECTION];
```

> **Warning:** Enabling FALLBACK on a large table is a resource-intensive operation that copies every row.

### Journaling

```sql
ALTER TABLE mydb.orders BEFORE JOURNAL;
ALTER TABLE mydb.orders NO BEFORE JOURNAL;
ALTER TABLE mydb.orders AFTER JOURNAL;
ALTER TABLE mydb.orders DUAL AFTER JOURNAL;
ALTER TABLE mydb.orders NO AFTER JOURNAL;
```

### CHECKSUM

```sql
ALTER TABLE mydb.orders CHECKSUM = ON;
ALTER TABLE mydb.orders CHECKSUM = OFF;
ALTER TABLE mydb.orders CHECKSUM = DEFAULT;
```

### BLOCKCOMPRESSION

```sql
ALTER TABLE mydb.orders BLOCKCOMPRESSION = AUTOTEMP;
ALTER TABLE mydb.orders BLOCKCOMPRESSION = MANUAL;
ALTER TABLE mydb.orders BLOCKCOMPRESSION = NEVER;
ALTER TABLE mydb.orders BLOCKCOMPRESSION = DEFAULT;
```

### FREESPACE

```sql
ALTER TABLE mydb.orders FREESPACE = 15 PERCENT;
ALTER TABLE mydb.orders FREESPACE = 0;
```

### MERGEBLOCKRATIO

```sql
ALTER TABLE mydb.orders DEFAULT MERGEBLOCKRATIO;
ALTER TABLE mydb.orders MERGEBLOCKRATIO = 40 PERCENT;
ALTER TABLE mydb.orders NO MERGEBLOCKRATIO;
```

### DATABLOCKSIZE

```sql
ALTER TABLE mydb.orders DATABLOCKSIZE = DEFAULT;
ALTER TABLE mydb.orders MAXIMUM DATABLOCKSIZE = 524288 BYTES;
```

## Constraint Operations

### ADD PRIMARY KEY

```sql
ALTER TABLE mydb.employees ADD PRIMARY KEY (employee_id);
ALTER TABLE mydb.employees ADD CONSTRAINT pk_emp PRIMARY KEY (employee_id);
```

### ADD UNIQUE

```sql
ALTER TABLE mydb.employees ADD UNIQUE (email);
ALTER TABLE mydb.employees ADD CONSTRAINT uq_email UNIQUE (email);
```

### ADD CHECK

```sql
ALTER TABLE mydb.orders ADD CHECK (amount >= 0);
ALTER TABLE mydb.orders ADD CONSTRAINT chk_amount CHECK (amount >= 0);
```

### ADD FOREIGN KEY

```sql
ALTER TABLE mydb.orders ADD FOREIGN KEY (customer_id)
    REFERENCES mydb.customers (customer_id);
```

### DROP CONSTRAINT

```sql
ALTER TABLE mydb.orders DROP CONSTRAINT chk_amount;
ALTER TABLE mydb.employees DROP CONSTRAINT pk_emp;
ALTER TABLE mydb.employees DROP CONSTRAINT uq_email;
```

## Table Type Conversion

### SET to MULTISET

```sql
-- Convert SET table to MULTISET (allows duplicate rows)
ALTER TABLE mydb.orders TO MULTISET;
```

### MULTISET to SET

```sql
-- Convert MULTISET to SET (rejects duplicate rows — fails if duplicates exist)
ALTER TABLE mydb.orders TO SET;
```

> **Warning:** Converting MULTISET to SET will fail if the table contains duplicate rows. Remove duplicates first.

## RENAME TABLE

```sql
RENAME TABLE [database_name.]old_name TO [database_name.]new_name;
-- OR
RENAME TABLE mydb.old_name AS mydb.new_name;
```

### Rules
- Both old and new names must be in the same database
- Views referencing the renamed table are NOT automatically updated
- Macros and stored procedures referencing the old name will fail

## DROP TABLE

```sql
DROP TABLE [database_name.]table_name;
```

- Drops the table definition and all data
- Drops all secondary indexes, join indexes, hash indexes on the table
- Does NOT drop views that reference the table (they become invalid)

## ALTER TABLE (Map and Colocation Form)

```sql
-- Move table to a different map
ALTER TABLE mydb.orders MAP = new_map_name;

-- Change colocation group
ALTER TABLE mydb.orders MAP = SparseMap1 COLOCATE USING new_colocation;
```

## ALTER TABLE TO CURRENT

For temporal tables — evolves the schema while preserving historical data.

```sql
ALTER TABLE mydb.employees TO CURRENT;
```

- Used after modifying a temporal table's validtime schema
- Applies the new schema to the current rows while preserving history

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| 5590: Cannot drop PI column | Column is part of primary index | Cannot drop PI columns — redesign table |
| 3706: Syntax error | Wrong ALTER syntax | Check syntax for specific ALTER operation |
| 2644: Cannot add NOT NULL | Existing rows have NULL values | Update NULLs first or use DEFAULT |
| 5312: Duplicate rows for SET | Converting MULTISET to SET with duplicates | Remove duplicates before conversion |
| 2646: No space | Insufficient perm space for FALLBACK or column add | Request more space |

## Privileges Required

- `ALTER TABLE` on the table (implicit with ownership)
- For RENAME: `DROP TABLE` on the table
- For DROP TABLE: `DROP TABLE` on the table

## References


> **Access:** `skill_resource_read(action="read", skill="alter-table", path="references/FILENAME")` — do NOT call `list`.

- [Alter Table Operations Reference](./references/alter-table-operations.md) — Detailed rules for column modifications, data type conversions, and online vs offline ALTER operations

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 3
