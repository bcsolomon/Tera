# Query Band Advanced Syntax and Reserved Names

## SET QUERY_BAND Complete Syntax

### Session Query Band

```sql
SET QUERY_BAND = 'name1=value1;name2=value2;' FOR SESSION;
```

The session query band is stored in the session table and recovered after a system reset. Each SET QUERY_BAND statement replaces the entire session query band (unless UPDATE is used). Remove with:

```sql
SET QUERY_BAND = NONE FOR SESSION;
```

### Transaction Query Band

```sql
BT;
SET QUERY_BAND = 'ClientUser=DG12234;ApplicationName=TRM;' FOR TRANSACTION;
INS DeptTable('Sales', 120);
INS DeptTable('Accounting', 130);
ET;
```

The transaction query band is discarded when the transaction ends (COMMIT, ROLLBACK, or ABORT). It is NOT written to the session table and NOT restored after a system reset.

Transaction query band can be set inside a macro or stored procedure:

```sql
REPLACE MACRO DisplaySales() AS
(
  SET QUERY_BAND = 'Group=Sales;' FOR TRANSACTION;
  SELECT * FROM SalesResults;
);
```

Transaction query band can be set from a stored procedure input parameter:

```sql
REPLACE PROCEDURE SetSalesTotals(IN QBIN VARCHAR(1000),
    IN stype VARCHAR(60), IN stotal INTEGER)
BEGIN
  BT;
  SET QUERY_BAND = QBIN FOR TRANSACTION;
  INS SalesTotals(stype, stotal);
  ET;
END;
```

### Parameter Markers for Transaction Query Band

The `?` parameter marker is supported for the entire query band string (not for individual names or values):

```java
String ssetqbpm = "SET QUERY_BAND = ? FOR TRANSACTION;";
String txnqb = "cat=asta;tree=palm;flower=rose;";
PreparedStatement pstmt = con.prepareStatement(ssetqbpm);
pstmt.setString(1, txnqb);
```

### Multi-Statement Request

The transaction query band can be used in a multi-statement request as long as it is the first statement:

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

### UPDATE Mode (TD 13.0+)

The UPDATE keyword adds to or modifies the current query band without replacing it entirely:

```sql
SET QUERY_BAND = 'name=value;' UPDATE FOR SESSION;
SET QUERY_BAND = 'name=value;' UPDATE FOR TRANSACTION;
```

Behavior:
- If the name does NOT exist in the current query band, the name-value pair is added.
- If the name DOES exist, the value is replaced.
- A name-value pair cannot be removed with UPDATE, but you can set it to empty: `GROUP=;`

```sql
-- Start with a session band
SET QUERY_BAND = 'city=san diego;' FOR SESSION;
-- GetQueryBand() returns: =S> city=san diego;

-- Add a new pair with UPDATE
SET QUERY_BAND = 'state=california;' UPDATE FOR SESSION;
-- GetQueryBand() returns: =S> state=california;city=san diego;

-- Change an existing value with UPDATE
SET QUERY_BAND = 'city=Fresno;' UPDATE FOR SESSION;
-- GetQueryBand() returns: =S> city=Fresno;state=california;

-- Without UPDATE, replaces entire band
SET QUERY_BAND = 'ClientUser=k31293;Group=payroll;' FOR SESSION;
-- GetQueryBand() returns: =S> ClientUser=k31293;Group=payroll;
```

### VOLATILE Option (TD 14.10+)

Skips writing the query band to the session table, avoiding the overhead of updating session state. The session query band will NOT be restored after a system reset. Volatile query bands are still logged in DBQL and access log tables.

```sql
SET QUERY_BAND = 'name=value;' VOLATILE FOR SESSION;
```

System-wide alternative: Set DBSControl Internal value 411 (QBVolatility) to TRUE to make all SET QUERY_BAND statements skip the session table write.

**Caution when mixing VOLATILE and non-VOLATILE:**

