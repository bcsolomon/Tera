# Column Partitioning & Primary AMP Index

## Column Partitioning Syntax

### Basic PARTITION BY COLUMN

```sql
PARTITION BY COLUMN [[NO] AUTO COMPRESS] [ADD n]
```

### With Explicit Format Specifications

```sql
PARTITION BY COLUMN [[NO] AUTO COMPRESS] [ALL BUT]
  ([COLUMN|ROW]{(column,...) | column} [[NO] AUTO COMPRESS], ...)
  [ADD n]
```

### Combined with Row Partitioning

```sql
PARTITION BY (
    COLUMN [[NO] AUTO COMPRESS] [ALL BUT] (...) [ADD n],
    RANGE_N(...) [ADD n]
    [, RANGE_N(...) [ADD n]]
)
```

## Column Partition Formats

| Format | Keyword | Storage | Best For |
|---|---|---|---|
| System-determined | `(col_list)` | System chooses COLUMN or ROW | Default |
| COLUMN (container) | `COLUMN(col_list)` | Multiple values packed into ~8KB containers | Most columns; autocompression |
| ROW (subrow) | `ROW(col_list)` | Each value as separate physical row | Wide VARCHAR, LOB, in-place updates |

### Autocompression Types (System-Selected)

- Null compression
- Run-length compression
- Local value-list compression (LVLC — dictionary per container)
- Trim compression (high-order zeros, trailing pads)
- Delta from mean
- UNICODE to UTF8 conversion

Autocompression carries forward the method from the last container — new data uses the same compression.

## COLUMN ALL BUT

When `ALL BUT` is specified, columns **not listed** each get their own single-column partition.
When `ALL BUT` is **not** specified, columns not listed are combined into **one** column partition.

```sql
-- ALL BUT: unlisted columns each get their own partition
CREATE TABLE mydb.orders (
    o_orderkey INTEGER NOT NULL,
    o_custkey INTEGER,
    o_orderstatus CHAR(1),
    o_totalprice DECIMAL(13,2),
    o_orderdate DATE,
    o_comment VARCHAR(79)
) NO PRIMARY INDEX
  PARTITION BY COLUMN ALL BUT (ROW(o_comment) NO AUTO COMPRESS);
-- o_orderkey, o_custkey, o_orderstatus, o_totalprice, o_orderdate
-- each get their own column partition (autocompressed)
-- o_comment is in its own ROW-format partition (no autocompression)

-- Without ALL BUT: unlisted columns combined
CREATE TABLE mydb.orders2 (...) NO PRIMARY INDEX
  PARTITION BY COLUMN (
    o_orderkey, o_custkey, o_orderstatus, o_totalprice,
    o_orderdate, ROW o_comment NO AUTO COMPRESS);
-- first 5 columns go into one partition together
-- o_comment in separate ROW partition
```

## Primary AMP Index (PA)

Distributes rows across AMPs by hash (like PI) but stores data in container format (like NoPI). Recommended for most CP implementations.

### Syntax

```sql
PRIMARY AMP INDEX (column_list)
  PARTITION BY COLUMN

-- Or combined with row partitioning:
PRIMARY AMP INDEX (column_list)
  PARTITION BY (
    COLUMN [ADD n],
    RANGE_N(col BETWEEN val AND val EACH interval))
```

### PA vs PI vs NoPI for Column Partitioning

| Feature | PI (CPPI) | PA | NoPI (CPNoPI) |
|---|---|---|---|
| Distribution | Hash by PI cols | Hash by PA cols | Round-robin |
| Container packing | New container per distinct PI value | Values appended to end of container | Values appended to end of container |
| Autocompression | Lower (interrupted by PI boundaries) | Better (continuous append) | Best (continuous append) |
| Local joins/aggregations | Yes | Yes | No (requires redistribution) |
| UNIQUE allowed? | Yes (if partitioning cols included) | No (use USI) | No (use USI) |
| Available since | 15.10 | 14.10 | 14.0 |

### PA Examples

```sql
-- CP with PA (recommended for most cases)
CREATE TABLE mydb.sales_cp (
    txn_no INTEGER,
    txn_date DATE,
    item_no INTEGER,
    quantity INTEGER,
    customer_id INTEGER
) PRIMARY AMP INDEX (customer_id)
  PARTITION BY COLUMN;

-- CP + RP with PA
CREATE TABLE mydb.sales_cprp (
    txn_no INTEGER,
    txn_date DATE,
    item_no INTEGER,
    quantity INTEGER,
    customer_id INTEGER
) PRIMARY AMP INDEX (customer_id)
  PARTITION BY (
    COLUMN,
    RANGE_N(txn_date BETWEEN DATE '2020-01-01'
        AND DATE '2030-12-31' EACH INTERVAL '1' DAY));
```

## Container Internals

### Delete Column Partition
- One system-managed delete column per CP table
- Stores deletion bits for COLUMN-format partitions
- Non-fastpath deletes are **logical only** — space not reclaimed
- Space reclaimed on: fastpath DELETE ALL, fastpath row-partition DELETE

### Row ID Compression
- Multiple values per container share one row ID on disk
- Other values' row IDs determined by position within container
- Non-trivial space savings for large tables

