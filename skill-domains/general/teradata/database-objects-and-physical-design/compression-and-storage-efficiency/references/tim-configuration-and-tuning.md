# TIM Configuration and Tuning

## Architecture Deep Dive

### Component Interaction

Teradata Intelligent Memory operates through three cooperating subsystems:

1. **Database Software (Filesystem)** — Manages variable-sized data blocks within fixed-size cylinders (~12 MB). The filesystem spawns a preload process after restart to fill VH cache.
2. **TVS (Teradata Virtual Storage)** — Collects I/O metrics per cylinder, calculates temperatures, and produces the sorted VH candidate list. Starting in 14.10, both physical disk reads and FSG cache hits count toward temperature.
3. **PDE (Parallel Database Extensions)** — Owns FSG cache memory. Splits total FSG into LRU pool and VH pool. Communicates VH cache capacity to TVS, receives the candidate list, and manages data block placement.

> Source: 541-0009920, Section 2 — Architecture

### Cylinder Promotion into VH Cache

The promotion workflow:

1. PDE tells TVS how much memory per AMP is available for VH cache.
2. TVS generates a candidate list containing the hottest perm cylinders for that AMP, sized larger than VH cache to account for partially filled cylinders.
3. When a permanent data block is read from physical disk, PDE checks whether its cylinder is on the VH candidate list.
4. If the cylinder is on the list **and** hotter than the coldest cylinder currently in VH cache, the data block is placed in VH cache.
5. The data block remains in VH cache until replaced by a hotter block or deleted by normal user activity.

### Demotion (Aging Out)

Data blocks are aged out of VH cache when:

- A hotter cylinder needs the space (temperature-based replacement).
- The underlying data is deleted from the database.
- The VH candidate list is refreshed and the cylinder no longer qualifies.
- The table is dropped.

There is **no direct transfer** between VH cache and LRU cache in Teradata 14.10. If VH data cools and loses its candidate status, it must be aged out, read again from disk, and then placed into LRU cache. The reverse is also true.

> Source: 541-0009920, Section 6.2

### VH Cache Preload After Restart

FSG cache contents survive a normal database restart. However, after a cold start or maintenance-induced restart:

1. The system reaches "logons enabled" state.
2. The filesystem spawns a background process that preloads all data blocks from VH candidate cylinders into VH cache.
3. This ensures applications hit the ground running with hot data already in memory.

Controlled by two `dbscontrol` settings in the storage fields:

| Setting | Default | Effect |
|---|---|---|
| `TIMCacheLoadDisabled` | FALSE | Set TRUE to skip preload entirely |
| `TIMCacheLoadThrottle` | FALSE | Set TRUE to throttle preload I/O and avoid saturating the storage subsystem |

> Source: 541-0009920, Section 6.3

## DBS Control Settings

### TIM FSG Cache Percent

Controls the percentage of total FSG cache allocated to VH cache. Set via the Control GDO Editor:

```
ctl
> screen dbs

(0) Minimum Node Action:        Clique-Down
(1) Minimum Nodes Per Clique:   1               (2) FSG Cache Percent:  90
(3) Clique Failure:             Clique-Down     (4) Cylinder Read:      On
(5) Restart After DAPowerFail:  On              (6) Cylinder Read Ageing Threshold:  0
(7) Maximum Fatal AMPs:         0               (8) TIM FSG Cache Percent:    50
```

To change:

```
> 8 = 30
> wr
CTL: Control GDO successfully written.
Warning: A change has been made to one or more fields
         that has a deferred effect.
         TPA reset must be performed so that those changes can take effect.
```

**Recommendation:** Start at the default 50%. Teradata Labs testing found that changing allocation by even 10–20% can cause dramatic performance shifts. If unsure, start at 10–20% and work up while monitoring DBQL and ResUsage.

> Source: 541-0009920, Sections 6.2, FAQ

### DBSCacheThr

The optimizer applies `DBSCacheThr` as a percentage of **total** FSG cache (LRU + VH) to determine whether a table is eligible for caching. When VH cache is enabled:

- The effective threshold for LRU-eligible objects (spool, volatile, temp, cold perm) is inflated because total FSG includes VH memory.
- Consider reducing `DBSCacheThr` proportionally.

**Example:** If `DBSCacheThr = 10` and you allocate 50% to VH cache, reduce `DBSCacheThr` to 5 to maintain the same effective LRU threshold.

**Recommendation:** Leave existing settings as-is initially. Revisit only if DBQL or ResUsage show reduced cache effectiveness impacting non-VH workloads.

> Source: 541-0009920, Section 3.4

### FSG Cache Per AMP

