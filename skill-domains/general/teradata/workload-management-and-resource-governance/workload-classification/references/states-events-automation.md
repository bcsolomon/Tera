# States, Events & Automation — Complete Reference

## State Matrix Architecture

The state matrix is a 2D grid that determines the active set of WLM rules:

```
                   Planned Environments (horizontal axis)
                   ┌──────────┬──────────┬──────────┬──────────┐
                   │ Always   │ Weekday  │ Weekend  │ MonthEnd │
    Health    ─────┼──────────┼──────────┼──────────┼──────────┤
    Conditions     │          │          │          │          │
    (vertical │ Normal  │ ST-Base  │ ST-Day   │ ST-Wkend │ ST-MEnd  │
     axis)    ├─────────┼──────────┼──────────┼──────────┼──────────┤
              │ Degraded│ ST-Dgrad │ ST-DgDay │ ST-DgWkd │ ST-DgME  │
              └─────────┴──────────┴──────────┴──────────┴──────────┘

Each cell = a State with its own throttle limits, filter rules,
            workload allocations, and timeshare access levels
```

### Default State Matrix

- 1×1: Single planned environment "Always" (24×365), single health condition "Normal"
- Default state: "Base"
- Only ONE state is active at any time

### State Resolution

When multiple planned environments could apply simultaneously (e.g., Weekend AND Daytime):
- TASM evaluates planned environments from **rightmost** (highest precedence) to left
- Stops at the first planned environment that fits current criteria
- **Drag planned environments right** in Workload Designer to increase precedence

## Fixed Attributes vs Working Values

### Fixed Attributes (Cannot Change by State)

| Attribute | Description |
|---|---|
| Classification criteria | What qualifies a request to a workload |
| Tier position | Tactical, SLG Tier 1-5, or Timeshare |
| Evaluation order | Sequence workloads are checked for classification |

### Working Values (CAN Vary by State)

**By Planned Environment:**

| Value | Description |
|---|---|
| SLG Tier allocation (share %) | Workload's resource share on its tier |
| Timeshare access level | Top, High, Medium, Low |
| Service Level Goals | Response time or throughput targets |
| Hold Query Response (MRT) | Minimum response time |

**By State (Planned Environment × Health Condition):**

| Value | Description |
|---|---|
| Workload throttle limits | Concurrency per workload |
| System throttle limits | System-wide concurrency |
| Filter rules (enabled/disabled) | Query rejection rules |
| Query session limits | Logon throttles |
| Utility limits | Utility concurrency |
| Resource limits (hard limits) | CPU/IO caps |

### Critical Rule

Do NOT change a workload's tier position between planned environments. Implement priority changes by adjusting share percentages or access levels within the same tier.

```
✓ Correct: WD-Reports at SLG Tier 1, 30% by day → 10% by night
✗ Incorrect: WD-Reports at SLG Tier 1 by day → SLG Tier 5 by night
```

Exception: Changing timeshare access levels (Top↔High↔Medium↔Low) is acceptable — all are within the same tier.

## Event Types

### Component Down Events (Detected at System Startup)

| Event | Trigger |
|---|---|
| Node Down | One or more nodes unavailable |
| AMP Fatal | One or more AMPs in fatal state |

### AMP Activity Events

| Event | Description | Key Settings |
|---|---|---|
| Available AWTs | AWTs available on busiest AMP | Threshold count, qualification time, AMP count |
| Flow Control | AMPs reporting flow control | AMP count threshold, qualification time |
| AWT Wait Time | Time messages wait for an AWT | Threshold, qualification time |

### System Usage Events

| Event | Description | Key Settings |
|---|---|---|
| CPU Utilization | System-wide CPU usage | Percentage threshold, qualification time |
| CPU Skew | Imbalanced CPU across nodes | Percentage threshold |
| IO Usage | Disk I/O bandwidth utilization | Bandwidth %, LUN % monitored, LUN % triggered |

### Workload Events (Per-Workload)

| Event | Description |
|---|---|
| CPU Utilization | CPU used by a specific workload |
| Arrivals | Request arrival rate for a workload |
| Active Requests | Current concurrency in a workload |
| Delay Queue Depth | Queries waiting in a workload's delay queue |

### Period Events

Time-based planned environment triggers:

```
Example periods:
  Daytime:   8:00 AM to 5:00 PM (Mon-Fri)
  Nighttime: 5:00 PM to 8:00 AM
  Weekend:   Saturday 00:00 to Sunday 23:59
```

**Rules:**
- Make periods **contiguous** (8:00 AM to 5:00 PM, then 5:00 PM to 12:00 AM) — gaps cause unintended state transitions
- Use **Wrap Around Midnight** for periods spanning midnight (e.g., 5 PM to 8 AM)
- Without Wrap Around Midnight: period only applies on specified days, may have unintended midnight boundary behavior

### User-Defined Events (UDEs)

Boolean variables toggled via Workload Management API:

```
Enable: API call sets UDE to TRUE with optional expiration timer
Disable: Explicit API call or automatic expiration

Use cases:
- Signal when a data load window is complete
- Allow external systems to trigger state changes
- Coordinate with ETL schedules
```

### Event Combinations

Combine multiple events with Boolean logic (AND, OR, NOT):

```
Example: EC-HighLoad = (CPU Util > 85%) AND (Available AWTs < 5)
  Action: Change health condition to "Stressed"
```

