# Client API and BI Tool Query Band Integration

> Source: 541-0006939 (Teradata Reserved Query Band Names), 541-0007069 (Using Query Banding in Teradata Vantage)

## JDBC Query Band Setting

### Basic JDBC Query Band via SQL Statement

The simplest approach is executing the SET QUERY_BAND SQL statement directly on a JDBC connection:

```java
Connection conn = DriverManager.getConnection(
    "jdbc:teradata://myserver/DATABASE=mydb", "user", "pass");

Statement stmt = conn.createStatement();
stmt.execute("SET QUERY_BAND = 'ApplicationName=MyApp;ClientUser=jsmith;" +
    "Group=Finance;Version=2.1.0;' FOR SESSION;");
stmt.close();

// All subsequent queries on this connection carry the session query band
```

### Parameterized Query Band with PreparedStatement

The `?` parameter marker is supported for the entire query band string in transaction-level bands:

```java
String url = "jdbc:teradata://myserver";
Connection con = DriverManager.getConnection(url, "user", "pass");

String ssetqbpm = "SET QUERY_BAND = ? FOR TRANSACTION;";
String txnqb = "ClientUser=jsmith;JobID=RPT_001;Importance=OnlineTactical;";

PreparedStatement pstmt = con.prepareStatement(ssetqbpm);
pstmt.setString(1, txnqb);
pstmt.execute();

// Execute the actual query
Statement stmt = con.createStatement();
ResultSet rs = stmt.executeQuery("SELECT * FROM SalesData");
// ... process results

con.commit(); // Transaction query band discarded at commit
```

### JDBC TRUST_ONLY for Proxy User Security

When using Trusted Sessions with JDBC, the `TRUSTED_SQL` connection parameter marks all requests as trusted. Use the `{fn teradata_untrusted}` escape function to downgrade user-supplied SQL:

```java
// Create DataSource with TRUSTED_SQL=ON
DataSource ds = new TeradataDataSource();
ds.setUrl("jdbc:teradata://myserver/TRUSTED_SQL=ON");
Connection con = ds.getConnection("estore_svc", "password");

// Trusted request — sets proxy user (application-generated SQL)
Statement trustedStmt = con.createStatement();
trustedStmt.execute(
    "SET QUERY_BAND = 'ProxyUser=DSmith;ProxyRole=WomensWear;' FOR SESSION;");

// Untrusted request — user-supplied SQL cannot change proxy user
String userSQL = getUserInput();
String untrustedSQL = "{fn teradata_untrusted}" + userSQL;
Statement untrustedStmt = con.createStatement();
untrustedStmt.execute(untrustedSQL);
```

The DBA must first enable TRUST_ONLY for the trusted user:

```sql
GRANT CONNECT THROUGH estore_svc WITH TRUST_ONLY;
```

### JDBC Connection Pool Pattern

Set the session query band when borrowing a connection and clear it on return:

```java
// On checkout
conn.createStatement().execute(
    "SET QUERY_BAND = 'ApplicationName=WebApp;ClientUser=" +
    currentUser + ";Group=" + userGroup + ";' FOR SESSION;");

// ... application logic ...

// On return
conn.createStatement().execute("SET QUERY_BAND = NONE FOR SESSION;");
pool.returnConnection(conn);
```

## Teradata .NET Data Provider

### TdQueryBand Class

The Teradata .NET Data Provider provides the `TdQueryBand` class for setting query bands. When this class is used, the request is automatically marked as trusted (important for Trusted Sessions):

```csharp
using Teradata.Client.Provider;

string connStr = "Data Source=myserver;User ID=user;Password=pass;";
using (TdConnection conn = new TdConnection(connStr))
{
    conn.Open();

    // Set session query band using TdQueryBand
    TdQueryBand qb = conn.QueryBand;
    qb.Set("ApplicationName", "DotNetApp");
    qb.Set("ClientUser", "jsmith");
    qb.Set("Group", "Finance");
    qb.Set("Version", "3.0.1");
    qb.Apply(TdQueryBandScope.Session);

    // Execute queries — query band is active
    using (TdCommand cmd = conn.CreateCommand())
    {
        cmd.CommandText = "SELECT * FROM SalesData";
        using (TdDataReader reader = cmd.ExecuteReader())
        {
            // ... process results
        }
    }

    // Clear session query band
    qb.Clear(TdQueryBandScope.Session);
}
```

