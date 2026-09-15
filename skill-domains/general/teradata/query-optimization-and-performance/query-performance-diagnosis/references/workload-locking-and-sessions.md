# Workload Management, Locking & Session Fundamentals

## Teradata Active System Management (TASM) — Performance Impact

### What TASM Does

TASM (also called TDWM — Teradata Dynamic Workload Management) controls:
- **Classification**: Which workload a query belongs to (by user, application, query band, target object)
- **Priority**: How much CPU/I/O time the query gets relative to others
- **Throttles**: Maximum concurrent queries per workload (excess queries delayed or rejected)
- **Filters**: Block specific query patterns entirely

### How TASM Affects Your Query

| TASM Control | User Symptom | Diagnosis |
|---|---|---|
| Low priority workload | Query runs slowly despite good plan | Check query band / workload assignment |
| Throttle delay | Query sits idle before starting | Look for delay time in DBQL |
| Filter/reject | Query returns error immediately | Check for abort/reject rules |
| Demotion | Query starts fast, then slows | Time-based demotion to lower priority |

### Stopping Runaway Queries

TASM provides mechanisms to prevent a single ad-hoc query from consuming all resources:

1. **Workload throttles**: Limit concurrent queries from ad-hoc users
   - Example: Ad-hoc workload limited to 5 concurrent — 6th query waits in delay queue
   
2. **Exception handling (system throttle abort)**:
   - Abort queries exceeding CPU/spool thresholds
   - Configured in Viewpoint Workload Designer
   
3. **Query Band tagging + classification**:
   ```sql
   SET QUERY_BAND = 'AppName=AdHocTool;Priority=Low;' FOR SESSION;
   -- TASM classifies to restricted workload based on query band
   ```

4. **Manual abort**: `ABORT SESSION <session-id>;` by DBA

### Diagnosing TASM Impact

```sql
-- Check what workload your query was classified to
SELECT QueryID, WDName, DelayTime, TotalFirstRespTime
FROM DBC.QryLogV
WHERE UserName = USER
ORDER BY StartTime DESC
SAMPLE 10;
-- If DelayTime > 0: your query was throttled (waited in delay queue)
-- If WDName = a low-priority workload: check classification rules

-- Find throttled queries system-wide
SELECT WDName, COUNT(*) AS throttled_cnt, AVG(DelayTime) AS avg_delay
FROM DBC.QryLogV
WHERE DelayTime > 0
  AND StartTime > CURRENT_TIMESTAMP - INTERVAL '1' DAY
GROUP BY WDName
ORDER BY avg_delay DESC;
```

---

## Locking — How It Blocks Queries

### Lock Levels (from most restrictive to least)

| Level | Allows Concurrent | Used By |
|---|---|---|
| **EXCLUSIVE** | Nothing else | DDL (ALTER, DROP), some utilities |
| **WRITE** | Other WRITE + READ (row-hash locks) | INSERT, UPDATE, DELETE |
| **READ** | Other READ | SELECT (default) |
| **ACCESS** | Everything | Dirty-read SELECT |

### Default Lock Behavior

- `SELECT` takes a **READ lock** on the table — blocks WRITE operations on same table
- `INSERT/UPDATE/DELETE` takes a **WRITE lock** — blocks other WRITE + can conflict with READ
- DDL takes an **EXCLUSIVE lock** — blocks everything

### Why a SELECT Blocks Your Load

A reporting SELECT takes a READ lock on the entire table (table-level). Your nightly INSERT/UPDATE needs a WRITE lock. The WRITE request waits for the READ to release.

**Fix: ACCESS lock for reporting queries**

```sql
-- Use ACCESS lock (dirty read) for reporting that doesn't need transactional consistency
LOCKING TABLE mydb.fact_table FOR ACCESS
SELECT region, SUM(sales) FROM mydb.fact_table GROUP BY region;
-- Does NOT block writers, does NOT wait for writers
-- Trade-off: may see partially committed rows
```

### Deadlock Diagnosis

A deadlock occurs when two sessions each hold a lock the other needs.

```sql
-- Find blocking sessions
SELECT BlockedQryId, BlockedSession, BlockingSession,
       LockType, LockedObject, LockStartTime
FROM DBC.LockConflictsV
WHERE BlockedQryId IS NOT NULL
ORDER BY LockStartTime DESC;

-- Alternative: check session status
SELECT SessionNo, UserName, CurrentState, LockWaitStartTime
FROM DBC.SessionInfoV
WHERE CurrentState = 'BLOCKED'
   OR CurrentState = 'DELAYED';

-- Historical deadlocks in DBQL
SELECT QueryID, AbortFlag, ErrorCode, ErrorText
FROM DBC.QryLogV
WHERE AbortFlag = 'Y'
  AND ErrorCode = 2631  -- Deadlock detected
  AND StartTime > CURRENT_TIMESTAMP - INTERVAL '1' DAY;
```

### Reducing Lock Contention

| Strategy | How |
|---|---|
| ACCESS locks for reads | `LOCKING TABLE ... FOR ACCESS SELECT ...` |
| Row-hash locks | Use PI-based WHERE (rowhash lock instead of table lock) |
| Shorter transactions | Commit frequently to release locks sooner |
| Load windows | Schedule heavy loads outside reporting hours |
| Read uncommitted | For dashboards that tolerate stale data |
| Partition-level locks | PPI tables can lock individual partitions |

---

## Session Modes — ANSI vs Teradata

### Key Differences