## Event Actions

When an event triggers, one or more actions can be configured:

| Action | Description |
|---|---|
| Change Planned Environment | Switch to a different PE (triggers state change) |
| Change Health Condition | Switch health state (triggers state change) |
| Send Alert | Notification via Teradata Alerts framework |
| Post to System Queue | Write to DBC.SystemQTbl for application consumption |
| Run Program | Execute an external program |

## AWT Usage Event — Detailed Configuration

### Available AWTs Algorithm Options

| Algorithm | Scope |
|---|---|
| WorkTypeNew only (default) | Count only AWTs available for new work (WorkType00 pool) |
| Entire unreserved pool (16.0+) | Count all AWTs in unreserved pool |

### Monitoring Columns (ResUsageSAWT)

| Column | Description |
|---|---|
| AvailableForWork00 | AWTs available for WorkType00 (new work) at interval end |
| AvailableForWork00Min | Minimum AWTs for WorkType00 during interval |
| AvailableForWork08 | AWTs available for WorkType08 (expedited) at interval end |
| AvailableForWork08Min | Minimum AWTs for WorkType08 during interval |

### AWT Event Recommendations

- Threshold: 2–5 available AWTs on the busiest AMP
- Qualification time: At least 60 seconds
- **Initial action:** Send notification (don't change state immediately)
- AWT shortages are normal during busy periods — only act on persistent shortages
- Cross-correlate with SLG metrics to confirm actual performance impact before automating state changes

### Response to Persistent AWT Shortages

1. Add throttles or reduce limits on lower-priority workloads
2. Reserve AWTs for tactical workloads (up to 20 reserved)
3. Reduce utility concurrency
4. Check if Flex Throttle feature conflicts with AWT event (both use same algorithm)

## Flow Control Event — Detailed Configuration

Flow control = AMPs blocking new messages because AWT message queue is full (20 messages per work type by default).

| Setting | Description |
|---|---|
| AMP Count | Number of AMPs that must report flow control |
| Qualification Time | How long flow control must persist |

### Flow Control Recommendations

- Qualification time: At least 1 minute for pure DS; shorter for tactical workloads
- AMP count: At least 1–2% of total AMPs (avoids insignificant detections)
- Flow control counts AMPs reporting ANY flow control during the interval — no distinction between 1ms and full-interval flow control
- Same set of AMPs does NOT need to persist across intervals

## IO Usage Event (16.10+)

Monitors disk I/O bandwidth utilization to detect I/O bottlenecks.

### Automatic Configuration

TASM automatically selects:
1. The clique with the AMP having the **least bandwidth** (theoretical bottleneck)
2. The **fastest array type** on that clique (most likely to exhibit bandwidth issues)

### Settings

| Parameter | Description | Default |
|---|---|---|
| Bandwidth Threshold % | IO utilization % to trigger event | Pre-selected |
| % of LUNs Monitored | Portion of LUNs to sample (max 50) | Pre-selected |
| % of Monitored LUNs Triggered | How many monitored LUNs must hit threshold | Pre-selected |

**Note:** Bandwidth percentages exceeding 100% are possible and valid — the max IOTA is a generalized metric.

### IO Usage Logging (TDWMEventLog, EventCode=9714)

| SubCode | Description |
|---|---|
| 1 | Configuration: TotalLUNs, MonitoredLUNs, TriggeredLUNs |
| 2 | Full set of monitored LUNs with clique/array identification |
| 3 | Event triggered (False → True) — LUNs exceeding threshold |
| 4 | Event still True, LUN set changed |
| 5 | Event deactivated |

SubCodes 3-5 require LOG_IOUSAGE_DETAILS option (contact support to enable).

## State Transition Overhead

| Operation | Overhead | Impact |
|---|---|---|
| State transition | Negligible | Delay queues re-evaluated; no TDWM database access |
| Ruleset activation | High (minutes on busy systems) | Reads TDWM database; re-evaluates all requests |

**Always prefer state transitions over ruleset changes for runtime adjustments.**

### State Transition Delay Queue Behavior

- If new throttle limit is higher → additional requests released up to new limit
- If new throttle limit is lower → no new requests released until active count falls below new limit
- Active count may temporarily exceed the new limit during transition

## Naming Conventions

| Object Type | Convention | Example |
|---|---|---|
| Planned Environment | PE-{name} | PE-Online, PE-BatchWindow |
| Health Condition | HC-{name} | HC-Normal, HC-Degraded |
| Event | EV-{name} | EV-BatchWindow, EV-HighCPU |
| Event Combination | EC-{name} | EC-BatchComplete |
| State | ST-{name} | ST-Online, ST-ThrottleQueries |
| Exception | EX-{name} | EX-HighCPU, EX-SkewDetect |

## State Matrix Recommendations

1. **Start with Base state** — add states only when clear need arises
2. Keep total unique states to a **minimum** (rarely need more than 3-5)
3. Limit planned environment transitions to **2-3 per day**
4. Reuse states where possible — multiple matrix cells can reference the same state
5. After creating a new state, **review all state-specific values** for filters/throttles
6. Multiple PEs may apply simultaneously — use **precedence** (rightmost = highest)
7. Avoid overcomplicating — simpler matrices are easier to monitor and tune
8. Use UDEs for external coordination (ETL completion signals, etc.)
