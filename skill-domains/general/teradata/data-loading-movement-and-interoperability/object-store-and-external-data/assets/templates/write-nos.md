# write nos

```sql
-- WRITE_NOS Template: Export to S3 as Parquet
-- Replace: <database>, <source_query>, <bucket>, <path>, <auth_object>

CREATE MULTISET TABLE <database>.export_manifest AS (
    SELECT *
    FROM TABLE ( WRITE_NOS (
        ON ( <source_query> )
        USING (
            LOCATION = '/s3/<bucket>.s3.amazonaws.com/<path>/'
            AUTHORIZATION = <database>.<auth_object>
            STOREDAS = 'PARQUET'
            COMPRESSION = 'SNAPPY'
            -- PARTITION BY (partition_column)
            -- NAMING = 'RANGE'
            MANIFESTFILE = 'TRUE'
        )
    ) AS w
) WITH DATA;
```
