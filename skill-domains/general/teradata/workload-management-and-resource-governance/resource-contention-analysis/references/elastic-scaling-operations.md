# Elastic Scaling Operations

Comprehensive reference for Teradata elasticity mechanisms including Capacity on Demand, folding/unfolding, resizing, MAPS expansion, storage expansion, and TASM elastic capabilities across cloud and on-premises deployment platforms.

> Source: TDN0009703 — Elasticity in Teradata Vantage

---

## 1. Capacity on Demand (COD)

COD imposes a limiting effect on one or more system resources (CPU, I/O, disk space). Resources are already installed but held back. Typically applied at initial installation with growth in mind — the customer pays less initially and unlocks capacity as business needs increase.

### 1.1 Workload Management COD (WM COD)

WM COD restricts the percentage of CPU and I/O available system-wide through Teradata Workload Management software.

**Key Characteristics:**
- Set in Viewpoint Workload Designer in 1% increments
- No restart required — changes take effect immediately
- Must be set for each planned environment (online, batch, month-end)
- CPU and I/O limits recommended to use the same percentage
- Available on Enterprise Tier with TASM; expanding to Advanced Tier on IntelliFlex

**Configuration Package Hard Ceiling:**
CS installs COD configuration packages at 12.5% intervals (88%, 75%, 63%, 50%). If the contract is for 80%, CS sets packages to 88% (next highest) and the administrator reduces to 80% in Viewpoint.

**Enforcement:**
- **CPU:** Hard limit on the TDAT control group using an enforcement period and quota; when quota reached, no TDAT work runs until the next period
- **I/O:** Enforced per disk drive; I/O requests costed by type/size; stops when COD-allowable bandwidth consumed per interval; cache reads not restricted

> Source: TDN0009703 §2.1.1–§2.1.3

### 1.2 Elastic Performance on Demand (EPOD)

EPOD extends WM COD to provide pay-per-use resource elasticity for unplanned business needs.

**Two EPOD Approaches:**

| Approach | Contracted | Elastic | Unavailable | Hard Ceiling |
|---|---|---|---|---|
| **A: WM COD + EPOD** | 63% | 12% | 25% | 75% |
| **B: EPOD only** | 60% | 40% | 0% | 100% (no ceiling) |

**How EPOD Works:**
1. CS installs PM COD packages to set the hard ceiling
2. Administrator sets WM COD to contracted percentage (soft ceiling)
3. When demand spikes, raise WM COD up to hard ceiling — no restart required
4. When demand subsides, reduce WM COD back down
5. Viewpoint "Elastic Performance" portlet tracks usage; billed hourly for elastic consumption

**ResUsage COD Columns:**

```sql
-- Check COD settings from ResUsage
SELECT
    WM_COD_CPU / 10.0 AS WM_COD_CPU_Pct,  -- 1000 = disabled
    WM_COD_IO         AS WM_COD_IO_Pct,    -- 100 = disabled
    PM_COD_CPU / 10.0 AS PM_COD_CPU_Pct,   -- 1000 = disabled
    PM_COD_IO         AS PM_COD_IO_Pct     -- 100 = disabled
FROM DBC.ResUsageSPMA
WHERE TheDate = CURRENT_DATE
QUALIFY ROW_NUMBER() OVER (ORDER BY TheTime DESC) = 1;
```

With EPOD, `PM_COD_XX` fields report 100% (disabled) because enforcement is via WM COD triggered by PM COD packages. The `WM_COD_XX` fields report the currently active WM COD values.

> Source: TDN0009703 §2.2

### 1.3 Disk Space COD (DS COD)

DS COD regulates available disk storage by hiding cylinders from AMP file systems.

**TVAM DS COD (Recommended):**
- Implemented through Teradata Virtual Administrative Manager (TVAM)
- CS installs storage capacity configuration packages (tamper-resistant)
- TVS marks a percentage of each AMP's cylinders as unavailable
- Applied equally to each subpool on a node
- On mixed-temperature systems, storage is taken from cold/medium tiers, preserving hot storage

**Operational Rules:**
- Changed in 5% increments (up or down)
- **Requires a restart** for each change
- When reducing DS COD (shrinking storage), equivalent data must be removed first
- Can be set independently across SSD and HDD storage classes (same percentage recommended)

**Traditional DS COD (Legacy):**
- Creates a dummy database with allocated perm space to make storage unavailable
- Not tamper-resistant; requires usage auditing
- Uses DBSControl parameter "Cylinders Saved for PERM" to limit SPOOL/TEMP
- PERM and SPOOL limits managed independently; no restart required

**Use Cases for DS COD:**
- Temporary storage boost for seasonal processing
- Space for block-level compression testing on large tables
- Supporting INSERT-SELECT during MAPS table migrations
- Locking down storage for planned future growth (combined with WM COD)

