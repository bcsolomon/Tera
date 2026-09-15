# Alter Table Operations — Complete Reference

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 3

## Online vs Offline ALTER Operations

Some ALTER TABLE operations can proceed while the table remains accessible; others require exclusive locks.

### Online Operations (Table Remains Accessible)

| Operation | Notes |
|-----------|-------|
| ADD nullable column with DEFAULT | Metadata-only change |
| ADD column with COMPRESS | Metadata-only if no default |
| MODIFY FORMAT/TITLE | Metadata-only |
| MODIFY DEFAULT | Metadata-only |
| ADD/DROP CHECK constraint | Metadata change + validation |
| MODIFY CHECKSUM | Metadata-only |

### Offline Operations (Exclusive Lock Required)

| Operation | Notes |
|-----------|-------|
| ADD NOT NULL column | All rows must be updated |
| DROP column | Table rewrite to remove column data |
| MODIFY data type | Table rewrite to convert data |
| ADD/REMOVE FALLBACK | Full table copy/removal |
| ADD/CHANGE column compression | Table rebuild |
| TO SET / TO MULTISET | Duplicate check + metadata |
| MODIFY column width (narrowing) | Data validation pass |

## Data Type Conversion Rules

### Numeric Conversions

| From | To | Allowed | Notes |
|------|----|---------|-------|
| BYTEINT | SMALLINT | Yes | Widening — always safe |
| SMALLINT | INTEGER | Yes | Widening |
| INTEGER | BIGINT | Yes | Widening |
| BIGINT | INTEGER | Yes | May overflow |
| DECIMAL(p1,s1) | DECIMAL(p2,s2) where p2≥p1, s2≥s1 | Yes | Widening |
| DECIMAL(p1,s1) | DECIMAL(p2,s2) where p2<p1 or s2<s1 | Conditional | May truncate/overflow |
| INTEGER | DECIMAL | Yes | Safe conversion |
| FLOAT | DECIMAL | Yes | May lose precision |
| NUMBER | DECIMAL | Yes | Compatible |

### Character Conversions

| From | To | Allowed | Notes |
|------|----|---------|-------|
| CHAR(n1) | CHAR(n2) where n2>n1 | Yes | Padded with spaces |
| CHAR(n1) | VARCHAR(n2) | Yes | Trailing spaces handled |
| VARCHAR(n1) | VARCHAR(n2) where n2>n1 | Yes | Widening — always safe |
| VARCHAR(n1) | VARCHAR(n2) where n2<n1 | Yes | Data truncation if values exceed n2 |
| VARCHAR | CHAR | Yes | Padded with spaces |
| CHAR/VARCHAR | CLOB | Yes | Safe conversion |
| CLOB | CHAR/VARCHAR | Conditional | May truncate |

### Date/Time Conversions

| From | To | Allowed | Notes |
|------|----|---------|-------|
| DATE | TIMESTAMP | Yes | Time portion set to 00:00:00 |
| TIMESTAMP | DATE | Yes | Time portion lost |
| TIMESTAMP(p1) | TIMESTAMP(p2) | Yes | Precision change |
| TIME | TIMESTAMP | No | Incompatible |

### Incompatible Conversions

These require dropping and re-adding the column:
- Numeric to character (or vice versa)
- DATE to numeric
- LOB types to non-LOB types
- UDT to different UDT

## ADD Column Details

### Adding to a SET Table

When adding a column to a SET table, the system must verify that no duplicate rows exist after the addition:
- If the new column has a DEFAULT, all rows get the same value — no duplicate check needed
- If the new column allows NULL, all rows get NULL — duplicate check may be needed

### Adding with Compression

```sql
-- Add column with value-list compression
ALTER TABLE mydb.orders ADD payment_type VARCHAR(10)
    COMPRESS ('CASH', 'CARD', 'WIRE');

-- Add column with algorithmic compression
ALTER TABLE mydb.documents ADD content VARCHAR(64000)
    COMPRESS USING TD_LZ_COMPRESS
    DECOMPRESS USING TD_LZ_DECOMPRESS;
```

### Adding Multiple Columns

Teradata ALTER TABLE supports only one ADD/DROP/MODIFY per statement. For multiple changes, use separate statements:

```sql
ALTER TABLE mydb.employees ADD middle_name VARCHAR(50);
ALTER TABLE mydb.employees ADD nickname VARCHAR(50);
ALTER TABLE mydb.employees ADD phone VARCHAR(20);
```

## DROP Column Details

### Restrictions

Cannot drop a column if it is:
- Part of the primary index
- Part of a partitioning expression
- Referenced by a secondary index (drop the index first)
- Referenced by a join index (drop the join index first)
- Referenced by a view (drop or alter the view first)
- Referenced by a CHECK constraint (drop the constraint first)
- Referenced by a FOREIGN KEY constraint (drop the constraint first)
- The only column remaining in the table

### Process

1. The system rewrites all rows without the dropped column
2. Secondary indexes on other columns are rebuilt
3. Statistics collected on the dropped column are removed
4. Perm space may decrease after the operation

## MODIFY Column Details

### Widening a Column

```sql
-- Safe: widen VARCHAR
ALTER TABLE mydb.employees MODIFY employee_name VARCHAR(200);
```

- No data loss risk
- May require table rewrite if internal storage format changes
- Minimal performance impact

### Narrowing a Column

```sql
-- Risky: narrow VARCHAR — existing data may exceed new limit
ALTER TABLE mydb.employees MODIFY employee_name VARCHAR(50);
```

- System checks all rows for values exceeding the new limit
- Fails if any row has a value longer than the new limit
- Use a SELECT to verify first:

```sql
SELECT MAX(CHAR_LENGTH(employee_name)) FROM mydb.employees;
```

### Changing Nullability

```sql
-- Add NOT NULL (fails if NULLs exist)
ALTER TABLE mydb.employees MODIFY email NOT NULL;

-- Remove NOT NULL
ALTER TABLE mydb.employees MODIFY email NULL;
```

Before adding NOT NULL, verify no NULLs exist:

```sql
SELECT COUNT(*) FROM mydb.employees WHERE email IS NULL;
```

## FALLBACK Toggle Details

### Enabling FALLBACK

```sql
ALTER TABLE mydb.orders FALLBACK;
```

1. System acquires an exclusive lock on the table
2. Creates a fallback copy of every row on a buddy AMP
3. Doubles the perm space used by the table
4. Future DML maintains both copies

**Duration:** Proportional to table size. For large tables, schedule during maintenance windows.

### Disabling FALLBACK

```sql
ALTER TABLE mydb.orders NO FALLBACK;
```

1. System acquires an exclusive lock
2. Removes all fallback copies
3. Frees approximately half the table's perm space

## SET / MULTISET Conversion

### Converting SET to MULTISET

```sql
ALTER TABLE mydb.orders TO MULTISET;
```

- Fast metadata-only operation
- No data validation needed
- Future INSERTs will allow duplicate rows

### Converting MULTISET to SET

```sql
ALTER TABLE mydb.orders TO SET;
```

1. System scans the entire table for duplicate rows
2. If duplicates are found, the operation fails
3. Remove duplicates first:

```sql
-- Identify duplicates
SELECT col1, col2, COUNT(*)
FROM mydb.orders
GROUP BY col1, col2
HAVING COUNT(*) > 1;

-- Remove duplicates (keep one copy)
DELETE FROM mydb.orders
WHERE ROWID NOT IN (
    SELECT MIN(ROWID) FROM mydb.orders GROUP BY col1, col2
);
```

## Locking During ALTER TABLE

| Operation | Lock Type | Duration |
|-----------|-----------|----------|
| ADD nullable column | Write → Exclusive briefly | Short |
| DROP column | Exclusive | Proportional to table size |
| MODIFY data type | Exclusive | Proportional to table size |
| FALLBACK toggle | Exclusive | Proportional to table size |
| CHECKSUM/FORMAT change | Write briefly | Short |
| Constraint ADD/DROP | Write → Exclusive briefly | Short to moderate |

## Best Practices

1. **Test on small table first** — verify ALTER syntax before running on production
2. **Check space** — ensure sufficient perm space for table rewrite operations
3. **Schedule offline ALTERs** — during low-activity periods
4. **Collect statistics after** — column additions/modifications may affect query plans
5. **Update dependent objects** — views, macros, and procedures may need updates after schema changes
