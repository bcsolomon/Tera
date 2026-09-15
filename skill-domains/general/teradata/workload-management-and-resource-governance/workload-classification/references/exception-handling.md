# Exception Handling — Complete Reference

## Exception Overview

Exceptions detect atypical conditions AFTER a query begins execution. They consist of:
1. **Criterion** — a measurable metric (CPU time, skew, spool, etc.)
2. **Threshold** — the value that triggers the exception
3. **Action** — what happens when the threshold is exceeded
4. Optional **qualification time** — sustain period for qualified criteria

## Exception Criteria Types

### Threshold-Based Criteria (Trigger Immediately)

| Criterion | Unit | Description |
|---|---|---|
| CPU Time | Seconds | Total CPU seconds consumed |
| Elapsed Time | Seconds | Wall-clock time since request started |
| Spool Rows | Count | Rows written to spool |
| Spool Size | Bytes | Total spool space consumed |
| Blocked Time | Seconds | Time waiting for locks |

### Qualified Criteria (Require Sustained Condition)

| Criterion | Unit | Qualification |
|---|---|---|
| CPU Milliseconds per I/O | ms/IO | Sustained over CPU qualification seconds |
| CPU Skew | % or difference | Sustained over CPU qualification seconds |
| I/O Skew | % or difference | Sustained over CPU qualification seconds |

## Exception Actions

| Action | Effect | Notes |
|---|---|---|
| Change Workload | Move request to a lower-priority WD | Most common; preserves the query |
| Abort | Kill the request immediately | Strong action; use carefully |
| Alert (Notify) | Send notification to admin | Informational; no impact on query |
| Log | Record exception in TDWMExceptionLog | Always happens for any exception |

Multiple actions can be combined (e.g., Change WD + Alert).

## Tactical Exceptions (Mandatory)

All tactical workloads automatically receive these exceptions — they CANNOT be disabled.

### CPU Exceptions

| Threshold | Default | Scope |
|---|---|---|
| CPU per Node | 2 seconds | Per-node check |
| CPU Sum Over All Nodes | NumNodes × CPU-per-Node | System-wide check |

### I/O Exceptions

| Threshold | Default | Scope |
|---|---|---|
| I/O per Node | 200 MB physical bytes | Per-node check |
| I/O Sum Over All Nodes | NumNodes × IO-per-Node | System-wide check |

### Tactical Exception Behavior

