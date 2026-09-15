# TVS Storage Tiering

## TVS Temperature Model

### How Temperature Is Calculated

Teradata Virtual Storage (TVS) tracks I/O frequency at the **cylinder level** to assign a numerical temperature value to each cylinder. A cylinder is a fixed-size allocation of contiguous disk sectors (~12 MB on Teradata 13.10+).

Starting with Teradata 14.10, temperature calculations include:

- **Physical disk I/Os** — reads from HDD or SSD.
- **FSG cache hits** — logical reads served from memory without hitting disk.

Prior to 14.10, only physical disk I/Os counted. This meant constantly cached data could appear artificially cold and risk demotion to slow storage.

> Source: 541-0009920, Sections 1–2

### Temperature Tiers

TVS normalizes numerical temperatures into four tiers:

| Tier | Meaning | Storage Placement |
|---|---|---|
| VERY HOT | Hottest data on the system | VH cache (in-memory) |
| HOT | Frequently accessed | SSD on mixed-storage systems |
| WARM | Moderate access frequency | Boundary between SSD and HDD |
| COLD | Infrequently accessed | HDD / slow storage |

The boundaries between tiers are reported in the Data Temperature Report as `TempWarmCeiling` and `TempWarmFloor`. The `VeryHotCache` column indicates the boundary for in-memory storage.

### Static Temperature

Some objects are assigned a **static temperature** that does not change over time. By default, all DBC table cylinders are set to VERY HOT STATIC, which:

- Keeps data dictionary access fast for parsing.
- Can waste VH candidate slots on large DBC log tables (DBQL, ResUsage, event logs).

Use the `dbscontrol` setting `UsePermDefaultsForDBC` to change DBC tables to HOT with normal cooling behavior.

> Source: 541-0009920, Section 5

### Boundary Cylinders

A single cylinder may contain data from multiple tables or partitions. Temperature is per-cylinder, not per-table. Consequences:

- A frequently accessed table sharing a cylinder with a cold table heats the entire cylinder.
- In the Data Temperature Report, only the table/partition at the beginning of the cylinder is reported.
- Boundary cylinders are more common with partitioned tables.

**Mitigation:** Use partitioning and indexing to isolate access patterns so that hot and cold data occupy separate cylinders. NoPI and non-partitioned tables tend to have uniform temperatures across all cylinders, reducing TVS's ability to differentiate.

> Source: 541-0009920, FAQ

## Storage Hierarchy

### Three-Tier Architecture

With Teradata Intelligent Memory, the storage hierarchy becomes:

```
┌─────────────────────────────┐
│    VH Cache (In-Memory)     │  ← VERY HOT cylinders
│    ~60 GB/sec/node scan     │
├─────────────────────────────┤
│    SSD (Solid State)        │  ← HOT cylinders
│    ~6.4 GB/sec/node scan    │
├─────────────────────────────┤
│    HDD (Hard Disk)          │  ← WARM/COLD cylinders
│    Lowest throughput        │
└─────────────────────────────┘
```

Performance benchmarks from the Teradata Active EDW 6700:
- **SSD scan rate:** ~6.4 GB/sec/node (15 SSDs)
- **Memory scan rate:** >60 GB/sec/node

Actual improvements vary dramatically depending on workload characteristics.

> Source: 541-0009920, Section 3.2

### Data Flow Between Tiers

**Physical storage migration (TVS):**
TVS automatically migrates cylinders between SSD and HDD based on temperature. This has been available since Teradata 13.10 for mixed-storage systems.

**Memory tier (TIM):**
VH cache is managed by PDE, not TVS directly. TVS provides the candidate list; PDE controls what is actually in memory.

**No direct transfer between VH cache and LRU cache** in Teradata 14.10:
- Data cooling out of VH cache must be aged out, read from disk, then placed in LRU cache.
- Data heating into VH range from LRU cache must be aged out of LRU, read from disk, then placed in VH cache.

This means there can be latency when data transitions between cache pools.

> Source: 541-0009920, Section 6.2

### Migration Policies

TVS migration is controlled by settings in the Control GDO Editor (`ctl > scr tvs`):

| Setting | Default | Description |
|---|---|---|
| Migration | On | Enable/disable automatic cylinder migration |
| Metric Collection | On | Enable/disable I/O frequency tracking |
| Migration Time to Respond | 30 min | Max time allowed for a migration operation |
| Migration Benefit Lifetime | 10080 min (7 days) | How long a migration benefit is expected to last |
| Maximum Concurrent Migrations | 2 | Max parallel migration operations |
| Metric Age Period | 300 min | How long temperature metrics are retained |
| Migration Period | 300 sec | How often migration evaluations occur |
| Migration I/O Collect Period | 100 sec | How often I/O metrics are collected and VH list updated |

**Recommendation:** Leave migration settings at defaults. TVS is designed to be hands-off — customers consistently find that automatic management outperforms manual placement.

> Source: 541-0009920, Sections 6.1, Introduction

## Manual Temperature Controls

### Query_Band for Data Loading

Set the temperature of newly loaded permanent data:

```sql
-- Load primary data as VERY HOT
SET QUERY_BAND='TVSTEMPERATURE_PRIMARY=VERYHOT;' FOR SESSION;

-- Load as HOT (recommended over VERY HOT for manual control)
SET QUERY_BAND='TVSTEMPERATURE_PRIMARY=HOT;' FOR SESSION;
```

**Access control:** The user must have EXECUTE access on the `DBC.VHCTRL()` macro to use VERY HOT. Without access, the temperature silently degrades to HOT. No error is returned.

> Source: 541-0009920, Section 7

