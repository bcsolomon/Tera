# Trusted Sessions and Workload Management Integration

## Trusted Sessions Overview

Trusted Sessions enable a middle-tier application to assert the identity and roles of an application end user for use in access rights checking and auditing. This is essential for connection-pooled environments where all connections share a single database logon.

**High-level flow:**
1. Middle-tier application creates a connection pool authenticating as a trusted user (e.g., `EStore`).
2. Application end user authenticates to the middle-tier application.
3. Application issues `SET QUERY_BAND` with `PROXYUSER` to assert the end user's identity.
4. Teradata validates the proxy user has CONNECT THROUGH privileges.
5. Session attributes switch to those of the proxy user for access checking and auditing.

## Proxy User Types

### Application Proxy Users (External Users)

Application proxy users do NOT have a Teradata Database logon. They are defined entirely through GRANT CONNECT THROUGH.

```sql
-- Create roles for access control
CREATE ROLE WomensWear;
CREATE ROLE MensWear;
CREATE ROLE Jewelry;
CREATE ROLE Shoes;

-- Create profiles for session limits
CREATE PROFILE Level1Profile AS
  SPOOL = 1e9, TEMPORARY = 5e8;
CREATE PROFILE Level2Profile AS
  SPOOL = 2e9, TEMPORARY = 1e9;

-- Grant connect through privileges
GRANT CONNECT THROUGH EStore TO DSmith, KLong
  WITH ROLE WomensWear, ChildrensWear WITH PROFILE Level2Profile;
GRANT CONNECT THROUGH EStore TO GCollins
  WITH ROLE MensWear WITH PROFILE Level1Profile;
GRANT CONNECT THROUGH EStore TO DBeard
  WITH ROLE Jewelry WITH PROFILE Level1Profile;
GRANT CONNECT THROUGH EStore TO RJones
  WITH ROLE Shoes WITH PROFILE Level1Profile;
```

Grant CTCONTROL to an application security administrator:

```sql
GRANT CTCONTROL ON EStore TO EstoreAdmin;
-- EstoreAdmin must also have WITH ADMIN OPTION on any role in GRANT CONNECT THROUGH
```

**Application proxy user session impact (TD 15.10+):**
- Access rights based on active roles of the proxy user
- All roles in CONNECT THROUGH privilege are active by default
- CURRENT_USER returns the proxy user name
- CURRENT_ROLE returns the proxy role name
- HELP SESSION returns proxy user and proxy role
- Proxy user logged in Access Log and DBQL
- MonitorSession PM/API returns ProxyUser
- Application proxy users have NO permanent space (actions requiring permanent space will fail)
- Session attributes set from proxy user's profile (if assigned); otherwise from trusted user
- Automatic rights for created objects are NOT granted to application proxy users
- WLM qualification uses proxy user's profile name and account (user name still the trusted user)

### Permanent Proxy Users (Database Users)

Permanent proxy users are existing Teradata Database users that can be asserted through a trusted session.

```sql
-- Users must already exist in the database
-- Grant connect through with WITHOUT ROLE to use the user's own roles
GRANT CONNECT THROUGH EStore TO PERMANENT JJohnson, KLuther, DButler WITHOUT ROLE;

-- Or with specific roles
GRANT CONNECT THROUGH EStore TO PERMANENT JJohnson WITH ROLE AnalystRole;
```

**Permanent proxy user session impact (TD 15.10+):**
- WITH ROLE: access rights based on the specified roles only
- WITHOUT ROLE: access rights based on all roles granted to the user plus direct grants
- Session attributes set from the permanent user's profile and user definition
- Permanent space charged to the permanent proxy user
- Spool/temp space utilization charged to the proxy user
- WLM qualification uses the permanent proxy user's user, profile, and account names
- Automatic rights for created objects ARE granted to permanent proxy users

### Proxy User Groups

For applications with hundreds/thousands of users, create proxy users representing groups instead of individual users:

```sql
-- Proxy users represent departments
GRANT CONNECT THROUGH EStore TO DeptMgr
    WITH ROLE WWearRole, MWearRole WITH PROFILE Level2Profile;
GRANT CONNECT THROUGH EStore TO WomensWear
    WITH ROLE WWearRole WITH PROFILE Level1Profile;
GRANT CONNECT THROUGH EStore TO MensWear
    WITH ROLE MWearRole WITH PROFILE Level1Profile;
GRANT CONNECT THROUGH EStore TO Jewelry
    WITH ROLE JewelryRole WITH PROFILE Level1Profile;
GRANT CONNECT THROUGH EStore TO Shoes
    WITH ROLE ShoesRole WITH PROFILE Level1Profile;
```

