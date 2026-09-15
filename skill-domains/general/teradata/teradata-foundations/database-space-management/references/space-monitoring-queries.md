# Space Monitoring Queries — Complete Reference

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 13

## System-Wide Space Overview

### Total System Space

```sql
SELECT
    SUM(MaxPerm) / 1e12 AS total_perm_tb,
    SUM(CurrentPerm) / 1e12 AS used_perm_tb,
    (SUM(MaxPerm) - SUM(CurrentPerm)) / 1e12 AS free_perm_tb,
    CAST(SUM(CurrentPerm) AS FLOAT) / NULLIFZERO(SUM(MaxPerm)) * 100 AS pct_used
FROM DBC.DiskSpaceV;
```

### Space by AMP

```sql
SELECT Vproc AS amp_id,
       SUM(MaxPerm) / 1e9 AS max_perm_gb,
       SUM(CurrentPerm) / 1e9 AS used_perm_gb,
       SUM(CurrentSpool) / 1e9 AS current_spool_gb,
       SUM(CurrentTemp) / 1e9 AS current_temp_gb
FROM DBC.DiskSpaceV
GROUP BY Vproc
ORDER BY used_perm_gb DESC;
```

### AMP Skew (Data Distribution)

```sql
SELECT
    MAX(amp_perm) / NULLIFZERO(AVG(amp_perm)) AS skew_factor,
    MAX(amp_perm) / 1e9 AS max_amp_gb,
    MIN(amp_perm) / 1e9 AS min_amp_gb,
    AVG(amp_perm) / 1e9 AS avg_amp_gb
FROM (
    SELECT Vproc, SUM(CurrentPerm) AS amp_perm
    FROM DBC.DiskSpaceV
    GROUP BY Vproc
) amp_summary;
```

## Database-Level Monitoring

### Top 20 Databases by Space Used

```sql
SELECT TOP 20
    DatabaseName,
    SUM(MaxPerm) / 1e9 AS max_gb,
    SUM(CurrentPerm) / 1e9 AS used_gb,
    (SUM(MaxPerm) - SUM(CurrentPerm)) / 1e9 AS free_gb,
    CAST(SUM(CurrentPerm) AS FLOAT) / NULLIFZERO(SUM(MaxPerm)) * 100 AS pct_used
FROM DBC.DiskSpaceV
GROUP BY DatabaseName
HAVING SUM(MaxPerm) > 0
ORDER BY used_gb DESC;
```

### Databases with Most Free Space (Candidates for Reclamation)

```sql
SELECT DatabaseName,
       SUM(MaxPerm) / 1e9 AS allocated_gb,
       SUM(CurrentPerm) / 1e9 AS used_gb,
       (SUM(MaxPerm) - SUM(CurrentPerm)) / 1e9 AS wasted_gb,
       CAST(SUM(CurrentPerm) AS FLOAT) / NULLIFZERO(SUM(MaxPerm)) * 100 AS utilization_pct
FROM DBC.DiskSpaceV
GROUP BY DatabaseName
HAVING (SUM(MaxPerm) - SUM(CurrentPerm)) / 1e9 > 10  -- > 10 GB wasted
ORDER BY wasted_gb DESC;
```

### Database Hierarchy with Space Roll-Up

```sql
SELECT d.DatabaseName,
       d.OwnerName,
       d.PermSpace / 1e9 AS allocated_gb,
       COALESCE(s.used_gb, 0) AS used_gb,
       d.SpoolSpace / 1e9 AS spool_limit_gb,
       d.TempSpace / 1e9 AS temp_limit_gb
FROM DBC.DatabasesV d
LEFT JOIN (
    SELECT DatabaseName, SUM(CurrentPerm) / 1e9 AS used_gb
    FROM DBC.DiskSpaceV
    GROUP BY DatabaseName
) s ON d.DatabaseName = s.DatabaseName
WHERE d.OwnerName = 'DBC'  -- Top-level databases
ORDER BY d.DatabaseName;
```

## Table-Level Monitoring

### Top 20 Tables by Space

```sql
SELECT TOP 20
    DatabaseName, TableName,
    SUM(CurrentPerm) / 1e9 AS perm_gb,
    SUM(PeakPerm) / 1e9 AS peak_gb,
    MAX(RowCount) AS est_row_count
FROM DBC.TableSizeV
GROUP BY DatabaseName, TableName
ORDER BY perm_gb DESC;
```

### Table Space with Row Counts

```sql
SELECT t.DatabaseName, t.TableName, t.TableKind,
       s.perm_mb,
       t.RowCount AS row_count_estimate,
       CASE WHEN t.RowCount > 0
            THEN s.perm_mb * 1e6 / t.RowCount
            ELSE 0 END AS avg_row_bytes
FROM DBC.TablesV t
JOIN (
    SELECT DatabaseName, TableName,
           SUM(CurrentPerm) / 1e6 AS perm_mb
    FROM DBC.TableSizeV
    GROUP BY DatabaseName, TableName
) s ON t.DatabaseName = s.DatabaseName AND t.TableName = s.TableName
WHERE t.DatabaseName = 'mydb'
  AND t.TableKind IN ('T', 'O')  -- Tables only
ORDER BY s.perm_mb DESC;
```

### Table Skew Analysis

