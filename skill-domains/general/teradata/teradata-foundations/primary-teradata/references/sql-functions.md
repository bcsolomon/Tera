# Teradata Date & Time

## Data Types
| Type | Description | Example literal |
|------|-------------|-----------------|
| `DATE` | Date only | `DATE '2024-01-15'` |
| `TIME` | Time only | `TIME '14:30:00'` |
| `TIMESTAMP` | Date + time | `TIMESTAMP '2024-01-15 14:30:00'` |
| `INTERVAL` | Duration | `INTERVAL '3' MONTH` |

## Current Values
```sql
CURRENT_DATE          -- today's date
CURRENT_TIME          -- current time
CURRENT_TIMESTAMP     -- current date + time
```

## Date Arithmetic
```sql
-- Add/subtract days (integers)
CURRENT_DATE - 7                          -- 7 days ago
CURRENT_DATE + 30                         -- 30 days from now

-- Add/subtract using INTERVAL
CURRENT_DATE - INTERVAL '1' MONTH
CURRENT_DATE + INTERVAL '2' YEAR
CURRENT_TIMESTAMP + INTERVAL '4' HOUR
CURRENT_TIMESTAMP - INTERVAL '90' MINUTE

-- Difference between two dates (returns integer days)
end_date - start_date

-- Difference in months
MONTHS_BETWEEN(end_date, start_date)
```

## Formatting & Casting
```sql
-- Date to formatted string
CAST(order_date AS VARCHAR(10) FORMAT 'YYYY-MM-DD')
CAST(order_date AS VARCHAR(10) FORMAT 'MM/DD/YYYY')

-- String to date
CAST('2024-01-15' AS DATE FORMAT 'YYYY-MM-DD')

-- Timestamp to date
CAST(ts_col AS DATE)

-- Date to timestamp
CAST(date_col AS TIMESTAMP)

-- Extract components
EXTRACT(YEAR  FROM date_col)
EXTRACT(MONTH FROM date_col)
EXTRACT(DAY   FROM date_col)
EXTRACT(HOUR  FROM ts_col)
```

## Truncation
```sql
-- Truncate to start of month
CAST(CAST(date_col AS CHAR(7) FORMAT 'YYYY-MM') || '-01' AS DATE FORMAT 'YYYY-MM-DD')

-- Or using TD_SYSFNLIB helpers where available
TRUNC(date_col, 'MM')   -- start of month
TRUNC(date_col, 'YYYY') -- start of year
```

## Day of Week / Week of Year
```sql
-- Day of week: Sunday=1 ... Saturday=7
((date_col - DATE '1900-01-07') MOD 7) + 1

-- Using TD_DAY_OF_WEEK if available
TD_DAY_OF_WEEK(date_col)    -- 1=Sunday

-- Week number
TD_WEEK_OF_YEAR(date_col)
```

## Common Patterns
```sql
-- Last N days
WHERE event_date >= CURRENT_DATE - 30

-- Current month
WHERE EXTRACT(YEAR FROM event_date) = EXTRACT(YEAR FROM CURRENT_DATE)
  AND EXTRACT(MONTH FROM event_date) = EXTRACT(MONTH FROM CURRENT_DATE)

-- Between two dates (inclusive)
WHERE event_date BETWEEN DATE '2024-01-01' AND DATE '2024-03-31'

-- Convert Unix epoch (seconds) to timestamp
CAST(DATE '1970-01-01' AS TIMESTAMP) + INTERVAL '1' SECOND * epoch_col
```

## Format Tokens
| Token | Meaning |
|-------|---------|
| `YYYY` | 4-digit year |
| `YY` | 2-digit year |
| `MM` | Month (01–12) |
| `MMM` | Month abbreviation (Jan, Feb…) |
| `DD` | Day (01–31) |
| `HH` | Hour (00–23) |
| `MI` | Minute (00–59) |
| `SS` | Second (00–59) |

---

# Teradata Aggregate Functions

## Standard Aggregates
```sql
COUNT(*)               -- count all rows
COUNT(col)             -- count non-NULL values
COUNT(DISTINCT col)    -- count distinct non-NULL values
SUM(col)
AVG(col)
MIN(col)
MAX(col)
```

## Statistical Aggregates
```sql
STDDEV_POP(col)        -- population standard deviation
STDDEV_SAMP(col)       -- sample standard deviation
VAR_POP(col)           -- population variance
VAR_SAMP(col)          -- sample variance
```

## Percentile / Quantile
```sql
-- Exact (sorts all data — can be slow on large sets)
PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY col)    -- median
PERCENTILE_DISC(0.25) WITHIN GROUP (ORDER BY col)   -- 25th percentile (discrete)

-- Approximate (fast, uses HLL sketch — Vantage)
APPROX_PERCENTILE(col, 0.5)
APPROX_PERCENTILE(col, 0.95)
```

## Approximate Count Distinct
```sql
-- HyperLogLog-based — much faster than COUNT(DISTINCT) on large data
APPROX_COUNT_DISTINCT(col)
```

## String Aggregation
```sql
-- Concatenate values into one string (XML-based, common pattern)
XMLAGG(XMLELEMENT(NAME x, col || ',') ORDER BY col)

-- Cleaner alternative using TD_SYSFNLIB.XMLAGG or custom UDF
```

