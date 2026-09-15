---
name: stored-procedure-java
description: 'Install, call, and remove Java External Stored Procedures (JXSP) on Teradata. Use when writing a stored procedure in Java that executes SQL via the in-engine JDBC connection, returns dynamic result sets, or requires Java libraries. Covers Java method signatures (IN=value, OUT/INOUT=array), JAR lifecycle (INSTALL_JAR, REPLACE_JAR, REMOVE_JAR, ALTER_JAVA_PATH), REPLACE PROCEDURE DDL, DYNAMIC RESULT SETS, in-engine JDBC (jdbc:default:connection), exception/SQLSTATE mapping, DbsInfo/TraceObj APIs, Eclipse remote debugging, error codes 7840-7984, and DROP PROCEDURE. Based on Teradata SQL External Routine Programming v20.00.'
when_to_use: 'Use when the user mentions JXSP, Java stored procedure, CREATE PROCEDURE LANGUAGE JAVA, jdbc:default:connection, DYNAMIC RESULT SETS, Java SP error codes, or wants to write Java procedural code that runs inside Teradata.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Java External Stored Procedure (JXSP)

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
> Use a SQL stored procedure (`stored-procedures`) as an alternative.

A JXSP is a Java static method registered as a `PROCEDURE`. It supports IN, OUT, and INOUT
parameters, can execute SQL via the in-engine JDBC connection, and returns dynamic result sets.

> **Not this skill:** For SQL stored procedures, see **stored-procedures**. For C/C++ XSPs,
> see **stored-procedure-c**. For Java scalar UDFs, see **scalar-udf-java**.

## When to Use

- Writing procedural Java logic invoked via `CALL`
- Executing SQL from Java using the in-engine JDBC connection
- Returning multiple dynamic result sets to a caller
- Using Java libraries or complex algorithms inside Teradata
- Replacing or updating an existing JXSP without dropping it first

## Core Concepts

### Java Method Signature

| Parameter mode | Java type | Notes |
|----------------|-----------|-------|
| `IN` | Primitive (simple mapping) or boxed/class type (object mapping) | Read-only value, passed directly |
| `OUT` or `INOUT` | Single-element array (`int[]`, `Integer[]`, `String[]`) | Method writes back via `param[0] = value` |

The method must be `public static void`. It must declare `throws SQLException` if it executes
SQL or signals errors. Simple mapping (SQL type to a Java primitive) is the default; object
mapping (to a Java class such as `Integer` or `String`) applies when no primitive fits or when
the EXTERNAL NAME clause lists the Java parameter classes explicitly (needed to represent NULLs).

### In-Engine JDBC Connection

```java
Connection conn = DriverManager.getConnection("jdbc:default:connection");
```

No hostname, port, or credentials are needed. The JXSP runs inside the Teradata engine.
The connection shares the caller's transaction context.

## Procedure: Write the Java Source

```java
import java.sql.*;

public class MyProc {
    // IN param: normal type; OUT/INOUT param: single-element array
    public static void myMethod(int param1, String[] param2)
        throws SQLException
    {
        param2[0] = "Result: " + param1;
    }

    // JXSP that executes SQL (IN custId -> plain int, OUT custName -> array)
    public static void customerLookup(int custId, String[] custName)
        throws SQLException
    {
        Connection conn = DriverManager.getConnection("jdbc:default:connection");
        PreparedStatement stmt = conn.prepareStatement(
            "SELECT cust_name FROM customer_table WHERE cust_id = ?");
        stmt.setInt(1, custId);
        ResultSet rs = stmt.executeQuery();
        if (rs.next()) custName[0] = rs.getString(1);
        rs.close(); stmt.close();
    }
}
```

Compile and package: `javac MyProc.java && jar cf MyProc.jar MyProc.class`

## Procedure: Install JAR and Register DDL

```sql
-- Step 1: install the JAR (CJ! = client JAR)
CALL SQLJ.INSTALL_JAR('CJ!jar_path/MyProc.jar', 'my_proc_jar', 0);

-- Optional: set classpath if JAR depends on other JARs
CALL SQLJ.ALTER_JAVA_PATH('my_proc_jar', '(*.*,utility_jar)');

-- Step 2: register the procedure
REPLACE PROCEDURE mydb.my_proc (
    IN  param1 INTEGER,
    OUT param2 VARCHAR(100)
)
LANGUAGE JAVA
MODIFIES SQL DATA              -- or NO SQL / READS SQL DATA / CONTAINS SQL
PARAMETER STYLE JAVA
DYNAMIC RESULT SETS 0          -- set > 0 when returning result sets
EXTERNAL NAME 'my_proc_jar:MyProc.myMethod';

-- Step 3: grant access
GRANT EXECUTE PROCEDURE ON mydb.my_proc TO app_role;
```

**EXTERNAL NAME format:** `'<JAR_ALIAS>:<ClassName>.<methodName>'`
When the method is overloaded, list the Java parameter classes (use object/array mapping
forms). The method returns `void`, so there is no `returns` clause:
`'my_jar:MyClass.myMethod(java.lang.Integer[])'`

