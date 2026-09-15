# Java Stored Procedures (JXSP): Complete Reference

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** Java Stored Procedures (JXSP): Complete Reference

> Source: 541-0006374-B02 (Teradata Java Stored Procedure User Guide)

## JAR Lifecycle Management

### Install a JAR

```sql
CALL SQLJ.INSTALL_JAR(
    locspec  IN VARCHAR(1000),  -- location of JAR file
    jar      IN VARCHAR(30),    -- JAR identifier name
    deploy   IN INTEGER         -- 0 = no deployment descriptor
);
```

**locspec formats:**
- `CJ!path/to/file.jar`: JAR on the **client** machine (client transfers to server)
- `SJ!path/to/file.jar`: JAR on the **server** filesystem
- `cj!file:~/classes/myjar.jar`: Client with URL syntax

The delimiter can be any single character (`!`, `:`, `?`). Location designator is case-insensitive; JAR path is case-sensitive. File name must end with `.jar`.

**locspec examples:**

```
'SJ:classes/accounts.jar'
'SJ:/usr/java_project/myproject.jar'
'sj!C:\java_source\ver1\accounts.jar'
'cj!file:~/classes/bookreports.jar'
'cj?mylocalJava.jar'
```

**jar name:** Any valid Teradata object identifier. Can use double quotes inside single quotes: `'"Jar1"'`.

**Privileges required:**
- `EXECUTE` on `SQLJ.INSTALL_JAR`
- `CREATE EXTERNAL PROCEDURE` on current database

**Storage:** JARs stored in `jarlib` directory on each DBS node (configurable via `cufconfig`). Also stored in an internal function (pseudo) table for backup. JARs are versioned; old versions are retained until executing XSPs complete.

### Replace a JAR

```sql
CALL SQLJ.REPLACE_JAR(
    locspec   IN VARCHAR(1000),
    jar       IN VARCHAR(30)
);
```

- JAR must already exist (unlike REPLACE PROCEDURE)
- Replacement JAR must contain class files for every class referenced by existing SQL routines
- New classes can be added; unreferenced classes can be removed
- Running XSPs continue using old version until complete; new invocations use new version
- Existing JXSP method signatures cannot be changed unless the JXSP is first dropped

### Remove a JAR

```sql
CALL SQLJ.REMOVE_JAR(
    jar       IN VARCHAR(30),
    undeploy  IN INTEGER      -- 0 = no undeployment descriptor
);
```

Fails if any stored procedures or other JARs depend on this JAR. Check dependencies first:

```sql
SELECT * FROM SQLJ.ROUTINE_JAR_USAGE WHERE JarName = 'my_jar_name';
SELECT * FROM SQLJ.JAR_JAR_USAGE WHERE JarName = 'my_jar_name';
```

All JXSPs defined against the JAR must be dropped first. All `ALTER_JAVA_PATH` references must be removed first.

**Required privilege:** `DROP PROCEDURE` on current database.

### Set Java Classpath (ALTER_JAVA_PATH)

```sql
CALL SQLJ.ALTER_JAVA_PATH(
    jar       IN VARCHAR(30),
    path      IN VARCHAR(1000)
);
```

Establishes classpath associations between JARs. Both JARs must reside in the **same database**.

**Path format:**

```sql
-- Include all classes from MathPkg JAR
CALL SQLJ.ALTER_JAVA_PATH('my_jar', '(*.*,MathPkg)');

-- Multiple dependencies
CALL SQLJ.ALTER_JAVA_PATH('my_jar', '(matrix.*,mymath_jar) (investment.stock,business_jar)');

-- Remove all classpath references
CALL SQLJ.ALTER_JAVA_PATH('my_jar', '');
-- or
CALL SQLJ.ALTER_JAVA_PATH('my_jar', '()');
```

**Rules:**
- Only `*` wildcard is supported for packages (not specific class selection)
- Does NOT influence `System.getProperty("java.class.path")`
- Uses DBS Java Loader for class lookup at runtime
- Circular dependencies are detected and rejected

### Redistribute JAR (After System Restore/Migrate)

```sql
CALL SQLJ.REDISTRIBUTE_JAR(
    jar       IN VARCHAR(30)
);
```

