# READ_NOS — Complete Reference

## Syntax

READ_NOS is a table operator used in the FROM clause:

```sql
SELECT columns
FROM (
    LOCATION = '<path>'
    AUTHORIZATION = <auth_object>
    RETURNTYPE = '<return_type>'
    [additional parameters]
) AS alias;
```

## LOCATION Path Formats

| Cloud | Format |
|---|---|
| Amazon S3 | `/s3/bucket-name.s3.amazonaws.com/path/` |
| Amazon S3 (region) | `/s3/bucket-name.s3.us-west-2.amazonaws.com/path/` |
| Azure Blob | `/az/account.blob.core.windows.net/container/path/` |
| Google Cloud | `/gs/bucket-name.storage.googleapis.com/path/` |

### Path Wildcards

```sql
-- All files in a directory
LOCATION = '/s3/bucket.s3.amazonaws.com/data/'

-- Specific file
LOCATION = '/s3/bucket.s3.amazonaws.com/data/file.parquet'

-- All Parquet files
LOCATION = '/s3/bucket.s3.amazonaws.com/data/*.parquet'
```

## RETURNTYPE Values

| Value | Returns | Use Case |
|---|---|---|
| `NOSREAD_KEYS` | File listing (location, size, timestamp) | Discover available files |
| `NOSREAD_SCHEMA` | Column names and types from file metadata | Inspect Parquet/ORC schema |
| `NOSREAD_RECORD` | Actual data rows | Query the data |

### NOSREAD_KEYS — List Files

```sql
SELECT location, object_length, object_timestamp
FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/data/'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_KEYS'
) AS keys
ORDER BY object_timestamp DESC;
```

Output columns:
- `Location` — Full path to each object
- `ObjectLength` — Size in bytes
- `ObjectTimestamp` — Last modified timestamp

### NOSREAD_SCHEMA — Discover Schema

```sql
SELECT * FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/data/sample.parquet'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_SCHEMA'
) AS schema_info;
```

Works with Parquet and ORC (schema embedded in file metadata).

### NOSREAD_RECORD — Read Data

```sql
-- JSON data (access via Payload column with dot notation)
SELECT payload..customer_id (INTEGER),
       payload..name (VARCHAR(100)),
       payload..amount (DECIMAL(10,2))
FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/orders/'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_RECORD'
) AS data;

-- Parquet data (columns projected directly)
SELECT col1, col2, col3
FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/parquet_data/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'PARQUET'
    RETURNTYPE = 'NOSREAD_RECORD'
) AS data;
```

## Additional Parameters

| Parameter | Values | Description |
|---|---|---|
| `STOREDAS` | `'PARQUET'`, `'JSON'`, `'CSV'`, `'ORC'`, `'AVRO'` | File format |
| `HEADER` | `'TRUE'`, `'FALSE'` | CSV has header row |
| `ROWFORMAT` | JSON string | Field/record delimiters for CSV |
| `SAMPLE_PERC` | `'1'` to `'100'` | Percentage of data to sample |
| `PATHPATTERN` | `'$dir1/$dir2/$file'` | Extract partition values from path |
| `MANIFESTFILE` | `'TRUE'` | Read files listed in a manifest |
| `MANIFESTONLY` | `'TRUE'` | Return manifest entries only |

### ROWFORMAT for CSV

```sql
ROWFORMAT = '{"field_delimiter":",","record_delimiter":"\\n","character_set":"UTF8"}'
```

| Key | Default | Description |
|---|---|---|
| `field_delimiter` | `,` | Column separator |
| `record_delimiter` | `\n` | Row separator |
| `character_set` | `UTF8` | Character encoding |
| `quote_character` | `"` | Field quote character |
| `escape_character` | `\\` | Escape character |

### PATHPATTERN — Extract Partition Values

```sql
-- Files at: /s3/bucket/data/year=2025/month=01/file.parquet
SELECT $PATH.$dir1 AS year_partition,
       $PATH.$dir2 AS month_partition,
       col1, col2
FROM (
    LOCATION = '/s3/bucket.s3.amazonaws.com/data/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'PARQUET'
    RETURNTYPE = 'NOSREAD_RECORD'
    PATHPATTERN = '$dir1/$dir2/$file'
) AS data;
```

## Loading Data into Teradata

