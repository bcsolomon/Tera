---
name: teradata-elasticity
description: 'Manage Teradata elastic scaling and dynamic resource provisioning for VantageCloud and on-premises systems. Use when configuring auto-scaling compute clusters, managing elastic capacity for workload spikes, understanding scale-up vs scale-out strategies, or planning capacity changes without system downtime.'
metadata:
  author: teradata-expert
  version: "1.0"
---

# Teradata Elasticity

## When to Use

- Scaling processing power up or down for workload spikes
- Configuring Capacity on Demand (WM COD, EPOD, DS COD)
- Folding/unfolding nodes in cloud or on-premises deployments
- Resizing cloud instances (scale-up without data redistribution)
- Planning system expansion using MAPS for permanent growth
- Expanding or restricting disk storage capacity
- Automating resource allocation with TASM elastic capabilities

## Core Concepts

### Elasticity Options Overview

| Feature | Purpose | Direction |
|---|---|---|
| **WM COD** | Restrict/release CPU and I/O via workload management | Bi-directional |
| **EPOD** | Pay-per-use elastic performance burst | Bi-directional |
| **DS COD** | Restrict/release installed disk storage | Bi-directional |
| **Folding/Unfolding** | Add/remove processing nodes temporarily | Bi-directional |
| **Resizing** | Replace nodes with more powerful instances | Scale-up |
| **Storage Expansion** | Add physical disk storage | One-way up |
| **MAPS** | Add complete hardware units with minimal downtime | Primarily up |
| **TASM automation** | Dynamic resource reallocation across workloads | Adaptive |

> Source: TDN0009703 Table 1 — Elasticity Options in the Teradata Database

### Scale-Up vs Scale-Out

| Strategy | Mechanism | Changes | Data Movement |
|---|---|---|---|
| **Scale-up (Resizing)** | Replace node instance type with more powerful hardware | CPU, memory per node | None |
| **Scale-out (Unfold)** | Add nodes, redistribute AMPs across more nodes | Node count, CPU, memory, I/O bandwidth | None (AMP migration only) |
| **Full expansion (MAPS)** | Add complete nodes with new AMPs and storage | All resources | Deferred (background) |

### AMP Migration — The Foundation

Folding/unfolding relies on **AMP migration**, originally built for high availability:

- AMPs are portable software processes (containerized units) that don't care which node they run on
- Within a clique, all nodes share connectivity to each other's storage
- During unfold: AMPs migrate from original nodes to new nodes via GDO record updates
- No data is physically moved — only AMP-to-node assignments change
- Total AMP count remains constant; fewer AMPs per node = more resources per AMP

## Capacity on Demand (COD)

### WM COD — CPU and I/O Throttling

```
-- Check current WM COD settings from ResUsage
SELECT WM_COD_CPU / 10.0 AS WMCodCpuPct,
       WM_COD_IO AS WMCodIoPct
FROM DBC.ResUsageSPMA
WHERE TheDate = CURRENT_DATE
QUALIFY ROW_NUMBER() OVER (ORDER BY TheTime DESC) = 1;
```

- Set in Viewpoint Workload Designer in 1% increments
- No restart required — takes effect immediately
- Hard ceiling set by CS configuration packages (12.5% increments: 87.5%, 75%, 62.5%, 50%)
- Soft ceiling set by administrator in Viewpoint (can be lower, not higher)

### EPOD — Elastic Performance on Demand

- Pre-pay for base capacity (e.g., 63%), with elastic layer above (e.g., 12%)
- Hard ceiling (e.g., 75%) set by platform metering packages
- DBA raises WM COD percentage to access elastic capacity — no restart
- Billed per hour based on actual usage in the elastic layer
- Monitor via Viewpoint "Elastic Performance" portlet

### DS COD — Disk Storage COD

- TVAM-based: TVS hides cylinders on each AMP from the file system
- Changed in 5% increments; **requires restart**
- Takes storage from cold/medium tiers, preserves hot storage
- Must remove equivalent data before reducing DS COD percentage

## Procedure: Folding/Unfolding in the Public Cloud

### Scaling Factors

| Start Factor | AMPs/Node | Can Fold To | Can Unfold To |
|---|---|---|---|
| 1x | 24 | — | 2x, 4x |
| 2x | 12 | 1x | 4x |
| 4x | 6 | 2x, 1x | — |

### Enable Unfold-Ready at Launch

Specify "Folding/unfolding Enabled" during instance launch to pre-configure:
- 4 IP addresses per node (supports up to 4x unfolding)
- 8 TVS vprocs per node (3 AMPs each)

### Unfold Process (AWS)

