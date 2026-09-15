# DBQL Monitoring for Workload Management

## Key DBC Views

| View | Content | Granularity |
|---|---|---|
| `DBC.DBQLogTbl` / `pdcrinfo.DBQLogTbl_Hst` | Per-request metrics | One row per query |
| `DBC.ResUsageSPS` / `pdcrinfo.ResUsageSPS_Hst` | Per-workload resource usage | Per logging interval |
| `DBC.TDWMSummaryLog` | Per-WD summary stats | Per interval |
| `DBC.TDWMEventLog` | TASM activity log | Per event |
| `DBC.TDWMExceptionLog` | Exception details | Per exception |
| `DBC.DBQLObjTbl` / `pdcrinfo.DBQLObjTbl_Hst` | Object-level query info | Per object per query |

## DBQL Key Columns for WLM

| Column | Description |
|---|---|
| `SessionWDID` | Workload assigned at session logon |
| `FinalWDID` | Workload after any re-classification or demotion |
| `TacticalCPUException` | 'Y' if tactical CPU exception fired |
| `TacticalIOException` | 'Y' if tactical I/O exception fired |
| `CPUDecayLevel` | Decay level reached (0, 1, or 2) |
| `IODecayLevel` | Decay level reached |
| `MinRespHoldTime` | Time spent in throttle delay queue |
| `DelayTime` | Total delay time |
| `AmpCPUTime` | Total AMP CPU seconds |
| `TotalIOCount` | Total I/O operations |
| `SpoolUsage` | Spool space consumed |
| `NumSteps` | Number of query steps |
| `NumOfActiveAMPs` | AMPs used |

## Common Monitoring Queries

### Top Workloads by CPU

```sql
SELECT FinalWDID, COUNT(*) AS query_count,
       SUM(AmpCPUTime) AS total_cpu,
       AVG(AmpCPUTime) AS avg_cpu,
       MAX(AmpCPUTime) AS max_cpu
FROM DBC.DBQLogTbl
WHERE LogDate = CURRENT_DATE
GROUP BY FinalWDID
ORDER BY total_cpu DESC;
```

### Throttle Impact — Delay Queue Time

```sql
SELECT FinalWDID,
       COUNT(*) AS delayed_queries,
       AVG(MinRespHoldTime) AS avg_delay_sec,
       MAX(MinRespHoldTime) AS max_delay_sec,
       SUM(MinRespHoldTime) AS total_delay_sec
FROM DBC.DBQLogTbl
WHERE LogDate = CURRENT_DATE
  AND MinRespHoldTime > 0
GROUP BY FinalWDID
ORDER BY total_delay_sec DESC;
```

### Tactical Exception Tracking

```sql
SELECT LogDate, COUNT(*) AS exceptions,
       SUM(CASE WHEN TacticalCPUException = 'Y' THEN 1 ELSE 0 END) AS cpu_exceptions,
       SUM(CASE WHEN TacticalIOException = 'Y' THEN 1 ELSE 0 END) AS io_exceptions
FROM DBC.DBQLogTbl
WHERE LogDate >= CURRENT_DATE - 7
  AND (TacticalCPUException = 'Y' OR TacticalIOException = 'Y')
GROUP BY LogDate
ORDER BY LogDate;
```

### Workload Exception History

```sql
SELECT ExceptionTime, UserName, WDName,
       ExceptionType, ExceptionValue, ExceptionAction
FROM DBC.TDWMExceptionLog
WHERE ExceptionTime >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
ORDER BY ExceptionTime DESC;
```

### Track Analytic Function Usage

```sql
SELECT qlog.LogDate, 
       olog.ObjectTableName AS function_name,
       COUNT(*) AS call_count,
       SUM(qlog.AmpCPUTime) AS total_cpu,
       AVG(qlog.AmpCPUTime) AS avg_cpu,
       SUM(qlog.TotalIOCount) AS total_io
FROM pdcrinfo.DBQLObjTbl_Hst olog
JOIN pdcrinfo.DBQLogTbl_Hst qlog
  ON olog.LogDate = qlog.LogDate
 AND olog.QueryId = qlog.QueryId
WHERE olog.LogDate BETWEEN CURRENT_DATE - 7 AND CURRENT_DATE
  AND olog.ObjectDatabaseName = 'TD_SYSFNLIB'
GROUP BY qlog.LogDate, olog.ObjectTableName
ORDER BY total_cpu DESC;
```

### Per-Workload Resource Summary (ResUsageSPS)

```sql
SELECT TheDate, TheTime, WDName,
       CPUUsage, IOKBReadSum, IOKBWriteSum,
       ActiveAMPCount, ActiveSessions
FROM DBC.ResUsageSPS
WHERE TheDate = CURRENT_DATE
ORDER BY TheDate, TheTime, WDName;
```

### Spool-Heavy Queries

```sql
SELECT UserName, QueryText, AmpCPUTime,
       SpoolUsage / 1e9 AS spool_gb,
       TotalIOCount, FinalWDID
FROM DBC.DBQLogTbl
WHERE LogDate = CURRENT_DATE
  AND SpoolUsage > 1e10  -- > 10 GB spool
ORDER BY SpoolUsage DESC
SAMPLE 20;
```

### Workload Arrivals and Completions

```sql
SELECT LogDate, WDName,
       Arrivals, Completions,
       AvgRespTime, MaxRespTime,
       AvgCPU, MaxCPU,
       SLGMet, SLGNotMet,
       DelayedCount, RejectedCount
FROM DBC.TDWMSummaryLog
WHERE LogDate >= CURRENT_DATE - 7
ORDER BY LogDate, WDName;
```

### TASM Event History

```sql
SELECT EventTime, EventType, EventName,
       OldState, NewState, Description
FROM DBC.TDWMEventLog
WHERE EventTime >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
ORDER BY EventTime DESC;
```