Check current FSG cache allocation per AMP using the `ctl` utility:

```
ctl
> screen hardware
```

This displays the amount of FSG cache available per AMP in kilobytes. Minimum requirements:

| Platform | Min FSG Cache / AMP |
|---|---|
| Active EDW 6000-series | 8 GB |
| Data Warehouse Appliance 2000-series | 5 GB |

> Source: 541-0009920, Section 3.1

### Migration I/O Collect Period

Controls how frequently TVS updates the VH candidate list and notifies PDE. Set via TVS screen in `ctl`:

```
ctl
> scr tvs

(A) Migration I/O Collect Period                :   100 sec
```

To change:

```
> a = 300
> wr
```

**Default:** 100 seconds. This means up to 100 seconds may elapse between when TVS recognizes a cylinder as VERY HOT and when PDE allows it into VH cache.

**Recommendation:** Leave at default to balance near real-time updates with the overhead of maintaining the VH list.

> Source: 541-0009920, Section 6.1

## Configuration Workflow

### Step 1: Assess Workload Suitability

Before enabling TIM, confirm:

1. **I/O is the bottleneck** — Review `ResUsageSPMA` for physical I/O approaching rated capacity.
2. **CPU capacity is available** — Check `PercentCPUBusy`; TIM shifts I/O wait time to CPU processing time.
3. **Target workload performs significant perm I/O** — Use DBQL to identify workloads with high `ReqPhysIO` and `ReqPhysIOKB`.

```sql
-- Identify I/O-heavy workloads from DBQL
SELECT UserName
      ,COUNT(*) AS QueryCount
      ,SUM(ReqPhysIOKB) / 1024.0 / 1024.0 AS PhysIOGB
      ,AVG(AMPCPUTime) AS AvgCPU
FROM  DBC.DBQLogTbl
WHERE StartTime >= CURRENT_DATE - 7
GROUP BY 1
ORDER BY PhysIOGB DESC;
```

### Step 2: Enable TIM

Contact Teradata Support to enable the feature. Once enabled, TIM defaults to 50% of FSG cache for VH.

### Step 3: Monitor Initial Behavior

After enabling, monitor for at least one full workload cycle:

```sql
-- VH cache utilization per node
SELECT SPMA.TheDate
      ,SPMA.TheTime / 10 * 10 (FORMAT '99:99:99') AS LogTime
      ,SPMA.NodeID
      ,SPMA.Spare10 / 1024.0 (FORMAT 'z,zzz,zzz') AS VHCacheSizeMB
      ,SUM(SVPR.Spare07) / 1024.0 (FORMAT 'z,zzz,zzz') AS VHCacheInUseMB
      ,SUM(SVPR.Spare01) / 1024.0 (FORMAT 'z,zzz,zzz') AS VHAgedMB
FROM  DBC.ResUsageSVPR SVPR
INNER JOIN DBC.ResUsageSPMA SPMA
  ON  SVPR.TheDate = SPMA.TheDate
 AND  SVPR.TheTime = SPMA.TheTime
 AND  SVPR.NodeID  = SPMA.NodeID
WHERE SPMA.TheDate = DATE
GROUP BY 1,2,3,4
ORDER BY 1,2,3;
```

> Source: 541-0009920, Appendix B — ResUsage Query #3

### Step 4: Tune Allocation

- If VH cache utilization is consistently low (<50%), reduce `TIM FSG Cache Percent` to return memory to LRU cache.
- If VH cache is full and data is being aged aggressively, consider increasing allocation or adding physical memory.
- If non-VH workloads show degraded cache effectiveness, review `DBSCacheThr`.

### Step 5: Evaluate Results

Compare before/after using DBQL request-level data:

```sql
-- Compare physical I/O before and after TIM
SELECT UserName
      ,RequestNum
      ,CAST(EXTRACT(HOUR FROM (FirstRespTime - StartTime) HOUR(2) TO SECOND(2)) * 3600
           + EXTRACT(MINUTE FROM (FirstRespTime - StartTime) HOUR(2) TO SECOND(2)) * 60
           + EXTRACT(SECOND FROM (FirstRespTime - StartTime) HOUR(2) TO SECOND(2))
       AS DECIMAL(10,2)) AS ElapsedTime
      ,TotalIOCount
      ,ReqPhysIO
      ,ReqPhysIOKB
      ,ExtraField33 AS VHLogicalIO
      ,ExtraField36 AS VHLogicalIOKB
      ,ZEROIFNULL((ReqIOKB - ReqPhysIOKB) / NULLIFZERO(ReqIOKB) * 100)
       (FORMAT 'ZZ9.9') AS CacheEffKB
FROM  DBC.DBQLogTbl
WHERE StartTime BETWEEN <before_start> AND <before_end>
  AND UserName = '<target_user>'
ORDER BY StartTime, RequestNum;
```

