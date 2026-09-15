---
name: query-logging-and-auditing
description: 'Configure Teradata query logging and access auditing using BEGIN LOGGING, END LOGGING, BEGIN QUERY LOGGING, END QUERY LOGGING, REPLACE QUERY LOGGING, FLUSH QUERY LOGGING, SHOW QUERY LOGGING, and BEGIN/END QUERY CAPTURE. Use when setting up DBQL (Database Query Log) rules, configuring access logging for security auditing, controlling logging granularity and frequency, managing query capture for workload replay, flushing DBQL cache, or monitoring query activity and resource usage.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Query Logging and Auditing

## When to Use

- Setting up DBQL rules to log query activity and resource usage
- Configuring access logging for security auditing
- Controlling which users, databases, or objects are logged
- Managing logging frequency (FIRST, LAST, EACH)
- Flushing DBQL cache to disk for immediate analysis
- Setting up query capture for workload analysis and replay
- Monitoring query performance and identifying expensive queries

## Two Logging Systems

| System | Purpose | Statements |
|--------|---------|------------|
| **Access Logging** | Security audit — logs privilege checks | BEGIN/END LOGGING |
| **DBQL (Query Logging)** | Performance/usage — logs query details, resources, explain plans | BEGIN/END QUERY LOGGING |

## Access Logging (BEGIN LOGGING)

### Syntax

```sql
BEGIN LOGGING [DENIALS] [WITH TEXT]
  ON [logging_frequency]
  [FOR CONSTRAINT constraint_name]
  { ALL | operation [,...] | GRANT }
  [BY user_name [,...]]
  [ON { DATABASE database_name | TABLE table_name | ... }]
;
```

### Logging Frequency

| Frequency | Behavior |
|-----------|----------|
| `FIRST` | Log only the first occurrence per session |
| `LAST` | Log only the last occurrence per session |
| `FIRST AND LAST` | Log both first and last |
| `EACH` | Log every occurrence (most verbose) |

### Common Access Logging Patterns

```sql
-- Log all failed privilege checks on a database
BEGIN LOGGING DENIALS ON EACH ALL ON DATABASE finance_db;

-- Log SELECT access on sensitive tables
BEGIN LOGGING ON EACH SELECT ON TABLE hr_db.salaries;

-- Log all operations by specific users
BEGIN LOGGING WITH TEXT ON EACH ALL BY suspicious_user;

-- Log GRANT operations system-wide
BEGIN LOGGING ON EACH GRANT;

-- Log DDL operations on a database
BEGIN LOGGING ON EACH
    CREATE, DROP, ALTER
    ON DATABASE production_db;
```

### END LOGGING

```sql
-- Stop logging for a specific rule
END LOGGING ON EACH SELECT ON TABLE hr_db.salaries;

-- Stop all logging for a database
END LOGGING ON ALL ON DATABASE finance_db;
```

### DENIALS Option

```sql
-- Log only failed access attempts (security monitoring)
BEGIN LOGGING DENIALS ON EACH ALL ON DATABASE production_db;
```

### WITH TEXT Option

```sql
-- Include the SQL text in the log entry
BEGIN LOGGING WITH TEXT ON EACH ALL BY audit_user;
```

## DBQL Query Logging (BEGIN QUERY LOGGING)

### Syntax

```sql
BEGIN QUERY LOGGING
  [WITH { SQL | OBJECTS | EXPLAIN | STEPINFO | PARAMINFO
        | STATSUSAGE | USECOUNT | UTILITYINFO | XMLPLAN
        | FEATUREINFO | LOCKINFO | SUMMARYONLY } [,...]]
  [LIMIT { SQLTEXT = n | THRESHOLD = n [SECONDS] | SUMMARY = interval }]
  ON { ALL | user_name [,...] }
;
```

### Common DBQL Patterns

```sql
-- Log all queries with SQL text for all users
BEGIN QUERY LOGGING WITH SQL ON ALL;

-- Log with full detail for specific users
BEGIN QUERY LOGGING WITH SQL, OBJECTS, EXPLAIN, STEPINFO
    ON analyst_user, etl_user;

-- Log only queries exceeding 10 seconds
BEGIN QUERY LOGGING WITH SQL
    LIMIT THRESHOLD = 10 SECONDS
    ON ALL;

-- Summary-only logging (aggregated, low overhead)
BEGIN QUERY LOGGING
    LIMIT SUMMARY = 600  -- aggregate every 10 minutes
    ON ALL;

-- Log with object-level detail (tables/columns accessed)
BEGIN QUERY LOGGING WITH SQL, OBJECTS ON ALL;

-- Log with step-level performance data
BEGIN QUERY LOGGING WITH SQL, STEPINFO ON ALL;

-- Log with EXPLAIN plan
BEGIN QUERY LOGGING WITH SQL, EXPLAIN ON ALL;

-- Log lock information
BEGIN QUERY LOGGING WITH SQL, LOCKINFO ON ALL;
```

### DBQL WITH Options

