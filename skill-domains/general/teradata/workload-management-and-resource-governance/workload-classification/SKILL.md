---
name: teradata-workload-management
description: 'Configure and manage Teradata workload management (TASM/TDWM), including workload classification, throttles, priority scheduling, virtual partitions, system filters, exception handling, AMP worker tasks, utility management, planned environments, and analytics resource control. Use when setting up workload priorities, throttle rules, resource limits, monitoring query performance via DBQL, or controlling analytics/ML workload impact.'
metadata:
  author: teradata
  version: "1.1"
---

# Teradata Workload Management

## When to Use

- Configuring workload classification rules (who/what/where)
- Setting up throttles to limit concurrency
- Managing priority scheduling (Tactical, SLG Tiers, Timeshare)
- Creating virtual partitions for resource isolation
- Defining system filters to reject bad queries
- Setting exception criteria (CPU, spool, elapsed time limits)
- Controlling utility jobs (FastLoad, MultiLoad, etc.)
- Monitoring workload performance via DBQL
- Limiting analytics/ML workload impact on production
- Working with TASM states and planned environments

## Priority Scheduling Hierarchy

```
Tdat (system)
├── Sys (PDE critical tasks)
├── Dflt (recovery, abort, gateway)
└── User (all user work)
    └── Virtual Partitions (1-10)
        ├── Tactical Tier (highest priority)
        ├── SLG Tiers 1-5 (allocation-based)
        │   ├── Workload A (40%)
        │   ├── Workload B (30%)
        │   └── Remaining (≥10%)
        └── Timeshare
            ├── Top (8x)
            ├── High (4x)
            ├── Medium (2x)
            └── Low (1x)
```

## Workload Types

| Type | Best For | Priority | Notes |
|---|---|---|---|
| **Tactical** | Single-AMP, sub-second queries | Highest | Reserved AWT pool; mandatory CPU/IO exceptions |
| **SLG Tier** | Mixed workloads with SLAs | Mid (1-5 tiers) | Allocation-based; supports hard limits |
| **Timeshare** | Low-priority, best-effort work | Lowest | Access levels: Top/High/Medium/Low |

## Procedure: Classify Workloads

Classification criteria determine which workload handles a request:

### Classification Criteria Types

| Type | Category | Examples |
|---|---|---|
| **Request Source (Who)** | Account, Username, Application, Profile, Client IP, Query Band |
| **Target (Where)** | Database, Table, View, Macro, SP, UDF |
| **Query Characteristics (What)** | Statement type, AMP count, row estimates, est. processing time |
| **Utility** | FastLoad, MultiLoad, FastExport, MLOADX, BAR |

### Classification Rules

- Same-type criteria are OR'd (user A OR user B)
- Different Who types are AND'd (user AND account AND application)
- **Exception — Target (Where):** different target types (database, table, view) are always **OR'd** by the database, even if Viewpoint UI displays AND
- **Exception — Query Band:** multiple query band key/value pairs are **OR'd** — matching ANY one satisfies
- Who + Where + What categories are AND'd across categories
- Requests match the first qualifying workload in evaluation order
- Unmatched requests go to WD-Default
- **Configuration:** Viewpoint Workload Designer or TASM API (RQC commands) — there is NO SQL DDL for workloads

## Procedure: Set Up Throttles

### Workload Throttles

Limit concurrent requests per workload:

| Setting | Effect |
|---|---|
| Limit = 5 | Max 5 concurrent queries in this workload |
| Action = Delay | Queue excess queries until slots open |
| Action = Reject | Reject excess queries immediately |

### System Throttles

| Rule Type | Scope |
|---|---|
| Collective | Single counter for all matching requests |
| Individual | Per-object counter (e.g., per table) |
| Member | Per-user counter |

### Group Throttles

Combine 2+ workload throttles under a shared limit.

### Key Recommendations

- Lead with workload throttles, supplement with system throttles
- Never throttle tactical workloads
- Use member throttles for per-user fairness
- Exclude utilities from system throttles

## Procedure: Control Analytics Workloads

Three-step approach to limit ML/analytics impact:

### Step 1: Assign Low Priority

Place analytics in Timeshare Low or a low-allocation SLG Tier.

### Step 2: Limit Concurrency

```
Throttle: Limit = 2 concurrent analytic sessions
Classification: Query Band or ObjectDatabase = 'TD_SYSFNLIB'
```

### Step 3: Set Hard Limit (SLG Tier only)

Set 5-10% hard limit on the analytics workload to cap resource consumption.

**Result:** Production queries recover ~95% of throughput with analytics running.

## Procedure: Set Exception Criteria

| Criterion | Type | Description |
|---|---|---|
| CPU Time | Threshold | Total CPU seconds |
| Elapsed Time | Threshold | Wall clock time |
| Spool Rows | Threshold | Rows written to spool |
| Spool Size | Threshold | Spool space in bytes |
| Blocked Time | Threshold | Time waiting for locks |
| CPU/Disk Ratio | Qualified | Sustained CPU-intensive pattern |
| CPU/IO Skew | Qualified | Uneven distribution |

