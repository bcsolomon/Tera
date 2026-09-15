---
name: sql-udfs
description: 'Create, modify, look up, and use SQL User Defined Functions (UDFs) on Teradata. Use when writing pure-SQL scalar UDFs or table UDFs. Covers CREATE/REPLACE/DROP FUNCTION, INLINE TYPE 1 optimization, determinism, SPECIFIC names, overloading, granting privileges, calling UDFs in queries, and discovering UDFs via DBC catalog views. For external (C/C++/Java) UDFs and aggregate UDFs, see teradata-external-udf.'
metadata:
  author: teradata
  version: "2.0"
  license: Proprietary
  copyright: "© 2026 Teradata Corporation. All rights reserved."
---

> **Tool Usage:**
> - Use `execute_sql` (teradata-sql-query-executor group) for DDL statements: CREATE/REPLACE/DROP FUNCTION, GRANT, COMMENT ON
> - Use `base_readQuery` (teradata-base group) for SELECT queries: testing UDFs, querying DBC catalog views, SHOW FUNCTION
> - Other useful teradata-base tools: `base_tableDDL`, `base_tableList`, `base_databaseList`, `base_columnDescription`, `base_tablePreview`, `base_db_info`
>
> **Tool Discovery & Management:**
> - `teradata_tool_help` — Get general help and orientation on available tools
> - `teradata_list_patterns` — List available tool groups/patterns
> - `teradata_search_tools` — Search and discover tools by pattern
> - `teradata_get_tool_schema` — Get the full parameter schema for a specific tool
> - `teradata_tool_call` — Execute a native Teradata tool directly
> - `teradata_cleanup_jobs` — Clean up long-running jobs

# Teradata SQL User Defined Functions (UDFs)

## When to Use

- Creating new scalar or table functions written in **pure SQL**
- Encapsulating reusable SQL expressions as named functions
- Modifying or replacing existing SQL UDFs
- Calling UDFs in SELECT, WHERE, HAVING, or other SQL clauses
- Granting execution privileges on UDFs
- **Discovering existing UDFs** in the catalog by name, database, or purpose
- **Reading UDF comments** to understand what a function does before using it
- **Adding comments to UDFs** to make them discoverable by description

> **Not this skill:** For external UDFs written in C/C++/Java, aggregate UDFs (4-phase C functions), or table operators, see **teradata-external-udf** in `04-external-udfs-and-table-functions/`.

## UDF Types Covered Here

| Type | Returns | Language | Use Case |
|------|---------|----------|----------|
| **Scalar UDF** | Single value per row | SQL | Transformations, calculations, formatting |
| **Table UDF** | Result set (table) | SQL | Generating rows, filtering, pivoting |

> `CREATE FUNCTION` must be granted explicitly. `DROP FUNCTION` and `EXECUTE FUNCTION WITH GRANT OPTION` are auto-granted on each function you create. `GRANT ALTER FUNCTION` targets a database, not a specific function.

## Procedure: Creating a SQL Scalar UDF

1. Determine the function name, parameters, and return type
2. Choose the appropriate database to house the function
3. Write the function body using SQL expressions
4. Use `CREATE FUNCTION` or `REPLACE FUNCTION` syntax
5. Grant EXECUTE FUNCTION privileges to users/roles

### SQL Scalar UDF Syntax

```sql
REPLACE FUNCTION database_name.function_name (
    param1 data_type,
    param2 data_type
)
RETURNS result_data_type
SPECIFIC specific_name
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
COLLATION INVOKER
INLINE TYPE 1
RETURN expression;
```

### Key Clauses

- **LANGUAGE SQL**: function body is pure SQL
- **DETERMINISTIC**: same inputs always produce same output (enables optimization)
- **NOT DETERMINISTIC**: output may vary for same inputs (e.g., uses RANDOM, CURRENT_TIMESTAMP)
- **CONTAINS SQL**: function contains SQL but does not read or modify data
- **READS SQL DATA**: function reads from tables (prevents inlining)
- **MODIFIES SQL DATA**: function inserts, updates, or deletes data
- **COLLATION INVOKER**: uses the session collation of the caller
- **INLINE TYPE 1**: allows the optimizer to inline the function body for better performance
- **SPECIFIC specific_name**: provides a unique internal identifier (required for overloading)

