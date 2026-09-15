# DBQL Column Catalog

Authoritative column reference for DBQL tables on the target system (Teradata 20.00).
Source: `DBC.ColumnsV` — queried directly from the live system.

> **Note:** `DBC.DBQLogTbl` does NOT have an `ElapsedTime` column.
> Use `TotalFirstRespTime` (FLOAT, seconds) for elapsed wall-clock time.
> Only `DBC.QryLogV` (active sessions) has `ElapsedTime` (as an INTERVAL).

---

## DBC.DBQLogTbl — Completed Query Log (291 columns)

### Key Performance Columns

| Column | Type | Description |
|--------|------|-------------|
| `QueryID` | DECIMAL | System-wide unique query identifier |
| `UserName` | VARCHAR | Name of the user who issued the query |
| `UserID` | BYTE | Internal ID of the user |
| `SessionID` | INTEGER | Unique session identification number |
| `StartTime` | TIMESTAMP | Time the query was submitted |
| `FirstStepTime` | TIMESTAMP | Time the first step was dispatched |
| `FirstRespTime` | TIMESTAMP | Timestamp when first response packet sent to host |
| `LastRespTime` | TIMESTAMP | End of the request / end of response phase |
| `TotalFirstRespTime` | FLOAT | **Elapsed seconds** = FirstRespTime − StartTime + MinRespHoldTime |
| `AMPCPUTime` | FLOAT | Total AMP CPU time in seconds |
| `AMPCPUTimeNorm` | FLOAT | Normalized AMP CPU time (co-existence) |
| `ParserCPUTime` | FLOAT | Total parser + dispatcher CPU seconds |
| `ParserCPUTimeNorm` | FLOAT | Normalized parser CPU seconds |
| `MaxAMPCPUTime` | FLOAT | CPU seconds of the highest-CPU AMP |
| `MaxCPUAmpNumber` | INTEGER | AMP number with highest CPU |
| `MinAmpCPUTime` | FLOAT | CPU seconds of the lowest-CPU AMP |
| `DisCPUTime` | FLOAT | Dispatcher CPU seconds |
| `SpoolUsage` | BIGINT | Peak spool bytes of any step (DataCollectAlg=3) |
| `PersistentSpool` | BIGINT | Persistent portion of SpoolUsage |
| `ReqMaxSpool` | BIGINT | Maximum spool usage by the request |

### Timing & Delay Columns

| Column | Type | Description |
|--------|------|-------------|
| `DelayTime` | FLOAT | Seconds delayed by workload management |
| `DeferTime` | FLOAT | Time deferred before execution |
| `TDWMAdmissionTime` | TIMESTAMP | Time admitted by workload management |
| `MinRespHoldTime` | FLOAT | Seconds response was held to meet min response time SLG |
| `SeqRespTime` | FLOAT | Sum of response time of all steps if executed sequentially |
| `LockDelay` | FLOAT | Max wait time for lock (centi-seconds) |
| `EstProcTime` | FLOAT | Optimizer's estimated processing time (seconds) |
| `EstMaxStepTime` | FLOAT | Estimated maximum step time from optimizer |
| `TDWMEstTotalTime` | FLOAT | Estimated total time in milliseconds (optimizer) |
| `ReqAWTTime` | FLOAT | AWT elapsed seconds for the request |
| `MaxReqAwtTime` | FLOAT | Max AWT elapsed seconds for the request |
| `UnityTime` | FLOAT | Seconds in Unity stored-procedure processing |

### Request Metadata Columns

| Column | Type | Description |
|--------|------|-------------|
| `RequestNum` | INTEGER | Client request number |
| `InternalRequestNum` | INTEGER | Internal Teradata request number |
| `StatementType` | CHAR(20) | Statement type: Select, Insert, Update, Delete, etc. |
| `StatementGroup` | VARCHAR | Grouping: DDL, DML, or SELECT |
| `Statements` | INTEGER | Number of statements in the request |
| `QueryText` | VARCHAR | Query text (default 200 chars, truncated) |
| `AppID` | CHAR | Application identifier |
| `QueryBand` | VARCHAR | Query band metadata |
| `RequestMode` | CHAR | Prep, PrepS, PrepExe, Exe, ExeS, ExeI |
| `NumSteps` | SMALLINT | Total level-1 steps for this query |
| `NumStepswPar` | SMALLINT | Level-1 steps with parallel sub-steps |
| `MaxStepsInPar` | SMALLINT | Max level-2 steps done in parallel |
| `ErrorCode` | INTEGER | Parser syntax error code (0 = success) |
| `ErrorText` | VARCHAR | Error message text if ErrorCode ≠ 0 |
| `ResponseTimeMet` | CHAR | 'T' if service level goals were met |

### Identity & Session Columns

| Column | Type | Description |
|--------|------|-------------|
| `AcctString` | VARCHAR | User unexpanded logon account string |
| `ExpandAcctString` | VARCHAR | Expanded logon string |
| `LogicalHostID` | SMALLINT | Logon source identifier (0 = internal session) |
| `LogonDateTime` | TIMESTAMP | Session logon timestamp |
| `ProxyUser` | VARCHAR | Proxy user name (if applicable) |
| `ProxyUserID` | BYTE | Internal proxy user ID |

