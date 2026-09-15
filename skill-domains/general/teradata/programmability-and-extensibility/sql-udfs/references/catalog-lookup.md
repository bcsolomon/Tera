# UDF Catalog Lookup and Comments on Teradata

> **Source:** Teradata Vantage SQL Data Definition Language Syntax and Examples, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-Data-Definition-Language-Syntax-and-Examples  
> **Extraction date:** 2025-07  
> **Topics:** UDF Catalog Lookup and Comments on Teradata

## Overview

Teradata stores UDF metadata in the DBC (Data Base Computer) system views. These views allow you to discover existing UDFs, inspect their signatures, read comments that describe their purpose, and identify the right function to use for a task.

## Key Catalog Views

| View | Purpose |
|------|---------|
| `DBC.FunctionsV` | All function metadata: name, type, parameters, language, etc. |
| `DBC.ObjectCommentsV` | Comments attached to any database object (filter ObjectType = 'F') |
| `DBC.ColumnsV` | Parameter details for functions (treated as "columns") |
| `DBC.AllRightsV` | Privileges granted on functions |
| `DBC.SysExternalFiles` | Installed external UDF shared objects/JARs |

## DBC.FunctionsV — Column Reference

| Column | Description |
|--------|-------------|
| `DatabaseName` | Database containing the function |
| `FunctionName` | Function name |
| `SpecificName` | Unique identifier (from SPECIFIC clause) |
| `FunctionType` | `F` = Scalar, `A` = Aggregate, `R` = Table, `L` = Table operator, `B` = Ordered aggregate |
| `ExternalName` | External object path (NULL for SQL UDFs) |
| `NumParameters` | Number of input parameters |
| `ParameterDataTypes` | Encoded parameter type information |
| `ReturnType` | Return data type |
| `LanguageName` | `SQL`, `C`, `CPP`, `JAVA` |
| `DeterministicOpt` | `Y` = Deterministic, `N` = Not deterministic |
| `NullCall` | `Y` = Called on NULL input, `N` = Returns NULL on NULL |
| `SQLDataAccess` | `CONTAINS SQL`, `READS SQL DATA`, `MODIFIES SQL DATA`, `NO SQL` |
| `CreateTimeStamp` | When the function was created |
| `LastAlterTimeStamp` | Last modification time |
| `CreatorName` | User who created/replaced the function |

## Discovering UDFs

### List All UDFs Across All Databases

```sql
SELECT DatabaseName, FunctionName, FunctionType, LanguageName, NumParameters
FROM DBC.FunctionsV
ORDER BY DatabaseName, FunctionName;
```

### List UDFs in a Specific Database

```sql
SELECT FunctionName, FunctionType, LanguageName, NumParameters,
       DeterministicOpt, SQLDataAccess, CreateTimeStamp
FROM DBC.FunctionsV
WHERE DatabaseName = 'my_database'
ORDER BY FunctionName;
```

### Search by Function Name Pattern

```sql
SELECT DatabaseName, FunctionName, FunctionType, NumParameters
FROM DBC.FunctionsV
WHERE FunctionName LIKE '%calc%'
   OR FunctionName LIKE '%compute%'
ORDER BY DatabaseName, FunctionName;
```

### Find UDFs by Type

```sql
-- All scalar functions
SELECT DatabaseName, FunctionName FROM DBC.FunctionsV WHERE FunctionType = 'F';

-- All aggregate functions
SELECT DatabaseName, FunctionName FROM DBC.FunctionsV WHERE FunctionType = 'A';

-- All table functions
SELECT DatabaseName, FunctionName FROM DBC.FunctionsV WHERE FunctionType = 'R';

-- All table operators
SELECT DatabaseName, FunctionName FROM DBC.FunctionsV WHERE FunctionType = 'L';

-- All ordered aggregate (analytical) functions
SELECT DatabaseName, FunctionName FROM DBC.FunctionsV WHERE FunctionType = 'B';
```

### Find UDFs by Language

