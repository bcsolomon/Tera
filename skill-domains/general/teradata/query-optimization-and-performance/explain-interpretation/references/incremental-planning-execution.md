# Incremental Planning and Execution (IPE)

> Source: TDN0009599-B01.1 — Incremental Planning and Execution in the Teradata Adaptive Optimizer (16.20 Feature Update 2)

## Overview

IPE is an adaptive optimization framework where the Teradata query optimizer can partially plan and execute a request incrementally. Runtime information is collected from each partial execution and fed back to the optimizer for dynamic planning of the next portion.

The optimizer repeats this cycle until the request completes:

1. **IDENTIFY** a fragment for partial execution
2. **GENERATE** an execution plan for the fragment
3. **EXECUTE** the fragment and **COLLECT** runtime information
4. **RECEIVE** runtime feedback
5. **USE** dynamic information for the next fragment

### Version History

| Version | Capabilities |
|---|---|
| 14.10 | IPE framework introduced; results feedback (single-row relation, scalar subquery) |
| 15.10 | Statistics feedback added (remote tables) |
| 16.00 | Improved dynamic statistics collection accuracy |
| 16.10 | Three new results feedback cases, two new statistics feedback cases, sampling-based collection |
| 16.20 FU2 | Multistatement request support, unique-join table feedback, dynamic plan caching |

## Feedback Types

### Results Feedback

Results feedback captures actual spool data values and uses them to rewrite and simplify the remaining portion of a request. Optimizations enabled:

- **Partition elimination** — substitute literal values into partitioning predicates
- **Join elimination** — remove joins when dimension values are known
- **Predicate simplification** — replace subqueries with constants, remove tautologies
- **Transitive closure** — derive new predicates from known values
- **Unsatisfiability propagation** — skip operations when EXISTS returns FALSE
- **Join index rewrite** — qualify sparse join indexes after values are known

**Example: Scalar subquery replacement**

```sql
-- Original
SELECT SUM(inv_quantity_on_hand)
FROM   inventory
WHERE  inv_date_sk BETWEEN (SELECT d_date_sk FROM date_dim
                            WHERE d_moy = 11 AND d_dom = 11 AND d_year = 2001)
                       AND (SELECT d_date_sk FROM date_dim
                            WHERE d_moy = 12 AND d_dom = 11 AND d_year = 2001);

-- After results feedback: subqueries replaced with actual values
SELECT SUM(inv_quantity_on_hand)
FROM   inventory
WHERE  inv_date_sk BETWEEN 2452225 AND 2452255;
-- If inventory is partitioned on inv_date_sk, partition elimination now applies
```

**Example: IN subquery with transitive closure**

```sql
-- Original
SELECT SUM(inv_quantity_on_hand)
FROM   catalog_sales, inventory
WHERE  cs_item_sk = inv_item_sk
  AND  cs_item_sk IN (SELECT i_item_sk FROM item
                      WHERE i_manufact_id IN (677, 940));

-- After results feedback: subquery replaced, transitive closure derives new predicate
SELECT SUM(inv_quantity_on_hand)
FROM   catalog_sales, inventory
WHERE  cs_item_sk = inv_item_sk
  AND  cs_item_sk IN (17564, 17565, 11282, 17707, 17319, 8572, 10473)
  AND  inv_item_sk IN (17564, 17565, 11282, 17707, 17319, 8572, 10473);
```

**Example: EXISTS returning FALSE — full query short-circuited**

```sql
-- If EXISTS subquery returns 0 rows, results feedback replaces it with 1=0
-- Unsatisfiability propagates up, eliminating ALL joins and subqueries
-- Final plan aggregates from an empty spool:
--   "We do an all-AMPs SUM step to aggregate from empty spool
--    with a condition of '(1=0)'"
```

### Statistics Feedback

Statistics feedback collects statistical information about spool data and updates the optimizer's cost estimates. Key statistics collected:

| Statistic | Description |
|---|---|
| **Row count** | Actual number of rows in the spool |
| **Spool size** | Physical size in bytes |
| **NUV** | Number of Unique Values (approximated via sampling) |
| **HMF** | High-Mode Frequency — frequency of the most common value |
| **High AMP frequency** | Max rows per AMP after redistribution |

