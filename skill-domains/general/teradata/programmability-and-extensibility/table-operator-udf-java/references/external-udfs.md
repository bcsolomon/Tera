# External UDFs on Teradata (C/C++/Java)

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** External UDFs on Teradata (C/C++/Java)

## Overview

External UDFs allow writing function logic in C, C++, or Java when SQL expressions are insufficient. They provide access to system libraries, complex algorithms, and external resources.

## Supported Languages

| Language | Delivery | Use Case |
|----------|----------|----------|
| C | Source (`.c`) or object (`.o`) file — DB compiles internally | High performance, low-level operations |
| C++ | Source (`.cpp`) or object (`.o`) file — DB compiles internally | Object-oriented logic, STL algorithms |
| Java | `.jar` archive via `SQLJ.INSTALL_JAR` | Platform portability, rich library ecosystem |

## C/C++ Scalar UDF

### SQL Registration

```sql
REPLACE FUNCTION database_name.function_name (
    param1 INTEGER,
    param2 VARCHAR(100)
)
RETURNS VARCHAR(200)
SPECIFIC function_name_specific
LANGUAGE C
NO SQL
DETERMINISTIC
EXTERNAL NAME 'CS!function_name!udf_src/function_name.c'
PARAMETER STYLE SQL;
```

### External Name Format

The EXTERNAL NAME string is a structured multi-component literal. Each component uses a two-character
prefix, followed by a delimiter (conventionally `!`), and the component value:

| Prefix | Meaning | Example |
|--------|---------|---------|
| `CS` | C/C++ **source** file from **client** | `CS!name!udf_src/udf.c` |
| `CO` | C/C++ **object** file from **client** | `CO!name!udf_src/udf.o` |
| `SS` / `SO` | Source / object from **server** | `SS!name!server/path.c` |
| `CI` / `SI` | **Include** (header) file, client / server | `CI!hdrs!include/types.h` |
| `SL` | **Library** (link against, server-side) | `SL!libm` |
| `SP` | Pre-built **package** (`.so`) distributed to **all server nodes** | `SP!pkg_path.so` — install via `CALL SYSLIB.installsp` before DDL; cannot combine with other file clauses (but can combine with `F!`) |
| `F!` | Override C function **entry point** | `F!my_impl` |

- First character: `C` = file on **client**; `S` = file on **server**
- `name_on_server` (second field for file clauses) is the unique identifier stored in the database — it is **not** the C function symbol
- Function entry defaults to the SQL function name; use `F!entry_name` to override
- Multiple components are chained with the same delimiter: `'CI!types!include/types.h!CS!myfunc!src/myfunc.c!F!myfunc_impl'`

### C Implementation

```c
#include "sqltypes_td.h"

void function_name(
    INTEGER      *param1,
    VARCHAR_LATIN *param2,
    VARCHAR_LATIN *result,
    int          *param1_null,
    int          *param2_null,
    int          *result_null,
    char          sqlstate[6],
    SQL_TEXT      extname[129],
    SQL_TEXT      specific_name[129],
    SQL_TEXT      error_msg[257])
{
    /* Check for NULL inputs */
    if (*param1_null == -1 || *param2_null == -1) {
        *result_null = -1;
        return;
    }
    
    /* Implement logic */
    sprintf(result, "Result: %d - %s", *param1, param2);
    *result_null = 0;
    
    /* On error:
       strcpy(sqlstate, "U0001");
       strcpy(error_msg, "Description of error");
    */
}
```

### Parameter Style SQL Convention

For each declared parameter, the C function receives:
1. A pointer to the parameter value
2. A pointer to the null indicator (-1 = NULL, 0 = NOT NULL)

Additional trailing parameters:
- `sqlstate[6]` — Set to "U0xxx" to signal an error
- `extname[129]` — The external function name
- `specific_name[129]` — The SPECIFIC name
- `error_msg[257]` — Error message text (if sqlstate is set)

## Java Scalar UDF

> Both Java UDFs and Java SPs (JXSPs) use `SQLJ.INSTALL_JAR` to install the JAR.
> The EXTERNAL NAME format is `jar_name:ClassName.method` — **not** a `JF!` prefix.

### SQL Registration

```sql
-- Step 1: Install the JAR
CALL SQLJ.INSTALL_JAR('CJ!/path/to/my_udf.jar', 'MY_UDF_JAR', 0);

-- Step 2: Register the function
REPLACE FUNCTION database_name.java_function (
    param1 INTEGER,
    param2 VARCHAR(100)
)
RETURNS VARCHAR(200)
LANGUAGE JAVA
NO SQL
DETERMINISTIC
EXTERNAL NAME 'MY_UDF_JAR:com.company.udf.MyFunction.execute'
PARAMETER STYLE JAVA;
```

### External Name Format

```
jar_alias:FullyQualifiedClassName.methodName
```

- `jar_alias` — the name used in `SQLJ.INSTALL_JAR` (case-sensitive)
- Class and method names are case-sensitive
- Method must be `public static` and return the mapped Java type

### Java Implementation

```java
package com.company.udf;

import java.sql.*;

public class MyFunction {
    public static String execute(Integer param1, String param2) throws SQLException {
        if (param2 == null) {
            return null;  // NULL handling
        }
        return "Result: " + param1 + " - " + param2;
    }
}
```

### Java Null Handling