```sql
-- All external C/C++ UDFs
SELECT DatabaseName, FunctionName, ExternalName
FROM DBC.FunctionsV
WHERE LanguageName IN ('C', 'CPP')
ORDER BY DatabaseName, FunctionName;

-- All SQL UDFs
SELECT DatabaseName, FunctionName
FROM DBC.FunctionsV
WHERE LanguageName = 'SQL';
```

### Find Recently Created or Modified UDFs

```sql
SELECT DatabaseName, FunctionName, CreatorName,
       CreateTimeStamp, LastAlterTimeStamp
FROM DBC.FunctionsV
WHERE LastAlterTimeStamp > CURRENT_DATE - INTERVAL '30' DAY
ORDER BY LastAlterTimeStamp DESC;
```

## Working with UDF Comments

### Reading Comments

Comments provide human-readable descriptions of what a function does, making UDFs discoverable by purpose rather than just name.

```sql
-- Get comment for a specific function
SELECT CommentString
FROM DBC.ObjectCommentsV
WHERE DatabaseName = 'my_database'
  AND ObjectName = 'my_function'
  AND ObjectType = 'F';
```

### List All UDFs with Their Comments

```sql
SELECT f.DatabaseName, f.FunctionName, f.FunctionType,
       f.NumParameters, c.CommentString
FROM DBC.FunctionsV f
LEFT JOIN DBC.ObjectCommentsV c
  ON f.DatabaseName = c.DatabaseName
  AND f.FunctionName = c.ObjectName
  AND c.ObjectType = 'F'
WHERE f.DatabaseName = 'my_database'
ORDER BY f.FunctionName;
```

### Find UDFs by Comment Content (Semantic Search)

```sql
-- Find functions related to "email" by comment
SELECT f.DatabaseName, f.FunctionName, f.FunctionType,
       c.CommentString
FROM DBC.FunctionsV f
JOIN DBC.ObjectCommentsV c
  ON f.DatabaseName = c.DatabaseName
  AND f.FunctionName = c.ObjectName
  AND c.ObjectType = 'F'
WHERE c.CommentString LIKE '%email%'
   OR c.CommentString LIKE '%mail%'
ORDER BY f.DatabaseName, f.FunctionName;
```

### Find UDFs Without Comments (Undocumented)

```sql
SELECT f.DatabaseName, f.FunctionName, f.FunctionType
FROM DBC.FunctionsV f
LEFT JOIN DBC.ObjectCommentsV c
  ON f.DatabaseName = c.DatabaseName
  AND f.FunctionName = c.ObjectName
  AND c.ObjectType = 'F'
WHERE c.CommentString IS NULL
  AND f.DatabaseName = 'my_database'
ORDER BY f.FunctionName;
```

### Adding Comments to UDFs

```sql
-- Add a comment to a function
COMMENT ON FUNCTION my_database.calc_compound_interest AS
'Calculates compound interest given principal, annual rate, and years. Domain: Finance. Returns DECIMAL(18,2) amount.';

-- Update an existing comment (same syntax — overwrites)
COMMENT ON FUNCTION my_database.mask_email AS
'Masks email addresses for privacy compliance. Shows first 2 chars + domain. Domain: Security/PII. Input: VARCHAR email. Returns: VARCHAR masked email.';

-- Remove a comment
COMMENT ON FUNCTION my_database.old_function AS '';
```

### Comment Best Practices

Write comments that enable identification by purpose. Include:

1. **What it does** — one-sentence description of behavior
2. **Domain** — business area (Finance, Security, ETL, Analytics, etc.)
3. **Input/Output** — brief parameter and return description
4. **Usage context** — when to use this function

Example format:
```
'<What it does>. Domain: <area>. Params: <brief>. Returns: <brief>. Use for: <context>.'
```