| Option | Logs To | Content |
|--------|---------|---------|
| `SQL` | DBQLSQLTbl | Full SQL text |
| `OBJECTS` | DBQLObjTbl | Tables, views, columns accessed |
| `EXPLAIN` | DBQLExplainTbl | EXPLAIN plan text |
| `STEPINFO` | DBQLStepTbl | Per-step CPU, I/O, spool |
| `PARAMINFO` | DBQLParamTbl | Parameterized query values |
| `STATSUSAGE` | DBQLStatsUsageTbl | Statistics used by optimizer |
| `USECOUNT` | DBQLUsecountTbl | Object access counts |
| `UTILITYINFO` | DBQLUtilityTbl | Utility (load/export) details |
| `XMLPLAN` | DBQLXMLTbl | XML format query plan |
| `FEATUREINFO` | DBQLFeatureInfoTbl | Features used by query |
| `LOCKINFO` | DBQLLockInfoTbl | Lock details |
| `SUMMARYONLY` | DBQLSummaryTbl | Aggregated metrics only |

### LIMIT Options

| Limit | Purpose |
|-------|---------|
| `SQLTEXT = n` | Maximum SQL text length to capture (bytes) |
| `THRESHOLD = n SECONDS` | Only log queries running longer than n seconds |
| `SUMMARY = interval` | Aggregate queries into summary records every interval seconds |

## REPLACE QUERY LOGGING

Modify an existing DBQL rule without dropping and recreating.

```sql
REPLACE QUERY LOGGING WITH SQL, OBJECTS, STEPINFO
    LIMIT THRESHOLD = 5 SECONDS
    ON ALL;
```

## FLUSH QUERY LOGGING

Force DBQL cache to be written to disk immediately.

```sql
-- Flush all cached DBQL data
FLUSH QUERY LOGGING WITH ALL;

-- Flush for specific users
FLUSH QUERY LOGGING WITH ALL ON user_name;
```

> By default, DBQL data is cached in memory and periodically flushed. Use FLUSH to make data available for immediate analysis.

## SHOW QUERY LOGGING

Display current DBQL rules.

```sql
SHOW QUERY LOGGING ON ALL;
SHOW QUERY LOGGING ON user_name;
```

## END QUERY LOGGING

```sql
-- Stop logging for all users
END QUERY LOGGING ON ALL;

-- Stop logging for specific user
END QUERY LOGGING ON analyst_user;
```

## BEGIN / END QUERY CAPTURE

Captures query plans and statistics for the Query Capture Database (QCD) — used for workload replay and plan analysis.

```sql
-- Start capturing
BEGIN QUERY CAPTURE ON ALL;

-- Stop capturing
END QUERY CAPTURE ON ALL;
```

## Querying DBQL Data

### Recent Query Activity

```sql
SELECT UserName, QueryText, StartTime, 
       AMPCPUTime, TotalIOCount, SpoolUsage,
       ErrorCode
FROM DBC.DBQLogTbl
WHERE StartTime > CURRENT_TIMESTAMP - INTERVAL '1' HOUR
ORDER BY AMPCPUTime DESC;
```

### Top Resource-Consuming Queries

```sql
SELECT TOP 20
    UserName,
    SUBSTR(QueryText, 1, 200) AS QuerySnippet,
    AMPCPUTime,
    TotalIOCount,
    SpoolUsage,
    ElapsedTime
FROM DBC.DBQLogTbl
WHERE StartTime > CURRENT_DATE - 1
ORDER BY AMPCPUTime DESC;
```

### Object Access Frequency

```sql
SELECT ObjectDatabaseName, ObjectTableName,
       COUNT(*) AS access_count,
       SUM(FreqOfUse) AS total_uses
FROM DBC.DBQLObjTbl
WHERE CollectTimeStamp > CURRENT_DATE - 7
GROUP BY 1, 2
ORDER BY access_count DESC;
```

### Access Log Entries

```sql
SELECT LogDate, LogTime, UserName, 
       StatementType, AccessResult
FROM DBC.AccLogTbl
WHERE LogDate > CURRENT_DATE - 1
ORDER BY LogDate DESC, LogTime DESC;
```

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| 3706: Syntax error | Invalid logging syntax | Check WITH options and ON clause |
| 5612: No privilege | Missing EXECUTE on DBC.AccLogRule | Grant EXECUTE on the macro |
| 3523: Rule already exists | Duplicate BEGIN QUERY LOGGING | Use REPLACE or END first |

## Prerequisites

- **Access Logging:** Run DIPACC script to create `DBC.AccLogRule` macro before first use
- **DBQL:** No special setup — system tables exist by default
- **Privilege:** `EXECUTE` on `DBC.AccLogRule` for access logging; DBA privileges for DBQL

## Performance Impact

| Logging Level | Overhead | Use Case |
|---------------|----------|----------|
| SUMMARYONLY | Minimal | Always-on baseline monitoring |
| SQL only | Low | General query auditing |
| SQL + OBJECTS | Low-Moderate | Understanding table access patterns |
| SQL + STEPINFO | Moderate | Performance analysis |
| SQL + EXPLAIN | Moderate-High | Plan analysis for specific users |
| ALL options | High | Short-term deep diagnostics only |
| THRESHOLD-based | Variable | Production-safe — only logs slow queries |

## References


> **Access:** `skill_resource_read(action="read", skill="query-logging-and-auditing", path="references/FILENAME")` — do NOT call `list`.

- [DBQL Tables and Analysis Queries](./references/dbql-tables-and-analysis.md) — Complete DBQL table schema, common analysis queries, and logging strategy recommendations

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 19
