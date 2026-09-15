---
name: teradata-vantagecloud-lake
description: 'Teradata VantageCloud Lake architecture including Primary Cluster, Compute Clusters, Object File System (OFS), compute groups and profiles, elastic scaling, cost management, OFS table design (indexes, ORDER BY, STJI), Flow Service loading, workload management in Lake, analytic compute clusters, and QueryGrid. Use when designing for VantageCloud Lake, creating OFS tables, configuring compute groups, managing elastic scaling, or migrating from on-premise to Lake.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata VantageCloud Lake

## When to Use

- Designing tables for the Object File System (OFS)
- Configuring compute groups and profiles for elastic scaling
- Managing cost vs performance tradeoffs
- Loading data into OFS tables
- Setting up analytic compute clusters
- Understanding Lake vs on-premise architecture differences
- Configuring workload management in Lake

## Lake Architecture

```
┌─────────────────────────────────┐
│        Primary Cluster          │
│  (Always-on, persistent data)   │
│  ┌──────┐ ┌──────┐ ┌──────┐   │
│  │ Node │ │ Node │ │ Node │   │
│  └──┬───┘ └──┬───┘ └──┬───┘   │
│     └────────┼────────┘        │
│              │ BYNET           │
└──────────────┼─────────────────┘
               │
    ┌──────────▼──────────┐
    │  Object File System │  (Cloud object storage: S3/Azure/GCS)
    │  (OFS)              │
    └──────────┬──────────┘
               │
  ┌────────────┼────────────┐
  │            │            │
┌─▼──┐    ┌───▼──┐    ┌───▼──┐
│ CC1│    │ CC2  │    │ CC3  │  Compute Clusters
│(BI)│    │(ETL) │    │(DS)  │  (Elastic, scale up/down)
└────┘    └──────┘    └──────┘
```

### Key Components

| Component | Description |
|---|---|
| **Primary Cluster** | Always-on nodes; manages metadata, small hot data |
| **Object File System (OFS)** | Cloud object storage for table data |
| **Compute Clusters** | Elastic compute; scale independently per workload |
| **Compute Groups** | Logical grouping of compute clusters with policies |
| **Compute Profiles** | Scaling configurations (min/max nodes, auto-scale) |

## Data Storage Options

| Location | Best For | Notes |
|---|---|---|
| Primary Cluster (local) | Small, frequently accessed tables | Limited space; higher cost |
| OFS (object storage) | Large tables, cold/warm data | Elastic; pay for storage used |

## OFS Table Design

### Creating OFS Tables

```sql
-- Basic OFS table (no primary index)
CREATE TABLE mydb.ofs_table (
    id INTEGER,
    event_date DATE,
    payload VARCHAR(1000)
) NO PRIMARY INDEX;  -- default for OFS

-- OFS table with primary index (distributes within OFS objects)
CREATE TABLE mydb.ofs_pi_table (
    id INTEGER,
    event_date DATE,
    amount DECIMAL(10,2)
) PRIMARY INDEX (id);

-- OFS table with ORDER BY (improves range scans)
CREATE TABLE mydb.ofs_ordered (
    id INTEGER,
    event_date DATE,
    amount DECIMAL(10,2)
) NO PRIMARY INDEX
  ORDER BY (event_date);
```

### OFS Index Options

| Index Type | Supported | Notes |
|---|---|---|
| Primary Index | Yes | Distributes data across OFS objects by hash |
| No Primary Index | Yes (default) | Objects assigned round-robin to AMPs |
| Single-Table Join Index (STJI) | Yes | Excellent for covered queries |
| ORDER BY | Yes | Improves range-scan performance |
| Secondary Index (USI/NUSI) | No | Not supported on OFS tables |
| Multi-table Join Index | No | Not supported on OFS tables |

### Single-Table Join Index on OFS

```sql
CREATE JOIN INDEX mydb.ji_ofs_events AS
SELECT event_date, event_type, SUM(amount) AS total
FROM mydb.ofs_events
GROUP BY event_date, event_type
PRIMARY INDEX (event_date);
```

STJIs provide covered access — the optimizer reads only the compact join index instead of the full OFS table.

## Compute Groups and Profiles

### Compute Groups

Logical containers that map users/applications to compute clusters:

```
Compute Group: "BI_Users"
├── Compute Profile: "standard" (2-4 nodes, auto-scale)
├── Compute Profile: "burst" (4-8 nodes, manual scale)
└── Default timeout: 30 min idle → scale down
```

### Compute Profiles

Define scaling behavior:

| Setting | Description |
|---|---|
| Min instances | Minimum nodes (can be 0 for scale-to-zero) |
| Max instances | Maximum nodes for auto-scaling |
| Auto-scale | Scale up/down based on demand |
| Idle timeout | Time before scaling down |
| Cool-down period | Minimum time between scale events |

### Analytic Compute Clusters

Dedicated clusters for ML/analytics with:
- Default throttle: 10 concurrent queries
- APPLY limit: 3 concurrent analytic functions
- GPU clusters available (throttle: 2)
- Isolated from production workloads

## Loading Data into OFS

### INSERT-SELECT (Recommended)

```sql
INSERT INTO mydb.ofs_target
SELECT * FROM mydb.staging_table;
```

### Flow Service (Continuous Loading)

Continuous data ingestion from external sources into OFS tables.

### WRITE_NOS to External Object Storage

```sql
-- Export from Lake to external cloud storage
CREATE MULTISET TABLE export_manifest AS (
    SELECT * FROM TABLE ( WRITE_NOS (
        ON (SELECT * FROM mydb.ofs_table WHERE event_date >= DATE '2025-01-01')
        USING (
            LOCATION = '/s3/external-bucket.s3.amazonaws.com/exports/'
            AUTHORIZATION = mydb.ext_auth
            STOREDAS = 'PARQUET'
            PARTITION BY (event_date)
        )
    ) AS w
) WITH DATA;
```

## Workload Management in Lake

### Default Priorities

Lake uses automatic prioritization:
- Tactical queries get highest priority
- Queries auto-classified by estimated cost
- Automatic demotion of long-running queries

### Account String Variables

```sql
-- Map users to compute groups via account strings
SET SESSION ACCOUNT = '$CG_BI_Users';
```

### Key Differences from On-Premise TASM

| Feature | On-Premise | Lake |
|---|---|---|
| Workload isolation | Virtual Partitions | Compute Groups |
| Scaling | Fixed hardware | Elastic scale up/down |
| Cost model | Fixed infrastructure | Pay-per-use compute |
| Throttles | Configurable | System-managed defaults + custom |
| Analytic control | Manual WLM | Dedicated analytic clusters |

## OFS Table Reorganization

```sql
-- Reorganize an OFS table (optimize object layout)
ALTER TABLE mydb.ofs_table REORGANIZE;
```

## Cost Management

### Factors

| Factor | Impact |
|---|---|
| Compute cluster size | Largest cost driver |
| Idle time before scale-down | Set aggressive timeouts |
| Data scanning volume | Use ORDER BY, STJIs to reduce I/O |
| Storage volume | OFS pricing per TB |

### Cost Reduction Techniques

- Scale-to-zero for infrequent workloads
- Right-size compute profiles (don't over-provision max)
- Use STJIs to reduce data scanned
- Partition OFS tables by date for elimination
- Schedule batch compute clusters to spin up only during ETL windows

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-vantagecloud-lake", path="references/FILENAME")` — do NOT call `list`.

Load these files for detailed technical reference on specific topics:

- **references/ofs-tables-and-data-management.md** — OFS internals (index structure, columnar format, row groups, column chunks), BFS vs OFS comparison, full DDL with MAP/STORAGE clauses, ORDER BY and PI mechanics, STJI covered/partially-covered patterns, loading methods (INSERT-SELECT, Flow Service, WRITE_NOS PARTITION BY vs HASH BY), reorganization, monitoring views (MSS, TD_Metric_Svc, NOS metrics)
- **references/compute-groups-and-workload-management.md** — CREATE COMPUTE GROUP/PROFILE full SQL syntax, compute group design patterns and tradeoffs, compute profile time-window design with overlap rules, throttle limits (15/10/3), autoscaling, analytic compute clusters, default workloads and priority, account string best practices, cost breakdown (compute ~80% / storage ~10-15% / I/O ~5%), OFS cache, UDF EXECUTE ON COMPUTE/PRIMARY, QueryGrid, APIs
