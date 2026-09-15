# Hard Limits and Capacity on Demand — Complete Reference

## Hard Limit Hierarchy

Three levels of hard limits can be applied independently or combined:

```
Level 1: System (WM COD)
  └── Limits entire Tdat control group — ALL user work
      Level 2: Virtual Partition
        └── Limits all workloads within one VP
            Level 3: Workload
              └── Limits one SLG Tier workload
```

- **Only SLG Tier workloads** support workload-level hard limits
- Tactical: too lightweight to need limits; automatically exempt
- Timeshare: hard limits not supported (use SLG Tier for hard-limit capability)

## WM COD (Workload Management Capacity on Demand)

System-level hard limit that restricts the total CPU and I/O available to ALL database work.

### Use Cases

- Purchased hardware with future growth planned — initially restrict to purchased capacity
- Contract-based resource restrictions with Teradata
- Gradually ramp up capacity as workloads grow

### Configuration in Viewpoint Workload Designer

Set in the Partition Resources tab:

```
WM COD = 80%
  → All database work limited to 80% of total CPU and I/O capacity
  → Remaining 20% is effectively idle from the database perspective
```

### CPU Enforcement (16.20 FU2+)

**New approach (16.20 Feature Update 2):** Enforcement by PDE layer, not operating system.

Key improvements over SLES 11 OS-based enforcement:

| Feature | Old Approach | New Approach (16.20 FU2) |
|---|---|---|
| Throttle scope | Entire Tdat control group | Individual tasks |
| Internal resource locks | Tasks holding locks were throttled | Tasks holding contended locks run freely |
| PDE system calls | Throttled | Never throttled |
| System workload (WDID 255) | Subject to limits | Always runs uninhibited |
| Rollback tasks | Always throttled | Optional: can be excluded |
| Enforcement point | Tdat control group | Internal VP level and below |

### Enforcement Mechanics

Both old and new use the same fundamental approach:

```
Enforcement Period: A prescribed slice of wall clock time
Quota: The % of the period where work can run on each CPU

Example: WM COD = 75%, Enforcement Period = 1 second
  → Work can run for 0.75 seconds of each 1-second period
  → 0.25 seconds of enforced idle time per period per CPU
```

### Smart Task Selection (New Approach)

When the quota is reached within an enforcement period:
1. Tasks holding contended internal resources → **NOT throttled** (run to release lock)
2. Tasks making PDE system calls (DBQL/ResUsage logging) → **NOT throttled**
3. Tasks in System workload (WDID 255) → **NEVER throttled**
4. Rollback tasks → optionally NOT throttled (configurable)
5. All other tasks → **throttled to compensate** (may be throttled more to maintain limit)

### Impact on Tactical Work

- Tactical requests ARE under WM COD control
- New approach: tactical queries get CPU immediately due to high weight; lower-priority tasks holding internal locks run just long enough to release them
- Old approach: all tasks under Tdat were equally delayed, causing tactical queries to wait for locks held by throttled low-priority tasks

### Non-Database CPU Adjustment

WM COD limits **database CPU only**, but system also has non-database CPU (PDE, OS, monitoring):

```
Problem: WM COD = 80% but non-DB CPU uses 10%
  → Database work gets 80% of total CPU
  → But actual total consumed = 80% + 10% = 90%
  → Effective user experience: only 80% capacity

Must-Do Adjustment:
  WM COD = Desired_Limit + Non_DB_CPU_Delta

Example: Want 70% usable capacity, non-DB CPU = 10%
  → Set WM COD = 80% (70% + 10%)
```

### Determining Non-Database CPU Delta

**Approach 1: ResUsage Method**

```sql
-- Find non-database CPU percentage
SELECT TheDate, TheTime,
       NodeCPU AS total_cpu,
       DBSCPUUsage AS db_cpu,
       (NodeCPU - DBSCPUUsage) AS non_db_cpu_pct
FROM DBC.ResUsageSPMA
WHERE TheDate = CURRENT_DATE
ORDER BY TheDate, TheTime;
```

