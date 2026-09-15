# Authorization and Datalake Setup — Complete Reference

> Source: Teradata Open Table Format for Apache Iceberg and Delta Lake User Guide; TD OTF Test Environment and Sample Queries (internal)

---

## REPLACE AUTHORIZATION

The AUTHORIZATION object stores credentials used to connect to a catalog or object storage from a DATALAKE definition. It is analogous to NOS `CREATE AUTHORIZATION` but uses the `REPLACE AUTHORIZATION` form.

### Syntax

```sql
REPLACE AUTHORIZATION [database.]auth_name
AS INVOKER | DEFINER  TRUSTED | UNTRUSTED
USER 'user_or_key'
PASSWORD 'password_or_secret';
```

### Parameters

| Parameter | Values | Description |
|-----------|--------|-------------|
| `INVOKER` | — | Each query runs using the session user's identity; credentials are resolved per query |
| `DEFINER` | — | Queries always run using the authorization owner's identity; credentials are fixed at definition time |
| `TRUSTED` | — | Teradata trusts the credentials without validating against an external LDAP source |
| `UNTRUSTED` | — | Credentials must be validated; used less commonly |
| `USER` | string | AWS Access Key ID, Azure storage account name, GCS service account email, or empty string for IAM role |
| `PASSWORD` | string | AWS Secret Access Key, Azure access key/SAS token, GCS service account key JSON, or IAM role ARN JSON |

### Examples

**AWS Access Key / Secret Key:**
```sql
REPLACE AUTHORIZATION my_db.glue_auth
AS INVOKER TRUSTED
USER '<YOUR_AWS_ACCESS_KEY_ID>'
PASSWORD '<YOUR_AWS_SECRET_ACCESS_KEY>';
```

**AWS IAM Role (AssumeRole) — recommended for production:**
```sql
REPLACE AUTHORIZATION my_db.iam_role_auth
AS INVOKER TRUSTED
USER ''
PASSWORD '{"RoleArn":"arn:aws:iam::123456789012:role/TDOTFAccessRole","ExternalId":"teradata-otf"}';
```

**Separate catalog and storage authorizations:**
```sql
-- Catalog auth (Glue API)
REPLACE AUTHORIZATION my_db.glue_catalog_auth
AS INVOKER TRUSTED
USER '<YOUR_AWS_ACCESS_KEY_ID>'
PASSWORD '<YOUR_AWS_SECRET_ACCESS_KEY>';

-- Storage auth (S3) — can be same or different credentials
REPLACE AUTHORIZATION my_db.s3_storage_auth
AS INVOKER TRUSTED
USER '<YOUR_AWS_ACCESS_KEY_ID>'
PASSWORD '<YOUR_AWS_SECRET_ACCESS_KEY>';
```

**Azure Data Lake Storage Gen2:**
```sql
REPLACE AUTHORIZATION my_db.adls_auth
AS INVOKER TRUSTED
USER 'mystorageaccount'
PASSWORD '<YOUR_AZURE_ACCOUNT_KEY>';
```

### Managing Authorizations

```sql
-- View authorization definition (credentials masked)
SHOW AUTHORIZATION my_db.glue_auth;

-- Drop an authorization
DROP AUTHORIZATION my_db.glue_auth;

-- List all authorizations in a database (DBC view)
SELECT AuthorizationName, DatabaseName, UserName
FROM DBC.AuthorizationsV
WHERE DatabaseName = 'my_db';
```

---

## REPLACE DATALAKE

The DATALAKE object is the primary DDL construct for OTF. It defines the catalog connection, storage location, and table format.

### Syntax

