---
name: scalar-udf-c
description: 'Create, register, test, and manage scalar C/C++ User Defined Functions on Teradata. Covers PARAMETER STYLE SQL convention with null indicators and trailing metadata, in-database compilation via CS! prefix, CO! compiled-object path, sqltypes_td.h type mappings (INTEGER, FLOAT, VARCHAR, DECIMAL, DATE), SPECIFIC clause for overload management, CHARACTER SET on char parameters, body patterns (success/null/error/warning), sqlstate codes, REPLACE FUNCTION for atomic updates, and catalog discovery via DBC.FunctionsV. Use when the user asks to write a C scalar UDF, convert SQL logic to C, map SQL types to C types, debug UDF compilation errors, or register a C function on Teradata.'
when_to_use: 'Use when the user mentions C UDF, scalar UDF, external function in C, C function registration, CREATE FUNCTION LANGUAGE C, LANGUAGE C, EXTERNAL NAME, or wants to implement per-row transformations in C or C++.'
metadata:
  author: teradata
  version: "1.0"
  license: Proprietary
  copyright: "© 2026 Teradata Corporation. All rights reserved."
---

> **Installation differs by platform.** All Teradata systems support external UDFs, XSPs, and UDTs,
> but not all allow the same installation process. The `CREATE`/`REPLACE ... EXTERNAL NAME` DDL in
> this skill applies to on-prem systems where you have full access to the database nodes. On
> Teradata-managed systems, direct DDL installation may be blocked for security reasons:
>
> - **VantageCloud Lake:** use the `tdextroutine` CLI to install, list, and uninstall these objects.
>   See [Create, Use, and Migrate UDFs and External Stored Procedures in VantageCloud Lake](https://docs.teradata.com/r/Lake-Using-Queries-UDFs-and-External-Stored-Procedures/Create-Use-and-Migrate-UDFs-and-External-Stored-Procedures-in-VantageCloud-Lake).
> - **VantageCloud Enterprise:** `EXTERNAL NAME` installation is supported on Compute Engine nodes
>   but not on the primary Enterprise Data Warehouse (EDW) node; that is typically handled through a
>   customer service request.
>
> Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`.

# Teradata Scalar C/C++ UDFs

## When to Use

- Writing a custom per-row transformation in C or C++ that cannot be expressed in SQL
- Converting SQL expressions to compiled C for performance-critical workloads
- Implementing string manipulation, numeric computation, or date logic in C
- Generating C function code from an SQL type specification
- Debugging compilation or registration errors for C scalar UDFs
- Granting or managing privileges for existing C scalar UDFs

> **Not this skill:** For aggregate UDFs (4-phase), see **aggregate-udf-c**. For table functions, see **table-function-udf-c**. For table operators, see **table-operator-udf-c**. For pure SQL UDFs, see **sql-udfs**. For Java UDFs, see **scalar-udf-java**.

## Core Concepts

### How C Scalar UDFs Work

C source code is **uploaded to and compiled within the database**. The `CS!` prefix in EXTERNAL NAME means "C Source". The database receives the `.c` file and compiles it internally with its own compiler and `sqltypes_td.h` header. Never compile outside the database.

### PARAMETER STYLE SQL Convention

Every C scalar UDF follows this parameter order:

1. **Value pointers**: one per SQL parameter, then the result
2. **Null indicators**: one `int *` per parameter and result (`-1` = NULL, `0` = NOT NULL)
3. **Trailing metadata**: `sqlstate[6]`, `extname[129]`, `specific_name[129]`, `error_msg[257]`

> `CREATE FUNCTION` must be granted explicitly. `DROP FUNCTION` and `EXECUTE FUNCTION WITH GRANT OPTION` are auto-granted on each function you create. See [Privilege Setup](./references/privilege-setup.md) for the full matrix including UDT grants and SPECIFIC FUNCTION syntax.

## Procedure: Create a C Scalar UDF

### Step 1: Write the C Source

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"

void double_value(
    INTEGER       *input_val,
    INTEGER       *result,
    int           *input_val_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257])
{
    if (*input_val_null == -1) {
        *result_null = -1;
        return;
    }
    *result = *input_val * 2;
    *result_null = 0;
}
```

### Step 2: Register the Function

```sql
CREATE FUNCTION mydb.double_value (input_val INTEGER)
RETURNS INTEGER
SPECIFIC double_value_int_impl     -- unique name for this overload; required for DROP SPECIFIC
LANGUAGE C
NO SQL
DETERMINISTIC
CALLED ON NULL INPUT
EXTERNAL NAME 'CS!double_value!double_value.c'
PARAMETER STYLE SQL;
```

The database compiles the C source internally. No client-side `gcc` is needed.

`SPECIFIC` names the exact overload; use `DROP SPECIFIC FUNCTION mydb.double_value_int_impl`
to drop one overload without affecting others with the same function name.

### Step 3: Grant Access

Grant the developer role privileges to create and manage UDFs, and grant application
users the ability to call the function:

```sql
-- Developer: allow creating and replacing UDFs in the target database
GRANT CREATE FUNCTION ON mydb TO udf_developer_role;

-- Developer: allow dropping and replacing UDFs (DROP also authorises REPLACE)
GRANT DROP FUNCTION ON mydb TO udf_developer_role;

-- Developer: allow altering execution mode/recompile (GRANT targets database, not a specific function)
GRANT ALTER FUNCTION ON mydb TO udf_developer_role;

-- Consumer: allow calling all functions in the database
GRANT EXECUTE FUNCTION ON mydb TO app_role;

-- Consumer: allow calling a specific function by SPECIFIC name
GRANT EXECUTE ON SPECIFIC FUNCTION mydb.double_value TO app_role;
```

> The user who creates the UDF automatically receives `EXECUTE FUNCTION WITH GRANT OPTION`
> on it. Only additional users need the explicit grant.

### Step 4: Test

```sql
SELECT mydb.double_value(10);  -- Expected: 20
SELECT mydb.double_value(NULL); -- Expected: NULL
```

## Procedure: Create a VARCHAR Scalar UDF

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"

void greet_user(
    VARCHAR_LATIN *user_name,
    VARCHAR_LATIN *result,
    int           *user_name_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257])
{
    if (*user_name_null == -1) {
        *result_null = -1;
        return;
    }
    sprintf(result, "Hello, %s!", user_name);
    *result_null = 0;
}
```

```sql
CREATE FUNCTION mydb.greet_user (user_name VARCHAR(100))
RETURNS VARCHAR(200)
LANGUAGE C
NO SQL
DETERMINISTIC
CALLED ON NULL INPUT
EXTERNAL NAME 'CS!greet_user!greet_user.c'
PARAMETER STYLE SQL;
```

VARCHAR parameters are passed as null-terminated C strings. Use `strlen()` for length, `sprintf()` or `strcpy()` for output.

## Procedure: Create a Multi-Parameter UDF

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"

void safe_divide(
    FLOAT         *numerator,
    FLOAT         *denominator,
    FLOAT         *result,
    int           *numerator_null,
    int           *denominator_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257])
{
    if (*numerator_null == -1 || *denominator_null == -1) {
        *result_null = -1;
        return;
    }
    if (*denominator == 0.0) {
        strcpy(sqlstate, "U0001");
        strcpy(error_msg, "Division by zero");
        return;
    }
    *result = *numerator / *denominator;
    *result_null = 0;
}
```

