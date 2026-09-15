# DBQL Tables and Query Patterns

Quick-reference for the Database Query Log (DBQL) views and tables used in query
performance diagnosis. Covers table purposes, key columns, duration computation,
time-window filtering, and lookup patterns for each diagnostic scenario.

---

## Table Overview

| Table / View | Scope | Use When |
|---|---|---|
| `DBC.QryLogV` | Active/running queries | The query is **still running** — not yet in the completed log |
| `DBC.DBQLogTbl` | Completed query summary | The query **already finished** — look up by user, time, text, or AppId |
| `DBC.DBQLObjTbl` | Object references per query | You need to find a query by **table name** it accessed |
| `DBC.DBQLSqlTbl` | Full SQL text | You need the **complete SQL** (QueryText in DBQLogTbl is truncated to ~200 chars) |
| `DBC.DBQLStepTbl` | Step-level execution data | You need **step elapsed time** and row-count comparisons |
| `DBC.DBQLExplainTbl` | Stored explain plans | You need the **explain plan** without re-running EXPLAIN |

### Decision: Which Table to Query First

```
Is the query still running?
  YES → DBC.QryLogV
  NO  → DBC.DBQLogTbl

Do you need to find it by table name?
  YES → DBC.DBQLObjTbl JOIN DBC.DBQLogTbl

Do you need full SQL text?
  YES → DBC.DBQLSqlTbl JOIN DBC.DBQLogTbl

Do you need step-level breakdown?
  YES → DBC.DBQLStepTbl (after confirming QueryId)
```

---

## Key Columns by Table

### DBC.QryLogV — Active Session Log

| Column | Type | Description |
|---|---|---|
| `QueryId` | DECIMAL(18) | Unique query identifier |
| `UserName` | VARCHAR(128) | User who submitted the query |
| `StartTime` | TIMESTAMP | When the query began |
| `ElapsedTime` | INTERVAL HOUR TO SECOND | Wall-clock time since query started (still accumulating) |
| `QueryText` | VARCHAR(10000) | First ~10 KB of query text |
| `SessionId` | INTEGER | Session that owns the query |
| `AccountString` | VARCHAR(128) | Account info for workload identification |

**Always include in SELECT:** `QueryId`, `UserName`, `StartTime`, `ElapsedTime`, `QueryText`

### DBC.DBQLogTbl — Completed Query Log

| Column | Type | Description |
|---|---|---|
| `QueryID` | DECIMAL(18) | Unique query identifier |
| `UserName` | VARCHAR(128) | Submitting user |
| `StartTime` | TIMESTAMP | Query start timestamp |
| `FirstRespTime` | TIMESTAMP | Time of first response row |
| `TotalFirstRespTime` | FLOAT | Total elapsed seconds (wall-clock duration from start to first response) |
| `AMPCPUTime` | FLOAT | Total AMP CPU seconds consumed |
| `SpoolUsage` | FLOAT | Peak spool bytes |
| `QueryText` | VARCHAR(10000) | First ~200 chars of SQL (truncated!) |
| `StatementType` | VARCHAR(20) | `'Select'`, `'Insert'`, `'Update'`, etc. |
| `AppID` | CHAR | Application identifier (e.g., `'INFORMATICA_ETL'`) |
| `NumSteps` | SMALLINT | Number of optimizer steps in the plan |
| `NumStepswPar` | SMALLINT | Steps with parallelism |
| `ErrorCode` | INTEGER | Non-zero if the query failed |

**Always include in SELECT:** `QueryID`, `UserName`, `StartTime`, `TotalFirstRespTime`, `QueryText`

**For performance ranking also include:** `AMPCPUTime`, `SpoolUsage`

### DBC.DBQLObjTbl — Object References

| Column | Type | Description |
|---|---|---|
| `QueryId` | DECIMAL(18) | Links to DBQLogTbl |
| `ObjectDatabaseName` | VARCHAR(128) | Database containing the referenced object |
| `ObjectTableName` | VARCHAR(128) | Table/view name referenced by the query |
| `ObjectType` | VARCHAR(20) | `'Tab'`, `'Viw'`, etc. |

**Join key:** `DBQLObjTbl.QueryId = DBQLogTbl.QueryId`

### DBC.DBQLSqlTbl — Full SQL Text