- Java UDFs use `PARAMETER STYLE JAVA`
- Primitive types (int, double) cannot be null — use wrapper classes (Integer, Double)
- To use nullable wrappers, specify Java types explicitly in EXTERNAL NAME:
  `EXTERNAL NAME 'MY_JAR:MyClass.myMethod(java.lang.Integer, java.lang.String)'`
- String and object types can be null naturally
- Return null to produce a SQL NULL result

### Java UDF Type Mappings

Same as Java SP mappings — see `teradata-stored-procedures/references/java-stored-procedures.md` for the complete SQL-to-Java type table. Key difference: UDF methods **return** the mapped type (not void), and all parameters are IN-only (no array wrappers).

### Java UDF JAR Installation

Java UDFs install JARs via `SQLJ.INSTALL_JAR`:

```sql
CALL SQLJ.INSTALL_JAR('CJ!/path/to/my_udf.jar', 'MY_UDF_JAR', 0);
-- Replace an existing JAR:
CALL SQLJ.REPLACE_JAR('CJ!/path/to/my_udf_v2.jar', 'MY_UDF_JAR');
-- Manage classpath for JAR dependencies:
CALL SQLJ.ALTER_JAVA_PATH('MY_UDF_JAR', 'DEP_JAR');
```

### Java UDF vs Java SP: Key Differences

| Aspect | Java UDF | Java SP (JXSP) |
|---|---|---|
| JAR install | `SQLJ.INSTALL_JAR` | `SQLJ.INSTALL_JAR` |
| Classpath | `SQLJ.ALTER_JAVA_PATH` | `SQLJ.ALTER_JAVA_PATH` |
| EXTERNAL NAME | `'jar_alias:ClassName.method'` | `'jar_alias:ClassName.method'` |
| Method return | Returns mapped Java type | `void` (uses OUT arrays) |
| SQL access | `NO SQL` only | `NO SQL` through `MODIFIES SQL DATA` |
| JDBC connection | Not available | `jdbc:default:connection` |
| Result sets | Via RETURNS clause | Via `DYNAMIC RESULT SETS` |
| Execution | Per-row (scalar) | Per-CALL |

## Installation Workflow

### Step 1: Register the Function

```sql
-- C/C++: REPLACE FUNCTION supplies source path; DB compiles internally
REPLACE FUNCTION mydb.my_function(param1 INTEGER)
RETURNS INTEGER
LANGUAGE C
NO SQL
DETERMINISTIC
EXTERNAL NAME 'CS!my_function!udf_src/my_function.c'
PARAMETER STYLE SQL;

-- Java: install JAR first, then register
CALL SQLJ.INSTALL_JAR('CJ!/path/to/my_udf.jar', 'MY_UDF_JAR', 0);
REPLACE FUNCTION mydb.java_function(param1 INTEGER)
RETURNS INTEGER
LANGUAGE JAVA
NO SQL
DETERMINISTIC
EXTERNAL NAME 'MY_UDF_JAR:com.company.udf.MyFunction.execute'
PARAMETER STYLE JAVA;
```

### Step 2: Grant Access

```sql
GRANT EXECUTE FUNCTION ON mydb.my_function TO app_role;
```

## Replacing/Updating External UDFs

```sql
-- C/C++: just re-run REPLACE FUNCTION with the new source path
REPLACE FUNCTION mydb.my_function(param1 INTEGER)
RETURNS INTEGER
LANGUAGE C
NO SQL
DETERMINISTIC
EXTERNAL NAME 'CS!my_function!udf_src/my_function_v2.c'
PARAMETER STYLE SQL;

-- Java: replace the JAR, then re-register
CALL SQLJ.REPLACE_JAR('CJ!/path/to/my_udf_v2.jar', 'MY_UDF_JAR');
REPLACE FUNCTION mydb.java_function(param1 INTEGER) ...;
```

## Table Functions (External)

External table UDFs return multiple rows and columns:

```sql
REPLACE FUNCTION mydb.parse_csv (
    csv_data CLOB
)
RETURNS TABLE (
    col1 VARCHAR(100),
    col2 INTEGER,
    col3 DATE
)
LANGUAGE C
NO SQL
DETERMINISTIC
EXTERNAL NAME 'CS!parse_csv!udf_src/parse_csv.c'
PARAMETER STYLE SQL;
```

Table UDFs in C use a contract-function approach with multiple call modes:
- **Mode 0**: Define output columns (called once)
- **Mode 1**: Process input and produce rows (called repeatedly)
- **Mode 2**: Cleanup (called once)

## Security Considerations

- External UDFs run in a sandboxed UDF server process
- File system access is restricted
- Network access may be restricted by site policy
- Always validate inputs to prevent buffer overflows
- Use `sqlstate` to report errors rather than crashing

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `Symbol not found` | C function name mismatch | SQL function name must match C symbol; or add `!F!entry_name` |
| `UDF crashed` | Segfault in C code | Check NULL handling, buffer sizes |
| `Java ClassNotFound` | Wrong class path in EXTERNAL NAME | Verify fully qualified class name matches JAR |
| `Compilation failed` | Source error or missing header | Check server compile log in `DBC.EventLog` |
| `Permission denied` | Privilege missing | Need `CREATE FUNCTION` on target database |

Use `DBC.FunctionsV` to verify registration:

```sql
SELECT FunctionName, SpecificName, ExternalName, LanguageCode
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb';
```
