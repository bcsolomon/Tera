# DBQL Tables and Analysis Queries — Complete Reference

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 19

## DBQL Table Overview

| Table | Content | Populated By |
|-------|---------|--------------|
| `DBC.DBQLogTbl` | Main query log — one row per query | Always (when DBQL is on) |
| `DBC.DBQLSQLTbl` | Full SQL text | `WITH SQL` |
| `DBC.DBQLObjTbl` | Objects (tables, views) accessed | `WITH OBJECTS` |
| `DBC.DBQLExplainTbl` | EXPLAIN plan text | `WITH EXPLAIN` |
| `DBC.DBQLStepTbl` | Per-step execution details | `WITH STEPINFO` |
| `DBC.DBQLParamTbl` | Parameter markers and values | `WITH PARAMINFO` |
| `DBC.DBQLStatsUsageTbl` | Statistics used by optimizer | `WITH STATSUSAGE` |
| `DBC.DBQLUtilityTbl` | Utility execution details | `WITH UTILITYINFO` |
| `DBC.DBQLXMLTbl` | XML-format query plan | `WITH XMLPLAN` |
| `DBC.DBQLFeatureInfoTbl` | Database features used | `WITH FEATUREINFO` |
| `DBC.DBQLLockInfoTbl` | Lock details per query | `WITH LOCKINFO` |
| `DBC.DBQLSummaryTbl` | Aggregated query metrics | `LIMIT SUMMARY` |

## Key Columns in DBC.DBQLogTbl

| Column | Type | Description |
|--------|------|-------------|
| `QueryID` | FLOAT | Unique query identifier |
| `UserName` | VARCHAR(128) | Submitting user |
| `AcctString` | VARCHAR(128) | Account string |
| `StartTime` | TIMESTAMP | Query start time |
| `FirstRespTime` | TIMESTAMP | Time of first response row |
| `ElapsedTime` | FLOAT | Total elapsed time (seconds) |
| `AMPCPUTime` | FLOAT | Total AMP CPU time (seconds) |
| `ParserCPUTime` | FLOAT | Parser CPU time |
| `TotalIOCount` | FLOAT | Total I/O operations |
| `SpoolUsage` | FLOAT | Peak spool space (bytes) |
| `NumResultRows` | FLOAT | Rows returned |
| `StatementType` | VARCHAR(20) | SELECT, INSERT, UPDATE, DELETE, etc. |
| `ErrorCode` | INTEGER | 0 = success, nonzero = error |
| `NumOfActiveAMPs` | INTEGER | AMPs used by the query |
| `MaxAMPCPUTime` | FLOAT | Max CPU on any single AMP |
| `MinAMPCPUTime` | FLOAT | Min CPU on any single AMP |
| `MaxAMPIO` | FLOAT | Max I/O on any single AMP |
| `Sessionid` | INTEGER | Session ID |
| `QueryBand` | VARCHAR(4096) | Query band string |

## Common Analysis Queries

### Top 20 Expensive Queries (Last 24 Hours)

```sql
SELECT TOP 20
    l.UserName,
    l.StartTime,
    l.AMPCPUTime,
    l.TotalIOCount,
    l.SpoolUsage / 1e9 AS spool_gb,
    l.ElapsedTime,
    l.NumResultRows,
    SUBSTR(s.SQLTextInfo, 1, 300) AS sql_snippet
FROM DBC.DBQLogTbl l
LEFT JOIN DBC.DBQLSQLTbl s ON l.QueryID = s.QueryID
WHERE l.StartTime > CURRENT_TIMESTAMP - INTERVAL '24' HOUR
  AND l.ErrorCode = 0
ORDER BY l.AMPCPUTime DESC;
```

### Query Volume by User (Hourly)

```sql
SELECT UserName,
       EXTRACT(HOUR FROM StartTime) AS hour_of_day,
       COUNT(*) AS query_count,
       SUM(AMPCPUTime) AS total_cpu,
       AVG(ElapsedTime) AS avg_elapsed
FROM DBC.DBQLogTbl
WHERE StartTime > CURRENT_DATE
GROUP BY 1, 2
ORDER BY 1, 2;
```

### Slow Queries (> 60 Seconds)

```sql
SELECT l.UserName, l.StartTime, l.ElapsedTime,
       l.AMPCPUTime, l.TotalIOCount,
       l.StatementType,
       SUBSTR(s.SQLTextInfo, 1, 500) AS sql_text
FROM DBC.DBQLogTbl l
LEFT JOIN DBC.DBQLSQLTbl s ON l.QueryID = s.QueryID
WHERE l.StartTime > CURRENT_DATE - 1
  AND l.ElapsedTime > 60
ORDER BY l.ElapsedTime DESC;
```

### AMP Skew Detection

