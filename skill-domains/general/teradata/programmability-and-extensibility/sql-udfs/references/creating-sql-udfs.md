# Creating SQL UDFs on Teradata

> **Source:** Teradata Vantage SQL Data Definition Language Syntax and Examples, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-Data-Definition-Language-Syntax-and-Examples  
> **Extraction date:** 2025-07  
> **Topics:** Creating SQL UDFs on Teradata

## Overview

SQL UDFs are the simplest UDF type — the function body is written entirely in SQL expressions. They are portable, easy to maintain, and benefit from optimizer inlining.

## Scalar SQL UDF — Full Syntax

```sql
REPLACE FUNCTION database_name.function_name (
    parameter_name_1  data_type_1,
    parameter_name_2  data_type_2
)
RETURNS return_data_type
SPECIFIC specific_function_name
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
COLLATION INVOKER
INLINE TYPE 1
RETURN (
    -- SQL expression using parameters
    expression
);
```

## Parameter Rules

- Maximum 128 parameters per function
- Each parameter must have an explicit name and data type
- Supported data types: INTEGER, DECIMAL, FLOAT, VARCHAR, CHAR, DATE, TIMESTAMP, BYTEINT, SMALLINT, BIGINT, CLOB, BLOB, NUMBER, PERIOD, INTERVAL, ARRAY, VARRAY, JSON
- Parameters are referenced by name in the function body
- Default values are NOT supported for parameters

## Return Type Rules

- Only a single scalar value can be returned (use Table UDF for multiple columns)
- Return type must be compatible with the RETURN expression result
- CAST may be needed if expression result doesn't exactly match the declared return type

## Determinism

| Keyword | Meaning | Optimizer Impact |
|---------|---------|-----------------|
| `DETERMINISTIC` | Same inputs → same output every time | Enables caching and inlining |
| `NOT DETERMINISTIC` | Same inputs may produce different output | Prevents caching |

Functions using any of these are NOT deterministic:
- `CURRENT_DATE`, `CURRENT_TIMESTAMP`, `CURRENT_TIME`
- `RANDOM()`
- `SESSION` variables
- Any function reading from volatile tables

## SQL Access Level

| Keyword | Meaning |
|---------|---------|
| `CONTAINS SQL` | Has SQL but does not access tables (default for SQL UDFs) |
| `READS SQL DATA` | Reads from tables (SELECT) |
| `MODIFIES SQL DATA` | Writes to tables (INSERT/UPDATE/DELETE) |
| `NO SQL` | Contains no SQL (only valid for external UDFs) |

## Examples

### Simple Calculation

```sql
REPLACE FUNCTION finance_db.calc_compound_interest (
    principal DECIMAL(18,2),
    annual_rate DECIMAL(8,6),
    years INTEGER
)
RETURNS DECIMAL(18,2)
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
COLLATION INVOKER
INLINE TYPE 1
RETURN (
    principal * ((1 + annual_rate) ** years)
);
```

### String Manipulation

```sql
REPLACE FUNCTION util_db.mask_email (
    email_addr VARCHAR(256)
)
RETURNS VARCHAR(256)
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
COLLATION INVOKER
INLINE TYPE 1
RETURN (
    SUBSTRING(email_addr FROM 1 FOR 2) ||
    '***' ||
    SUBSTRING(email_addr FROM POSITION('@' IN email_addr))
);
```

### Date Calculation

```sql
REPLACE FUNCTION util_db.business_days_between (
    start_dt DATE,
    end_dt DATE
)
RETURNS INTEGER
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
COLLATION INVOKER
INLINE TYPE 1
RETURN (
    (end_dt - start_dt + 1)
    - ((end_dt - start_dt + 1) / 7) * 2
    - CASE WHEN (start_dt - DATE '0001-01-01') MOD 7 >= 5 THEN 1 ELSE 0 END
    - CASE WHEN (end_dt - DATE '0001-01-01') MOD 7 >= 6 THEN 1 ELSE 0 END
);
```

### Conditional Logic with CASE

```sql
REPLACE FUNCTION sales_db.customer_tier (
    annual_spend DECIMAL(12,2)
)
RETURNS VARCHAR(20)
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
COLLATION INVOKER
INLINE TYPE 1
RETURN (
    CASE
        WHEN annual_spend >= 100000 THEN 'Platinum'
        WHEN annual_spend >= 50000  THEN 'Gold'
        WHEN annual_spend >= 10000  THEN 'Silver'
        ELSE 'Bronze'
    END
);
```

### UDF that Reads Data

```sql
REPLACE FUNCTION lookup_db.get_product_name (
    prod_id INTEGER
)
RETURNS VARCHAR(100)
LANGUAGE SQL
READS SQL DATA
DETERMINISTIC
COLLATION INVOKER
INLINE TYPE 1
RETURN (
    SELECT product_name
    FROM products_db.product_master
    WHERE product_id = prod_id
);
```

## Overloading Functions

Teradata supports function overloading — multiple functions with the same name but different parameter signatures. Use the `SPECIFIC` clause to provide a unique internal identifier:

```sql
REPLACE FUNCTION util_db.format_amount (amt DECIMAL(18,2))
RETURNS VARCHAR(30)
SPECIFIC format_amount_decimal
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
COLLATION INVOKER
INLINE TYPE 1
RETURN ('$' || TRIM(CAST(amt AS FORMAT '---,---,--9.99')));

REPLACE FUNCTION util_db.format_amount (amt INTEGER)
RETURNS VARCHAR(30)
SPECIFIC format_amount_int
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
COLLATION INVOKER
INLINE TYPE 1
RETURN ('$' || TRIM(CAST(amt AS FORMAT '---,---,--9')));
```

## NULL Handling

- If any parameter is NULL, the function body still executes
- Use COALESCE or CASE WHEN param IS NULL to handle NULLs explicitly
- NULL propagation: arithmetic with NULL yields NULL

```sql
REPLACE FUNCTION util_db.safe_divide (
    numerator DECIMAL(18,4),
    denominator DECIMAL(18,4)
)
RETURNS DECIMAL(18,4)
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
COLLATION INVOKER
INLINE TYPE 1
RETURN (
    CASE
        WHEN denominator IS NULL OR denominator = 0 THEN NULL
        ELSE numerator / denominator
    END
);
```
