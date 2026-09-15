# Compute Groups, Workload Management, and Cost in VantageCloud Lake

## Compute Group SQL Syntax

### CREATE COMPUTE GROUP

```sql
-- Standard Compute Group
CREATE COMPUTE GROUP Sales_Group;

-- Analytic Compute Group (for OAF/APPLY queries)
CREATE COMPUTE GROUP Analytics_Group
USING QUERY_STRATEGY ('ANALYTIC');
```

### CREATE COMPUTE PROFILE

```sql
-- Standard Compute Profile
CREATE COMPUTE PROFILE Profile1_Sales
IN Sales_Group,
INSTANCE = TD_COG_MEDIUM
USING
  SCALING_POLICY('STANDARD')
  ...;

-- Analytic Compute Profile
CREATE COMPUTE PROFILE Profile1_Analytics
IN Analytics_Group,
INSTANCE = TD_COG_MEDIUM,
INSTANCE TYPE = ANALYTIC
USING
  SCALING_POLICY('STANDARD')
  ...;
```

### SET SESSION for Compute Group

```sql
-- Switch to a different Compute Group within a session
SET SESSION COMPUTE GROUP = Analytics_Group;
```

The Compute Group specified in the User or Profile record in the Data Dictionary is used for all queries in a session. The user may change it with SET SESSION. User must have privileges for all Compute Groups they wish to use.

## Compute Group Design

### Design Orientations

Compute Groups can be organized by:
- **Department**: Marketing CG, Sales CG, Customer CG
- **Application**: BI CG, ETL CG, Data Science CG
- **Task**: Load CG, Ad Hoc CG, Dashboard CG

### Design Pattern Tradeoffs

**Option 1: All workloads in one Compute Group**
- Fewer resources required
- Greater reliance on priority differentiation
- Autoscale could be triggered by a single workload
- Example:
  - Dashboard users: Account = `$R`
  - Reports users: Account = `$M`
  - Ad hoc users: Account = `$L`

**Option 2: Isolate resource-intensive workloads**
- Separate ad hoc into its own CG with limited resources, no autoscale
- Apply autoscale and prioritization only to the main CG
- More cost control for unpredictable workloads

### When Priorities Matter Within a Compute Group

| CPU Utilization | Priority Impact |
|---|---|
| Lightly used | Priority differentiation has little value |
| 50%+ | Priorities begin to have value |
| 60-75% | Priorities have increasingly noticeable impact |
| 75%+ | Priorities become critical |
| 90%+ | Use of priorities essential for SLA workloads |

## Compute Profile Design

### Time-Window Based Profiles

Define multiple Compute Profiles per Compute Group for different time windows:

```
Compute Profile #1: 8 AM to 12:15 PM  — Up to 15% of processing power
Compute Profile #2: 12 noon to 5:15 PM — Up to 10% of processing power
Compute Profile #3: 5 PM to 8:15 AM   — Up to 5% of processing power
```

**Critical**: Overlap start/end times by at least **15 minutes** between profiles. Without overlap, clusters from Profile #1 may shut down before Profile #2 clusters are ready, causing queries to fall to the Primary Cluster.

### Sizing Compute Profiles

Steps:
1. Observe workload usage patterns by time of day from source platform
2. Assess percent of total resources used in each time window
3. Look for peaks and valleys within each window
4. Define a Compute Profile with sufficient power for each window
5. Determine autoscale min/max based on resource usage range

### Concurrency and Throttles

| Cluster Type | Global Throttle (queries per cluster) |
|---|---|
| Standard Compute Cluster | 15 concurrent queries |
| Analytic Compute Cluster | 10 concurrent queries |
| Analytic APPLY throttle | 3 concurrent APPLY queries |

Queries exceeding the throttle limit are placed in a **delay queue** and released when an active query completes or a new Compute Cluster is provisioned via autoscale.

### Autoscaling

- **STANDARD** scaling policy: All Compute Clusters provisioned at profile creation; standby clusters hibernated immediately; fast activation when needed
- Min = Max cluster count → **no autoscaling** during that profile
- Max cluster count is the key mechanism for controlling autoscale cost
- When delay queue triggers, autoscale activates a standby cluster

### Compute Profile Overrides

```sql
-- Suspend and resume Compute Profiles via SQL
-- Use only in exceptional situations to avoid unexpected costs
```

## Analytic Compute Clusters

### Requirements

- Queries with APPLY operator **require** an analytic Compute Group
- APPLY on a standard Compute Group → query **fails**
- User must either:
  - Have default Compute Group set to one with analytic clusters, OR
  - Issue `SET SESSION COMPUTE GROUP` to an analytic group before APPLY queries

### Dual Throttle System

```
Analytic Compute Group
├── All-Query Throttle: 10 per cluster (SQL + APPLY combined)
└── APPLY Throttle: 3 per cluster (APPLY only, subset of the 10)
```