#### Collection Mechanisms

| Method | When Used | I/O Overhead |
|---|---|---|
| **2-step** | RET or JIN steps; data collected before writing to spool | Negligible (in-memory) |
| **1-step** | Multi-step spools (e.g., UNION branches); reads from materialized spool | Can be noticeable |

#### Sampling

Sampling reduces CPU overhead at the cost of some accuracy:

- **2-step collection:** Every (100/p)th row sampled; default p=50%
- **1-step collection:** First p% of spool sampled; default p=10%
- Sampling stops early when additional data does not change estimates

## Eligibility and Qualification

### Eligibility Criteria

A request is eligible for IPE if it contains any of these constructs:

| Construct | Feedback Type | Description |
|---|---|---|
| Single-row relation | Results | Base table with equality on UPI or USI |
| Noncorrelated scalar subquery | Results (or statistics) | Subquery returning 0 or 1 row |
| Noncorrelated EXISTS/NOT EXISTS | Results | EXISTS subquery in WHERE clause |
| Noncorrelated IN/NOT IN/ANY/ALL | Results | Single-column subquery in WHERE clause |
| Single-row spool | Results | Derived table guaranteed to return 1 row (e.g., aggregation without GROUP BY) |
| Unique-Join Table (UJT) | Results | Base table joined on unique index with single-table conditions |
| Nonfolded derived table/view | Statistics (or results) | Derived table not folded into parent query |
| Remote table/table operator/function | Statistics | Data from remote servers (UDA) |
| Implicit subquery to aggregation | Statistics | Input spool to GROUP BY or analytic functions |

### Qualification Criteria

Even if eligible, IPE must pass cost thresholds:

1. **Estimated static plan execution time > 1 minute** (default `IPEMinCostEstThreshold=60000` ms)
2. **Parsing time < 10% of estimated execution time** (`IPEParsingPctThreshold=10`)
3. **Common Step Pruning savings < 5%** of static plan cost (`IPEMinCommonStepPruneThreshold=5`)
4. **Sufficient memory** — available segments exceed those used for static planning

## Fragmentation

Fragmentation determines what portions of the query to execute incrementally.

### Priority Rules

1. **Results feedback first** — can simplify the request and eliminate the need for subsequent statistics feedback
2. **Statistics feedback second** — only if no results feedback candidates remain

### Grouping Policy

- Preserves spool materialization order from the static plan
- Groups independent adjacent statistics targets into one fragment
- Avoids grouping all targets (prevents out-of-spool failures)

### Cross-Block Optimization

The optimizer may skip fragmentation when two operations (e.g., join + aggregation) need to be planned together. Example: if a Partial Group By (PGB) plan is the better option, fragmenting the join input would prevent the pre-aggregation.

## Dynamic Feedback Kind Switching

AMPs can override the optimizer's feedback request at execution time:

| Switch Direction | Trigger | Purpose |
|---|---|---|
| Results → Statistics | Spool > 32 KB or > 16 rows | Prevents parser overload from large data |
| Statistics → Results | Spool has 0 or 1 row | Allows simplification of trivial results |

EXPLAIN indicator:
```
The actual size of Spool 10 is 1,812 rows (55,296 bytes).
Dynamically switched to statistics feedback.
```

## Dynamic EXPLAIN

### EXPLAIN vs DYNAMIC EXPLAIN

| Modifier | Default Behavior |
|---|---|
| `EXPLAIN` / `STATIC EXPLAIN` | Shows static plan; notes IPE eligibility |
| `DYNAMIC EXPLAIN` | Executes intermediate fragments, shows dynamic plan |

**Important:** `DYNAMIC EXPLAIN` actually executes intermediate fragments. It may take time to complete and consumes resources.

### Cost Profile Constants for EXPLAIN

| Constant | Values | Effect |
|---|---|---|
| `ExplainMode` | 1 (default=STATIC), 2 (default=DYNAMIC) | Changes what `EXPLAIN` defaults to |
| `SecureExplain` | 1=Redact values, 2=Show values, 3=Block dynamic EXPLAIN | Controls visibility of feedback values |

### EXPLAIN Structure of a Dynamic Plan

