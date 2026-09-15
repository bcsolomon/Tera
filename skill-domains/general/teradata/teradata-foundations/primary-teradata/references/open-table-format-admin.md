# Catalog Integration Guide — Complete Reference

> Source: Teradata Open Table Format User Guide; AWS Lake Formation Integration Setup (internal); AWS IAM Assume Role Setup for Teradata OTF (internal)

---

## Overview

Teradata OTF supports four catalog types. Each requires different USING clause parameters in the REPLACE DATALAKE statement and may require specific IAM or network configuration.

| Catalog Type | `catalog_type` Value | Key Extra Parameter | Typical Table Format |
|-------------|---------------------|---------------------|---------------------|
| AWS Glue Data Catalog | `glue` | None (region auto-resolved) | Iceberg |
| Apache Hive Metastore | `hive` | `catalog_server` | Iceberg only |
| Apache Polaris | `polaris` | `catalog_server`, `catalog_warehouse` | Iceberg |
| Databricks Unity Catalog | `unity` | `catalog_server`, `catalog_warehouse` | Iceberg or Delta |

---

## AWS Glue Data Catalog

AWS Glue is the most common catalog for Iceberg on AWS. It is a fully managed service — no server address is needed.

### Setup

```sql
-- Step 1: Create authorization
REPLACE AUTHORIZATION my_db.glue_auth
AS INVOKER TRUSTED
USER '<your-aws-access-key-id>'
PASSWORD '<your-aws-secret-access-key>';

-- Step 2: Create datalake
REPLACE DATALAKE my_glue_iceberg
EXTERNAL SECURITY INVOKER TRUSTED CATALOG my_db.glue_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE my_db.glue_auth
USING
  catalog_type    ('glue')
  storage_region  ('us-east-1')
  storage_location('s3://my-iceberg-warehouse/')
TABLE FORMAT iceberg;
```

### IAM Policy for Glue + S3 (read-only)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "GlueCatalogRead",
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase", "glue:GetDatabases",
        "glue:GetTable", "glue:GetTables",
        "glue:GetPartition", "glue:GetPartitions"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3StorageRead",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::my-iceberg-warehouse",
        "arn:aws:s3:::my-iceberg-warehouse/*"
      ]
    }
  ]
}
```

### Multi-Region Glue Catalogs

Glue is region-scoped. If your Glue catalog and S3 bucket are in different regions than the Teradata system, the `storage_region` must match the S3 bucket region. Create a separate DATALAKE for each region.

---

## AWS IAM Role (AssumeRole)

Using IAM roles is preferred over access keys for production. The Teradata system assumes the role using STS AssumeRole.

### Role Trust Policy (attach to the IAM role)

The role must trust the IAM identity that Teradata runs as (typically an EC2 instance profile or an IAM user):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:user/teradata-otf-caller"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "teradata-otf"
        }
      }
    }
  ]
}
```

### AUTHORIZATION Using IAM Role

```sql
REPLACE AUTHORIZATION my_db.iam_role_auth
AS INVOKER TRUSTED
USER ''
PASSWORD '{"RoleArn":"arn:aws:iam::123456789012:role/TD-OTF-AccessRole","ExternalId":"teradata-otf"}';

REPLACE DATALAKE prod_iceberg
EXTERNAL SECURITY INVOKER TRUSTED CATALOG my_db.iam_role_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE my_db.iam_role_auth
USING
  catalog_type    ('glue')
  storage_region  ('us-east-1')
  storage_location('s3://my-warehouse/')
TABLE FORMAT iceberg;
```

---

## AWS Lake Formation

AWS Lake Formation adds fine-grained access control on top of Glue and S3. When Lake Formation is enabled on a database or table, IAM S3 permissions alone are not sufficient — Lake Formation must also grant `SELECT` or `DESCRIBE` on the table.

### Setup Flow

1. Create the IAM role or user for Teradata OTF access (see AssumeRole section above).
2. In the AWS Lake Formation console, register the Teradata IAM principal as a **data lake principal**.
3. Grant table-level or column-level permissions via Lake Formation:

```
Lake Formation > Permissions > Grant
  Principal: arn:aws:iam::123456789012:role/TD-OTF-AccessRole
  Database: sales_db
  Table: orders
  Permissions: SELECT, DESCRIBE
```

4. Verify the IAM role has the Lake Formation `lakeformation:GetDataAccess` permission:

```json
{
  "Effect": "Allow",
  "Action": ["lakeformation:GetDataAccess"],
  "Resource": "*"
}
```

5. Create the AUTHORIZATION and DATALAKE objects as normal — the Lake Formation enforcement is transparent to Teradata SQL.

### Lake Formation vs. S3 Bucket Policies

When Lake Formation is enabled on a database:
- Bucket policy denying access to everyone except Lake Formation is normal — do NOT add the Teradata IAM role directly to the S3 bucket policy
- Lake Formation's vended credentials handle storage access automatically
- The IAM role only needs `lakeformation:GetDataAccess` for storage — not `s3:GetObject` directly

### Column-Level Security with Lake Formation

Lake Formation can restrict which columns the Teradata role can access. Queries that reference restricted columns will return a `Permission denied` error. This is enforced server-side in Glue/LF, not in Teradata.

```sql
-- If column 'ssn' is Lake Formation-restricted, this fails
SELECT ssn FROM prod_iceberg.hr_db.employees;
-- This succeeds
SELECT employee_id, name, department FROM prod_iceberg.hr_db.employees;
```

---

## Apache Hive Metastore

Hive Metastore is common in on-premises Hadoop and CDH/HDP clusters, and in cloud deployments using EMR or Databricks.

### Setup

```sql
-- Authorization (Hive may use Kerberos or simple username/password)
REPLACE AUTHORIZATION my_db.hive_auth
AS INVOKER TRUSTED
USER 'hive_service_user'
PASSWORD 'hive_service_password';

-- Storage authorization (S3 or HDFS-compatible)
REPLACE AUTHORIZATION my_db.s3_auth
AS INVOKER TRUSTED
USER '<your-aws-access-key-id>'
PASSWORD '<your-aws-secret-access-key>';

-- Datalake with Hive catalog
REPLACE DATALAKE hive_iceberg
EXTERNAL SECURITY INVOKER TRUSTED CATALOG my_db.hive_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE my_db.s3_auth
USING
  catalog_type    ('hive')
  catalog_server  ('hive-metastore.corp.example.com:9083')
  storage_region  ('us-west-2')
  storage_location('s3://my-hive-warehouse/')
TABLE FORMAT iceberg;
```

### Connectivity Requirements

- TCP port 9083 (default Thrift) must be reachable from all Teradata nodes to the Hive Metastore server
- If Kerberos is enabled, additional Kerberos configuration on Teradata nodes is required — contact your system administrator
- **Hive Metastore supports Iceberg only** — Delta Lake is NOT supported with Hive catalog in Teradata OTF. Use Glue or Unity Catalog for Delta.

---

## Apache Polaris (open-source)

Apache Polaris is an open-source REST catalog originally developed by Snowflake, now Apache-licensed.

### Setup

```sql
REPLACE AUTHORIZATION my_db.polaris_auth
AS INVOKER TRUSTED
USER 'polaris_client_id'
PASSWORD 'polaris_client_secret';

REPLACE DATALAKE polaris_iceberg
EXTERNAL SECURITY INVOKER TRUSTED CATALOG my_db.polaris_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE my_db.polaris_auth
USING
  catalog_type    ('polaris')
  catalog_server  ('polaris.example.com:443')
  catalog_warehouse('my_warehouse')
  storage_region  ('us-east-1')
  storage_location('s3://my-polaris-warehouse/')
TABLE FORMAT iceberg;
```

### OAuth Integration Pattern (Polaris)

Some Polaris deployments require OAuth client credentials rather than static basic credentials.

