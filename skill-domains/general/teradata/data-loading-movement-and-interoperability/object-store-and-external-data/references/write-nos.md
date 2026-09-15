# WRITE_NOS — Complete Reference

## Syntax

```sql
CREATE MULTISET TABLE results AS (
    SELECT *
    FROM TABLE ( WRITE_NOS (
        ON ( <source_query> )
        USING (
            LOCATION = '<target_path>'
            AUTHORIZATION = <auth_object>
            STOREDAS = '<format>'
            [additional options]
        )
    ) AS write_out
) WITH DATA;
```

The outer CTAS captures the manifest (file locations, row counts, sizes).

## Parameters

| Parameter | Required | Values | Description |
|---|---|---|---|
| `LOCATION` | Yes | Cloud path | Target directory in object store |
| `AUTHORIZATION` | Yes | Auth object | Credentials for write access |
| `STOREDAS` | Yes | `'PARQUET'`, `'JSON'`, `'CSV'` | Output file format |
| `COMPRESSION` | No | See below | Compression algorithm |
| `NAMING` | No | `'RANGE'`, `'RANDOM'`, `'DISCRETE'` | File naming strategy |
| `PARTITION BY` | No | Column list | Partition output by columns |
| `HASH BY` | No | Column list | Hash-distribute output files |
| `LOCAL ORDER BY` | No | Column list | Sort rows within each file |
| `MANIFESTFILE` | No | `'TRUE'` | Generate a manifest file |
| `MANIFESTONLY` | No | `'TRUE'` | Return manifest but skip data write |
| `MAXOBJECTLENGTH` | No | Size string | Max file size (e.g., `'512MB'`) |

## Compression Options

| Format | Supported Compression |
|---|---|
| Parquet | `SNAPPY` (default), `GZIP`, `ZSTD`, `LZO`, `NONE` |
| JSON | `GZIP`, `NONE` |
| CSV | `GZIP`, `NONE` |

## File Naming Strategies

| NAMING | Behavior |
|---|---|
| `RANGE` | Files named with data range indicators |
| `RANDOM` | UUID-based file names |
| `DISCRETE` | One file per AMP per partition |

## Examples

### Basic Parquet Export

```sql
CREATE MULTISET TABLE export_manifest AS (
    SELECT *
    FROM TABLE ( WRITE_NOS (
        ON (SELECT * FROM mydb.sales WHERE year = 2025)
        USING (
            LOCATION = '/s3/my-bucket.s3.amazonaws.com/exports/sales_2025/'
            AUTHORIZATION = mydb.s3_auth
            STOREDAS = 'PARQUET'
            COMPRESSION = 'SNAPPY'
        )
    ) AS w
) WITH DATA;
```

### Partitioned Export

```sql
CREATE MULTISET TABLE export_manifest AS (
    SELECT *
    FROM TABLE ( WRITE_NOS (
        ON (SELECT region, product, sale_date, amount FROM mydb.sales)
        USING (
            LOCATION = '/s3/my-bucket.s3.amazonaws.com/exports/partitioned/'
            AUTHORIZATION = mydb.s3_auth
            STOREDAS = 'PARQUET'
            COMPRESSION = 'SNAPPY'
            PARTITION BY (region)
            NAMING = 'DISCRETE'
            MANIFESTFILE = 'TRUE'
        )
    ) AS w
) WITH DATA;
```

Output structure:
```
exports/partitioned/
├── region=East/
│   ├── data_0001.parquet
│   └── data_0002.parquet
├── region=West/
│   └── data_0001.parquet
└── manifest.json
```

### CSV Export

```sql
CREATE MULTISET TABLE export_manifest AS (
    SELECT *
    FROM TABLE ( WRITE_NOS (
        ON (SELECT * FROM mydb.report_data)
        USING (
            LOCATION = '/s3/my-bucket.s3.amazonaws.com/csv_exports/'
            AUTHORIZATION = mydb.s3_auth
            STOREDAS = 'CSV'
            COMPRESSION = 'GZIP'
        )
    ) AS w
) WITH DATA;
```

### JSON Export

```sql
CREATE MULTISET TABLE export_manifest AS (
    SELECT *
    FROM TABLE ( WRITE_NOS (
        ON (SELECT customer_id, name, address FROM mydb.customers)
        USING (
            LOCATION = '/s3/my-bucket.s3.amazonaws.com/json_exports/'
            AUTHORIZATION = mydb.s3_auth
            STOREDAS = 'JSON'
            COMPRESSION = 'GZIP'
        )
    ) AS w
) WITH DATA;
```