```
The following is the dynamic plan for the request.
 ...
 6) We do an all-AMPs FEEDBACK RETRIEVE step ...
    The actual size of Spool 6 is 45,993 rows (1,655,748 bytes) ...
 7) We send an END PLAN FRAGMENT step for plan fragment 1.
 ...
 9) We do an all-AMPs FEEDBACK RETRIEVE step ...
    The actual size of Spool 10 is 1 row (24 bytes) ...
10) We send an END PLAN FRAGMENT step for plan fragment 2.
 ...
15) Finally, we send out an END TRANSACTION step.
```

Key indicators:
- **FEEDBACK RETRIEVE step** — where feedback is collected; "statistics" keyword means column-level stats
- **END PLAN FRAGMENT** — marks the boundary between fragments
- **"sample (50%) statistics go into Spool N"** — column-level dynamic statistics being collected

## DBQL Tracking

| Table | IPE-Relevant Fields |
|---|---|
| `DBC.DBQLogTbl` | `NumFragments` (>0 = dynamic plan used); `CacheFlag='R'` = IPE plan cached |
| `DBC.DBQLStepTbl` | `FragmentNum` for each step; step names `DSPRET` (feedback retrieve), `EPF` (end plan fragment) |
| `DBC.DBQLExplainTbl` | Full dynamic explain text |
| `DBC.DBQLXmlTbl` | XML with `NumFragments` attribute on Plan element |

### Useful DBQL Queries

```sql
-- Count IPE queries in a session
SELECT COUNT(*)
FROM   DBC.DBQLogTbl
WHERE  SessionId = 3179 AND NumFragments > 0;

-- Total CPU for a specific fragment
SELECT SUM(CPUTime)
FROM   DBC.DBQLStepTbl
WHERE  QueryId = 307184826029325025 AND FragmentNum = 1;

-- Count cached IPE plans
SELECT COUNT(*)
FROM   DBC.DBQLogTbl
WHERE  CacheFlag = 'R' AND NumFragments > 0;
```

## Dynamic Plan Caching

A dynamic plan can be cached for reuse when **all** conditions are met:

1. Plan uses **statistics feedback only** (no results feedback)
2. Request is **nonparameterized**
3. System automatically determines caching is appropriate

The caching process:
1. First submission: request is marked as a caching candidate
2. Second submission: dynamic plan generated, dynamic statistics steps removed, plan cached as a generic plan
3. Subsequent submissions: cached plan reused without parsing or statistics collection overhead

## Multistatement Request Support (16.20 FU2)

- IPE eligibility checked per statement; if any statement qualifies, the whole request is eligible
- The last fragment of one statement and the first fragment of the next are combined when the next statement is IPE-eligible
- Trigger statements that create multistatement requests are supported

## Cost Profile Constants Reference

| Constant | Default | Description |
|---|---|---|
| `DYNAMICPLAN` | 0 (system) | 0=default, 1=off, 2=enforce |
| `IPEFeedbackControl` | 0 (=5) | 1=SSQ+unique+stats, 2=SSQ+unique, 3=stats only, 4=results only, 5=both |
| `IPEStatsFeedbackControl` | 0 (=4) | 1=remote only, 2=remote+local ops, 3=+functions, 4=+subqueries/DTs |
| `IPEMinCostEstThreshold` | 60000 | Min estimated cost (ms) to qualify |
| `IPEMinCommonStepPruneThreshold` | 5 | Max CSP % before disqualifying |
| `IPEParsingPctThreshold` | 10 | Max parsing % of execution cost |
| `IPEMaxFeedbackSize` | 32 | Max results feedback size (KB) before switching |
| `IPESFLevel` | 0 (=3) | Stats depth: 1=rowcount, 3=NUV+HMF, 5=all+min/max |
| `IPEMaxSFEntryCnt` | 0 (unlimited) | Max SF entries per request |
| `IPEMaxSFHashColLen` | 0 (=40) | Max bytes for target columns |
| `IPEMaxSFHashColCnt` | 0 (=10) | Max target columns for stats |
| `ExplainMode` | 1 | 1=STATIC default, 2=DYNAMIC default |
| `SecureExplain` | 1 | 1=redact, 2=show values, 3=block dynamic |