**Approach 2: Direct Measurement**

Run workloads at various WM COD settings and compare total Node CPU vs Database CPU in ResUsage. The delta is the non-database overhead.

## I/O COD

### Implementation

I/O limits use the TDMeter module per disk:

```
I/O COD enforces a bandwidth-based limit per disk
  → Uses I/O token allocations (IOTAs) as the metric
  → Physical I/O measured by bandwidth, not count
```

### Behavior

- I/O COD operates independently from CPU COD
- Both use the same WM COD percentage setting
- I/O enforcement is per disk device via TDMeter
- Proportional reduction: if WM COD = 80%, each disk gets 80% of its bandwidth capacity

## Virtual Partition Hard Limits

Convert a VP from dynamic to fixed allocation:

| Mode | Without Hard Limit | With Hard Limit |
|---|---|---|
| Dynamic | VP can exceed allocation when siblings idle | — |
| Fixed | — | VP NEVER exceeds its allocation percentage |

### Configuration

Set in Workload Designer → Partition Resources tab:
- Check "Hard Limit" next to the VP allocation percentage
- The allocation percentage becomes the upper bound

### VP Limits + WM COD

When combined, the VP limit applies within the WM COD envelope:

```
WM COD = 80%, VP Allocation = 50% (fixed)

Effective VP limit = 50% of 80% = 40% of total system
  → VP can never use more than 40% of total system resources
  → Remaining 40% available to other VPs (up to WM COD limit)
```

## Workload Hard Limits

Apply a cap on an individual SLG Tier workload's resource consumption.

### How to Set

In Workload Designer → Workload Resource Allocation screen:
1. Select the SLG Tier workload
2. Check "Hard Limit"
3. The workload's allocation percentage becomes an upper bound

### Behavior

```
SLG Tier 1, Workload A: Allocation = 20%, Hard Limit = ON

Without hard limit:
  → WD-A gets 20% minimum, can exceed when siblings are idle

With hard limit:
  → WD-A can NEVER exceed 20% of tier resources
  → Even if all other workloads are idle
```

### Workload Hard Limits + WM COD

Workload hard limits are relative to the tier, NOT the system. But they interact with WM COD:

```
WM COD = 80%, VP = 100% (dynamic), SLG Tier 1, WD-A = 20% (hard limit)

The 20% is of tier resources, which is itself a fraction of VP and system resources.
As WM COD changes, the absolute resources available to WD-A change proportionally,
but the 20% cap within the tier remains constant.
```

## Combining Multiple Levels of Limits

All three levels can be applied simultaneously. Each acts independently:

### VP Limit vs Workload Hard Limit

| Scenario | VP Limit | WD Limit | Behavior |
|---|---|---|---|
| VP only | 50% fixed | None | VP limited to 50% system; WDs share freely within |
| WD only | Dynamic | 20% hard | WD limited to 20% of tier; VP can exceed allocation |
| Both | 50% fixed | 20% hard | VP limited to 50% system; WD limited to 20% of tier within VP |

### Three Levels Combined

```
WM COD = 80%
VP1 = 50% (fixed hard limit)
VP2 = 50% (dynamic)
WD-Analytics in VP1 = 10% (hard limit on SLG Tier)

Effective limits:
  Total system: 80% of total CPU/IO
  VP1: 50% of 80% = 40% of total
  VP2: up to 80% when VP1 underutilizes
  WD-Analytics: 10% of VP1's tier resources ≈ 4% of total system
```

## EPOD (Elastic Performance on Demand)

Temporary burst beyond COD limits for peak workloads.

### Two Approaches

| Approach | Description |
|---|---|
| Pre-paid EPOD | Purchase burst capacity in advance |
| Pay-per-use EPOD | Usage metered and billed based on consumption above COD |

### EPOD Monitoring

- Elastic Performance portlet in Viewpoint tracks burst usage
- ResUsage COD reporting shows periods when EPOD was active
- EPOD usage is based on the highest resource consumption within a reporting interval