```sql
SET QUERY_BAND = 'QB-expression-A;' FOR SESSION;
  -- Session query band = QB-expression-A, sessiontbl = QB-expression-A

SET QUERY_BAND = 'QB-expression-B;' VOLATILE FOR SESSION;
  -- Session query band = QB-expression-B, sessiontbl = QB-expression-A (unchanged)

-- After system reset:
  -- Session query band restored to QB-expression-A (from sessiontbl)
```

### Maximum Query Band Length

| Release | Max Length |
|---|---|
| TD 12.0–15.10 | 2048 characters |
| TD 16.0+ default | 3072 characters |
| TD 16.0+ configurable | Up to 4096 characters |

Configured via DBS Control utility field `106. MaxSetQueryBandSize` (values: 2048, 3072, 4096).

## Profile Query Band (TD 15.10+)

The profile query band is set at logon and cannot be removed by the user. It enforces that a session always has certain name-value pairs.

```sql
-- Create a profile with a query band (DEFAULT allows user override of values)
CREATE PROFILE load1profile AS QUERY_BAND = 'TVSTEMPERATURE=WARM;' (DEFAULT);
MODIFY USER loaduser AS PROFILE = load1profile;

-- NOT DEFAULT prevents users from overriding the values
CREATE PROFILE userprof AS QUERY_BAND = 'TVSTEMPERATURE=Cold;' (NOT DEFAULT);
MODIFY USER userabc AS PROFILE = userprof;
```

When NOT DEFAULT, if a user sets a session/transaction query band with the same name, matching pairs are silently discarded with Warning 9987:

```
*** Warning: 9987 The query band contains name-value pairs(s) that match your
profile non default query band name(s) or ignored query band value(s).
The matching name-value pair(s) were discarded.
```

### Profile Ignore Query Band Values (TD 16.0+)

Prevents specific name-value pairs from being set in SET QUERY_BAND statements. Matching pairs are silently discarded.

```sql
-- Use Case 1: Block specific value, allow others
CREATE PROFILE salesprofile AS,
  QUERY_BAND = 'GROUP=WestCoast;',
  IGNORE QUERY_BAND VALUES = 'TVSTemperature=HOT;';
-- TVSTemperature=COLD and TVSTemperature=WARM still allowed

-- Use Case 2: Block any value for a name (name=; with no value)
CREATE PROFILE tprofile AS,
  IGNORE QUERY_BAND VALUES = 'Importance=;';
-- All Importance=<anything> pairs will be discarded

-- Use Case 3: Mix default and non-overridable names
CREATE PROFILE mixprofile AS,
  QUERY_BAND = 'A=1;B=2;C=3;D=4;' (DEFAULT),
  IGNORE QUERY_BAND = 'B=;D=;';
-- A and C can be overridden; B and D cannot
```

## Query Band Precedence

When multiple query band types are set simultaneously, they are concatenated with type prefixes:

```
=T> JobID=RPT1;Action=Analysis; =S> ClientUser=DT785; =P> Group=Finance;
```

| Prefix | Type | Precedence |
|---|---|---|
| `=T>` | Transaction query band | Highest (searched first) |
| `=S>` | Session query band | Middle |
| `=P>` | Profile query band | Lowest |

When a name-value pair is looked up, the first match wins (transaction → session → profile). This applies to:
- **Workload Management**: Classification criteria matches the highest-precedence pair.
- **System query band names**: The highest-precedence value controls the feature behavior.

```sql
-- Example: Transaction overrides session for WLM classification
-- Filter rule TASMRule1 classification: group=west
-- Combined bands: =T> group=east; =S> group=west;
-- Result: Request does NOT match TASMRule1 because group=east is highest precedence

-- Example: System name precedence
-- Combined: =T> BlockCompression=FALLBACK; =S> BlockCompression=ALL; SpecificPlan=ALWAYS; =P> SpecificPlan=OFF
-- Effective: BlockCompression=FALLBACK, SpecificPlan=ALWAYS
```

## Complete Reserved Query Band Names

### Base Application Query Band Names