Both throttles can trigger autoscale when queries are placed in delay queue.

### GPU Clusters

- Available for analytic workloads
- Throttle: 2 concurrent queries per cluster

## Workload Management

### Default Workloads

| Workload Name | Workload Type | Access Rate | Classification |
|---|---|---|---|
| Tactical-WD | Tactical | super-priority | AcctString = `$TA*` |
| T-WD | Timeshare Top | 8 | AcctString = `$R*` |
| H-WD | Timeshare High | 4 | AcctString = `$H*` |
| M-WD | Timeshare Medium | 2 | AcctString = `$M*` |
| L-WD | Timeshare Low | 1 | AcctString = `$L*` |
| WD-Default | Timeshare Medium | 2 | No account string or invalid string |

Access rates are relative to Timeshare Low:
- Top (T-WD) gets **8x** the resources of Low
- High (H-WD) gets **4x** the resources of Low
- Medium (M-WD) gets **2x** the resources of Low

Note: T-WD uses account string `$R` (legacy "Rush" name) for backward compatibility.

### Assigning Users to Priorities

```sql
-- Assign a user to High priority via account string
MODIFY USER Dashboard_User AS ACCOUNT = '$H';

-- Map users to compute groups via account strings
SET SESSION ACCOUNT = '$CG_BI_Users';
```

### Automatic Prioritization (Post-GA Feature)

Incoming queries automatically assigned priority based on expected execution time:

```
Very short requests → Very High Priority Workload
Medium requests    → Medium-High Priority Workload
Long requests      → Medium Priority Workload
Very long requests → Low Priority Workload
```

As a query consumes more CPU, it is **automatically demoted** to the next lower priority. Four priority levels total. No administrator setup required. Account string assignments override this automation.

### Account String Best Practices

- Users without an account string run in **WD-Default** (medium priority)
- Running all queries at default medium priority is a viable starting point
- **Avoid Account String Expansion (ASE) variables** in Lake (e.g., `&D`, `&H`)
  - DBC.Acctg information not available for Compute Clusters
  - Compute Clusters unaware of ASE variables from Primary Cluster
  - Reporting from DBC.Acctg only represents Primary Cluster consumption

### Priority Passing Between Clusters

- Account string set on Primary Cluster is passed via QueryFabric to Compute Cluster
- Both parent and child queries use the same priority
- Users without account strings execute at default medium priority on both clusters
- Workload name passing (post-GA): Only default workload names (T-WD, H-WD, etc.) are recognized on Compute Clusters
- **Custom workload names imported from traditional TASM are NOT recognized** on Compute Clusters → queries fall to M-WD (medium) priority

### User-Defined Throttles and Filters

Created via WLM SQL APIs (not Viewpoint, which is not part of Lake):

```sql
-- APIs documented in: Teradata Vantage - Application Programming Reference
-- Steps: Define throttle → Set query limit → Add classification → Enable → Activate

-- For filter rules: Set query limit to 0, action = abort
```

- Enforced on Primary Cluster at query start
- Never re-checked when work moves between clusters
- A throttle's query limit counts queries on BOTH Primary and Compute Clusters

### TASM Migration Considerations

| Issue | Impact |
|---|---|
| Custom workload names (e.g., WD-HSL-High) | Not propagated to Compute Clusters |
| Imported TASM ruleset | May behave differently on Lake architecture |
| State matrix | Not available in Lake default WLM; simulate with Compute Profiles |
| Non-default workloads on Compute Clusters | All run at M-WD (medium) priority |

**Recommendation**: Rethink and simplify WLM for Lake rather than importing legacy TASM rulesets. Use Compute Group isolation and Compute Profile scheduling instead.

### Simulating TASM State Matrix with Compute Profiles

Instead of TASM state matrix (not available in Lake default WLM):
- Use multiple Compute Profiles with different time parameters
- Schedule scripts to run at preset or triggered times for:
  - Forcing Compute Profile changes based on events (e.g., file arrival)
  - Changing user-defined throttle limits via API
  - Activating/deactivating throttle or filter rules

## Cost Management

### Cost Breakdown

| Cost Factor | Estimated Share | Control |
|---|---|---|
| Compute (Compute Clusters) | Majority (~75-85%) | DBA has greatest control via sizing, count, autoscale |
| Storage (object storage) | ~10-15% | Rises over time with data growth; OFS cheaper than BFS |
| Object Store Access (I/O) | ~5% | OFS Cache on Compute Cluster nodes reduces cloud I/O charges |

### OFS Cache

- Resides on Compute Cluster nodes
- Caches recently accessed OFS data
- Subsequent queries bypass OFS reads → fewer I/O charges from cloud vendor

### Shared Storage Costs

If data in object storage is shared across departments, apportion cost proportionally. Example: If Marketing pays 30% of total Lake compute cost → Marketing pays 30% of shared storage cost.

### Cost Reduction Techniques

