# Storage and Cache Architecture

> Source: Synthesized from TDN0001167 (Block-Level Compression), 541-0007106 (Table Rebuild & Clique Architecture), TDN0009803 (Teradata Vantage Overview), 541-0007565 (NoPI Table Guide), and Teradata Database documentation on FSG cache, cylinder management, WAL, and PE/AMP/BYNET internals.

## Physical Storage Hierarchy

```
Node (physical server)
├── AMPs (virtual processors, typically 8-32 per node)
│   ├── Vdisk (logical disk partition owned exclusively by one AMP)
│   │   ├── Cylinders (unit of storage allocation)
│   │   │   ├── Data Blocks (container for rows, up to ~1MB)
│   │   │   │   └── Rows (individual table records)
│   │   │   └── Cylinder Index (tracks data blocks within cylinder)
│   │   └── Master Index (memory-resident, one entry per allocated cylinder)
│   └── FSG Cache (in-memory cache of disk blocks)
└── Shared Disk Arrays (within clique boundary)
```

### Key Storage Concepts

| Concept | Description |
|---|---|
| **Vdisk** | Virtual disk — logical partition assigned to exactly one AMP. One AMP owns one or more vdisks exclusively |
| **Pdisk** | Portion of a LUN assigned to an AMP, uniquely identified and independently addressable |
| **Cylinder** | Basic unit of disk allocation (~1.8MB on modern systems). Contains data blocks for one or more tables |
| **Data Block** | Container holding multiple rows of a single table. Size configurable via `PermDBSize` |
| **Master Index** | Memory-resident structure containing an entry for every allocated cylinder on an AMP |
| **Cylinder Index** | Tracks which data blocks reside within each cylinder |

---

## FSG Cache (File Segment Cache)

The FSG (File System Segment Management Subsystem) cache is the primary memory cache for data blocks. Managed by PDE (Parallel Database Extensions), it sits between the AMP software and physical disk I/O.

### How FSG Cache Works

- **Cache hit**: Data block found in memory → no disk I/O required
- **Cache miss**: Block read from disk → placed in FSG cache for future access
- **Eviction**: LRU policy — least recently used blocks evicted when cache is full

### FSG Cache Behavior

- **Scope**: Per-AMP — each AMP manages its own FSG cache independently
- **Granularity**: Data blocks (not rows or cylinders)
- **Eviction**: LRU (Least Recently Used) replacement policy
- **Compressed blocks**: Stored compressed in FSG cache; each session must decompress into temporary memory for reading
- **Write-through**: Modified blocks are written to WAL first, then eventually flushed to disk

### FSG Cache Sizing

FSG cache size is determined by available node memory minus allocations for the operating system, PDE, and AMP software. On modern systems, FSG can consume a significant fraction of node memory.

**Monitoring FSG cache performance:**

```sql
-- Check cache hit ratios from ResUsage
SELECT TheDate, TheTime, NodeID,
       FilePReads,    -- physical reads (cache misses)
       FileLReads,    -- logical reads (total requests)
       CASE WHEN FileLReads > 0
            THEN (1 - (FilePReads * 1.0 / FileLReads)) * 100
            ELSE 100 END AS CacheHitPct
FROM DBC.ResUsageSVPR
WHERE vproc_type = 'AMP'
ORDER BY TheDate DESC, TheTime DESC
SAMPLE 20;
```

### FSG Cache and Block-Level Compression

When a table has block-level compression (BLC) enabled:

1. The **compressed** data block is read from disk into FSG cache
2. Each session needing the block must decompress it into **temporary memory**
3. Uncompressed blocks **cannot be shared** across sessions
4. Even the same session re-accessing a compressed block must decompress it again

This means BLC trades CPU for disk space — higher CPU for decompression, but fewer I/Os due to smaller blocks.

---

## Cylinder Management

### Cylinder Structure

Each AMP's vdisk is divided into cylinders. A cylinder is the smallest unit of space allocation. When a table needs more space, the file system allocates entire cylinders.

**Properties:**
- One cylinder can contain data blocks from **multiple tables**
- The Master Index tracks which tables have data in each cylinder
- Cylinders are assigned a **temperature** by TVS (Teradata Virtual Storage) based on access frequency

### Cylinder Packing

Cylinder packing consolidates partially-filled cylinders to reclaim space. Two mechanisms exist:

| Mechanism | Trigger | Scope |
|---|---|---|
| **AutoCylPack** (background) | Automatic, runs after AutoTempComp | Consolidates compressed and sparse cylinders |
| **Ferret PACKDISK** | Manual, via Ferret utility | Forces cylinder consolidation across an AMP |

**AutoCylPack behavior:**
- Enabled via DBS Control: `AutoCylPackColddata = TRUE` (default: FALSE)
- Combines data blocks from sparse cylinders into fewer, fuller cylinders
- Frees empty cylinders back to the free cylinder pool
- Default is FALSE to prevent heating cold cylinders inadvertently

```
Before AutoCylPack:
  Cylinder A: [Table1: 30%] [Table2: 15%] [free: 55%]
  Cylinder B: [Table1: 20%] [free: 80%]

After AutoCylPack:
  Cylinder A: [Table1: 50%] [Table2: 15%] [free: 35%]
  Cylinder B: [free: 100%]  ← returned to free pool
```

### Monitoring Cylinder Usage

```sql
-- Check free space per AMP using Ferret-style queries
SELECT Vproc, CurrentPerm, MaxPerm, PeakPerm,
       (MaxPerm - CurrentPerm) AS FreePerm,
       CAST((CurrentPerm * 100.0 / NULLIFZERO(MaxPerm)) AS DECIMAL(5,1)) AS PctUsed
FROM DBC.DiskSpaceV
WHERE DatabaseName = 'DBC'
ORDER BY PctUsed DESC;
```

---

## Data Blocks

### Block Size Configuration

Data block size directly impacts I/O efficiency and FSG cache utilization.

| DBS Control Field | Applies To | Default | Range |
|---|---|---|---|
| `PermDBSize` | Permanent tables | 127.5 KB (older) / up to 1 MB | System-wide default |
| `SpoolDBSize` | Spool files | Typically matches PermDBSize | System-wide default |
| `DATABLOCKSIZE` | Per-table override | Inherits from PermDBSize | `CREATE TABLE ... DATABLOCKSIZE = n BYTES` |

**Recommendations:**
- Use maximum block size for tables with BLC — larger blocks achieve better compression ratios
- Larger blocks reduce Master Index entries but increase I/O per read
- For OLTP-heavy workloads with small row access, smaller blocks may reduce unnecessary data transfer

```sql
-- Create table with explicit block size
CREATE TABLE mydb.large_fact (
    txn_id BIGINT,
    txn_date DATE,
    amount DECIMAL(15,2)
)
PRIMARY INDEX (txn_id)
DATABLOCKSIZE = 1048576 BYTES;  -- 1 MB maximum
```

### Free Space Percent (FSP)

FSP reserves space within each data block for future row insertions, reducing block splits.

```sql
-- Create table with free space percent
CREATE TABLE mydb.volatile_data (...)
PRIMARY INDEX (id)
FREESPACE = 20 PERCENT;  -- 20% reserved for growth
```

| Workload Type | Recommended FSP |
|---|---|
| Static / batch-loaded | 0% (default) |
| Moderate inserts/updates | 10-15% |
| Heavy OLTP | 15-25% |

---

## Write-Ahead Logging (WAL)

WAL ensures transaction durability and crash recovery. Before any data block modification is written to permanent storage, the change is recorded in the WAL log.

### WAL Flow

1. Transaction modifies a row → change written to WAL log (in memory)
2. Data block modified in FSG cache
3. At commit time → WAL flushed to disk (sequential I/O)
4. Modified data block written to permanent disk later (at checkpoint or cache eviction)

### WAL Characteristics

- **Sequential writes** — WAL is append-only, producing fast sequential I/O
- **Per-AMP** — each AMP maintains its own WAL log
- **Crash recovery** — on restart, WAL is replayed to bring data blocks to a consistent state
- **Performance impact** — WAL flush at commit time is a significant cost for high-frequency single-row transactions (e.g., TPump)

### Transient Journal

The Transient Journal works alongside WAL for transaction rollback:

- Stores **before-images** of modified rows during an active transaction
- Used for `ROLLBACK` — restores original row values
- Automatically discarded after successful `COMMIT`
- Certain bulk operations (e.g., `DELETE ALL ROWS`, dropping partitions) are optimized to avoid per-row transient journaling

---

## PE/AMP/BYNET Message Flow

