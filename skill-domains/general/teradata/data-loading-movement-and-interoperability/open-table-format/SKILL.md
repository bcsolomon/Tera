---
name: open-table-format
description: 'Query, create, and manage Apache Iceberg and Delta Lake tables in external catalogs from Teradata Vantage using Open Table Format (OTF). Use when creating DATALAKE objects, querying Iceberg or Delta Lake tables, setting up AUTHORIZATION objects for catalog/storage access, exploring OTF databases and tables with HELP DATALAKE, performing time-travel queries on Iceberg tables, integrating with AWS Glue, Apache Hive Metastore, Polaris, or Unity Catalog, configuring AWS Lake Formation permissions, or troubleshooting OTF connectivity. Covers both Iceberg and Delta Lake formats across S3, Azure ADLS, and GCS storage.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Open Table Format (OTF)

## When to Use

- Creating a DATALAKE object to connect Teradata to an external table catalog
- Querying Apache Iceberg or Delta Lake tables from Teradata SQL
- Setting up AUTHORIZATION objects for catalog (AWS Glue, Hive, Polaris, Unity Catalog) and storage access
- Exploring OTF-managed databases and tables (`HELP DATALAKE`, `HELP DATABASE`, `HELP TABLE`)
- Managing DATALAKE lifecycle (`REPLACE`, `ALTER`, `COMMENT ON`, `SHOW`, `DROP`)
- Performing Iceberg time-travel or snapshot queries
- Creating new Iceberg or Delta Lake tables from Teradata
- Collecting OTF table statistics (`COLLECT STATS`, `SHOW STATS`, `HELP STATS`, `DROP STATS`)
- Creating and maintaining Teradata-managed OTF tables (including retention policy)
- Configuring AWS Lake Formation integration for fine-grained OTF access control
- Configuring OAuth-based integrations for Polaris and Unity catalog access
- Integrating Iceberg REST catalogs such as Polaris, Unity, and BigLake metastore
- Diagnosing OTF connectivity or permission errors

## Core Concepts

| Term | Definition |
|------|-----------|
| **Datalake object** | Teradata DDL object that maps a catalog + storage location to a queryable namespace; created with `REPLACE DATALAKE` |
| **Authorization object** | Credential holder used by DATALAKE for catalog and storage access; created with `REPLACE AUTHORIZATION` |
| **Catalog** | Metadata service that stores table schemas, partitions, and snapshots (AWS Glue, Hive Metastore, Polaris, Unity Catalog) |
| **Table format** | Open standard for ACID table semantics on object storage — `iceberg` or `delta` |
| **Three-part name** | OTF tables are addressed as `datalake_name.database_name.table_name` |
| **INVOKER vs DEFINER** | `INVOKER` uses the querying user's context; `DEFINER` uses the authorization owner's credentials |

### Supported Catalog Types

| `catalog_type` Value | Catalog System | Notes |
|---------------------|----------------|-------|
| `glue` | AWS Glue Data Catalog | Most common for Iceberg on AWS |
| `hive` | Apache Hive Metastore | Requires `catalog_server` (host:port); **Iceberg only** |
| `polaris` | Apache Polaris (Snowflake open-source) | Requires `catalog_server` and `catalog_warehouse` |
| `unity` | Databricks Unity Catalog | Requires `catalog_server` and `catalog_warehouse` |

### Supported Table Formats

| `TABLE FORMAT` | Use Case |
|---------------|----------|
| `iceberg` | Apache Iceberg — time travel, schema evolution, partition evolution |
| `delta` | Delta Lake — ACID transactions, CDC, Z-order clustering |

## Procedure: Create Authorization Object

An AUTHORIZATION object holds the credentials used to connect to a catalog or object storage. Create separate authorizations for catalog and storage if they use different credentials.

```sql
-- Access key / secret key (AWS S3 or Glue)
REPLACE AUTHORIZATION my_db.my_catalog_auth
AS INVOKER TRUSTED
USER 'AWS_ACCESS_KEY_ID'
PASSWORD 'AWS_SECRET_ACCESS_KEY';

-- IAM Role (AssumeRole) — leave USER empty, pass RoleArn in PASSWORD as JSON
REPLACE AUTHORIZATION my_db.my_role_auth
AS INVOKER TRUSTED
USER ''
PASSWORD '{"RoleArn":"arn:aws:iam::123456789012:role/my-otf-role","ExternalId":"optional-external-id"}';

-- Azure Data Lake Storage
REPLACE AUTHORIZATION my_db.my_azure_auth
AS INVOKER TRUSTED
USER 'storage_account_name'
PASSWORD 'storage_account_access_key_or_sas_token';
```