- **Per-node trigger:** Request is demoted on THAT node only when CPU-per-Node or IO-per-Node threshold is reached
- Different nodes may run the request in different workloads (skewed work on one node may exceed threshold while others don't)
- **Sum-over-all-nodes trigger:** Request is demoted on ALL nodes; notification actions fire
- DBQL logging: `TacticalCPUException` = count of nodes hitting CPU threshold; `TacticalIOException` = count of nodes hitting I/O threshold

### Tactical Exception Recommendations

- Keep thresholds low — at or near defaults
- Never set CPU exception below 1 second
- After system reconfig (add/remove nodes), recheck sum-over-all-nodes values — they do NOT auto-adjust
- Multiple tactical workloads can have DIFFERENT thresholds (e.g., stricter for call-center, lenient for dashboards)

## CPU Milliseconds per I/O (Product Join Indicator)

Detects queries with unusually high CPU relative to logical I/O — classic sign of unconstrained product joins.

### Calculation

```
CPU ms/IO = (TotalCPUTime_seconds × 1000) / TotalIOs
```

### Typical Values

| Pattern | CPU ms/IO Range |
|---|---|
| Typical queries | 1–2 |
| Legitimate small-table product join | 2–3 |
| High CPU queries (potential problem) | > 3 |
| PDCR report trigger threshold | 6 (5400 and below), 3 (5450 and above) |

### Recommendation

- Start with a threshold of **5** for exception detection
- Fine-tune by analyzing workload patterns in DBQL
- Always specify accumulated CPU qualification seconds (see below)
- The TASM exception checks intervals, NOT the entire query — interval-level values can be higher than query-level averages

## Skew Detection

### Skew as Percentage (Preferred)

```sql
CPU Skew % = ((HighAMPCPU - AvgAMPCPU) / HighAMPCPU) × 100
I/O Skew % = ((HighAMPIO  - AvgAMPIO)  / HighAMPIO)  × 100
```

- Value of 0% = no skew
- Higher values = worse skew
- **Recommended threshold:** 25–30%

### Skew as Difference

```sql
CPU Skew Diff = HighAMPCPU - AvgAMPCPU
I/O Skew Diff = HighAMPIO  - AvgAMPIO
```

- Value of 0 = no skew
- Less desirable than percentage for detection — can give misleading results on short steps

### Skew Impact Formula

```
Skew Impact = ((HighAMP - AvgAMP) / AvgAMP) + 1

Example: HighAMP=1000, AvgAMP=700
  Impact = ((1000-700)/700) + 1 = 1.43× (query runs 43% longer)
  Skew % = 30%
```

### Skew Detection Method

**Best approach:** Use skew percentage as primary, AND skew difference as secondary guard against false positives.

```
Example: Skew % > 30% AND Skew Diff > 50 CPU seconds
  qualified for at least 100 accumulated CPU seconds
```

### False Skew Scenarios

| Scenario | Problem |
|---|---|
| Very short step (3 CPU sec HighAMP, 2 avg) | 33% skew but only 1 sec difference — insignificant |
| Heavy concurrency | Limits metric accumulation; skew may not be meaningful |

### Detection Scope

- TASM checks skew per **request**, not per system
- Calculation considers only AMPs active in the request step (not all system AMPs)
- Group-AMP requests using equal CPU per involved AMP show 0% skew even if non-involved AMPs are idle
- Detection is **asynchronous** at the exception interval — NOT at step boundaries
- Synchronous (step-boundary) skew detection is disabled in favor of asynchronous

## Accumulated CPU Qualification Time

For qualified criteria (CPU ms/IO, skew), the condition must be **sustained** for a specified number of CPU seconds — NOT wall-clock seconds.

### Why CPU Seconds Instead of Wall-Clock

CPU qualification ensures consistent detection regardless of system load:
- Light system: Skewed query may complete quickly in wall-clock time
- Heavy system: Same query may run much longer in wall-clock time
- Using CPU seconds, both scenarios trigger at the same accumulated consumption

### How Qualification Works

1. Exception interval expires → TASM checks criterion
2. If threshold exceeded → qualification timer starts accumulating CPU seconds
3. Each subsequent interval: if threshold still exceeded → timer keeps accumulating
4. If threshold NOT exceeded in any subsequent check → timer resets to zero
5. When accumulated CPU qualification seconds reached → exception fires

### Example (3-AMP System, Skew % > 30%, Qualification = 500 CPU sec)

| Interval | AMP CPU (1/2/3) | Skew % | Accumulated | Action |
|---|---|---|---|---|
| 1 | 100/99/98 | 1% | 0 | — |
| 2 | 98/99/100 | 1% | 0 | — |
| 3 | 86/100/88 | 9% | 0 | — |
| 4 | 45/100/44 | 37% | 0 | Timer starts |
| 5 | 43/100/44 | 38% | 187 | Accumulating |
| 6 | 44/100/45 | 37% | 376 | Accumulating |
| 7 | 44/100/43 | 38% | 563 | **EXCEPTION** |

### Determining Qualification Time

Consider total CPU capacity: On a 10-node, 2-CPU system → 20 CPU seconds per wall-clock second. A busy query may use a fraction of that. Use DBQL and ResUsage analysis to determine appropriate qualification time values.

## Change-WD Consistency Best Practice

When exception action is "Change WD", enable the exception for **ALL planned environments**.

### Rationale

- Same query should always resolve to the same destination workload
- Simplifies accounting and monitoring
- Workload Designer issues a warning if not consistent

### Different Behavior by Time of Day

Use working values on the destination workload rather than disabling exceptions:

```
Daytime: Exception → Change to WD-Containment (Timeshare Low)
Nighttime: Exception → Change to WD-Containment (Timeshare Medium)
  → Same destination WD, different priority per planned environment
```

### Abort by Day, Contain by Night

Create TWO exceptions with same criteria:
1. `HiCPU-Abort`: action=Abort, enabled only for daytime PE
2. `HiCPU-Contain`: action=Change WD to WD-Containment, enabled for ALL PEs

Abort action has automatic precedence over Change WD when both are enabled.

## Exception Intervals

| Interval | Default | Range | Purpose |
|---|---|---|---|
| Exception Interval | 60 sec | 1–3600 sec | Time between asynchronous exception checks |
| Dashboard Interval | 60 sec | — | Workload summary accumulation period |
| Event Interval | 60 sec | 5/10/30/60 sec | Time between event occurrence checks |
| Logging Interval | 600 sec | — | Flush frequency for TDWM logs to disk |

Relationships: Dashboard interval must be a multiple of event interval; logging interval must be a multiple of dashboard interval.

## Exception Logging

### TDWMExceptionLog

One row per exception detected:

| Column | Content |
|---|---|
| ExceptionTime | When the exception was detected |
| UserName | User who submitted the request |
| WDName | Workload where request was running |
| ExceptionType | Type of criterion triggered |
| ExceptionValue | Actual value that triggered the exception |
| ExceptionAction | Action taken (abort, change WD, alert) |
| QueryId | Links to DBQLogTbl for full request details |

### DBQL Exception Columns

| Column | Description |
|---|---|
| TacticalCPUException | Count of nodes hitting tactical CPU threshold ('Y' if any) |
| TacticalIOException | Count of nodes hitting tactical I/O threshold ('Y' if any) |
| CPUDecayLevel | Timeshare decay level reached (0, 1, or 2) |
| IODecayLevel | I/O decay level reached |
| FinalWDID | Workload after any exception-driven changes |

## Timeshare Automatic Decay (Off by Default)

When enabled, applies to ALL timeshare workloads — cannot target specific WDs.

### Decay Stages

| Stage | CPU Trigger | I/O Trigger | Effect |
|---|---|---|---|
| No decay | < 100 sec | < 100 MB | Full access rate |
| 1st decay | 100 sec | 100 MB | Rate ÷ 2 |
| 2nd decay | 10,000 sec | 10,000 MB | Rate ÷ 4 (final) |

### Decay Considerations

- Same thresholds for all access levels (Top treated same as Low)
- Decay is per-node — different nodes may be at different decay levels
- If many queries in Low decay, they may hold locks/AWTs excessively long
- If most queries experience decay, relative priorities revert to pre-decay ratios
- **Recommendation:** Keep decay off for more predictable priority differentiation

## Exception Recommendations

1. **Lead with classification** — properly classify requests before relying on exceptions
2. Use exceptions to **catch misclassified** or unexpectedly expensive queries
3. Prefer **Change WD** over Abort for SLG workloads — preserves the work
4. Set **CPU ms/IO** threshold at 5 initially, tune based on workload analysis
5. Use **skew percentage** (25-30%) with qualification time (100+ CPU sec)
6. AND skew percentage with skew difference to avoid false positives
7. Monitor exceptions via `DBC.TDWMExceptionLog` and DBQL `FinalWDID` column
8. After system reconfig, always recheck tactical sum-over-all-nodes thresholds
