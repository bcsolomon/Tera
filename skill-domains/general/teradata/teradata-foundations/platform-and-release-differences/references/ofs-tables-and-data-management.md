# OFS Tables and Data Management in VantageCloud Lake

## BFS vs OFS Comparison

| Aspect | Block File System (BFS) | Object File System (OFS) |
|---|---|---|
| Index structure | Separate index per AMP for all AMP's data | Separate index per table in managed object storage |
| Index hierarchy | Master Index → Cylinder Index → Data Block | Root → Leaf → Data Object |
| Index location | AMP's memory or AMP's block storage | Separate objects in table's managed storage bucket or NVME cache |
| Metadata in index | No metadata in indexing structure | Min/max metadata at each level for object elimination |
| Storage type | Cloud provider block storage (expensive, high performance) | Cloud provider object storage (lower cost, virtually unlimited) |
| Accessibility | Only from Primary Cluster | Primary Cluster and Compute Clusters |
| Update model | Updates in place | No updates in place — new objects created |
| Recommended for | System tables, data dictionary, small reference tables, tactical query tables | Vast majority of user data tables |

## OFS Internal Index Structure

Each OFS table has a dedicated internal index: Root → Leaf → Data Object.

- Min/max values for up to **64 columns** are gathered per object and stored in root and leaf objects
- Enables **object elimination** during reads based on query constraints
- Reduces I/O without needing user-defined indexes

Example: A query with `WHERE ProcDate BETWEEN '1996-06-01' AND '1996-06-07'` on a table with `ORDER BY ProcDate`:
1. ProcDate criteria applied to min/max values in root object
2. Only matching leaf objects are accessed
3. Only data objects with rows in the ProcDate range are read

## OFS Object Architecture

- Rows packed into **16 MB objects** during loading
- Each object gets a unique **Logical Unique Identifier (LUUID)**
- Object identifiers go through the Teradata hashing algorithm for AMP assignment
- Small object size (16 MB) minimizes skew across AMPs

### Columnar Format Internals

OFS columnar objects contain a single **Row Group** organized as:

```
Data Object (LUUID = Gxl7we8)
├── Column Chunk for Txn_ID
│   ├── Page 1 (val1, val2, val3...)
│   ├── Page 2 (val4, val5, val6...)
│   └── Page 3 (val7, val8, val9...)
├── Column Chunk for Txn_Date
│   ├── Page 4 ...
│   ├── Page 5 ...
│   └── Page 6 ...
└── Column Chunk for Txn_Cost
    ├── Page 7 ...
    ├── Page 8 ...
    └── Page 9 ...
```

- I/O is at the **page level** within column chunks
- Only pages containing columns needed by the query are accessed
- Columnar format is the **recommended format** for OFS tables

### Row ID in OFS

OFS Row ID is 16 bytes total, same structure as BFS:

| Field | Size | Description |
|---|---|---|
| Hash (of LUUID) | 8 bytes | Hash of the object's logical unique ID |
| Partition Number | 4 bytes | Partition assignment |
| Uniqueness Number | 4 bytes | Offset into the row group |

## OFS Physical Design Options

For OFS tables, the available physical design choices are:
- Row vs. columnar format (columnar recommended)
- ORDER BY clause (similar to partitioning in BFS)
- Primary Index (distributes by hash)
- Single-Table Join Indexes (STJIs) in BFS

**Not supported on OFS tables:**
- Unique secondary indexes (USI)
- Non-unique secondary indexes (NUSI)
- Multi-table join indexes

Columnar format reduces the need for secondary indexes because each column becomes its own column partition, offering similar filtering advantages.

## OFS Table DDL Examples

### Basic OFS Table with MAP and STORAGE

```sql
CREATE MULTISET TABLE FS_Tbl,
  MAP = TD_MAP2,
  STORAGE = TD_OFSSTORAGE
  (
    StoreNo INTEGER,
    OrderTotal INTEGER,
    StoreName VARCHAR(50),
    OrderDate DATE FORMAT 'YY/MM/DD'
  )
NO PRIMARY INDEX;
```

### OFS Table with ORDER BY

```sql
CREATE TABLE mydb.ofs_ordered (
    id INTEGER,
    event_date DATE,
    amount DECIMAL(10,2)
) NO PRIMARY INDEX
  ORDER BY (event_date);
```

### OFS Table with Primary Index

```sql
CREATE TABLE mydb.ofs_pi_table (
    id INTEGER,
    event_date DATE,
    amount DECIMAL(10,2)
) PRIMARY INDEX (id);
```

### Combining ORDER BY and PRIMARY INDEX

```sql
CREATE TABLE mydb.ofs_combined (
    order_key INTEGER,
    order_date DATE,
    amount DECIMAL(10,2)
) PRIMARY INDEX (order_key)
  ORDER BY (order_date);
```