> Source: 541-0009920, Appendix A — DBQL Query #1

## Monitoring Queries

### DBQL Step-Level TIM Metrics

```sql
SELECT RequestNum
      ,StepLev1Num
      ,StepLev2Num
      ,StepName
      ,CPUTime
      ,IOCount
      ,ExtraField13                AS StepIOKB
      ,ExtraField29                AS StepPhysIO
      ,ExtraField30                AS StepPhysIOKB
      ,ExtraField5                 AS VHLogicalIO
      ,ExtraField27                AS VHLogicalIOKB
      ,ExtraField26                AS VHPhysIO
      ,ExtraField28                AS VHPhysIOKB
      ,ZEROIFNULL((StepIOKB - StepPhysIOKB) / NULLIFZERO(StepIOKB) * 100)
       (FORMAT 'ZZ9.9')           AS CacheEffKB
      ,ZEROIFNULL(VHLogicalIO / NULLIFZERO(IOCount) * 100)
       (FORMAT 'ZZ9.9')           AS VHPercentOfLogIO
      ,ZEROIFNULL(VHPhysIO / NULLIFZERO(VHLogicalIO) * 100)
       (FORMAT 'ZZ9.9')           AS VHCacheMissRate
FROM  DBC.DBQLStepTbl STPTBL
WHERE <date_and_user_filters>
ORDER BY RequestNum, StepLev1Num, StepLev2Num;
```

> Source: 541-0009920, Appendix A — DBQL Query #2

### Node-Level CPU and I/O with VH Metrics

```sql
SELECT TheDate (FORMAT 'yyyy-mm-dd') AS LogDate
      ,CAST(TheTime AS INT) / 10 * 10 (FORMAT '99:99:99') AS LogTime
      ,NodeID
      ,SUM(CPUUServPart09 + CPUUServPart10 + CPUUServPart11 + CPUUServPart12
         + CPUUServPart31 + CPUUServPart32) AS CPUUServ
      ,SUM(CPUUExecPart09 + CPUUExecPart10 + CPUUExecPart11 + CPUUExecPart12
         + CPUUExecPart13 + CPUUExecPart31 + CPUUExecPart32) AS CPUUExec
      ,(CPUUExec + CPUUServ) / NCPUs / Secs AS PercentCPUBusy
      ,SUM(FilePDbAcqKB + FilePCiAcqKB) / 1024.0 / Secs AS LogicalPermReadMBSec
      ,SUM(FilePDbPreReadKB + FilePCiPreReadKB
         + FilePDbAcqReadKB + FilePCiAcqReadKB) / 1024.0 / Secs AS PhysPermReadMBSec
      ,SUM(Spare02) / Secs          AS VHLogicalReadsSec
      ,SUM(Spare03) / 1024.0 / Secs AS VHLogicalReadMBSec
      ,SUM(Spare04) / Secs          AS VHPhysReadsSec
      ,SUM(Spare05) / 1024.0 / Secs AS VHPhysReadMBSec
      ,ZEROIFNULL((LogicalPermReadMBSec - PhysPermReadMBSec)
       / NULLIFZERO(LogicalPermReadMBSec) * 100) (FORMAT 'ZZ9.9') AS PermCacheEffMB
FROM  DBC.ResUsageSVPR
WHERE TheDate = DATE
  AND VprType = 'AMP'
GROUP BY 1,2,3,NCPUs,Secs
ORDER BY 1,2,3;
```

> Source: 541-0009920, Appendix B — ResUsage Query #1

### Workload-Level VH Metrics

```sql
SELECT TheDate (FORMAT 'yyyy-mm-dd') AS LogDate
      ,CAST(TheTime AS INT) / 10 * 10 (FORMAT '99:99:99') AS LogTime
      ,NodeID
      ,RuleName
      ,SUM(FilePDbAcqKB + FilePCiAcqKB) / 1024.0 / Secs AS LogPermReadMBSec
      ,SUM(FilePDbPreReadKB + FilePCiPreReadKB
         + FilePDbAcqReadKB + FilePCiAcqReadKB) / 1024.0 / Secs AS PhysPermReadMBSec
      ,SUM(Spare11) / Secs            AS VHLogReadsSec
      ,SUM(Spare12) / 1024.0 / Secs   AS VHLogReadMBSec
      ,SUM(Spare13) / Secs            AS VHPhysReadsSec
      ,SUM(Spare14) / 1024.0 / Secs   AS VHPhysReadMBSec
FROM  DBC.ResUsageSPS SPS
INNER JOIN TDWM.RuleDefs RULES
  ON  SPS.WDid = RULES.RuleId
WHERE TheDate = DATE
GROUP BY 1,2,3,4,Secs
ORDER BY 1,2,3,4;
```

