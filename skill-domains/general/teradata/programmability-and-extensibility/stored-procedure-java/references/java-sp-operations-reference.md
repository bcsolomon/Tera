# Java Stored Procedures: Operations Reference

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** Java Stored Procedures: Operations Reference

> Source: 541-0006374-B02 (Teradata Java Stored Procedure User Guide)

## Exception Handling and SQLSTATE

### Rules for SQLSTATE Mapping

| Exception Type | SQLSTATE |
|---|---|
| `SQLException` with state `38xxx` (not `38000`) | Uses the provided `38xxx` |
| `SQLException` with any other state | Maps to `39001` |
| Non-SQLException (RuntimeException, etc.) | Maps to `38000` |
| Teradata-specific (`TS000`) | Teradata error code via `getErrorCode()` |

### Throwing Errors

```java
// User-defined error with custom SQLSTATE
throw new SQLException("Invalid input: value must be positive", "38101");

// Catching Teradata-specific exceptions
try {
    int len = Tbl.getScale();
} catch (SQLException e) {
    if (e.getSQLState().equals("TS000")) {
        int teradataCode = e.getErrorCode();
        // Handle Teradata-specific error
    }
}
```

## Dictionary Views and Tables

### SQLJ Views (Current Database Scope)

| View | Content |
|---|---|
| `SQLJ.JARS` | Installed JAR files (JarName, Owner, CreatorName, ...) |
| `SQLJ.ROUTINE_JAR_USAGE` | Which procedures depend on which JARs |
| `SQLJ.JAR_JAR_USAGE` | JAR-to-JAR classpath dependencies (from ALTER_JAVA_PATH) |

### DBC Tables (System-Wide)

| Table | JXSP Content |
|---|---|
| `DBC.TVM` | Table/view metadata; JAR stored as TableKind='N' |
| `DBC.JARS` | Low-level JAR metadata (JarId, ClassVersion, JarRevision) |
| `DBC.JAR_JAR_USAGE` | System-level JAR dependency graph |
| `DBC.ROUTINE_JAR_USAGE` | System-level procedure-to-JAR mappings |
| `DBC.Dependency` | Cross-object dependency tracking including JARs |
| `DBC.DBase.JarLibRevision` | JAR version tracking on each AMP vproc |

```sql
-- List all installed JARs in current database
SELECT * FROM SQLJ.JARS;

-- Check procedure-to-JAR dependencies
SELECT * FROM SQLJ.ROUTINE_JAR_USAGE;

-- View JAR classpath dependencies
SELECT * FROM SQLJ.JAR_JAR_USAGE WHERE JarName = 'my_jar';

-- Verify JAR distribution
SELECT DISTINCT JarLibRevision
FROM DBC.DBase WHERE JarName = 'my_jar';
```

## Session Info API (com.teradata.fnc.DbsInfo)

```java
import com.teradata.fnc.DbsInfo;

DbsInfo info = new DbsInfo();
```

| Method | Return | Description |
|---|---|---|
| `getUserName()` | `String` | Session user name |
| `getUserId()` | `int` | Session user ID |
| `getUserAccount()` | `String` | Account string |
| `getSessionNo()` | `int` | Session number |
| `getStatementNo()` | `int` | Current statement number |
| `getRequestNo()` | `int` | Current request number |
| `getHost()` | `String` | Host ID / logon source |
| `getTraceString()` | `String` | Current session trace string |

### Static Trace Methods

```java
// Write trace objects (structured tracing)
DbsInfo.TraceWrite(TraceObj[] objarray);

// Write simple trace string
DbsInfo.traceWrite(String traceString);
```

## Tracing / Debugging

### TraceObj Class (com.teradata.fnc.TraceObj)

```java
import com.teradata.fnc.TraceObj;

// Constructor
TraceObj obj = new TraceObj(Object value, int typeId);
```

**Type ID Constants:**

