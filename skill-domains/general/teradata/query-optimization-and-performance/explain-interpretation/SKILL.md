---
name: teradata-adaptive-optimizer
description: 'Guide Teradata adaptive optimization features including Incremental Planning and Execution (IPE), Dynamic Partition Elimination (DPE), feedback-driven plan adjustments, and cost estimation improvements. Use when tuning queries with suboptimal plans, configuring optimizer features, understanding plan reoptimization, or diagnosing why the optimizer chose a particular strategy.'
metadata:
  author: teradata-expert
  version: "1.0"
---

# Teradata Adaptive Optimizer

## When to Use

- Diagnosing suboptimal query plans caused by inaccurate cost estimates
- Understanding why the optimizer chose a static vs dynamic plan
- Configuring or tuning IPE (Incremental Planning and Execution) behavior
- Leveraging Dynamic Partition Elimination (DPE) for partition pruning at runtime
- Troubleshooting queries eligible for IPE that fail to qualify
- Analyzing EXPLAIN output showing FEEDBACK RETRIEVE steps or DPE annotations
- Tuning queries in UDA environments with remote tables and missing statistics

## Core Concepts

### Incremental Planning and Execution (IPE)

IPE is an adaptive optimization framework where the optimizer partially plans and executes a request, collects runtime feedback, and dynamically replans remaining steps. Two kinds of feedback drive this:

| Feedback Type | What Is Collected | How It Helps |
|---|---|---|
| **Results Feedback** | Actual spool data values | Partition elimination, join elimination, predicate simplification, join index rewrite |
| **Statistics Feedback** | NUV, HMF, row counts from spools | Accurate cost estimation for joins, aggregations, redistribution decisions |

**IPE flow:** IDENTIFY fragment → GENERATE plan → EXECUTE fragment → COLLECT feedback → REPLAN next fragment.

The optimizer always generates a **static plan** first, then decides whether dynamic planning is warranted based on eligibility and qualification criteria.

### Dynamic Partition Elimination (DPE)

DPE prunes partitions at execution time rather than at optimization time. It occurs when:

- A partitioned table is joined to a small dimension table
- The join column matches the partitioning column
- The optimizer annotates the join with "enhanced by dynamic partition elimination"

DPE allows partition pruning even when the filtering values are not known until runtime, complementing static partition elimination from literal predicates.

### Static vs Dynamic Plans

| Aspect | Static Plan | Dynamic Plan |
|---|---|---|
| **Generation** | Traditional optimization | Incremental with feedback |
| **Statistics** | Pre-collected on base tables | Dynamic statistics from spools |
| **Partitioning** | Static elimination only | DPE + results-feedback elimination |
| **EXPLAIN** | Default `EXPLAIN` output | Requires `DYNAMIC EXPLAIN` |
| **Caching** | Always cacheable | Cacheable only with statistics-feedback-only plans |

## Procedure: Diagnosing Suboptimal Plans

1. **Run EXPLAIN** on the query and look for IPE eligibility indicators:
   - `"This request is eligible for incremental planning and execution (IPE)."` — eligible
   - `"...but does not meet cost thresholds."` — eligible but not qualified
   - No IPE message — not eligible
2. **Run DYNAMIC EXPLAIN** to see the actual dynamic plan:
   ```sql
   DYNAMIC EXPLAIN SELECT ... ;
   ```
3. **Compare static vs dynamic plans** — look for differences in join order, partition access, and estimated row counts.
4. **Check DBQL for IPE usage:**
   ```sql
   -- Count IPE queries in a session
   SELECT COUNT(*)
   FROM DBC.DBQLogTbl
   WHERE SessionId = <session_id> AND NumFragments > 0;

   -- Check CPU per fragment
   SELECT FragmentNum, SUM(CPUTime)
   FROM DBC.DBQLStepTbl
   WHERE QueryId = <query_id>
   GROUP BY FragmentNum;
   ```
5. **Look for FEEDBACK RETRIEVE steps** in EXPLAIN output — these indicate where feedback is collected and how it differs from estimates.

## Procedure: Configuring IPE

### Enforce IPE for Testing

```sql
-- Force IPE regardless of qualification thresholds
SET QUERY_BAND = 'DYNAMICPLAN=SYSTEMX;' FOR SESSION;
```

### Disable IPE

```sql
-- Turn off IPE entirely
SET QUERY_BAND = 'DYNAMICPLAN=OFF;' FOR SESSION;
```

### Reset to Default

```sql
-- Restore default IPE behavior (optimizer decides)
SET QUERY_BAND = 'DYNAMICPLAN=SYSTEM;' FOR SESSION;
```

### Key Cost Profile Constants

