# Priority Scheduling — Complete Reference

## Linux CFS Integration

Teradata Priority Scheduler translates admin settings into Linux Completely Fair Scheduler (CFS) OS shares. CFS uses control groups in a tree hierarchy. Resources flow top-down through the tree.

## Control Group Hierarchy

```
Tdat (root)
├── Sys (workload ID 255)
│   └── Critical PDE tasks — very high OS shares
├── Dflt (workload ID 254)
│   └── Recovery, abort processing, deadlock detection, gateway
└── User
    └── Virtual Partition 1 (default)
    │   ├── Tactical
    │   │   └── WD: real-time-queries
    │   ├── SLG Tier 1
    │   │   ├── WD: oltp-queries (40%)
    │   │   ├── WD: reports (30%)
    │   │   └── Remaining (≥10%)
    │   ├── SLG Tier 2
    │   │   ├── WD: batch-jobs (60%)
    │   │   └── Remaining (≥10%)
    │   └── Timeshare
    │       ├── WD: ad-hoc-top (Top = 8x)
    │       ├── WD: ad-hoc-high (High = 4x)
    │       ├── WD: ad-hoc-med (Medium = 2x)
    │       └── WD: analytics (Low = 1x)
    └── Virtual Partition 2 (optional)
        └── ... (own Tactical/SLG/Timeshare)
```

## Virtual Runtime

CFS scheduling decision: `virtual_runtime = CPU_seconds_used / shares`

Task with **smallest** virtual runtime runs next. Red-black tree sorts all runnable tasks. Preemption granularity: 50,000 nanoseconds (0.05ms).

Higher shares → virtual runtime grows slower → task runs more often.

## Tactical Tier

- Highest priority user work
- Designed for single-AMP or few-AMP, sub-second queries
- Automatically expedited — accesses reserved AWT pool
- **No workload allocation** — consumes whatever it needs
- **Mandatory auto-exceptions** (cannot be deleted):
  - CPU per node (default 2 sec)
  - CPU sum over all nodes
  - I/O per node (default 200 MB)
  - I/O sum over all nodes
- Breach → automatic demotion to non-tactical workload
- **Recommendation:** Don't set CPU exception < 1 second

### Reserved AWT Pool

Formula: `(reserve_count × 2) + 2` AWTs removed from general pool per AMP.

| Message Type | Purpose |
|---|---|
| WorkEight | Expedited steps (dispatch channel 4) |
| WorkNine | Expedited steps (dispatch channel 5) |
| WorkTen | Fixed 2 reserves per AMP |

## SLG Tiers (TASM Only)

- 1 to 5 tiers (Tier 1 = highest SLG priority)
- Each tier has workloads with **allocation percentages** (must total ≤90%)
- **Remaining workload** auto-created (minimum 10% — ensures resources flow down)
- Inactive workloads: allocation redistributed among active siblings

### SLG Tier 1 Expedited (14.10+)

SLG Tier 1 workloads can be marked as expedited → get reserved AWTs (like tactical).

### Global Weight Calculation

Actual % of system = product of allocations walking up the tree:

```
Example: VP allocation = 60%, SLG Tier 1 = 50%, Workload A = 40%
Global Weight = 0.60 × 0.50 × 0.40 = 12% of system resources
```

### Hard Limits on SLG Workloads

When enabled, a workload cannot exceed its allocated percentage even if other workloads are idle.

## Timeshare Tier

- 4 fixed access levels with hardcoded ratios:

| Access Level | Rate Multiplier |
|---|---|
| Top | 8x |
| High | 4x |
| Medium | 2x |
| Low | 1x |

- Priority is **blind to concurrency** — Top always gets 8x Low regardless of how many queries
- No Remaining workload — gets whatever flows from above
- Cannot set hard limits (use SLG Tier for hard limits)

### Automatic Decay (Off by Default)

When enabled, long-running queries automatically drop access level:

| Stage | Trigger | New Rate |
|---|---|---|
| 1st decay | 10 sec CPU or 100 MB I/O | Rate ÷ 2 |
| 2nd decay | 200 sec CPU or 10,000 MB I/O | Rate ÷ 4 |

DBQL columns: `CPUDecayLevel`, `IODecayLevel`

## Virtual Partitions

| Mode | Behavior |
|---|---|
| Dynamic | VP can exceed allocation when siblings are idle |
| Fixed | Hard cap — VP never exceeds its allocation |

- Default: 1 VP with 100% allocation
- Maximum: 10 VPs
- Each VP has its own complete Tactical → SLG → Timeshare hierarchy
- VP-level throttles available (TASM)

## Resource Hard Limits (WM COD)

Three levels of hard limits:

### 1. System Level (WM COD)

Hard limit on entire Tdat control group:
- CPU: Period-based quota per enforcement period
- I/O: TDMeter per disk, bandwidth-based costing
- Must account for non-database CPU (PDE, OS): adjust upward by delta

### 2. Virtual Partition Level

Hard limit on VP allocation (Dynamic → Fixed).

### 3. Workload Level

Hard limit on individual SLG Tier workload's resource percentage.

### EPOD (Elastic Performance on Demand)

Burst beyond COD limits temporarily for peak workloads.

## AWT Architecture

- ~80 AWTs pre-allocated per AMP
- AWTs handle all work: user queries, utilities, system tasks
- AWT message queue ordered by Global Weight

### AWT Resource Limits

Control utility AWT consumption:

```
Example: Limit FastLoad to 20% of AWTs
→ At 80 AWTs/AMP: max 16 AWTs for FastLoad
```

### AWT Shortage Symptoms

- Flow control events
- Increasing AWT wait times
- Query delays unrelated to throttles

## Flex Throttles (TASM 16.0+)

Auto-release queries from delay queue when:
- Available AWTs exceed threshold
- CPU utilization below threshold

Configured per state in the state matrix.
