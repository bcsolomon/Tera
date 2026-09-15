# Throttles and Filters — Complete Reference

## Throttle Hierarchy

Throttles control concurrency at multiple levels. A request can be under control of multiple throttles simultaneously and must satisfy ALL throttle counters before it can run.

```
Throttle Types (evaluated independently):
├── Query Session Limits (reject only — cannot delay logons)
├── System Throttles (workload-independent, broad scope)
│   ├── Collective — single counter for all matching requests
│   ├── Individual — per-object counter (e.g., per account)
│   └── Member — per-user counter within the object
├── Virtual Partition Throttles (TASM only — per VP concurrency)
├── Workload Throttles (per-workload concurrency)
└── Group Throttles (shared limit across 2+ workloads)
```

## System Throttle Rule Types

### Collective

All qualifying requests share a single counter. Least granular.

```
Example: Limit all sandbox queries to 10 concurrent
→ Classification: Account = 'Sandbox*'
→ Rule Type: Collective
→ Limit: 10, Action: Delay
```

### Individual

Each qualifying object gets its own counter. More granular.

```
Example: Limit each account to 5 concurrent queries
→ Classification: Account = 'Mktg', 'Sales', 'Finance'
→ Rule Type: Individual
→ Limit: 5, Action: Delay
→ Result: Mktg can run 5, Sales can run 5, etc. independently
```

If only a single object is associated with the throttle, Individual and Collective behave identically.

### Member

Each user within the qualifying objects gets their own counter. Highest granularity.

```
Example: Limit each user to 3 concurrent queries
→ Classification: Account = 'Sandbox*'
→ Rule Type: Member
→ Limit: 3, Action: Delay
→ Result: User A can run 3, User B can run 3, etc.
```

Use member throttles for per-user fairness — prevents one user from monopolizing a workload's throttle slots.

## Workload Throttles

Primary tool for concurrency control. Defined as part of the workload definition.

| Setting | Options |
|---|---|
| Limit | Max concurrent requests in this workload |
| Action | Delay (queue) or Reject |
| Group Participation | Optional — join a group throttle |

### Key Behaviors

- Controls ALL requests that classify to the workload
- Cannot be enabled/disabled independently — always active with the workload
- Requests within stored procedures are managed individually
- Already-running queries can never be returned to a delay queue
- Bypassed users are NOT exempt from workload throttles

### Workload Throttle + Demotions

When a query demotes from WD-High to WD-Low:
1. WD-High throttle counter decremented
2. WD-Low throttle counter incremented
3. Demoted query is NEVER delayed — it's already executing
4. WD-Low may temporarily exceed its limit

## Group Throttles

Combine 2+ workload throttles under a shared limit. Solves two problems:

### Problem 1: Demotions Exceeding Total Concurrency

```
Without Group Throttle:
  WD-Medium (limit=6): 6 active → 2 demote to WD-Long
  WD-Long (limit=3): 3 active + 2 demoted = 5 active
  Total: 4 + 5 = 9 (exceeded intended limit of 9)

With Group Throttle (limit=9):
  WD-Medium: 4 active (freed 2 slots but group throttle blocks new releases)
  WD-Long: 5 active
  Total: 9 (group throttle holds the line)
```

### Problem 2: Sharing Unused Slots

```
Without Group Throttle:
  WD-Medium (limit=6): only 3 active — 3 slots wasted
  WD-Long (limit=3): 3 active — at limit, cannot use WD-Medium's spare slots

With Group Throttle (limit=9, WD-Medium limit=8, WD-Long limit=6):
  WD-Medium: 3 active
  WD-Long: 6 active (uses unused group capacity)
  Total: 9 (group throttle satisfied)
```

### Group Throttle Rules

- All member workloads must have their own workload throttle defined
- Only workload throttles with delay action can participate
- A workload can belong to only ONE group throttle
- All member workloads must be in the same virtual partition (TASM)
- Group throttle has no classification criteria — relies on member workloads
- When both group and workload throttle have delayed queries, the workload with the longest-waiting query releases first

## Query Session Limits

Session-based system throttles that limit logon concurrency.

| Feature | Behavior |
|---|---|
| Action | Reject only — cannot delay logons |
| Classification | Source criteria only (account, profile, IP address, user) |
| Scope | Cannot use target or query characteristics criteria |
| Global | A session throttle with no classification applies to ALL logon attempts |
| Existing Sessions | Already-active sessions are never logged off |

## Delay Queue Mechanics

### Queue Ordering Options

| Option | Behavior |
|---|---|
| Time-ordered (FIFO) | First delayed query is released first |
| Priority-ordered | Higher priority workload's query released first |

