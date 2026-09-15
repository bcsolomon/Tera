---
name: views-and-recursive-views
description: 'Create and manage Teradata views using CREATE VIEW, REPLACE VIEW, CREATE RECURSIVE VIEW, and REPLACE RECURSIVE VIEW DDL. Use when creating views over tables or other views, replacing view definitions, creating recursive views for hierarchical data traversal (bill of materials, org charts, graph traversal), using WITH CHECK OPTION for updatable views, specifying LOCKING clauses in views, renaming or dropping views, or querying DBC.TVM for view metadata.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Views and Recursive Views

## When to Use

- Creating views to simplify complex queries or restrict column access
- Replacing existing view definitions without dropping and recreating
- Building recursive views for hierarchical or graph data (org charts, BOMs)
- Making views updatable with WITH CHECK OPTION
- Embedding LOCKING clauses in views to control lock behavior
- Renaming or dropping views

## CREATE VIEW Syntax

```sql
CREATE VIEW [database_name.]view_name AS
  [LOCKING locking_clause]
  SELECT column_list
  FROM table_or_view [, ...]
  [WHERE conditions]
  [WITH CHECK OPTION]
;
```

### REPLACE VIEW

```sql
REPLACE VIEW [database_name.]view_name AS
  SELECT column_list
  FROM table_or_view
  [WHERE conditions]
;
```

- If the view exists, replaces its definition and retains existing privileges
- If the view does not exist, creates a new view

## Common Patterns

### Simple View (Column Restriction)

```sql
CREATE VIEW mydb.v_employee_public AS
    SELECT employee_id, employee_name, department_id, hire_date
    FROM mydb.employees;
```

### Filtered View (Row Restriction)

```sql
CREATE VIEW mydb.v_active_orders AS
    SELECT order_id, customer_id, order_date, amount
    FROM mydb.orders
    WHERE status = 'ACTIVE';
```

### Join View

```sql
CREATE VIEW mydb.v_order_details AS
    SELECT o.order_id, o.order_date, o.amount,
           c.customer_name, c.region
    FROM mydb.orders o
    INNER JOIN mydb.customers c ON o.customer_id = c.customer_id;
```

### Aggregate View

```sql
CREATE VIEW mydb.v_daily_sales AS
    SELECT order_date,
           COUNT(*) AS order_count,
           SUM(amount) AS total_amount
    FROM mydb.orders
    GROUP BY order_date;
```

### View with Column Aliases

```sql
CREATE VIEW mydb.v_emp_summary (emp_id, full_name, dept, start_date) AS
    SELECT employee_id, employee_name, department_id, hire_date
    FROM mydb.employees;
```

## Updatable Views

A view is updatable if:
- It selects from a single base table
- It includes the primary index columns
- It does not use DISTINCT, GROUP BY, HAVING, aggregates, or UNION

### WITH CHECK OPTION

Ensures INSERT/UPDATE through the view satisfies the view's WHERE clause.

```sql
CREATE VIEW mydb.v_us_customers AS
    SELECT customer_id, customer_name, country
    FROM mydb.customers
    WHERE country = 'US'
    WITH CHECK OPTION;

-- This INSERT succeeds:
INSERT INTO mydb.v_us_customers VALUES (100, 'Acme Corp', 'US');

-- This INSERT fails (violates WITH CHECK OPTION):
INSERT INTO mydb.v_us_customers VALUES (101, 'Euro Ltd', 'UK');
```

## LOCKING Clause in Views

Embed lock-level preferences directly in the view definition.

```sql
CREATE VIEW mydb.v_report AS
    LOCKING mydb.orders FOR ACCESS
    SELECT order_date, SUM(amount) AS total
    FROM mydb.orders
    GROUP BY order_date;
```

### LOCKING Options

