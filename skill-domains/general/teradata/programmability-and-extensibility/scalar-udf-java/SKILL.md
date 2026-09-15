---
name: scalar-udf-java
description: 'Create, register, and remove Java scalar User-Defined Functions on Teradata. Use when implementing per-row transformations, calculations, or string operations in Java that execute inside the Teradata engine. Covers Java method requirements (public static, boxed types for nullable params), JAR lifecycle (SQLJ.INSTALL_JAR / REPLACE_JAR / REMOVE_JAR), PARAMETER STYLE JAVA, EXTERNAL NAME format (JAR_ALIAS:ClassName.method), NULL handling with boxed types, and full lifecycle DDL. Based on Teradata SQL External Routine Programming v20.00.'
when_to_use: 'Use when the user mentions Java scalar UDF, Java UDF, LANGUAGE JAVA scalar function, boxed types for UDF, Java external function, or wants to implement a per-row scalar function in Java on Teradata.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Java Scalar UDF

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

A Java scalar UDF is a `public static` method in a Java class registered with Teradata via
`SQLJ.INSTALL_JAR` + `CREATE FUNCTION ... LANGUAGE JAVA`. The method receives boxed Java types
(`Integer`, `Double`, `String`) so that `null` can represent SQL NULLs.

> **Not this skill:** For C/C++ scalar UDFs, see **scalar-udf-c**. For Java aggregate UDFs,
> see **aggregate-udf-java**. For Java table functions, see **table-function-udf-java**.
> For Java stored procedures (JXSP), see **stored-procedure-java**.

## When to Use

- Implementing business logic, string manipulation, or math functions in Java
- Using Java standard libraries (regex, date/time, encoding, cryptography) inside Teradata queries
- Portability across teams that prefer Java over C
- Situations where the Java ecosystem (Maven dependencies, unit testing) is preferred

## SQL-to-Java Type Mapping

Use boxed types so a SQL NULL can arrive as `null`. Primitives are valid only for parameters that
are never NULL.

| SQL Type | Java Type (nullable) | Notes |
|----------|----------------------|-------|
| `INTEGER`, `BYTEINT`, `SMALLINT` | `Integer` | `Byte`/`Short` also accepted |
| `BIGINT` | `Long` | |
| `FLOAT`, `REAL`, `DOUBLE PRECISION` | `Double` | |
| `DECIMAL(p,s)` / `NUMBER` | `java.math.BigDecimal` | Preserves scale |
| `VARCHAR`, `CHAR`, `CLOB` | `String` | LOB read fully into memory |
| `BYTE`, `VARBYTE`, `BLOB` | `byte[]` | |
| `DATE` | `java.sql.Date` | |
| `TIME`, `TIMESTAMP` | `java.sql.Time`, `java.sql.Timestamp` | |

## Java Method Requirements

```java
package com.company.udf;

public class StringUtils {
    /**
     * Reverses a string, returning null if input is null.
     */
    public static String reverseStr(String input) {
        if (input == null) return null;         // null check is mandatory
        return new StringBuilder(input).reverse().toString();
    }

    /**
     * Integer factorial. Handles null and negative values.
     */
    public static Integer factorial(Integer n) {
        if (n == null || n < 0) return null;
        int result = 1;
        for (int i = 2; i <= n; i++) result *= i;
        return result;
    }
}
```

**Rules:**
- Method must be `public static`.
- Prefer **boxed types** (`Integer`, `Long`, `Double`, `Float`, `String`, `byte[]`) for
  parameters and the return type. A boxed type is required wherever a SQL NULL must be
  representable (it arrives as `null`), and when the `EXTERNAL NAME` lists parameter classes
  explicitly. Primitives (`int`, `long`, `double`) are valid only for parameters that are never
  NULL; they cannot represent a SQL NULL and will raise an error if one is passed.
- Return `null` to signal a SQL NULL result.
- Do not catch `Throwable` broadly. Let checked exceptions propagate as `SQLException`.

## Procedure: Build the JAR

```bash
javac -cp .:/path/to/tdgssconfig.jar:/path/to/terajdbc4.jar \
      com/company/udf/StringUtils.java

jar cf string_utils.jar com/company/udf/StringUtils.class
```

## Procedure: Install the JAR

```sql
-- Grant once per developer role (DBA performs this)
GRANT EXECUTE PROCEDURE ON SQLJ.INSTALL_JAR TO udf_developer_role;
GRANT EXECUTE PROCEDURE ON SQLJ.REMOVE_JAR  TO udf_developer_role;

-- Install from client-side path (CJ = Client Java)
DATABASE mydb;
CALL SQLJ.INSTALL_JAR('CJ!/path/to/string_utils.jar', 'STRING_UTILS_JAR', 0);

-- If this JAR depends on other JARs (optional)
CALL SQLJ.ALTER_JAVA_PATH('STRING_UTILS_JAR', 'COMMON_LIB_JAR');
```

## Procedure: Register the Function DDL

