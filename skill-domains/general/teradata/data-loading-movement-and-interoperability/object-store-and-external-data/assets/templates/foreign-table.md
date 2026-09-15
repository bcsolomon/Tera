# foreign taule

```sql
-- Foreign Table Template: Parquet on S3
-- Replace: <database>, <table_name>, <bucket>, <path>, <auth_object>

CREATE FOREIGN TABLE <database>.<table_name>
USING (
    LOCATION = '/s3/<bucket>.s3.amazonaws.com/<path>/'
    AUTHORIZATION = <database>.<auth_object>
    STOREDAS = 'PARQUET'
    -- PATHPATTERN = '$dir1/$dir2/$file'
)
NO PRIMARY INDEX;
```
