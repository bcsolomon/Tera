---
name: teradata-sql-fundamentals
description: 'Teradata SQL syntax and fundamentals including CREATE/ALTER/DROP TABLE, INSERT/UPDATE/DELETE/MERGE, SELECT with Teradata extensions (QUALIFY, SAMPLE, TOP, NORMALIZE), joins, subqueries, CTEs, VOLATILE/GLOBAL TEMPORARY tables, SET vs MULTISET, SHOW/HELP commands, EXPLAIN, locking modifiers, and Teradata-specific functions (CSUM, MAVG, MDIFF, MSUM, MLINREG, RANK, QUANTILE). Use for any general Teradata SQL questions, DDL/DML syntax, or Teradata-specific SQL extensions.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata SQL Fundamentals

## When to Use

- Writing Teradata-specific SQL (QUALIFY, SAMPLE, TOP, NORMALIZE)
- Creating and modifying tables (DDL)
- INSERT/UPDATE/DELETE/MERGE operations
- Using Teradata ordered analytical functions (CSUM, MAVG, RANK)
- Working with volatile and global temporary tables
- Understanding SET vs MULTISET table behavior
- Using locking modifiers for read consistency
- EXPLAIN plan interpretation

## CREATE TABLE

```sql
-- Basic table
CREATE MULTISET TABLE mydb.orders (
    order_id    INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    order_date  DATE FORMAT 'YYYY-MM-DD' NOT NULL,
    amount      DECIMAL(13,2),
    status      VARCHAR(20) DEFAULT 'pending'
) PRIMARY INDEX (order_id);

-- With unique primary index
CREATE SET TABLE mydb.customers (
    customer_id INTEGER NOT NULL,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(200),
    region      CHAR(2)
) UNIQUE PRIMARY INDEX (customer_id);

-- No primary index
CREATE MULTISET TABLE mydb.staging (
    raw_data VARCHAR(10000)
) NO PRIMARY INDEX;

-- CTAS (Create Table As Select)
CREATE MULTISET TABLE mydb.daily_summary AS (
    SELECT order_date, COUNT(*) AS order_count, SUM(amount) AS total
    FROM mydb.orders
    GROUP BY order_date
) WITH DATA
PRIMARY INDEX (order_date);
```

### SET vs MULTISET

| Type | Duplicates | INSERT Performance | Default |
|---|---|---|---|
| `SET` | Rejected | Slower (duplicate check) | Pre-14.0 |
| `MULTISET` | Allowed | Faster | 14.0+ |

## Volatile & Temporary Tables

```sql
-- Volatile table (session-scoped, auto-dropped)
CREATE VOLATILE TABLE vt_temp AS (
    SELECT customer_id, SUM(amount) AS total
    FROM mydb.orders
    GROUP BY customer_id
) WITH DATA
ON COMMIT PRESERVE ROWS;

-- Global temporary table (definition persists, data is session-scoped)
CREATE GLOBAL TEMPORARY TABLE mydb.gt_staging (
    id INTEGER,
    data VARCHAR(1000)
) ON COMMIT PRESERVE ROWS;
```

## ALTER TABLE

```sql
ALTER TABLE mydb.orders ADD new_col VARCHAR(50);
ALTER TABLE mydb.orders DROP new_col;
ALTER TABLE mydb.orders RENAME old_col TO new_col;
ALTER TABLE mydb.orders ADD CONSTRAINT chk CHECK (amount > 0);
```

## INSERT / UPDATE / DELETE / MERGE

```sql
-- Insert
INSERT INTO mydb.orders VALUES (1, 100, DATE '2025-06-15', 99.99, 'active');
INSERT INTO mydb.orders SELECT * FROM mydb.staging;

-- Update
UPDATE mydb.orders SET status = 'shipped' WHERE order_id = 1;

-- Delete
DELETE FROM mydb.orders WHERE order_date < DATE '2020-01-01';

-- Upsert (MERGE)
MERGE INTO mydb.customers tgt
USING mydb.new_customers src
ON tgt.customer_id = src.customer_id
WHEN MATCHED THEN UPDATE SET name = src.name, email = src.email
WHEN NOT MATCHED THEN INSERT VALUES (src.customer_id, src.name, src.email, src.region);
```

## SELECT — Teradata Extensions

### QUALIFY — Filter Window Function Results

```sql
-- Top 3 customers by spend per region
SELECT region, customer_id, total_spend,
       RANK() OVER (PARTITION BY region ORDER BY total_spend DESC) AS rnk
FROM mydb.customer_summary
QUALIFY rnk <= 3;
```