### INSERT-SELECT from READ_NOS

```sql
INSERT INTO mydb.target_table
SELECT payload..id (INTEGER),
       payload..name (VARCHAR(100)),
       payload..amount (DECIMAL(10,2))
FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/source/'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_RECORD'
) AS source;
```

### CREATE TABLE AS (CTAS) from READ_NOS

```sql
CREATE MULTISET TABLE mydb.loaded_data AS (
    SELECT payload..id (INTEGER) AS id,
           payload..name (VARCHAR(100)) AS name,
           payload..amount (DECIMAL(10,2)) AS amount
    FROM (
        LOCATION = '/s3/my-bucket.s3.amazonaws.com/source/'
        AUTHORIZATION = mydb.s3_auth
        RETURNTYPE = 'NOSREAD_RECORD'
    ) AS source
) WITH DATA
PRIMARY INDEX (id);
```

## Performance Tips

- Use STOREDAS = 'PARQUET' when possible — columnar pushdown reduces I/O
- Use SAMPLE_PERC for exploration before full reads
- PATHPATTERN-based filtering avoids scanning irrelevant directories
- Parquet/ORC column pruning: SELECT only needed columns

---

## Complete Parameter Reference

| Parameter | Required | Values | Default | Description |
|---|---|---|---|---|
| `LOCATION` | Yes | Cloud path string | — | URI pointing to external object store |
| `AUTHORIZATION` | Yes | Auth object or JSON | — | Credentials for object store access |
| `RETURNTYPE` | No | `'NOSREAD_KEYS'`, `'NOSREAD_SCHEMA'`, `'NOSREAD_RECORD'` | `'NOSREAD_RECORD'` | What type of data to return |
| `STOREDAS` | No | `'PARQUET'`, `'JSON'`, `'CSV'`, `'ORC'`, `'AVRO'` | Auto-detect | Explicit file format declaration |
| `HEADER` | No | `'TRUE'`, `'FALSE'` | `'FALSE'` | Whether CSV files have a header row |
| `ROWFORMAT` | No | JSON string | See below | Field/record delimiters and character set |
| `SAMPLE_PERC` | No | `'1'` to `'100'` | — | Percentage of files to sample |
| `PATHPATTERN` | No | Pattern string | — | Extract partition values from path segments |
| `MANIFESTFILE` | No | `'TRUE'` | `'FALSE'` | Treat LOCATION as a manifest file |
| `MANIFESTONLY` | No | `'TRUE'` | `'FALSE'` | Return manifest entries without reading data |
| `FULLSCAN` | No | `'TRUE'`, `'FALSE'` | `'FALSE'` | Force full scan of all files |
| `TABLE_FORMAT` | No | `'DELTALAKE'` | — | Enable Delta Lake manifest-based reads |
| `BUFFERSIZE` | No | Integer string | `'16000000'` | Buffer size in bytes for data transfer |
| `STRIP_EXTERIOR_SPACES` | No | `'TRUE'`, `'FALSE'` | `'FALSE'` | Strip leading/trailing spaces from CSV fields |
| `STRIP_ENCLOSING_CHAR` | No | Character or `'NONE'` | `'NONE'` | Remove enclosing characters from CSV fields |

### STOREDAS — Format Detection vs. Explicit Declaration

When `STOREDAS` is omitted, NOS auto-detects the format by sampling the first 16 MB from the most recent file. Auto-detection works well for files with standard extensions (`.json`, `.csv`, `.parquet`), but explicit declaration is recommended for:

- **Performance**: skips format detection overhead
- **Accuracy**: prevents misidentification of non-standard file extensions
- **Parquet columnar pushdown**: only available when `STOREDAS = 'PARQUET'` is explicit

```sql
-- Auto-detect (slower, may misidentify)
SELECT * FROM (
    LOCATION = '/s3/bucket.s3.amazonaws.com/data/'
    AUTHORIZATION = mydb.s3_auth
) AS d;

-- Explicit (faster, enables columnar optimizations)
SELECT * FROM (
    LOCATION = '/s3/bucket.s3.amazonaws.com/data/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'PARQUET'
) AS d;
```

### FULLSCAN Behavior

By default, NOS uses file metadata and sampling to infer schema. `FULLSCAN = 'TRUE'` forces NOS to read all files to build a complete schema. Use this when:
- Files have inconsistent schemas (different columns across files)
- Auto-detected data types are too narrow for some files

