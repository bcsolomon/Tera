---
name: join-and-hash-indexes
description: 'Create and manage Teradata join indexes and hash indexes using CREATE JOIN INDEX and CREATE HASH INDEX DDL. Use when pre-computing joins for query performance, creating single-table or multi-table join indexes, building aggregate join indexes for summary tables, creating sparse join indexes for filtered subsets, using hash indexes for single-table denormalization, choosing between join index types, or altering/dropping join and hash indexes.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Join Indexes and Hash Indexes

## When to Use

- Pre-computing expensive joins to accelerate repeated queries
- Creating aggregate (summary) tables as join indexes
- Filtering large tables into sparse join indexes for subset access
- Using hash indexes for single-table column subsetting
- Choosing between join index, hash index, and materialized views
- Altering or dropping existing join/hash indexes

## Core Concepts

### Join Index vs Hash Index

| Feature | Join Index | Hash Index |
|---------|-----------|------------|
| Tables | Single or multi-table | Single table only |
| Aggregation | Supported (`GROUP BY`) | Not supported |
| Sparse (filtered) | Supported (`WHERE`) | Not supported |
| Column subset | Yes | Yes |
| Maintenance | Automatic on base table DML | Automatic on base table DML |
| PI flexibility | Can differ from base table PI | Must differ from base table PI |

### When to Choose Each

| Scenario | Use |
|----------|-----|
| Accelerate a specific multi-table join | Multi-table join index |
| Pre-aggregate for dashboard queries | Aggregate join index |
| Query a filtered subset of a large table | Sparse join index |
| Redistribute a single table on an alternate key | Hash index or single-table join index |
| Replace PI for different access path | Hash index |

## CREATE JOIN INDEX Syntax

```sql
CREATE JOIN INDEX [database_name.]join_index_name
  [, table_option [,...]]
  AS select_expression
  PRIMARY INDEX [index_name] (column_name [,...])
  [PARTITION BY partition_expression]
  [ORDER BY [VALUES | HASH] (column_name)]
;
```

## Join Index Types

### Single-Table Join Index

Redistributes or reorders a single table on a different primary index.

```sql
CREATE JOIN INDEX mydb.ji_orders_by_date AS
    SELECT order_id, customer_id, order_date, amount
    FROM mydb.orders
PRIMARY INDEX (order_date);
```

### Multi-Table Join Index

Pre-computes a join between two or more tables.

```sql
CREATE JOIN INDEX mydb.ji_order_customer AS
    SELECT o.order_id, o.order_date, o.amount,
           c.customer_name, c.region
    FROM mydb.orders o
    INNER JOIN mydb.customers c ON o.customer_id = c.customer_id
PRIMARY INDEX (order_id);
```

### Aggregate Join Index

Pre-computes aggregated results (summary table).

```sql
CREATE JOIN INDEX mydb.ji_daily_sales AS
    SELECT order_date,
           SUM(amount) AS total_amount,
           COUNT(*) AS order_count
    FROM mydb.orders
    GROUP BY order_date
PRIMARY INDEX (order_date);
```

### Sparse Join Index

Contains only rows matching a filter condition.

```sql
CREATE JOIN INDEX mydb.ji_high_value_orders AS
    SELECT order_id, customer_id, order_date, amount
    FROM mydb.orders
    WHERE amount > 10000
PRIMARY INDEX (order_id);
```

### Partitioned Join Index

```sql
CREATE JOIN INDEX mydb.ji_orders_partitioned AS
    SELECT order_id, customer_id, order_date, amount
    FROM mydb.orders
PRIMARY INDEX (customer_id)
PARTITION BY RANGE_N(order_date BETWEEN DATE '2020-01-01'
    AND DATE '2030-12-31' EACH INTERVAL '1' MONTH);
```

## CREATE HASH INDEX Syntax

```sql
CREATE HASH INDEX [database_name.]hash_index_name
  [, table_option [,...]]
  (column_name [,...])
  ON [database_name.]table_name
  [BY (column_name [,...])]
  [ORDER BY [VALUES | HASH] (column_name)]
;
```

### Hash Index Example

```sql
-- Redistribute employees by department for department-based queries
CREATE HASH INDEX mydb.hi_emp_by_dept
    (employee_id, employee_name, department_id, salary)
    ON mydb.employees
    BY (department_id)
    ORDER BY VALUES (salary);
```

## ALTER and DROP

### ALTER JOIN INDEX

```sql
-- Rebuild after base table changes
ALTER JOIN INDEX mydb.ji_orders_by_date REBUILD;
```

### ALTER HASH INDEX

```sql
-- Move hash index to a different map
ALTER HASH INDEX mydb.hi_emp_by_dept MAP = new_map_name;
```

### DROP JOIN INDEX

```sql
DROP JOIN INDEX [database_name.]join_index_name;
```

### DROP HASH INDEX

```sql
DROP HASH INDEX [database_name.]hash_index_name;
```

## Table Options for Join/Hash Indexes

| Option | Supported |
|--------|-----------|
| FALLBACK | Yes |
| CHECKSUM | Yes |
| BLOCKCOMPRESSION | Yes |
| MAP / COLOCATE USING | Yes |
| FREESPACE | Yes |

```sql
CREATE JOIN INDEX mydb.ji_sales, FALLBACK, CHECKSUM = DEFAULT AS
    SELECT ... FROM ...
PRIMARY INDEX (...);
```

## Querying Join/Hash Index Metadata

```sql
-- List join indexes
SELECT DatabaseName, TableName, TableKind, CreateTimeStamp
FROM DBC.TablesV
WHERE TableKind = 'I'  -- 'I' = Join Index
  AND DatabaseName = 'mydb';

-- List hash indexes
SELECT DatabaseName, TableName, TableKind
FROM DBC.TablesV
WHERE TableKind = 'N'  -- 'N' = Hash Index
  AND DatabaseName = 'mydb';

-- View join index definition
SHOW JOIN INDEX mydb.ji_orders_by_date;

-- View hash index definition
SHOW HASH INDEX mydb.hi_emp_by_dept;
```

## Performance Considerations

- Join indexes consume perm space — maintained automatically on every DML to base tables
- The optimizer transparently substitutes a join index when it covers a query
- Collect statistics on join index columns for optimal query plans
- Use `EXPLAIN` to verify the optimizer is using the join index
- Aggregate join indexes can dramatically reduce query time for summary/dashboard queries

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| 5728: Cannot create join index | Missing privilege or unsupported feature | Check CREATE TABLE privilege on target DB |
| 5738: Join index too wide | Row exceeds max size | Reduce number of columns |
| 2646: No space | Insufficient perm space | Increase space allocation |
| 5495: Base table is NoPI | Join index requires PI on base | Add PI to base table first |

## Privileges Required

- `CREATE TABLE` on the database containing the join/hash index
- `SELECT` on all base tables referenced in the join index definition

## References


> **Access:** `skill_resource_read(action="read", skill="join-and-hash-indexes", path="references/FILENAME")` — do NOT call `list`.

- [Join Index Design Patterns](./references/join-index-design-patterns.md) — Detailed examples of single-table, multi-table, aggregate, and sparse join indexes with optimizer interaction

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 5