## GROUP BY Variants
```sql
-- Standard
SELECT dept, SUM(salary) FROM db.t GROUP BY dept;

-- Multiple grouping sets in one pass
GROUP BY GROUPING SETS ((dept), (region), (dept, region), ())

-- Equivalent shorthand
GROUP BY ROLLUP(dept, region)   -- all prefixes + grand total
GROUP BY CUBE(dept, region)     -- all combinations

-- Identify which grouping a row belongs to
GROUPING(dept)     -- 1 if dept is aggregated away, 0 if not
```

## HAVING
```sql
SELECT dept, COUNT(*) AS cnt
FROM db.employees
GROUP BY dept
HAVING COUNT(*) > 10;
```

## Conditional Aggregation
```sql
-- Count rows meeting a condition
SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_count

-- Average only non-zero values
AVG(NULLIFZERO(amount))

-- Max of a filtered subset
MAX(CASE WHEN category = 'A' THEN value END)
```

## Common Patterns
```sql
-- Frequency distribution
SELECT val, COUNT(*) AS freq,
       COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS pct
FROM db.t
GROUP BY val
ORDER BY freq DESC;

-- Running total (use window function instead of aggregate)
SUM(amount) OVER (ORDER BY event_date ROWS UNBOUNDED PRECEDING)
```

---

# Teradata Window (OLAP) Functions

## Syntax Template
```sql
function() OVER (
    [PARTITION BY col1, col2]
    [ORDER BY col3 [ASC|DESC]]
    [ROWS|RANGE BETWEEN frame_start AND frame_end]
)
```

## Ranking Functions
```sql
ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC)  -- unique sequential rank
RANK()       OVER (PARTITION BY dept ORDER BY salary DESC)  -- gaps on ties
DENSE_RANK() OVER (PARTITION BY dept ORDER BY salary DESC)  -- no gaps on ties
PERCENT_RANK() OVER (ORDER BY col)                          -- 0.0 to 1.0 relative rank
CUME_DIST()    OVER (ORDER BY col)                          -- cumulative distribution
NTILE(4)       OVER (ORDER BY col)                          -- assign quartile (1–4)
```

## Offset Functions
```sql
LAG(col, n, default)  OVER (PARTITION BY ... ORDER BY ...)  -- previous row value
LEAD(col, n, default) OVER (PARTITION BY ... ORDER BY ...)  -- next row value
FIRST_VALUE(col)      OVER (PARTITION BY ... ORDER BY ...)
LAST_VALUE(col)       OVER (PARTITION BY ... ORDER BY ... ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
```

## Running / Moving Aggregates
```sql
-- Running total
SUM(amount) OVER (ORDER BY event_date ROWS UNBOUNDED PRECEDING)

-- Running average
AVG(amount) OVER (ORDER BY event_date ROWS UNBOUNDED PRECEDING)

-- 7-day moving average (current row + 6 preceding)
AVG(amount) OVER (ORDER BY event_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)

-- Partition total (for % of total calculations)
SUM(amount) OVER (PARTITION BY dept)
```

## Frame Specifications
| Clause | Meaning |
|--------|---------|
| `ROWS UNBOUNDED PRECEDING` | From first row in partition to current |
| `ROWS BETWEEN n PRECEDING AND CURRENT ROW` | Rolling window of n+1 rows |
| `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING` | Entire partition |
| `RANGE BETWEEN INTERVAL '7' DAY PRECEDING AND CURRENT ROW` | Date-based range window |

## QUALIFY — Filter on Window Results
Teradata's `QUALIFY` applies a filter on window function output without a subquery:
```sql
-- Keep only the most recent row per customer
SELECT *
FROM db.events
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY ts DESC) = 1;

-- Top 3 products by revenue per category
SELECT category, product, revenue
FROM db.sales
QUALIFY RANK() OVER (PARTITION BY category ORDER BY revenue DESC) <= 3;

-- Flag rows where value jumps more than 10% from previous
SELECT *, value / LAG(value) OVER (PARTITION BY id ORDER BY dt) - 1 AS pct_chg
FROM db.series
QUALIFY ABS(pct_chg) > 0.10;
```

## Common Patterns

```sql
-- Deduplicate: keep latest record per key
SELECT * FROM db.t
QUALIFY ROW_NUMBER() OVER (PARTITION BY key_col ORDER BY updated_at DESC) = 1;

-- Running total that resets per partition
SELECT dept, month, sales,
       SUM(sales) OVER (PARTITION BY dept ORDER BY month ROWS UNBOUNDED PRECEDING) AS ytd
FROM db.monthly_sales;

-- Period-over-period comparison
SELECT dt, revenue,
       LAG(revenue, 1, 0) OVER (ORDER BY dt) AS prev_revenue,
       revenue - LAG(revenue, 1, 0) OVER (ORDER BY dt) AS delta
FROM db.daily_revenue;

-- Percentile bucket (decile)
SELECT *, NTILE(10) OVER (ORDER BY score) AS decile FROM db.scores;

-- Gap-and-island: number consecutive groups
SELECT id, dt,
       dt - ROW_NUMBER() OVER (PARTITION BY id ORDER BY dt) AS grp
FROM db.daily_activity;
```
