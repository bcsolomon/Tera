# Utility Management — Complete Reference

## Supported Utility Protocols

| Protocol | Utility Names |
|---|---|
| FastLoad | FastLoad, TPT Load operator, JDBC FastLoad, CSP Save Dump |
| MultiLoad | MultiLoad, TPT Update operator |
| MLOADX | TPT Update operator (extended mode) |
| FastExport | FastExport, TPT Export operator, JDBC FastExport |
| Backup/Restore | ARCMAIN, DSA (Data Stream Architecture) |

**Not managed as utilities:** TPump and TPT Stream operator use normal SQL protocol — manage them as SQL requests.

## Utility Session Architecture

| Utility | Control SQL Session | Auxiliary SQL Session | Utility Sessions |
|---|---|---|---|
| FastLoad, MultiLoad, FastExport | Yes | Yes | Yes |
| TPT Load/Update/Export | Yes | Yes | Yes |
| MLOADX | Yes | Yes | Yes (via SQL sessions) |
| JDBC FastLoad/FastExport | Yes | No | Yes |
| CSP Save Dump | Yes | No | Yes |
| ARCMAIN | Yes | No | Yes |
| DSA | Yes | No | No |

## Internal Utility Throttle Limits

These are ALWAYS enforced by the system, regardless of user-defined throttles.

| Rule | Limit | Action | Utilities Covered |
|---|---|---|---|
| FastLoad+MultiLoad+FastExport | 60 | Delay | All FL, ML, FE (Teradata + non-conforming) |
| FastLoad+MultiLoad | 30 | Delay | All FL + ML utilities |
| FastLoad | 30 | Delay | All FL utilities |
| MultiLoad | 30 | Delay | All ML utilities |
| MLOADX | 30 (or 120 if enabled) | Delay | TPT Update operator (extended) |
| FastExport | 60 | Delay | All FE utilities |
| Backup/Restore | 350 | Delay | ARCMAIN + DSA |

### MLOADX Higher Limit (15.0+)

- Default: MLOADX shares the 30-job limit with traditional MultiLoad
- **Optional:** Enable separate MLOADX limit up to 120 concurrent jobs
- Internal AWT resource limits prevent excessive AWT consumption even at 120 jobs

## User-Defined Utility Throttles

Created via Workload Designer under the Sessions icon (displayed as "Utility Limits").

### Configuration

| Parameter | Description |
|---|---|
| Utility Names | Which utilities to throttle (one or more protocols) |
| Concurrency Limit | Maximum concurrent jobs |
| Action | Delay or Reject |
| State | Can vary limits by state in state matrix |

### Examples

```
Rule 1: Allow 10 FastLoad utilities (any kind) with delay
Rule 2: Allow 2 TPT Updates with reject
Rule 3: Allow 15 ARCMAIN+DSA with delay
Rule 4: Allow 40 MLOADX jobs with delay
Rule 5: Allow 5 DSA Backup jobs with delay
Rule 6: Allow 3 DSA Restore jobs with delay
```

**Non-conforming utilities:** Delay option is NOT supported — TASM always rejects non-conforming utilities that exceed limits, even if the rule specifies Delay.

## Default Utility Session Rules

These rules centrally control how many sessions each utility job can connect. They **override** MINSESS/MAXSESS parameters in utility scripts.

### Session Count Formulas

| Protocol | Medium/Default Data Size (Base) | Small | Large |
|---|---|---|---|
| FastLoad + MultiLoad | If NumAMPs ≤ 20: NumAMPs; else Min((20+NumAMPs/20), 100) | Base × 0.5 | Min(Base × 1.5, NumAMPs) |
| CSP Save Dump | If NumNodes ≤ 10: 4/node; ≤ 20: 3/node; < 50: 2/node; else 1/node | N/A | N/A |
| FastExport | If NumAMPs ≤ 4: NumAMPs; else 4 | Base × 0.5 | Min(Base × 1.5, NumAMPs) |
| ARC | If NumAMPs ≤ 20: 4; else Min((4+NumAMPs/50), 20) | Base × 0.5 | Min(Base × 1.5, 2×NumAMPs) |
| DSA | 1 | N/A | N/A |

### Data Size Selection

Use query band to select data-size-specific defaults:

```sql
SET QUERY_BAND = 'UtilityDataSize=LARGE;' FOR SESSION;
-- or SMALL, MEDIUM
-- If not specified, Medium/Default is used
```

### Maximum Session Limits

| Protocol | System Maximum |
|---|---|
| FastLoad, MultiLoad, FastExport | NumAMPs |
| ARCMAIN | 2 × NumAMPs |
| BAR Max Build Processes | 5 |

### Default Rules Cannot Be Deleted

Default rules can be modified but not removed. Additional user-defined rules can be created.

## User-Defined Utility Session Rules

Create additional session rules with classification criteria for specific users, applications, or job types.

### Available Classification Criteria

- Utility Name
- Request Source (user, account, application, profile)
- Query Band
- Data Size (via UtilityDataSize query band)

### Example: Limit MultiLoad Sessions for User1