### Container Contexts (PPICacheThrP)
- Minimum: 8 contexts
- Maximum: 256 contexts
- Default PPICacheThrP = 10 (1% of FSG cache) → typically 30-80 contexts
- Each context reads/writes one column partition simultaneously
- Insufficient contexts → multiple scan passes: `CEILING(num_column_partitions / available_contexts)`

## Loading CP Tables

### Recommended: INSERT-SELECT

```sql
-- Load from staging into CP table
INSERT INTO mydb.sales_cp
SELECT * FROM mydb.staging_sales;

-- With LOCAL ORDER BY for better compression
INSERT INTO mydb.sales_cp
SELECT * FROM mydb.staging_sales
LOCAL ORDER BY (txn_date);
```

### Loading Restrictions

| Utility | Supported? | Notes |
|---|---|---|
| INSERT-SELECT | Yes | Recommended method |
| BTEQ/SQL | Yes | Row-at-a-time |
| TPT Stream | Yes | Not recommended |
| FastLoad | No | Not supported |
| MultiLoad | No | Not supported |
| TPT Load/Update | No | Not supported |
| MERGE/UPSERT | No | Not supported for CP with PA or NoPI |

### Loading Pattern

```sql
-- Step 1: Load into non-CP staging table
CREATE MULTISET TABLE mydb.staging (
    txn_no INTEGER, txn_date DATE, item_no INTEGER,
    quantity INTEGER, customer_id INTEGER
) NO PRIMARY INDEX;

-- Step 2: FastLoad/TPT into staging
-- (load utility of choice)

-- Step 3: INSERT-SELECT into CP table
INSERT INTO mydb.sales_cp
SELECT * FROM mydb.staging;

-- Step 4: Drop staging
DROP TABLE mydb.staging;
```

## ALTER TABLE for Column Partitioning

### Adding Columns

```sql
-- Add column into existing column partition
ALTER TABLE mydb.orders ADD storeid INT INTO store_name;

-- Add new single-column partition
ALTER TABLE mydb.orders ADD store_status INT;

-- Add new multicolumn partition
ALTER TABLE mydb.orders ADD (storezip INT, storemgr INT, storeregion INT);

-- Add with explicit ROW format
ALTER TABLE mydb.orders ADD ROW(store_location VARCHAR(100)) NO AUTO COMPRESS;

-- Add with explicit COLUMN format
ALTER TABLE mydb.orders ADD COLUMN(alt_ship_addr VARCHAR(500), alt_bill_addr VARCHAR(200));
```

### Dropping Columns

```sql
ALTER TABLE mydb.orders DROP storezip;
ALTER TABLE mydb.orders DROP storemgr, DROP storeregion;
```

### Changing Format/Compression

```sql
-- Change to ROW format, no autocompress
ALTER TABLE mydb.orders ADD ROW(storezip) NO AUTO COMPRESS;

-- Change to COLUMN format
ALTER TABLE mydb.orders ADD COLUMN(storezip);

-- Change to system-determined format
ALTER TABLE mydb.orders ADD SYSTEM(storezip);

-- Enable autocompress
ALTER TABLE mydb.orders ADD (storezip) AUTO COMPRESS;
```

## CP Join Index

```sql
-- CP join index (ROWID alias REQUIRED)
CREATE JOIN INDEX mydb.ji_orders AS
  SELECT a, b, d, ROWID AS rw
  FROM mydb.orders
  PRIMARY AMP (a) PARTITION BY COLUMN;
```

**Rules:** CP join index must be single-table, nonaggregate, noncompressed, no primary index, no value-ordering, cannot be unique.

## CP Table Requirements

- Must be **MULTISET** (SET not allowed)
- Cannot be global temporary, volatile, queue, or error table
- Cannot have permanent journals
- Default is NO PRIMARY INDEX regardless of PrimaryIndexDefault setting
- CHARACTER SET KANJI1 not allowed (use UNICODE)

## Good CP Candidates

- MULTISET tables >1 GB/AMP
- >50 columns with variable column access patterns
- Static/append-only data (few updates/deletes)
- Analytics workloads scanning subsets of columns
- Wide fact tables, sensor data, clickstream data

## Catalog Discovery

```sql
-- Check column partition details
HELP COLUMN mydb.orders.*;
-- Column Partition Number: 0=not CP, n=partition number
-- Column Partition Format: CS/CU/RS/RU/NA
-- Column Partition AC: AC=autocompress, NC=no autocompress

-- HELP INDEX partitioning indicators
-- A = Append order, column partitioned
-- K = Hash ordered + append, column partitioned
-- R = Row partitioned + append, column partitioned
-- S = Row partitioned + hash + append, column partitioned

-- Key DBC views
SELECT * FROM DBC.PartitioningConstraintsV WHERE DatabaseName='mydb';
SELECT ColumnPartitioningLevel FROM DBC.TableConstraints WHERE DatabaseName='mydb';
```

## DBS Control Settings for CP

| Setting | Description | Default |
|---|---|---|
| PPICacheThrP | % of FSG cache for multicontext ops | 10 (=1%) |
| CPUpdate | Controls update-in-place behavior | 3 |
| AutoCompressDefault | Default AUTO/NO AUTO COMPRESS | 1 |
| PartitioningConstraintForm | Constraint text format (1=recommended) | 0 |