You can also execute `SET QUERY_BAND` directly via `TdCommand.ExecuteNonQuery()`, but when using Trusted Sessions the `TdQueryBand` class must be used to ensure the request is marked as trusted.

## ODBC / CLIv2

ODBC applications set query bands by executing the SET QUERY_BAND statement via `SQLExecDirect`:

```c
SQLHSTMT hstmt;
SQLAllocHandle(SQL_HANDLE_STMT, hdbc, &hstmt);
SQLExecDirect(hstmt,
    (SQLCHAR*)"SET QUERY_BAND = "
    "'ApplicationName=ODBCApp;ClientUser=jsmith;Group=Finance;' "
    "FOR SESSION;", SQL_NTS);
SQLFreeHandle(SQL_HANDLE_STMT, hstmt);
```

For Trusted Sessions with CLIv2, the DBCAREA `trustedRequest` field is set to `Y` (trusted) or `N` (not trusted) to control whether proxy user changes are permitted.

## BTEQ

### Session Query Band in BTEQ Scripts

```sql
.LOGON myserver/acctuser
SET QUERY_BAND='ClientUser=MG445;ApplicationName=CRM;JobID=CRM123;' FOR SESSION;

INSERT INTO Payroll_Test (EmpNo, Name, DeptNo)
  VALUES (1592, 'Mary Jones', 900);
UPDATE DeptCount SET EmpCount = EmpCount + 1;
SELECT * FROM DeptCount;

.LOGOFF
```

### Transaction Query Band in Multi-Statement Requests

BTEQ supports transaction-level query bands as the first statement in a multi-statement request:

```sql
SET QUERY_BAND='ClientUser=MG445;JobID=Payroll;'
  FOR TRANSACTION
;INSERT INTO Payroll_Test (EmpNo, Name, DeptNo)
  VALUES (1592, 'Mary Jones', 900);

SET QUERY_BAND='ClientUser=MG445;JobID=Dept;'
  FOR TRANSACTION
;UPDATE DeptCount SET EmpCount = EmpCount + 1
;SELECT * FROM DeptCount;
```

Use `SELECT GetQueryBand();` or `SELECT GetQueryBandValue(0, 'ClientUser');` in BTEQ to verify the active query band and extract specific values.

## Profile-Based Query Band Enforcement

### CREATE/MODIFY PROFILE with Query Band

Profile query bands are set at logon and enforced by the DBA. They cannot be removed by the user.

```sql
-- Set a profile query band with DEFAULT (user can override same-named keys)
CREATE PROFILE load_profile AS
  QUERY_BAND = 'TVSTEMPERATURE=WARM;' (DEFAULT);
MODIFY USER loaduser AS PROFILE = load_profile;

-- Set a profile query band with NOT DEFAULT (user cannot override same-named keys)
CREATE PROFILE strict_profile AS
  QUERY_BAND = 'TVSTEMPERATURE=Cold;' (NOT DEFAULT);
MODIFY USER userabc AS PROFILE = strict_profile;
```

When NOT DEFAULT is used, matching name-value pairs in SET QUERY_BAND are silently discarded with warning 9987. The profile value takes precedence.

### Ignore Query Band Values (TD 16.0+)

Prevents specific name-value pairs from being set by users:

```sql
-- Prevent users from setting TVSTemperature=HOT (WARM/COLD still allowed)
CREATE PROFILE sales_profile AS
  QUERY_BAND = 'GROUP=WestCoast;',
  IGNORE QUERY_BAND VALUES = 'TVSTemperature=HOT;';

-- Prevent any value for Importance
CREATE PROFILE avg_user_profile AS
  IGNORE QUERY_BAND VALUES = 'Importance=;';

-- Mixed: some names overridable, others locked
CREATE PROFILE mix_profile AS
  QUERY_BAND = 'A=1;B=2;C=3;D=4;' (DEFAULT),
  IGNORE QUERY_BAND VALUES = 'B=;D=;';
-- A and C can be overridden; B and D are locked
```

## ThreadLocalContext Pattern (Java)

