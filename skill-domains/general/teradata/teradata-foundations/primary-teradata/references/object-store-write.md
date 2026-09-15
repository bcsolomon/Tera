# Native Object Store (NOS)

## WRITE_NOS

WRITE_NOS exports data from a Vantage table or subquery to external object storage.

**Required privilege:** `EXECUTE FUNCTION` on `TD_SYSFNLIB.WRITE_NOS`.

**Important:** WRITE_NOS does NOT overwrite existing data objects. If a file with the same path already exists, WRITE_NOS stops, returns an error, and does not create a manifest even if `MANIFESTFILE` was specified. Any partially written files must be removed manually before retrying.

### Syntax

```sql
SELECT [NodeId, AmpId, Sequence, ObjectName, ObjectSize, RecordCount | *]
FROM WRITE_NOS (
  ON { [database_name.]table_name | (subquery) }
     [ PARTITION BY col [,...] ORDER BY col [,...]
     | HASH BY col [,...] LOCAL ORDER BY col [,...]
     | LOCAL ORDER BY col [,...] ]
  USING
    LOCATION         ('/connector/endpoint/bucket/prefix')
    [AUTHORIZATION   ( { [DatabaseName.]AuthObjectName |
                         '{"Access_ID":"id","Access_Key":"key","Session_Token":"tok"}' } )]
    STOREDAS         ({ 'PARQUET' | 'CSV' })
    [NAMING          ({ 'DISCRETE' | 'RANGE' })]
    [HEADER          ({ 'TRUE' | 'FALSE' })]
    [ROWFORMAT       ('{"field_delimiter":"fd","record_delimiter":"\n"}')]
    [MANIFESTFILE    ('/connector/endpoint/bucket/path/manifest.json')]
    [MANIFESTONLY    ('TRUE')]
    [OVERWRITE       ({ 'TRUE' | 'FALSE' })]
    [INCLUDE_ORDERING ({ 'TRUE' | 'FALSE' })]
    [INCLUDE_HASHBY  ({ 'TRUE' | 'FALSE' })]
    [MAXOBJECTSIZE   ('n')]
    [COMPRESSION     ({ 'GZIP' | 'SNAPPY' })]
) AS alias;
```

### USING Clause Parameters

| Parameter | Description |
|---|---|
| `LOCATION` | Required. URI where files will be written. |
| `AUTHORIZATION` | Auth object name or inline JSON credentials. |
| `STOREDAS` | Required. Output format: `'PARQUET'` or `'CSV'`. |
| `NAMING` | `'DISCRETE'` — object names include exact partition values. `'RANGE'` — object names include min and max partition values. |
| `HEADER` | CSV only. `'TRUE'` writes column names as first row. |
| `ROWFORMAT` | CSV only. Field and record delimiters. |
| `MANIFESTFILE` | Full path where manifest file is written listing all output objects. |
| `MANIFESTONLY` | `'TRUE'` — write only a manifest, no data. Used for recovery from failed writes. Must be combined with `MANIFESTFILE`. |
| `OVERWRITE` | Controls whether an existing manifest file is overwritten. Applies only to the manifest, never to data objects. |
| `INCLUDE_ORDERING` | `'TRUE'` — partition column values are written into the data objects (becomes actual column in foreign table). `'FALSE'` — partition column values appear in path names only (becomes virtual column in foreign table). |
| `INCLUDE_HASHBY` | Same semantics as INCLUDE_ORDERING but for HASH BY columns. |
| `MAXOBJECTSIZE` | Maximum output file size in MB (4–16). Default: `DefaultRowGroupSize` in DBS Control. |
| `COMPRESSION` | Parquet only. `'GZIP'` or `'SNAPPY'`. Compression occurs within Parquet row groups; file extension remains `.parquet`. |

### Distribution Clauses

| Clause | Behavior |
|---|---|
| `PARTITION BY col ORDER BY col` | One file per partition per AMP. Column names in PARTITION BY must match ORDER BY. |
| `HASH BY col LOCAL ORDER BY col` | One file per AMP. Column names in HASH BY must match LOCAL ORDER BY. |
| `LOCAL ORDER BY col` | Orders data on each AMP before writing. Use instead of PARTITION BY when partition columns have few distinct values (to avoid data skew). |

