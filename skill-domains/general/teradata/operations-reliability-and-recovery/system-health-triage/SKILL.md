---
name: teradata-system-admin
description: 'Teradata system administration including space management (PERM/SPOOL/TEMP), DBS Control settings, database hierarchy, session management, EXPLAIN plans, system monitoring (DBC views, ResUsage), backup/restore (ARC/DSA/BAR), reconfiguration, and performance diagnosis. Use when managing database space, interpreting EXPLAIN output, monitoring system health, configuring DBS Control parameters, managing sessions, or troubleshooting performance.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata System Administration

## When to Use

- Managing database/user space (PERM, SPOOL, TEMP)
- Interpreting EXPLAIN plans
- Monitoring system performance (ResUsage, DBQL)
- Configuring DBS Control parameters
- Managing user sessions
- Backup and restore operations
- Diagnosing and resolving performance issues

## Space Management

### Space Types

| Type | Description | Scope |
|---|---|---|
| **PERM** | Permanent data storage | Per database/user, inherited hierarchy |
| **SPOOL** | Temporary query workspace | Per user, borrowed from unused PERM |
| **TEMP** | Materialized volatile/global temp tables | Per user, borrowed from unused PERM |

### View Space Usage

```sql
-- Space by database
SELECT DatabaseName,
       SUM(CurrentPerm) / 1e9 AS perm_gb,
       SUM(MaxPerm) / 1e9 AS max_perm_gb,
       SUM(CurrentSpool) / 1e9 AS spool_gb,
       SUM(PeakSpool) / 1e9 AS peak_spool_gb,
       SUM(CurrentTemp) / 1e9 AS temp_gb
FROM DBC.DiskSpaceV
GROUP BY DatabaseName
ORDER BY perm_gb DESC;

-- Space by table
SELECT DatabaseName, TableName,
       SUM(CurrentPerm) / 1e6 AS perm_mb
FROM DBC.TableSizeV
WHERE DatabaseName = 'mydb'
GROUP BY DatabaseName, TableName
ORDER BY perm_mb DESC;

-- Space skew by AMP for a table
SELECT Vproc AS amp,
       CurrentPerm / 1e6 AS perm_mb
FROM DBC.TableSizeV
WHERE DatabaseName = 'mydb' AND TableName = 'orders'
ORDER BY perm_mb DESC;
```

### Manage Space

```sql
-- Increase database perm space
MODIFY DATABASE mydb AS PERM = 100e9;  -- 100 GB

-- Set user spool limit
MODIFY USER analyst AS SPOOL = 10e9;   -- 10 GB max spool

-- Give temp space
MODIFY USER etl_user AS TEMPORARY = 5e9;
```

## Database Hierarchy

```
DBC (system root)
├── SystemFE
├── SYSLIB
├── SYSUIF
└── user_dbs
    ├── prod_db (PERM = 500 GB)
    │   ├── staging (PERM = 100 GB)
    │   └── reporting (PERM = 50 GB)
    └── dev_db (PERM = 50 GB)
```

Space is hierarchical — child databases borrow unused PERM from parent.

```sql
-- Create database
CREATE DATABASE staging
FROM prod_db
AS PERM = 100e9
NO FALLBACK;

-- Create user under database
CREATE USER analyst
FROM prod_db
AS PERM = 1e9
PASSWORD = 'SecurePass'
SPOOL = 5e9;
```

## EXPLAIN Plans

```sql
EXPLAIN SELECT * FROM mydb.orders WHERE order_date = DATE '2025-06-15';
```

### Key EXPLAIN Indicators

| Indicator | Meaning |
|---|---|
| `single-AMP` | PI equality access — fastest |
| `all-AMPs` | Full table scan or NUSI |
| `by way of the primary index` | PI access |
| `by way of index #N` | Secondary index access |
| `product join` | Cartesian join — usually bad |
| `merge join` | Sorted merge — good for large joins |
| `hash join` | Hash redistribute — good |
| `spool` | Intermediate results materialized |
| `confidence level` | How confident optimizer is in estimates |
| `N partitions` | Number of partitions accessed |

### Force Statistics Check

```sql
DIAGNOSTIC HELPSTATS ON FOR SESSION;
-- Then run query — shows missing/recommended statistics
```

## Session Management

```sql
-- View active sessions
SELECT SessionNo, UserName, CurrentState, LogonDateTime,
       TotalCPUTime, TotalIOCount
FROM DBC.SessionInfoV
WHERE CurrentState <> 'IDLE'
ORDER BY TotalCPUTime DESC;

-- Abort a session
ABORT SESSION session_number;

-- View locks
SELECT DatabaseName, TableName, LockType, LockerUserName
FROM DBC.LockInfoV
ORDER BY DatabaseName, TableName;
```

## Key DBS Control Parameters