### Setting Constants via Query Band

```sql
-- Enforce IPE
SET QUERY_BAND = 'DYNAMICPLAN=SYSTEMX;' FOR SESSION;

-- Disable IPE
SET QUERY_BAND = 'DYNAMICPLAN=OFF;' FOR SESSION;

-- Reset to default
SET QUERY_BAND = 'DYNAMICPLAN=SYSTEM;' FOR SESSION;
```

### Setting Constants via Cost Profile

```sql
-- Enforce IPE
EXEC DBC.InsertConstantValue('CP_DYNPLAN', 'DYNAMICPLAN', 2);

-- Set min cost threshold to 5 minutes
EXEC DBC.InsertConstantValue('CP_DYNPLAN', 'IPEMinCostEstThreshold', 300000);

-- Rowcount-only statistics (reduce overhead)
EXEC DBC.InsertConstantValue('CP_DYNPLAN', 'IPESFLevel', 1);
```

## Limitations

- Recursive queries (`WITH RECURSIVE`) are not supported for dynamic planning
- Dynamic planning is skipped for multistatement requests in Fast Export mode
- Dynamic plans with results feedback are not cached
- Common step pruning does not operate across fragments — can cause higher peak spool usage

## Performance Considerations

### When IPE Helps

- Complex queries with subqueries where results feedback enables partition or join elimination
- Queries against remote tables (UDA) where base statistics are unknown
- Queries with inaccurate spool estimates leading to suboptimal join orders
- Queries where a join index could be used but only after runtime values are known

### When IPE Hurts

- Small queries that are overestimated and unnecessarily qualify for IPE
- Queries where the dynamic plan matches the static plan — parsing overhead is wasted
- High common step pruning benefit lost due to fragmentation
- Column-level statistics collection overhead on queries with many grouping columns

### Tuning Recommendations

| Symptom | Action |
|---|---|
| Small queries getting IPE overhead | Raise `IPEMinCostEstThreshold` |
| Column stats not improving plans | Set `IPESFLevel=1` (rowcount only) |
| Too many stats columns collected | Lower `IPEMaxSFHashColCnt` or `IPEMaxSFHashColLen` |
| CSP benefit lost to fragmentation | Lower `IPEMinCommonStepPruneThreshold` |
| Want to test IPE on a specific query | Use `DYNAMICPLAN=SYSTEMX` query band |

## Case Study: Join Index Rewrite via Results Feedback

A join index `ji_customer_item` covers states `('DC', 'RI', 'DE', 'HI')`. A query filters by states from a subquery. Without IPE, the optimizer cannot determine if the subquery results are covered by the join index.

**With IPE:**
1. Fragment 1: Collect statistics on the aggregation input
2. Fragment 2: Execute the IN subquery → results feedback returns `('DE', 'DC')`
3. The optimizer detects these values are covered by the join index
4. Fragment 3: Reads directly from `ji_customer_item` instead of joining 5 base tables

```sql
-- Static plan: 5-table join, estimated 2 minutes 2 seconds
-- Dynamic plan: single JI scan, estimated < 1 second
```

## Case Study: Unique-Join Table Partition Elimination

```sql
SELECT i_item_id, i_item_desc, i_current_price
FROM   item, inventory, date_dim, store_sales
WHERE  i_current_price BETWEEN 62 AND 92
  AND  inv_item_sk = i_item_sk
  AND  d_date_sk = inv_date_sk
  AND  d_date BETWEEN '2000-05-25' AND '2000-06-08'
  AND  i_manufact_id IN ('129', '270', '821', '423')
  AND  inv_quantity_on_hand BETWEEN 100 AND 500
  AND  ss_item_sk = i_item_sk;
```

- `date_dim` is a Unique-Join Table (UPI on `d_date_sk`, range condition on `d_date`)
- Fragment 1 retrieves 15 `d_date_sk` values as results feedback
- Fragment 2 plugs values into `inv_date_sk IN (:*, ..., :*)`, accesses only 15 partitions of `inventory`
- **Static plan with DPE:** Also accesses 15 partitions but requires spool materialization of `date_dim`
- **Dynamic plan:** Eliminates the join and spool overhead entirely
