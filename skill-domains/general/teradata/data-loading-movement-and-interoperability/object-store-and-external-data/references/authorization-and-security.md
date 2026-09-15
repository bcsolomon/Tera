# Authorization and Security — Complete Reference

> Source: TDN0009800 (Native Object Store Orange Book, v1.6–v1.8)

## Overview

Every NOS access requires two security checks:

1. **Database privilege check** — Does the user have privileges to access the foreign table or run the table operator?
2. **Object store credential check** — Does the foreign table or operator have valid credentials to access the external object store?

If either check fails, access is denied. Database privileges alone do not grant access to the underlying object store, and object store credentials alone do not bypass Teradata access controls.

---

## Cloud Credential Nomenclature

Authorization objects use `USER` and `PASSWORD` fields whose meaning varies by cloud provider:

| System / Scheme | USER | PASSWORD |
|---|---|---|
| AWS (access key) | Access Key ID | Secret Access Key |
| AWS (IAM AssumeRole) | `''` (empty) | `'{"RoleArn":"arn:aws:iam::ACCOUNT:role/ROLE"}'` |
| Azure / Shared Key | Storage Account Name | Storage Account Key |
| Azure SAS | Storage Account Name | Account SAS Token |
| Google Cloud (S3 interop) | Access Key ID | Access Key Secret |
| Google Cloud (native) | Client Email | Private Key |
| On-premises object stores | Access Key ID | Access Key Secret |
| Public access | `''` (empty) | `''` (empty) |

---

## CREATE AUTHORIZATION Syntax

```sql
CREATE AUTHORIZATION [database.]auth_name
[AS {DEFINER | INVOKER} TRUSTED]
USER '<user_value>'
PASSWORD '<password_value>';
```

### REPLACE AUTHORIZATION

```sql
REPLACE AUTHORIZATION [database.]auth_name
[AS {DEFINER | INVOKER} TRUSTED]
USER '<new_user_value>'
PASSWORD '<new_password_value>';
```

### DROP AUTHORIZATION

```sql
DROP AUTHORIZATION [database.]auth_name;
```

---

## Authorization Object Scoping

### System-Wide Authorization (17.10+)

Omit the `AS DEFINER TRUSTED` / `AS INVOKER TRUSTED` clause. The authorization object can be referenced by foreign tables in any database. This is the recommended approach when multiple databases need the same credentials.

```sql
CREATE AUTHORIZATION mydb.s3_auth
USER 'AKIAIOSFODNN7EXAMPLE'
PASSWORD 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY';
```

### DEFINER Authorization

Only foreign tables **in the same database** as the authorization object can use it. Standard access rights on the tables govern user access. The authorization object must be created in the same database as the foreign table that references it.

```sql
CREATE AUTHORIZATION mydb.s3_auth_def
AS DEFINER TRUSTED
USER 'AKIAIOSFODNN7EXAMPLE'
PASSWORD 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY';
```

### INVOKER Authorization

Only the **user who created** the authorization object can use it.

```sql
CREATE AUTHORIZATION mydb.s3_auth_inv
AS INVOKER TRUSTED
USER 'AKIAIOSFODNN7EXAMPLE'
PASSWORD 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY';
```

### Public Access Authorization

For publicly accessible object stores, pass empty strings for both `USER` and `PASSWORD`:

```sql
CREATE AUTHORIZATION mydb.public_auth
USER ''
PASSWORD '';
```

---

## AWS Security Configuration

### Option 1 — IAM Roles and Policies (Instance-Level)

Use AWS IAM roles attached to the Teradata EC2 instance to grant access without explicit credentials. This approach requires AWS Management Console configuration.

**Cross-account setup** (Vantage-as-a-Service): Teradata provides an IAM role name associated with your EC2 instance. You add an S3 bucket policy granting that role `s3:GetObject`, `s3:ListBucket`, `s3:GetBucketLocation`, and `s3:PutObject` permissions on your bucket resources.

Once configured, foreign tables on the EC2 instance can access the bucket **without additional credentials**. Any database user with foreign table privileges can read the data.