| Constant | Default | Purpose |
|---|---|---|
| `IPEMinCostEstThreshold` | 60000 (1 min) | Minimum static plan cost (ms) to qualify for IPE |
| `IPEParsingPctThreshold` | 10 | Max parsing cost as % of execution cost |
| `IPEFeedbackControl` | 0 (=5) | Controls which feedback types are enabled (1-5) |
| `IPEStatsFeedbackControl` | 0 (=4) | Scope of statistics feedback eligibility |
| `IPESFLevel` | 0 (=3) | Degree of statistics collected (1=rowcount only, 3=NUV+HMF) |
| `IPEMaxFeedbackSize` | 32 KB | Max results feedback size before switching to statistics |

```sql
-- Example: raise min cost threshold to 5 minutes
EXEC DBC.InsertConstantValue('CP_DYNPLAN', 'IPEMinCostEstThreshold', 300000);
```

## Procedure: Using DPE

DPE is automatic when conditions are met. To verify DPE is being used:

1. **Check EXPLAIN output** for the phrase `"enhanced by dynamic partition elimination"`:
   ```
   Spool 3 and TPCDS.store_sales are joined using a product join,
   with a join condition of ("...ss_sold_date_sk = d_date_sk")
   enhanced by dynamic partition elimination.
   ```
2. **Ensure the dimension table** (small side) is joined on the partitioning column of the fact table.
3. **Compare with IPE results feedback** — for Unique-Join Tables, IPE may eliminate the join entirely and access only the needed partitions directly, avoiding the spool materialization that DPE requires.

### DPE vs IPE Partition Elimination

| Approach | Mechanism | Overhead |
|---|---|---|
| **DPE** | Runtime partition pruning during join | Requires spool materialization of dimension |
| **IPE Results Feedback** | Substitutes actual values, eliminates join | No dimension spool needed |

## Common Errors / Troubleshooting

### Query eligible but not qualified for IPE

**Cause:** Estimated execution time < 1 minute, or parsing cost > 10% of execution time, or common step pruning savings > 5%.

**Fix:** Lower `IPEMinCostEstThreshold`, or enforce with `DYNAMICPLAN=SYSTEMX` for testing.

### Dynamic plan equivalent to static plan (regression)

**Cause:** Dynamic statistics did not improve the plan. Extra parsing overhead is wasted.

**Fix:** If consistent, set `IPESFLevel=1` (rowcount only) or increase `IPEMinCostEstThreshold` to skip small queries.

### Results feedback switched to statistics feedback

**Cause:** Subquery returned > 32 KB or > 16 rows, exceeding `IPEMaxFeedbackSize`.

**Fix:** Increase `IPEMaxFeedbackSize` if the results feedback is expected to be beneficial.

### EXPLAIN shows `:*` masked values

**Cause:** `SecureExplain` cost profile is set to redact intermediate results.

**Fix:** Set `SecureExplain=2` (NonSecure) to see actual values in EXPLAIN output:
```sql
EXEC DBC.InsertConstantValue('CP_DYNPLAN', 'SecureExplain', 2);
```

### EXPLAIN always shows static plan even with DYNAMIC EXPLAIN

**Cause:** `SecureExplain=3` (Secure mode) blocks dynamic plan display.

**Fix:** Set `SecureExplain` to 1 or 2.

### IPE overhead on small queries

**Cause:** Queries with overestimated costs qualify for IPE but dynamic plan matches static plan.

**Fix:** Raise `IPEMinCostEstThreshold` to prevent small queries from qualifying.

### Dynamic plan not cached

**Cause:** Plan uses results feedback, or request is parameterized. Only statistics-feedback-only dynamic plans for nonparameterized requests can be cached.

**Fix:** This is expected behavior. Consider collecting base-table statistics if caching is important.

## TASM Integration

IPE requests can be classified using the **IPE Request** criterion in TASM rules. Two options control how TASM evaluates IPE requests:

| Option | DBS Control #351 | Behavior |
|---|---|---|
| **First-fragment** (default) | 0 | TASM evaluates the first fragment only; step-level criteria are skipped |
| **Static-plan** | 1 | TASM evaluates the full static concrete plan; adds parsing overhead |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-adaptive-optimizer", path="references/FILENAME")` — do NOT call `list`.

- [references/incremental-planning-execution.md](references/incremental-planning-execution.md) — IPE architecture, eligibility rules, fragmentation, feedback mechanisms, dynamic statistics collection, plan caching, DBQL tracking, and cost profile constants
- [references/dynamic-partition-elimination.md](references/dynamic-partition-elimination.md) — DPE mechanics, partition pruning at execution time, query patterns, EXPLAIN indicators, comparison with IPE results feedback, and interaction with PPI and statistics