### Request Processing Flow

```
Client → PE (parse, optimize, dispatch steps)
           → BYNET (dual-redundant, routes to target AMPs)
              → AMPs (access vdisk data, return results via BYNET → PE)
```

### Message Types

| Operation | BYNET Pattern | Description |
|---|---|---|
| **PI access** (UPI lookup) | Point-to-point (1 AMP) | Hash determines single target AMP |
| **USI lookup** | Point-to-point (2 AMPs) | Subtable AMP → base table AMP |
| **Full table scan** | Broadcast (all AMPs in map) | All AMPs in table's map participate |
| **Redistribution** | All-to-all | Every AMP sends rows to potentially every other AMP |
| **NUSI access** | Broadcast (all AMPs in map) | Each AMP scans local subtable |
| **Merge join** | No redistribution | Both tables co-located on same AMP |

### BYNET Architecture

- **Dual fabric**: Two independent BYNET networks (BYNET0 and BYNET1) for fault tolerance
- **Load balancing**: Messages alternate between BYNET0 and BYNET1
- **If one fails**: All traffic routes through the surviving BYNET with no data loss
- **Broadcast optimization**: Single message replicated at network level, not by sender
- **Merge phase**: BYNET handles ordered merging of sorted result streams from multiple AMPs

---

## Clique Architecture and Failover

### Clique Definition

A **clique** is a group of nodes that share access to the same disk arrays. Cliques provide hardware-level fault tolerance.

```
Clique 1                    Clique 2
┌──────────────────────┐   ┌──────────────────────┐
│ Node1    Node2       │   │ Node3    Node4       │
│ AMP0-7   AMP8-15     │   │ AMP16-23 AMP24-31   │
│     ↕         ↕      │   │     ↕         ↕     │
│ ┌─────────────────┐  │   │ ┌─────────────────┐ │
│ │ Shared Disk     │  │   │ │ Shared Disk     │ │
│ │ Arrays          │  │   │ │ Arrays          │ │
│ └─────────────────┘  │   │ └─────────────────┘ │
└──────────────────────┘   └──────────────────────┘
```

### Failover Behavior

When a node fails, its AMPs are **migrated** to surviving nodes within the same clique:

1. The failed node's AMPs are marked as down
2. Surviving nodes in the clique take ownership of the failed node's vdisks
3. AMPs restart on surviving nodes, accessing data via shared disk arrays
4. System continues operating with **degraded performance** (surviving nodes handle more AMPs)

### AMP Clusters and Fallback

AMP Clusters determine fallback data placement:

- A **cluster** is a group of AMPs (typically 2) where each AMP holds the fallback copy of the other's data
- Cluster members reside on **different nodes** (ideally different cliques) so a single node failure doesn't lose both copies
- **Recommended**: 2-AMP clusters for production systems

```
Cluster 0:  AMP 0 (Node 1) ↔ AMP 32 (Node 5)
            Primary data on AMP 0, fallback on AMP 32
            Primary data on AMP 32, fallback on AMP 0
```

### Hot Standby Nodes (HSN)

- A spare node within a clique, not running AMPs under normal operation
- On node failure, AMPs migrate to the HSN instead of overloading surviving production nodes
- Typically one HSN per clique on large EDW configurations

---

## Vdisk Management

### Vdisk Structure

Each AMP owns one or more vdisks exclusively. A vdisk is composed of pdisks (portions of LUNs from the disk array).

**Key properties:**
- One AMP → one or more vdisks (exclusive ownership)
- Vdisk data is physically striped across multiple pdisks for I/O parallelism
- No other AMP can read/write another AMP's vdisk (shared-nothing guarantee)

### Space Accounting

Space is managed at two levels with MAPS:

| Level | Mechanism | Purpose |
|---|---|---|
| **Global** | `DBC.GlobalDBSpace` | Tracks total space usage across all AMPs for each database |
| **Per-AMP** | `DBC.DatabaseSpace` | Per-AMP quota; soft limit that can flex with skew limits |