> Source: TDN0009703 §2.3

---

## 2. Teradata Virtual Storage (TVS)

TVS is fundamental to DS COD, folding/unfolding, and AMP migration.

- TVS vproc manages cylinder allocation and tracks physical data location per subpool
- Each AMP's Master Index carries an "Extent ID"; TVS interprets it to find the actual cylinder
- This decoupling allows multiple AMPs as virtual processes on a single node while retaining shared-nothing architecture
- Supports temperature-based data placement, TBBLC, and Teradata Intelligent Memory (TIM)
- Always running on all platforms (permanent since Teradata Database 13.0)

> Source: TDN0009703 §2.3.1

---

## 3. AMP Migration Mechanics

AMP migration is the foundational technology for folding/unfolding.

- AMPs are self-contained, stateless software processes; the `config.GDO` record defines AMP-to-node assignments
- During migration: system brought down → GDO updated → AMPs reassigned to different nodes
- Within a clique, all nodes share connectivity to each other's storage — no data movement needed
- **Original purpose:** high availability — AMPs migrate to surviving nodes (or HSN) on node failure
- **Repurposed for elasticity:** AMPs migrate to new/passive nodes during unfold; same mechanism, no data redistribution

> Source: TDN0009703 §3.1

---

## 4. Folding/Unfolding in the Public Cloud

Supported on Enterprise, Advanced, and Base Tiers.

### 4.1 Scaling Factors and AMP Distribution

| Initial Scale | AMPs/Node | Unfold Options | Fold Options | Max Nodes (64 limit) |
|---|---|---|---|---|
| 1x (4 nodes) | 24 | 2x→8 nodes, 4x→16 nodes | — | 16 nodes at 4x |
| 2x (8 nodes) | 12 | 4x→16 nodes | 1x→4 nodes | 16 nodes at 4x |
| 4x (16 nodes) | 6 | — | 2x→8 nodes, 1x→4 nodes | Already at 4x |

Starting at 2x is recommended as a middle ground — supports both folding and unfolding.

**What Changes After Unfold:**
- More nodes, fewer AMPs per node
- More CPU, memory, I/O bandwidth per AMP
- Same total AMP count, same total storage volume
- Each new node gets 2 parsing engines automatically
- More sessions can be supported

**What Does NOT Change:**
- Total number of AMPs
- Total number of AMP worker tasks
- Total storage volume

### 4.2 Unit of Migration — The Subpool

In the public cloud, the migration unit is a **subpool**:
- Each 1x node has 8 subpools
- Each subpool services 3 AMPs
- Each subpool has an associated TVS vproc
- During unfold, EBS volumes are detached from original nodes and reattached to new nodes

### 4.3 Components That Migrate

| Component | Before (1x, 2 nodes) | After (2x, 4 nodes) |
|---|---|---|
| AMPs/node | 24 | 12 |
| Subpools/node | 8 | 4 |
| TVS vprocs/node | 8 | 4 |
| IP addresses/node | 4 | 2 |
| Parsing engines/node | 2 | 2 |

**Unfold-Ready Configuration:**
Specify "Folding/unfolding Enabled" at launch to pre-configure 4 IPs and 8 TVS vprocs per node. This avoids needing to add these components during unfold.

### 4.4 Timing and Process

**Unfold Process:**
1. Stop the instance
2. Issue unfold command with target level (2x or 4x)
3. New nodes provisioned automatically
4. EBS volumes detached/reattached; GDO records updated
5. AMPs, TVS vprocs, IP addresses migrated
6. 2 PEs defined on each new node
7. Instance relaunched

| Operation | AWS | Azure |
|---|---|---|
| Unfold | 15–20 minutes | 25–30 minutes |
| Fold | 10–15 minutes | 20–25 minutes |

**Fold Process:**
- Reverses all unfold operations
- AMPs, TVS vprocs, IPs returned to original nodes
- PEs on folded nodes deleted
- Provisioned nodes released

> Source: TDN0009703 §4

### 4.5 Performance Impact

Internal testing on a 4-node AWS instance (80 active sessions, 20 AMPs/node):

| Configuration | Elapsed Time | Improvement |
|---|---|---|
| 4 nodes (1x) | 4,365 sec | Baseline |
| 8 nodes (2x) | 2,193 sec | ~2× faster |
| 16 nodes (4x) | 1,141 sec | ~3.8× faster |

- Best fit for CPU-bottlenecked systems
- Near-linear physical I/O increases from additional storage bandwidth
- Linear improvement not guaranteed — depends on bottleneck type and workload

> Source: TDN0009703 §4.5

---

## 5. Folding/Unfolding on IntelliFlex (On-Premises)

### 5.1 Configuration and COD Nodes