| Lock | Behavior |
|------|----------|
| `FOR ACCESS` | Dirty read — no locks, fastest, may see uncommitted data |
| `FOR READ` | Shared read lock |
| `FOR WRITE` | Write lock |
| `FOR EXCLUSIVE` | Exclusive lock |

## Recursive Views

Recursive views enable hierarchical or graph traversal queries using recursive CTEs embedded in a view.

### CREATE RECURSIVE VIEW Syntax

```sql
CREATE RECURSIVE VIEW [database_name.]view_name
    (column_name [,...]) AS
  anchor_query
  UNION ALL
  recursive_query
;
```

### Organization Chart Example

```sql
CREATE RECURSIVE VIEW mydb.v_org_chart
    (employee_id, employee_name, manager_id, lvl) AS
(
    -- Anchor: top-level managers (no manager)
    SELECT employee_id, employee_name, manager_id, 1
    FROM mydb.employees
    WHERE manager_id IS NULL

    UNION ALL

    -- Recursive: employees reporting to previously found managers
    SELECT e.employee_id, e.employee_name, e.manager_id, o.lvl + 1
    FROM mydb.employees e
    INNER JOIN mydb.v_org_chart o ON e.manager_id = o.employee_id
);
```

### Bill of Materials Example

```sql
CREATE RECURSIVE VIEW mydb.v_bom
    (parent_part, child_part, quantity, depth) AS
(
    -- Anchor: top-level assemblies
    SELECT parent_part_id, child_part_id, quantity, 1
    FROM mydb.bill_of_materials
    WHERE parent_part_id IN (SELECT part_id FROM mydb.top_assemblies)

    UNION ALL

    -- Recursive: sub-components
    SELECT b.parent_part_id, b.child_part_id, b.quantity, v.depth + 1
    FROM mydb.bill_of_materials b
    INNER JOIN mydb.v_bom v ON b.parent_part_id = v.child_part
    WHERE v.depth < 20  -- safety limit
);
```

### Recursive View Rules

| Rule | Detail |
|------|--------|
| Column list | Required — must list all columns in the view definition |
| Anchor query | Must not reference the recursive view |
| Recursive query | Must reference the recursive view exactly once |
| UNION ALL | Required — UNION (without ALL) is not allowed |
| Depth limit | Use a depth/level column with WHERE to prevent infinite recursion |
| Aggregates | Not allowed in the recursive query |
| DISTINCT | Not allowed in the recursive query |

## RENAME VIEW

```sql
RENAME VIEW [database_name.]old_view_name TO new_view_name;
```

## DROP VIEW

```sql
DROP VIEW [database_name.]view_name;
```

- Does not affect the underlying tables
- Other views that reference the dropped view become invalid

## Querying View Metadata

```sql
-- List views in a database
SELECT TableName, CreateTimeStamp, LastAlterTimeStamp
FROM DBC.TablesV
WHERE DatabaseName = 'mydb'
  AND TableKind = 'V';

-- View the definition
SHOW VIEW mydb.v_employee_public;

-- View column details
HELP VIEW mydb.v_employee_public;
```

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| 3706: Syntax error in view | Invalid SQL in view body | Validate the SELECT independently first |
| 3523: View already exists | CREATE VIEW on existing view | Use REPLACE VIEW instead |
| 5765: WITH CHECK OPTION violation | INSERT/UPDATE violates view filter | Ensure data matches view WHERE clause |
| 3807: Object does not exist | Referenced table dropped | Recreate the table or update the view |

## Privileges Required

- `CREATE VIEW` on the target database
- `SELECT` on all underlying tables (with GRANT OPTION for non-owner access)
- `DROP VIEW` to drop or replace an existing view

## References


> **Access:** `skill_resource_read(action="read", skill="views-and-recursive-views", path="references/FILENAME")` — do NOT call `list`.

- [Recursive View Patterns](./references/recursive-view-patterns.md) — Detailed recursive CTE patterns for hierarchies, graphs, path enumeration, and cycle detection

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 4