The application maps end users to group proxy users and sets ClientUser for tracking:

```sql
SET QUERY_BAND = 'PROXYUSER=Shoes;CLIENTUSER=RJones;' FOR SESSION;
-- ClientUser can be extracted via GetQueryBandValue for individual tracking
```

## Asserting and Removing Proxy Users

### Setting a Proxy User

```sql
-- Set proxy user only (all granted roles become active)
SET QUERY_BAND = 'PROXYUSER=DSmith;' FOR SESSION;

-- Set proxy user with a specific role (only that role is active)
SET QUERY_BAND = 'PROXYUSER=DSmith;PROXYROLE=WomensWear;' FOR SESSION;

-- ProxyRole must be one of the roles defined in the CONNECT THROUGH privilege
```

### Removing a Proxy User

```sql
-- Option 1: Set a different proxy user
SET QUERY_BAND = 'PROXYUSER=GCollins;' FOR SESSION;

-- Option 2: Set query band without PROXYUSER
SET QUERY_BAND = 'ApplicationName=EStore;' FOR SESSION;

-- Option 3: Clear the query band entirely
SET QUERY_BAND = NONE FOR SESSION;

-- Option 4: If set via transaction band, proxy is removed at transaction end
BT;
SET QUERY_BAND = 'PROXYUSER=DSmith;' FOR TRANSACTION;
-- ... queries run as DSmith ...
ET;
-- Proxy user is now removed
```

## Row-Level Security with Trusted Sessions

When using Trusted Sessions, use `CURRENT_USER` instead of `USER` in security views. CURRENT_USER returns the proxy user name when a proxy is set, or the logged-on user when no proxy is set.

```sql
-- Security mapping table
CREATE TABLE SecurityMapping (
    UserName VARCHAR(128),
    Dept INTEGER
);

-- Row-level security view using CURRENT_USER (works with proxy users)
CREATE VIEW DepartmentView AS
  SELECT * FROM Employee
  WHERE DeptNumber IN
    (SELECT Dept FROM SecurityMapping WHERE UserName = CURRENT_USER);

-- Note: USER and CURRENT_USER are equivalent when there is no proxy user
```

## TRUST_ONLY Option

Prevents end users from injecting SET QUERY_BAND statements to change the proxy user when using application white-board/SQL editor features.

```sql
-- Enable TRUST_ONLY for the trusted user
GRANT CONNECT THROUGH EStore WITH TRUST_ONLY;
```

When TRUST_ONLY is enabled, all SET QUERY_BAND statements that set or remove a proxy user must come from a "trusted" request or they are rejected.

### Client API Trusted Request Mechanisms

**CLIv2**: Set the `trustedRequest` field in the DBCAREA data structure to `Y` (trusted) or `N` (not trusted).

**JDBC**: Create a DataSource with `TRUSTED_SQL=ON` connection parameter. All requests are trusted by default. Downgrade individual requests with:

```java
// Prepend escape function to untrust user-input SQL
String untrustedSQL = "{fn teradata_untrusted}" + userInputSQL;
```

**Teradata .NET Data Provider**: Use the `TdQueryband` class to set query bands. Requests through this class are automatically marked as trusted.

## Trusted Sessions and Secure Zones

The trusted user, permanent proxy user, and proxy role in a GRANT CONNECT THROUGH statement cannot belong to a Teradata Secure Zone. Application proxy users CAN access objects within a zone if both zone access grant and discretionary access control privileges are granted to the proxy role.

## Trusted Sessions and X Views (TD 16.0+)

When a session is set to a proxy user, DBC X Views return rows based on the proxy user's access rights:
- Permanent proxy user WITHOUT ROLE: rights of the permanent user plus active roles
- Application proxy user or permanent proxy user WITH ROLE: rights of active roles only

## Workload Management Integration

### Filter Rules with Query Bands

TASM filter rules can use query band name-value pairs as classification criteria. Query band names and values are NOT case sensitive for WLM matching.

```sql
-- Example: Filter rule blocks DDL for Marketing group between 8am-5pm
-- In TASM Workload Designer, create filter rule with:
--   Query Band: Group=Marketing
--   Action: Reject DDL
--   Time Period: 8am-5pm

-- When a Marketing user tries DDL during business hours:
SET QUERY_BAND = 'ClientUser=AA39494;Group=Marketing;' FOR SESSION;
CREATE TABLE testtab2(c1 INT, c2 INT);
-- *** Failure 3149 TWM Access violation: No access allowed, For DDL requests,
--   For query band GROUP=MARKETING, During rule state DayState
```

