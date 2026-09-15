# Recursive View Patterns — Complete Reference

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 4

## Pattern 1: Organization Hierarchy with Full Path

Build a full path string showing the management chain.

```sql
CREATE RECURSIVE VIEW mydb.v_org_path
    (employee_id, employee_name, manager_id, lvl, path) AS
(
    -- Anchor: CEO / top-level managers
    SELECT employee_id, employee_name, manager_id, 1,
           CAST(employee_name AS VARCHAR(2000))
    FROM mydb.employees
    WHERE manager_id IS NULL

    UNION ALL

    SELECT e.employee_id, e.employee_name, e.manager_id, o.lvl + 1,
           o.path || ' > ' || TRIM(e.employee_name)
    FROM mydb.employees e
    INNER JOIN mydb.v_org_path o ON e.manager_id = o.employee_id
    WHERE o.lvl < 15
);
```

### Usage

```sql
-- Find all reports under a specific manager
SELECT employee_name, lvl, path
FROM mydb.v_org_path
WHERE path LIKE '%John Smith%'
ORDER BY lvl;

-- Count direct and indirect reports per manager
SELECT manager_id, COUNT(*) - 1 AS total_reports
FROM mydb.v_org_path
GROUP BY manager_id;
```

## Pattern 2: Bill of Materials with Cumulative Quantity

Calculate the total quantity of each component needed for an assembly.

```sql
CREATE RECURSIVE VIEW mydb.v_bom_qty
    (top_assembly, component_id, component_name, qty_per_assembly, depth) AS
(
    -- Anchor: direct components of each top assembly
    SELECT b.parent_id, b.child_id, p.part_name, b.quantity, 1
    FROM mydb.bom b
    INNER JOIN mydb.parts p ON b.child_id = p.part_id
    WHERE b.parent_id IN (SELECT assembly_id FROM mydb.assemblies)

    UNION ALL

    -- Recursive: sub-components with multiplied quantities
    SELECT v.top_assembly, b.child_id, p.part_name,
           v.qty_per_assembly * b.quantity, v.depth + 1
    FROM mydb.bom b
    INNER JOIN mydb.v_bom_qty v ON b.parent_id = v.component_id
    INNER JOIN mydb.parts p ON b.child_id = p.part_id
    WHERE v.depth < 20
);
```

### Total Component Requirements

```sql
SELECT top_assembly, component_id, component_name,
       SUM(qty_per_assembly) AS total_needed
FROM mydb.v_bom_qty
GROUP BY top_assembly, component_id, component_name
ORDER BY top_assembly, total_needed DESC;
```

## Pattern 3: Graph Traversal (Network Paths)

Find all paths between nodes in a network (e.g., flight routes, network topology).

```sql
CREATE RECURSIVE VIEW mydb.v_network_paths
    (origin, destination, hops, route) AS
(
    -- Anchor: direct connections
    SELECT from_node, to_node, 1,
           CAST(from_node || '->' || to_node AS VARCHAR(4000))
    FROM mydb.connections

    UNION ALL

    -- Recursive: extend paths by one hop
    SELECT p.origin, c.to_node, p.hops + 1,
           p.route || '->' || TRIM(c.to_node)
    FROM mydb.v_network_paths p
    INNER JOIN mydb.connections c ON p.destination = c.from_node
    WHERE p.hops < 10
      AND POSITION(TRIM(c.to_node) IN p.route) = 0  -- prevent cycles
);
```

### Shortest Path

```sql
SELECT origin, destination, MIN(hops) AS shortest_hops
FROM mydb.v_network_paths
WHERE origin = 'A' AND destination = 'Z'
GROUP BY origin, destination;
```

## Pattern 4: Date Range Expansion

Generate a row for each date in a range (useful for gap-filling).

```sql
CREATE RECURSIVE VIEW mydb.v_calendar
    (cal_date) AS
(
    SELECT DATE '2020-01-01'

    UNION ALL

    SELECT cal_date + INTERVAL '1' DAY
    FROM mydb.v_calendar
    WHERE cal_date < DATE '2030-12-31'
);
```

### Usage with LEFT JOIN for Gap-Filling

```sql
SELECT c.cal_date, COALESCE(s.total_sales, 0) AS total_sales
FROM mydb.v_calendar c
LEFT JOIN mydb.v_daily_sales s ON c.cal_date = s.sale_date
WHERE c.cal_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31'
ORDER BY c.cal_date;
```

## Pattern 5: Category Tree Flattening

Flatten a category hierarchy into columns.

```sql
CREATE RECURSIVE VIEW mydb.v_category_tree
    (cat_id, cat_name, parent_id, root_id, root_name, lvl) AS
(
    -- Anchor: root categories
    SELECT category_id, category_name, parent_category_id,
           category_id, category_name, 1
    FROM mydb.categories
    WHERE parent_category_id IS NULL

    UNION ALL

    SELECT c.category_id, c.category_name, c.parent_category_id,
           t.root_id, t.root_name, t.lvl + 1
    FROM mydb.categories c
    INNER JOIN mydb.v_category_tree t ON c.parent_category_id = t.cat_id
    WHERE t.lvl < 10
);
```

## Cycle Detection

Teradata does not have built-in cycle detection in recursive views. Implement manually:

### Using Path String

```sql
-- In the recursive member, check if the node is already in the path
WHERE POSITION(TRIM(CAST(child_id AS VARCHAR(20))) IN v.path_string) = 0
```

### Using Depth Limit

```sql
-- Always include a depth/level limit to prevent infinite recursion
WHERE v.depth < 20
```

> **Important:** Without cycle detection, a recursive view on cyclic data will run indefinitely until the system kills the query. Always include a depth limit.

## Performance Considerations

| Factor | Impact |
|--------|--------|
| Depth limit | Lower limits = faster but may miss deep branches |
| UNION ALL | Required — UNION would remove duplicates (expensive and not supported) |
| Spool space | Recursive views can consume large amounts of spool — monitor spool usage |
| Join complexity | Keep the recursive query simple — complex joins in each recursion multiply cost |
| Index on join column | Ensure the recursive join column has a PI or secondary index |

### Optimization Tips

1. **Index the parent/child columns** — recursive joins on these columns happen repeatedly
2. **Use narrow column types** — especially for the path string (VARCHAR, not CLOB)
3. **Filter early** — apply WHERE conditions in the anchor query when possible
4. **Set realistic depth limits** — most hierarchies are 10-15 levels deep

## REPLACE RECURSIVE VIEW

```sql
REPLACE RECURSIVE VIEW mydb.v_org_chart
    (employee_id, employee_name, manager_id, lvl) AS
(
    SELECT employee_id, employee_name, manager_id, 1
    FROM mydb.employees
    WHERE manager_id IS NULL
    UNION ALL
    SELECT e.employee_id, e.employee_name, e.manager_id, o.lvl + 1
    FROM mydb.employees e
    INNER JOIN mydb.v_org_chart o ON e.manager_id = o.employee_id
);
```

- Same semantics as REPLACE VIEW — retains privileges if view exists, creates if not