## PATHPATTERN — Extracting Partition Values from Paths

PATHPATTERN maps path segments to named variables that can be used in SELECT and WHERE clauses. Variables are always UNICODE type.

### Defining Named Path Variables

```sql
-- Default pattern (auto-assigned)
PATHPATTERN = '$Var1/$Var2/$Var3/$Var4/$Var5'

-- Named pattern (recommended)
PATHPATTERN = '$data/$siteno/$year/$month/$day'
```

### Using Path Variables in Queries

```sql
-- Reference path variables with $PATH.$varname
SELECT $PATH.$year AS year_val,
       $PATH.$month AS month_val,
       col1, col2
FROM (
    LOCATION = '/s3/bucket.s3.amazonaws.com/data/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'PARQUET'
    PATHPATTERN = '$data/$siteno/$year/$month/$day'
) AS d
WHERE $PATH.$year = '2025'
  AND $PATH.$month BETWEEN '01' AND '06';
```

### Path Filtering vs. Payload Filtering

Path filtering restricts which files are read — similar to partition elimination. Payload filtering requires all files to be read and rows examined after transformation.

```sql
-- EFFICIENT: Path filtering — only matching files are read
SELECT * FROM my_foreign_table
WHERE $PATH.$siteno = '09380000';

-- INEFFICIENT: Payload filtering — all files read, then filtered
SELECT * FROM my_foreign_table
WHERE payload.site_no = '09380000';
```

**Key rule**: When the same value exists in both the path and the payload, always filter on the path variable.

### Collecting Statistics on Path Variables

```sql
COLLECT STATS COLUMN($PATH.$siteno) AS path_siteno ON my_foreign_table;
```

Statistics on path variables help the optimizer estimate cardinality for joins and aggregations involving foreign tables.

## Delta Lake Support

NOS can read Delta Lake tables via symlink-format manifest files (available from ASE 17.10.03.11+).

### Setup Steps

1. **Generate manifests** using Apache Spark:
```
GENERATE symlink_format_manifest FOR TABLE delta.'<path-to-delta-table>'
```

2. **Create foreign table** pointing to the manifest directory:
```sql
CREATE FOREIGN TABLE my_delta_table
USING (
    LOCATION = '/s3/bucket.s3.amazonaws.com/<path>/_symlink_format_manifest/'
    MANIFEST = 'TRUE'
    TABLE_FORMAT = 'DELTALAKE'
)
NO PRIMARY INDEX;
```

3. **Update manifests** after data changes — either explicitly re-run the generate command, or enable automatic updates:
```
ALTER TABLE delta.`<path>` SET
TBLPROPERTIES(delta.compatibility.symlinkFormatManifest.enabled=true)
```

### Delta Lake Consistency Guarantees

| Table Type | Consistency |
|---|---|
| Unpartitioned | Full snapshot consistency (single manifest file updated atomically) |
| Partitioned | Per-partition consistency only; cross-partition reads may see mixed versions |

### Delta Lake Limitations

- Schema evolution requires manually updating the Teradata foreign table definition
- Performance and scalability characteristics are experimental
- Concurrent manifest rewrites during queries may produce incorrect results on some storage systems

## Manifest Files

Manifest files are JSON listings that specify exactly which files to read, providing an alternative to path-prefix scanning.

```json
{
  "entries": [
    {"url": "s3://my-bucket/data/region=east/2025-01-01.parquet"},
    {"url": "s3://my-bucket/data/region=west/2025-01-01.parquet"}
  ]
}
```

```sql
SELECT * FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/manifests/jan2025.json'
    AUTHORIZATION = mydb.s3_auth
    MANIFESTFILE = 'TRUE'
    STOREDAS = 'PARQUET'
) AS d;
```

**When to use manifests**:
- Selecting files that are not easily represented by path-prefix filtering
- Ensuring a consistent set of files across repeated queries
- Very large file counts that don't change often (faster than prefix enumeration)
- READ_NOS does not support PATHPATTERN — use manifests to scope data instead

## Error Handling and Troubleshooting

### Common Errors