See [Authorization and Datalake Setup](./references/authorization-and-datalake-setup.md) for all parameters, DROP/SHOW syntax, and security model details.

## Procedure: Create a Datalake Object

A DATALAKE object combines an authorization, catalog connection, and table format into a queryable namespace.

```sql
-- Iceberg with AWS Glue catalog
REPLACE DATALAKE my_datalake
EXTERNAL SECURITY INVOKER TRUSTED CATALOG my_db.my_catalog_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE my_db.my_catalog_auth
USING
  catalog_type    ('glue')
  storage_region  ('us-east-1')
  storage_location('s3://my-bucket/warehouse/')
TABLE FORMAT iceberg;

-- Delta Lake with Hive Metastore
REPLACE DATALAKE my_delta_lake
EXTERNAL SECURITY INVOKER TRUSTED CATALOG my_db.my_hive_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE my_db.my_storage_auth
USING
  catalog_type    ('hive')
  catalog_server  ('hive-metastore.example.com:9083')
  storage_region  ('us-west-2')
  storage_location('s3://my-delta-bucket/tables/')
TABLE FORMAT delta;
```

See [Authorization and Datalake Setup](./references/authorization-and-datalake-setup.md) for all USING parameters.

## Procedure: Explore OTF Databases and Tables

After creating a DATALAKE, use HELP commands to navigate the catalog.

```sql
-- List all databases registered in the datalake
HELP DATALAKE my_datalake;

-- List all tables in a specific database
HELP DATABASE my_datalake.sales_db;

-- List columns of a specific table
HELP TABLE my_datalake.sales_db.orders;

-- Query datalake metadata view
SELECT DatalakeName, CatalogType, StorageLocation
FROM DBC.DatalakeInfoV;
```

See [Authorization and Datalake Setup](./references/authorization-and-datalake-setup.md) for lifecycle statements and metadata views.

## Procedure: Query OTF Tables

Use standard Teradata SQL with three-part names.

```sql
-- Basic query
SELECT * FROM my_datalake.sales_db.orders;

-- Filtered query
SELECT order_id, customer_id, total
FROM my_datalake.sales_db.orders
WHERE order_date >= DATE '2024-01-01';

-- Aggregation and join with local Teradata table
SELECT c.name, SUM(o.total) AS revenue
FROM my_datalake.sales_db.orders o
JOIN my_local_db.customers c ON o.customer_id = c.id
GROUP BY c.name
ORDER BY revenue DESC;

-- INSERT INTO Teradata table from OTF table (data movement)
INSERT INTO my_local_db.orders_snapshot
SELECT * FROM my_datalake.sales_db.orders
WHERE order_date = CURRENT_DATE - 1;
```

See [Iceberg and Delta Lake Operations](./references/iceberg-and-delta-operations.md) for time-travel, metadata queries, CREATE TABLE, and DML.

## Procedure: Iceberg Time Travel

Iceberg tables support querying historical snapshots. This is one of the key advantages of the Iceberg format.

```sql
-- Query as of a specific timestamp
SELECT * FROM my_datalake.sales_db.orders
FOR TIMESTAMP AS OF TIMESTAMP '2024-06-01 00:00:00';

-- Query as of a specific snapshot ID
SELECT * FROM my_datalake.sales_db.orders
FOR VERSION AS OF 8912345678901234567;

-- View available snapshots
SELECT * FROM my_datalake.sales_db."orders$snapshots";
```

See [Iceberg and Delta Lake Operations](./references/iceberg-and-delta-operations.md) for history tables, manifest queries, and Delta Lake CDC reads.

## Procedure: Manage DATALAKE Lifecycle

Use lifecycle statements when credentials rotate, comments need updates, or integrations are retired.

```sql
-- Replace definition in place
REPLACE DATALAKE my_datalake
EXTERNAL SECURITY INVOKER TRUSTED CATALOG my_db.my_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE my_db.my_auth
USING
  catalog_type('glue')
  storage_region('us-east-1')
  storage_location('s3://my-bucket/warehouse/')
TABLE FORMAT iceberg;

-- Alter authorization bindings
ALTER DATALAKE my_datalake
MODIFY EXTERNAL SECURITY INVOKER TRUSTED CATALOG my_db.new_catalog_auth,
MODIFY EXTERNAL SECURITY INVOKER TRUSTED STORAGE my_db.new_storage_auth;

-- Add descriptive comment for operations visibility
COMMENT ON DATALAKE my_datalake IS 'Finance Iceberg production catalog';

-- Show generated DDL for verification
SHOW DATALAKE my_datalake;

-- Drop when no longer needed
DROP DATALAKE my_datalake;
```