### Grant Access

```sql
-- Developer: allow creating and replacing UDFs in a database
GRANT CREATE FUNCTION ON udf_db TO udf_developer_role;

-- Consumer: allow calling all UDFs in a database
GRANT EXECUTE FUNCTION ON udf_db TO app_role;

-- Consumer: allow calling one specific overload (preferred for overloaded functions)
GRANT EXECUTE ON SPECIFIC FUNCTION udf_db.function_v1 TO app_role;

-- Consumer: allow calling one function by signature
GRANT EXECUTE FUNCTION ON udf_db.function_name(INTEGER, VARCHAR(100)) TO app_role;
```

## Procedure: Creating a SQL Table UDF

Table UDFs return a result set and can be used in the FROM clause.

```sql
REPLACE FUNCTION database_name.function_name (
    param1 data_type
)
RETURNS TABLE (
    col1 data_type,
    col2 data_type
)
LANGUAGE SQL
READS SQL DATA
DETERMINISTIC
COLLATION INVOKER
RETURN (
    SELECT col1, col2
    FROM some_table
    WHERE some_column = param1
);
```

### Table UDF Usage

```sql
-- Table UDFs appear in FROM clause with TABLE keyword
SELECT * FROM TABLE(database_name.table_func(param1)) AS t;

-- Can be joined like any other table
SELECT t.col1, s.other_col
FROM TABLE(database_name.table_func(123)) AS t
JOIN sales_db.summary s ON t.key_col = s.key_col;
```

## Calling UDFs in Queries

```sql
-- Scalar UDF in SELECT
SELECT database_name.function_name(column1, column2) AS result
FROM my_table;

-- Scalar UDF in WHERE
SELECT * FROM my_table
WHERE database_name.function_name(column1) > threshold;

-- Scalar UDF in HAVING
SELECT department, SUM(amount) AS total
FROM transactions
GROUP BY department
HAVING database_name.function_name(SUM(amount)) > 0;
```

## Overloading Functions

Teradata supports function overloading: multiple functions with the same name but different parameter signatures. Use the `SPECIFIC` clause to provide unique internal identifiers.

```sql
REPLACE FUNCTION util_db.format_amount (amt DECIMAL(18,2))
RETURNS VARCHAR(30)
SPECIFIC format_amount_decimal
LANGUAGE SQL CONTAINS SQL DETERMINISTIC COLLATION INVOKER INLINE TYPE 1
RETURN ('$' || TRIM(CAST(amt AS FORMAT '---,---,--9.99')));

REPLACE FUNCTION util_db.format_amount (amt INTEGER)
RETURNS VARCHAR(30)
SPECIFIC format_amount_int
LANGUAGE SQL CONTAINS SQL DETERMINISTIC COLLATION INVOKER INLINE TYPE 1
RETURN ('$' || TRIM(CAST(amt AS FORMAT '---,---,--9')));
```

## Procedure: Discovering UDFs from the Catalog

Use the Teradata DBC views to find existing UDFs by name, database, type, or comment text.

### List All UDFs in a Database

```sql
SELECT FunctionName, SpecificName, FunctionType, NumParameters
FROM DBC.FunctionsV
WHERE DatabaseName = 'database_name'
ORDER BY FunctionName;
```

### Search UDFs by Name Pattern

```sql
SELECT DatabaseName, FunctionName, FunctionType, NumParameters
FROM DBC.FunctionsV
WHERE FunctionName LIKE '%search_term%'
ORDER BY DatabaseName, FunctionName;
```

### Get Full UDF Details

```sql
SELECT f.DatabaseName, f.FunctionName, f.FunctionType,
       f.NumParameters, f.ParameterDataTypes, f.ReturnType,
       f.LanguageName, f.DeterministicOpt, f.SQLDataAccess
FROM DBC.FunctionsV f
WHERE f.DatabaseName = 'database_name'
  AND f.FunctionName = 'function_name';
```