**Important**: Filter rules that prevent logon do NOT use query band classification (profile query band is applied after successful logon). Use object types like user, account, or profile for logon filters.

### Workload Definitions with Query Bands

Query band name-value pairs can be configured as "Who" classification criteria in workload definitions.

**Classification rules:**
- Different query band NAMES are ANDed (all must match).
- Different VALUES for the same NAME are ORed (any can match).
- Names and values are NOT case sensitive.

```sql
-- WD 1: Marketing-Online (Tactical priority)
-- Classification: ClientUser IN (DG456, KS232, MG123)
--             AND Group = Marketing
--             AND Importance = OnlineTactical

-- WD 2: Marketing-Batch (Normal priority)
-- Classification: ClientUser IN (MG123, DG456, KS232, WD333)
--             AND Group = Marketing
--             AND Importance = BatchStrategic

-- User controls their own priority by changing the Importance value:
SET QUERY_BAND = 'ClientUser=MG123;Group=Marketing;Importance=OnlineTactical;' FOR SESSION;
SELECT * FROM cust_table WHERE CustomerId = 'Teradata';
-- Request classified to Marketing-Online (Tactical priority)

SET QUERY_BAND = 'ClientUser=MG123;Group=Marketing;Importance=BatchStrategic;' FOR SESSION;
SELECT * FROM cust_table WHERE State = 'CA';
-- Request classified to Marketing-Batch (Normal priority)
```

### WLM Use Case Patterns

- **Interactive priority**: Tag interactive screen queries to classify to high-priority workloads to prevent user delays.
- **Throttle bypass**: Use a special query band value to classify to a workload with no throttle limit for exceptional cases.
- **Department separation**: Same application, different departments classified to different workloads with different throttle limits.
- **Tactical qualification**: For CPU-estimate-based tactical workloads, add query band classification to ensure only high-priority work enters tactical workloads.

## DBQL Advanced Query Band Analysis

### Extract Usage by Query Band Functions

```sql
-- Using GetQueryBandValueSF for DBQL analysis (recommended, 2x faster)
SELECT UserName, StartTime,
       ((FirstRespTime - StartTime) DAY(4) TO SECOND) AS TotalRespTime,
       ((FirstRespTime - FirstStepTime) DAY(4) TO SECOND) AS QryExecTime
FROM DBC.DBQLogTbl
WHERE GetQueryBandValueSF(queryband, 0, 'Importance') = 'BatchStrategic'
ORDER BY UserName, StartTime;

-- Extract system usage by ClientUser and Group
SELECT AMPCPUTime, ParserCPUTime
FROM DBC.DBQLogTbl
WHERE GetQueryBandValueSF(queryband, 0, 'ClientUser') = 'KS3887'
  AND GetQueryBandValueSF(queryband, 0, 'Group') = 'finance';

-- Extract all requests in a unit of work
SELECT StartTime, QueryText
FROM DBC.DBQLogTbl
WHERE GetQueryBandValueSF(queryband, 0, 'JobId') = 'z56'
ORDER BY StartTime;
```

### DBQL Query Band Reporting with Log Views

```sql
-- Extract query band and SQL text from the log view
SELECT QueryBand (FORMAT 'X(50)'), QueryText (FORMAT 'X(30)')
FROM DBC.QryLogV
ORDER BY StartTime, QueryId;

-- Extract aggregate metrics grouped by a query band name
SELECT LogDate, UserName,
       GetQueryBandValueSF(queryband, 0, 'TESTReport') AS RptQBValue,
       EXTRACT(HOUR FROM FirstStepTime) AS FirstStepHr,
       StatementGroup, StatementType,
       AVG(ParserCPUTime), AVG(AMPCPUTime),
       MAX(ParserCPUTime), MAX(AMPCPUTime), COUNT(*)
FROM DBC.DBQLogTbl
WHERE LogDate = CURRENT_DATE
  AND GetQueryBandValueSF(queryband, 0, 'TESTProj') = 'ProjA1'
  AND queryband IS NOT NULL
GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY 1, 2, 3, 4, 5, 6;
```

### Parse Query Band Pairs from DBQL

```sql
-- Decompose all query band pairs from a specific logged query
SELECT QBName, QBValue
FROM (SELECT queryband FROM DBC.DBQLogTbl
      WHERE QueryId = 307192533543958049) AS t1,
     TABLE (GetQueryBandPairs(t1.queryband, 0)) AS t2;

-- Note: On releases before TD 15.0, add "AND queryband IS NOT NULL"
-- because GetQueryBandValue did not accept NULL inputs
```

