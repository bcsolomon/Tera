---
name: teradata-native-object-store
description: 'Read, write, and query data in external object stores (S3, Azure Blob, Google Cloud Storage) from Teradata Vantage using Native Object Store (NOS). Use when creating foreign tables, using READ_NOS or WRITE_NOS, querying Parquet/JSON/CSV/ORC/Avro files, creating authorizations for cloud storage, processing semi-structured data (JSON dot notation, JSON_TABLE, XMLEXTRACT, XMLTABLE, DATASET), or loading external data into Teradata.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Native Object Store (NOS)

## When to Use

- Querying data in S3, Azure Blob Storage, or Google Cloud Storage
- Creating foreign tables over external Parquet/JSON/CSV/ORC/Avro files
- Using READ_NOS for ad-hoc object store queries
- Using WRITE_NOS to export data to object stores
- Setting up cloud storage authorizations (CREATE AUTHORIZATION)
- Processing JSON data with dot notation, JSONPath, or JSON_TABLE
- Processing XML data with XMLEXTRACT or XMLTABLE
- Working with CSV/Avro datasets
- Loading semi-structured data into relational tables

## NOS Access Methods

| Method | Best For | Persistence |
|---|---|---|
| `READ_NOS` | Ad-hoc exploration, schema discovery | None (table operator) |
| `CREATE FOREIGN TABLE` | Repeated queries, views, joins | Permanent DDL |
| `WRITE_NOS` | Exporting data to object store | None (table operator) |

## Procedure: Setting Up Cloud Authorization

Before accessing external data, create an authorization object:

```sql
-- S3 with access key
CREATE AUTHORIZATION mydb.s3_auth
AS DEFINER TRUSTED
USER 'AWS_ACCESS_KEY_ID'
PASSWORD 'AWS_SECRET_ACCESS_KEY';

-- S3 with IAM Role (AssumeRole)
CREATE AUTHORIZATION mydb.s3_role_auth
AS DEFINER TRUSTED
USER ''
PASSWORD '{"RoleArn":"arn:aws:iam::123456789:role/my-role"}';

-- Azure Blob Storage
CREATE AUTHORIZATION mydb.azure_auth
AS DEFINER TRUSTED
USER 'storage_account_name'
PASSWORD 'storage_account_key';

-- Google Cloud Storage
CREATE AUTHORIZATION mydb.gcs_auth
AS DEFINER TRUSTED
USER ''
PASSWORD '{"ServiceAccountKey":"{...json_key...}"}';
```

## Procedure: Querying with READ_NOS

### Discover Files (List Keys)

```sql
SELECT location, object_length, object_timestamp
FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/path/'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_KEYS'
) AS keys;
```

### Discover Schema

```sql
SELECT *
FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/path/data.parquet'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_SCHEMA'
) AS schema_info;
```

### Read Data

```sql
SELECT payload..json_key1, payload..json_key2
FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/path/'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_RECORD'
) AS data;
```

### Sample Data

```sql
SELECT * FROM (
    LOCATION = '/s3/my-bucket/path/'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_RECORD'
    SAMPLE_PERC = '10'              -- Read ~10% of data
) AS sample;
```

See [READ_NOS reference](./references/read-nos.md) for all parameters and patterns.

## Procedure: Creating Foreign Tables

```sql
CREATE FOREIGN TABLE mydb.ext_sales
USING (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/sales/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'PARQUET'            -- or JSON, CSV, ORC, AVRO
    -- HEADER = 'TRUE'             -- CSV only
    -- ROWFORMAT = '{"field_delimiter":",","record_delimiter":"\n"}'  -- CSV
    -- PATHPATTERN = '$dir1/$dir2/$file'  -- Path-based partitioning
)
NO PRIMARY INDEX;
```

### Querying Foreign Tables

```sql
-- Direct query
SELECT sale_date, SUM(amount) FROM mydb.ext_sales GROUP BY sale_date;

-- Create view over foreign table
CREATE VIEW mydb.v_recent_sales AS
SELECT * FROM mydb.ext_sales WHERE sale_date >= CURRENT_DATE - 30;

-- Join with local tables
SELECT c.name, s.amount
FROM mydb.ext_sales s
JOIN mydb.customers c ON s.customer_id = c.id;
```