```sql
CREATE FUNCTION mydb.safe_divide (num FLOAT, den FLOAT)
RETURNS FLOAT
LANGUAGE C
NO SQL
DETERMINISTIC
CALLED ON NULL INPUT
EXTERNAL NAME 'CS!safe_divide!safe_divide.c'
PARAMETER STYLE SQL;
```

## Procedure: Update an Existing UDF

Use `REPLACE FUNCTION` for atomic updates. The database recompiles the source:

```sql
REPLACE FUNCTION mydb.double_value (input_val INTEGER)
RETURNS INTEGER
LANGUAGE C
NO SQL
DETERMINISTIC
CALLED ON NULL INPUT
EXTERNAL NAME 'CS!double_value!double_value.c'
PARAMETER STYLE SQL;
```

## Procedure: Discover and Verify UDFs

```sql
-- Check a specific function
SELECT FunctionName, ExternalName, LanguageName, CreateTimeStamp
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND FunctionName = 'double_value';

-- List all C UDFs in a database
SELECT FunctionName, ExternalName, CreateTimeStamp
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND LanguageName = 'C';

-- Show DDL for a function
SHOW FUNCTION mydb.double_value;
```

## External Name Format

```
CS!<c_function_name>!<source_file.c>    -- C Source (default: database compiles)
CO!<c_function_name>!<object_file.o>    -- C Object (.o relocatable; client-side)
SL!<library_base_name>                  -- Server Library: link -l<name> (see Linking an External Library)
SP!<package_path.so>                    -- Server Package (.so already distributed to all nodes)
SP!<package_path.so>!F!<entry_name>     -- Server Package with explicit entry point override
```