```sql
REPLACE DATALAKE datalake_name
[EXTERNAL SECURITY INVOKER | DEFINER  TRUSTED | UNTRUSTED  CATALOG [database.]catalog_auth_name] [,]
[EXTERNAL SECURITY INVOKER | DEFINER  TRUSTED | UNTRUSTED  STORAGE [database.]storage_auth_name]
USING
  catalog_type    ('glue' | 'hive' | 'polaris' | 'unity')
  [catalog_server ('host:port')]
  [catalog_warehouse ('warehouse_name')]
  [storage_region  ('aws-region')]
  storage_location('s3://bucket/path/'
               | 'az://container@account.dfs.core.windows.net/path/'
               | 'gs://bucket/path/')
TABLE FORMAT iceberg | delta;
```

### USING Clause Parameters

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `catalog_type` | Yes | Type of metadata catalog | `'glue'`, `'hive'`, `'polaris'`, `'unity'` |
| `catalog_server` | Hive/Polaris/Unity only | Hostname and port of the catalog service | `'hive-host.example.com:9083'` |
| `catalog_warehouse` | Polaris/Unity only | Catalog warehouse identifier | `'main'` |
| `storage_region` | Yes (AWS/Azure) | Cloud region of the storage bucket | `'us-east-1'` |
| `storage_location` | Yes | Root path of the data lake storage | `'s3://my-bucket/warehouse/'` |
| `TABLE FORMAT` | Yes | Open table format standard | `iceberg` or `delta` |

### Storage Location Format by Cloud

| Cloud | Format | Example |
|-------|--------|---------|
| AWS S3 | `s3://bucket-name/path/` | `'s3://my-data-lake/warehouse/'` |
| Azure ADLS Gen2 | `az://container@account.dfs.core.windows.net/path/` | `'az://mycontainer@mystorageacct.dfs.core.windows.net/lake/'` |
| Google Cloud Storage | `gs://bucket-name/path/` | `'gs://my-gcs-bucket/warehouse/'` |

### Complete Examples

**Iceberg with AWS Glue — single shared authorization:**
```sql
REPLACE AUTHORIZATION prod_db.glue_auth
AS INVOKER TRUSTED
USER '<YOUR_AWS_ACCESS_KEY_ID>'
PASSWORD '<YOUR_AWS_SECRET_ACCESS_KEY>';

REPLACE DATALAKE prod_iceberg
EXTERNAL SECURITY INVOKER TRUSTED CATALOG prod_db.glue_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE prod_db.glue_auth
USING
  catalog_type    ('glue')
  storage_region  ('us-east-1')
  storage_location('s3://my-iceberg-lake/warehouse/')
TABLE FORMAT iceberg;
```

**Delta Lake with Hive Metastore — separate catalog and storage auth:**
```sql
REPLACE AUTHORIZATION my_db.hive_auth
AS INVOKER TRUSTED
USER 'hive_user'
PASSWORD '<YOUR_HIVE_PASSWORD>';

REPLACE AUTHORIZATION my_db.s3_auth
AS INVOKER TRUSTED
USER '<YOUR_AWS_ACCESS_KEY_ID>'
PASSWORD '<YOUR_AWS_SECRET_ACCESS_KEY>';

REPLACE DATALAKE delta_lake
EXTERNAL SECURITY INVOKER TRUSTED CATALOG my_db.hive_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE my_db.s3_auth
USING
  catalog_type    ('hive')
  catalog_server  ('hive-metastore.internal.example.com:9083')
  storage_region  ('us-west-2')
  storage_location('s3://my-delta-bucket/tables/')
TABLE FORMAT delta;
```

**Iceberg with IAM Role (production-recommended):**
```sql
REPLACE AUTHORIZATION my_db.iam_role_auth
AS INVOKER TRUSTED
USER ''
PASSWORD '{"RoleArn":"arn:aws:iam::123456789012:role/TD-OTF-Role"}';

REPLACE DATALAKE prod_iceberg
EXTERNAL SECURITY INVOKER TRUSTED CATALOG my_db.iam_role_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE my_db.iam_role_auth
USING
  catalog_type    ('glue')
  storage_region  ('us-east-1')
  storage_location('s3://my-iceberg-lake/')
TABLE FORMAT iceberg;
```

