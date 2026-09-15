# create datalake iceuerg

```sql
-- ============================================================
-- Teradata OTF: Iceberg + AWS Glue Datalake Setup Template
-- ============================================================
-- Customize the placeholders below before running.
-- Run each statement individually; check for errors between steps.
--
-- REQUIRED:
--   <DB_NAME>         - Teradata database to store the authorization object
--   <AUTH_NAME>       - Name for the AUTHORIZATION object (e.g., glue_iceberg_auth)
--   <ACCESS_KEY_ID>   - AWS Access Key ID (or use IAM role variant below)
--   <SECRET_KEY>      - AWS Secret Access Key
--   <DATALAKE_NAME>   - Name for the DATALAKE object (e.g., prod_iceberg)
--   <AWS_REGION>      - AWS region of the Glue catalog and S3 bucket (e.g., us-east-1)
--   <S3_BUCKET_PATH>  - S3 location root (e.g., s3://my-warehouse/iceberg/)
-- ============================================================

-- Step 1: Create the authorization object
--   Stores AWS credentials used to access Glue catalog and S3.
--   Option A: Access key / secret key
REPLACE AUTHORIZATION <DB_NAME>.<AUTH_NAME>
AS INVOKER TRUSTED
USER '<ACCESS_KEY_ID>'
PASSWORD '<SECRET_KEY>';

--   Option B: IAM Role (recommended for production — comment out Option A above)
-- REPLACE AUTHORIZATION <DB_NAME>.<AUTH_NAME>
-- AS INVOKER TRUSTED
-- USER ''
-- PASSWORD '{"RoleArn":"arn:aws:iam::<ACCOUNT_ID>:role/<ROLE_NAME>","ExternalId":"<OPTIONAL_EXTERNAL_ID>"}';

-- Step 2: Verify the authorization was created
SHOW AUTHORIZATION <DB_NAME>.<AUTH_NAME>;

-- Step 3: Create the datalake object
--   Connects the Glue catalog and S3 storage using the authorization above.
REPLACE DATALAKE <DATALAKE_NAME>
EXTERNAL SECURITY INVOKER TRUSTED CATALOG <DB_NAME>.<AUTH_NAME>,
EXTERNAL SECURITY INVOKER TRUSTED STORAGE <DB_NAME>.<AUTH_NAME>
USING
  catalog_type    ('glue')
  storage_region  ('<AWS_REGION>')
  storage_location('<S3_BUCKET_PATH>')
TABLE FORMAT iceberg;

-- Step 4: Verify the datalake was created and list available databases
SHOW DATALAKE <DATALAKE_NAME>;
HELP DATALAKE <DATALAKE_NAME>;

-- Step 5: Inspect a specific database in the catalog
--   Replace <CATALOG_DATABASE> with a database name from HELP DATALAKE output
HELP DATABASE <DATALAKE_NAME>.<CATALOG_DATABASE>;

-- Step 6: Inspect a specific table
--   Replace <TABLE_NAME> with a table name from HELP DATABASE output
HELP TABLE <DATALAKE_NAME>.<CATALOG_DATABASE>.<TABLE_NAME>;

-- Step 7: Run a sample query
SELECT TOP 5 * FROM <DATALAKE_NAME>.<CATALOG_DATABASE>.<TABLE_NAME>;

-- ============================================================
-- Cleanup (run to remove objects if no longer needed)
-- ============================================================
-- DROP DATALAKE <DATALAKE_NAME>;
-- DROP AUTHORIZATION <DB_NAME>.<AUTH_NAME>;
```