- `CS` uploads the `.c` file from the client. The database compiles it. Use this in almost all cases.
- `CO` uploads a pre-compiled `.o` relocatable object from the client. The database links it server-side.
- `SP` references a `.so` shared object that must already be distributed to all server nodes before the DDL runs. Distribute using `CALL SYSLIB.installsp(...)`, PCL, or FTP. Cannot be combined with other file clauses (`CS`, `CO`, etc.) but can be combined with `F!` to override the entry point. Max path length is 256 characters.
- The C function symbol must match the actual function name in the source exactly.

**CO! DDL example (pre-compiled .o object):**
```sql
CREATE FUNCTION mydb.udf_name (p1 INTEGER)
RETURNS INTEGER
SPECIFIC udf_name_int_impl
LANGUAGE C NO SQL PARAMETER STYLE SQL CALLED ON NULL INPUT
EXTERNAL NAME 'CO!udf_name!udf_src/udf_name.o';
```

### Linking an External Library

To link a UDF against a third-party library that is not part of the base toolchain (for
example `librdkafka` or `libcurl`), append a server library item and register its location:

- `SL!<name>` adds `-l<name>` to the in-database link line (`SL!rdkafka` links `-lrdkafka`).
- The library directory must be added to the `cufconfig` `USRLibraryPath` setting so the
  linker can find it (this also sets the runtime `rpath`).
- The library and its headers must be staged on every node (and inside the `udfsectsk`
  container for protected mode).

```sql
EXTERNAL NAME 'CS!kafka_produce!kafka_produce.c!SL!rdkafka';
```

See [Linking an External Library](./references/linking-external-libraries.md) for the full
mechanism (`SL` vs `SP`, `USRLibraryPath`, header paths, and node staging).

## Quick Type Mapping Reference

| SQL Type | C Type | Notes |
|----------|--------|-------|
| `INTEGER` | `INTEGER` (`int`) | 4 bytes |
| `BIGINT` | `BIGINT` (`long long`) | 8 bytes |
| `FLOAT` | `FLOAT` (`double`) | 8 bytes |
| `VARCHAR(n)` | `VARCHAR_LATIN` | Null-terminated string; for Unicode use `VARCHAR_UNICODE` |
| `CHAR(n)` | `CHARACTER_LATIN` | Fixed-width, space-padded; for Unicode use `CHARACTER_UNICODE` |
| `DECIMAL(5-9,m)` | `DECIMAL4` (`int`) | Scaled integer |
| `DATE` | `DATE` (`int`) | Encoded: `(year-1900)*10000 + month*100 + day` |

For multi-byte data add `CHARACTER SET UNICODE` to CHAR/VARCHAR parameters and the RETURNS clause:
```sql
CREATE FUNCTION mydb.to_upper (s VARCHAR(100) CHARACTER SET UNICODE)
RETURNS VARCHAR(100) CHARACTER SET UNICODE ...
```

