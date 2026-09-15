# Workload Classification & Priority Mechanics

> Sources: TDN0001728 — Teradata Integrated Workload Management; TDN0001776 — Teradata Active System Management; 541-0008867 — Priority Scheduler

> **Configuration Method:** Workload classification is configured via **Viewpoint Workload Designer** (GUI) or **TASM API** (RQC commands). There is NO SQL DDL (no CREATE/ALTER/DROP WORKLOAD statements). Wildcard patterns use `*` (any chars) and `?` (single char) — NOT SQL `%` or `_`.

## Classification Criteria Types

### Request Source ("Who")

Account string, Account name, Application, Client IP address, Client ID, Username, Profile.

Starting in 15.10: Profiles and Users can be OR'd (optional; can still AND them).

#### Wildcard Patterns in Classification

All Request Source criteria support wildcard matching:

| Criterion | Wildcard Example | Meaning |
|---|---|---|
| Account string | `$TA*`, `$H*`, `$L*`, `$M*`, `$R*` | Match accounts starting with prefix |
| Username | `MKTG*` | Match users starting with MKTG |
| Client IP address | `*.*.*.*` | Match ALL IP addresses |
| Client IP address | `10.1.*.*` | Match a specific subnet |
| Client IP address | `192.168.1.?` | `?` matches single character |

- `*` matches zero or more characters
- `?` matches exactly one character
- Multiple patterns within the same criterion type are OR'd

**Examples (tasm_api syntax):**
```
RQC: ADD ACCTSTR $TA*, $H*, $L*, $M*, $R*   -- account string wildcards
RQC: ADD CLADDR *.*.*.*                       -- match all client IPs
RQC: ADD CLADDR 10.1.*.*                      -- match subnet
RQC: ADD USERNAME MKTG*                       -- username wildcard
```

### Target ("Where")

Database, Table, View, Macro, Stored procedure, UDFs/UDMs, External Server Name.

Sub-criteria on data objects: full table scan, join type, step row count, estimated step processing time, data block selectivity.

**Critical rule:** Different Target types (e.g., Database + Table) are always **OR'd** — matching either one satisfies the target criterion. This differs from Request Source where different types are AND'd. Target criteria as a whole are AND'd with Request Source ("Who") criteria — so `User=Payroll AND Database=Finance` means the request must come from Payroll user AND target the Finance database.

### Query Characteristics ("What")

Statement type (DDL, DML, Select, COLLECT STATISTICS), AMP limits (single/few-AMP), step/final row count, estimated processing time, min/max step time, join type, full-table scan, estimated memory usage, IPE attribute.

**Note:** Statement type is a **Query Characteristics ("What")** criterion, NOT a Target ("Where") criterion.

### Query Band

Supplemental app-provided metadata (request type, web page origin, interactive vs. non-interactive). Set via `SET QUERY_BAND = 'Job=t900b;Report=Weekly;Universe=West;' FOR SESSION` (or FOR TRANSACTION). Add a Query Band criterion in Workload Designer and specify the key-value pair to match.

**IMPORTANT — Query Band OR Rule:** Multiple query band criteria within the same workload are **OR'd** — matching ANY one key/value pair satisfies the query band criterion. This is an EXCEPTION to the normal "different Who types are AND'd" rule. For example, if a workload specifies `Job=t900b` and `Report=Weekly`, a request matching EITHER one classifies to that workload.

> **⚠️ COMMON MISTAKE:** Do NOT claim that different query band names are AND'd. That is WRONG. Query band criteria are always OR'd regardless of whether the names differ. Example: a workload with criteria `Job=t900b` and `Report=Weekly` matches a request that has ONLY `Job=t900b` (without Report), because query band criteria are OR'd.

SET QUERY_BAND triggers immediate **re-classification** of the session workload. Query band classification works for both session and request classification.

### Utility

FastLoad, MultiLoad, MLOADX, FastExport, DSA Backup/Restore.

## Combining Multiple Criteria — AND/OR Rules

| Criteria Relationship | Behavior |
|---|---|
| Same type (e.g., User A, User B, User C) | **OR'd** — match any one |
| Different types in Who (e.g., User + Account + Application) | **AND'd** — must match all |
| Profile + User (15.10+) | **Optionally OR'd** |
| Different Target types (Database + Table + View) | **Always OR'd** by the database engine |
| Who + Where + What categories | **AND'd** across categories |
| Multiple Query Band key/value pairs | **OR'd** — matching ANY one satisfies (exception to Who AND rule) |

### Critical Rule: Target (Where) Types Are Always OR'd