## Manifest Output Columns

The CTAS result contains one row per file written:

| Column | Description |
|---|---|
| `FileName` | Full path of written file |
| `StartedAt` | Write start timestamp |
| `FinishedAt` | Write end timestamp |
| `RowCount` | Rows written to this file |
| `FileSize` | File size in bytes |

## Performance Tips

- Use `PARTITION BY` to create Hive-style partitioned output for downstream tools
- `COMPRESSION = 'SNAPPY'` offers the best write speed for Parquet
- `COMPRESSION = 'ZSTD'` offers better compression ratio
- `MAXOBJECTLENGTH` controls file size — smaller files = more parallelism for readers
- `HASH BY` distributes data across files for parallel reading

---

## Complete Parameter Reference

| Parameter | Required | Values | Default | Description |
|---|---|---|---|---|
| `LOCATION` | Yes | Cloud path string | — | Target directory in object store |
| `AUTHORIZATION` | Yes | Auth object or JSON | — | Credentials for write access |
| `STOREDAS` | Yes | `'PARQUET'`, `'JSON'`, `'CSV'` | — | Output file format |
| `COMPRESSION` | No | See compression table | `'SNAPPY'` (Parquet), `'NONE'` (others) | Compression algorithm |
| `NAMING` | No | `'RANGE'`, `'RANDOM'`, `'DISCRETE'` | `'RANGE'` | File naming strategy |
| `PARTITION BY` | No | Column list | — | Hive-style partitioned output |
| `HASH BY` | No | Column list | — | Hash-distribute rows across AMPs |
| `LOCAL ORDER BY` | No | Column list | — | Sort rows within each file |
| `INCLUDE_ORDERING` | No | `'TRUE'`, `'FALSE'` | `'FALSE'` | Include ORDER BY columns in file path names |
| `MANIFESTFILE` | No | `'TRUE'` | `'FALSE'` | Generate a manifest file listing all output files |
| `MANIFESTONLY` | No | `'TRUE'` | `'FALSE'` | Return manifest metadata but skip data write |
| `MAXOBJECTLENGTH` | No | Size string (e.g., `'512MB'`) | `'16MB'` | Maximum file size before splitting |
| `MAXOBJECTSIZE` | No | Size string | `'16MB'` | Alias for MAXOBJECTLENGTH |

## PARTITION BY — Hive-Style Partitioned Output

PARTITION BY redistributes rows across AMPs by hashing the specified columns (same method as a primary index hash), then invokes WRITE_NOS once per partition per AMP. This creates a directory structure that downstream tools (Spark, Hive, Presto, NOS foreign tables) recognize as Hive-style partitions.

### How It Works

1. Rows are redistributed across AMPs based on a hash of the PARTITION BY columns
2. On each AMP, WRITE_NOS is invoked once per distinct partition value
3. Each partition generates at least one file; large partitions generate multiple files (controlled by `MAXOBJECTLENGTH`)

### PARTITION BY Example

```sql
CREATE MULTISET TABLE export_manifest AS (
    SELECT *
    FROM TABLE ( WRITE_NOS (
        ON (SELECT region, product_category, sale_date, amount
            FROM mydb.sales
            WHERE sale_date BETWEEN DATE '2025-01-01' AND DATE '2025-12-31')
        PARTITION BY region, product_category
        LOCAL ORDER BY sale_date
        USING (
            LOCATION = '/s3/my-bucket.s3.amazonaws.com/exports/partitioned_sales/'
            AUTHORIZATION = mydb.s3_auth
            STOREDAS = 'PARQUET'
            COMPRESSION = 'SNAPPY'
            NAMING = 'DISCRETE'
            INCLUDE_ORDERING = 'TRUE'
            MANIFESTFILE = 'TRUE'
        )
    ) AS w
) WITH DATA;
```

Output directory structure:
```
exports/partitioned_sales/
├── region=East/product_category=Electronics/
│   ├── data_0001.parquet
│   └── data_0002.parquet
├── region=East/product_category=Clothing/
│   └── data_0001.parquet
├── region=West/product_category=Electronics/
│   └── data_0001.parquet
└── manifest.json
```

### PARTITION BY Guidelines