1. Stop the database instance
2. Issue unfold command specifying level (2x or 4x)
3. New nodes provisioned; EBS volumes detached/reattached
4. AMPs, TVS vprocs, IP addresses migrated to new nodes
5. 2 parsing engines auto-created per new node
6. Instance relaunches — **15–20 minutes (AWS), 25–30 minutes (Azure)**

### Fold Process

- Reverses unfold: AMPs, TVS vprocs, IPs returned to original nodes
- PEs on folded nodes deleted
- **10–15 minutes (AWS), 20–25 minutes (Azure)**

## Procedure: Folding/Unfolding on IntelliFlex (On-Premises)

### Configuration Notation

```
Cliques(ActiveNodes + HSN + CODNodes)
Example: 4(6+1+3) = 4 cliques, 6 active + 1 hot standby + 3 COD nodes each
```

### Unfold Steps

1. CS defines new AMP-to-node assignments for COD nodes
2. Restart issued — typically minutes of outage
3. AMPs and TVS vprocs migrate to COD nodes
4. Parsing engines on COD nodes come online

### Key Differences from Cloud

- Operates at clique level; all cliques must unfold identically
- Granularity: any number of COD nodes (not limited to 2x/4x)
- Max expansion: 3× original nodes (limited by 3 TVS vprocs per original node)
- COD nodes require pre-installed parsing engines (offline until unfold)

## Procedure: Resizing (Scale-Up) in the Cloud

```
-- Single command to resize (AWS example)
-- Stop instance → change instance type → restart
-- Keeps same AMPs, AMP worker tasks, IP connections, storage
-- Typically completes in ~10 minutes
```

- Not available with BYOL (Bring Your Own License)
- Not available on IntelliFlex on-premises

## System Expansion with MAPS

- Adds **all** resources: nodes, AMPs, memory, storage, I/O, PEs
- Multiple hash maps coexist — no data redistribution during outage
- Tables moved to new map in background; data readable during move
- Best for permanent growth when COD/unfold limits are reached

```sql
-- Check current map assignments
SELECT TableName, MapName
FROM DBC.TablesV
WHERE DatabaseName = 'mydb';
```

## TASM Elastic-Like Capabilities

| Feature | Behavior |
|---|---|
| **Workload Exceptions** | Auto-demote queries exceeding CPU/I/O thresholds |
| **Tactical Exceptions** | Auto-demote tactical queries using >2 CPU sec or >200 MB I/O/node |
| **Timeshare Decay** | Reduce access rate for long-running Timeshare queries |
| **Flex Throttles** | Release delayed queries when system resources are underutilized |
| **System Events** | Trigger state changes on sustained CPU or AWT thresholds |
| **By-Workload Events** | Trigger state changes on workload-specific conditions |

## Platform Comparison

| Feature | Public Cloud | On-Prem IntelliFlex | IntelliCloud IntelliFlex | IntelliCloud Public Cloud |
|---|---|---|---|---|
| WM COD | No | Enterprise | Enterprise | No |
| EPOD | No | Enterprise | Enterprise | No |
| DS COD | No | Yes | Yes | No |
| Fold/Unfold | Yes | Yes | Yes | Yes |
| Storage Expansion | Yes | Yes | Yes | Yes |
| MAPS | No* | Yes | Yes | No* |
| TASM | Enterprise | Enterprise | Enterprise | Enterprise |

*MAPS on cloud planned for future releases

> Source: TDN0009703 Table 2 — Deployment Platform Comparison

## Troubleshooting

| Issue | Cause | Resolution |
|---|---|---|
| Cannot unfold past 4x | Upper limit of 64 nodes in cloud | Use MAPS for further expansion |
| WM COD won't exceed percentage | Hard ceiling from CS config packages | Contact CS to raise ceiling |
| DS COD reduction fails | Data usage exceeds target capacity | Delete data to below target before reducing |
| Performance not linear after unfold | Only CPU/memory added, not AMPs/storage | Expected — improvement depends on bottleneck type |
| Fold takes longer than expected | More components to migrate back | Normal — fold is typically faster than unfold |
| Uneven AMPs after IntelliFlex unfold | Normal when COD node count isn't factor of original | Acceptable; slight imbalance has no material impact |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-elasticity", path="references/FILENAME")` — do NOT call `list`.

- [Elastic Scaling Operations](./references/elastic-scaling-operations.md) — Capacity on Demand architecture (WM COD, EPOD, DS COD), folding/unfolding on cloud and IntelliFlex, AMP migration mechanics, MAPS expansion, resizing, storage expansion, TASM elastic capabilities, IntelliCloud configurations