Teradata provides a `ThreadLocalContext` utility class for managing query band context across multi-threaded Java applications. It uses `java.lang.ThreadLocal` to maintain context per thread of execution.

### Console Application Initialization

```java
public static void main(String[] args) {
    // At first point of application entry, initialize ThreadLocalContext
    ThreadLocalContext.setClientUser(System.getProperty("USER"));
    ThreadLocalContext.setGroup("TZA_BROKER");
    ThreadLocalContext.setProxyUser("TZA_PROXY_USER");
    ThreadLocalContext.setProxyRole("TZA_PROXY_ROLE");
    ThreadLocalContext.setApplicationName("MyApp");
    ThreadLocalContext.setVersion("2.0.0");
    ThreadLocalContext.setSource(MyApp.class.toString());
    ThreadLocalContext.setAction("main");
    // ...
}
```

### Web Application Servlet Filter

```java
public class ApplicationContextFilter implements Filter {
    public void doFilter(ServletRequest request, ServletResponse response,
            FilterChain chain) throws IOException, ServletException {
        // Capture HTTP context into ThreadLocal
        ThreadLocalContext.setSource(
            ((HttpServletRequest) request).getRequestURI());
        ThreadLocalContext.setAction(
            ((HttpServletRequest) request).getMethod());
        // StartTime is set automatically
        chain.doFilter(request, response);
    }
}
```

### Applying ThreadLocalContext to Queries

```java
String query = "SELECT * FROM ZipCodeRiskFactors " +
    "WHERE ? BETWEEN StartZipRange AND EndZipRange";

PreparedStatement stmt = connection.prepareStatement(
    ThreadLocalContext.getQueryBandForTransaction() + query);
stmt.setInt(1, Integer.parseInt(zipCode));
stmt.execute();
stmt.close();
```

The `getQueryBandForTransaction()` method builds a complete `SET QUERY_BAND = '...' FOR TRANSACTION;` statement from all the context values set on the current thread, including an auto-generated `QueryIssueTime` in UTC format.

### Key ThreadLocalContext Methods

Setter methods for each reserved name: `setClientUser()`, `setGroup()`, `setProxyUser()`, `setProxyRole()`, `setApplicationName()`, `setVersion()`, `setSource()`, `setAction()`, `setImportance()`, `setJobID()`.

Output methods: `getQueryBandForSession()` and `getQueryBandForTransaction()` build complete SET QUERY_BAND statements. Call `removeUserVars()` to clear all context for the current thread.

## MicroStrategy Integration

MicroStrategy can be configured to set Teradata query bands using VLDB settings at the DB Instance level. MicroStrategy provides substitution variables that map to reserved query band names.

### Variable Mapping

| MicroStrategy Variable | Meaning | Reserved Query Band |
|---|---|---|
| `!u` | MicroStrategy user name | `ClientUser` |
| `!p` | Project name | `Source` |
| `!o` | Report name | `Action` |
| `!j` | Intelligence Server job ID | `JobID` |
| `!i` | Report priority | `Importance` |
| `!d` | Date from Intelligence Server | `StartTime` (combine with `!t`) |
| `!t` | Timestamp from Intelligence Server | `StartTime` (combine with `!d`) |
| `!z` | Project ID (16-digit hex) | (custom) |
| `!r` | Report ID (16-digit hex) | (custom) |
| `!s` | User Session ID (16-digit hex) | (custom) |

### Configuration Steps

1. **Separate metadata DB Instance** — If using Teradata for the metadata repository, configure a separate DB Instance with a dedicated login (e.g., `MSTR_MD`) so metadata requests are isolated.

2. **Set the Report Pre-SQL Statement** (VLDB setting at DB Instance level):

```
SET QUERY_BAND = 'ApplicationName=MicroStrategy;Version=9.0;ClientUser=!u;Source=!p;Action=!o;StartTime=!dT!t;JobID=!j;Importance=!i;' FOR SESSION;
```

3. **Set the Report Post-SQL Statement** (VLDB setting at DB Instance level):

```
SET QUERY_BAND = NONE FOR SESSION;
```

A single report request may generate multiple SQL statements. By including `Source` (project) and `Action` (report), TASM can treat them as a single logical report for workload management. The Pre-SQL sets the band before execution and Post-SQL clears it afterward.