| Constant | Value | Java Object Type |
|---|---|---|
| `BYTEINT_DBS` | 1 | `Byte` |
| `SMALLINT_DBS` | 2 | `Short` |
| `INTEGER_DBS` | 3 | `Integer` |
| `FLOAT_DBS` | 4 | `Double` |
| `DECIMAL1_DBS` | 5 | `BigDecimal` (1-2 digits) |
| `DECIMAL2_DBS` | 6 | `BigDecimal` (3-4 digits) |
| `DECIMAL4_DBS` | 7 | `BigDecimal` (5-9 digits) |
| `DECIMAL8_DBS` | 8 | `BigDecimal` (10-18 digits) |
| `DECIMAL16_DBS` | 33 | `BigDecimal` (19-38 digits) |
| `LATIN_CHAR_DBS` | 9 | `String` (fixed LATIN) |
| `LATIN_VARCHAR_DBS` | 10 | `String` (var LATIN) |
| `UNICODE_CHAR_DBS` | 11 | `String` (fixed UNICODE) |
| `UNICODE_VARCHAR_DBS` | 12 | `String` (var UNICODE) |
| `LATIN_LONGVARCHAR_DBS` | 13 | `String` (long var LATIN) |
| `UNICODE_LONGVARCHAR_DBS` | 14 | `String` (long var UNICODE) |
| `DATE_DBS` | 15 | `java.sql.Date` |
| `BYTE_DBS` | 16 | `byte[]` (fixed) |
| `VARBYTE_DBS` | 17 | `byte[]` (var) |
| `LONGVARBYTE_DBS` | 18 | `byte[]` (long) |
| `BLOB_DBS` | 19 | `com.teradata.fnc.Blob` |
| `LATIN_CLOB_DBS` | 20 | `com.teradata.fnc.Clob` |
| `UNICODE_CLOB_DBS` | 21 | `com.teradata.fnc.Clob` |
| `BIGINT_DBS` | 22 | `Long` |
| `DOUBLE_DBS` | 23 | `Double` |
| `BOOLEAN_DBS` | 24 | `Boolean` |
| `INTERVAL_DBS` | 25 | `String` |
| `TIME_DBS` | 26 | `java.sql.Time` |
| `TIMESTAMP_DBS` | 27 | `java.sql.Timestamp` |
| `TIMETZ_DBS` | 28 | `java.sql.Time` (with TZ) |
| `TIMESTAMPTZ_DBS` | 29 | `java.sql.Timestamp` (with TZ) |

**Accessor methods:** `getValue()`, `getTypeId()`

### Trace Table Setup

```sql
-- Create a global temporary trace table (one per session)
CREATE SET GLOBAL TEMPORARY TRACE TABLE tracetbl,
    FALLBACK, CHECKSUM = DEFAULT, LOG;

-- Enable trace for session
SET SESSION FUNCTION TRACE USING '' FOR TABLE tracetbl;

-- Execute Java SP
CALL my_java_sp();

-- Read trace output
SELECT * FROM tracetbl;
```

### Eclipse Remote Debugging

1. Configure `cufconfig` on DBS node:
   - Set `JavaBaseDebugPort` (e.g., 5005)
   - Set `JavaServerTaskCount` to number of concurrent debug sessions

2. JVM starts with `-Xdebug -Xrunjdwp:transport=dt_socket,server=y,suspend=y,address=<port>`

3. In Eclipse: Run > Debug Configurations > Remote Java Application, connect to DBS node on assigned port

## Teradata Java Extension Classes

### LOB Classes (com.teradata.fnc)

| Class | Purpose |
|---|---|
| `com.teradata.fnc.Blob` | BLOB value for TraceObj and XSP internals |
| `com.teradata.fnc.Clob` | CLOB value for TraceObj and XSP internals |
| `com.teradata.Blob` | Extended BLOB support |
| `com.teradata.Clob` | Extended CLOB support |
| `com.teradata.Timestamp` | Extended Timestamp support |
| `com.teradata.Time` | Extended Time support |

