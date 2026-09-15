---
name: macros
description: 'Create and manage Teradata macros using CREATE MACRO, REPLACE MACRO, and DROP MACRO DDL. Use when building parameterized multi-statement macros, encapsulating frequently used SQL operations, creating macros with USING modifiers for parameters, embedding LOCKING clauses in macros, executing macros with EXECUTE, or managing macro lifecycle (rename, drop, help).'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Macros

## When to Use

- Encapsulating frequently used SQL statements in a reusable object
- Creating parameterized queries with typed parameters
- Bundling multiple statements into a single executable unit
- Providing controlled data access to users without exposing underlying tables
- Replacing ad-hoc scripts with server-side stored logic

## Core Concepts

### What Is a Macro?

A macro is a named set of SQL statements stored in the database and executed as a unit. Key characteristics:

| Feature | Detail |
|---------|--------|
| **Multi-statement** | Can contain multiple SQL statements separated by semicolons |
| **Parameterized** | Accepts typed parameters at execution time |
| **Single transaction** | All statements execute in one implicit transaction |
| **Security boundary** | Access controlled by macro owner's privileges, not caller's |
| **Stored in DD** | Definition stored in DBC.TVM and DBC.TextTbl |

### Macro vs Stored Procedure

| Aspect | Macro | Stored Procedure |
|--------|-------|------------------|
| Control flow | No (sequential statements only) | Yes (IF, WHILE, CASE, cursors) |
| Error handling | No HANDLER | DECLARE HANDLER |
| Parameters | Input only (USING) | IN, OUT, INOUT |
| Result sets | Returns all statement results | Controlled via cursors |
| Transaction | Implicit single transaction | Can span multiple transactions |
| Complexity | Simple multi-statement | Complex logic |

## CREATE MACRO Syntax

```sql
{ CREATE MACRO | CM } [database_name.]macro_name
  [ ( parameter_name data_type [,...] ) ]
  AS (
    [USING using_modifier]
    [LOCKING locking_clause]
    sql_statement_1 ;
    [sql_statement_2 ;]
    [...]
  );
```

### REPLACE MACRO

```sql
REPLACE MACRO [database_name.]macro_name
  [ ( parameter_name data_type [,...] ) ]
  AS (
    sql_statement ;
  );
```

## Common Patterns

### Simple Macro (No Parameters)

```sql
CREATE MACRO mydb.m_active_orders AS (
    SELECT order_id, customer_id, order_date, amount
    FROM mydb.orders
    WHERE status = 'ACTIVE'
    ORDER BY order_date DESC;
);
```

### Parameterized Macro

```sql
CREATE MACRO mydb.m_orders_by_customer (
    cust_id INTEGER,
    start_dt DATE,
    end_dt DATE
) AS (
    SELECT order_id, order_date, amount, status
    FROM mydb.orders
    WHERE customer_id = :cust_id
      AND order_date BETWEEN :start_dt AND :end_dt
    ORDER BY order_date;
);
```

### Multi-Statement Macro

```sql
CREATE MACRO mydb.m_monthly_close (
    close_month DATE
) AS (
    -- Archive closed orders
    INSERT INTO mydb.orders_archive
    SELECT * FROM mydb.orders
    WHERE status = 'CLOSED'
      AND order_date < :close_month;

    -- Delete archived orders
    DELETE FROM mydb.orders
    WHERE status = 'CLOSED'
      AND order_date < :close_month;
);
```

### Macro with LOCKING Clause

```sql
CREATE MACRO mydb.m_report_snapshot AS (
    LOCKING mydb.orders FOR ACCESS
    LOCKING mydb.customers FOR ACCESS
    SELECT o.order_date, c.customer_name, SUM(o.amount) AS total
    FROM mydb.orders o
    JOIN mydb.customers c ON o.customer_id = c.customer_id
    GROUP BY 1, 2;
);
```

### Macro with USING Modifier

```sql
CREATE MACRO mydb.m_search_products (
    search_term VARCHAR(100)
) AS (
    USING (search_pattern VARCHAR(100) DEFAULT '%')
    SELECT product_id, product_name, category
    FROM mydb.products
    WHERE product_name LIKE :search_pattern;
);
```

## Executing Macros

```sql
-- No parameters
EXECUTE mydb.m_active_orders;
EXEC mydb.m_active_orders;

-- With parameters
EXECUTE mydb.m_orders_by_customer(12345, DATE '2025-01-01', DATE '2025-12-31');

-- Named parameters (Teradata extension)
EXEC mydb.m_orders_by_customer(cust_id = 12345, start_dt = DATE '2025-01-01', end_dt = DATE '2025-12-31');
```

## Managing Macros

### RENAME MACRO

```sql
RENAME MACRO [database_name.]old_name TO new_name;
```

### DROP MACRO

```sql
DROP MACRO [database_name.]macro_name;
```

### HELP MACRO

```sql
-- Show macro parameters and types
HELP MACRO mydb.m_orders_by_customer;

-- Show macro definition
SHOW MACRO mydb.m_orders_by_customer;
```

## Querying Macro Metadata

```sql
-- List macros in a database
SELECT TableName, CreateTimeStamp, LastAlterTimeStamp
FROM DBC.TablesV
WHERE DatabaseName = 'mydb'
  AND TableKind = 'M';

-- View macro text
SELECT TableName, TextString
FROM DBC.TextTbl
WHERE DatabaseName = 'mydb'
  AND TableKind = 'M'
ORDER BY TableName, LineNo;
```

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| 3706: Syntax error | Invalid SQL in macro body | Validate each statement independently |
| 3523: Macro already exists | CREATE MACRO on existing name | Use REPLACE MACRO instead |
| 3707: Parameter mismatch | Wrong number/type of arguments | Check HELP MACRO for expected parameters |
| 5305: Insufficient privileges | Macro owner lacks privileges on referenced tables | Grant required privileges to macro's owning database |

## Privileges Required

- `CREATE MACRO` on the target database to create
- `DROP MACRO` to drop or replace
- `EXECUTE` on the macro to run it
- Macro owner (containing database) must have all privileges needed by the statements

## Security Considerations

- Macros execute with the privileges of the **owning database**, not the calling user
- This enables controlled access: users can execute a macro without having direct SELECT/INSERT/DELETE on the underlying tables
- Always audit macro definitions to ensure they don't expose unintended data

## References


> **Access:** `skill_resource_read(action="read", skill="macros", path="references/FILENAME")` — do NOT call `list`.

- [Macro Design and Security Patterns](./references/macro-patterns.md) — Advanced macro patterns, security delegation, and parameter handling

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 9