## IBM Cognos Integration

IBM Cognos 8.4+ enables administrators to associate Teradata SET QUERY_BAND statements with data source connections using XML command blocks that fire at connection lifecycle events (Open Connection, Open Session, Close Session, Close Connection). Query bands should be set in session-level command blocks so they re-execute as different user sessions share database connections.

### Simple Open Connection Command Block

```xml
<commandBlock>
  <commands>
    <sqlCommand>
      <sql>SET QUERY_BAND = 'ApplicationName=HR Reporting;' FOR SESSION</sql>
    </sqlCommand>
  </commands>
</commandBlock>
```

### Close Connection Command Block

```xml
<commandBlock>
  <commands>
    <sqlCommand>
      <sql>SET QUERY_BAND = NONE FOR SESSION</sql>
    </sqlCommand>
  </commands>
</commandBlock>
```

### Parameterized Command Block with LDAP User

Cognos can resolve session parameters from the authentication provider (e.g., LDAP). The `#...#` syntax denotes expression evaluation:

```xml
<commandBlock>
  <commands>
    <sqlCommand>
      <sql>#
'SET QUERY_BAND=''ClientUser=' + $account.personalInfo.email
  + ';'' FOR SESSION'
      #</sql>
    </sqlCommand>
  </commands>
</commandBlock>
```

### Priority-Based Command Block for Prompt Data Sources

Use separate data sources with different query band priorities — for example, higher priority for prompt queries:

```xml
<commandBlock>
  <commands>
    <sqlCommand>
      <sql>#
'SET QUERY_BAND=''Importance=OnlineTactical;'' FOR SESSION'
      #</sql>
    </sqlCommand>
  </commands>
</commandBlock>
```

Configure command blocks through the Cognos connection wizard when creating or modifying a Teradata (ODBC) data source. Connections inherit command blocks from the parent data source; use **Reset to parent value** to restore inherited settings.

## DBS Control: MaxSetQueryBandSize

The maximum length of a SET QUERY_BAND statement is controlled by DBS Control.

| Release | Default | Configurable Values |
|---|---|---|
| Pre-16.0 | 2048 characters | Fixed |
| 16.0+ | 3072 characters | 2048, 3072, or 4096 |

The setting is **DBS Control field 106 (MaxSetQueryBandSize)** in the General Field group. When increasing the limit, verify that all third-party tools in the environment support the larger query band length.

Note: The HELP SESSION `QueryBand` field (which returns concatenated transaction + session bands) may be truncated when MaxSetQueryBandSize is set above 2048 and the session export width is greater than one. A warning code is returned if truncation occurs. The individual query band fields (Transaction QueryBand, Session QueryBand, Profile QueryBand) always contain the complete value.

## VOLATILE Option for Performance

Use the VOLATILE keyword (TD 14.10+) to skip writing the query band to the session table, reducing overhead for high-frequency updates:

```sql
SET QUERY_BAND = 'ClientUser=jsmith;ApplicationName=FastApp;' VOLATILE FOR SESSION;
```

VOLATILE query bands are still logged in DBQL but are NOT restored after a system reset. Alternatively, set `DBSControl Internal value 411 (QBVolatility)` to TRUE system-wide. Do not mix VOLATILE and non-VOLATILE SET QUERY_BAND statements in the same session — on system reset, only the last non-VOLATILE value is restored.

## Best Practices for Client Integration

- Set query bands in connection initialization code, not ad hoc in business logic
- Use `ThreadLocalContext` or equivalent pattern to propagate context through application layers
- Always clear session query bands when returning connections to a pool (`SET QUERY_BAND = NONE FOR SESSION`)
- For BI tools, configure Pre-SQL and Post-SQL at the data source or DB Instance level
- Use profile query bands (NOT DEFAULT) for values that must not be overridden by applications
- Use Ignore Query Band Values to prevent misuse of priority or system names
- Use VOLATILE for high-frequency query band updates where session recovery is not needed
- Keep total query band length under the configured MaxSetQueryBandSize to avoid truncation
- Use `TRUSTED_SQL=ON` (JDBC) or `TdQueryBand` class (.NET) when implementing Trusted Sessions
- Never store sensitive data (passwords, tokens) in query bands — they are logged in DBQL