```sql
SELECT UserName, QueryID, StartTime,
       AMPCPUTime,
       MaxAMPCPUTime,
       MinAMPCPUTime,
       CASE WHEN MinAMPCPUTime > 0
            THEN MaxAMPCPUTime / MinAMPCPUTime
            ELSE 999 END AS cpu_skew_ratio
FROM DBC.DBQLogTbl
WHERE StartTime > CURRENT_DATE - 1
  AND AMPCPUTime > 10
  AND MaxAMPCPUTime / NULLIFZERO(MinAMPCPUTime) > 5
ORDER BY cpu_skew_ratio DESC;
```

### Most Accessed Tables

```sql
SELECT ObjectDatabaseName AS db_name,
       ObjectTableName AS table_name,
       COUNT(*) AS query_count,
       COUNT(DISTINCT l.UserName) AS distinct_users
FROM DBC.DBQLObjTbl o
JOIN DBC.DBQLogTbl l ON o.QueryID = l.QueryID
WHERE o.CollectTimeStamp > CURRENT_DATE - 7
  AND o.ObjectType = 'Tab'
GROUP BY 1, 2
ORDER BY query_count DESC;
```

### Failed Queries

```sql
SELECT UserName, ErrorCode, StatementType,
       COUNT(*) AS failure_count,
       SUBSTR(s.SQLTextInfo, 1, 200) AS sample_sql
FROM DBC.DBQLogTbl l
LEFT JOIN DBC.DBQLSQLTbl s ON l.QueryID = s.QueryID
WHERE l.StartTime > CURRENT_DATE - 1
  AND l.ErrorCode <> 0
GROUP BY 1, 2, 3, 5
ORDER BY failure_count DESC;
```

### Spool Space Consumers

```sql
SELECT TOP 20
    UserName, QueryID, StartTime,
    SpoolUsage / 1e9 AS spool_gb,
    AMPCPUTime,
    ElapsedTime
FROM DBC.DBQLogTbl
WHERE StartTime > CURRENT_DATE - 1
  AND SpoolUsage > 1e9  -- > 1 GB spool
ORDER BY SpoolUsage DESC;
```

## Access Log Analysis

### Failed Privilege Checks

```sql
SELECT LogDate, LogTime, UserName,
       StatementType, AccessResult,
       ObjectDatabaseName, ObjectTableName
FROM DBC.AccLogTbl
WHERE AccessResult = 'Denied'
  AND LogDate > CURRENT_DATE - 7
ORDER BY LogDate DESC, LogTime DESC;
```

### Privilege Check Summary by User

```sql
SELECT UserName, AccessResult,
       COUNT(*) AS check_count
FROM DBC.AccLogTbl
WHERE LogDate > CURRENT_DATE - 7
GROUP BY 1, 2
ORDER BY check_count DESC;
```

## Logging Strategy Recommendations

### Production (Always-On)

```sql
-- Lightweight: summary only, low overhead
BEGIN QUERY LOGGING LIMIT SUMMARY = 600 ON ALL;

-- Targeted: full detail for ETL accounts
BEGIN QUERY LOGGING WITH SQL, OBJECTS, STEPINFO
    ON etl_service_account;

-- Threshold: capture slow queries for investigation
BEGIN QUERY LOGGING WITH SQL, EXPLAIN
    LIMIT THRESHOLD = 30 SECONDS
    ON ALL;
```

### Troubleshooting (Short-Term)

```sql
-- Full detail for a specific user experiencing issues
BEGIN QUERY LOGGING WITH SQL, OBJECTS, EXPLAIN, STEPINFO
    ON problem_user;

-- Remember to turn off after investigation
END QUERY LOGGING ON problem_user;
```

### Security Auditing

```sql
-- Log all access to sensitive databases
BEGIN LOGGING WITH TEXT ON EACH ALL ON DATABASE pii_db;
BEGIN LOGGING WITH TEXT ON EACH ALL ON DATABASE financial_db;

-- Log all privilege denials system-wide
BEGIN LOGGING DENIALS ON EACH ALL;
```

## DBQL Data Retention

DBQL tables grow continuously. Implement regular cleanup:

```sql
-- Delete DBQL data older than 30 days
DELETE FROM DBC.DBQLogTbl WHERE StartTime < CURRENT_DATE - 30;
DELETE FROM DBC.DBQLSQLTbl WHERE CollectTimeStamp < CURRENT_DATE - 30;
DELETE FROM DBC.DBQLObjTbl WHERE CollectTimeStamp < CURRENT_DATE - 30;
DELETE FROM DBC.DBQLStepTbl WHERE CollectTimeStamp < CURRENT_DATE - 30;

-- Archive before deleting (recommended)
INSERT INTO archive_db.dbql_archive
SELECT * FROM DBC.DBQLogTbl
WHERE StartTime BETWEEN CURRENT_DATE - 60 AND CURRENT_DATE - 30;
```

## DBQL Cache Behavior

- DBQL data is cached in memory on each AMP
- Cache is flushed automatically at configurable intervals (default ~10 minutes)
- Use `FLUSH QUERY LOGGING` for immediate availability
- Large cache sizes reduce I/O but delay data availability