```
Rule: "ML-User1"
  Utility: Stand Alone MultiLoad
  User: User1
  Max Sessions: 2
```

### Evaluation Order

1. User-defined rules are ALWAYS evaluated before default rules
2. Within user-defined rules, DBA controls order via drag-and-drop
3. More restrictive criteria should be placed higher in evaluation order
4. First matching rule wins

## Utility Workload Throttles

A utility workload uses Utility as a classification criterion. Enables more granular concurrency control.

### Unit of Work Concept (13.10+)

A utility unit of work (UOW) spans the entire load/unload process:

```
UOW Start: CHECK WORKLOAD → BEGIN LOADING/MLOAD/EXPORT
UOW End: END LOADING/MLOAD/EXPORT

Within the UOW:
- Only the first SQL statement classifies via Utility criterion
- Subsequent statements auto-assigned to the same utility workload
- Throttle counter incremented at UOW start, decremented at UOW end
```

For backup/restore: the entire script is treated as one UOW.

### Classification Criteria Available for Utility Workloads

| Supported | Not Supported |
|---|---|
| Request Source (who) | Query Characteristics (what) |
| Target: Database, Table, View | Target: Macro, Stored Procedure |
| Query Band | Service Level Goals |
| Utility Type | — |

### Example: Limit User1 to 2 FastExport Jobs

```
Workload: WD-User1-FE
  Classification: User = User1 AND Utility = FastExport
  Throttle: Limit = 2, Action = Delay
```

### Pre-13.10 vs 13.10+ Behavior

Before TTU 13.10, workload throttles on utilities had issues:
- Multiple delays during load/unload process
- Active utility count could exceed limits

After TTU 13.10: treated as single UOW — throttles work correctly.

Pre-TTU 13.10 utilities submitted to a 13.10+ server behave as pre-13.10 (no UOW enhancement).

## AWT Resource Limits

Control AWT consumption by utility jobs beyond simple concurrency limits.

### How It Works

1. Utility job is submitted
2. TASM checks the job's AWT requirement against all applicable AWT resource limits
3. If any limit would be exceeded → job is delayed (or rejected based on throttle action)
4. ALL applicable limits must be satisfied before the job can run

### AWT Requirements by Protocol

| Protocol | AWTs per Job |
|---|---|
| FastLoad Phase 1 | 1 per session |
| FastLoad Phase 2 | 1 (total) |
| MultiLoad Acquisition | 1 per session |
| MultiLoad Application | 2 per AMP |
| FastExport | 1 per session |
| DSA Backup | 1-3 initially |
| DSA Restore | 3 initially, up to 55 dynamically |
| MLOADX | 1 per session |

DSA Restore: TASM initially assumes 3 AWTs, but actual usage (up to 55) is dynamically updated and affects the NEXT utility job assessment.

### Configuration

Created in Workload Designer under Throttles → Resource Limits tab.

### Multi-Rule Scenarios

```
Rule 1: 45% of AWTs for ALL DSA Restore jobs (system-wide)
Rule 2: 15% of AWTs for DSA Restore from User A

Scenario 1: Only User A's DSA Restore jobs running
  → Cannot exceed 15% (Rule 2 is the limiting factor)

Scenario 2: Other users consuming 45% of AWTs for DSA Restore
  → User A's new job delayed — Rule 1 limit reached
  → Even though User A is within their 15% limit
```

### AWT Release and Delayed Jobs

When delayed due to AWT limits:
- Jobs are released when other utilities free AWTs (e.g., FastLoad transitions from Phase 1 to Phase 2)
- The throttle delay/reject action of the applicable utility throttle determines behavior

## Excluding Utilities from System Throttles

System throttles should NOT manage utilities. Two approaches to exclude:

### Approach 1: Exclude by Application Name

```
System throttle classification:
  User = User1
  Exclude Application = FASTLOAD, MULTILOAD
```

### Approach 2: Exclude by Query Band

Every utility job carries a query band with its utility name. Effective for channel-attached utilities where application names may not be available.

```
System throttle classification:
  Query Band: UtilityName NOT IN ('FASTLOAD', 'MULTILOAD', ...)
```

## Utility Classification in Workloads

### Console Utility Mapping

Console utilities (CheckTable, UpdateSpace, etc.) map to predefined workloads based on internal mappings. The DBA can redirect specific console utilities to custom workloads.

### Recommendations for Utility Workloads

1. Always include Utility type as classification criterion in utility workloads
2. Place utility workloads HIGH in evaluation order to prevent utility requests from classifying to SQL workloads
3. Use utility throttles for system-level limits; workload throttles for per-user/application limits
4. Do NOT use system throttles for utilities — use dedicated utility throttles
5. Ensure TTU 13.10+ for correct UOW-based throttle behavior

## Disabling Utility Session Rules

**Last resort only.** Set DBS control field `DisableTDWMSessionRules = TRUE` to revert to pre-13.10 session behavior. All other TASM features (filters, throttles, workloads, events) remain active.

Use case: Environments where most utility scripts already specify tuned session counts, making individual session rules unmanageable.