Maximum 10 columns for any of the above. ORDER BY and LOCAL ORDER BY column restrictions: types limited to BYTEINT, SMALLINT, INTEGER, BIGINT, DATE, VARCHAR (≤128 chars, alphanumeric + `- _ ! * ' ( )` only).

### Return Columns

| Column | Type | Description |
|---|---|---|
| `NodeId` | INTEGER | Database engine node that wrote the object |
| `AmpId` | INTEGER | AMP that wrote the object |
| `Sequence` | BIGINT | Unique sequence to avoid name conflicts |
| `ObjectName` | VARCHAR(1024) | Full object path: `/connector/endpoint/bucket/prefix/[partition/]object_<Node>_<AMP>_<Seq>.parquet` |
| `ObjectSize` | BIGINT | Object size in bytes |
| `RecordCount` | BIGINT | Number of records in the object |

### Examples

**Write with partitioning:**
```sql
SELECT NodeId, AmpId, Sequence, ObjectName, ObjectSize, RecordCount
FROM WRITE_NOS (
  ON (SELECT * FROM mydb.river_flow)
  PARTITION BY SiteNo ORDER BY SiteNo
  USING
    AUTHORIZATION (aws_auth)
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/river-flow/')
    STOREDAS ('PARQUET')
    NAMING ('DISCRETE')
    MANIFESTFILE ('/S3/s3.amazonaws.com/my-bucket/river-flow/manifest.json')
    INCLUDE_ORDERING ('TRUE')
    MAXOBJECTSIZE ('16')
    COMPRESSION ('SNAPPY')
) AS d
ORDER BY AmpId;
```

**Generate destination path name in subquery:**
```sql
SELECT ObjectName FROM WRITE_NOS (
  ON (SELECT c1, c2, c3, c4,
             CONCAT('year=', SUBSTR(c4, 1, 4)) AS YearPath
      FROM mydb.mytable)
  PARTITION BY c1, c3, YearPath ORDER BY c1, c3, YearPath
  USING
    LOCATION ('/S3/s3.amazonaws.com/my-bucket/output/')
    AUTHORIZATION (aws_auth)
    NAMING ('DISCRETE')
    INCLUDE_ORDERING ('FALSE')
    STOREDAS ('PARQUET')
) AS d;
-- Object paths will include: /year=1999/, /year=2010/, etc.
```

**Recovery — create manifest from existing files after a failed write:**
```sql
SELECT * FROM WRITE_NOS (
  ON (
    SELECT Location, ObjectLength
    FROM READ_NOS (
      USING
        LOCATION ('/S3/s3.amazonaws.com/my-bucket/output/')
        AUTHORIZATION (aws_auth)
        RETURNTYPE ('NOSREAD_KEYS')
    ) AS d1
  )
  USING
    MANIFESTFILE ('/S3/s3.amazonaws.com/my-bucket/output/manifest.json')
    MANIFESTONLY ('TRUE')
    OVERWRITE ('TRUE')
) AS d;
```

### WRITE_NOS Type Limitations

Not all Teradata column types can be written to Parquet or CSV. Support varies by Vantage version. Unsupported types (e.g., PERIOD, some INTERVAL types) will cause errors. Check Teradata documentation for your version's type support matrix. For unsupported types, CAST to a supported type (e.g., VARCHAR) in the subquery before passing to WRITE_NOS.

---


## Best Practices

- **Reduce scan volume:** Specify a more specific `LOCATION` path, or use `PATHPATTERN` variables in the SQL statement so Vantage can prune which files it reads.

- **Encapsulate path filtering in views:** Have the DBA create a view over the foreign table that captures path filtering with appropriate CAST expressions. Expose the view to end users instead of the raw foreign table. This ensures consistent predicate push-down and type safety.

- **Cast JSON/CSV values for aggregation:** JSON attribute values and CSV fields are VARCHAR by default. Casting to narrower types (INTEGER, DECIMAL, DATE, etc.) before GROUP BY or ORDER BY improves performance significantly.

- **Collect statistics on join columns:** When joining a foreign table to a relational table or another foreign table on a payload attribute, collect statistics on that attribute to enable the optimizer to choose an efficient join strategy.

- **Cast to narrow types to reduce spool:** When NOS data is spooled (e.g., for joins or aggregations), smaller types produce smaller spool. Cast early — in the foreign table view or in the query — rather than working with wide VARCHAR columns throughout.
