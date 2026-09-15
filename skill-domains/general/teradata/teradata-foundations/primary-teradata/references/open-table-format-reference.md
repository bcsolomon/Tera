# Limitations and Type Mapping — Complete Reference

> Source: Teradata Open Table Format for Apache Iceberg and Delta Lake User Guide, Release 20.00

---

## Supported Versions and Scope

| Area | Support |
|------|---------|
| Iceberg format | Apache Iceberg v2 |
| Delta format | Delta Lake v3.0 |
| Query mode | Read and write via OTF SQL syntax |
| Security | IAM-based and Lake Formation integration |

---

## Teradata to Iceberg Type Mapping

| Teradata Type | Iceberg Type | Read/Write | Notes |
|--------------|-------------|------------|-------|
| INTEGER | int | Read/Write | Direct mapping |
| BIGINT | long | Read/Write | Direct mapping |
| SMALLINT | int | Read/Write | Widened to int |
| BYTEINT | int | Read/Write | Widened to int |
| DECIMAL(p,s) | decimal(p,s) | Read/Write | Precision and scale preserved |
| FLOAT / REAL | double | Read/Write | Standard IEEE 754 |
| VARCHAR(n) | string | Read/Write | Length semantics not enforced in Iceberg |
| CHAR(n) | string | Read/Write | Trailing spaces may be trimmed |
| CLOB | string | Read/Write | Large text |
| DATE | date | Read/Write | Direct mapping |
| TIMESTAMP | timestamp | Read/Write | Microsecond precision |
| BLOB | binary | Read/Write | Binary large object |
| BYTE(n) | binary | Read/Write | Fixed-length binary |
| VARBYTE(n) | binary | Read/Write | Variable-length binary |

### Iceberg Limitation Notes

- TIME data type is not supported in Iceberg v2; use TIMESTAMP instead.
- Some catalog/platform combinations have additional constraints; verify against your target platform release notes.
- TIME data handling may vary by catalog implementation; validate in pre-production for Unity-based deployments.

---

## Teradata to Delta Type Mapping

| Teradata Type | Delta Type | Read/Write | Notes |
|--------------|-----------|------------|-------|
| INTEGER | integer | Read/Write | Direct mapping |
| BIGINT | long | Read/Write | Direct mapping |
| SMALLINT | integer | Read/Write | Widened |
| DECIMAL(p,s) | decimal(p,s) | Read/Write | Precision must fit; trailing-zero partition issue |
| FLOAT / REAL | double | Read/Write | Standard IEEE 754 |
| VARCHAR(n) | string | Read/Write | **User-defined length NOT enforced by Delta** |
| CHAR(n) | string | Read/Write | **User-defined length NOT enforced by Delta** |
| VARBYTE(n) | binary | Read/Write | **User-defined length NOT enforced by Delta** |
| BYTE(n) | binary | Read/Write | **User-defined length NOT enforced by Delta** |
| BLOB | binary | Read/Write | **User-defined length NOT enforced by Delta** |
| DATE | date | Read/Write | Direct mapping |
| TIMESTAMP | timestamp | Read/Write | **Partition column read caveats apply** |

### Delta Limitation Notes

1. **VARCHAR/CHAR/VARBYTE/BYTE/BLOB columns do not use user-defined length.** Delta stores these as variable-length types without enforcing the Teradata-specified length constraint.
2. **Decimal values in partition columns with trailing zeros may fail validation.** For example, a value of `10.50` may be stored as `10.5` in Delta, causing partition predicate mismatches.
3. **Reading TIMESTAMP partition columns may fail** in some Delta engine paths. Use non-partition timestamp columns or DATE partition columns as alternatives.
4. **Renaming partition columns before reads causes read exceptions.** The preferred pattern is drop and recreate the table with the desired partition naming.
5. Expressions with string representations of complex types (array/struct) can fail in some query contexts.

---

## Known Operational Limitations

| Area | Limitation | Mitigation |
|------|------------|------------|
| Cross-cloud access | Accessing buckets in another CSP requires explicit network/security setup | Validate VNet/VPC routing, DNS, firewall, and endpoint policy before query rollout |
| Security handoff | Lake Formation and IAM must both be configured correctly for AWS governed tables | Validate `lakeformation:GetDataAccess` and table-level grants before production cutover |
| Catalog reachability | Hive/REST catalog endpoint latency and availability affect query startup | Use regional endpoints and test failover paths |
| Metadata drift | External engines may evolve schema/partitions independently | Add periodic metadata verification checks and compatibility tests |

---

## Troubleshooting Pattern for Type and Partition Errors

1. Validate table metadata using `SHOW TABLE` and format-specific metadata tables.
2. Re-run with explicit casts for DECIMAL and TIMESTAMP fields.
3. For Delta partition rename issues, use controlled table recreation:

```sql
DROP TABLE my_delta_lake.sales_db.orders NO PURGE;
CREATE TABLE my_delta_lake.sales_db.orders (...)
PARTITIONED BY (...);
```

4. Re-test read paths with simple predicates before reintroducing complex expressions.

---

## Validation Checklist Before Production

- Confirm source-to-target type compatibility for DECIMAL and TIMESTAMP columns.
- Validate partition-column reads for both current and historical data.
- Run smoke tests for both direct table reads and view-based access paths.
- Verify behavior of nested/complex field queries used by downstream tools.
- Document known engine-specific caveats in deployment runbooks.