Retrieves JAR from internal table, writes to primary node, redistributes to all nodes. Use during copy, migrate, or system restore. After archive/restore, use `jxspconv.pl` under `ltdbs/bin` to recompile all JXSP and redistribute all JARs.

## CREATE PROCEDURE Syntax

```sql
[CREATE | REPLACE] PROCEDURE database_name.procedure_name (
    [IN | OUT | INOUT] param1 data_type,
    [IN | OUT | INOUT] param2 data_type
)
LANGUAGE JAVA
MODIFIES SQL DATA                    -- or NO SQL, CONTAINS SQL, READS SQL DATA
PARAMETER STYLE JAVA
[DYNAMIC RESULT SETS n]              -- 0-15 result sets returned to caller
EXTERNAL NAME 'jar_name:com.company.package.ClassName.methodName';
```

### EXTERNAL NAME Format

```
'jar_name:fully.qualified.ClassName.methodName'
'jar_name:fully.qualified.ClassName.methodName(java.lang.Double[])'  -- explicit parameter types
```

- `jar_name` matches the name used in `INSTALL_JAR`
- Class and method names are **case-sensitive**
- Method must be `public static void`
- No class constructor is called before invoking the method
- Package name included if class is in a package
- Optional parameter list overrides default type mapping (for nullable primitives)

**Validation commands:**

```bash
jar -tf file.jar                              # list JAR contents
javap -classpath file.jar full.classname      # list methods/signatures
```

### SQL Data Access Levels

| Clause | Meaning | Default Connection |
|---|---|---|
| `NO SQL` | No SQL statements allowed | NOT set up (exception if attempted) |
| `CONTAINS SQL` | Control statements only (e.g., CALL) | Available |
| `READS SQL DATA` | SELECT only | Available |
| `MODIFIES SQL DATA` | INSERT/UPDATE/DELETE allowed | Available |

Parent SP data access restrictions cascade to child SP calls.

### Dynamic Result Sets

- Range: 0–15 result sets per procedure
- Warning issued if method returns more than specified count
- ResultSet parameters must be the **last** parameters in the method signature
- JXSP only supports "Return to Client" result set mode
- Must use default connection to return result sets

## Java Method Signature Conventions

```java
public class ClassName {
    public static void methodName(
        // IN parameters: normal Java types
        int param1,

        // OUT parameters: single-element arrays
        String[] param2,

        // INOUT parameters: single-element arrays
        java.math.BigDecimal[] param3
    ) throws SQLException
    {
        // Access OUT/INOUT: param2[0] = "value";
        // Access INOUT input: param3[0]
    }
}
```

**Rules:**
- Method must be `public static void`
- IN parameters: use plain Java types
- OUT and INOUT parameters: use single-element arrays (`Type[]`)
- Method must declare `throws SQLException`
- NULL handling: wrapper types (Integer, Double) for nullable primitives

## SQL-to-Java Type Mappings

### Simple Mapping (PARAMETER STYLE JAVA)

| SQL Type | Java IN Type | Java OUT/INOUT Type | Notes |
|---|---|---|---|
| `BYTEINT` | `byte` | `byte[]` | |
| `SMALLINT` | `short` | `short[]` | |
| `INTEGER` | `int` | `int[]` | |
| `BIGINT` | `long` | `long[]` | |
| `REAL` / `FLOAT` | `double` | `double[]` | |
| `DOUBLE PRECISION` | `double` | `double[]` | |
| `DECIMAL(m,n)` m≤18 | `java.math.BigDecimal` | `java.math.BigDecimal[]` | |
| `DECIMAL(m,n)` 18<m≤38 | `java.math.BigDecimal` | `java.math.BigDecimal[]` | |
| `NUMERIC` | `java.math.BigDecimal` | `java.math.BigDecimal[]` | |
| `CHAR(n)` / `VARCHAR(n)` | `String` | `String[]` | |
| `LONG VARCHAR` | `String` | `String[]` | |
| `DATE` | `java.sql.Date` | `java.sql.Date[]` | |
| `TIME [WITH TIME ZONE]` | `java.sql.Time` | `java.sql.Time[]` | |
| `TIMESTAMP [WITH TIME ZONE]` | `java.sql.Timestamp` | `java.sql.Timestamp[]` | |
| `BYTE(n)` / `VARBYTE(n)` | `byte[]` | `byte[][]` | |
| `BLOB` | `java.sql.Blob` | `java.sql.Blob[]` | Locator semantics |
| `CLOB` | `java.sql.Clob` | `java.sql.Clob[]` | Locator semantics |
| `INTERVAL` (all 13 types) | `String` | `String[]` | |
| `ResultSet` (output only) | N/A | `java.sql.ResultSet[]` | Dynamic result sets |