```sql
-- Check per-database space usage
SELECT DatabaseName,
       SUM(CurrentPerm) / 1e9 AS CurrentGB,
       SUM(MaxPerm) / 1e9 AS MaxGB,
       SUM(PeakPerm) / 1e9 AS PeakGB,
       CAST(SUM(CurrentPerm) * 100.0 / NULLIFZERO(SUM(MaxPerm)) AS DECIMAL(5,1)) AS PctUsed
FROM DBC.DiskSpaceV
GROUP BY DatabaseName
HAVING SUM(CurrentPerm) > 1e9
ORDER BY CurrentGB DESC;

-- Check per-AMP space distribution for a table
SELECT HASHAMP(HASHBUCKET(HASHROW(pi_col))) AS amp_id,
       COUNT(*) AS row_count
FROM mydb.large_table
GROUP BY 1
ORDER BY 2 DESC;
```

---

## Block-Level I/O Patterns

### Read Patterns

| Access Type | I/O Pattern | FSG Cache Benefit |
|---|---|---|
| **PI lookup** | Single-block random read | High — frequently accessed blocks stay cached |
| **Full table scan** | Sequential cylinder reads | Moderate — blocks cycled through cache quickly |
| **NUSI scan** | Local subtable scan + base block reads | Moderate — subtable blocks may stay cached |
| **Join (redistribution)** | All-to-all network + disk reads | Low — large data volumes may flush cache |

### Write Patterns

| Operation | I/O Pattern | Journal Overhead |
|---|---|---|
| **Single-row INSERT** | WAL write + data block modify | Transient journal entry per row |
| **Bulk INSERT-SELECT** | Sequential writes, batch WAL | Optimized — reduced per-row journaling |
| **DELETE all rows** | Metadata update only | No per-row transient journal |
| **UPDATE** | WAL + old block read + new block write | Before-image in transient journal |
| **DROP PARTITION** | Metadata + cylinder deallocation | Optimized — no per-row journal |

---

## Key DBS Control Settings for Storage and Cache

| DBS Control Field | Category | Purpose | Default |
|---|---|---|---|
| `PermDBSize` | File System | Maximum data block size for permanent tables | ~127.5 KB |
| `SpoolDBSize` | File System | Maximum data block size for spool files | ~127.5 KB |
| `AutoCylPackColddata` | File System | Enable background cylinder consolidation for cold data | FALSE |
| `BlockLevelCompression` | Compression | Master switch for block-level compression | Platform-dependent |
| `DefaultTableMode` | Compression | Default compression mode (MANUAL/AUTOTEMP/ALWAYS/NEVER) | NEVER |
| `TempBLCThresh` | Compression | Temperature threshold for automatic compression | Cold |
| `TempBLCSpread` | Compression | Buffer zone above/below threshold to prevent oscillation | 5% |
| `EnableTempBLC` | Compression | Enable temperature-based block-level compression | Platform-dependent |
| `NoDot0Backdown` | General | Once TRUE, prevents downgrade to pre-MAPS release | FALSE |

---

## Teradata Virtual Storage (TVS)

TVS assigns temperature ratings to cylinders based on access frequency, enabling intelligent data placement across storage tiers.

### Temperature Tiers

| Temperature | Access Pattern | Storage Tier | Compression |
|---|---|---|---|
| **Hot** | Frequently accessed | SSD / fastest storage | Uncompressed |
| **Warm** | Moderate access | Mid-tier storage | Optional |
| **Cold** | Rarely accessed | HDD / capacity storage | Auto-compressed (if enabled) |

### How TVS Works

1. Each AMP tracks cylinder access counts independently
2. TVS periodically recalculates temperature for all cylinders
3. Data blocks are migrated between storage tiers based on temperature
4. Temperature-based BLC compresses cold cylinders automatically when `EnableTempBLC = TRUE`

---

## Practical Monitoring Queries

```sql
-- System-wide disk space summary
SELECT COUNT(DISTINCT Vproc) AS AMPCount,
       SUM(CurrentPerm) / 1e12 AS TotalPermTB,
       SUM(MaxPerm) / 1e12 AS TotalMaxTB,
       CAST(SUM(CurrentPerm) * 100.0 / NULLIFZERO(SUM(MaxPerm)) AS DECIMAL(5,1)) AS PctUsed
FROM DBC.DiskSpaceV;

-- Top tables by space consumption
SELECT TOP 20
       DatabaseName, TableName,
       SUM(CurrentPerm) / 1e9 AS SizeGB,
       SUM(PeakPerm) / 1e9 AS PeakGB
FROM DBC.TableSizeV
GROUP BY DatabaseName, TableName
ORDER BY SizeGB DESC;
```