**QUALIFY** is evaluated after window functions, like HAVING is for GROUP BY.

### SAMPLE

```sql
-- Random rows
SELECT * FROM mydb.orders SAMPLE 100;        -- 100 rows
SELECT * FROM mydb.orders SAMPLE 0.10;       -- 10% of rows

-- Stratified sample
SELECT * FROM mydb.orders SAMPLE 50
    WHEN region = 'East' THEN 0.2
    WHEN region = 'West' THEN 0.3;
```

### TOP

```sql
SELECT TOP 10 * FROM mydb.orders ORDER BY amount DESC;
SELECT TOP 10 WITH TIES * FROM mydb.orders ORDER BY amount DESC;
SELECT TOP 5 PERCENT * FROM mydb.orders ORDER BY amount DESC;
```

### NORMALIZE

Merge overlapping/adjacent PERIOD values:

```sql
SELECT customer_id, NORMALIZE subscription_period
FROM mydb.subscriptions
GROUP BY customer_id;
```

## Teradata Ordered Analytical Functions

These are Teradata-proprietary window functions:

```sql
-- CSUM: Cumulative sum
SELECT order_date, amount,
       CSUM(amount, order_date) AS running_total
FROM mydb.orders;

-- MAVG: Moving average
SELECT order_date, amount,
       MAVG(amount, 7, order_date) AS avg_7day
FROM mydb.orders;

-- MSUM: Moving sum
SELECT order_date, amount,
       MSUM(amount, 30, order_date) AS sum_30day
FROM mydb.orders;

-- MDIFF: Moving difference
SELECT order_date, amount,
       MDIFF(amount, 1, order_date) AS day_over_day_change
FROM mydb.orders;

-- MLINREG: Moving linear regression
SELECT order_date, amount,
       MLINREG(amount, 30, order_date) AS trend_30day
FROM mydb.orders;

-- RANK
SELECT customer_id, total_spend,
       RANK(total_spend DESC) AS spend_rank
FROM mydb.customer_summary;

-- QUANTILE
SELECT customer_id, total_spend,
       QUANTILE(100, total_spend) AS percentile
FROM mydb.customer_summary;
```

## ANSI Window Functions

```sql
SELECT order_date, amount,
       SUM(amount) OVER (ORDER BY order_date ROWS UNBOUNDED PRECEDING) AS running_total,
       ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date) AS row_num,
       LAG(amount, 1) OVER (ORDER BY order_date) AS prev_amount,
       LEAD(amount, 1) OVER (ORDER BY order_date) AS next_amount,
       FIRST_VALUE(amount) OVER (PARTITION BY customer_id ORDER BY order_date) AS first_order
FROM mydb.orders;
```

## Common Table Expressions (CTEs)

```sql
WITH recent_orders AS (
    SELECT * FROM mydb.orders WHERE order_date >= CURRENT_DATE - 30
),
customer_totals AS (
    SELECT customer_id, SUM(amount) AS total
    FROM recent_orders
    GROUP BY customer_id
)
SELECT c.name, ct.total
FROM customer_totals ct
JOIN mydb.customers c ON ct.customer_id = c.customer_id
ORDER BY ct.total DESC;

-- Recursive CTE
WITH RECURSIVE org_tree (emp_id, manager_id, level) AS (
    SELECT emp_id, manager_id, 0
    FROM mydb.employees WHERE manager_id IS NULL
    UNION ALL
    SELECT e.emp_id, e.manager_id, t.level + 1
    FROM mydb.employees e
    JOIN org_tree t ON e.manager_id = t.emp_id
)
SELECT * FROM org_tree;
```

## Locking Modifiers

```sql
-- Read without locking (dirty read)
LOCKING ROW FOR ACCESS SELECT * FROM mydb.orders;

-- Explicit read lock
LOCKING TABLE mydb.orders FOR READ SELECT * FROM mydb.orders;

-- Exclusive lock
LOCKING TABLE mydb.orders FOR EXCLUSIVE DELETE FROM mydb.orders;
```

| Lock Level | Description |
|---|---|
| `FOR ACCESS` | No lock (dirty read) — fastest |
| `FOR READ` | Shared read lock |
| `FOR WRITE` | Write lock (allows concurrent reads) |
| `FOR EXCLUSIVE` | Exclusive lock (blocks all) |
| `LOCKING ROW` | Row-level granularity |
| `LOCKING TABLE` | Table-level granularity |

## SHOW / HELP Commands