| Syntax | Impact on Row Placement |
|---|---|
| ORDER BY Col_A | Source spool sorted and distributed by value range of ORDER BY columns. Rows with same value co-located in same object(s). |
| PRIMARY INDEX PI_Col ORDER BY Date_Col | Source spool sorted and distributed by hash of PI. Rows co-located by ORDER BY value, sequenced by ordering column and PI hash. |

### Choosing ORDER BY vs PRIMARY INDEX Columns

- **ORDER BY**: Select columns that reduce read effort (equivalent of PPI columns from BFS tables). Rows with same value co-located in fewer objects.
- **PRIMARY INDEX**: Select columns that support AMP-local joins (PK-to-FK joins). Also useful for reducing global aggregation effort. Match to existing BFS PI definition if migrating.

## Single-Table Join Index (STJI) on OFS

STJIs in BFS on the Primary Cluster provide alternative access paths for OFS table data.

### Covered STJI Example

```sql
-- STJI created on Primary Cluster BFS storage
CREATE JOIN INDEX OFS_USER.JIOFS,
  MAP = TD_MAP2 AS
SELECT FS_Tbl.StoreNo,
       FS_Tbl.OrderTotal
FROM FS_Tbl
PRIMARY INDEX (StoreNo);
```

- **Covered STJI**: Contains all columns needed by a query — optimizer reads only the STJI, bypasses OFS entirely
- **Partially covered STJI**: Carries a Row ID pointing to base table rows (acts like a NUSI for OFS data)
- Tactical queries using a covered STJI execute entirely on the Primary Cluster with lower latency

### STJI EXPLAIN Output

```
1) First, we lock OFS_user.JIOFS in TD_MAP2 for access on a
   reserved RowHash to prevent global deadlock.
2) Next, we lock OFS_user.JIOFS in TD_MAP2 for access.
3) We do an all-AMPs RETRIEVE step in TD_MAP2 from OFS_user.JIOFS
   (Load Committed) by way of an all-rows scan...
```

## OFS Primary Index Mechanics

### Row Hash Range Assignment

During loading:
1. Primary index value is hashed → row assigned to an AMP
2. Each AMP sorts received rows and loads them into 16 MB objects
3. Each object contains rows from a **contiguous range of row hash values**

During reading:
1. Row hash ranges are **dynamically assigned** to AMPs of the reading cluster
2. Assignment is based on the number of AMPs in the reading cluster
3. Different-sized clusters can read the same table — a 3-AMP cluster gets broader ranges than a 6-AMP cluster
4. Tables with the same PI definition can be joined via AMP-local joins

### Object Overlap

- Object row hash boundaries may not align with reading AMP range boundaries
- Multiple AMPs may share reading of a single object
- I/O at page/column-chunk level minimizes actual overlap impact
- Optimizer detects degree of overlap and may choose not to use PI if fragmentation is high

## ORDER BY Loading Mechanics

During INSERT SELECT into an OFS table with ORDER BY:
1. Source spool is sorted by ORDER BY column(s)
2. Data is redistributed across AMPs based on value range of ORDER BY column(s)
3. Each AMP builds 16 MB data objects from its rows
4. Last object from an AMP may be smaller — subsequent INSERT SELECTs will NOT merge into it

Ordering guarantees:
- Global sort during INSERT SELECT
- Local sort within each object
- Multiple ORDER BY columns: sorted on first column, then second, etc.
- Without ORDER BY: no sort, no local ordering within objects

## Loading Data into OFS

### Supported Load Methods

| Method | Source | Notes |
|---|---|---|
| INSERT SELECT | BFS table or foreign table | Recommended approach; single commit at end |
| CREATE TABLE...AS | BFS or foreign table | Creates and loads in one step |
| Flow Service | External object storage | Continuous micro-batch loading |

### Not Supported for OFS

- TPT Load
- TPT Update
- TPT Stream
- Row-at-a-time INSERT/DELETE/UPDATE (avoid — creates many small objects)

### Flow Service Details

- Continuous micro-batch loading from external object storage into OFS
- Loads through Primary Cluster only (not from Compute Clusters)
- Configurable via UI or API (command-line utility for scripting)

Advantages over INSERT SELECT:
- **Checkpoint/recovery**: Restart at point of failure, completed micro-batches preserved
- **Quick data availability**: Each micro-batch available for queries immediately after commit
- **Less spool**: Single micro-batch needs far less spool than one large INSERT SELECT

MVCC (Multi-Version Concurrency Control) enables micro-batches to be immediately queryable without blocking.

### Common Load Scenarios