## Practical Configuration Guide

### Setting Up WM COD

1. Determine desired usable capacity (e.g., 70%)
2. Measure non-database CPU delta using ResUsage
3. Set WM COD = desired + delta (e.g., 70% + 10% = 80%)
4. Monitor with ResUsage to confirm actual database CPU matches target
5. Adjust as needed — non-DB CPU can vary by workload mix

### Setting Up VP Hard Limits

1. Define business units / geographic divisions
2. Assign allocation percentages (must sum ≤ 100%)
3. Enable hard limit only on VPs that must be strictly capped
4. Leave at least one VP dynamic for flexibility
5. Test with production-like workloads to validate

### Setting Up Workload Hard Limits

Best for constraining analytics or other intensive workloads:

```
Step 1: Place analytics WD in SLG Tier (Timeshare doesn't support hard limits)
Step 2: Assign low allocation (5-10%)
Step 3: Enable hard limit
Step 4: Optionally add throttle for concurrency control
Step 5: Monitor CPU/IO consumption in ResUsageSPS
```

### Analytics Control — Three-Step Recipe

```
Step 1: Assign Low Priority
  → Place analytics WD in Timeshare Low or low SLG Tier allocation
  → Limits relative resource access

Step 2: Limit Concurrency with Throttles
  → Set workload throttle (e.g., limit = 2)
  → Reduces AWT and memory consumption
  → Classification: Query Band, Estimated Memory, or ObjectDatabase = 'TD_SYSFNLIB'

Step 3: Set Hard Limit (SLG Tier only)
  → Enable hard limit at 5-10%
  → Absolute cap even when system has spare resources

Result: Production queries recover ~95% of throughput with analytics running
```

### Test Results Summary (from WLM Analytics OB 2025)

Impact of WLM tuning on a fully-loaded system (95-100% CPU baseline):

| Metric | No WLM | Reduce Priority | + Throttle (2) | + Hard Limit (7%) |
|---|---|---|---|---|
| Tactical avg elapsed | 0.16s | ~0.11s | ~0.11s | ~0.11s |
| DS avg elapsed | 406.7s | ~350s | ~200s | ~187s |
| DS query count (2hr) | 171 | ~250 | ~340 | 351 |
| Analytics queries (2hr) | 23 | ~15 | 4 | 1 |

**Key insight:** Tactical recovers with just priority reduction. DS needs throttle + hard limit to recover fully. Analytics throughput decreases significantly — tune limits based on acceptable tradeoff.

## VantageCloud Lake Considerations

Lake uses simplified, automated WLM:

| Feature | Description |
|---|---|
| Cluster Isolation | Compute clusters have independent resources — no complex WLM needed |
| Automatic WDs | Pre-defined workloads (Tactical, Top, High, Medium, Low) |
| Automatic Demotions | Queries demoted based on CPU threshold per WD |
| Automatic Throttles | Per compute group, dynamically adjusted with cluster count |
| Analytic Compute Clusters | Lower throttle (10), more memory/CPU per query |
| Analytic GPU Clusters | Throttle of 2, specialized for ML inference |
| APPLY Operator Throttle | Global throttle of 3 for APPLY within analytic clusters |

## Monitoring Hard Limits

### ResUsageSPS — Per-Workload

```sql
SELECT TheDate, TheTime, WDName,
       CPUUsage, IOKBReadSum, IOKBWriteSum
FROM DBC.ResUsageSPS
WHERE TheDate = CURRENT_DATE
ORDER BY TheDate, TheTime, WDName;
```

### ResUsageSPMA — System-Level CPU Split

```sql
SELECT TheDate, TheTime,
       NodeCPU, DBSCPUUsage,
       (NodeCPU - DBSCPUUsage) AS NonDBCPU
FROM DBC.ResUsageSPMA
WHERE TheDate = CURRENT_DATE
ORDER BY TheDate, TheTime;
```

### Analytics Consumption Assessment (DBQL)

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