---

## Supported File Formats

| Table Format | File Format | Read | Write | Notes |
|-------------|------------|------|-------|-------|
| Iceberg | Parquet | Yes | Yes | Default and recommended |
| Iceberg | AVRO | Yes | Yes | Alternative serialization |
| Iceberg | ORC | Yes | No | Read-only support |
| Delta Lake | Parquet | Yes | Yes | Only format supported by Delta |

---

## Compression Formats (Iceberg Parquet)

| Compression | Support | Notes |
|------------|---------|-------|
| ZSTD | Default | Best compression ratio without significant CPU overhead |
| SNAPPY | Supported | Fastest compression/decompression; moderate ratio |
| GZIP | Supported | Highest compression ratio but slower processing |

---

## Supported Object Storage

| Storage Provider | Iceberg | Delta Lake | Location Format |
|-----------------|---------|------------|----------------|
| AWS S3 | Yes | Yes | `s3://bucket/path/` |
| Azure ADLS Gen2 | Yes | Yes | `az://container@account.dfs.core.windows.net/path/` |
| Azure Blob Storage | Yes | No | Via ADLS Gen2 endpoint |
| Google Cloud Storage | Yes | Yes | `gs://bucket/path/` |

> **Note**: Azure Blob Storage is supported for Iceberg but NOT for Delta Lake.

---

## Network Security and Encryption

All data transmitted between the Vantage platform and external object storage or catalog services uses **TLS 1.2 encryption** in transit. This applies to:
- All catalog API connections (Glue HTTPS, Hive Thrift-over-TLS, Polaris REST, Unity REST)
- All storage I/O (S3 HTTPS, ADLS HTTPS, GCS HTTPS)
- No plaintext (HTTP) connections are supported for OTF operations
- Encryption at rest depends on the object storage configuration (e.g., S3 SSE, ADLS encryption)

---

## Authorization Models by Cloud Provider

| Cloud | Catalog-Level Auth | Storage-Level Auth | Notes |
|-------|-------------------|-------------------|-------|
| AWS | IAM User Credentials (access key/secret) | IAM User Credentials | Simplest setup |
| AWS | AWS Assume Role (STS) | AWS Assume Role (STS) | Production recommended |
| AWS | AWS Lake Formation (Glue only, N/A for storage) | N/A — Lake Formation vends storage credentials | Fine-grained column-level security |
| Azure | Azure AD Service Principal | Storage Account Key or SAS Token | For Databricks Unity on Azure |
| Azure | Databricks Unity Service Principal (OAuth) | Storage Account Key or SAS Token | OAuth integration |
| GCP | OAuth Service Account | OAuth Service Account | For BigLake and GCS |
| GCP | Databricks Unity Service Principal (OAuth) | OAuth Service Account | For Unity on GCP |

---

## OTF Statistics Architecture

| Aspect | Detail |
|--------|--------|
| Storage | Stats stored in **DBC.StatsTbl** (same as native Teradata statistics) |
| OTF View | **DBC.OtfStatsV** provides OTF-specific statistics visibility |
| Metadata scope | OTF standard metadata provides **scalar stats only**: null count, distinct value count, min/max |
| Histogram support | **Not supported** for OTF tables — histograms require native Teradata table stats |
| Expression stats | **Not supported** for OTF columns |
| Supported SQL | `COLLECT STATS`, `DROP STATS`, `SHOW STATS`, `HELP STATS` |

---

## Database Views over OTF Tables

| Statement | Supported |
|-----------|----------|
| `CREATE VIEW` | Yes |
| `REPLACE VIEW` | Yes |
| `DROP VIEW` | Yes |
| `HELP VIEW` | Yes |
| `SELECT` from VIEW | Yes |

- Views can join OTF tables with BFS (block file system) and OFS (object file system) tables.
- **Key limitation**: Views are NOT automatically refreshed when the underlying OTF table schema changes. Users must manually execute `REPLACE VIEW` after any OTF schema evolution to pick up new columns or type changes.

---

## Managed OTF Tables and Retention

Teradata-managed OTF tables store data using open table formats (Iceberg) but with Teradata lifecycle management.

| Aspect | Detail |
|--------|--------|
| Retention clause | `RETENTIONDAYS` (integer days, set at CREATE or ALTER) |
| Multi-level config | Profile → User → Database → Table (table-level overrides all others) |
| Profile view | `DBC.ProfileInfoV` column `RetentionDays` |
| Database view | `DBC.DatabasesV` column `RetentionDays` |

```sql
-- Set retention at table level
ALTER TABLE managed_db.orders_managed SET RETENTIONDAYS = 30;

-- Set retention at database level
ALTER DATABASE managed_db SET RETENTIONDAYS = 90;
```

---

## Performance Characteristics

- OTF is a **Java-based solution**. Performance is comparable to other Java-based OTF engines like **Apache Spark**.
- Filter on partition columns to eliminate manifest scans (major speedup).
- Minimize `SELECT *` on wide tables — OTF reads are columnar; selecting fewer columns reduces I/O.
- Prefer `DATE` literals over string casts for partition predicates.
- For repeated heavy analytics, materialize OTF data into native Teradata tables via `INSERT ... SELECT`.
- Use `COLLECT STATS` on frequently filtered columns to improve optimizer join and aggregation plans.
