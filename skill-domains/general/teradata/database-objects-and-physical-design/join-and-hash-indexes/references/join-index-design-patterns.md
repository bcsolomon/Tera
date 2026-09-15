# Join Index Design Patterns — Complete Reference

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 5

## Single-Table Join Index Patterns

### Alternate Access Path

Redistribute a table on a different column than its primary index for queries that don't use the PI.

```sql
-- Base table: PI on customer_id
CREATE MULTISET TABLE mydb.orders (
    order_id     INTEGER NOT NULL,
    customer_id  INTEGER NOT NULL,
    order_date   DATE NOT NULL,
    product_id   INTEGER,
    amount       DECIMAL(15,2)
) PRIMARY INDEX (customer_id);

-- Join index: redistribute on order_date for date-range queries
CREATE JOIN INDEX mydb.ji_orders_by_date AS
    SELECT order_id, customer_id, order_date, product_id, amount
    FROM mydb.orders
PRIMARY INDEX (order_date);
```

**When the optimizer uses it:** Queries with `WHERE order_date = ...` or `WHERE order_date BETWEEN ... AND ...` use the join index instead of full-table-scanning the base table.

### Column Subset (Projection Index)

Store only the columns needed for a specific query pattern.

```sql
CREATE JOIN INDEX mydb.ji_order_summary AS
    SELECT order_id, order_date, amount
    FROM mydb.orders
PRIMARY INDEX (order_id);
```

**Benefit:** Smaller row size = more rows per data block = faster scans for queries needing only these columns.

## Multi-Table Join Index Patterns

### Star Schema Acceleration

Pre-join a fact table with dimension tables for star-schema queries.

```sql
CREATE JOIN INDEX mydb.ji_sales_star AS
    SELECT f.sale_id, f.sale_date, f.quantity, f.revenue,
           p.product_name, p.category,
           s.store_name, s.region
    FROM mydb.sales_fact f
    INNER JOIN mydb.dim_product p ON f.product_id = p.product_id
    INNER JOIN mydb.dim_store s ON f.store_id = s.store_id
PRIMARY INDEX (sale_id);
```

### Two-Table Denormalization

```sql
CREATE JOIN INDEX mydb.ji_emp_dept AS
    SELECT e.employee_id, e.employee_name, e.hire_date,
           d.department_name, d.location
    FROM mydb.employees e
    INNER JOIN mydb.departments d ON e.department_id = d.department_id
PRIMARY INDEX (employee_id);
```

### Restrictions on Multi-Table Join Indexes
- Only inner joins and left outer joins are supported
- No self-joins
- No subqueries in the SELECT list
- Join columns must be equality conditions
- No DISTINCT, HAVING, or window functions

## Aggregate Join Index Patterns

### Daily Summary

```sql
CREATE JOIN INDEX mydb.ji_daily_revenue AS
    SELECT sale_date,
           store_id,
           SUM(revenue) AS total_revenue,
           COUNT(*) AS transaction_count,
           SUM(quantity) AS total_quantity
    FROM mydb.sales_fact
    GROUP BY sale_date, store_id
PRIMARY INDEX (sale_date);
```

### Monthly Rollup

```sql
CREATE JOIN INDEX mydb.ji_monthly_sales AS
    SELECT EXTRACT(YEAR FROM sale_date) AS sale_year,
           EXTRACT(MONTH FROM sale_date) AS sale_month,
           category_id,
           SUM(revenue) AS monthly_revenue,
           COUNT(*) AS monthly_count
    FROM mydb.sales_fact
    GROUP BY 1, 2, 3
PRIMARY INDEX (sale_year, sale_month);
```

### Aggregate Function Support

| Function | Supported in Aggregate JI |
|----------|--------------------------|
| `SUM()` | Yes |
| `COUNT(*)` | Yes |
| `COUNT(column)` | Yes |
| `MIN()` | Yes — but cannot be incrementally maintained for DELETE |
| `MAX()` | Yes — but cannot be incrementally maintained for DELETE |
| `AVG()` | No — use `SUM/COUNT` instead |
| Window functions | No |