| Behavior | Teradata Mode | ANSI Mode |
|---|---|---|
| Implicit transactions | Each statement is auto-committed | Statements are in an open transaction until COMMIT |
| Case sensitivity (identifiers) | Case-insensitive | Case-sensitive (unless quoted) |
| Trailing spaces | Compared (PAD SPACE semantics) | Significant in some contexts |
| CREATE TABLE default | SET (no duplicate rows) | MULTISET (duplicates allowed) |
| Character comparison | Non-ANSI truncation rules | ANSI truncation rules |
| Implicit commit | After each statement | Only on explicit COMMIT |

### Performance Impact

| Scenario | Impact |
|---|---|
| ANSI mode implicit transactions | Locks held until COMMIT — longer lock hold times |
| Teradata mode auto-commit | Locks released after each statement — less contention |
| ANSI SET table default | Duplicate checking overhead on inserts |
| Mixed session modes in ETL | Unexpected behavior, debugging complexity |

### Checking Session Mode

```sql
-- Current session
SELECT SessionMode FROM DBC.SessionInfoV WHERE SessionNo = SESSION;
-- Returns 'TERADATA' or 'ANSI'
```

---

## Concurrency — Why More Sessions ≠ More Throughput

### The Saturation Point

Teradata parallelism is **AMP-level**. Each AMP has limited:
- CPU cycles
- I/O bandwidth
- Memory for spool
- Worker tasks (WTs)

Adding more concurrent sessions beyond saturation:
- Increases lock contention (more sessions competing for same tables)
- Increases spool consumption (each session needs spool space)
- Increases CPU context switching overhead
- Can trigger flow control (AMPs overwhelmed, PEs throttle submissions)

### Diagnosing Concurrency Issues

```sql
-- Check if flow control is active (AMP overload signal)
SELECT TheTime, NodeID, FlowCtlCount
FROM DBC.ResUsageSPMA
WHERE TheTime > CURRENT_TIMESTAMP - INTERVAL '1' HOUR
  AND FlowCtlCount > 0;

-- Check concurrent session count vs response time
SELECT EXTRACT(HOUR FROM StartTime) AS hr,
       COUNT(*) AS query_cnt,
       AVG(TotalFirstRespTime) AS avg_resp_sec
FROM DBC.QryLogV
WHERE StartTime > CURRENT_TIMESTAMP - INTERVAL '1' DAY
  AND StatementType = 'Select'
GROUP BY hr
ORDER BY hr;
```

### Optimal Concurrency Guidelines

| Workload Type | Suggested Concurrency per AMP |
|---|---|
| Complex analytics (full scans, big joins) | 1–2 |
| Mixed workload (reporting + tactical) | 3–5 |
| Tactical (sub-second, PI access) | 10–20 |
| Utility loads (FastLoad, TPump) | 1–3 per table |

Use TASM throttles to enforce these limits.

---

## Space Management — Finding Bloat

### Permanent Space Consumers

```sql
-- Top space consumers in a database
SELECT TableName, 
       SUM(CurrentPerm) AS total_perm_bytes,
       SUM(CurrentPerm) / 1024 / 1024 / 1024 AS perm_gb,
       SUM(PeakPerm) AS peak_bytes
FROM DBC.TableSizeV
WHERE DatabaseName = 'mydb'
GROUP BY TableName
ORDER BY total_perm_bytes DESC
SAMPLE 20;

-- Detect skew (uneven space across AMPs)
SELECT TableName,
       MAX(CurrentPerm) AS max_amp_bytes,
       AVG(CurrentPerm) AS avg_amp_bytes,
       (MAX(CurrentPerm) - AVG(CurrentPerm)) * 100.0 / NULLIFZERO(AVG(CurrentPerm)) AS skew_pct
FROM DBC.TableSizeV
WHERE DatabaseName = 'mydb'
GROUP BY TableName
HAVING skew_pct > 10
ORDER BY skew_pct DESC;
```

### Table Bloat Detection

Tables can bloat from:
- Deleted rows not reclaimed (transient journal holds space)
- Many small updates creating row fragments
- Cylinder migration leaving partially empty cylinders

```sql
-- Ratio of current rows to perm space (low ratio = bloat)
SELECT t.TableName,
       t.CurrentPerm / 1024 / 1024 AS perm_mb,
       (SELECT COUNT(*) FROM mydb.table_name) AS row_cnt,
       -- Estimated row size
       t.CurrentPerm / NULLIFZERO((SELECT COUNT(*) FROM mydb.table_name)) AS bytes_per_row
FROM DBC.TableSizeV t
WHERE t.DatabaseName = 'mydb' AND t.TableName = 'my_table'
GROUP BY t.TableName, t.CurrentPerm;
```

---

## DBQL-Based Table Usage Tracking

### Finding Unused Tables

```sql
-- Tables not queried in 90 days (candidates for archive)
SELECT t.DatabaseName, t.TableName, t.CreateTimeStamp,
       MAX(q.StartTime) AS last_accessed
FROM DBC.TablesV t
LEFT JOIN DBC.QryLogObjectsV q 
  ON t.DatabaseName = q.ObjectDatabaseName 
  AND t.TableName = q.ObjectTableName
WHERE t.DatabaseName = 'mydb'
  AND t.TableKind = 'T'
GROUP BY t.DatabaseName, t.TableName, t.CreateTimeStamp
HAVING last_accessed IS NULL 
   OR last_accessed < CURRENT_TIMESTAMP - INTERVAL '90' DAY
ORDER BY t.CreateTimeStamp;
```