| Column | Type | Description |
|---|---|---|
| `QueryId` | DECIMAL(18) | Links to DBQLogTbl |
| `SqlTextInfo` | VARCHAR(31000) | SQL text chunk |
| `SqlRowNo` | INTEGER | Ordering sequence (1-based) for multi-row SQL |

**Join key:** `DBQLSqlTbl.QueryId = DBQLogTbl.QueryId`
**Order by:** `SqlRowNo` to reassemble full text

### DBC.DBQLStepTbl — Step-Level Data

| Column | Type | Description |
|---|---|---|
| `QueryID` | DECIMAL(18) | Links to DBQLogTbl |
| `StepLev1Num` | INTEGER | Step sequence (level 1) within the query plan |
| `StepName` | VARCHAR(128) | Operation type (RETRIEVE, JOIN, AGG, etc.) |
| `CPUTime` | FLOAT | CPU seconds this step consumed |
| `StepStartTime` | TIMESTAMP | When the step started |
| `StepStopTime` | TIMESTAMP | When the step finished |
| `EstRowCount` | FLOAT | Optimizer's estimated row count |
| `RowCount` | FLOAT | Actual row count produced |

**Compute step elapsed time:** `(StepStopTime - StepStartTime) SECOND(4)` or use `CPUTime` as a proxy.

**Key comparison:** `EstRowCount` vs `RowCount` — large discrepancies indicate stale statistics or cardinality misestimation.

---

## Computing Duration

### For Active Queries (DBC.QryLogV)

`ElapsedTime` is a running INTERVAL value. Use directly:

```sql
SELECT QueryId, UserName, StartTime, ElapsedTime, QueryText
FROM DBC.QryLogV
WHERE UserName = 'rpt_user'
ORDER BY ElapsedTime DESC;
```

The longest-running query sorts to the top.

### For Completed Queries (DBC.DBQLogTbl)

`TotalFirstRespTime` is a FLOAT in seconds. To get human-readable duration:

```sql
-- Raw seconds (for sorting and comparison)
SELECT QueryID, TotalFirstRespTime
FROM DBC.DBQLogTbl
ORDER BY TotalFirstRespTime DESC;

-- As hours:minutes:seconds
SELECT QueryID,
       CAST(TotalFirstRespTime / 3600 AS INTEGER) AS Hours,
       CAST(MOD(CAST(TotalFirstRespTime AS INTEGER), 3600) / 60 AS INTEGER) AS Minutes,
       MOD(CAST(TotalFirstRespTime AS INTEGER), 60) AS Seconds
FROM DBC.DBQLogTbl;

-- Alternative: compute from timestamps
SELECT QueryID,
       (FirstRespTime - StartTime) HOUR(4) TO SECOND AS Duration
FROM DBC.DBQLogTbl;
```

### For Steps (DBC.DBQLStepTbl)

`CPUTime` is a FLOAT in seconds at the step level. To find the bottleneck:

```sql
-- Bottleneck step by CPU
SELECT StepLev1Num, StepName, CPUTime
FROM DBC.DBQLStepTbl
WHERE QueryID = <query_id>
ORDER BY CPUTime DESC;

-- Total step CPU vs query elapsed time (difference = overhead/queuing)
SELECT SUM(CPUTime) AS TotalStepCPU
FROM DBC.DBQLStepTbl
WHERE QueryID = <query_id>;
```

---

## Time-Window Filtering

### Standard Patterns

Always apply a time filter to avoid scanning the entire DBQL log. Use Teradata
INTERVAL syntax:

```sql
-- Last 3 hours (for active/recently-running queries)
WHERE StartTime >= CURRENT_TIMESTAMP - INTERVAL '3' HOUR

-- Last 24 hours (general lookups)
WHERE StartTime >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR

-- Today only
WHERE CAST(StartTime AS DATE) = CURRENT_DATE

-- Specific time window (when user provides "around 2pm")
WHERE StartTime BETWEEN TIMESTAMP '2026-07-15 13:30:00' AND TIMESTAMP '2026-07-15 14:30:00'

-- Last 7 days (broad search)
WHERE StartTime >= CURRENT_TIMESTAMP - INTERVAL '7' DAY
```

### Choosing the Right Window

