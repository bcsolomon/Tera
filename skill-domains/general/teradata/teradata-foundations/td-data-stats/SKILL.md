---
name: td-data-stats
description: Statistical and analytical SQL skill for data exploration use cases, including aggregations, trend analysis, period comparisons, and statistical summaries in Teradata.
---

# td-data-stats

## Purpose
Use this skill to answer business questions with analytical SQL patterns quickly and reliably.

Primary outcomes:
- Aggregations by business dimensions (region, product, segment, channel)
- Trend analysis over time (daily, weekly, monthly, quarterly)
- Period-over-period comparisons (QoQ, MoM, YoY)
- Statistical summaries (mean, median, percentiles, stddev, variance)

## When To Use
Use when the request is primarily exploratory or analytical, such as:
- "What is average order value by region for Q1 vs Q2?"
- "Which categories grew fastest month over month?"
- "What is the distribution of transaction values?"

Do not use as the primary skill for:
- Data quality profiling across all columns
- Model training/scoring workflows
- Data engineering ETL pipelines

## Audience
- Business Analyst
- Data Scientist

## Query Strategy
1. Confirm analysis grain and metric definition.
2. Scope time windows explicitly (date filters, period labels).
3. Aggregate in-database first; return only summarized results.
4. Use window functions for trends and period comparisons.
5. Use statistical functions/native operators for robust summaries.

## Core Patterns

### 1) Aggregation and grouped summaries
Use `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`, `STDDEV_SAMP`, `VAR_SAMP`, and conditional aggregation with `CASE`.

### 2) Trend analysis
Use time-bucketed grouping plus window functions for running values and changes:
- `LAG` / `LEAD` for period deltas
- Running totals/averages with `SUM(...) OVER (...)` and `AVG(...) OVER (...)`

### 3) Comparisons
Use period labeling and side-by-side comparison logic:
- Compare Q1 vs Q2, current vs prior period
- Include absolute delta and percent delta

### 4) Statistical summaries
Use:
- `PERCENTILE_CONT` / `PERCENTILE_DISC` (exact)
- `APPROX_PERCENTILE` (large-scale approximation)
- `APPROX_COUNT_DISTINCT` for fast cardinality estimation

### 5) Distribution and ranking
Use:
- Frequency distributions via `GROUP BY`
- `NTILE`, `RANK`, `DENSE_RANK`, `ROW_NUMBER`
- `QUALIFY` for top-N per partition and dedup logic

## Teradata-Specific Best Practices
- Prefer Teradata-native analytical capabilities where available.
- Avoid pulling raw large datasets; aggregate before returning results.
- Use `TOP`/`SAMPLE` only for quick validation views.
- For non-trivial, large queries, run `EXPLAIN` before execution.

## Output Contract
Always return:
1. A concise interpretation of what the query answers.
2. SQL query with clear CTE structure and explicit aliases.
3. Optional validation snippet (small `TOP`/`SAMPLE`) when useful.


## Canonical Example
Question: What is average order value by region for Q1 vs Q2?

```sql
WITH base AS (
    SELECT
        region,
        EXTRACT(QUARTER FROM order_date) AS qtr,
        order_id,
        order_amount
    FROM sales.orders
    WHERE order_date >= DATE '2026-01-01'
      AND order_date <  DATE '2026-07-01'
),
order_level AS (
    SELECT
        region,
        qtr,
        order_id,
        SUM(order_amount) AS order_value
    FROM base
    GROUP BY 1, 2, 3
),
summary AS (
    SELECT
        region,
        qtr,
        AVG(order_value) AS avg_order_value,
        COUNT(*) AS order_count
    FROM order_level
    WHERE qtr IN (1, 2)
    GROUP BY 1, 2
),
pivoted AS (
    SELECT
        region,
        MAX(CASE WHEN qtr = 1 THEN avg_order_value END) AS aov_q1,
        MAX(CASE WHEN qtr = 2 THEN avg_order_value END) AS aov_q2
    FROM summary
    GROUP BY 1
)
SELECT
    region,
    aov_q1,
    aov_q2,
    aov_q2 - aov_q1 AS aov_delta,
    CASE
        WHEN aov_q1 = 0 OR aov_q1 IS NULL THEN NULL
        ELSE (aov_q2 - aov_q1) / aov_q1
    END AS aov_pct_change
FROM pivoted
ORDER BY region;
```

## Reference Cheatsheet

Source-aligned patterns adapted from:
- tdsql-mcp `syntax/aggregate-functions.md`
- tdsql-mcp `syntax/window-functions.md`
- tdsql-mcp `syntax/data-exploration.md`
- tdsql-mcp `syntax/guidelines.md`

### Aggregate and Statistical Functions
```sql
COUNT(*)
COUNT(col)
COUNT(DISTINCT col)
SUM(col)
AVG(col)
MIN(col)
MAX(col)
STDDEV_POP(col)
STDDEV_SAMP(col)
VAR_POP(col)
VAR_SAMP(col)
```

### Percentiles
```sql
PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY col)
PERCENTILE_DISC(0.25) WITHIN GROUP (ORDER BY col)
APPROX_PERCENTILE(col, 0.95)
APPROX_COUNT_DISTINCT(col)
```

### Window Template
```sql
function() OVER (
    [PARTITION BY col1, col2]
    [ORDER BY col3 [ASC|DESC]]
    [ROWS|RANGE BETWEEN frame_start AND frame_end]
)
```

### Trend and Comparison Snippets
```sql
-- Previous period comparison
SELECT
    dt,
    metric,
    LAG(metric, 1, 0) OVER (ORDER BY dt) AS prev_metric,
    metric - LAG(metric, 1, 0) OVER (ORDER BY dt) AS delta
FROM db.series;

-- Running total
SELECT
    dt,
    amount,
    SUM(amount) OVER (ORDER BY dt ROWS UNBOUNDED PRECEDING) AS running_total
FROM db.t;
```

### QUALIFY Patterns
```sql
-- Top 3 per category
SELECT category, product, revenue
FROM db.sales
QUALIFY RANK() OVER (PARTITION BY category ORDER BY revenue DESC) <= 3;

-- Latest row per key
SELECT *
FROM db.events
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY ts DESC) = 1;
```

### Exploration and Summary Operators
```sql
-- Column summary
SELECT *
FROM TD_ColumnSummary(
    ON db.table AS InputTable
    USING TargetColumns('col1', 'col2')
) AS t;

-- Univariate statistics
SELECT *
FROM TD_UnivariateStatistics(
    ON db.table AS InputTable
    PARTITION BY ANY
    USING TargetColumns('col1', 'col2')
) AS t;
```

### Operating Rules
- Aggregate before returning results.
- Keep heavy computation in-database.
- Use `TOP`/`SAMPLE` only for quick validation.
- For complex queries on large data, `EXPLAIN` before execution.