## Procedure: Collect OTF Statistics

Statistics are supported for OTF tables and improve optimizer decisions for larger analytical workloads.

```sql
-- Collect stats on commonly-filtered columns
COLLECT STATS COLUMN(order_date) ON my_datalake.sales_db.orders;
COLLECT STATS COLUMN(customer_id) ON my_datalake.sales_db.orders;

-- Inspect or remove stats
SHOW STATS ON my_datalake.sales_db.orders;
HELP STATS my_datalake.sales_db.orders;
DROP STATS COLUMN(customer_id) ON my_datalake.sales_db.orders;
```

See [Iceberg and Delta Lake Operations](./references/iceberg-and-delta-operations.md) for performance and statistics guidance.

## Quick Reference — Key Facts

These tables answer the most common knowledge questions. Consult reference files for deeper details.

### Supported File Formats

| Table Format | File Formats | Notes |
|-------------|-------------|-------|
| Iceberg | Parquet (read/write), AVRO (read/write), ORC (read-only) | Parquet is default and recommended |
| Delta Lake | Parquet only | All Delta data stored as Parquet |

### Supported Object Storage

| Storage | Iceberg | Delta Lake |
|---------|---------|------------|
| AWS S3 | Yes | Yes |
| Azure ADLS Gen2 | Yes | Yes |
| Azure Blob Storage | Yes | No |
| Google Cloud Storage | Yes | Yes |

### Compression Formats (Iceberg Parquet)

| Format | Support | Notes |
|--------|---------|-------|
| ZSTD | Default | Best compression ratio without significant CPU overhead |
| SNAPPY | Supported | Fast compression/decompression, moderate ratio |
| GZIP | Supported | Highest ratio but slower |

### Teradata to Iceberg Type Mapping

| Teradata Type | Iceberg Type | Read/Write |
|--------------|-------------|------------|
| INTEGER | int | Read/Write |
| BIGINT | long | Read/Write |
| SMALLINT | int | Read/Write |
| DECIMAL(p,s) | decimal(p,s) | Read/Write |
| VARCHAR(n) | string | Read/Write |
| CHAR(n) | string | Read/Write |
| DATE | date | Read/Write |
| TIMESTAMP | timestamp | Read/Write |
| BLOB / BYTE / VARBYTE | binary | Read/Write |

### Teradata to Delta Type Mapping

| Teradata Type | Delta Type | Read/Write |
|--------------|-----------|------------|
| INTEGER | integer | Read/Write |
| BIGINT | long | Read/Write |
| DECIMAL(p,s) | decimal(p,s) | Read/Write |
| VARCHAR(n) | string | Read/Write — length not enforced by Delta |
| DATE | date | Read/Write |
| TIMESTAMP | timestamp | Read/Write — partition column read caveats |

### Delta Lake Key Limitations

1. **VARCHAR/CHAR/VARBYTE/BYTE/BLOB** columns do not use user-defined length — Delta stores as variable-length.
2. **Decimal partition columns** with trailing zeros may fail validation (e.g., `10.50` stored as `10.5`).
3. **TIMESTAMP partition columns** may fail on read in some Delta engine paths.
4. **Partition column rename** causes read exceptions — must drop and recreate the table.

### Authorization Models by Cloud Provider

| Cloud | Catalog-Level Auth | Storage-Level Auth |
|-------|-------------------|-------------------|
| AWS | IAM User Credentials, AWS Assume Role, AWS Lake Formation (Glue only) | IAM User Credentials, AWS Assume Role |
| Azure | Azure AD Service Principal, Databricks Unity Service Principal | Storage Account Key, SAS Token |
| GCP | OAuth Service Account, Databricks Unity Service Principal | OAuth Service Account |

### Network Security

All data transmitted between the Vantage platform and external object storage or catalog services uses **TLS 1.2 encryption** in transit. No plaintext connections are supported. This applies to all catalog types (Glue, Hive, Polaris, Unity) and all storage providers (S3, ADLS, GCS).

### OTF Statistics Architecture

- Stats are stored in **DBC.StatsTbl** (same as native Teradata stats).
- Use **DBC.OtfStatsV** to view OTF-specific statistics.
- OTF standard metadata provides **scalar stats only**: null count, distinct values, min/max. **No histogram support**.
- **Expression-based statistics are not supported** for OTF columns.
- Supported SQL: `COLLECT STATS`, `DROP STATS`, `SHOW STATS`, `HELP STATS`.