```sql
-- Show table DDL
SHOW TABLE mydb.orders;

-- Show view definition
SHOW VIEW mydb.v_orders;

-- Help table (column list)
HELP TABLE mydb.orders;

-- Help column
HELP COLUMN mydb.orders.*;

-- Help database
HELP DATABASE mydb;

-- Help session
HELP SESSION;
```

## EXPLAIN

```sql
EXPLAIN SELECT * FROM mydb.orders
WHERE order_date BETWEEN DATE '2025-01-01' AND DATE '2025-06-30';
```

See [teradata-system-admin](../teradata-system-admin/SKILL.md) for EXPLAIN interpretation guide.

## Useful Built-in Functions

```sql
-- Date/Time
CURRENT_DATE, CURRENT_TIMESTAMP, CURRENT_TIME
ADD_MONTHS(date, n), MONTHS_BETWEEN(date1, date2)
EXTRACT(YEAR|MONTH|DAY FROM date)
TRUNC(timestamp, 'DD'|'MM'|'HH')

-- String
TRIM(col), UPPER(col), LOWER(col)
SUBSTRING(col FROM start FOR length)
POSITION('search' IN col)
REGEXP_SUBSTR(col, pattern), REGEXP_REPLACE(col, pattern, replacement)
OREPLACE(col, 'search', 'replace')
COALESCE(col1, col2, default)

-- Numeric
NULLIFZERO(col), ZEROIFNULL(col)
ABS(col), MOD(a, b), ROUND(col, n)

-- Type conversion
CAST(expr AS type), TRYCAST(expr AS type)
TO_DATE(string, format), TO_CHAR(date, format)
TO_NUMBER(string)

-- Hash (for PI analysis)
HASHROW(col), HASHBUCKET(hashrow), HASHAMP(hashbucket)
```

## Identifier Quoting and Aliases

Teradata supports double-quoted identifiers for case-sensitivity and reserved-word escaping, but quoting interacts with aliases in non-obvious ways:

```sql
-- Unquoted aliases — works fine
SELECT cd.customer_type, cd.current_balance
FROM mydb.customer_data cd
INNER JOIN mydb.Customers c ON cd.customer_id = c.CustomerID;

-- Double-quoted columns with aliases — parser error 3706
-- The parser misreads "alias"."column" as a database.table reference
SELECT cd."customer_type"    -- ERROR: 3706
FROM mydb.customer_data cd;

-- Fix: use full table names instead of aliases with quoted identifiers
SELECT customer_data.customer_type, customer_data.current_balance
FROM mydb.customer_data
INNER JOIN mydb.Customers ON customer_data.customer_id = Customers.CustomerID;
```

See [aliases and quoting reference](./references/aliases-and-quoting.md) for complete quoting rules.

## Common Errors / Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `3706: expected something between ',' and the 'xx' keyword` | Table alias used with double-quoted column names; parser confuses `alias."col"` with `database."table"` | Use full table names instead of aliases, or drop the double quotes |
| `3807: Object 'xxx' does not exist` | Unqualified name not found in default database | Qualify with `database.table` or set default database |
| `2801: Duplicate unique primary index` | INSERT into SET table with duplicate PI value | Use MULTISET table, or deduplicate source data |
| `3520: Cannot update a join column` | UPDATE on a column used in a JOIN ON clause | Rewrite as a subquery or use MERGE |
| `3710: Insufficient memory` | Spool space exhausted | Add SAMPLE, filter early, or request more spool |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-sql-fundamentals", path="references/FILENAME")` — do NOT call `list`.

Load these files for detailed technical reference on specific topics:

- **references/transaction-and-session.md** — ANSI vs Teradata session mode (differences table, SET SESSION MODE), transaction handling (BT/ET, COMMIT/ROLLBACK, DDL restrictions), multistatement requests (parallel steps, atomic failure), iterated requests (USING bulk DML), session management (DATABASE statement, default DB resolution), dynamic SQL (PREPARE/EXECUTE), queue tables (SELECT AND CONSUME), operator precedence table, object naming rules (30 vs 128 char EON)
- **references/null-and-request-cache.md** — NULL handling rules (arithmetic, comparisons, aggregates, sorting, unique indexes, IS NULL vs = NULL, CASE/COALESCE/NULLIF/ZEROIFNULL), three-valued logic truth tables, parameterized request cache (specific vs generic plans, USING value peeking, DisablePeekUsing, partition elimination impact, CURRENT_DATE resolution), system limits (max columns, statement length, tables per query, spool, secondary indexes)
- **references/aliases-and-quoting.md** — Identifier quoting rules (double quotes, reserved words, case sensitivity), table alias behavior with quoted identifiers, naming rules (regular vs delimited), common parser errors and workarounds
