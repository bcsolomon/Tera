---
name: teradata-intelligent-memory
description: 'Configure and manage Teradata Intelligent Memory (TIM) for automatic tiering of hot data to in-memory storage. Use when optimizing frequently accessed tables or cylinders for memory caching, configuring TVS (Teradata Virtual Storage) temperature-based tiering, monitoring memory utilization and cache hit rates, or managing SSD/HDD data placement strategies.'
metadata:
  author: teradata-expert
  version: "1.0"
---

# Teradata Intelligent Memory (TIM)

## When to Use

- Enabling or configuring Teradata Intelligent Memory on a system
- Determining whether TIM will benefit a specific workload (I/O-bound with spare CPU)
- Allocating VERY HOT (VH) cache memory for frequently accessed permanent data
- Improving response-time consistency for tactical or SLA-driven applications
- Reducing physical I/O for repeatedly scanned large analytic tables
- Monitoring VH cache utilization, hit rates, and aging behavior via DBQL / ResUsage
- Using manual controls (Query_Band, Ferret FORCE) to heat or cool specific tables
- Tuning DBS Control settings related to TIM (DBSCacheThr, TIM FSG Cache Percent)
- Configuring TVS Migration I/O Collect Period for VH candidate list refresh
- Diagnosing side effects such as increased CPU consumption or reduced LRU cache effectiveness
- Optimizing data block sizes to reduce VH cache memory fragmentation
- Managing DBC table temperatures and log table maintenance for TIM

## Core Concepts

### What Is Teradata Intelligent Memory?

Teradata Intelligent Memory (TIM) extends the existing FSG cache and TVS infrastructure to keep the most frequently accessed permanent data in memory. Instead of relying solely on LRU (Least Recently Used) eviction, TIM uses **temperature-based caching**: the hottest cylinders on the system are marked VERY HOT and pinned in a dedicated portion of FSG cache called **VH cache**.

> Source: 541-0009920, Section 1 — Introduction

| Aspect | Traditional FSG Cache | Teradata Intelligent Memory |
|---|---|---|
| Eviction policy | LRU — most recently used data stays | Temperature — hottest cylinders stay |
| Scope | All data (perm, spool, volatile, temp) | Permanent data only |
| Predictability | Varies with concurrency and table size | Near-perfect cache hit for VH data |
| Eligible data | Subject to DBSCacheThr threshold | Based on cylinder temperature from TVS |

### Architecture Overview

TIM is a collaboration among three subsystems:

1. **Database Software** — Manages data blocks and cylinders in the filesystem.
2. **TVS (Teradata Virtual Storage)** — Tracks I/O frequency per cylinder, calculates temperatures, and builds the **VH candidate list** sorted by temperature.
3. **PDE (Parallel Database Extensions)** — Allocates VH cache memory and keeps as many of the hottest cylinders from the candidate list in cache as possible.

The VH candidate list is intentionally larger than VH cache capacity to account for empty space within cylinders. When a permanent data block is read from disk, PDE places it in VH cache if its cylinder is on the candidate list and hotter than the coldest cylinder currently in VH cache.

> Source: 541-0009920, Section 2 — Architecture

### Temperature Model

Starting with Teradata 14.10, **all I/Os** (both physical disk reads and FSG cache hits) contribute to cylinder temperature. Prior versions only counted physical I/Os, which could under-report the temperature of data that remained cached in FSG.

Temperature tiers:

| Tier | Description |
|---|---|
| VERY HOT | Hottest cylinders — eligible for VH cache (in-memory) |
| HOT | Frequently accessed — eligible for SSD placement on mixed storage |
| WARM | Moderate access — boundary between fast and slow storage |
| COLD | Infrequently accessed — placed on HDD / slow storage |

Temperature is tracked at the **cylinder level** (~12 MB). Because a cylinder may contain data from multiple tables or partitions, a hot table sharing a cylinder with a cold table will heat the entire cylinder.

> Source: 541-0009920, Sections 1–2, FAQ

### When TIM Helps

Ideal conditions for TIM:

- **Physical I/O is the bottleneck** — system approaches rated I/O throughput capacity.
- **CPU capacity is available** — removing I/O waits causes the system to consume more CPU per unit time.
- **Permanent data is being read** — inserts, updates, and deletes do not benefit even if data is in VH cache.
- **Volatile and temporary tables are not involved** — only permanent tables are eligible.

Use cases:
- Large analytic tables scanned repeatedly over extended periods that would normally age out of LRU cache.
- Tactical / near-real-time applications needing consistent sub-second response times.
- Tables not eligible for FSG caching due to cylinder-read limits or DBSCacheThr thresholds.

> Source: 541-0009920, Sections 3.2–3.3

### Potential Side Effects

1. **Increased CPU consumption** — Faster data access means the CPU processes work faster, potentially impacting other workloads. Workload management controls should be in place.
2. **Reduced LRU cache for non-VH data** — Memory allocated to VH cache is unavailable for spool, volatile, temp, and cold perm data. Consider adjusting `DBSCacheThr` or adding physical memory.
3. **Optimizer cache threshold interaction** — The optimizer applies `DBSCacheThr` to total FSG cache (LRU + VH). If 50% of FSG is VH cache, consider reducing `DBSCacheThr` proportionally to target the same effective LRU threshold.

> Source: 541-0009920, Section 3.4

## Configuration Summary

### Enabling TIM

TIM requires Teradata 14.10+. Minimum FSG cache per AMP:
- Active EDW (6000-series): **8 GB**
- Data Warehouse Appliance (2000-series): **5 GB**