## Procedure: Return Dynamic Result Sets

The method signature appends **one `ResultSet[]` output parameter per result set**, after the
IN/INOUT/OUT parameters. Inside the method, execute the statement, then assign
`stmt.getResultSet()` into the array element. **Do not close the `Statement`** that produced a
returned result set. A null or uninitialized array element returns no result set.

```java
import java.sql.*;

public class jExamples {
    /* DDL: ... DYNAMIC RESULT SETS 2 PARAMETER STYLE JAVA
            EXTERNAL NAME 'my_proc_jar:jExamples.usrCmd' */
    public static void usrCmd(String command,
                              ResultSet[] rs1,
                              ResultSet[] rs2) throws SQLException {
        Connection conn = DriverManager.getConnection("jdbc:default:connection");
        Statement stmt = conn.createStatement(
            ResultSet.TYPE_SCROLL_INSENSITIVE, ResultSet.CONCUR_READ_ONLY);

        if (stmt.execute(command)) {
            rs1[0] = stmt.getResultSet();                         // return first result set
        }
        if (stmt.getMoreResults(Statement.KEEP_CURRENT_RESULT)) {
            rs2[0] = stmt.getResultSet();                         // return second result set
        }
        /* Do NOT close stmt: the returned result sets need it. */
    }
}
```

DDL: declare the count with `DYNAMIC RESULT SETS n` (1 to 15) and a SQL-access clause other
than `NO SQL`. Restrictions: a result-set statement cannot be part of a multistatement request,
inline LOB reads from a result set are unsupported, and a result set created by a called stored
procedure cannot be forwarded to this procedure's caller (it can only be consumed).

## Procedure: Call and Verify

```sql
CALL mydb.my_proc(10, result_var);

HELP PROCEDURE mydb.my_proc;

SELECT ProcedureName, ExternalName, LanguageName
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND ProcedureName = 'my_proc';
```

## Procedure: Update JAR

```sql
-- Replace in-place (does not drop the procedure)
CALL SQLJ.REPLACE_JAR('CJ!jar_path/MyProc_v2.jar', 'my_proc_jar');
```

Running JXSPs continue using the old version until complete; new invocations use the new JAR.

## Procedure: Uninstall

```sql
-- 1. Check for dependent procedures
SELECT ProcedureName, ExternalName FROM DBC.FunctionsV
WHERE ExternalName LIKE '%my_proc_jar%';

-- 2. Drop the procedure
DROP PROCEDURE mydb.my_proc;

-- 3. Remove the JAR (only if no other procedures reference it)
DATABASE mydb;
CALL SQLJ.REMOVE_JAR('my_proc_jar', 0);
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| Procedure already exists | Use `REPLACE PROCEDURE`. No prior DROP is needed. |
| JAR already installed | Use `SQLJ.REPLACE_JAR` to update; `INSTALL_JAR` errors if JAR exists |
| JAR depends on other JARs | `CALL SQLJ.ALTER_JAVA_PATH('my_jar', '(*.*,dep_jar)')` |
| INOUT in Java | Use single-element array: `int[] param` → `param[0] = newValue` |
| Throw user-defined error | `throw new SQLException("message", "38101")`. Use the `38xxx` SQLSTATE range. |
| Dynamic result sets | Append one `ResultSet[]` output param per set; assign `stmt.getResultSet()`; do not close the Statement; declare `DYNAMIC RESULT SETS n` |
| Consume a called SP's result set | Use `CallableStatement` (`con.prepareCall("CALL sp(?)")`), `execute()`, then `getResultSet()`; cannot re-return it to your own caller |
| Teradata-managed platform (VantageCloud Lake or Enterprise) | External routines are supported, but direct `EXTERNAL NAME` install may be blocked. On Lake, install/list/uninstall with the `tdextroutine` CLI. On Enterprise, install on Compute Engine nodes or via a service request (not the EDW node). Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`. |
| Error codes 7840–7984 | See [Java SP Operations Reference](./references/java-sp-operations-reference.md) |

## References


> **Access:** `skill_resource_read(action="read", skill="stored-procedure-java", path="references/FILENAME")` — do NOT call `list`.

- [Java Stored Procedures](./references/java-stored-procedures.md): JAR lifecycle (INSTALL/REPLACE/REMOVE/ALTER_JAVA_PATH/REDISTRIBUTE), locspec formats, SQL-to-Java type mappings, JDBC default connection, dynamic result sets, SQLJ views, DBC JAR tables
- [Java SP Operations Reference](./references/java-sp-operations-reference.md): exception/SQLSTATE mapping, DbsInfo/TraceObj APIs, Eclipse remote debug setup (JavaBaseDebugPort), security model, error codes 7840-7984, dictionary views

## Templates

- [Java SP Template](./assets/templates/java-sp.md)