- **Scale-to-zero**: Hibernate Compute Groups when not in use
- **Time-window Compute Profiles**: Smaller/fewer clusters during low demand
- **Conservative autoscaling**: Allow some queries to queue in delay queue
- **Right-size clusters**: Start small (2-3 clusters), increase as needed
- **Consolidate workloads**: Combine similar workloads into one CG for higher utilization
- **STJIs**: Reduce data scanned for tactical queries
- **ORDER BY on OFS tables**: Reduce I/O via object elimination
- **Performance burst + diet**: After a high-performance window, introduce a lower-cost Compute Profile to compensate

### Performance Burst Pattern

```
Original Profile     → 1 active + 1 standby cluster (large)
Performance Boost    → 1 active + 2 standby clusters (extra-large)
Low-Cost Recovery    → 1 active + 0 standby, no autoscale (medium)
```

During cost-reduction windows, use workload priorities to maintain performance for critical work at the expense of lower-priority work.

## Capacity Planning in Lake

### Shift from Traditional

- **Traditional**: Over-provision, plan for next big expansion, project 1-2 years out
- **Lake**: Maintain adequate resources while keeping costs at expected levels
- Planning done at **Compute Group level**, not system level

### Factors That Can Drive Up Costs

- Unexpected changes to a workload or application
- Inappropriate autoscaling policies
- Unusual peaks in processing requirements

### Approach

1. Chart utilization patterns from DBQL and ResUsage
2. Identify usage spikes/dips by application, day, season
3. Start Compute Groups small (2-3 clusters)
4. Adjust these parameters iteratively:
   - Size of Compute Clusters
   - Number of active clusters
   - Autoscaling policies
5. Reduce compute power if costs exceed expectations

### Predictable vs. Exploratory Workloads

- **Predictable** (e.g., Monday morning batch): Flexible autoscaling, potentially costly
- **Exploratory/ad hoc**: Constrain to medium cluster, limited hours, no autoscale

## UDF Execution on Specific Clusters

```sql
-- UDF that can ONLY execute on Compute Clusters
CREATE FUNCTION udf1_cog (parameter_1 INT)
  RETURNS INT
  LANGUAGE C
  NO SQL
  PARAMETER STYLE SQL
  DETERMINISTIC
  EXTERNAL NAME 'CS!udf1_cog!udf1_cog.c'
EXECUTE ON COMPUTE;
```

- `EXECUTE ON COMPUTE`: UDF only runs on Compute Clusters; fails if no Compute Group privilege or no clusters available
- `EXECUTE ON PRIMARY`: UDF restricted to Primary Cluster
- UDF library on network file system, shared across all clusters

### UDF Service in Lake

- POD-level service manages external UDF installation via RESTful API
- Supports C, C++, Java external UDFs
- Compiling/building moved from TPA nodes to UDF Service
- UDFs execute in **containers** on TPA nodes (enforces cloud security: no network/disk access)
- Fully self-service installation, no DevOps involvement
- Integrates with customer CI/CD pipelines

## QueryGrid in Lake

- Pre-installed on all Lake platforms
- Pre-configured to connect to Teradata Enterprise platforms (on-premises, VantageCloud Enterprise on AWS)
- Supports multi-source joins, pushdown processing
- Queries can originate from any connected system
- Pushes predicate filtering close to data to minimize data movement
- For frequently used remote data, migrate locally rather than federate

## APIs and Automation

Public RESTful APIs available for:
- Changing active Compute Profiles (e.g., for month-end processing)
- Monitoring resource metrics across platforms
- Triggering ETL processes based on data arrival
- Creating user-defined throttles and filters
- Automating data pipeline orchestration

In Lake, automation via APIs replaces much of what was done through scripted code or UI on traditional platforms.

## Key Architectural Differences from On-Premise

| Aspect | On-Premise | VantageCloud Lake |
|---|---|---|
| Data storage | All on BFS (block storage) | BFS (small, hot) + OFS (bulk) + External |
| Compute | Single shared cluster | Primary + elastic Compute Clusters |
| Workload isolation | Virtual Partitions / TASM | Compute Groups (physical isolation) |
| Scaling | Fixed hardware, planned expansions | Elastic autoscale, scale-to-zero |
| Cost model | Fixed infrastructure cost | Pay-per-use compute + storage + I/O |
| Load utilities | TPT Load/Update/Stream | INSERT SELECT, Flow Service (TPT only for BFS) |
| WLM | Full TASM with state matrix | Simplified defaults + Compute Profile scheduling |
| Capacity planning | System-level, multi-year | Compute Group-level, iterative |
| UDF deployment | Manual on TPA nodes | Self-service via UDF Service API + containers |
| Monitoring | DBQL in DBC database | MSS → external object storage → TD_Metric_Svc views |
| Secondary indexes | USI/NUSI supported | Not supported on OFS; use columnar + ORDER BY + STJIs |