See [Foreign Tables reference](./references/foreign-tables.md) for all USING parameters.

## Procedure: Writing Data to Object Store

```sql
CREATE MULTISET TABLE results AS (
    SELECT *
    FROM TABLE ( WRITE_NOS (
        ON (SELECT * FROM mydb.large_table WHERE year = 2025)
        USING (
            LOCATION = '/s3/my-bucket.s3.amazonaws.com/exports/'
            AUTHORIZATION = mydb.s3_auth
            STOREDAS = 'PARQUET'
            COMPRESSION = 'SNAPPY'          -- or GZIP, ZSTD, LZO, NONE
            NAMING = 'RANGE'                -- or RANDOM, DISCRETE
            PARTITION BY (region)           -- Optional: partition output files
            MANIFESTFILE = 'TRUE'           -- Generate manifest
        )
    ) AS write_out
) WITH DATA;
```

See [WRITE_NOS reference](./references/write-nos.md) for all options.

## Procedure: Processing Semi-Structured Data

### JSON — Dot Notation

```sql
-- Access JSON fields in a JSON column or NOS payload
SELECT payload..customer_name,
       payload..order.total (FLOAT)
FROM mydb.ext_json_table;

-- Nested arrays
SELECT payload..items[0].product_name
FROM mydb.ext_json_table;
```

### JSON_TABLE

```sql
SELECT jt.*
FROM mydb.json_data,
TABLE (JSON_TABLE(json_col, '$'
    COLUMNS (
        name VARCHAR(100) PATH '$.customer_name',
        total DECIMAL(10,2) PATH '$.order.total',
        item_count INTEGER PATH '$.order.items.size()'
    )
)) AS jt;
```

### XML — XMLEXTRACT / XMLTABLE

```sql
-- Extract XML values
SELECT XMLEXTRACT(xml_col, '/root/element/text()') FROM xml_table;

-- XMLTABLE for relational projection
SELECT xt.*
FROM xml_data,
TABLE (XMLTABLE('/root/items/item' PASSING xml_col
    COLUMNS
        item_id INTEGER PATH '@id',
        name VARCHAR(100) PATH 'name',
        price DECIMAL(8,2) PATH 'price'
)) AS xt;
```

See [Semi-Structured Data reference](./references/semi-structured-data.md) for JSON_SHRED_BATCH, DATASET, CSV/Avro, and XML patterns.

## Supported File Formats

| Format | READ_NOS | Foreign Table | WRITE_NOS |
|---|---|---|---|
| Parquet | Yes | Yes | Yes |
| JSON | Yes | Yes | Yes |
| CSV | Yes | Yes | Yes |
| ORC | Yes | Yes | No |
| Avro | Yes | Yes | No |

## Common Errors and Solutions

| Error | Cause | Fix |
|---|---|---|
| `Access denied` | Bad credentials | Verify CREATE AUTHORIZATION credentials |
| `Bucket not found` | Wrong LOCATION path | Check bucket name and region in URL |
| `Schema mismatch` | Column types don't match file | Use RETURNTYPE='NOSREAD_SCHEMA' to inspect |
| `No files found` | Empty path or wrong pattern | Verify LOCATION path; check PATHPATTERN |
| `Authorization not found` | Wrong auth name | Use fully qualified `db.auth_name` |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-native-object-store", path="references/FILENAME")` — do NOT call `list`.

- [Authorization and Security](./references/authorization-and-security.md) — CREATE/REPLACE/DROP AUTHORIZATION syntax, cloud credential mapping (AWS access key/IAM role, Azure shared key/SAS, GCS), privilege model (database + object store checks), DEFINER vs INVOKER trusted modes, public access, credential troubleshooting
- [READ_NOS](./references/read-nos.md) — All parameters, return types, and query patterns
- [WRITE_NOS](./references/write-nos.md) — Export options, partitioning, compression, manifests
- [Foreign Tables](./references/foreign-tables.md) — USING parameters, PATHPATTERN, schema discovery
- [Semi-Structured Data](./references/semi-structured-data.md) — JSON, XML, CSV, Avro processing