> **Note:** `MIN` and `MAX` in aggregate join indexes require full recomputation on DELETE operations. Prefer `SUM`/`COUNT` for tables with frequent deletes.

## Sparse Join Index Patterns

### Active Records Only

```sql
CREATE JOIN INDEX mydb.ji_active_orders AS
    SELECT order_id, customer_id, order_date, amount
    FROM mydb.orders
    WHERE order_status = 'ACTIVE'
PRIMARY INDEX (order_id);
```

### Recent Data Window

```sql
CREATE JOIN INDEX mydb.ji_recent_transactions AS
    SELECT txn_id, account_id, txn_date, amount, txn_type
    FROM mydb.transactions
    WHERE txn_date >= DATE '2025-01-01'
PRIMARY INDEX (txn_id);
```

### High-Value Subset

```sql
CREATE JOIN INDEX mydb.ji_premium_customers AS
    SELECT c.customer_id, c.customer_name, c.tier,
           o.order_id, o.amount
    FROM mydb.customers c
    INNER JOIN mydb.orders o ON c.customer_id = o.customer_id
    WHERE c.tier = 'PREMIUM'
PRIMARY INDEX (customer_id);
```

### Sparse Join Index Maintenance
- Only rows matching the WHERE clause are stored
- DML on base tables is evaluated against the WHERE clause
- INSERT: new row added to JI only if it matches the filter
- UPDATE: row added/removed from JI if the filter columns change
- DELETE: row removed from JI if it was included

## Hash Index Patterns

### Alternate Distribution

```sql
CREATE HASH INDEX mydb.hi_orders_by_product
    (order_id, customer_id, order_date, amount)
    ON mydb.orders
    BY (product_id);
```

### Value-Ordered Hash Index

```sql
CREATE HASH INDEX mydb.hi_emp_salary
    (employee_id, employee_name, salary)
    ON mydb.employees
    BY (department_id)
    ORDER BY VALUES (salary);
```

### Hash Index vs Single-Table Join Index

| Aspect | Hash Index | Single-Table JI |
|--------|-----------|-----------------|
| Syntax | Column list + `BY` clause | Full `SELECT ... FROM` |
| Aggregation | No | Yes |
| WHERE filter | No | Yes |
| Flexibility | Less (column list only) | More (full query) |
| Use case | Simple redistribution | Complex projections |

## Optimizer Interaction

The optimizer automatically considers join indexes when:
1. The query columns are a subset of the join index columns (covering)
2. The join conditions match the join index definition
3. The estimated cost of using the join index is lower than base table access

### Verifying Join Index Usage

```sql
EXPLAIN SELECT sale_date, SUM(revenue)
FROM mydb.sales_fact
GROUP BY sale_date;
```

Look for: `"retrieved from join index mydb.ji_daily_revenue"` in the EXPLAIN output.

### Forcing Join Index Consideration

If the optimizer ignores a join index:
1. Collect statistics on the join index columns
2. Verify the query columns are covered by the join index
3. Check that the join index is not stale (HELP JOIN INDEX)

## Space and Maintenance Considerations

| Factor | Impact |
|--------|--------|
| Perm space | Join indexes consume space proportional to their row count × row size |
| DML overhead | Every INSERT/UPDATE/DELETE on base tables triggers join index maintenance |
| Statistics | Collect statistics on join index columns separately from base tables |
| Rebuild | Use `ALTER JOIN INDEX ... REBUILD` after bulk operations if needed |

### Estimating Space

```sql
-- Approximate space used by a join index
SELECT SUM(CurrentPerm) AS bytes_used
FROM DBC.TableSizeV
WHERE DatabaseName = 'mydb'
  AND TableName = 'ji_orders_by_date';
```