### Database Views over OTF Tables

- `CREATE VIEW`, `REPLACE VIEW`, `DROP VIEW`, `HELP VIEW`, and `SELECT` from views are all supported over OTF tables.
- Views can join OTF tables with BFS (block file system) and OFS (object file system) tables.
- **Key limitation**: Views are NOT automatically refreshed when the underlying OTF table schema changes. Users must manually run `REPLACE VIEW` after any OTF schema evolution.

### Managed OTF Tables and Retention

- Teradata-managed OTF tables store data using open table formats (Iceberg) but with Teradata lifecycle management.
- Retention is configured via the **`RETENTIONDAYS`** clause (not `SET RETENTION POLICY INTERVAL`).
- Retention can be set at multiple levels: **profile → user → database → table** (table-level overrides all).
- View retention settings: `DBC.ProfileInfoV` (profile level), `DBC.DatabasesV` (database level).

### Performance Characteristics

- OTF is a **Java-based solution**. Performance is comparable to other Java-based OTF engines like **Apache Spark**.
- Filter on partition columns to eliminate manifest scans.
- Minimize `SELECT *` on wide tables — OTF reads are columnar.
- Prefer `DATE` literals over string casts for partition predicates.
- For repeated heavy analytics, materialize OTF data into native Teradata tables via `INSERT ... SELECT`.

### Catalog Support by Table Format

| Catalog | Iceberg | Delta Lake |
|---------|---------|------------|
| AWS Glue | Yes | Yes |
| Apache Hive Metastore | Yes | **No** |
| Apache Polaris | Yes (Iceberg-only) | No |
| Databricks Unity Catalog | Yes | Yes |
| BigLake Metastore | Yes (Iceberg-only) | No |

> **Note**: Hive Metastore is NOT supported for Delta Lake — only Glue and Unity Catalog support Delta.

## Common Errors / Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `DATALAKE does not exist` | REPLACE DATALAKE not run, wrong name, or session rollback | Run `HELP DATALAKE <name>` to verify; query `DBC.DataLakesV` to list all datalakes; check that REPLACE DATALAKE was committed (not rolled back or run in a different session) |
| `Authorization failed` | Wrong credentials or IAM role | Verify access key, or test IAM role with AWS CLI |
| `Catalog connection refused` | Wrong `catalog_server` host/port (Hive) | Confirm Hive Metastore is reachable from Teradata nodes |
| `Table not found in catalog` | Wrong database name or table not registered | Use `HELP DATALAKE` → `HELP DATABASE` to navigate |
| `Feature not available` | DBS control flags not set | Contact DBA to enable OTF-related DBS flags |
| `Permission denied on S3` | IAM policy missing `s3:GetObject` | Review IAM policy attached to role/user |
| `Schema mismatch` | Catalog schema differs from storage file | Refresh catalog metadata or update table definition in catalog |

## Prerequisites

Before using OTF, verify with your DBA that the following are configured:
- OTF feature is licensed and installed on the Teradata system
- Required DBS control flags for OTF are enabled (e.g., `OTFEnabled`)
- Teradata nodes have network access to the catalog server and object storage
- The IAM role or access key has the required catalog and storage permissions

## References


> **Access:** `skill_resource_read(action="read", skill="open-table-format", path="references/FILENAME")` — do NOT call `list`.

- [Authorization and Datalake Setup](./references/authorization-and-datalake-setup.md) — Full REPLACE/ALTER/COMMENT/SHOW/DROP DATALAKE lifecycle, metadata views, security model
- [Iceberg and Delta Lake Operations](./references/iceberg-and-delta-operations.md) — Time travel, metadata tables, statistics, managed OTF lifecycle, DML, snapshots, Delta CDC
- [Catalog Integration Guide](./references/catalog-integration.md) — Per-catalog setup (Glue, Hive, Polaris, Unity Catalog, BigLake), IAM, Lake Formation, OAuth patterns
- [Limitations and Type Mapping](./references/limitations-and-type-mapping.md) — Supported format versions, key type mappings, platform limitations, troubleshooting edge cases

## Templates

- [Iceberg Datalake Setup](./assets/templates/create-datalake-iceberg.md) — Ready-to-use template for Iceberg with AWS Glue
- [Delta Lake Datalake Setup](./assets/templates/create-datalake-delta.md) — Ready-to-use template for Delta Lake with Hive Metastore