### Exception Actions

| Action | Effect |
|---|---|
| Change Workload | Demote to lower priority (e.g., Timeshare Low) |
| Abort | Kill the query |
| Alert | Send notification |

### Tactical Exceptions (Mandatory)

All tactical workloads automatically have:
- CPU per node (default 2 sec)
- CPU sum over all nodes
- I/O per node (default 200 MB)
- I/O sum over all nodes

Breach → automatic demotion to non-tactical workload.

## System Filters

Reject queries before execution based on estimated cost:

```
Example rules:
- Reject if est. processing time > 200 hours
- Reject unconstrained product joins on tables > 1B rows
- Warning mode: log but don't reject (WarningOnly='T' in DBQL)
```

## Virtual Partitions

Divide system resources between business units:

| Mode | Behavior |
|---|---|
| Dynamic | VP can exceed allocation when others are idle |
| Fixed | Hard cap — VP never exceeds allocation |

Each VP has its own Tactical → SLG → Timeshare hierarchy.

## TASM: States & Planned Environments

### Planned Environments

Time-based processing windows (Day/Night, Weekday/Weekend, Month-End).

### State Matrix

2D grid: Planned Environments × Health Conditions. Each cell = a State with its own:
- Throttle limits
- Filter rules
- Workload allocations
- Timeshare access levels

**Cannot change per state:** Classification criteria, tier position, evaluation order.

### Health Events

| Event Type | Examples |
|---|---|
| Component | Node down, AMP fatal |
| AMP Activity | Available AWTs, Flow Control, AWT Wait Time |
| System Usage | CPU Utilization, CPU Skew, I/O Usage |
| Workload | Active Requests, Delay Queue Depth, Arrivals |
| Period | Time-based (cron-like) |
| User-Defined | API-toggled boolean |

## AMP Worker Tasks (AWTs)

- ~80 per AMP (pre-allocated)
- Tactical/expedited workloads get reserved AWT pools
- Formula: `(reserve_count × 2) + 2` removed from general pool
- AWT Resource Limits control utility AWT consumption

## Utility Management

| Utility | Internal Limit | Notes |
|---|---|---|
| FastLoad | 30 | Combined FL+ML max 30 |
| MultiLoad | 30 | Combined FL+ML max 30 |
| FastExport | 60 | |
| MLOADX | 120 | TPT parallel export |
| BAR | 350 | Backup/archive/restore |

Utility session rules control sessions per job (defaults based on NumAMPs/NumNodes).

## Monitoring — Key DBQL Views

See [DBQL Monitoring reference](./references/dbql-monitoring.md) for query examples.

| View | Content |
|---|---|
| `DBC.DBQLogTbl` | Per-request: CPU, I/O, elapsed time, WD assignment |
| `DBC.ResUsageSPS` | Per-workload resource usage per interval |
| `DBC.TDWMSummaryLog` | Per-WD summary: arrivals, completions, delays, SLG met |
| `DBC.TDWMEventLog` | Chronological TASM activity log |
| `DBC.TDWMExceptionLog` | Exception details |

## Common Errors and Solutions

| Problem | Cause | Fix |
|---|---|---|
| Queries stuck in delay queue | Throttle too tight | Increase throttle limit or add flex throttle |
| Tactical demotion | Exceeded CPU/IO exception | Optimize query or increase exception threshold |
| AWT exhaustion | Too many utilities or analytics | Set AWT Resource Limits; throttle utilities |
| Unclassified queries | No matching workload | Check classification criteria; review WD-Default |
| Analytics crushing production | No resource control | Apply 3-step: low priority + throttle + hard limit |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-workload-management", path="references/FILENAME")` — do NOT call `list`.

- [Priority Scheduling](./references/priority-scheduling.md) — Detailed scheduling hierarchy, OS shares, virtual partitions
- [DBQL Monitoring](./references/dbql-monitoring.md) — SQL queries for workload analysis
- [Throttles & Filters](./references/throttles-and-filters.md) — System/workload/group throttles, delay queues, filter rules, bypass
- [Exception Handling](./references/exception-handling.md) — Exception criteria, skew detection, CPU ms/IO, qualification time, actions
- [Utility Management](./references/utility-management.md) — Utility protocols, internal limits, session rules, AWT resource limits
- [States, Events & Automation](./references/states-events-automation.md) — State matrix, event types, planned environments, working values
- [Hard Limits & COD](./references/hard-limits-and-cod.md) — WM COD, VP limits, workload limits, EPOD, analytics control
- [Workload Classification](./references/workload-classification.md) — Classification criteria (Who/Where/What/QueryBand/Utility), AND/OR rules, session vs. request classification, evaluation order, tactical management, global weight calculations, SLGs, special users (DBC/TDWM)
- [VantageCloud Lake WLM](./references/vantagecloud-lake-wlm.md) — Lake multi-cluster architecture, automatic classification, auto-demotion, compute cluster types and throttle limits, APPLY operator throttle, recommended WLM sequence for analytics
