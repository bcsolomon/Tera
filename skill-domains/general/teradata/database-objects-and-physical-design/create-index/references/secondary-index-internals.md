# Secondary Index Internals — Complete Reference

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 5

## USI (Unique Secondary Index) Architecture

A USI is implemented as a **subtable** distributed across all AMPs. Each subtable row contains:

1. The hash of the secondary index value (determines which AMP holds the subtable row)
2. The secondary index column value(s)
3. The row ID of the base table row (AMP + partition + row hash + uniqueness value)

### USI Lookup Process

1. User submits query with `WHERE usi_column = value`
2. System hashes the value → identifies the AMP holding the subtable row
3. Reads the subtable row on that AMP → gets the base table row ID
4. Uses the row ID to access the base table row on the owning AMP

**Result:** 2-AMP operation (subtable AMP + base table AMP). Very efficient for point lookups.

### USI and NULL Values

- If a USI column is nullable, only one NULL is allowed across the entire table
- If the USI is on multiple columns, the combination must be unique (individual columns can repeat)

## NUSI (Non-Unique Secondary Index) Architecture

A NUSI subtable is stored **locally on each AMP** alongside the base table data. Each AMP's subtable contains entries only for the base table rows stored on that AMP.

### NUSI Subtable Row Contents

1. The secondary index column value(s)
2. A bitmap or list of row IDs for base table rows with that value on this AMP

### NUSI Lookup Process

1. User submits query with `WHERE nusi_column = value`
2. System sends the request to **all AMPs** (all-AMP operation)
3. Each AMP searches its local NUSI subtable for matching entries
4. Each AMP uses the row IDs to access matching base table rows locally

**Result:** All-AMP operation but each AMP only accesses local data. Good when many AMPs each return a few rows.

### NUSI Bit Mapping

For low-cardinality columns, the NUSI subtable uses **bit maps** rather than explicit row lists:
- One bit per row in the AMP's partition
- Bit = 1 means the row matches the index value
- Very compact for columns with few distinct values

## Value-Ordered Secondary Indexes

A value-ordered NUSI stores subtable rows sorted by the column value rather than by row hash.

```sql
CREATE INDEX idx_amount ORDER BY VALUES (amount) ON mydb.transactions (amount);
```

### Benefits
- Range scans (`BETWEEN`, `>`, `<`) can use the sorted subtable directly
- Avoids full subtable scan for range predicates
- Optimizer can use the index for `ORDER BY` on the indexed column

### When to Use
- Range queries on non-PI columns: `WHERE amount BETWEEN 100 AND 500`
- Top-N queries: `SELECT TOP 10 ... ORDER BY amount`
- Aggregate queries on sorted data: `GROUP BY` on the indexed column

### Restrictions
- Cannot specify `UNIQUE` with `ORDER BY`
- Cannot specify `ALL` with `ORDER BY`
- The order column must be one of the index columns

## Hash-Ordered Secondary Indexes

Default behavior — subtable rows are stored in hash order of the index value.

```sql
CREATE INDEX idx_hash ORDER BY HASH (lookup_key) ON mydb.lookup_table (lookup_key);
```

### When to Use
- Equality lookups: `WHERE column = value`
- When range scans are not needed

## Covering Indexes

A **covering index** contains all columns needed to satisfy a query, eliminating the need to access the base table.

```sql
-- NUSI that covers queries needing only customer_id and order_date
CREATE INDEX idx_cust_date ON mydb.orders (customer_id, order_date);

-- Query covered by this index (no base table access needed)
SELECT customer_id, order_date FROM mydb.orders
WHERE customer_id = 12345;
```

### ALL Keyword for Join Index NUSIs

```sql
CREATE INDEX idx_ji_all ALL (column_name) ON mydb.my_join_index;
```

- `ALL` maintains row ID pointers for each logical row of a join index
- Enables the NUSI to cover the join index
- Without `ALL`, the NUSI only stores compressed physical rows

## LOAD IDENTITY

```sql
CREATE INDEX idx_load ORDER BY VALUES (col1)
    WITH LOAD IDENTITY
    ON mydb.staging_table (col1);
```

- Assigns a load identity for concurrent load isolation
- Used with `BEGIN ISOLATED LOADING` for concurrent utility operations
- `WITH NO LOAD IDENTITY` is the default

## Index Naming Best Practices

| Convention | Example | Notes |
|------------|---------|-------|
| Prefix with `idx_` | `idx_email` | Distinguishes from other objects |
| Include table hint | `idx_emp_dept` | `emp` = employees, `dept` = department_id |
| Indicate type | `usi_email`, `nusi_dept` | Optional but aids documentation |

### Named vs Unnamed Indexes

```sql
-- Named (preferred — easier to manage)
CREATE INDEX idx_dept ON mydb.employees (department_id);
DROP INDEX idx_dept ON mydb.employees;

-- Unnamed (must drop by column definition)
CREATE INDEX (department_id) ON mydb.employees;
DROP INDEX (department_id) ON mydb.employees;
```

## Statistics on Secondary Indexes

- Collect statistics on NUSI columns to help the optimizer estimate selectivity
- Without stats, the optimizer may skip NUSI access in favor of full-table scan
- USI lookups are typically chosen regardless of statistics (cost is always 2 AMPs)

```sql
COLLECT STATISTICS ON mydb.employees INDEX (department_id);
COLLECT STATISTICS ON mydb.employees INDEX idx_dept;
```

## Secondary Index Maintenance Cost

Every INSERT, UPDATE, or DELETE on the base table also updates all secondary index subtables:

| Operation | USI Cost | NUSI Cost |
|-----------|----------|-----------|
| INSERT | Update subtable on the USI AMP | Update local subtable on the row's AMP |
| UPDATE (indexed col) | Delete old + insert new subtable entry | Update local subtable |
| DELETE | Delete subtable entry | Update local subtable |

### Guidelines
- Limit indexes on tables with heavy DML to reduce maintenance overhead
- Consider dropping indexes before bulk loads, then recreating
- Monitor with `DBC.IndicesV` and `HELP INDEX` to audit index usage