## Client API Integration

### JDBC

```java
// Set query band via JDBC connection property
Properties props = new Properties();
props.setProperty("user", "serviceaccount");
props.setProperty("password", "password");
Connection conn = DriverManager.getConnection("jdbc:teradata://host", props);

// Set query band via SQL
Statement stmt = conn.createStatement();
stmt.execute("SET QUERY_BAND = 'ApplicationName=MyApp;ClientUser=jsmith;' FOR SESSION");

// Parameterized transaction query band
PreparedStatement pstmt = conn.prepareStatement("SET QUERY_BAND = ? FOR TRANSACTION;");
pstmt.setString(1, "JobID=payroll;JobSeq=1;");
pstmt.execute();
```

### Java ThreadLocalContext Pattern

Teradata provides a `ThreadLocalContext` class for maintaining application context across threads. Key helper methods:

```java
// Console application: set context at entry point
ThreadLocalContext.setClientUser(System.getProperty("USER"));
ThreadLocalContext.setGroup("TZA_BROKER");
ThreadLocalContext.setProxyUser("TZA_PROXY_USER");
ThreadLocalContext.setProxyRole("TZA_PROXY_ROLE");
ThreadLocalContext.setSource(MyApp.class.toString());
ThreadLocalContext.setAction("main");

// Web application: set context in a Servlet Filter
public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain) {
    ThreadLocalContext.setSource(((HttpServletRequest) request).getRequestURI());
    ThreadLocalContext.setAction(((HttpServletRequest) request).getMethod());
    // ...
}

// Attach to queries automatically
String query = "SELECT * FROM ZipCodeRiskFactors WHERE ? BETWEEN StartZipRange AND EndZipRange";
PreparedStatement stmt = connection.prepareStatement(
    ThreadLocalContext.getQueryBandForTransaction() + query);

// Helper methods generate formatted SET QUERY_BAND statements:
// getQueryBandForTransaction() returns "SET QUERY_BAND='...' FOR TRANSACTION;"
// getQueryBandForSession() returns "SET QUERY_BAND='...' FOR SESSION;"
// QueryIssueTime is automatically injected into every query band
```

### BTEQ

```sql
.LOGON acctuser
SET QUERY_BAND = 'ClientUser=MG445;ApplicationName=CRM;JobID=CRM123;' FOR SESSION;
INSERT INTO Payroll_Test (EmpNo, Name, DeptNo) VALUES (1592, 'Mary Jones', 900);
UPDATE DeptCount SET EmpCount = EmpCount + 1;
SELECT * FROM DeptCount;
.LOGOFF
```

### Third-Party BI Tools

**MicroStrategy**: Configurable through MicroStrategy Intelligence Server to set query bands for metadata requests and report requests with customizable priority levels.

**IBM Cognos**: Use connection command blocks to set query bands at connection/session initialization. Command blocks can be added when creating a data source or modified on existing connections.

## Error Handling and Common Issues

| Error/Warning | Cause | Resolution |
|---|---|---|
| Warning 9987 | SET QUERY_BAND contains pairs matching profile NOT DEFAULT names or Ignored Query Band Values | Expected behavior; matching pairs are silently discarded |
| Failure 3149 | TWM Access violation from filter rule | Query band matched a filter rule restricting access during the current time period |
| Failure on proxy logon | GRANT CONNECT THROUGH not set up | Issue appropriate GRANT CONNECT THROUGH for the proxy user/trusted user combination |
| Missing trailing semicolon | Query band string doesn't end with `;` | Always end with semicolon: `'key=value;'` not `'key=value'` |
| Query band truncated in HELP SESSION | MaxSetQueryBandSize > 2048 with export width > 1 | Use individual query band fields instead of combined QueryBand field |
| NULL queryband in DBQL | No query band was set for the session | Add `AND queryband IS NOT NULL` to DBQL queries (required before TD 15.0) |

## Performance Considerations

- **Session table writes**: Each non-VOLATILE SET QUERY_BAND FOR SESSION writes to the session table. Use VOLATILE option for high-frequency changes.
- **Max length**: Larger query bands increase network and storage overhead. Stay within practical limits even though 4096 is supported.
- **GetQueryBandValueSF vs GetQueryBandValue**: Always prefer the SF (embedded services) version for DBQL analysis — ~2x faster throughput.
- **TD 16.0+ optimization**: GetQueryBandValue(0, 'name') in WHERE clauses is replaced with constants at parse time, enabling index access.
- **Utility query bands**: Set FOR SESSION (not TRANSACTION) for load/unload utilities to allow operation across restarts.
