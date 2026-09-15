# Iceberg and Delta Lake Operations — Complete Reference

> Source: Teradata Open Table Format for Apache Iceberg and Delta Lake User Guide; TD OTF Test Environment and Sample Queries (internal)

---

## OTF Table Addressing

All OTF tables use a three-part name: `datalake_name.database_name.table_name`

```sql
-- Pattern
SELECT ... FROM <datalake>.<database>.<table>;

-- Example
SELECT * FROM prod_iceberg.sales_db.orders;
```

---

## Discovery: HELP Commands

Use HELP commands to navigate the catalog hierarchy before querying.

### List Databases in a Datalake

```sql
HELP DATALAKE prod_iceberg;
```

Returns: All database names registered in the catalog.

Example output:
```
DatabaseName
---------------------------------------------------------------------------
sales_db
hr_records
marketing_db
ecommerce
```

### List Tables in a Database

```sql
HELP DATABASE prod_iceberg.sales_db;
```

Returns: All table and view names in the specified database.

### List Columns of a Table

```sql
HELP TABLE prod_iceberg.sales_db.orders;
```

Returns: Column names. Use `SHOW TABLE` for full DDL including types and constraints.

### Show Table DDL

```sql
SHOW TABLE prod_iceberg.sales_db.orders;
```

---

## SELECT Queries

### Basic Queries

```sql
-- All rows
SELECT * FROM prod_iceberg.sales_db.orders;

-- Filtered
SELECT order_id, customer_id, order_date, total
FROM prod_iceberg.sales_db.orders
WHERE order_date BETWEEN DATE '2024-01-01' AND DATE '2024-12-31';

-- Aggregation
SELECT DATE_TRUNC('month', order_date) AS month,
       COUNT(*) AS order_count,
       SUM(total) AS revenue
FROM prod_iceberg.sales_db.orders
GROUP BY 1
ORDER BY 1;

-- Join OTF table with local Teradata table
SELECT c.customer_name, o.order_date, o.total
FROM prod_iceberg.sales_db.orders o
JOIN my_local_db.customers c ON o.customer_id = c.id
WHERE o.total > 1000;
```

### Cross-Format Joins

OTF tables can be joined with:
- Other OTF tables in the same or different datalake
- Teradata native tables
- NOS foreign tables

```sql
-- Join Iceberg with NOS foreign table
SELECT i.order_id, n.shipment_date
FROM prod_iceberg.sales_db.orders i
JOIN mydb.external_shipments n ON i.order_id = n.order_id;
```

---

## Data Movement: OTF to Teradata

Load OTF data into Teradata tables for high-performance processing.

```sql
-- Create Teradata table from OTF source
CREATE MULTISET TABLE my_db.orders_snapshot AS (
    SELECT * FROM prod_iceberg.sales_db.orders
    WHERE order_date = CURRENT_DATE - 1
) WITH DATA PRIMARY INDEX (order_id);

-- Incremental load via INSERT
INSERT INTO my_db.orders_daily
SELECT order_id, customer_id, total, order_date
FROM prod_iceberg.sales_db.orders
WHERE order_date = CURRENT_DATE - 1;
```

---

## Apache Iceberg — Format-Specific Operations

### Time Travel

Iceberg tables maintain a complete history of snapshots. Use `FOR TIMESTAMP AS OF` or `FOR VERSION AS OF` to query historical data.

```sql
-- Query as of a specific point in time
SELECT * FROM prod_iceberg.sales_db.orders
FOR TIMESTAMP AS OF TIMESTAMP '2024-06-01 00:00:00';

-- Query as of a specific snapshot ID
SELECT * FROM prod_iceberg.sales_db.orders
FOR VERSION AS OF 8912345678901234567;

-- Count rows at a past point in time
SELECT COUNT(*) FROM prod_iceberg.sales_db.orders
FOR TIMESTAMP AS OF TIMESTAMP '2024-01-01 00:00:00';
```

### Metadata Tables (Iceberg)

Iceberg exposes internal metadata as special tables using `$` suffix notation. These are read-only.

```sql
-- List all snapshots (history of writes)
SELECT * FROM prod_iceberg.sales_db."orders$snapshots";

-- View commit history
SELECT * FROM prod_iceberg.sales_db."orders$history";

-- View manifest files
SELECT * FROM prod_iceberg.sales_db."orders$manifests";

-- View data files in a snapshot
SELECT * FROM prod_iceberg.sales_db."orders$files";

-- View partition summary
SELECT * FROM prod_iceberg.sales_db."orders$partitions";
```

### Iceberg Snapshot Columns