```sql
REPLACE FUNCTION mydb.reverse_str (input VARCHAR(1000))
RETURNS VARCHAR(1000)
SPECIFIC reverse_str_impl
LANGUAGE JAVA
NO SQL
CALLED ON NULL INPUT
DETERMINISTIC
PARAMETER STYLE JAVA
EXTERNAL NAME 'STRING_UTILS_JAR:com.company.udf.StringUtils.reverseStr';

GRANT EXECUTE FUNCTION ON mydb.reverse_str TO app_role;
```

### EXTERNAL NAME Format

```
'<JAR_ALIAS>:<FullyQualifiedClassName>.<methodName>'
```

For overloaded methods, include the full Java type signature:
```
'STRING_UTILS_JAR:com.company.udf.MathUtils.add(java.lang.Integer, java.lang.Integer) returns java.lang.Integer'
```

### PARAMETER STYLE JAVA

With `PARAMETER STYLE JAVA`, Teradata uses boxed Java types to represent NULLs natively:
- `null` Java reference = SQL NULL
- No separate null indicator parameters needed
- Always `CALLED ON NULL INPUT`. The method must check for `null` itself.

### CALLED ON NULL INPUT vs RETURNS NULL ON NULL INPUT

| Clause | Behavior | Use when |
|--------|----------|---------|
| `CALLED ON NULL INPUT` | Java method is called even when args are null; check `== null` in code | Custom null logic needed |
| `RETURNS NULL ON NULL INPUT` | Teradata returns NULL without calling the method | Pure function. Returns null when any input is null. |

## Procedure: Test and Verify

```sql
SELECT mydb.reverse_str('Hello World');  -- 'dlroW olleH'
SELECT mydb.factorial(5);                -- 120
SELECT mydb.reverse_str(NULL);           -- NULL

SELECT FunctionName, ExternalName, LanguageName
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND FunctionName = 'reverse_str';
```

## Procedure: Uninstall

```sql
-- Check for dependencies first
SELECT * FROM DBC.FunctionXRefsV
WHERE UDFDatabase = 'mydb' AND UDFName = 'reverse_str';

-- Drop one overload
DROP SPECIFIC FUNCTION mydb.reverse_str_impl;
-- OR drop all overloads
DROP FUNCTION mydb.reverse_str;

-- Remove the JAR after all functions referencing it are dropped
CALL SQLJ.REMOVE_JAR('STRING_UTILS_JAR', 0);
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| `NullPointerException` in Java | Always check parameters for `null` before dereferencing |
| Overloaded Java method | Add full type signature in EXTERNAL NAME: `ClassName.method(java.lang.Integer)` |
| JAR already installed | `CALL SQLJ.REMOVE_JAR('ALIAS', 0)` then reinstall; or use `REPLACE_JAR` |
| `ClassNotFoundException` | Verify fully qualified class name; check JAR contents with `jar tf` |
| Primitive type parameter | Replace with boxed type. Use `Integer` instead of `int`, `Double` instead of `double`. |
| Dependencies between JARs | Use `SQLJ.ALTER_JAVA_PATH` to set classpath before CREATE FUNCTION |
| Teradata-managed platform (VantageCloud Lake or Enterprise) | External routines are supported, but direct `EXTERNAL NAME` install may be blocked. On Lake, install/list/uninstall with the `tdextroutine` CLI. On Enterprise, install on Compute Engine nodes or via a service request (not the EDW node). Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`. |
| `FENCED` / `SQL SECURITY DEFINER` in DDL | Not valid for Java UDFs. Remove these clauses. |

## Common Errors and Solutions

| Error | Cause | Fix |
|-------|-------|-----|
| `SQLJ has no privilege` on `INSTALL_JAR` | Developer role lacks the SQLJ grant | `GRANT EXECUTE PROCEDURE ON SQLJ.INSTALL_JAR TO <role>` (DBA action) |
| `The specified JAR name already exists` | JAR alias already installed | `CALL SQLJ.REPLACE_JAR(...)`, or `REMOVE_JAR` then `INSTALL_JAR` |
| `ClassNotFoundException` | Fully qualified class name in EXTERNAL NAME is wrong, or class not in the JAR | Verify the FQCN and confirm with `jar tf string_utils.jar` |
| `NoSuchMethodException` | Method name, case, or parameter signature does not match | Match `Class.method` exactly; for overloads add the full type signature in EXTERNAL NAME |
| `The UDF/XSP/UDM ... is not a valid Java method` | Method is not `public static`, or returns `void` | Make the method `public static` with a non-void boxed return type |
| `NullPointerException` at runtime | A primitive parameter received a SQL NULL, or code dereferenced a null arg | Use boxed types (`Integer`, `Double`) and null-check every parameter |
| `Data type mismatch` on CREATE FUNCTION | SQL parameter/return types do not map to the Java signature | Align SQL types with the Java boxed types (see [External UDFs](./references/external-udfs.md) mapping table) |
| `FENCED` / `SQL SECURITY DEFINER` rejected | DB2-style clauses invalid for Java UDFs | Remove them; Java UDFs run in the JVM protected server |

## References


> **Access:** `skill_resource_read(action="read", skill="scalar-udf-java", path="references/FILENAME")` — do NOT call `list`.

- [External UDFs](./references/external-udfs.md): full Java UDF development guide, type mappings, Java vs JXSP comparison table, privilege matrix