### Classification & Flags

| Column | Type | Description |
|--------|------|-------------|
| `TacticalRequest` | CHAR | 'T' if tactical request |
| `TacticalCPUException` | INTEGER | Nodes with CPU exception |
| `CPUDecayLevel` | SMALLINT | Most severe CPU decay level reached |
| `QueryRedriven` | CHAR | 'Y'/'N' if query was re-driven |
| `ParamQuery` | CHAR | 'T' if parameterized |
| `RemoteQuery` | CHAR | 'T' if remote query submitted |
| `MaxStepMemory` | FLOAT | Max memory (MB) used by any step |

---

## DBC.QryLogV — Active Session View (216 columns)

### Key Columns (differs from DBQLogTbl)

| Column | Type | Description |
|--------|------|-------------|
| `QueryID` | DECIMAL | System-wide unique query identifier |
| `UserName` | VARCHAR | User who issued the query |
| `SessionID` | INTEGER | Session number |
| `StartTime` | TIMESTAMP | Time query was submitted |
| `FirstStepTime` | TIMESTAMP | Time first step dispatched |
| `FirstRespTime` | TIMESTAMP | Time first response sent to host |
| `**ElapsedTime**` | INTERVAL | **Difference between FirstRespTime and StartTime** (running interval) |
| `AMPCPUTime` | FLOAT | Total AMP CPU seconds |
| `ParserCPUTime` | FLOAT | Parser + dispatcher CPU seconds |
| `MaxAMPCPUTime` | FLOAT | Highest-CPU AMP seconds |
| `MinAmpCPUTime` | FLOAT | Lowest-CPU AMP seconds |
| `SpoolUsage` | BIGINT | Peak spool bytes |
| `NumSteps` | SMALLINT | Total level-1 steps |
| `StatementType` | CHAR | Statement type |
| `QueryText` | VARCHAR | Query text (200 chars default) |
| `AppID` | CHAR | Application identifier |
| `QueryBand` | VARCHAR | Query band metadata |
| `ErrorCode` | INTEGER | Error code |
| `DelayTime` | FLOAT | Workload management delay seconds |
| `EstProcTime` | FLOAT | Estimated processing time (seconds) |
| `EstMaxStepTime` | FLOAT | Estimated max step time |
| `TotalFirstRespTime` | FLOAT | Elapsed seconds (same formula as DBQLogTbl) |
| `SeqRespTime` | FLOAT | Sequential response time sum |
| `LastRespTime` | TIMESTAMP | End of request |
| `LockDelay` | FLOAT | Lock wait (centi-seconds) |

> **Key difference:** QryLogV has `ElapsedTime` as a live INTERVAL; DBQLogTbl uses `TotalFirstRespTime` (FLOAT seconds).

---

## DBC.DBQLStepTbl — Step-Level Execution Data (197 columns)

### Key Performance Columns

| Column | Type | Description |
|--------|------|-------------|
| `QueryID` | DECIMAL | Links to DBQLogTbl.QueryID |
| `StepLev1Num` | SMALLINT | Level-1 step number (primary sequence) |
| `StepLev2Num` | SMALLINT | Level-2 step number (parallel sub-steps) |
| `StepName` | CHAR | Step abbreviation (e.g., RET, JIN, SUM, MRM, EXE) |
| `StepStartTime` | TIMESTAMP | When step was sent to the AMP |
| `StepStopTime` | TIMESTAMP | When step returned from the AMP |
| `CPUTime` | FLOAT | Total step CPU seconds on AMPs |
| `CPUtimeNorm` | FLOAT | Normalized step CPU seconds |
| `MaxAmpCPUTime` | FLOAT | Highest-CPU AMP for this step |
| `MaxCPUAmpNumber` | INTEGER | AMP number with highest CPU |
| `MinAmpCPUTime` | FLOAT | Lowest-CPU AMP for this step |
| `EstProcTime` | FLOAT | Optimizer's estimated step time (seconds) |
| `EstCPUCost` | FLOAT | Optimizer's CPU estimate (milliseconds) |
| `EstIOCost` | FLOAT | Optimizer's IO service estimate (milliseconds) |
| `EstNetCost` | FLOAT | Optimizer's BYNET cost (milliseconds) |
| `EstHRCost` | FLOAT | Optimizer's other costs |
| `EstRowCount` | FLOAT | Optimizer's estimated row count |
| `RowCount` | FLOAT | Actual rows returned/inserted |
| `RowCount2` | FLOAT | Actual rows updated (MRM/EXE steps) |
| `RowCount3` | FLOAT | Actual rows deleted (EXE steps) |
| `EstRowCountSkew` | FLOAT | Estimated skew rows |
| `SpoolUsage` | BIGINT | Peak spool bytes for this step (DataCollectAlg=3) |
| `MaxAMPSpool` | BIGINT | Highest spool on any AMP |
| `MaxSpoolAmpNumber` | INTEGER | AMP with highest spool |
| `MinAMPSpool` | BIGINT | Lowest spool on any AMP |
| `NumOfActiveAMPs` | INTEGER | AMPs active for this step |
| `AWTTime` | FLOAT | AWT elapsed time for the step |
| `MaxAWTTime` | FLOAT | Max AWT on any AMP |
| `StepStatus` | CHAR | Step completion status |
| `StepInstance` | INTEGER | Instance number for iterative steps |
| `StepWD` | INTEGER | Workload identifier for the step |
| `FragmentNum` | INTEGER | Fragment number in IPE plan execution |