### Tbl Class (com.teradata.fnc.Tbl)

Used only in UDF/UDM context; not applicable for Java SPs. Calling `Tbl.getScale()` outside UDF context throws SQLSTATE `TS000`.

## Development Environment

### Required JARs for Compilation

Located in `ltdbs/bin` on the DBS node:

| JAR | Purpose |
|---|---|
| `javFnc.jar` | Teradata extension classes: DbsInfo, TraceObj, Tbl |
| `terajdbc4.jar` | Teradata JDBC driver (server edition) |

**Compile example:**

```bash
javac -classpath /path/to/javFnc.jar:/path/to/terajdbc4.jar MyClass.java
jar cf my_jar.jar com/company/MyClass.class
```

### Minimum Java Version

- Teradata DBS ships with a certified JRE
- 64-bit JVM only (32-bit not supported)
- JVM timezone is always **UTC** regardless of system timezone

## Security and Execution Environment

### Execution Model

- JXSPs run in `EXECUTE PROTECTED` mode inside a `udfsectsk` protected-mode server
- Each JXSP invocation runs **serially** (no concurrent Java threads per server)
- Each server JVM allocates **4MB of memory** (configurable)
- JARs are per-database, not global; use `ALTER_JAVA_PATH` only between JARs in the same database

### File I/O Requirements

Java SPs can read/write files on the DBS node filesystem, but require:

1. **OS-level permissions**: the database OS user account must have read/write on target directories
2. **`cufconfig` settings**: Java file I/O must be enabled in the UDF configuration
3. **`CREATE AUTHORIZATION`**: may be required for external resource access credentials

### Network Access

Java SPs can open outbound network connections (HTTP, sockets, etc.):

```java
import java.net.*;

URL url = new URL("http://webserver.example.com/api/data");
URLConnection conn = url.openConnection();
BufferedReader reader = new BufferedReader(
    new InputStreamReader(conn.getInputStream()));
```

### Character Set Support

- LATIN and UNICODE character sets supported for CHAR/VARCHAR parameters
- KANJI1 character set NOT supported (error 7854)
- String parameters automatically converted between SQL character set and Java's internal UTF-16

## Performance Notes

- Java SP overhead vs C is approximately **2.5x slower**
- Typically dwarfed by the SQL work done inside the procedure
- Java JVM uses an extra **4MB memory** per protected-mode server
- JARs are per-database, not global
- JXSP invocations are **serial** per server (no concurrent Java execution)
- Connection pooling: default connection is reused within session
- Close Statements/ResultSets promptly; each consumes dispatcher resources
- Batch operations via `PreparedStatement.addBatch()` and `executeBatch()` supported

## Common JXSP Error Codes

| Code | SQLSTATE | Meaning |
|---|---|---|
| 7686 | | Inline BLOB/CLOB result set read not supported |
| 7827 | | Java SQL Exception: invalid SQLSTATE format |
| 7840 | 38000 | Java execution error (generic) / uncaught Java exception |
| 7841 | | Java class initialization error |
| 7842 | | Java method signature mismatch |
| 7843 | | JVM startup failure |
| 7844 | | Java out of memory |
| 7845 | | JVM internal error |
| 7850 | TS000 | Tbl class method invalid for column type |
| 7854 | | KANJI1 character set not supported for JXSP |
| 7984 | | Java class not found / method not found / wrong jar |

### com.teradata.fnc SQLSTATEs

| SQLSTATE | Meaning |
|---|---|
| `TS000` | Tbl class usage error |
| `TS001` | DbsInfo initialization failure |
| `TS002` | TraceObj type mismatch |
| `38xxx` | User-defined SQLSTATE (38001–38999 usable) |
| `39001` | Remapped from non-38xxx SQLSTATEs |
| `38000` | Remapped from non-SQL exceptions |