> **Note:** NOS only supports SSE-KMS with customer-managed keys in cross-account configurations. For AWS Managed Keys, use Option 2 instead.

### Option 2 — IAM Access Key + Authorization Object

Generate an IAM access key ID and secret key for the S3 bucket, then store them in a Teradata authorization object. This provides **granular per-table access control** and is more secure than Option 1.

```sql
CREATE AUTHORIZATION mydb.s3_key_auth
AS DEFINER TRUSTED
USER 'AKIAIOSFODNN7EXAMPLE'
PASSWORD 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY';
```

### Option 3 — IAM AssumeRole

Pass the IAM role ARN as a JSON payload in the PASSWORD field. The engine assumes the role at query time to obtain temporary credentials.

```sql
CREATE AUTHORIZATION mydb.s3_role_auth
AS DEFINER TRUSTED
USER ''
PASSWORD '{"RoleArn":"arn:aws:iam::123456789012:role/nos-access-role"}';
```

---

## Azure Storage Security Configuration

### Option 1 — Storage Account Access Key

Generate an access key from the Azure Portal. The storage account name and key are stored in the authorization object.

```sql
CREATE AUTHORIZATION mydb.azure_key_auth
AS DEFINER TRUSTED
USER 'mystorageaccount'
PASSWORD 'base64-encoded-storage-account-key';
```

> **Note:** Access keys grant access to **all containers** in the storage account. Users with CREATE TABLE privileges could potentially access other containers by creating additional foreign tables.

### Option 2 — Shared Access Signature (SAS) Token

SAS tokens provide more granular control including time-based access restrictions and specific permission scoping.

```sql
CREATE AUTHORIZATION mydb.azure_sas_auth
AS DEFINER TRUSTED
USER 'mystorageaccount'
PASSWORD 'sv=2020-08-04&ss=b&srt=sco&sp=rl&se=2026-12-31&sig=...';
```

---

## Google Cloud Storage Security Configuration

### HMAC Keys (S3 Interoperability)

Generate HMAC keys from the Google Cloud Console. The access ID and secret key pair are stored in the authorization object.

```sql
CREATE AUTHORIZATION mydb.gcs_hmac_auth
AS DEFINER TRUSTED
USER 'GOOGTS7C7FUP3AIRVJTE2BCD'
PASSWORD 'bGoa+V7g/yqDXvKRqq+JTFn4uQZbPiQJo4pf9RzJ';
```

### Service Account Key (Native)

Pass the service account JSON key content in the PASSWORD field.

```sql
CREATE AUTHORIZATION mydb.gcs_native_auth
AS DEFINER TRUSTED
USER ''
PASSWORD '{"ServiceAccountKey":"{...service_account_json...}"}';
```

---

## Referencing Authorization Objects

### In Foreign Tables

Authorization objects are referenced either via `EXTERNAL SECURITY` in the DDL or `AUTHORIZATION` in the USING clause:

```sql
-- EXTERNAL SECURITY syntax
CREATE FOREIGN TABLE mydb.ext_data
, EXTERNAL SECURITY DEFINER TRUSTED mydb.s3_auth
USING (
    LOCATION = '/s3/bucket.s3.amazonaws.com/data/'
    STOREDAS = 'PARQUET'
)
NO PRIMARY INDEX;

-- AUTHORIZATION in USING clause
CREATE FOREIGN TABLE mydb.ext_data
USING (
    LOCATION = '/s3/bucket.s3.amazonaws.com/data/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'PARQUET'
)
NO PRIMARY INDEX;
```

### In READ_NOS

```sql
SELECT payload.* FROM (
    LOCATION = '/s3/bucket.s3.amazonaws.com/data/'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_RECORD'
) AS d;
```

Alternatively, pass inline JSON credentials (no authorization object):

```sql
AUTHORIZATION = '{"ACCESS_ID":"YOUR-KEY","ACCESS_KEY":"YOUR-SECRET"}'
```

### In WRITE_NOS