| Parameter | Group | Description |
|---|---|---|
| `MaxSpoolUsage` | System | Global spool limit |
| `DefaultDatabase` | System | Default database for new sessions |
| `FSGCacheSize` | Performance | File segment cache size |
| `NumStatisticsCacheSegs` | Performance | Statistics cache segments (2-200, default 4) |
| `ScriptMemLimit` | Performance | STO memory limit per AMP |
| `MaxLoadTasks` | Load | Max concurrent load jobs |

## System Monitoring Views

| View | Content |
|---|---|
| `DBC.ResUsageSPMA` | Per-node CPU, memory, I/O |
| `DBC.ResUsageSVPR` | Per-AMP resource usage |
| `DBC.ResUsageSPS` | Per-workload resource usage |
| `DBC.DBQLogTbl` | Per-query logging (CPU, I/O, spool, elapsed) |
| `DBC.SessionInfoV` | Active session info |
| `DBC.LockInfoV` | Current lock information |
| `DBC.DiskSpaceV` | Space usage by database |
| `DBC.AllSpaceV` | Comprehensive space view |
| `DBC.TableSizeV` | Table sizes by AMP |
| `DBC.AMPUsage` | AMP-level utilization |
| `DBC.LogOnOffV` | Logon/logoff history |

### Quick Health Check

```sql
-- CPU usage by node (recent)
SELECT TheDate, TheTime, NodeID,
       CPUUServ + CPUUExec AS cpu_busy_pct
FROM DBC.ResUsageSPMA
WHERE TheDate = CURRENT_DATE
ORDER BY TheDate DESC, TheTime DESC;

-- AMP with most I/O
SELECT Vproc, SUM(FileAcqs) AS total_io
FROM DBC.ResUsageSVPR
WHERE TheDate = CURRENT_DATE
GROUP BY Vproc
ORDER BY total_io DESC
SAMPLE 10;

-- Top queries by CPU today
SELECT TOP 10 UserName, QueryText,
       AmpCPUTime, TotalIOCount, SpoolUsage / 1e9 AS spool_gb
FROM DBC.DBQLogTbl
WHERE LogDate = CURRENT_DATE
ORDER BY AmpCPUTime DESC;
```

## Backup and Restore

### ARC (Archive/Restore)

```sql
-- Backup database
ARCHIVE DATA TABLES (mydb) ALL
FILE = backup_file;

-- Restore database
RESTORE DATA TABLES (mydb) ALL
FROM ARCHIVE FILE = backup_file;
```

### DSA (Disk Storage Architecture) / BAR

Modern backup using NetBackup, DD Boost, or native object storage.

## Common Administrative Tasks

```sql
-- Check Teradata version
SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'VERSION';

-- Check node configuration
SELECT * FROM DBC.ResUsageSPMA WHERE TheDate = CURRENT_DATE SAMPLE 1;

-- DBQL logging setup
BEGIN QUERY LOGGING ON ALL;
BEGIN QUERY LOGGING WITH OBJECTS, STATSUSAGE ON mydb;

-- End logging
END QUERY LOGGING ON ALL;
```

## Performance Diagnosis Checklist

1. **Check EXPLAIN** — look for product joins, all-AMP scans
2. **Check statistics** — `DIAGNOSTIC HELPSTATS ON FOR SESSION`
3. **Check data skew** — query `DBC.TableSizeV` by AMP
4. **Check spool usage** — `SpoolUsage` in DBQL
5. **Check locks** — `DBC.LockInfoV` for blocking
6. **Check AWT availability** — `ResUsageSPMA` for flow control
7. **Check CPU/IO balance** — `ResUsageSVPR` for hot AMPs

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-system-admin", path="references/FILENAME")` — do NOT call `list`.

Load these files for detailed technical reference on specific topics:

- **references/utility-commands-reference.md** — checktable (levels, error codes, remediation), vprocmanager (AMP state management, boot, restart), rcvmanager (recovery monitoring, OJ/CJ), rebuild (all modes: surgical, single table, full-AMP, many full-AMP), cnsrun/cnstool scripting, recovery concepts (clusters, fallback, journals), data recovery decision tree
- **references/crash-dump-reference.md** — ctl debug screen (dump parameters, selective dumps), csp crash dump save program (modes, list, save, clear, performance impact), crashdumps database setup (sizing formula, dump server requirements), pcl multi-node commands, dump verification utilities (logview, csppeek, dmptrace, checksums), crash dump offload/upload (get_cdump.sh, upload2gsc.pl, DUL)
- **references/space-management-reference.md** — SQL SHOWBLOCKS/SHOWWHERE macros (full syntax, display options, output columns), CLASS values, TableID decoding (subtable TAI values), TVS storage grades and temperature classification, Ferret vs SQL comparison, performance considerations
- **references/block-compression-reference.md** — BLC modes (MANUAL/AUTOTEMP/NEVER/ALWAYS), all DBS Control compression parameters (41 fields with defaults), Ferret COMPRESS/UNCOMPRESS/SHOWCOMPRESS commands, query bands for compression, TVS temperature-based compression (AutoTempComp), independent subtable control, compression ratios and CPU impact, ResUsage metrics, MVC vs ALC vs BLC comparison