- **Avoid unique columns** as partition keys — each unique value creates at least one file, producing many single-row files
- **Avoid single-value columns** — all rows redistribute to one AMP, eliminating parallelism
- **Count partitions first** before running WRITE_NOS to estimate file count:
  ```sql
  SELECT COUNT(DISTINCT region || '|' || product_category) FROM mydb.sales;
  ```
- If PARTITION BY is specified, the partitioning columns **must also appear** in the ORDER BY list to prevent file name conflicts

## LOCAL ORDER BY — Sorting Within Files

LOCAL ORDER BY sorts rows on each AMP before writing to files. The ORDER BY columns contribute to the file name and become part of the path key.

### Allowed Data Types for ORDER BY Columns

| Type | Notes |
|---|---|
| `SMALLINT` | — |
| `INTEGER` | — |
| `BIGINT` | — |
| `DATE` | Format in file name: `YYYY-MM-DD` |
| `VARCHAR` | Max length 128; only alphanumeric and `-_!*.'()` allowed |

**Maximum**: 10 columns in the ORDER BY list.

### ORDER BY Without PARTITION BY

```sql
SELECT * FROM TABLE ( WRITE_NOS (
    ON (SELECT * FROM mydb.daily_metrics)
    LOCAL ORDER BY metric_date
    USING (
        LOCATION = '/s3/my-bucket.s3.amazonaws.com/exports/ordered/'
        AUTHORIZATION = mydb.s3_auth
        STOREDAS = 'PARQUET'
        NAMING = 'DISCRETE'
        INCLUDE_ORDERING = 'TRUE'
    )
) AS w;
```

## HASH BY — Redistribution Without Partitioning

HASH BY redistributes rows across AMPs like PARTITION BY, but invokes WRITE_NOS only once per AMP (processing all rows on that AMP into one or more files). The hash columns do **not** appear in the file path.

```sql
SELECT * FROM TABLE ( WRITE_NOS (
    ON (SELECT * FROM mydb.large_table)
    HASH BY customer_id
    LOCAL ORDER BY transaction_date
    USING (
        LOCATION = '/s3/my-bucket.s3.amazonaws.com/exports/hashed/'
        AUTHORIZATION = mydb.s3_auth
        STOREDAS = 'PARQUET'
        COMPRESSION = 'SNAPPY'
    )
) AS w;
```

**When to use HASH BY vs. PARTITION BY**:
- Use `PARTITION BY` when you need Hive-style directory partitioning for downstream consumers
- Use `HASH BY` when you want even data distribution across files without partition directories

## Overwrite Protection and Error Recovery

### No Overwrite Protection

WRITE_NOS does **not** check for existing files at the target location. If you write to the same path twice, you get duplicate files — not an overwrite of existing files.

**Best practice**: Always write to a new, empty directory, or manually clean the target directory before re-running WRITE_NOS.

### Failure Mid-Copy

If WRITE_NOS encounters an error during execution (e.g., an illegal character in a partition column value):

1. The operation **stops immediately** with an error message
2. Files already written to the object store are **not deleted**
3. Re-executing without cleanup **risks duplicate rows**

**Recovery procedure**:
1. Manually remove all files created by the failed WRITE_NOS job from the object store
2. Fix the root cause (e.g., cleanse the partition column data)
3. Re-execute the WRITE_NOS operation

### Validating Written Data

```sql
-- Compare row counts
SELECT COUNT(*) FROM mydb.source_table;
SELECT SUM(RowCount) FROM export_manifest;

-- Bitwise comparison via MINUS
SELECT * FROM mydb.source_table
MINUS
SELECT * FROM my_foreign_table_on_written_data;
```

## Cross-Object-Store Copy

WRITE_NOS can copy data from one object store to another (including across cloud providers and regions) in a single command:

```sql
SELECT * FROM TABLE ( WRITE_NOS (
    ON (
        SELECT col1, col2, col3
        FROM (
            LOCATION = '/az/source-acct.blob.core.windows.net/container/data/'
            AUTHORIZATION = mydb.azure_auth
            STOREDAS = 'CSV'
        ) AS source
    )
    USING (
        LOCATION = '/s3/target-bucket.s3.amazonaws.com/migrated_data/'
        AUTHORIZATION = mydb.s3_auth
        STOREDAS = 'PARQUET'
        COMPRESSION = 'SNAPPY'
    )
) AS w;
```

This reads CSV from Azure, transforms to Parquet, and writes to S3 — with inline CAST or filtering as needed.

## Manifest Files