```sql
SELECT * FROM WRITE_NOS (
    ON (SELECT * FROM mydb.source_table)
    USING (
        LOCATION = '/s3/bucket.s3.amazonaws.com/exports/'
        AUTHORIZATION (mydb.s3_auth)
        STOREDAS = 'PARQUET'
    )
) AS d;
```

The `AUTHORIZATION` attribute is not required if using IAM roles and policies on AWS deployments.

---

## Function Mapping for Authorization

Function mapping binds an authorization object to a table operator, so SQL statements do not need to carry credentials.

### READ_NOS Function Mapping

```sql
CREATE AUTHORIZATION mydb.auth_nos
DEFINER TRUSTED
USER 'AKIAIOSFODNN7EXAMPLE'
PASSWORD 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYzEXAMPLEKEY';

CREATE FUNCTION MAPPING mydb.read_nos_fm
FOR READ_NOS EXTERNAL SECURITY DEFINER TRUSTED mydb.auth_nos
USING
    RETURNTYPE('NOSREAD_RECORD'),
    LOCATION,
ANY IN TABLE;

-- Query using function mapping — no credentials in SQL
SELECT TOP 5 *
FROM mydb.read_nos_fm (
    USING LOCATION ('/s3/bucket.s3.amazonaws.com/data/')
) AS dt;
```

### WRITE_NOS Function Mapping

```sql
CREATE FUNCTION MAPPING mydb.write_nos_fm
FOR WRITE_NOS
USING
    STOREDAS ('PARQUET'),
    AUTHORIZATION (mydb.auth_nos),
    LOCATION, NAMING, COMPRESSION,
ANY IN TABLE;
```

Function mapping against a foreign table requires the authorization object to be **in the same database** as the foreign table.

---

## Foreign Table Privileges

Standard database privileges control who can create, modify, drop, or query foreign tables:

```sql
GRANT CREATE TABLE ON mydb TO user1;
GRANT SELECT ON mydb.ext_sales TO analyst_role;
```

> **Important:** Granting foreign table privileges does **not** grant access to the underlying object store. The authorization object (or IAM role) must also permit access. Conversely, object store credentials do not bypass Teradata access controls.

---

## Key Rotation

When object store credentials have an expiration date, overlap old and new key validity periods, then use `REPLACE AUTHORIZATION` to update without disrupting users:

```sql
REPLACE AUTHORIZATION mydb.s3_auth
AS DEFINER TRUSTED
USER 'NEW-ACCESS-KEY-ID'
PASSWORD 'NEW-SECRET-ACCESS-KEY';
```

### Finding Authorization Objects

```sql
SELECT TVMNameI AS AuthObjName, DatabaseNameI AS DatabaseName,
    (CASE AuthorizationType
        WHEN 'S' THEN 'Definer_Trusted'
        WHEN 'T' THEN 'Invoker_Trusted'
        WHEN 'U' THEN 'System_Auth' END) AS AuthorizationType,
    t.CreatorName
FROM dbc.TVM t
JOIN dbc.DBase d ON t.DatabaseId = d.DatabaseId
WHERE OSUserName = 'YOUR-ACCESS-KEY'
ORDER BY TVMNameI;
```

---

## Network Security

All connections between the Advanced SQL Engine and external object stores use **HTTPS** — data in transit is always encrypted. NOS connectors do not support proxy configuration; a proxy must be a transparent passthrough.

---

## Best Practices

1. **Use DEFINER authorization for shared access** — Multiple users query via the foreign table without knowing credentials.
2. **Use INVOKER authorization for personal access** — Restricts usage to the creator.
3. **Prefer system-wide authorization (17.10+)** — Avoids duplicating objects across databases.
4. **Use IAM roles over access keys on AWS** — Eliminates static credentials.
5. **Use SAS tokens over account keys on Azure** — Provides time-bounded, permission-scoped access.
6. **Rotate keys proactively** — Overlap validity windows and use `REPLACE AUTHORIZATION`.
7. **Use function mapping for production** — Hides credentials and simplifies SQL for end users.
8. **Separate authorization from table management** — Different roles can own credentials vs. table definitions.