```sql
REPLACE AUTHORIZATION my_db.polaris_oauth_auth
AS INVOKER TRUSTED
USER 'oauth_client_id'
PASSWORD '{"client_secret":"<oauth-client-secret>","token_endpoint":"https://polaris.example.com/oauth/token","scope":"catalog.read catalog.write"}';
```

---

## Databricks Unity Catalog

Unity Catalog uses an HTTP REST interface. The `catalog_server` must point to the Databricks workspace URL.

### Setup

```sql
REPLACE AUTHORIZATION my_db.unity_auth
AS INVOKER TRUSTED
USER 'token'
PASSWORD '<databricks-personal-access-token>';

REPLACE DATALAKE unity_iceberg
EXTERNAL SECURITY INVOKER TRUSTED CATALOG my_db.unity_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE my_db.unity_auth
USING
  catalog_type    ('unity')
  catalog_server  ('adb-1234567890123456.7.azuredatabricks.net')
  catalog_warehouse('main')
  storage_region  ('eastus')
  storage_location('az://mycontainer@mystorageacct.dfs.core.windows.net/warehouse/')
TABLE FORMAT delta;
```

### Unity Catalog Permissions

Grant Teradata the `USE CATALOG`, `USE SCHEMA`, and `SELECT` privileges in Unity Catalog:

```sql
-- In Databricks SQL
GRANT USE CATALOG ON CATALOG main TO `teradata-service-principal`;
GRANT USE SCHEMA ON SCHEMA main.sales_db TO `teradata-service-principal`;
GRANT SELECT ON TABLE main.sales_db.orders TO `teradata-service-principal`;
```

### OAuth Integration Pattern (Unity)

For service-principal based OAuth flows, store token endpoint and client secret details in the authorization payload.

```sql
REPLACE AUTHORIZATION my_db.unity_oauth_auth
AS INVOKER TRUSTED
USER 'oauth_client_id'
PASSWORD '{"client_secret":"<oauth-client-secret>","token_endpoint":"https://adb-1234567890123456.7.azuredatabricks.net/oidc/v1/token","scope":"all-apis"}';
```

---

## BigLake Metastore Integration (Iceberg REST Catalog)

For Iceberg REST deployments using BigLake metastore, create a DATALAKE with REST-catalog endpoint details and cloud storage path.

```sql
REPLACE AUTHORIZATION my_db.biglake_auth
AS INVOKER TRUSTED
USER 'oauth_client_id'
PASSWORD '{"client_secret":"<oauth-client-secret>","token_endpoint":"https://oauth2.googleapis.com/token","scope":"https://www.googleapis.com/auth/cloud-platform"}';

REPLACE DATALAKE biglake_iceberg
EXTERNAL SECURITY INVOKER TRUSTED CATALOG my_db.biglake_auth,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE my_db.biglake_auth
USING
  catalog_type    ('polaris')
  catalog_server  ('biglake.googleapis.com:443')
  catalog_warehouse('projects/<project-id>/locations/<region>/catalogs/<catalog-name>')
  storage_location('gs://my-biglake-warehouse/')
TABLE FORMAT iceberg;
```

---

## Catalog Comparison Quick Reference

| | AWS Glue | Hive Metastore | Apache Polaris | Unity Catalog | BigLake Metastore |
|--|---------|----------------|----------------|---------------|-------------------|
| Managed service | Yes (AWS) | No | Self-hosted or cloud | Yes (Databricks) | Yes (GCP) |
| Network req. | HTTPS to Glue API | TCP 9083 | HTTPS to REST API | HTTPS to Databricks | HTTPS to REST API |
| Auth type | Access key / IAM role | Username/password or Kerberos | Client ID/secret or OAuth | PAT token or OAuth SPN | OAuth service principal |
| Iceberg support | Yes | Yes | Yes | Yes | Yes |
| Delta support | Yes | **No** | No | Yes | No |
| Fine-grained access | Via Lake Formation | Via Ranger / Sentry | Via Polaris roles | Via Unity Catalog | Via IAM + BigLake policies |
| Multi-region | One per region | One per cluster | Yes | Yes | Yes |