When `MANIFESTFILE = 'TRUE'`, WRITE_NOS generates a JSON manifest listing all files created during the write operation. This manifest can be used by subsequent READ_NOS or foreign table queries.

```sql
-- Write with manifest generation
CREATE MULTISET TABLE manifest_result AS (
    SELECT *
    FROM TABLE ( WRITE_NOS (
        ON (SELECT * FROM mydb.report_data)
        USING (
            LOCATION = '/s3/my-bucket.s3.amazonaws.com/output/'
            AUTHORIZATION = mydb.s3_auth
            STOREDAS = 'PARQUET'
            MANIFESTFILE = 'TRUE'
        )
    ) AS w
) WITH DATA;

-- Read the data back using the manifest
SELECT * FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/output/manifest.json'
    AUTHORIZATION = mydb.s3_auth
    MANIFESTFILE = 'TRUE'
    STOREDAS = 'PARQUET'
) AS d;
```

## Privileges

WRITE_NOS requires an explicit function grant:

```sql
GRANT EXECUTE FUNCTION ON TD_SYSFNLIB.WRITE_NOS TO <username>;
```

## Advanced Performance Considerations

### Parallelism and File Count

Each AMP generates at least one file. On a system with 200 AMPs, a simple WRITE_NOS produces at least 200 files. This is beneficial for downstream parallel readers but may produce too many small files for small data sets.

**Controls**:
- `MAXOBJECTLENGTH` — increase beyond 16 MB default to produce fewer, larger files
- `PARTITION BY` — increases file count (at least one file per partition per AMP)
- `HASH BY` — redistributes rows to control which AMPs hold which data

### File Size Tuning

| Scenario | MAXOBJECTLENGTH | Rationale |
|---|---|---|
| Small dataset, many AMPs | `'64MB'` or `'128MB'` | Avoid many tiny files |
| Large dataset, frequent reads | `'16MB'` (default) | Maximize read parallelism |
| Archive / cold storage | `'256MB'` or `'512MB'` | Minimize file count for storage efficiency |

### Compression Trade-offs

| Compression | Write Speed | Read Speed | Compression Ratio | Splittable |
|---|---|---|---|---|
| `SNAPPY` | Fastest | Fast | Low | Yes (Parquet) |
| `GZIP` | Slow | Medium | High | No |
| `ZSTD` | Medium | Fast | High | Yes (Parquet) |
| `LZO` | Fast | Fast | Low | Yes |
| `NONE` | Fastest | Fastest | None | Yes |

**Recommendation**: Use `SNAPPY` for general-purpose workloads. Use `ZSTD` when storage cost is the priority and write frequency is low.

### Workload Management for WRITE_NOS

- Create a dedicated WLM workload with limited concurrency (start with 2 concurrent limit)
- Add Target classification matching `TD_SYSFNLIB.WRITE_NOS`
- WRITE_NOS does not modify source data — it creates a point-in-time copy
- Post-copy synchronization between source and target must be built into the application layer

### Cold Data Offload Pattern

A common use case for WRITE_NOS is offloading infrequently accessed data to cheaper object storage:

```sql
-- 1. Write old data to object store
SELECT * FROM TABLE ( WRITE_NOS (
    ON (SELECT * FROM mydb.fact_table WHERE txn_date < DATE '2024-07-01')
    PARTITION BY txn_year, txn_month
    LOCAL ORDER BY txn_date
    USING (
        LOCATION = '/s3/archive-bucket.s3.amazonaws.com/fact_archive/'
        AUTHORIZATION = mydb.s3_auth
        STOREDAS = 'PARQUET'
        COMPRESSION = 'ZSTD'
        NAMING = 'DISCRETE'
        INCLUDE_ORDERING = 'TRUE'
        MANIFESTFILE = 'TRUE'
    )
) AS w;

-- 2. Create foreign table over archived data
CREATE FOREIGN TABLE mydb.fact_archive
,EXTERNAL SECURITY mydb.s3_auth
USING (
    LOCATION = '/s3/archive-bucket.s3.amazonaws.com/fact_archive/'
    STOREDAS = 'PARQUET'
    PATHPATTERN = '$year/$month/$file'
)
NO PRIMARY INDEX;

-- 3. Create a UNION ALL view for transparent access
CREATE VIEW mydb.fact_all AS
    SELECT * FROM mydb.fact_table
    UNION ALL
    SELECT * FROM mydb.fact_archive;
```