| Scenario | Recommended Filter |
|---|---|
| Query still running | `INTERVAL '2' HOUR` or `INTERVAL '3' HOUR` |
| User says "today" or "this morning" | `CURRENT_DATE` |
| User provides a specific time | `BETWEEN` with ±30 min buffer |
| User says "yesterday" | `CAST(StartTime AS DATE) = CURRENT_DATE - 1` |
| General "find my query" (no time given) | `INTERVAL '24' HOUR` |
| ETL batch window | `INTERVAL '12' HOUR` or specific batch window |

### Important Notes

- **Always include a time filter** — DBQL tables can be very large (billions of rows on busy systems).
- **INTERVAL syntax requires single quotes around the numeric value:** `INTERVAL '3' HOUR` (not `INTERVAL 3 HOUR`).
- **Use StartTime** as the filter column — it is indexed and partitioned in DBQL.
- **Buffer the window** when the user gives an approximate time — add 30–60 minutes each side.

---

## Lookup Patterns by Scenario

### Pattern 1: Find a Still-Running Query by Username

```sql
SELECT QueryId, UserName, StartTime, ElapsedTime, QueryText
FROM DBC.QryLogV
WHERE UserName = '<username>'
  AND StartTime >= CURRENT_TIMESTAMP - INTERVAL '3' HOUR
ORDER BY ElapsedTime DESC;
```

**Key points:**
- Use `DBC.QryLogV` (not DBQLogTbl) for active queries
- Filter by `UserName` AND a recent time window
- Order by `ElapsedTime DESC` to surface the longest-running first
- Always explain: "Using the active session log because the query is still running"

### Pattern 2: Find a Completed Query by Username and Time

```sql
SELECT QueryID, UserName, StartTime, TotalFirstRespTime, AMPCPUTime,
       SUBSTR(QueryText, 1, 200) AS QuerySnippet
FROM DBC.DBQLogTbl
WHERE UserName = '<username>'
  AND StartTime >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
ORDER BY TotalFirstRespTime DESC;
```

**Key points:**
- Use `DBC.DBQLogTbl` for completed queries
- Include `TotalFirstRespTime` and `AMPCPUTime` for performance context
- Use `SUBSTR(QueryText, 1, 200)` since QueryText may be long
- Order by `TotalFirstRespTime DESC` to find the slowest

### Pattern 3: Find a Query by Table Name

```sql
SELECT o.QueryID, o.ObjectDatabaseName, o.ObjectTableName,
       q.UserName, q.StartTime, q.TotalFirstRespTime,
       CAST(q.QueryText AS VARCHAR(200)) AS QuerySnippet
FROM DBC.DBQLObjTbl o
JOIN DBC.DBQLogTbl q ON o.QueryID = q.QueryID
WHERE o.ObjectTableName = '<table_name>'
  AND q.UserName = '<username>'
  AND q.StatementType = 'Select'
  AND q.StartTime >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
ORDER BY q.StartTime DESC;
```

**Key points:**
- JOIN `DBQLObjTbl` → `DBQLogTbl` on QueryId
- Filter `ObjectTableName` (case-sensitive, usually UPPERCASE)
- Optionally filter `ObjectDatabaseName` for specificity
- Add `StatementType = 'Select'` to exclude DDL/utility statements

### Pattern 4: Find a Query by Application Name (AppID)

```sql
SELECT QueryID, UserName, AppID, StartTime, TotalFirstRespTime,
       SUBSTR(QueryText, 1, 200) AS QuerySnippet
FROM DBC.DBQLogTbl
WHERE AppID = '<app_name>'
  AND StartTime >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
ORDER BY TotalFirstRespTime DESC;
```

**Key points:**
- `AppID` identifies the application (e.g., `'INFORMATICA_ETL'`, `'BTEQ'`, `'JDBC'`)
- Always include time window
- Include `UserName` in output for context

### Pattern 5: Top N Slowest Queries

```sql
SELECT TOP 10 QueryID, UserName, StartTime, TotalFirstRespTime, AMPCPUTime,
       SpoolUsage, SUBSTR(QueryText, 1, 200) AS QuerySnippet
FROM DBC.DBQLogTbl
WHERE UserName = '<username>'
  AND StartTime >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
ORDER BY TotalFirstRespTime DESC;
```

**Key points:**
- Use `TOP 10` (Teradata syntax — not LIMIT)
- Filter by user and time window
- Include `AMPCPUTime` alongside `TotalFirstRespTime` for CPU-bound vs wait analysis
- Order by `TotalFirstRespTime DESC` (always)