1. **Flow Service**: Data arriving continuously, need access ASAP, restart-on-failure needed
2. **INSERT SELECT**: Moving data from BFS or external object storage into OFS
3. **ETL staging**: Load to BFS staging table (can use traditional TPT), transform, then INSERT SELECT to OFS

### Row-at-a-Time Update Warning

Each individual row insert/delete/update creates a new object. Avoid:
- Single-row INSERT/DELETE/UPDATE against OFS tables
- TPump or TPT Stream against OFS tables (creates many small objects even with large pack sizes)

If TPump-style loading is required, run reorganization after load events.

## WRITE_NOS Options for External Object Storage

### PARTITION BY

Redistributes rows by hash of column list, invokes WRITE_NOS once per partition on each AMP. Each object contains rows for a **single partition value**.

### HASH BY

Same row redistribution as PARTITION BY, but WRITE_NOS is invoked **once per AMP**. Objects may contain rows from **multiple partition values** up to 16 MB.

### ORDER BY in WRITE_NOS

Sorts data on AMP before writing. Can combine with PARTITION BY or HASH BY. If used alone, avoids row redistribution (faster writes). Column values contribute to path segment names for path filtering.

## OFS Table Reorganization

```sql
ALTER TABLE mydb.ofs_table REORGANIZE;
```

- New objects are created on every load event (object storage has no in-place updates)
- Over time, sequential rows spread across different objects → increased I/O
- Reorganization consolidates and re-sorts data into minimal number of objects
- A background **Scheduler** utility will automate this; until available, run manually
- **Skip reorganization for static/cold-data tables**
- Monitor row counts over time for non-static large OFS tables to determine when reorganization is needed

## Monitoring in Lake

### Metric Streaming Service (MSS)

- DBQL and ResUsage data collected per cluster (Primary and each Compute Cluster)
- Extracted from DBC database in near-real time
- Stored in external object storage in **Parquet format**, then deleted from DBC
- Accessible via pre-defined foreign tables with views in **TD_Metric_Svc** database

### DBQL Views in TD_Metric_Svc

| DBQL Table | MSS View |
|---|---|
| DBQLogTbl | TD_METRIC_SVC.DBQLogV |
| DBQLExplainTbl | TD_METRIC_SVC.DBQLExplainV |
| DBQLObjTbl | TD_METRIC_SVC.DBQLSqlV |
| DBQLSqlTbl | TD_METRIC_SVC.DBQLStepV |
| DBQLStepTbl | TD_METRIC_SVC.DBQLUtilityV |
| DBQLSummaryTbl | TD_METRIC_SVC.DBQSummaryV |
| DBQLUtilityTbl | TD_METRIC_SVC.DBQLogV |

Not all DBQL tables are incorporated into MSS.

### Component ID Column

MSS adds a **component ID** column to each row:
- `POG` = Primary Cluster
- `COG` = Compute Cluster
- Enables analysis per cluster, per group, or system-wide

### ParentQueryID

- Added to DBQLogTbl for cross-cluster query correlation
- On Primary Cluster rows: ParentQueryID = QueryID
- On Compute Cluster rows: ParentQueryID matches the Primary Cluster's QueryID
- Use ParentQueryID to join all DBQL rows for a single query across clusters

### OFS/NOS Performance Metrics in DBQL

| Field | Description |
|---|---|
| NosRecordsReturned | Number of NOS or OFS records returned |
| NosRecordsSkipped | Number of records skipped |
| NosTables | Total NOS or OFS tables accessed |
| NosFilesSkipped | Files partially or fully skipped due to errors |
| NosFiles | Number of file reads attempted |
| NosTotalIOWaitTime | Total IO wait time across all steps |
| NosPhysReadIO | Total physical read IOs for NOS/OFS files |
| NosPhysReadIOKB | Total physical read IO KBs |
| NosRecordsReturnedKB | KBs in records returned |
| NosMaxIOWaitTime | Max IO wait time for individual IO (seconds, floating point) |
| NosCPUTime | CPU time for reading NOS/OFS files (seconds, floating point) |

Note: For columnar OFS tables, NosPhysReadIO records I/Os at both column chunk and page level.

## Data Placement Recommendations

### What to Store in BFS (Primary Cluster)

- System tables and data dictionary
- Small, frequently used reference tables
- Tables/indexes for tactical query SLAs
- Temporary staging tables for ETL
- Tables with features not yet supported by OFS

### What to Store in OFS (Managed Object Storage)

- Vast majority of user data tables
- All tables accessed by Compute Clusters
- Medium and large analytic tables

### What to Store in External Object Storage

- Seldom-used or archival data
- Exploratory data being evaluated
- Data shared with non-Teradata applications (Spark, etc.)
- Parquet/CSV/JSON files accessed via NOS

**Goal**: Keep Primary Cluster small, move most moderate/large tables to OFS for Compute Cluster processing.
