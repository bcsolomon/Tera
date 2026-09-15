# Foreign Tables — Complete Reference

## CREATE FOREIGN TABLE Syntax

```sql
CREATE FOREIGN TABLE [database.]table_name
[, EXTERNAL SECURITY [DEFINER | INVOKER] authorization_name]
USING (
    LOCATION = '<path>'
    [AUTHORIZATION = <auth_object>]
    [STOREDAS = '<format>']
    [HEADER = 'TRUE' | 'FALSE']
    [ROWFORMAT = '<json_spec>']
    [PATHPATTERN = '<pattern>']
    [SCHEMA = '<json_schema>']
)
[NO PRIMARY INDEX];
```

## USING Parameters

| Parameter | Required | Values | Description |
|---|---|---|---|
| `LOCATION` | Yes | Cloud path | S3/Azure/GCS path to data |
| `AUTHORIZATION` | Conditional | Auth object | Required unless using EXTERNAL SECURITY |
| `STOREDAS` | No | `'PARQUET'`, `'JSON'`, `'CSV'`, `'ORC'`, `'AVRO'` | File format (auto-detected for Parquet/ORC) |
| `HEADER` | No | `'TRUE'`, `'FALSE'` | CSV has header row |
| `ROWFORMAT` | No | JSON spec | CSV delimiters |
| `PATHPATTERN` | No | Path pattern | Extract partition columns from path |
| `SCHEMA` | No | JSON schema | Explicit column definitions |

## Schema Discovery (17.20+)

In Teradata 17.20+, foreign tables support automatic schema discovery for Parquet and ORC:

```sql
-- Auto-detect schema from Parquet metadata
CREATE FOREIGN TABLE mydb.ext_data
USING (
    LOCATION = '/s3/bucket.s3.amazonaws.com/parquet_data/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'PARQUET'
)
NO PRIMARY INDEX;
```

For JSON/CSV, define the schema explicitly:

```sql
CREATE FOREIGN TABLE mydb.ext_csv_data
USING (
    LOCATION = '/s3/bucket.s3.amazonaws.com/csv_data/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'CSV'
    HEADER = 'TRUE'
    ROWFORMAT = '{"field_delimiter":",","record_delimiter":"\\n"}'
)
NO PRIMARY INDEX;
```

## PATHPATTERN — Partition Pruning

PATHPATTERN maps directory names to virtual columns, enabling partition pruning:

```
Object store layout:
s3://bucket/sales/year=2024/month=12/data.parquet
s3://bucket/sales/year=2025/month=01/data.parquet
```

```sql
CREATE FOREIGN TABLE mydb.ext_sales
USING (
    LOCATION = '/s3/bucket.s3.amazonaws.com/sales/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'PARQUET'
    PATHPATTERN = '$year/$month/$file'
)
NO PRIMARY INDEX;

-- Query with partition pruning (only scans year=2025 directory)
SELECT * FROM mydb.ext_sales
WHERE $PATH.$year = 'year=2025';
```

### PATHPATTERN Variables

| Variable | Matches |
|---|---|
| `$dir1`, `$dir2`, ... | Named directory levels |
| `$file` | File name |

Access in queries: `$PATH.$dir1`, `$PATH.$dir2`, etc.

## Examples by Format

### Parquet

```sql
CREATE FOREIGN TABLE mydb.ext_parquet
USING (
    LOCATION = '/s3/bucket.s3.amazonaws.com/data/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'PARQUET'
)
NO PRIMARY INDEX;
```

### JSON

```sql
CREATE FOREIGN TABLE mydb.ext_json
USING (
    LOCATION = '/s3/bucket.s3.amazonaws.com/json_data/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'JSON'
)
NO PRIMARY INDEX;

-- Query JSON fields with dot notation
SELECT payload..customer_id (INTEGER),
       payload..name (VARCHAR(100))
FROM mydb.ext_json;
```

### CSV with Headers

```sql
CREATE FOREIGN TABLE mydb.ext_csv
USING (
    LOCATION = '/s3/bucket.s3.amazonaws.com/csv_data/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'CSV'
    HEADER = 'TRUE'
    ROWFORMAT = '{"field_delimiter":"|","record_delimiter":"\\n"}'
)
NO PRIMARY INDEX;
```

### ORC

```sql
CREATE FOREIGN TABLE mydb.ext_orc
USING (
    LOCATION = '/s3/bucket.s3.amazonaws.com/orc_data/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'ORC'
)
NO PRIMARY INDEX;
```

## Authorization Variants

### DEFINER Security (Default)

The authorization object owner's credentials are used:

```sql
CREATE AUTHORIZATION mydb.s3_auth
AS DEFINER TRUSTED
USER 'AKIAIOSFODNN7EXAMPLE'
PASSWORD 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY';

CREATE FOREIGN TABLE mydb.ext_data
USING (
    LOCATION = '/s3/bucket.s3.amazonaws.com/data/'
    AUTHORIZATION = mydb.s3_auth
)
NO PRIMARY INDEX;
```

### INVOKER Security

Each user provides their own credentials:

```sql
CREATE AUTHORIZATION mydb.s3_invoker_auth
AS INVOKER TRUSTED
USER ''
PASSWORD '';

-- Each user must create their own authorization with the same name
-- in their own database or have credentials set
```

### IAM Role (AssumeRole)

```sql
CREATE AUTHORIZATION mydb.s3_role_auth
AS DEFINER TRUSTED
USER ''
PASSWORD '{"RoleArn":"arn:aws:iam::123456789012:role/teradata-nos-role"}';
```

### Temporary STS Credentials

```sql
CREATE AUTHORIZATION mydb.s3_temp_auth
AS DEFINER TRUSTED
USER 'temp_access_key'
PASSWORD '{"SecretAccessKey":"temp_secret","SessionToken":"FwoGZX..."}';
```

## Managing Foreign Tables

```sql
-- View foreign table definition
SHOW TABLE mydb.ext_data;

-- Drop foreign table
DROP TABLE mydb.ext_data;

-- View all foreign tables in a database
SELECT TableName, TableKind
FROM DBC.TablesV
WHERE DatabaseName = 'mydb'
  AND TableKind = 'O';  -- 'O' = foreign table
```

## Views Over Foreign Tables

```sql
-- Create a typed view for easier querying
CREATE VIEW mydb.v_orders AS
SELECT payload..order_id (INTEGER) AS order_id,
       payload..customer (VARCHAR(100)) AS customer,
       payload..total (DECIMAL(10,2)) AS total,
       payload..order_date (DATE FORMAT 'YYYY-MM-DD') AS order_date
FROM mydb.ext_json_orders;

-- Users query the view like a regular table
SELECT customer, SUM(total)
FROM mydb.v_orders
WHERE order_date >= DATE '2025-01-01'
GROUP BY customer;
```

## Delta Lake Support

Foreign tables can read Delta Lake format:

```sql
CREATE FOREIGN TABLE mydb.ext_delta
USING (
    LOCATION = '/s3/bucket.s3.amazonaws.com/delta_table/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'DELTA'
)
NO PRIMARY INDEX;
```

Delta Lake support includes:
- Time travel (reading historical versions)
- Schema evolution
- Transaction log reading

## Limitations

- Foreign tables are read-only (no INSERT/UPDATE/DELETE)
- No statistics collection on foreign tables
- JOIN performance depends on data transfer from object store
- Large JSON/CSV files may be slower than Parquet/ORC