```sql
SELECT DatabaseName, TableName,
       MAX(CurrentPerm) AS max_amp_bytes,
       MIN(CurrentPerm) AS min_amp_bytes,
       AVG(CurrentPerm) AS avg_amp_bytes,
       CASE WHEN AVG(CurrentPerm) > 0
            THEN MAX(CurrentPerm) / AVG(CurrentPerm)
            ELSE 0 END AS skew_factor
FROM DBC.TableSizeV
WHERE DatabaseName = 'mydb'
  AND TableName = 'large_table'
GROUP BY DatabaseName, TableName;
```

## Spool Space Monitoring

### Current Spool Consumers

```sql
SELECT SessionNo, UserName, CurrentSpool / 1e9 AS spool_gb
FROM DBC.SessionInfoV
WHERE CurrentSpool > 0
ORDER BY CurrentSpool DESC;
```

### Historical Spool Usage (from DBQL)

```sql
SELECT UserName,
       MAX(SpoolUsage) / 1e9 AS max_spool_gb,
       AVG(SpoolUsage) / 1e9 AS avg_spool_gb,
       COUNT(*) AS query_count
FROM DBC.DBQLogTbl
WHERE StartTime > CURRENT_DATE - 7
  AND SpoolUsage > 1e9
GROUP BY UserName
ORDER BY max_spool_gb DESC;
```

## Capacity Planning

### Space Growth Rate

```sql
-- Requires historical snapshots (store daily in a tracking table)
-- Example assuming a space_history table exists:
SELECT snapshot_date, database_name,
       used_perm_gb,
       used_perm_gb - LAG(used_perm_gb) OVER (
           PARTITION BY database_name ORDER BY snapshot_date
       ) AS daily_growth_gb
FROM space_tracking.daily_snapshots
WHERE database_name = 'production_db'
  AND snapshot_date > CURRENT_DATE - 30
ORDER BY snapshot_date;
```

### Projected Days Until Full

```sql
-- Based on average daily growth
WITH growth AS (
    SELECT DatabaseName,
           SUM(MaxPerm) AS max_bytes,
           SUM(CurrentPerm) AS current_bytes,
           -- Estimate daily growth (would need historical data in practice)
           SUM(CurrentPerm) * 0.005 AS est_daily_growth  -- ~0.5% per day estimate
    FROM DBC.DiskSpaceV
    GROUP BY DatabaseName
    HAVING SUM(MaxPerm) > 1e9
)
SELECT DatabaseName,
       max_bytes / 1e9 AS max_gb,
       current_bytes / 1e9 AS used_gb,
       (max_bytes - current_bytes) / 1e9 AS free_gb,
       CASE WHEN est_daily_growth > 0
            THEN CAST((max_bytes - current_bytes) / est_daily_growth AS INTEGER)
            ELSE 9999 END AS days_until_full
FROM growth
ORDER BY days_until_full ASC;
```

## Alerting Patterns

### Databases Over Threshold

```sql
-- Use as a periodic check (e.g., daily macro or scheduled query)
SELECT DatabaseName,
       SUM(MaxPerm) / 1e9 AS max_gb,
       SUM(CurrentPerm) / 1e9 AS used_gb,
       CAST(SUM(CurrentPerm) AS FLOAT) / NULLIFZERO(SUM(MaxPerm)) * 100 AS pct_full,
       CASE
           WHEN CAST(SUM(CurrentPerm) AS FLOAT) / NULLIFZERO(SUM(MaxPerm)) * 100 > 95 THEN 'CRITICAL'
           WHEN CAST(SUM(CurrentPerm) AS FLOAT) / NULLIFZERO(SUM(MaxPerm)) * 100 > 85 THEN 'WARNING'
           WHEN CAST(SUM(CurrentPerm) AS FLOAT) / NULLIFZERO(SUM(MaxPerm)) * 100 > 75 THEN 'ATTENTION'
           ELSE 'OK'
       END AS status
FROM DBC.DiskSpaceV
GROUP BY DatabaseName
HAVING CAST(SUM(CurrentPerm) AS FLOAT) / NULLIFZERO(SUM(MaxPerm)) * 100 > 75
   AND SUM(MaxPerm) > 1e9
ORDER BY pct_full DESC;
```

## Space Reclamation

### Identify and Clean Stale Tables

```sql
-- Tables not accessed in 90+ days (requires DBQL WITH OBJECTS)
SELECT o.ObjectDatabaseName, o.ObjectTableName,
       ts.perm_mb,
       MAX(o.CollectTimeStamp) AS last_accessed
FROM DBC.DBQLObjTbl o
JOIN (
    SELECT DatabaseName, TableName, SUM(CurrentPerm) / 1e6 AS perm_mb
    FROM DBC.TableSizeV
    GROUP BY DatabaseName, TableName
    HAVING SUM(CurrentPerm) > 100e6  -- > 100 MB
) ts ON o.ObjectDatabaseName = ts.DatabaseName AND o.ObjectTableName = ts.TableName
GROUP BY 1, 2, 3
HAVING MAX(o.CollectTimeStamp) < CURRENT_DATE - 90
ORDER BY ts.perm_mb DESC;
```

### Release Unused Allocated Space

```sql
-- Reduce over-allocated database to actual usage + 20% buffer
-- First check current usage:
SELECT DatabaseName,
       SUM(MaxPerm) / 1e9 AS allocated_gb,
       SUM(CurrentPerm) / 1e9 AS used_gb
FROM DBC.DiskSpaceV
WHERE DatabaseName = 'over_allocated_db'
GROUP BY DatabaseName;

-- Then modify (returns freed space to parent):
MODIFY DATABASE over_allocated_db AS PERM = 6e9;  -- reduce to actual need + buffer
```