### Queue Capacity

The delay queue can hold approximately 40,000 queries (up to 16 MB).

### Blocker Actions

Sessions on the delay queue may hold locks if part of a multi-statement transaction. TASM checks at regular intervals:

| Action | Behavior |
|---|---|
| Log | Record the blocking situation |
| Abort | Abort the blocked request |
| Release | Release the blocked request to run |

Default: Check every cycle (configurable), take action after 1 cycle.

### Prevent Mid-Transaction Throttle Delays

When enabled, TASM will NOT delay queries within transactions that hold locks higher than access locks. Prevents deadlocks from throttled in-transaction requests.

## Flex Throttles (TASM 16.0+)

Auto-release queries from the delay queue when system resources are underutilized.

### Configuration

| Setting | Description |
|---|---|
| AWT Threshold | Available AWTs above which queries can be released |
| CPU Threshold | CPU utilization below which queries can be released |
| Flex Action Interval | Pause between release actions to let system adjust |
| Max Queries Released | Upper limit per flex action cycle |
| Evaluation Mode | Assess impact without actually releasing queries |

### Behavior

- Only overrides workload throttles with non-zero limits
- Honors all other throttles (system, group, VP)
- Can be enabled/disabled per state
- Delay queue ordering (time or priority) is honored
- Uses same Available AWT algorithm as the AvailableAWTs system event

### Monitoring Flex Throttles

DBQL: Released queries are flagged in their DBQLogTbl entry.

TDWMEventLog entries (EventCode=3195):

| SubCode | Meaning |
|---|---|
| 1 | Flex Throttle feature enabled |
| 2 | Flex Throttle feature disabled |
| 3 | WDIds using Flex Throttles in current state |
| 4 | Released AAAA OF BBBB Left CCCC (actual release) |
| 5 | Released AAAA OF BBBB Left CCCC (evaluation mode) |

## System Filters

Reject queries BEFORE execution based on estimated cost/characteristics.

### Classification Criteria

Same criteria as workload classification:
- Request Source (Who): Account, User, Application, Profile, IP, Query Band
- Target (Where): Database, Table, View, Macro, SP, UDF
- Query Characteristics (What): Statement type, AMP count, est. processing time, join type, FTS, row estimates
- Sub-criteria: Unconstrained product join, full table scan, data block selectivity

Same-type criteria are OR'd; different-type criteria are AND'd.

### Warning Mode

| Mode | Behavior |
|---|---|
| Active | Query is rejected; user receives error |
| Warning Only | Query runs normally; `WarningOnly='T'` logged in DBQL |

**Best practice:** Deploy new filters in warning mode for 1-2 weeks to assess impact before enabling rejection.

### Common Filter Rules in Production

```
Filter 1: Reject unconstrained product joins
  Criteria: Product Join = Unconstrained
            AND Est. Processing Time > 200 hours

Filter 2: Reject large unconstrained product joins by row count
  Criteria: Product Join = Unconstrained
            AND Step Row Count > 1,000,000,000

Filter 3: Reject full table scans on very large tables
  Criteria: Full Table Scan = Yes
            AND Table Row Count > 1,000,000,000
  Exclude: Specific admin users

Filter 4: System quiesce for maintenance
  Criteria: (none — applies to all requests)
  Effect: Reject all new requests; existing queries complete naturally
```

### Filter State Control

Filters can be enabled/disabled per state in the state matrix.

## Bypass Privileges

| Bypass Scope | Honors Bypass? |
|---|---|
| System throttles | Yes |
| Virtual partition throttles | Yes |
| System filters | Yes |
| Workload throttles | **No** |
| Group throttles | **No** |

- Users DBC and TDWM are automatically bypassed
- Bypass is all-or-nothing — applies to ALL system-level rules
- **Recommendation:** Use sparingly; avoid granting bypass broadly

## Throttle Recommendations

1. **Lead with workload throttles**, supplement with system throttles
2. **Never throttle tactical workloads** — they must run immediately
3. Throttle Low and Medium timeshare workloads to prevent AWT depletion
4. Apply **system member throttles** (limit 1-3 per user) for fairness
5. **Exclude utilities** from system throttles (use utility throttles instead)
6. Use **group throttles** when demotions could exceed application concurrency goals
7. Start conservatively (higher limits) and tighten gradually based on DBQL analysis
8. Monitor delay queue depth via `DBC.TDWMSummaryLog` — look for `DelayedCount`
9. Use **flex throttles** for 1-2 important workloads to prevent under-utilization
10. Stored procedures: nested calls count as separate requests against throttle limits