See [SQL-to-C Type Mappings](./references/sql-to-c-type-mappings.md) for the complete table.

## Common Errors and Solutions

| Error | Cause | Fix |
|-------|-------|-----|
| `No CREATE FUNCTION privilege` | Missing privilege | `GRANT CREATE FUNCTION ON mydb TO username` |
| `Symbol not found` | C function name mismatch | C function name must match EXTERNAL NAME exactly |
| `Compilation error` | C source errors | Fix C code; database compiles with its own compiler |
| `UDF crashed` | Segfault in C code | Check NULL handling, buffer sizes, pointer arithmetic |
| `SPL1027: Response limit exceeded` | Result exceeds RETURNS size | Increase RETURNS VARCHAR length or truncate output |
| `FENCED` / `NOT FENCED` in DDL | DB2 syntax, invalid in Teradata | Remove these clauses entirely |
| `SQL SECURITY DEFINER` in C/Java DDL | Only valid for `LANGUAGE SQL` | Remove. Not valid for external routines. |

## Function Body Patterns

Every C scalar UDF body follows one of four patterns. `IsNull = -1`, `IsNotNull = 0`.

| Pattern | When | What to set |
|---------|------|-------------|
| **1: Success** | Normal result | `*result = value; *result_ind = IsNotNull;` |
| **2: Return NULL** | Input is null or null result is valid | `*result_ind = IsNull;` Do not write `*result`. |
| **3: Signal error** | Domain error (result discarded) | `strcpy(sqlstate, "38001"); strcpy(error_message, "msg");` |
| **4: Signal warning** | Partial result with caution | Write result and `*result_ind = IsNotNull`, then set `sqlstate = "01H01"` |

**sqlstate codes:**

| Range | Category | Result used? |
|-------|----------|-------------|
| `"00000"` | Success (default) | Yes. Never set explicitly. |
| `"01H01"` to `"01H99"` | User warning | Yes. Write result before setting. |
| `"22012"` | Division by zero | No |
| `"22004"` | NULL value not allowed | No |
| `"38001"`–`"38999"` | User-defined error | No |

**Forbidden inside any UDF body:** `exit()`, `abort()`, `printf()`, `fopen()`, static/global state variables, `malloc()` without `free()`. See [Best Practices](./references/best-practices.md).

See [Create Function Reference](./references/create-function-reference.md) for the full DDL clause order, SPECIFIC clause overload examples, and CHARACTER SET patterns.

## Security

- C UDFs run sandboxed in the UDF server process
- Always validate inputs. Check null indicators before accessing values.
- Validate string lengths before copying to prevent buffer overflows
- Use `sqlstate`/`error_msg` for error reporting. Never crash or abort.
- Creator receives EXECUTE automatically; use GRANT EXECUTE FUNCTION for others

## References


> **Access:** `skill_resource_read(action="read", skill="scalar-udf-c", path="references/FILENAME")` — do NOT call `list`.

- [PARAMETER STYLE SQL Deep Dive](./references/parameter-style-sql.md): null indicators, error reporting, trailing metadata
- [SQL-to-C Type Mappings](./references/sql-to-c-type-mappings.md): complete type mapping table, size macros, DATE encoding
- [Scalar UDF Examples](./references/scalar-udf-examples.md): complete worked examples for common data types
- [Best Practices](./references/best-practices.md): memory management, input validation, compilation, anti-patterns, forbidden operations
- [Create Function Reference](./references/create-function-reference.md): full DDL clause order, SPECIFIC overload management, CHARACTER SET, DROP SPECIFIC FUNCTION
- [Linking an External Library](./references/linking-external-libraries.md): attaching a third-party library (`SL`/`SP` EXTERNAL NAME items, `cufconfig` USRLibraryPath, header paths, node staging, protected-mode container)

## Templates

- [Scalar C UDF SQL Template](./assets/scalar-c-udf.md): registration DDL with all clauses
- [Scalar C UDF C Template](./assets/scalar-c-udf-source.md): C source boilerplate with null handling