The feature is enabled via the Teradata Support organization. Once enabled, the default allocates **50%** of FSG cache to VH cache.

### Setting VH Cache Size

Use the Control GDO Editor (`ctl`):

```
ctl
> screen dbs
> 8 = 30          -- Set TIM FSG Cache Percent to 30%
> wr              -- Write changes (requires TPA reset)
```

Field `(8) TIM FSG Cache Percent` controls the percentage of FSG cache reserved for VH cache.

> Source: 541-0009920, Section 6.2

### Key DBS Control Settings

| Setting | Purpose | Default |
|---|---|---|
| `TIM FSG Cache Percent` | % of FSG cache allocated to VH cache | 50 |
| `DBSCacheThr` | Max table size (% of FSG) eligible for caching | 10 (EDW) / 100 (DWA) |
| `TIMCacheLoadDisabled` | Disable VH preload after restart | FALSE |
| `TIMCacheLoadThrottle` | Throttle VH preload I/O | FALSE |
| `Migration I/O Collect Period` | How often TVS updates VH candidate list (seconds) | 100 |

> Source: 541-0009920, Sections 6.1–6.3

### Manual Controls

**Query_Band** — Load data as VERY HOT:

```sql
SET QUERY_BAND='TVSTEMPERATURE_PRIMARY=VERYHOT;' FOR SESSION;
```

Requires EXECUTE access on `DBC.VHCTRL()` macro. Without access, the temperature silently degrades to HOT.

**Ferret FORCE** — Change temperature of existing table:

```
> force "ADW_DB.INVOICE" P TEMPERATURE=VERYHOT
```

> **Warning:** Manual VERY HOT temperature is unnaturally high and may take months to cool down. Prefer HOT as the manual setting, or let TVS manage temperatures automatically.

> Source: 541-0009920, Section 7

## Monitoring

### DBQL Columns for TIM

At the request level (`DBQLogTbl`):
- `VHLogicalIO` / `VHLogicalIOKB` — Logical reads from VH cache
- `VHPhysIO` / `VHPhysIOKB` — VH reads serviced by physical disk (cache miss)

At the step level (`DBQLStepTbl`): same metrics per step.

### ResUsage Metrics

| Table | Metric | Description |
|---|---|---|
| `ResUsageSPMA` | `VHCacheKB` | VH cache size per node |
| `ResUsageSVPR` | `VHCacheInUseKB` | VH cache currently in use per AMP |
| `ResUsageSVPR` | `VHAgedOut` / `VHAgedOutKB` | Data aged out of VH cache |
| `ResUsageSVPR` | `VHAcqs` / `VHAcqKB` | Logical VH reads |
| `ResUsageSVPR` | `VHAcqReads` / `VHAcqReadKB` | Physical reads due to VH cache miss |
| `ResUsageSPS` | `VHAcqs` / `VHAcqKB` | VH logical reads per workload |

> Source: 541-0009920, Sections 4.1–4.2, Appendix E

### Cache Effectiveness Formula

```sql
ZEROIFNULL((ReqIOKB - ReqPhysIOKB) / NULLIFZERO(ReqIOKB) * 100) AS CacheEffKB
```

VH-specific hit rate:

```sql
ZEROIFNULL(VHPhysIO / NULLIFZERO(VHLogicalIO) * 100) AS VHCacheMissRate
```

> Source: 541-0009920, Appendix A

## Maintenance

- **DBC tables** default to VERY HOT STATIC temperature. Large DBC log tables (ResUsage, DBQL, event logs) remain on the VH candidate list permanently. Move log data to COLD history tables and run `PACKDISK` on DBC to free VH candidate slots.
- **Memory fragmentation** — Data block sizes that are powers of 2 (64 KB, 128 KB) pack most efficiently into VH cache. Use `ALTER TABLE ... DATABLOCKSIZE=127KILOBYTES IMMEDIATE` to reblock. Expect 20–30% fragmentation loss on a mature system.
- **VH preload** — After a restart, the system automatically preloads VH cylinders into cache at logons-enabled. Disable with `TIMCacheLoadDisabled = TRUE` or throttle with `TIMCacheLoadThrottle = TRUE`.

> Source: 541-0009920, Section 5

## Troubleshooting

| Symptom | Likely Cause | Action |
|---|---|---|
| No reduction in physical I/O after enabling TIM | VH cache too small or workload not I/O-bound | Review ResUsage for I/O saturation; increase TIM FSG Cache Percent |
| Increased response time for non-critical workloads | LRU cache reduced by VH allocation | Check `DBSCacheThr`; add physical memory; reduce VH% |
| VH cache utilization below 80% | Data block fragmentation | Reblock hot tables to power-of-2 block sizes |
| Tables unexpectedly hot or in VH cache | Shared cylinders (boundary cylinders) | Review Data Temperature Report; partition tables to isolate access |
| VH candidate list not updating | Migration I/O Collect Period too long | Check TVS setting; default 100 sec is recommended |
| Manual VERY HOT data not cooling | VERY HOT manual temperature is unnaturally high | Use Ferret FORCE to cool; prefer HOT instead of VERY HOT for manual |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-intelligent-memory", path="references/FILENAME")` — do NOT call `list`.

- [TIM Configuration and Tuning](references/tim-configuration-and-tuning.md) — Architecture details, DBS Control settings, configuration workflow, monitoring queries
- [TVS Storage Tiering](references/tvs-storage-tiering.md) — Temperature model, SSD/HDD/memory tiers, migration policies, compression interactions