### Nullable Primitive Types (Object Mapping)

Primitive types (`int`, `short`, `byte`, `long`, `double`) cannot represent SQL NULL (a conflict between null and 0). To support NULL, use wrapper classes and specify the Java type in the EXTERNAL NAME:

```sql
-- Override to use nullable Double instead of primitive double
REPLACE PROCEDURE mydb.nullable_proc (INOUT val FLOAT)
LANGUAGE JAVA
MODIFIES SQL DATA
PARAMETER STYLE JAVA
EXTERNAL NAME 'my_jar:MyClass.myMethod(java.lang.Double[])';
```

```java
public static void myMethod(Double[] val) throws SQLException {
    if (val[0] != null) {
        val[0] = val[0].doubleValue() + 1;
    }
    // val[0] remains null if input was NULL
}
```

| Primitive | Nullable Wrapper |
|---|---|
| `byte` | `java.lang.Byte` |
| `short` | `java.lang.Short` |
| `int` | `java.lang.Integer` |
| `long` | `java.lang.Long` |
| `double` | `java.lang.Double` |

### Supported and Unsupported Parameter Types

Beyond the primitive and class mappings above, these SQL types are also supported as Java SP
parameters and return types:

| SQL type | Java mapping |
|---|---|
| Distinct UDT | Java type of the source predefined type (simple, or boxed when EXTERNAL NAME lists the class) |
| Structured UDT | `java.sql.Struct` (`com.teradata.fnc.Struct`); ST_Geometry attributes cannot be passed |
| `PERIOD` (all) | `java.sql.Struct` |
| `ARRAY` / `VARRAY` | `java.sql.Array` (`com.teradata.fnc.Array`); 1-D and N-D supported |
| `JSON` | `java.sql.Blob`, or `String`/`byte[]` for sizes up to 64K |
| `DATASET` (Avro) | `java.sql.Blob`, or `byte[]` up to 64K |
| `DATASET` (CSV) | `java.sql.Clob`, or `String` up to 64K |

The only SQL types **not supported** as Java SP/UDF parameters or return types are the GRAPHIC
character-set variants and VARIANT_TYPE:

- `CHARACTER CHARACTER SET GRAPHIC`
- `VARCHAR CHARACTER SET GRAPHIC`
- `LONG VARCHAR CHARACTER SET GRAPHIC`
- `VARIANT_TYPE`

CAST these to a supported type before passing. Note also that an ARRAY parameter cannot have a
base type that is a nested structured UDT.

### LOB Parameters

BLOB and CLOB use locator semantics per the JDBC spec. Explicit `AS LOCATOR` is not required/permitted for Java SPs; it is implicit.

## JDBC Within Stored Procedures

### Default Connection

Java SPs use the default internal connection; no host, user, or password is needed:

```java
Connection con = DriverManager.getConnection("jdbc:default:connection");
```

**Key rules:**
- Uses the **same session** as the CALL statement
- No logon/password required
- Only available when SQL data access is NOT `NO SQL`; attempting it with `NO SQL` throws an exception
- Uses Teradata JDBC driver (server version shipped with DBS)
- SQL messages routed from `udfsectsk` protected mode server through internal DBS gateway to dispatcher
- **Do NOT close** the default connection; it belongs to the session
- Always `close()` Statements and ResultSets to release dispatcher resources

### Statement Types

```java
// Simple statement
Statement stmt = con.createStatement();
ResultSet rs = stmt.executeQuery("SELECT * FROM employees");

// Parameterized statement
PreparedStatement pstmt = con.prepareStatement(
    "INSERT INTO orders(id, amount) VALUES (?, ?)");
pstmt.setInt(1, orderId);
pstmt.setBigDecimal(2, amount);
pstmt.executeUpdate();
pstmt.close();
```

### Connecting to External Databases

Java SPs can also open standard JDBC connections to other Teradata systems or external databases:

```java
// Connect to a different Teradata system
Connection extCon = DriverManager.getConnection(
    "jdbc:teradata://other-system/DATABASE=mydb", "user", "password");
```