| Name | Description | Usage |
|---|---|---|
| `ClientUser` | Unique ID of the original end user (corporate ID, device ID). Examples: `CFO101`, `ATM-1579` | Individual resource accounting, WLM prioritization, query notification, problem resolution |
| `Group` | User's work group (from LDAP/directory). Examples: `Marketing`, `CRM-PowerUsers` | Group accounting, WLM, notification, problem resolution |
| `ProxyUser` | Proxy identifier for Trusted Sessions. Can be permanent TD user or external user | WLM, Trusted Sessions security, row-level filtering via CURRENT_USER |
| `ProxyRole` | Proxy role for Trusted Sessions. Must be an actual role created in Teradata | WLM, Trusted Sessions security, row-level filtering via CURRENT_ROLE |
| `ApplicationName` | Name/identifier of the application. Examples: `TRM`, `DCM`, `TDE`, `MDM` | Application auditing, WLM, problem resolution |
| `Version` | Application version number. Examples: `06.00.00.00`, `UNKNOWN` | Logging, upgrade planning, problem resolution |
| `QueryIssueTime` | UTC timestamp when query was issued by application. Format: `YYYY-MM-DDThh:mm:ss.sTZD` | Performance measurement, problem resolution |
| `Source` | Original source context (URL, web service, engine name). Examples: `http://host/trm/crossSegment.do`, `MDM Batch Engine` | WLM, logging, debugging |
| `Action` | User action or method that generated the query. Examples: `Save Analysis Profile`, `getFinancialsReport` | WLM, logging, debugging |
| `StartTime` | Entry point timestamp of the thread of execution. Format: UTC `YYYY-MM-DDThh:mm:ss.sTZD` | Performance measurement, query correlation |

### Optional Application Query Band Names

| Name | Description | Example Values |
|---|---|---|
| `Importance` | Priority hint for the query | `OnlineTactical`, `OnlineStrategic`, `BatchTactical`, `BatchStrategic` |
| `MaxQueryTime` | Maximum query time in milliseconds | `300`, `1000` |
| `Deadline` | UTC deadline for query completion | `2007-12-31T23:59:59Z` |
| `JobID` | Unit of work identifier | `Job157`, `payroll` |
| `JobLen` | Number of pieces of work in the job | `5` |
| `JobDeadline` | Deadline for completing the unit of work | `2007-12-31T23:59:59Z` |
| `JobSeq` | Sequence number within the job | `2` |
| `UtilityName` | Utility mechanism name. Recognized: `FASTLOAD`, `MULTLOAD`, `FASTEXP`, `TPTLOAD`, `TPTUPD`, `TPTEXP`, `JDBCL`, `JDBCM`, `JDBCE`, `DOTNETL`, `DOTNETM`, `DOTNETE`, `ARC`, `GENFASTL`, `GENMULTL`, `GENFASTE`, `CSPLOAD` | `FASTLOAD`, `JDBCL` |
| `Destination` | Target database.table name | `TRM_V6.CampaignData` |
| `UtilityDataSize` | Data size estimate for utility operations. Used by TASM for utility management | `SMALL`, `MEDIUM`, `LARGE` |

### System Query Band Names (Feature Directives)

These toggle on/off aspects of various database features:

| Name | Recognized Values | Description |
|---|---|---|
| `BlockCompression` | `YES`, `NO`, `ALL`, `NONE`, `FALLBACK`, `FALLBACKANDCLOBS`, `WITHOUTCLOBS`, `ONLYCLOBS` | Controls block compression for data loads into empty tables |
| `DynamicPlan` | `SYSTEM`, `SYSTEMX`, `OFF` | Controls Incremental Planning and Execution (IPE) for DynamicPlan |
| `ProxyRole` | Role name | Sets the Trusted Session proxy role |
| `ProxyUser` | User name | Sets the Trusted Session proxy user |
| `Redrive` | `ON`, `OFF` | Controls Redrive Protection within a session (ignored if not enabled for the session) |
| `SpecificPlan` | `SYSTEM`, `OFF`, `ALWAYS` | Controls IPE for parameterized and nonparameterized queries |
| `TVSMigration` | `DYNAMIC` | Enables dynamic data migration in Teradata Virtual Storage (TVS) |
| `TVSTemperature` | `VERYHOT`, `HOT`, `WARM`, `COLD` | Data storage temperature for TVS. VERYHOT requires EXECUTE on DBC.VHCTRL |
| `TVSTemperature_Primary` | `VERYHOT`, `HOT`, `WARM`, `COLD` | TVS temperature for primary row and primary secondary index subtables |
| `TVSTemperature_PrimaryCLOBs` | `VERYHOT`, `HOT`, `WARM`, `COLD` | TVS temperature for primary row CLOB subtables |
| `TVSTemperature_Fallback` | `VERYHOT`, `HOT`, `WARM`, `COLD` | TVS temperature for fallback row and fallback secondary index subtables |
| `TVSTemperature_FallbackCLOBs` | `VERYHOT`, `HOT`, `WARM`, `COLD` | TVS temperature for fallback row CLOB subtables |

### QueryGrid Configuration Query Band Names

Set in the query band to override foreign server object settings for Teradata-to-Teradata connector:

| Name | Description |
|---|---|
| `ByteCountReportFreq` | Report frequency in bytes |
| `ConcurrentStreams` | Parallel efficiency |
| `Listen_Timeout` | Seconds to wait for connection while listening |
| `QueryLogging` | When `true`, turns on query logging on the remote system |
| `Read_Timeout` | Seconds to wait on the socket |

### QueryGrid Remote Query Band Names

Automatically set by the Teradata-to-Teradata connector on the remote system to enable joining local and remote DBQL data:

| Name | Description |
|---|---|
| `TD_HOSTID` | Unique identifier of the logon source |
| `TD_HOSTIP` | IP address of the local Teradata system |
| `TD_QUERYID` | Internally generated QueryGrid query identifier |
| `TD_REQUEST` | Request number of the QueryGrid query |
| `TD_SESSION` | Unique session ID executing the QueryGrid query |
| `TD_USER` | Unique ID of the local user |

### Internal/Utility Query Band Names

Used by Teradata utilities internally; values have no meaning when set outside of utilities:

| Name | Description |
|---|---|
| `DSAJobType` | Specifies backup or restore for Data Stream Architecture |
| `DSAPhase` | Current phase of a DSA job |
| `UtilityAWT` | Number of AMP Worker Tasks required for the job |
| `UtilityDataSize` | Data size estimate (SMALL, MEDIUM, LARGE) |
| `UtilityLSN` | Logon Sequence Number for utility job session association |
| `UtilityName` | Utility mechanism name |

## System Functions for Query Bands

### Querying Reserved Names

```sql
-- List all currently recognized reserved query band names
SELECT queryband_name, category, max_len, default_value, description, queryband_type
FROM SYSLIB.QueryBandReservedNames;
```

Underlying table function:

```sql
REPLACE FUNCTION SYSLIB.QueryBandReservedNames_TBF()
RETURNS TABLE
    (queryband_name VARCHAR(128) CHARACTER SET UNICODE,
     release_introduced CHAR(5) CHARACTER SET LATIN,
     release_dropped CHAR(5) CHARACTER SET LATIN,
     category CHAR(1) CHARACTER SET LATIN,
     max_len INTEGER,
     default_value VARCHAR(256) CHARACTER SET UNICODE,
     description VARCHAR(512) CHARACTER SET UNICODE,
     queryband_type CHAR(1) CHARACTER SET LATIN);
```

### GetQueryBand()

Returns the concatenated query bands for the current session with type prefixes:

```sql
SELECT GetQueryBand();
-- Returns: =S> Importance=BatchStrategic;ClientUser=DG1234; =P> Group=Finance;Area=West;
```

### GetQueryBandValue() / GetQueryBandValueSF()

Retrieves the value of a specified name. First parameter selects which band to search:
- `0` = First match across all bands (transaction → session → profile)
- `1` = Transaction query band only
- `2` = Session query band only
- `3` = Profile query band only