Contrary to how Who criteria work, **Where criteria representing different types of target objects (database, table, view, stored procedure, etc.) are ALWAYS OR'd together by the database**. For example, if a workload has classification for a specific database AND a specific table, a request only needs to match ONE of those target objects to classify to that workload — it does NOT need to match both.

This is a hardcoded database behavior — even if Viewpoint Workload Designer displays "AND" between different target types, the database internally treats them as OR. (This UI discrepancy is a known issue to be fixed in a future release.)

### Summary of AND/OR Logic

```
Within Who:   same type = OR  |  different types = AND  (except Profile+User can be OR'd)
Within Where: ALL types = OR  (always, regardless of UI display)
Within What:  same type = OR  |  different types = AND
Query Band:   ALL criteria = OR  (any one key/value match satisfies; this is an EXCEPTION to Who AND rule)
Across categories (Who + Where + What): AND
```

## Session vs. Request Classification

> **CRITICAL FACTS — Always include when explaining session vs. request classification:**
> 1. Session classification determines **parser priority** (how the parser prioritizes the request); request classification determines **execution priority** (how the request executes on AMPs). Use these exact terms.
> 2. **PE-only requests** (CALL, SHOW, HELP) always run in the **session workload** — they are never independently request-classified because they have no AMP steps.
> 3. **SET QUERY_BAND triggers re-classification** of the session workload immediately. At **transaction completion**, the session re-classifies back to its baseline workload.
> 4. Request-level criteria include **optimizer plan data**: estimated processing time, AMP count, join type, full-table scan, step row count.

| Aspect | Session Classification | Request Classification |
|---|---|---|
| When | At logon time | After parsing each request |
| Criteria used | Only Request Source ("Who") | All criteria + optimizer plan |
| Re-classification | On SET QUERY_BAND, on transaction completion | Every request |
| Effect | Determines parser priority, logged in SessionWDID | Determines execution priority, logged in FinalWDID |
| PE-only requests | CALL, SHOW, HELP run in session workload | N/A — no AMP steps |
| DBQL field | `DBC.DBQLogTbl.SessionWDID` | `DBC.DBQLogTbl.FinalWDID` |

### Key Re-classification Rules

- **SET QUERY_BAND triggers session re-classification** — the session is immediately re-evaluated against all workloads using the updated query band criteria
- When a query band goes out of effect (transaction completion), the session is re-classified again back to its baseline workload
- Multiple query band criteria within a single workload are **OR'd** — matching any one query band key/value pair satisfies that criterion
- The parser priority for subsequent requests changes immediately after re-classification

### PE-Only Requests

Requests that use only the Parsing Engine (PE) and never dispatch to AMPs:
- CALL (stored procedure invocation)
- SHOW (display object DDL)
- HELP (metadata queries like HELP TABLE, HELP DATABASE)

These always run in the **session workload** and are never independently classified to a request workload.

### Session Classification Algorithm

1. Sort all workloads by priority (highest first): tier first, then highest global weight within tier
2. Select first workload where session logon info matches ALL Who criteria
3. Non-Who criteria (est. processing time, etc.) are ignored at session logon time
4. If no match → assigned to WD-Default

## Workload Evaluation Order

- Requests compared against workloads in DBA-specified order; **first match wins**
- New workloads placed just above WD-Default — always adjust after adding
- More specific workloads higher, more general lower
- Utilities and DBA/BAR workloads should be highest

### Evaluation Order Pitfall

```
WD-A: User=Payroll              ← higher
WD-B: User=Payroll AND est_time < 5s  ← lower (never reached!)
```

Fix: move WD-B above WD-A.

## Priority Hierarchy

### Three Workload Management Methods

| Method | Purpose | Resource Behavior |
|---|---|---|
| **Tactical** | Sub-second single/few-AMP queries | Highest priority; auto-expedited; reserved AWTs |
| **SLG Tier** (1–5 tiers) | All-AMP tactical, SLG-critical work | Workload allocation (share %) within tier |
| **Timeshare** (Top/High/Medium/Low) | Everything else | Fixed access rates: 8×/4×/2×/1×; blind to concurrency |

### Timeshare Access Rates

| Level | Access Rate | Resource Relative to Low |
|---|---|---|
| Top | 8 | 8× |
| High | 4 | 4× |
| Medium | 2 | 2× |
| Low | 1 | 1× (base) |

**Key property:** Concurrency does NOT dilute the rate. Each Top request always gets 8× what each Low request gets, regardless of how many are running.

### Timeshare Resource Calculation Example