IntelliFlex uses **COD nodes** (passive nodes) pre-installed in each clique:

```
Configuration notation: Cliques(ActiveNodes + HSN + CODNodes)
Example: 4(6+1+3)
  4 cliques
  6 active nodes per clique
  1 hot standby node per clique
  3 COD nodes per clique
```

**Unfold examples from 4(6+1+3):**
- `4(8+1+1)` — unfold 2 COD nodes per clique
- `4(9+1+0)` — unfold all 3 COD nodes per clique

All cliques must maintain identical configuration after unfold.

### 5.2 Components Migrated

During unfold, these components are reassigned (not physically moved):

| Component | 6 Active Nodes | After Unfold to 9 Nodes |
|---|---|---|
| AMPs/node | 40 | ~27 (slight variance acceptable) |
| TVS vprocs/node | 3 | 2 (some nodes may have 1) |
| Parsing engines | Pre-installed on COD nodes (offline) | Come online |

### 5.3 Unfold-Ready Preparation

- PEs must be pre-defined on COD nodes at installation (offline until unfold)
- All IntelliFlex systems configured with 3 TVS vprocs per node
- TVS vprocs migrate with their associated AMPs during unfold
- Slight AMP/TVS imbalance between nodes after unfold is normal and acceptable

### 5.4 Limitations

| Constraint | Details |
|---|---|
| Max expansion | 3× original nodes (limited by 3 TVS vprocs per original node) |
| Max nodes per clique | 12 (excluding HSN) |
| Unfold granularity | By node (any number of COD nodes) |
| Outage required | Yes — restart, typically minutes |
| HSN preserved | Always — never used as COD node |
| Max unfold-ready config | `4+1+8` (4 active, 1 HSN, 8 COD) |

**Best for I/O-bound systems:** More nodes → more memory → more FSG cache → better cache hit ratio → improved I/O bandwidth.

> Source: TDN0009703 §5

---

## 6. IntelliCloud Configurations

### 6.1 IntelliCloud on Public Cloud

Identical to direct public cloud fold/unfold (2x and 4x), except managed by IntelliCloud — customer does not issue commands.

### 6.2 IntelliCloud on IntelliBase

Does not support folding/unfolding. Each IntelliBase node has integrated internal storage, so nodes cannot be added without adding storage.

### 6.3 IntelliCloud on IntelliFlex

Uses a combination of three elastic techniques at predefined TCore levels:
1. AMP migration (activate/deactivate COD nodes)
2. WM COD adjustment (CPU and I/O)
3. DS COD adjustment (storage, small instances only)

**Small Instance (2+1 configuration):**

| Level Example | TCore | Active Nodes | WM COD | DS COD |
|---|---|---|---|---|
| Entry | 53 | 2 of 3 | 75% | 50% |
| Mid | 80 | 3 of 3 | 88% | 100% |
| Maximum | 90 | 3 of 3 | 100% | 100% |

**Medium Instance (4+2 configuration):**

| Level Example | TCore | Active Nodes | WM COD | DS COD |
|---|---|---|---|---|
| Entry | 97 | 4 of 6 | 100% | 100% |
| Maximum | 111 | 6 of 6 | 100% | 100% |

**Key Points:**
- Step-ups between levels are 7-TCore or 10-TCore
- All hardware for maximum level installed at initial deployment
- Cannot mix small and medium instances in one system
- Multiple instances of same size can be combined (each = one clique)
- Restart required for fold/unfold
- Must remove data before reducing DS COD percentage

> Source: TDN0009703 §6

---

## 7. Resizing (Scale-Up)

Resizing replaces current nodes with more powerful instances — a different approach than scale-out (unfold).

### 7.1 Public Cloud Resizing

**Process:**
1. Stop the instance
2. Redefine the instance type (single command)
3. Storage temporarily disconnected and reconnected to replacement nodes
4. Restart — typically ~10 minutes

**What stays the same:** AMPs, AMP worker tasks, IP connections, storage volume

**Restrictions:**
- Not available with BYOL (Bring Your Own License)
- Must use supported instance types
- Not available on IntelliFlex on-premises

> Source: TDN0009703 §7.1

---

## 8. Storage Expansion

### 8.1 Public Cloud Storage Expansion

- Only available on 1x scaling factor (24 AMPs/node, 24 storage volumes/node)
- Requires stopping the database, running expansion command, relaunching
- Available on Marketplace hourly rates and IntelliCloud (not BYOL)
- **One-way only** — cannot reduce storage after expansion (cloud provider limitation)

### 8.2 IntelliFlex Storage Expansion

**Option A: Add drives to existing arrays**
- Simplest approach if array slots available
- Must have room across all AMP arrays
- Can be planned at initial installation

**Option B: Add new arrays**
- Two arrays of same type per clique
- Depends on cabinet slot availability

