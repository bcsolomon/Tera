# create datalake delta

```sql
-- ============================================================
-- Teradata OTF: Delta Lake + Hive Metastore Datalake Setup Template
-- ============================================================
-- Customize the placeholders below before running.
-- Run each statement individually; check for errors between steps.
--
-- REQUIRED:
--   <DB_NAME>           - Teradata database to store authorization objects
--   <CATALOG_AUTH_NAME> - Name for Hive catalog authorization (e.g., hive_catalog_auth)
--   <STORAGE_AUTH_NAME> - Name for storage authorization (e.g., s3_delta_auth)
--   <HIVE_USER>         - Hive Metastore service username
--   <HIVE_PASSWORD>     - Hive Metastore service password
--   <ACCESS_KEY_ID>     - AWS Access Key ID for S3 storage
--   <SECRET_KEY>        - AWS Secret Access Key for S3 storage
--   <DATALAKE_NAME>     - Name for the DATALAKE object (e.g., delta_lake)
--   <HIVE_HOST>         - Hive Metastore hostname (e.g., hive-metastore.corp.example.com)
--   <HIVE_PORT>         - Hive Metastore Thrift port (default: 9083)
--   <AWS_REGION>        - AWS region of the S3 bucket (e.g., us-west-2)
--   <S3_BUCKET_PATH>    - S3 location root (e.g., s3://my-delta-tables/)
-- ============================================================

-- Step 1: Create authorization for Hive Metastore catalog access
REPLACE AUTHORIZATION <DB_NAME>.<CATALOG_AUTH_NAME>
AS INVOKER TRUSTED
USER '<HIVE_USER>'
PASSWORD '<HIVE_PASSWORD>';

-- Step 2: Create authorization for S3 storage access
REPLACE AUTHORIZATION <DB_NAME>.<STORAGE_AUTH_NAME>
AS INVOKER TRUSTED
USER '<ACCESS_KEY_ID>'
PASSWORD '<SECRET_KEY>';

-- Step 3: Create the datalake object with Delta Lake format
REPLACE DATALAKE <DATALAKE_NAME>
EXTERNAL SECURITY INVOKER TRUSTED CATALOG <DB_NAME>.<CATALOG_AUTH_NAME>,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE <DB_NAME>.<STORAGE_AUTH_NAME>
USING
  catalog_type    ('hive')
  catalog_server  ('<HIVE_HOST>:<HIVE_PORT>')
  storage_region  ('<AWS_REGION>')
  storage_location('<S3_BUCKET_PATH>')
TABLE FORMAT delta;

-- Step 4: Verify the datalake and list databases
SHOW DATALAKE <DATALAKE_NAME>;
HELP DATALAKE <DATALAKE_NAME>;

-- Step 5: Inspect a specific database
HELP DATABASE <DATALAKE_NAME>.<CATALOG_DATABASE>;

-- Step 6: Inspect a specific table
HELP TABLE <DATALAKE_NAME>.<CATALOG_DATABASE>.<TABLE_NAME>;

-- Step 7: Run a sample query
SELECT TOP 5 * FROM <DATALAKE_NAME>.<CATALOG_DATABASE>.<TABLE_NAME>;

-- Step 8: Delta Lake time travel example
-- SELECT * FROM <DATALAKE_NAME>.<CATALOG_DATABASE>.<TABLE_NAME>
-- FOR TIMESTAMP AS OF TIMESTAMP '2024-01-01 00:00:00';

-- ============================================================
-- Cleanup (run to remove objects if no longer needed)
-- ============================================================
-- DROP DATALAKE <DATALAKE_NAME>;
-- DROP AUTHORIZATION <DB_NAME>.<STORAGE_AUTH_NAME>;
-- DROP AUTHORIZATION <DB_NAME>.<CATALOG_AUTH_NAME>;
```