Good examples:
```sql
COMMENT ON FUNCTION udf_lib.safe_divide AS
'Divides numerator by denominator, returns NULL on zero/NULL denominator. Domain: Math/Utility. Params: (DECIMAL numerator, DECIMAL denominator). Returns: DECIMAL. Use for: avoiding division-by-zero errors in calculations.';

COMMENT ON FUNCTION udf_lib.customer_tier AS
'Maps annual spend amount to tier label (Platinum/Gold/Silver/Bronze). Domain: Sales/CRM. Params: (DECIMAL annual_spend). Returns: VARCHAR tier name. Use for: customer segmentation and reporting.';
```

## Getting UDF Parameter Details

### From DBC.FunctionsV (Quick View)

```sql
SELECT FunctionName, NumParameters, ParameterDataTypes, ReturnType
FROM DBC.FunctionsV
WHERE DatabaseName = 'my_database'
  AND FunctionName = 'my_function';
```

### From HELP FUNCTION (Interactive)

```sql
HELP FUNCTION my_database.my_function;
```

Returns column-style output showing each parameter name, type, and the return type.

### From SHOW FUNCTION (Full Source)

```sql
SHOW FUNCTION my_database.my_function;
```

Returns the complete CREATE/REPLACE FUNCTION DDL, including the function body for SQL UDFs.

## Checking Privileges

### Who Can Execute a Function?

```sql
-- Users granted EXECUTE FUNCTION directly (AllRightsV has no RoleName column)
SELECT UserName, AccessRight
FROM DBC.AllRightsV
WHERE DatabaseName = 'my_database'
  AND TableName = 'my_function'
  AND AccessRight = 'EF'   -- EF = Execute Function
ORDER BY UserName;

-- Roles granted EXECUTE FUNCTION (role grants live in AllRoleRightsV)
SELECT RoleName, AccessRight
FROM DBC.AllRoleRightsV
WHERE DatabaseName = 'my_database'
  AND TableName = 'my_function'
  AND AccessRight = 'EF'
ORDER BY RoleName;
```

### What Functions Can a User Execute?

```sql
SELECT DatabaseName, TableName AS FunctionName
FROM DBC.AllRightsV
WHERE UserName = 'target_user'
  AND AccessRight = 'EF'
ORDER BY DatabaseName, TableName;
```

## Comprehensive UDF Inventory Query

A single query to get a full picture of all UDFs in a database with their comments, type, language, and parameter count:

```sql
SELECT
    f.FunctionName,
    CASE f.FunctionType
        WHEN 'F' THEN 'Scalar'
        WHEN 'A' THEN 'Aggregate'
        WHEN 'R' THEN 'Table'
        WHEN 'L' THEN 'Table Operator'
        WHEN 'B' THEN 'Ordered Aggregate'
        ELSE f.FunctionType
    END AS FunctionKind,
    f.LanguageName,
    f.NumParameters,
    f.DeterministicOpt AS Deterministic,
    f.SQLDataAccess,
    f.CreatorName,
    f.LastAlterTimeStamp AS LastModified,
    COALESCE(c.CommentString, '(no comment)') AS Description
FROM DBC.FunctionsV f
LEFT JOIN DBC.ObjectCommentsV c
    ON f.DatabaseName = c.DatabaseName
    AND f.FunctionName = c.ObjectName
    AND c.ObjectType = 'F'
WHERE f.DatabaseName = 'my_database'
ORDER BY f.FunctionName;
```

## Overloaded Functions

When a function name is overloaded (multiple signatures), use `SpecificName` to distinguish them:

```sql
SELECT FunctionName, SpecificName, NumParameters, ParameterDataTypes
FROM DBC.FunctionsV
WHERE DatabaseName = 'my_database'
  AND FunctionName = 'format_amount'
ORDER BY SpecificName;
```

Comments on overloaded functions apply to the function name, not individual overloads. To document each overload, include overload details in the comment:

```sql
COMMENT ON FUNCTION my_database.format_amount AS
'Formats numeric amounts as currency strings with $ prefix. Overloads: (DECIMAL) for precise amounts, (INTEGER) for whole numbers. Domain: Formatting/Display.';
```