> **Compute step elapsed time:** `(StepStopTime - StepStartTime) SECOND(4)` — there is no `StepElapsedTime` column.
> **Skew detection:** Compare `MaxAmpCPUTime` vs `MinAmpCPUTime` or `MaxAMPSpool` vs `MinAMPSpool`.
> **Cardinality errors:** Compare `EstRowCount` vs `RowCount`.

---

## DBC.DBQLObjTbl — Object References (20 columns)

| Column | Type | Description |
|--------|------|-------------|
| `QueryID` | DECIMAL | Links to DBQLogTbl.QueryID |
| `ObjectDatabaseName` | VARCHAR | Database owning the target object |
| `ObjectTableName` | VARCHAR | Table or view name |
| `ObjectColumnName` | VARCHAR | Column name (if applicable) |
| `ObjectType` | CHAR | Object type code: D=database, T=table, Q=backup, J=journal |
| `FreqofUse` | INTEGER | Times the object was accessed (optimizer count) |
| `TypeofUse` | TINYINT | Use classification code |
| `ObjectID` | BYTE | Internal object identifier |
| `ObjectNum` | INTEGER | Index number in the table |
| `CollectTimeStamp` | TIMESTAMP | When the log entry was generated |
| `ParentReqStartTime` | TIMESTAMP | Parent request submission time |
| `ParentQueryID` | DECIMAL | Parent query ID |

> **Join key:** `DBQLObjTbl.QueryID = DBQLogTbl.QueryID`

---

## DBC.DBQLSqlTbl — Full SQL Text (11 columns)

| Column | Type | Description |
|--------|------|-------------|
| `QueryID` | DECIMAL | Links to DBQLogTbl.QueryID |
| `SqlRowNo` | INTEGER | Row number for multi-row SQL (1-based ordering) |
| `SqlTextInfo` | VARCHAR | Full SQL text segment (up to ~31,000 chars per row) |
| `CollectTimeStamp` | TIMESTAMP | When the log was generated |
| `ParentReqStartTime` | TIMESTAMP | Parent request submission time |
| `ParentQueryID` | DECIMAL | Parent query ID |

> **Reassemble:** `ORDER BY SqlRowNo` to concatenate full SQL text.
> Most queries fit in `SqlRowNo = 1`.

---

## DBC.DBQLExplainTbl — Stored Explain Plans (11 columns)

| Column | Type | Description |
|--------|------|-------------|
| `QueryID` | DECIMAL | Links to DBQLogTbl.QueryID |
| `ExpRowNo` | INTEGER | Row number if explain text > 64KB (ordering) |
| `ExplainText` | VARCHAR | Full explain text segment |
| `CollectTimeStamp` | TIMESTAMP | When the log was generated |
| `ParentReqStartTime` | TIMESTAMP | Parent request submission time |
| `ParentQueryID` | DECIMAL | Parent query ID |

> **Reassemble:** `ORDER BY ExpRowNo` to concatenate full explain.
> Requires `WITH EXPLAIN` logging option to be enabled.

---

## Quick Column-Name Mapping (Common Misconceptions)

| What you want | Wrong name | Correct column | Table |
|---------------|-----------|----------------|-------|
| Elapsed time (completed) | `ElapsedTime` | `TotalFirstRespTime` | DBQLogTbl |
| Elapsed time (active) | — | `ElapsedTime` | QryLogV ✓ |
| Total CPU | `CPUTime` | `AMPCPUTime` | DBQLogTbl |
| Step CPU | — | `CPUTime` | DBQLStepTbl ✓ |
| Step elapsed | `StepElapsedTime` | compute: `StepStopTime - StepStartTime` | DBQLStepTbl |
| Step number | `StepNum` | `StepLev1Num` | DBQLStepTbl |
| App identifier | `AppId` | `AppID` | DBQLogTbl |
| Query ID | `QueryId` | `QueryID` | all tables |

---

## Type Code Legend

| Code | Teradata Type |
|------|--------------|
| D | DECIMAL |
| I | INTEGER |
| I2 | SMALLINT |
| I1 | BYTEINT |
| I8 | BIGINT |
| F | FLOAT |
| TS | TIMESTAMP |
| CF | CHAR (fixed) |
| CV | VARCHAR |
| BF | BYTE (fixed) |
| BV | VARBYTE |
| SZ | TD_ANYTYPE |