### 8.3 Rebalancing After Expansion

After adding physical storage, the **Rebalancer utility** must be run:
- Moves cylinders from old drives to new drives for even free-space distribution
- Cylinder moves are fast — no row redistribution or decompression needed
- Without rebalancing, all new allocations go to empty drives, creating I/O hotspots
- Typically takes up to an hour; system is down during rebalancing

**DS COD vs Storage Expansion:**
- DS COD: no rebalancing needed, simple restart, bi-directional
- Storage expansion: rebalancing required, longer outage, one-way (hard to reduce)

> Source: TDN0009703 §7.2

---

## 9. MAPS — Multi-Dimensional Expansion

MAPS addresses **all** growth dimensions simultaneously: nodes, AMPs, memory, storage, I/O bandwidth, and parsing engines.

### 9.1 How MAPS Works

**Before MAPS:** Only one hash map existed. Adding nodes required Reconfig — redistributing all data using a new hash map. Took hours or days.

**With MAPS:** Multiple hash maps coexist.
1. New nodes added and configured during a short outage
2. New hash map created that includes old and new AMPs
3. No data moved during the outage — system comes up quickly
4. Tables moved to new map in background over time
5. Data fully readable during background migration

```sql
-- Check hash map assignments
SELECT DatabaseName, TableName, MapName
FROM DBC.TablesV
WHERE DatabaseName = 'mydb'
ORDER BY TableName;
```

### 9.2 MAPS vs Other Options

| Dimension | Unfold | Storage Expansion | MAPS |
|---|---|---|---|
| CPU/Memory | Yes | No | Yes |
| AMPs | No | No | Yes |
| Storage | No | Yes | Yes |
| I/O Bandwidth | Yes | Limited | Yes |
| Parsing Engines | Yes | No | Yes |
| Data Movement | None | Rebalance | Background |
| Downtime | Minutes | ~1 hour | Minutes to hours |
| Reversibility | Fold back | Difficult | Possible but complex |

### 9.3 Availability

- All on-premises systems on Teradata Database 16.10+
- IntelliCloud: available when 16.20 is certified
- Not currently on public cloud (AWS, Azure)

> Source: TDN0009703 §7.3

---

## 10. TASM Elastic-Like Capabilities

Workload management features that dynamically reallocate resources across workloads.

### 10.1 Workload Exceptions

Behavior-based rules that auto-demote or abort queries exhibiting anomalies (high CPU, I/O, elapsed time, skew). Exception chains allow progressive demotion: `AdHoc-Short → CPU>10s → AdHoc-Medium → CPU>200s → AdHoc-Long`.

### 10.2 Tactical Exceptions

Automatic exception on Tactical tier workloads: demotes queries exceeding 2 CPU seconds or 200 MB I/O/node to low-priority Timeshare.

### 10.3 Timeshare Decay

Reduces access rate for long-running Timeshare queries at configurable CPU/I/O thresholds. First threshold halves the rate; second threshold quarters it. Decayed rate persists until completion.

### 10.4 Flex Throttles

Releases delayed queries when AMP worker tasks and CPU are underutilized. Self-adjusting — turns off when resource usage rises.

### 10.5 State Changes

- **System events:** Trigger state changes on sustained CPU/AWT thresholds (e.g., CPU ≥ 90% for 10 min). Auto-revert when condition clears.
- **By-workload events:** Monitor workload-specific conditions (CPU skew, arrival rate, queue depth) and trigger state changes.

> Source: TDN0009703 §8

---

## 11. Planning Considerations

### Choosing the Right Elastic Option

| Scenario | Recommended Option |
|---|---|
| Temporary CPU spike (hours/days) | EPOD or Unfold |
| Planned monthly processing surge | WM COD + planned environments |
| Permanent growth, all resources | MAPS |
| Quick instance upgrade | Resizing (cloud only) |
| Storage running low, temporary | DS COD |
| Storage running low, permanent | Storage expansion |
| Dynamic workload prioritization | TASM system events + state changes |

### Combining Elastic Options

IntelliCloud on IntelliFlex demonstrates how options combine:
- WM COD adjusts CPU/I/O availability
- DS COD adjusts storage availability (small instances)
- AMP migration activates COD nodes
- All three coordinated through predefined TCore levels

### Pre-Planning Best Practices

1. **Cloud:** Enable folding/unfolding at instance launch (pre-configures IPs and TVS vprocs)
2. **IntelliFlex:** Order COD nodes and pre-define PEs during initial installation
3. **DS COD:** Install enough storage for projected maximum usage
4. **MAPS:** Available for on-premises when permanent growth is anticipated
5. **TASM:** Define system events, workload exceptions, and flex throttles proactively

> Source: TDN0009703 §9