### Managing Datalake Objects

```sql
-- Show datalake definition
SHOW DATALAKE prod_iceberg;

-- List all datalakes (DBC view)
SELECT DatalakeName, DatabaseName
FROM DBC.DataLakesV;

-- Preferred discovery view for detailed metadata
SELECT DatalakeName, CatalogType, StorageLocation, TableFormat
FROM DBC.DatalakeInfoV;

-- Drop a datalake
DROP DATALAKE prod_iceberg;

-- Describe using HELP — lists databases registered in the catalog
HELP DATALAKE prod_iceberg;
```

---

## ALTER DATALAKE

Use `ALTER DATALAKE` when rotating credentials or changing catalog/storage bindings without recreating object names used by existing workloads.

### Syntax Pattern

```sql
ALTER DATALAKE datalake_name
MODIFY EXTERNAL SECURITY INVOKER | DEFINER TRUSTED | UNTRUSTED CATALOG [database.]catalog_auth_name,
MODIFY EXTERNAL SECURITY INVOKER | DEFINER TRUSTED | UNTRUSTED STORAGE [database.]storage_auth_name;
```

### Example

```sql
ALTER DATALAKE prod_iceberg
MODIFY EXTERNAL SECURITY INVOKER TRUSTED CATALOG prod_db.glue_auth_v2,
MODIFY EXTERNAL SECURITY INVOKER TRUSTED STORAGE prod_db.glue_auth_v2;
```

---

## COMMENT ON DATALAKE

Use comments to annotate ownership, usage scope, or environment metadata.

```sql
COMMENT ON DATALAKE prod_iceberg IS 'Finance production Iceberg catalog';
```

To clear a comment:

```sql
COMMENT ON DATALAKE prod_iceberg IS NULL;
```

---

## SHOW DATALAKE

`SHOW DATALAKE` emits generated DDL and is useful during audits, migrations, and incident response.

```sql
SHOW DATALAKE prod_iceberg;
```

---

## DROP DATALAKE

Dropping a DATALAKE removes only the Teradata metadata object. It does not delete external data in object storage.

```sql
DROP DATALAKE prod_iceberg;
```

---

## IAM Policy Requirements

The IAM user or role used in the AUTHORIZATION object needs the following minimum permissions:

### For AWS Glue Catalog access:
```json
{
  "Effect": "Allow",
  "Action": [
    "glue:GetDatabase",
    "glue:GetDatabases",
    "glue:GetTable",
    "glue:GetTables",
    "glue:GetPartition",
    "glue:GetPartitions"
  ],
  "Resource": "*"
}
```

### For S3 Storage access (read):
```json
{
  "Effect": "Allow",
  "Action": [
    "s3:GetObject",
    "s3:ListBucket"
  ],
  "Resource": [
    "arn:aws:s3:::my-iceberg-lake",
    "arn:aws:s3:::my-iceberg-lake/*"
  ]
}
```

### For S3 Storage access (read + write):
```json
{
  "Effect": "Allow",
  "Action": [
    "s3:GetObject",
    "s3:PutObject",
    "s3:DeleteObject",
    "s3:ListBucket"
  ],
  "Resource": [
    "arn:aws:s3:::my-iceberg-lake",
    "arn:aws:s3:::my-iceberg-lake/*"
  ]
}
```

---

## DBS Control Flags

Before using OTF on a Teradata system, a DBA must enable the required system flags. Contact your system administrator to verify these are set:

| Flag | Purpose |
|------|---------|
| OTF feature license | Licensed and installed on all vprocs |
| Network connectivity | Teradata nodes must reach the catalog server and cloud storage endpoints |
| Firewall rules | HTTPS (443) to Glue/Hive endpoints; HTTPS to S3/ADLS/GCS |

These are system-level settings — they are not accessible via SQL. If you receive a `Feature not available` or `Function not supported` error, contact your DBA.