### Search UDFs by Comment Text (Find by Purpose)

```sql
SELECT c.DatabaseName, c.ObjectName, c.CommentString,
       f.FunctionType, f.NumParameters
FROM DBC.ObjectCommentsV c
JOIN DBC.FunctionsV f
  ON c.DatabaseName = f.DatabaseName
  AND c.ObjectName = f.FunctionName
WHERE c.ObjectType = 'F'
  AND c.CommentString LIKE '%search_keyword%'
ORDER BY c.DatabaseName, c.ObjectName;
```

### Add or Update a Comment on a UDF

```sql
COMMENT ON FUNCTION database_name.function_name AS
'Brief description of what this function does, its domain, and intended use cases.';
```

### Get UDF Source Code

```sql
SHOW FUNCTION database_name.function_name;
```

### FunctionType Values

| FunctionType | Meaning |
|--------------|---------|
| `F` | Scalar function |
| `A` | Aggregate function (external) |
| `R` | Table function (returns rows) |
| `L` | Table operator |
| `B` | Ordered aggregate (analytical) |

See [UDF Catalog Lookup reference](./references/catalog-lookup.md) for advanced queries and metadata interpretation.

## Managing UDFs

```sql
-- Drop a function
DROP FUNCTION database_name.function_name;

-- Grant execute privilege
GRANT EXECUTE FUNCTION ON database_name.function_name TO user_or_role;

-- Show function definition
SHOW FUNCTION database_name.function_name;

-- List functions in a database
SELECT * FROM DBC.FunctionsV WHERE DatabaseName = 'database_name';
```

## SQL UDF Best Practices

### Performance
- **Always use `INLINE TYPE 1`**: enables the optimizer to substitute the function body into the query plan
- **Mark `DETERMINISTIC`** when possible: enables caching and reduces redundant computation
- **Avoid `READS SQL DATA`** unless necessary: it prevents inlining. Pass needed data as parameters instead.

### Design
- Use descriptive naming: `<domain>_<action>_<subject>` (e.g., `fin_calc_compound_interest`)
- Always include a `SPECIFIC` clause for clarity in traces and overload resolution
- Handle NULL explicitly with COALESCE or CASE WHEN
- Keep functions focused on a single purpose

### Security
- Grant EXECUTE FUNCTION to roles, not individual users
- Group UDFs by domain in dedicated databases (`udf_finance`, `udf_utils`)
- Document each UDF with `COMMENT ON FUNCTION`

See [best-practices.md](./references/best-practices.md) for full guidelines including testing, versioning, and anti-patterns.

## Common Errors and Solutions

| Error | Cause | Fix |
|-------|-------|-----|
| `Function already exists` | Duplicate name | Use `REPLACE FUNCTION` instead of `CREATE FUNCTION` |
| `No privilege for EXECUTE FUNCTION` | Missing grant | `GRANT EXECUTE FUNCTION ON db.func TO role` |
| `SPL1027: Missing RETURN statement` | No RETURN in body | Add `RETURN expression;` at end |
| `Invalid type conversion` | Type mismatch | Check parameter/return types match usage |
| `Function not deterministic` | Used in invalid context | Add `NOT DETERMINISTIC` or remove non-deterministic expressions |

## References


> **Access:** `skill_resource_read(action="read", skill="sql-udfs", path="references/FILENAME")` — do NOT call `list`.

- [Creating SQL UDFs](./references/creating-sql-udfs.md): detailed syntax guide with examples, overloading, and NULL handling
- [UDF Catalog Lookup](./references/catalog-lookup.md): discovering UDFs via DBC views, comments, and privilege checking
- [Best Practices](./references/best-practices.md): performance, naming, security, testing, and anti-patterns

## Templates

- [Scalar UDF Template](./assets/scalar-udf.md)
- [Table UDF Template](./assets/table-udf.md)