```sql
-- Version 1: Current session (no query band string parameter)
SELECT GetQueryBandValue(0, 'ClientUser');
-- Returns: DG1234

-- Version 2: From a DBQL query band string (for analyzing logs)
SELECT GetQueryBandValueSF(queryband, 0, 'Importance')
FROM DBC.DBQLogTbl
WHERE LogDate = CURRENT_DATE;
```

**Performance note**: `GetQueryBandValueSF` is an embedded services function (TD 15.0+) that runs ~2x faster than the UDF version `GetQueryBandValue`:
- `GetQueryBandValue`: ~16.7 requests/second
- `GetQueryBandValueSF`: ~33.3 requests/second

In TD 16.0+, `GetQueryBandValue(0, 'name')` is optimized: the parser replaces the function call with a constant when used in predicates, enabling index access:

```sql
SET QUERY_BAND = 'dbname=qbuser;MyDate=2011-03-01;' FOR SESSION;
-- EXPLAIN shows: condition of "DatabaseName = 'qbuser'" (constant substituted)
SELECT tablename FROM DBC.TablesV
WHERE DatabaseName = GetQueryBandValue(0, 'dbname');
```

### GetQueryBandPairs()

Returns name-value pairs as separate columns. Same first-parameter convention as GetQueryBandValue:

```sql
-- Version 1: From current session
SELECT QBName, QBValue
FROM TABLE (GetQueryBandPairs(0)) AS t1
ORDER BY QBName;

-- Version 2: From DBQL
SELECT QBName, QBValue
FROM (SELECT queryband FROM DBC.DBQLogTbl WHERE QueryId = 307192533543958049) AS t1,
     TABLE (GetQueryBandPairs(t1.queryband, 0)) AS t2;
```

### MonitorQueryBand()

Administrative function to retrieve the query band for any session (requires EXECUTE FUNCTION privilege on MonitorSession and MonitorQueryBand):

```sql
-- First find the session
SELECT HostId, SessionNo, RunVprocNo
FROM TABLE (MonitorSession(1, 'testuser', 0)) AS t2;

-- Then get its query band
SELECT MonitorQueryBand(1, 1001, 30719);
-- Returns: =S> Importance=BatchStrategic;ClientUser=DG1234; =P> Group=Finance;Area=West;
```

### HELP SESSION

Returns individual fields for each query band type:

```
help session;
    QueryBand =T> Job=MonthlyEnd; =S> Importance=BatchStrategic;ClientUser=DG1234;
    Transaction QueryBand Job=MonthlyEnd;
    Session QueryBand Importance=BatchStrategic;ClientUser=DG1234;
    Profile QueryBand Group=Finance;Area=West;
```

Note: The combined QueryBand field may be truncated when MaxSetQueryBandSize > 2048 and session export width > 1. Individual fields always contain the complete query band.

## Feature History by Release

| Release | Features |
|---|---|
| TD 12.0 | Query Banding introduced |
| TD 13.0 | UPDATE option; query band logged in DBC accesslog; Trusted Sessions (ProxyUser/ProxyRole); transaction band from macro/SP parameters |
| TD 13.10 | TRUST_ONLY mechanism; TVSTemperature, TVSMigration, UtilityName, UtilityDataSize system names |
| TD 14.0 | BlockCompression; TVSTemperature_Primary/PrimaryCLOBs/Fallback/FallbackCLOBs |
| TD 14.10 | VOLATILE option; Redrive, DynamicPlan, SpecificPlan system names; VERYHOT TVS value |
| TD 15.0 | GetQueryBandValue accepts NULL; GetQueryBandValueSF embedded function; DSAPhase, UtilityLSN; QueryGrid names |
| TD 15.10 | Profile Query Band; Trusted Sessions proxy user profiles and session attributes; DSAJobType, UtilityAWT |
| TD 16.0 | Ignore Query Band Values; max length to 4096; GetQueryBandValue optimization; X Views Trusted Sessions support |