| Error | Cause | Solution |
|---|---|---|
| Access denied / 403 | Invalid credentials or insufficient permissions | Verify authorization object USER/PASSWORD; check IAM policies |
| No files found at location | Incorrect LOCATION path or empty prefix | Use `RETURNTYPE = 'NOSREAD_KEYS'` to verify path |
| Schema mismatch | Column types differ across files | Use `FULLSCAN = 'TRUE'` or explicit CAST in SELECT |
| Out of memory | Too many concurrent NOS queries or large files | Reduce concurrency via WLM throttles; use SAMPLE_PERC |
| Character set mismatch | UNICODE path vars compared to LATIN payload | Use `TRANSLATE(... USING latin_to_unicode)` for transitive closure |

### Debugging with NOSREAD_KEYS

Always verify file discovery before querying data:

```sql
-- Check what files NOS sees
SELECT location, object_length, object_timestamp
FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/data/'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_KEYS'
) AS d
ORDER BY location;
```

### Validating Schema Before Load

```sql
-- Inspect Parquet schema before querying
SELECT * FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/data/sample.parquet'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_SCHEMA'
) AS d;
```

### Handling Failed Inserts

If an INSERT-SELECT from READ_NOS fails mid-operation, partial data may already be loaded. Use `HASHAMP()` or row counts to verify completeness before retrying.

## Privileges

READ_NOS requires an explicit function grant:

```sql
GRANT EXECUTE FUNCTION ON TD_SYSFNLIB.READ_NOS TO <username>;
```

## Advanced Performance Tuning

### STOREDAS Impact on Query Plans

| Format | Predicate Pushdown | Column Pruning | Path Filtering |
|---|---|---|---|
| Parquet | Yes (min/max metadata in row groups) | Yes | Yes |
| ORC | Yes | Yes | Yes |
| CSV | No | Selective columns fetched (ASE 17.10+) | Yes |
| JSON | No | No (full payload read) | Yes |

### Parquet Column Context Limits

The database allocates an in-memory "column partition context" for each column being read from Parquet. The default limit is 10 concurrent contexts per request.

**Impact**: A `SELECT *` on a 100-column Parquet foreign table forces serialized column reads in batches of 10, increasing spool I/O.

**Best practice**: Always select only the columns you need from Parquet files.

```sql
-- BAD: reads all columns, hits context limit
SELECT * FROM (
    LOCATION = '/s3/bucket.s3.amazonaws.com/wide_table/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'PARQUET'
) AS d;

-- GOOD: only needed columns, minimal contexts
SELECT customer_id, order_date, amount
FROM (
    LOCATION = '/s3/bucket.s3.amazonaws.com/wide_table/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'PARQUET'
) AS d;
```

### HASH BY RANDOM for Load Balancing

When loading NOS data into persistent tables, data may land on only a few AMPs (one per source file). Use `HASH BY RANDOM` to redistribute:

```sql
INSERT INTO mydb.target_table
SELECT * FROM my_foreign_table
HASH BY RANDOM;
```

`HASH BY RANDOM` performs block-at-a-time redistribution, which is faster than row-level hashing via `HASH BY <column>`.

### Object Store Transfer Rates

- NOS uses RESTful API calls over the network to access cloud storage
- **Keep data and compute in the same cloud region** to avoid cross-region latency
- AWS network bandwidth varies by EC2 instance type (up to 25 Gbps for the largest instances)
- NOS is **not recommended for tactical workloads** with strict SLAs due to network latency variability

### GROUP BY / ORDER BY on VARCHAR Payload

JSON and CSV payload attributes default to large VARCHAR types. The database truncates these to 1 KB for GROUP BY / ORDER BY. Always CAST to narrower types:

```sql
-- Without CAST: character-based sorting, inaccurate numeric results
SELECT MAX(payload..Temp) FROM ...;

-- With CAST: correct numeric aggregation
SELECT MAX(CAST(payload..Temp AS FLOAT)) FROM ...;
```

### Workload Management Recommendations

- NOS queries typically use 32+ MB memory per AMP — classified as "Very Large" estimated memory
- Recommended maximum concurrency: **25 concurrent queries** on a 24 AMPs/node system
- For systems with tactical SLAs: limit to **4 concurrent NOS queries**
- Create a dedicated Workload Definition at medium or low priority for NOS workloads
- Use WLM throttles with "Estimated Memory" classification as a proxy for NOS request identification
