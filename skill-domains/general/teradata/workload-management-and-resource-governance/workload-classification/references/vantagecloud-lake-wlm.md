# VantageCloud Lake Workload Management

> Source: WLM_Analytics_OB — Controlling Analytics with WLM

## Architecture Differences from On-Premises

| Aspect | Traditional TASM | VantageCloud Lake |
|---|---|---|
| Cluster model | Single system, virtual partitions | Primary + multiple Compute Clusters |
| Isolation | VP-based resource partitioning | Cluster-level physical isolation |
| Classification | DBA-defined rules per workload | Pre-defined automatic classification |
| Demotion | DBA-configured exceptions | Auto-demotion by CPU threshold |
| Scaling | Fixed hardware | Dynamic cluster add/remove |
| Complexity | High (many knobs) | Low (automated defaults) |

## Multi-Cluster Architecture

- **Primary Cluster:** Always running; handles DDL, system queries, small tactical work
- **Compute Clusters:** Elastically provisioned; grouped into Compute Groups
- Clusters within a Compute Group share data but execute independently
- Adding/removing clusters has no impact on other clusters' running queries

## Automatic Workload Classification

Lake pre-defines workload definitions (WDs) with distinct priorities. Requests are auto-classified by query characteristics — no DBA rule configuration required.

### Auto-Demotion

- Queries exceeding CPU thresholds are automatically demoted to lower-priority WDs
- **Bypass option:** Associate users with a second set of WDs without demotion exceptions
- Use bypass for known long-running analytics that should not be demoted

## Compute Cluster Types and Throttle Limits

| Cluster Type | Default Throttle | Typical Use Case |
|---|---|---|
| Standard Compute | 30 | General queries, ETL, reporting |
| Analytic Compute | 10 | Complex analytics, more memory/CPU per query |
| Analytic GPU | 2 | ML inference, deep learning |

### APPLY Operator

- Additional global throttle of **3** for APPLY operator queries within Analytic Compute
- Prevents resource exhaustion from parallel UDF/external function invocations

### Dynamic Throttle Adjustment

- Throttle limits auto-adjust as clusters activate/hibernate within a compute group
- Compute group-level throttle = sum of active cluster limits
- Example: 3 Standard clusters active → group throttle = 90

## Recommended WLM Sequence for Analytics

Control analytics resource consumption in this order (least to most restrictive):

### 1. Assign Priority (Preferred)

Place analytics workloads in a low-priority WD. Allows analytics to use spare resources without impacting higher-priority work.

### 2. Limit Concurrency with Throttles

Target throttles by:
- Estimated memory consumption
- Function name (e.g., specific analytic functions)
- Username or user group

Excess queries are delayed (queued) rather than rejected.

### 3. Set Hard Limits (Last Resort)

- CPU + I/O percentage limits per workload
- **Prevents using spare resources** — only use when priority and throttles are insufficient
- Hard limits add processing overhead

## Lake vs. Traditional — When to Use What

| Scenario | Lake Approach | Traditional Approach |
|---|---|---|
| Isolate analytics from OLTP | Separate Compute Cluster | Virtual Partition with allocation |
| Limit long-running queries | Auto-demotion (default) | Exception with demotion action |
| Control ML workloads | GPU cluster (throttle=2) | TASM + ScriptMemLimit |
| Handle burst demand | Auto-scale compute group | Flex throttles + states |
| Prioritize tactical queries | Primary cluster priority | Tactical WD + reserved AWTs |

## Best Practices for Lake WLM

1. **Start with defaults** — Lake's auto-classification and demotion handle most scenarios
2. **Use cluster isolation** instead of complex WLM rules — simpler and more effective
3. **Reserve demotion bypass** for known analytics workloads with predictable resource needs
4. **Monitor compute group throttles** — if queries are frequently delayed, add clusters
5. **Use Analytic Compute clusters** for memory-intensive analytics (10 concurrent vs. 30)
6. **Avoid hard limits on compute clusters** — let priority and throttles handle contention

## Monitoring Lake WLM

### Query Activity by Cluster

```sql
-- Active queries per compute cluster
SELECT ComputeClusterName, COUNT(*) AS active_queries,
       SUM(AmpCPUTime) AS total_cpu
FROM DBC.DBQLogTbl
WHERE LogDate = CURRENT_DATE
GROUP BY ComputeClusterName
ORDER BY total_cpu DESC;
```

### Throttle Queue Monitoring

```sql
-- Queries delayed by throttle limits
SELECT UserName, QueryText, DelayTime, StartTime
FROM DBC.DBQLogTbl
WHERE LogDate = CURRENT_DATE
  AND DelayTime > 0
ORDER BY DelayTime DESC;
```

### Demotion Events

```sql
-- Find queries that were auto-demoted
SELECT UserName, QueryText, AmpCPUTime,
       TotalFirstRespTime AS elapsed_sec
FROM DBC.DBQLogTbl
WHERE LogDate >= CURRENT_DATE - 7
  AND WDName LIKE '%Demoted%'
ORDER BY AmpCPUTime DESC;
```

## Compute Group Configuration

### Cluster Scaling Policies

| Policy | Behavior |
|--------|----------|
| **Auto-scale** | Clusters activate/hibernate based on queue depth and utilization |
| **Min/Max clusters** | Set boundaries: e.g., min 1, max 5 Standard clusters |
| **Cool-down period** | Minimum time before hibernating an idle cluster |
| **Scale-up threshold** | Queue depth or CPU utilization that triggers new cluster activation |

### Compute Group Isolation Patterns

```
Primary Cluster ─── DDL, admin, tactical queries
                    (always on, highest priority)

Compute Group A ─── BI / Reporting
  └─ 2-4 Standard clusters (auto-scale)

Compute Group B ─── Data Science / ML
  └─ 1-2 Analytic clusters (throttle=10 each)

Compute Group C ─── ETL / Batch
  └─ 1-3 Standard clusters (off-hours scaling)
```

### Mapping Users to Compute Groups

Users and applications are directed to specific compute groups via:
- **User/role assignment** — each user's default compute group
- **Query band routing** — SET QUERY_BAND with compute group target
- **Application profile** — middleware-configured compute group selection

## Migration from Traditional TASM to Lake WLM

| Traditional TASM Concept | Lake Equivalent |
|---|---|
| Virtual Partitions | Compute Groups / Clusters |
| Allocation Groups + WDs | Auto-classification with priority |
| Exception Demotion rules | Auto-demotion (built-in CPU thresholds) |
| Planned Environment states | Auto-scaling policies |
| AWT reservation | Cluster-level throttle limits |
| Bypass classification rules | Demotion bypass user assignment |
| TASM Utility Throttles | APPLY operator throttle (3 per cluster) |