| Column | Type | Description |
|--------|------|-------------|
| `committed_at` | TIMESTAMP | When this snapshot was committed |
| `snapshot_id` | BIGINT | Unique snapshot identifier — use with `FOR VERSION AS OF` |
| `parent_id` | BIGINT | Previous snapshot ID (NULL for first snapshot) |
| `operation` | VARCHAR | `append`, `replace`, `overwrite`, `delete` |
| `summary` | MAP | Statistics for this commit (added/deleted files, row counts) |

### Create Iceberg Table

When Teradata has write access to the catalog and storage:

```sql
CREATE TABLE prod_iceberg.new_db.products (
    product_id    INTEGER,
    product_name  VARCHAR(200),
    category      VARCHAR(100),
    price         DECIMAL(10, 2),
    created_at    TIMESTAMP
);
```

### DML on Iceberg Tables

OTF supports full ACID DML when the authorization has write permissions:

```sql
-- INSERT
INSERT INTO prod_iceberg.sales_db.orders
VALUES (10001, 'CUST-001', DATE '2024-07-01', 249.99, 'shipped');

-- UPDATE
UPDATE prod_iceberg.sales_db.orders
SET status = 'delivered'
WHERE order_id = 10001;

-- DELETE
DELETE FROM prod_iceberg.sales_db.orders
WHERE order_date < DATE '2020-01-01';

-- MERGE (upsert)
MERGE INTO prod_iceberg.sales_db.orders AS tgt
USING (SELECT * FROM my_db.orders_staging) AS src
ON tgt.order_id = src.order_id
WHEN MATCHED THEN UPDATE SET status = src.status, total = src.total
WHEN NOT MATCHED THEN INSERT VALUES (src.order_id, src.customer_id, src.order_date, src.total, src.status);
```

---

## Delta Lake — Format-Specific Operations

### Querying Delta Tables

Standard SELECT queries work the same way as Iceberg:

```sql
SELECT * FROM my_delta_lake.analytics_db.events
WHERE event_date = CURRENT_DATE;
```

### Delta Lake Time Travel

```sql
-- Query as of a specific timestamp
SELECT * FROM my_delta_lake.analytics_db.events
FOR TIMESTAMP AS OF TIMESTAMP '2024-06-01 00:00:00';

-- Query a specific Delta table version
SELECT * FROM my_delta_lake.analytics_db.events
FOR VERSION AS OF 42;
```

### Delta Metadata Tables

```sql
-- Transaction log history
SELECT * FROM my_delta_lake.analytics_db."events$history";

-- Delta table details
SELECT * FROM my_delta_lake.analytics_db."events$details";
```

### DML on Delta Tables

```sql
-- INSERT
INSERT INTO my_delta_lake.analytics_db.events
SELECT * FROM my_db.events_staging;

-- UPDATE
UPDATE my_delta_lake.analytics_db.events
SET processed = TRUE
WHERE event_date < CURRENT_DATE - 7;

-- DELETE
DELETE FROM my_delta_lake.analytics_db.events
WHERE event_type = 'test';
```

---

## Partition Pruning and Performance Tips

| Practice | Benefit |
|----------|---------|
| Filter on partition columns | Eliminates manifest scans; major speedup |
| Use `FOR TIMESTAMP AS OF` with recent snapshots | Old snapshot reads scan more manifests |
| Minimize `SELECT *` on wide tables | OTF reads are columnar — selecting fewer columns reduces I/O |
| Prefer `DATE` literals over string casts | Avoids implicit cast overhead on partition predicates |
| Use Teradata-local joins when possible | Push Teradata-managed tables to the inner side of joins |
| Load frequently-queried OTF data to Teradata native | For repeated heavy analytics, an `INSERT ... SELECT` materialize pattern is faster |

---

## Row Count and Table Stats

```sql
-- Row count
SELECT COUNT(*) FROM prod_iceberg.sales_db.orders;

-- Row count by partition (for Iceberg, via partitions metadata)
SELECT partition, record_count
FROM prod_iceberg.sales_db."orders$partitions";

-- Column distinct count (sampling)
SELECT APPROXCOUNT(DISTINCT customer_id)
FROM prod_iceberg.sales_db.orders;
```

---

## Collect OTF Statistics

The OTF manual documents statistics support for these SQL statements:
- `COLLECT STATS`
- `DROP STATS`
- `HELP STATS`
- `SHOW STATS`

**Statistics architecture**: OTF stats are stored in **DBC.StatsTbl** (same location as native Teradata statistics). Use **DBC.OtfStatsV** to view OTF-specific statistics.

**Key limitation**: OTF standard metadata provides **scalar stats only** — null count, distinct value count, min/max. **Histograms are not supported** for OTF tables. **Expression-based statistics are not supported** for OTF columns.