### SELECT Example

```java
public static void getEmployee(int empId, String[] name, java.math.BigDecimal[] salary)
    throws SQLException
{
    Connection con = DriverManager.getConnection("jdbc:default:connection");
    PreparedStatement stmt = con.prepareStatement(
        "SELECT employee_name, salary FROM employees WHERE emp_id = ?");
    stmt.setInt(1, empId);
    ResultSet rs = stmt.executeQuery();
    if (rs.next()) {
        name[0] = rs.getString(1);
        salary[0] = rs.getBigDecimal(2);
    }
    rs.close();
    stmt.close();
}
```

### INSERT/UPDATE Example

```java
public static void updatePrice(int itemId, java.math.BigDecimal newPrice)
    throws SQLException
{
    Connection con = DriverManager.getConnection("jdbc:default:connection");
    PreparedStatement stmt = con.prepareStatement(
        "UPDATE inventory SET price = ? WHERE item_id = ?");
    stmt.setBigDecimal(1, newPrice);
    stmt.setInt(2, itemId);
    stmt.executeUpdate();
    stmt.close();
}
```

### LOB (BLOB/CLOB) Example

```java
public static void writeBlob(int rowId, String filename) throws SQLException {
    try {
        Connection con = DriverManager.getConnection("jdbc:default:connection");
        PreparedStatement stmt = con.prepareStatement(
            "UPDATE webtab SET b = ? WHERE id = " + rowId);
        File file = new File(filename);
        FileInputStream data = new FileInputStream(file);
        stmt.setBinaryStream(1, data, data.available());
        stmt.execute();
        stmt.close();
    } catch (Exception e) {
        throw new SQLException(e.getMessage(), "38100");
    }
}
```

**LOB note:** Inline BLOB/CLOB reading from a result set is NOT supported (error 7686). Use locator-based access instead.

## Dynamic Result Sets

### Single Result Set

```sql
REPLACE PROCEDURE mydb.get_orders (IN customer_id INTEGER)
LANGUAGE JAVA
READS SQL DATA
PARAMETER STYLE JAVA
DYNAMIC RESULT SETS 1
EXTERNAL NAME 'my_jar:com.company.Orders.getOrders';
```

```java
public static void getOrders(int customerId, java.sql.ResultSet[] rs0)
    throws SQLException
{
    Connection con = DriverManager.getConnection("jdbc:default:connection");
    PreparedStatement stmt = con.prepareStatement(
        "SELECT order_id, order_date, amount FROM orders WHERE cust_id = ?");
    stmt.setInt(1, customerId);
    rs0[0] = stmt.executeQuery();
    // Do NOT close stmt or rs; the client reads from rs after method returns
}
```

### Multiple Result Sets with Positioning

```java
public static void multiResults(String command,
        int pos1, int pos2,
        ResultSet[] rs1, ResultSet[] rs2) throws Exception
{
    Connection con = DriverManager.getConnection("jdbc:default:connection");
    Statement stmt = con.createStatement(
        ResultSet.TYPE_SCROLL_INSENSITIVE,
        ResultSet.CONCUR_READ_ONLY);
    if (stmt.execute(command)) {
        rs1[0] = stmt.getResultSet();
        rs1[0].absolute(pos1);       // position for client
    }
    if (stmt.getMoreResults(Statement.KEEP_CURRENT_RESULT)) {
        rs2[0] = stmt.getResultSet();
        rs2[0].absolute(pos2);
    }
}
```

### Result Set Rules

- ResultSet parameters must be the **last** parameters in the method signature
- Count must match `DYNAMIC RESULT SETS n` in CREATE PROCEDURE
- JXSP only supports "Return to Client" mode
- Position of result set when method ends determines where client starts reading
- Each statement is independently positionable
- All Java requests use scrolling enabled
- Supported result-returning statements: SELECT, HELP TABLE/VIEW/MACRO, SHOW TABLE/VIEW/MACRO, COMMENT
- Auto-generated keys from single inserts returned as result set (not batch inserts)
```


> **See also:** [java-sp-operations-reference.md](java-sp-operations-reference.md): exception handling, SQLSTATE mapping, dictionary views, session info API, tracing/debugging, extension classes, security, performance, and error codes.