> Source: 541-0009920, Appendix B — ResUsage Query #2

### Data Temperature Report

Requires the heatmap UDF and view (see Appendix D of the source). Once installed:

```sql
-- All objects with VH candidate/cache status
SELECT DatabaseName
      ,TableName
      ,StartTableIdTypeAndIndex
      ,Temperature
      ,NormalizedTempInfo
      ,VeryHotCandidate
      ,VeryHotCache
      ,PercentFull
FROM  TD1410_HEATMAP_V
ORDER BY Temperature DESC;

-- Only VH candidates
SELECT DatabaseName
      ,TableName
      ,Temperature
      ,NormalizedTempInfo
      ,VeryHotCandidate
      ,VeryHotCache
      ,PercentFull
FROM  TD1410_HEATMAP_V
WHERE VeryHotCandidate = 'Y'
ORDER BY Temperature DESC;
```

> Source: 541-0009920, Sections 4.3, Appendix C–D

### Ferret SHOWWHERE

The Ferret `SHOWWHERE` command shows cylinder temperature and physical placement, including a `VH` column indicating the percentage of cylinders on the VH candidate list:

```
ferret
> scope table <dbname>.<tablename>
> showwhere
```

> Source: 541-0009920, Section 4.4

## ResUsage and DBQL Column Reference

### ResUsage Columns (14.10 Spare Fields)

| Table | Metric | Column | Type | Description |
|---|---|---|---|---|
| SPMA | VHCacheKB | Spare10 | Float | VH cache size per node (KB) |
| SVPR | VHAgedOut | Spare00 | Float | Count of segments aged out of VH cache |
| SVPR | VHAgedOutKB | Spare01 | Float | Volume (KB) aged out of VH cache |
| SVPR | VHAcqs | Spare02 | Float | Logical read count from VH cache |
| SVPR | VHAcqKB | Spare03 | Float | Logical read volume (KB) from VH cache |
| SVPR | VHAcqReads | Spare04 | Float | Physical reads due to VH cache miss |
| SVPR | VHAcqReadKB | Spare05 | Float | Physical read volume (KB) on VH miss |
| SVPR | VHCacheInUseKB | Spare07 | Float | VH cache currently in use (KB) |
| SPS | VHAcqs | Spare11 | Float | Logical VH reads per workload |
| SPS | VHAcqKB | Spare12 | Float | Logical VH volume (KB) per workload |
| SPS | VHAcqReads | Spare13 | Float | Physical reads on VH miss per workload |
| SPS | VHAcqReadKB | Spare14 | Float | Physical read volume (KB) on VH miss per workload |

### DBQL Columns (14.10 ExtraField)

| Table | Metric | Column | Description |
|---|---|---|---|
| DBQLogTbl | VHLogicalIO | ExtraField33 | VH logical I/O count per request |
| DBQLogTbl | VHPhysIO | ExtraField34 | VH physical I/O count per request |
| DBQLogTbl | VHLogicalIOKB | ExtraField36 | VH logical I/O KB per request |
| DBQLogTbl | VHPhysIOKB | ExtraField37 | VH physical I/O KB per request |
| DBQLStepTbl | VHLogicalIO | ExtraField5 | VH logical I/O count per step |
| DBQLStepTbl | VHPhysIO | ExtraField26 | VH physical I/O count per step |
| DBQLStepTbl | VHLogicalIOKB | ExtraField27 | VH logical I/O KB per step |
| DBQLStepTbl | VHPhysIOKB | ExtraField28 | VH physical I/O KB per step |

> Source: 541-0009920, Appendix E

## Memory Fragmentation and Data Block Sizing

VH cache memory can become fragmented when data blocks do not fit evenly into contiguous cache structures. Optimal data block sizes are **powers of 2** (64 KB, 128 KB, etc.).

| Block Size | VH Cache Utilization |
|---|---|
| 97 KB | ~78% |
| 127 KB | ~96% |

On a mature system, expect 20–30% fragmentation loss. To reblock a table:

```sql
ALTER TABLE dbname.tablename, DATABLOCKSIZE=127KILOBYTES IMMEDIATE;
```

**Caution:** The table is locked until the ALTER completes and the operation cannot be interrupted. Data blocks may be smaller than specified if Block Level Compression (BLC) is in use. Use Ferret `SHOWBLOCKS` to check actual block sizes.

> Source: 541-0009920, Section 5