```sql
-- Collect column statistics
COLLECT STATS COLUMN(order_date) ON prod_iceberg.sales_db.orders;
COLLECT STATS COLUMN(customer_id) ON prod_iceberg.sales_db.orders;

-- Review collected statistics
SHOW STATS ON prod_iceberg.sales_db.orders;
HELP STATS prod_iceberg.sales_db.orders;

-- View OTF-specific stats
SELECT * FROM DBC.OtfStatsV
WHERE DatabaseName = 'prod_iceberg' AND TableName = 'orders';

-- Drop stale or no-longer-needed statistics
DROP STATS COLUMN(customer_id) ON prod_iceberg.sales_db.orders;
```

For heavily used workloads, refresh stats after major data volume changes.

---

## Creating and Maintaining OTF Databases and Tables

```sql
-- Create OTF database (if catalog supports namespace creation)
CREATE DATABASE prod_iceberg.new_domain;

-- Create OTF table
CREATE TABLE prod_iceberg.new_domain.events (
    event_id      BIGINT,
    event_ts      TIMESTAMP,
    event_type    VARCHAR(100),
    payload       JSON
);

-- Create from another table
CREATE TABLE prod_iceberg.new_domain.events_archive AS (
    SELECT * FROM prod_iceberg.new_domain.events
) WITH DATA;

-- Alter table
ALTER TABLE prod_iceberg.new_domain.events
ADD COLUMN source_system VARCHAR(64);

-- Drop table
DROP TABLE prod_iceberg.new_domain.events_archive;

-- Drop database (after objects are removed)
DROP DATABASE prod_iceberg.new_domain;
```

---

## Teradata-Managed OTF Tables and Retention

Teradata-managed OTF tables add lifecycle controls while still using open-table formats.

Retention is configured via the **`RETENTIONDAYS`** clause (integer days). Retention can be set at multiple levels: **profile → user → database → table** (table-level overrides all others). View retention settings in `DBC.ProfileInfoV` (profile level) and `DBC.DatabasesV` (database level).

```sql
-- Managed OTF table example
CREATE TABLE managed_iceberg_db.orders_managed (
    order_id      BIGINT,
    customer_id   BIGINT,
    order_ts      TIMESTAMP,
    total_amount  DECIMAL(18,2)
)
AS TABLE TYPE = ICEBERG;

-- Set retention at table level (30 days)
ALTER TABLE managed_iceberg_db.orders_managed SET RETENTIONDAYS = 30;

-- Set retention at database level
ALTER DATABASE managed_iceberg_db SET RETENTIONDAYS = 90;

-- Check retention settings
SELECT DatabaseName, RetentionDays FROM DBC.DatabasesV
WHERE DatabaseName = 'managed_iceberg_db';
```

Use short retention for transient intermediate tables, and longer retention for regulated workloads.

---

## Database Views for OTF Tables

Use views when you need stable semantic contracts for BI tools or to hide complex paths.

Supported statements: `CREATE VIEW`, `REPLACE VIEW`, `DROP VIEW`, `HELP VIEW`, and `SELECT` from views.

Views can join OTF tables with BFS (block file system) and OFS (object file system) tables.

**Key limitation**: Views are NOT automatically refreshed when the underlying OTF table schema changes (e.g., columns added or types changed). Users must manually run `REPLACE VIEW` after any OTF schema evolution to pick up changes.

```sql
CREATE VIEW analytics_db.v_orders_recent AS
SELECT order_id, customer_id, order_date, total
FROM prod_iceberg.sales_db.orders
WHERE order_date >= CURRENT_DATE - 30;

-- After OTF schema changes, refresh the view:
REPLACE VIEW analytics_db.v_orders_recent AS
SELECT order_id, customer_id, order_date, total, new_column
FROM prod_iceberg.sales_db.orders
WHERE order_date >= CURRENT_DATE - 30;
```

Alternatives to views:
- Use direct three-part names where schema contracts are stable.
- Use materialized local snapshots for repeated heavy transformations.

---

## Comparing Iceberg and Delta Lake in Teradata OTF

| Feature | Iceberg | Delta Lake |
|---------|---------|------------|
| Time travel | `FOR TIMESTAMP AS OF` / `FOR VERSION AS OF` | `FOR TIMESTAMP AS OF` / `FOR VERSION AS OF` |
| ACID DML | Yes (full MERGE support) | Yes |
| Metadata tables | `$snapshots`, `$history`, `$manifests`, `$files`, `$partitions` | `$history`, `$details` |
| Schema evolution | Full (add, drop, rename, reorder, widen) | Add columns only |
| Partition evolution | Yes (change partition spec without rewrite) | No |
| Z-order clustering | No | Yes |
| CDC / Change Data Feed | No (use snapshot diff) | Yes (`$cdf` metadata) |
| Catalog support | Glue, Hive, Polaris, Unity | Glue, Hive, Unity |