With 2 Top, 3 High, 1 Medium, 6 Low requests:

| Level | Rate × Count | Per-Request Share |
|---|---|---|
| Top | 8 × 2 = 16 | 8/36 = 22.2% |
| High | 4 × 3 = 12 | 4/36 = 11.1% |
| Medium | 2 × 1 = 2 | 2/36 = 5.6% |
| Low | 1 × 6 = 6 | 1/36 = 2.8% |
| **Total** | **36** | |

## Tactical Workload Management

### Mandatory Tactical Exceptions

| Parameter | Default | Notes |
|---|---|---|
| CPU per Node | 2 seconds | Don't set below 1 second (overhead) |
| CPU sum over all nodes | CPU_per_node × num_nodes | Static after save; won't auto-adjust on reconfig |
| I/O per Node | 200 MB | |
| I/O sum over all nodes | IO_per_node × num_nodes | Static after save |

### Demotion Behavior

- Per-node threshold exceeded → demoted on **that node only**
- Sum-over-all-nodes exceeded → demoted **across all nodes**
- Request can run in different workloads on different nodes (skew scenario)
- Demoted request takes reserved AWT until current step completes
- DBQL fields: `TacticalCPUException`, `TacticalIOException`

### Reserved AMP Worker Tasks

- Specified in Workload Designer → General → Limits/Reserves
- Applied to WorkEight and WorkNine message work types
- WorkTen always has fixed reserve of 2
- Shared across all VPs, first-come-first-served
- Upper limit: 20 reserved AWTs
- Only set above 0 if AWT shortage is impacting tactical performance

## Global Weights

### What Global Weights Represent

- The actual % of platform resources allocated to a workload
- Used to order internal queues (AWT message queue)
- Tactical workloads excluded (super-priority)
- Based on definitions, not runtime activity/concurrency
- All global weights sum to 100% (unless WM COD is active)

### SLG Tier Global Weight Calculation

Walk upward in the hierarchy, multiplying allocations:

$$\text{Global Weight} = \text{Tier\_Alloc} \times \text{Parent\_Remaining} \times \cdots \times \text{VP\_Alloc} \times \text{COD\_Pct}$$

Example: MktgQry on SLG Tier 3 with 40% allocation:

$40\% \times 50\% \times 65\% \times 100\% \times 100\% = 13\%$

### Timeshare Global Weight Calculation

Example with 1 Top, 2 High, 2 Medium, 2 Low WDs, Timeshare receiving 9.8%:

| Level | Rate × WDs | % of Timeshare | Global Weight per WD |
|---|---|---|---|
| Top | 8 | 36.4% | 3.6% |
| High | 8 | 36.4% | 1.8% |
| Medium | 4 | 18.2% | 0.9% |
| Low | 2 | 9.1% | 0.4% |

### Key Gotcha

SLG Tier workloads can have a **lower** global weight than Timeshare workloads. A canary query can run faster in Timeshare than SLG Tier if the SLG Tier allocation is low.

## Service Level Goals (SLGs)

### SLG Types

- **Response time at service %:** e.g., 2 seconds or less 99% of the time
- **Throughput:** e.g., 1000 queries per hour

### Establishing Initial SLGs

- Known business need: set from observed user behavior (e.g., 4-sec prevents kill-restart)
- Unknown: draw initial "line in the sand" from typical actuals (1×–2× typical), then adjust
- Monitor via Viewpoint Workload Monitor portlet and DBQL / TDWMSummaryLog

## Special Users

### User DBC

- Super-user; cannot be given a profile; cannot be granted secure zone access
- Sessions classified to workloads same as any other user
- Primarily for admin tasks only DBC can perform

### User TDWM

- Internal workload management operations (rule set changes, event logging)
- Exclude from MRT settings; don't apply restrictive WLM rules

### Minimum Response Time (MRT / Hold Query Response)

- Optional per-workload setting for consistent response times
- Response held at AMP; charged against spool; AWTs released before hold
- DBQL field: `MinRespHoldTime`
- Don't use with TDWM or DBSSETUPDBA users

## Classification Best Practices

1. Lead with Request Source and/or Query Band criteria
2. Keep total workloads manageable (5–20)
3. Avoid long include/exclude lists; use accounts, wildcards (`UserID='MKTG*'`)
4. Don't rely on exception management for classification
5. Use evaluation order to manage complex logic
6. Add utilities to WDs with Utility criteria
7. Reserve WD-Default for unexpected requests; set low priority
8. Only single/few-AMP, highly-tuned queries in tactical
9. Never assign load utilities to tactical workloads