### Ferret FORCE Command

Change the temperature of existing tables:

```
ferret
> force "ADW_DB.INVOICE" P TEMPERATURE=VERYHOT

  FORCE command changed the temperature of table ADW_DB.INVOICE
  to VERY-HOT.
  The temperature of 638 cylinders have been changed to VERY-HOT.
```

### Cooling Overheated Data

Manual VERY HOT temperature values are unnaturally high. If data loaded as VERY HOT is never accessed, it takes **several months** to cool down to WARM naturally. To accelerate cooling:

1. Use Ferret FORCE to set the table to a lower temperature (e.g., WARM or COLD).
2. Let TVS reheat the data naturally based on actual access patterns.

**Best practice:** Use HOT (not VERY HOT) for manual temperature settings. HOT is typically high enough for the data to appear on the VH candidate list while remaining within a natural temperature range.

> Source: 541-0009920, Section 7, FAQ

## Compression Interactions

### Block Level Compression (BLC)

Data compressed with BLC remains compressed when stored in FSG cache or VH cache. The data is decompressed when the database software processes it and recompressed when written back to cache.

**Trade-off with TIM:**
- **Pro:** Compressed data occupies less VH cache space, allowing more data to be cached.
- **Con:** Decompression overhead increases CPU time per data access, potentially increasing response times for applications accessing compressed data in memory.

> Source: 541-0009920, FAQ

### Temperature-Based Compression

Temperature-based compression primarily affects COLD data and is independent of TIM. It can be used alongside TIM without conflict — COLD data gets compressed for storage efficiency while VERY HOT data remains in memory.

> Source: 541-0009920, FAQ

## Performance Implications

### CPU vs. I/O Trade-Off

TIM removes I/O wait time but increases CPU consumption rate per query. A query that previously spent most of its elapsed time waiting for disk reads will now consume CPU continuously. This can:

- **Benefit** the target workload — 80% or greater reduction in elapsed time is possible for I/O-bound work.
- **Impact** other workloads — Higher sustained CPU consumption leaves less CPU for concurrent queries.
- **Require** workload management — TASM/TIWM rules should prevent any single workload from monopolizing CPU.

Example from Teradata Labs testing:
- Before TIM: 3,968 seconds elapsed, 3.3 TB physical I/O, ~30% average CPU.
- After TIM: 783 seconds elapsed, 44 GB physical I/O, ~70% average CPU.
- Result: 80% reduction in elapsed time.

> Source: 541-0009920, Section 4.5

### Tactical Workload Benefits

Tactical queries (short-running, single/group AMP, index-based) may already enjoy 80–90% cache effectiveness with LRU FSG cache. TIM can increase this to **99%+**, significantly reducing both average response time and response time variance when the I/O subsystem is saturated.

> Source: 541-0009920, Section 3.3

### Table Design Recommendations

Table design affects how well TVS can differentiate temperatures:

| Design | Temperature Differentiation | TIM Effectiveness |
|---|---|---|
| Partitioned by date/range | High — only accessed partitions heat up | Best |
| Column-partitioned | High — only accessed columns heat up | Best |
| Secondary/join indexes | Moderate — index cylinders heat independently | Good |
| Non-partitioned with PI | Low — full table scans heat all cylinders equally | Limited |
| NoPI tables | Lowest — all cylinders have similar temperature | Least effective |

**Recommendation:** Apply partitioning and indexing to isolate frequently accessed data into distinct cylinders. This helps TVS place the right data in VH cache and on SSDs.

> Source: 541-0009920, FAQ

### Sizing VH Cache

There is no direct formula from DBQL/ResUsage to calculate exact memory requirements. Use this approach:

1. Identify the highest-I/O workloads from DBQL (`ReqPhysIOKB`).
2. Determine the tables those workloads access.
3. Estimate the hot subset size (e.g., if 80% of queries scan the last 7 days of a daily-loaded table, multiply daily load size × 7 × replication factor).
4. Allocate enough VH cache to hold that subset.

**Example:** A table receives 50 GB daily, partitioned by date. If 80% of queries scan data <7 days old, aim for at least 400 GB of VH cache for that table's hot partition set (accounting for fallback and overhead).

> Source: 541-0009920, FAQ

## Eligible and Ineligible Data

### Eligible for VH Cache

- Permanent tables (primary data, fallback, secondary indexes, join indexes)
- DBC tables (static VERY HOT by default)

### Not Eligible for VH Cache

| Object Type | Reason |
|---|---|
| Spool tables | Short-lived; all spool has the same HOT temperature in TVS |
| Volatile tables | No persistent definition; session-scoped |
| Global temporary tables | Contents are session-scoped |
| Data being inserted/updated/deleted | TIM benefits reads, not writes |

> Source: 541-0009920, Sections 3.2, FAQ

## Monitoring Temperature Changes Over Time

The Data Temperature Report (using the heatmap UDF and view) can be collected periodically and stored in a history table to track how cylinder temperatures evolve:

```sql
-- Store periodic temperature snapshots
INSERT INTO temperature_history
SELECT CURRENT_TIMESTAMP AS SnapshotTime
      ,DatabaseName
      ,TableName
      ,StartPartition
      ,CylinderId
      ,Temperature
      ,NormalizedTempInfo
      ,VeryHotCandidate
      ,VeryHotCache
      ,PercentFull
FROM  TD1410_HEATMAP_V;
```

This enables trending analysis to understand:
- How quickly new data heats up after loading.
- Which partitions cycle between hot and cold over time.
- Whether manual temperature overrides are cooling as expected.

> Source: 541-0009920, Section 4.3