### Pattern 6: Retrieve Full SQL Text

```sql
SELECT q.QueryID, q.UserName, q.StartTime, q.TotalFirstRespTime,
       s.SqlTextInfo, s.SqlRowNo
FROM DBC.DBQLogTbl q
JOIN DBC.DBQLSqlTbl s ON q.QueryID = s.QueryID
WHERE q.QueryID = <discovered_query_id>
ORDER BY s.SqlRowNo;
```

**Key points:**
- JOIN only after you have a confirmed QueryId
- `SqlTextInfo` chunks ordered by `SqlRowNo` (concatenate for full text)
- Most queries fit in `SqlRowNo = 1`; long queries span multiple rows

### Pattern 7: Check Step-Level Data Availability

```sql
SELECT StepLev1Num, StepName, CPUTime, EstRowCount, RowCount
FROM DBC.DBQLStepTbl
WHERE QueryID = <query_id>
ORDER BY CPUTime DESC;
```

**Key points:**
- If zero rows returned → step-level logging not enabled for that user
- Fix with: `REPLACE QUERY LOGGING WITH STEPINFO ON <username>;`
- `EstRowCount` vs `RowCount` discrepancy signals stats problems

### Pattern 8: Check for Explain Plan in DBQL

```sql
SELECT ExplainText
FROM DBC.DBQLExplainTbl
WHERE QueryId = <query_id>
ORDER BY ExplainRowNo;
```

**Key points:**
- Explain text stored row-by-row; concatenate by `ExplainRowNo`
- If no rows, the explain must be generated manually with `EXPLAIN <sql>`

---

## Common Column Combinations for SELECT

For quick reference, here are the recommended SELECT column sets per scenario:

| Scenario | Required Columns |
|---|---|
| Active query lookup | `QueryID, UserName, StartTime, ElapsedTime, QueryText` |
| Completed query by user | `QueryID, UserName, StartTime, TotalFirstRespTime, AMPCPUTime, QueryText` |
| Top N slowest | `QueryID, UserName, StartTime, TotalFirstRespTime, AMPCPUTime, SpoolUsage, QueryText` |
| By application | `QueryID, UserName, AppID, StartTime, TotalFirstRespTime, QueryText` |
| By table name (join) | `o.QueryID, o.ObjectTableName, q.UserName, q.StartTime, q.TotalFirstRespTime, q.QueryText` |
| Step analysis | `StepLev1Num, StepName, CPUTime, EstRowCount, RowCount` |
| Full SQL retrieval | `q.QueryID, s.SqlTextInfo, s.SqlRowNo` |

---

## Teradata SQL Syntax Reminders

| Feature | Teradata Syntax | Common Mistake |
|---|---|---|
| Time interval | `INTERVAL '3' HOUR` | `INTERVAL 3 HOUR` (missing quotes) |
| Top N rows | `SELECT TOP 10 ...` | `LIMIT 10` (not supported) |
| Substring | `SUBSTR(col, 1, 200)` | `SUBSTRING(col FROM 1 FOR 200)` |
| Current time | `CURRENT_TIMESTAMP` | `NOW()` (not supported) |
| Date cast | `CAST(col AS DATE)` | `DATE(col)` |
| String match | `LIKE '%pattern%'` | Same as ANSI |
| Case sensitivity | Column values are case-sensitive | Forgetting UPPER() when needed |

---

## Ordering Best Practices

- **Always include ORDER BY** in diagnostic queries — DBQL results without ordering are non-deterministic.
- **Primary sort for performance diagnosis:** `TotalFirstRespTime DESC` (slowest first).
- **Secondary sort alternative:** `StartTime DESC` (most recent first) when looking for latest activity.
- **Step-level sort:** `CPUTime DESC` to identify the bottleneck step.

---

## Explanation Guidelines

When presenting DBQL results, always explain:

1. **Which table you queried and why** — e.g., "Using DBC.QryLogV because the query is still active" or "Using DBQLogTbl because the query already completed."
2. **What the time filter means** — e.g., "Filtering to the last 3 hours to find recently-started queries."
3. **How to interpret TotalFirstRespTime** — e.g., "TotalFirstRespTime shows wall-clock duration in seconds; the query took 847 seconds (about 14 minutes)."
4. **What ordering reveals** — e.g., "Ordered by TotalFirstRespTime DESC so the slowest query appears first."
