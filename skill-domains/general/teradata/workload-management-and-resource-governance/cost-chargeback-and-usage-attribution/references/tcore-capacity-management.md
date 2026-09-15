# TCore Capacity Management Reference

Detailed reference for Teradata TCore capacity models, Capacity on Demand mechanisms, consumption pricing, and metering infrastructure.

> Source: TDN0009960 — Teradata Vantage Capacity and Consumption Models

---

## 1. TCore Definition and Calculation

TCore is a normalized measure of performance potential that provides a constant consumption metric across Teradata's hybrid cloud deployment options. It enables license portability and pricing consistency as customers move their Advanced SQL Engine license between platforms.

The TCore calculation considers:
- The number of CPU cores available on each node
- The I/O throughput available to each core

TCore is not a raw hardware metric — it is an abstracted unit that allows fair comparison across IntelliFlex generations, on-premises deployments, and cloud platforms.

### TCore and Licensing Tiers

| Tier | WM COD | Elastic TCore | Consumption Model |
|---|---|---|---|
| Enterprise | Yes (TASM) | Yes | N/A |
| Advanced | Yes (TIWM) | Yes | N/A |
| VantageCloud as a Service | N/A | N/A | Yes |

> Source: TDN0009960, Sections 1.1, 2.1

---

## 2. Workload Management COD (WM COD)

WM COD restricts the percentage of CPU and I/O available system-wide through Teradata Workload Management software. It is set using Viewpoint Workload Designer and enforced by the SLES 11 operating system's control group hierarchy.

### Configuration

- **Range:** 75%–100% in 1% increments (current platforms)
- **Change method:** Viewpoint Workload Designer — no restart required, takes effect immediately
- **Enforcement scope:** All database workloads; system tasks (OS, gateway) are not restricted

### COD Configuration Packages

Teradata Customer Services installs hardware configuration packages that set a tamper-resistant hard ceiling. The packages support only 12.5-point intervals: 87.5%, 75%, 62.5%, 50%. The administrator then sets WM COD to the contracted percentage within Viewpoint.

Example: A contract for 80% WM COD uses an 88% (87.5% rounded up) package ceiling. The administrator reduces WM COD from 88% to 80% in Viewpoint.

### CPU Enforcement Mechanism

The SLES 11 OS places a CPU hard limit at the top of the Teradata priority hierarchy, above all virtual partitions and workloads. Enforcement uses two internal parameters:

1. **Enforcement period** — a prescribed amount of clock time (e.g., 1 second)
2. **Quota** — the percent of the enforcement period where database work can run on each CPU

When the quota is reached within a period, no database work runs until the next period starts. The enforcement period is determined internally and is not user-tunable.

### I/O Enforcement Mechanism

I/O WM COD restricts bandwidth on each disk device independently. The TDSched module costs each I/O request based on whether it is a read or write and its estimated size. When COD-allowable bandwidth is consumed within an enforcement interval for a disk, I/O requests stop until the next interval. Only physical I/O is restricted — cache reads are not affected.

### ResUsage COD Fields

The following columns appear in ResUsageSPMA and related tables:

| Column | Description | Disabled Value |
|---|---|---|
| `WM_COD_CPU` | WM CPU COD in tenths of a percent (e.g., 750 = 75%) | 1000 |
| `WM_COD_IO` | WM I/O COD in whole percent (e.g., 75 = 75%) | 100 |
| `PM_COD_CPU` | Platform Metering CPU COD in tenths of a percent | 1000 |
| `PM_COD_IO` | Platform Metering I/O COD in whole percent | 100 |

Under EPOD, `PM_COD_XX` fields report 100% while `WM_COD_XX` fields report the active WM COD values. The PM COD fields can be ignored when using EPOD.

```sql
-- Query current COD settings
SELECT TheDate, TheTime, NodeID,
       WM_COD_CPU / 10.0 AS WM_CPU_Pct,
       WM_COD_IO AS WM_IO_Pct,
       PM_COD_CPU / 10.0 AS PM_CPU_Pct,
       PM_COD_IO AS PM_IO_Pct
FROM DBC.ResUsageSPMA
WHERE TheDate = CURRENT_DATE
ORDER BY TheTime DESC;
```

> Source: TDN0009960, Sections 2.1–2.2.2

---

## 3. Elastic Performance on Demand (EPOD)

EPOD is a pay-per-use billing model for TCore capacity on demand. It is available on IntelliFlex platforms and VantageCloud with Enterprise or Advanced tier licenses.

### How EPOD Works

1. Customer purchases a baseline TCore level (e.g., 63% of capacity)
2. A portion above the baseline is designated as elastic (e.g., 12%)
3. Optionally, remaining capacity is unavailable until a new contract (e.g., 25%)
4. The administrator releases elastic capacity by raising WM COD settings in Viewpoint
5. Usage above the baseline is billed based on hourly CPU utilization from ResUsageSPMA

### Two EPOD Configurations

**Configuration A — With Hard Ceiling:**
- 63% pre-paid (baseline)
- 12% elastic
- 25% unavailable (hard ceiling at 75% via PM COD packages)

**Configuration B — Fully Elastic:**
- 60% pre-paid (baseline)
- 40% elastic (no hard ceiling, all remaining capacity is elastic)

### Monitoring EPOD Usage

The Viewpoint Elastic Performance portlet aggregates CPU usage by hour from ResUsageSPMA. Usage within the elastic band is highlighted and billed accordingly.

> Source: TDN0009960, Sections 2.2–2.2.3

---

## 4. Disk Storage COD (DS COD)

DS COD limits available disk space by having TVS hide cylinders from each AMP's file system. It is only available on on-premises systems.

### TVAM DS COD Characteristics

- Activated in **5% increments** up or down
- Requires **CS installation** of storage capacity configuration packages (tamper-resistant)
- Requires a **planned outage** to quiesce the system for each change
- Can be set independently across SSD and HDD storage classes
- **Never restrict fast storage (SSD)** on hybrid systems
- No performance impact has been reported after changes
- Verify adequate free space in DBC before reducing storage capacity

### Effect on File System

When DS COD is applied, TVS marks a percentage of cylinders on each AMP as unavailable. On hybrid storage, TVS removes space from slow and medium storage only. Changes add or remove space from the DBC database; user space allocations are unaffected.

> Source: TDN0009960, Sections 2.3–2.3.3

---

## 5. TCore Activation Levels

TCore Activation Levels reduce maximum available TCore on IntelliFlex 2.1 platforms by disabling CPU cores in hardware. Both CPU seconds and I/O bandwidth are proportionally reduced.

### Four Activation Levels

| Level | Active Cores | TIER_FACTOR | Example TCore (72-core node) |
|---|---|---|---|
| Level 1 | 100% | 100 | 102 |
| Level 2 | 77% | 77 | 79 |
| Level 3 | 55% | 55 | 56 |
| Level 4 | 33% | 33 | 34 |

### Combining with WM COD

WM COD can be layered for finer granularity:

| WM COD | Level 1 TCore | Level 2 TCore | Level 3 TCore | Level 4 TCore |
|---|---|---|---|---|
| 100% | 102 | 79 | 56 | 34 |
| 88% | 90 | 70 | 49 | 30 |
| 75% | 77 | 59 | 42 | 26 |

Effective TCore = Activation Level TCore × WM COD %.

### Changing TCore Activation Levels

Requires a Customer Services engagement and a maintenance window:

1. Set maintenance window
2. Take database down
3. Run "TCore-activation" tool on each node
4. Reboot each node
5. Verify new Activation Level and throttle settings
6. Bring up the Advanced SQL Engine nodes

### Impact on Monitoring

**DBQL:** CPU seconds per query remain similar across levels (a CPU second accomplishes the same work). Elapsed time increases at lower levels due to fewer available CPU seconds.

**ResUsage:** Fewer total CPU seconds per logging interval at lower levels. 100% CPU utilization is reported when all available cores are fully consumed, regardless of activation level.

### ResUsage Validation

```sql
-- Validate TCore Activation Level
SELECT TheDate, TheTime, NodeID,
       NCPUs,
       TIER_FACTOR,
       WM_COD_CPU / 10.0 AS WM_CPU_Pct,
       ((CPUUServ + CPUUExec) / NCPUs) / Secs AS CPUBusyPct
FROM DBC.ResUsageSPMA
WHERE TheDate = CURRENT_DATE
ORDER BY TheTime DESC;
```

| ResUsage Column | Reports |
|---|---|
| `TIER_FACTOR` | Percentage of total system capability at current level (100, 77, 55, or 33) |
| `NCPUs` | Count of active CPU cores on the node |

### Query Plan Considerations

- Levels 1, 2, 3: AMPsPerCPU remains 1 — **no plan changes**
- Level 4: Active cores may be fewer than AMPs, causing AMPsPerCPU > 1 — **possible plan changes**
- WM COD on top of any level does not affect optimizer costing

### Limitations

- Does not cover Machine Learning Engine or Graph Engine
- Gaps in supportable TCore values between levels
- Requires restart and CS involvement for each change

> Source: TDN0009960, Sections 3.0–3.3

---

## 6. Elastic TCore

Elastic TCore uses CPU affinity (software) to restrict database tasks to a subset of CPU cores. All physical cores remain active. Available on IntelliFlex 2.1+ with Advanced SQL Engine 16.20 FU2 (Vantage 1.1).

### How It Works

The Advanced SQL Engine manipulates CPU affinity of tasks supporting user queries. Database work is confined to a designated subset of CPU cores. Non-database work (OS, gateway) can use all cores. No hardware changes are involved.

### Benefits Over TCore Activation Levels

| Feature | TCore Activation Levels | Elastic TCore |
|---|---|---|
| Change method | Restart + CS | Immediate, no restart |
| TCore granularity | Four levels + WM COD | Any individual TCore value |
| Enforcement scope | All CPU (database + system) | Database CPU only |
| WM COD requirement | Required for fine-tuning | Not required |
| Query plan risk | Level 4 | None |

### Control Options

**Customer-Controlled (default):** Customer executes SQL commands to increase or decrease TCore at any time. No Teradata support involvement. Best for sites with volatile resource needs.

**Teradata-Controlled:** CS personnel make all TCore changes at the customer's request. Best for sites that want planned, deliberate changes.

### Transitioning from TCore Activation Levels

When upgrading to Vantage 1.1:
1. Existing WM COD percentage remains in effect
2. Same number of CPU cores enabled via software instead of hardware
3. Recommended: eliminate WM COD for pricing and increase Elastic TCore to equivalent total TCore
4. WM COD can still be used voluntarily for workload management purposes

### ResUsage Monitoring with Elastic TCore

`NCPUs` always reports 100% of physical cores (software changes are not visible to resource usage subsystem). Use `TDEnabledCPUs` instead:

```sql
-- Correct CPU utilization calculation for Elastic TCore
SELECT TheDate, TheTime, NodeID,
       NCPUs,
       TDEnabledCPUs,
       CAST(TDEnabledCPUs AS FLOAT) / NCPUs AS PctEnabledCPUs,
       ((CPUUServ + CPUUExec) / TDEnabledCPUs) / Secs AS CPUBusyPct
FROM DBC.ResUsageSPMA
WHERE TheDate = CURRENT_DATE
ORDER BY TheTime DESC;
```

| Field | Source | Reports |
|---|---|---|
| `NCPUs` | Hardware | Total physical cores — does NOT change with Elastic TCore |
| `TDEnabledCPUs` | Software | Cores available for database work — changes with Elastic TCore |

### Workload Hard Limits Under Elastic TCore

Workload hard limit enforcement currently uses `NCPUs`, which can cause over-allocation when Elastic TCore restricts available cores. For example, a 20% hard limit with 55% of cores active allows the workload ~36% of available CPU.

**Workarounds:**
1. Replace `NCPUs` with `TDEnabledCPUs` in ResUsage views and SQL
2. Reduce hard limit percentage proportionally (e.g., 11% instead of 20% when at ~55% TCore)

### System vs. Database CPU Separation

Under Elastic TCore, the OS tends to schedule system processes on the idle (non-database) cores. This separation is generally beneficial. When TCore is increased to 100%, both types of work share all cores, which can cause:
- Slight competition between system and database tasks at saturation
- ResUsage CPU may not increase as much as expected (system work was previously "free")

### Limitations

- IntelliFlex platforms only
- Does not cover Machine Learning Engine or Graph Engine
- `TDEnabledCPUs` not yet in ResUsageSPS (workload-level) table

> Source: TDN0009960, Sections 4.0–4.6

---

## 7. Vantage Consumption Model

The Consumption Model prices based on actual workload consumption rather than installed capacity. Runs only on VantageCloud Delivered as a Service (AWS, Azure).

### Pricing Components

1. **Vantage Units** — Logical I/O consumed by all queries and operations
2. **TB of Customer Data Space** — Provisioned storage (fixed cost)

### What Counts as Logical I/O

Logical I/O is any request by the execution engine to read or write data to base tables or intermediate spool files. Collected from each AMP for each step of execution.

**Included in Vantage Units:**
- All Advanced SQL Engine queries (including TDREST)
- ML Engine and Graph Engine queries (Vantage 1.1)
- Viewpoint and system monitoring (data collectors, PDCR, Stats Manager)
- Load utilities (MultiLoad, FastLoad)
- Backup/restore and data migration (NPARC, DTU)
- Manually or WM-aborted queries
- Compression/decompression overhead
- DBQL metrics collection and insertion

**Excluded from Vantage Units:**
- Consumption collector queries (vcmuser)
- Movement of usage data from DICT to PDCR
- System-aborted queries (database error code returned)
- ResUsage metrics gathering
- TVS background tasks

### DBQL Logging Under Consumption

DBQL logging is automatically enabled for all users via `BEGIN QUERY LOGGING FOR ALL`. Only DBQLogTbl and UtilityInfo tables are populated. Users **cannot** create additional DBQL rules that narrow scope. THRESHOLD and SUMMARY logging are disallowed.

**Impact:** Tactical applications cannot use threshold logging to reduce overhead. Test SLA-sensitive applications thoroughly before setting elapsed time expectations.

### Controlling Consumption Costs

**Physical Design Optimization:**
- Use partitioning to enable partition elimination and reduce scanned data
- Create secondary indexes and join indexes to narrow data access
- Maintain current statistics on join columns for complex queries
- Avoid full table scans on large tables
- Avoid product joins that produce large intermediate spools

**Workload Management:**
- Less critical than capacity models since cost is per-I/O, not per-CPU-hour
- Consider throttling: Native Object Store reads, SCRIPT/R table operators, Data Lab workloads

**Consumption Alerts:**
- Configure Vantage Unit thresholds via Consumption Dashboard → Site → Alarm settings
- Email alerts notify administrators when consumption hits specified thresholds

### Consumption Telemetry

Teradata installs a `VODUSER` account with SELECT access to consumption telemetry:

```sql
-- Views accessible to VODUSER
-- pdcrinfo.vod_dbqlogtbl
-- pdcrinfo.vod_dbqlutilitytbl
-- pdcrinfo.vod_tables
-- pdcrinfo.resusagespma_hst
-- dbc.tablesizev
```

DBQL and PDCR logs must retain a minimum of **four months** of current data.

### Reporting by Department

1. Enable the Viewpoint PDCR portlet
2. Run the daily job to populate `PdcrData.UserInfo`
3. Update the `Department` column for each user
4. Maintain as users change departments or are added

> Source: TDN0009960, Sections 5.0–5.4

---

## 8. Model Comparison Summary

| Aspect | TCore Activation Levels | Elastic TCore | Consumption Model |
|---|---|---|---|
| Platform | IntelliFlex 2.1 (on-prem/managed cloud) | IntelliFlex 2.1+ | VantageCloud as a Service |
| Pricing metric | TCore | TCore | Vantage Units + TB |
| What is restricted | CPU + I/O (all work) | CPU + I/O (database only) | Nothing restricted |
| Change method | Restart + CS | Software, no restart | N/A |
| Self-service | No | Yes (customer-controlled option) | Managed by Teradata |
| WM COD role | Required for fine-tuning | Optional | Optional |
| Query plan risk | Level 4 only | None | None |
| ML/Graph coverage | No | No | Yes |
| Direction | Being phased out | Recommended replacement | Initial cloud offering |

> Source: TDN0009960, Section 6.4

---

## 9. Key Abbreviations

| Term | Definition |
|---|---|
| **COD** | Capacity on Demand — technologies that restrict access to resources |
| **DS COD** | Disk Storage COD — limits disk space via TVS/TVAM |
| **EPOD** | Elastic Performance on Demand — pay-per-use billing on WM COD |
| **TCore** | Normalized performance measure considering CPU cores and I/O per core |
| **TVAM** | Teradata Virtual Allocation Manager — tool for storage optimization |
| **TVS** | Teradata Virtual Storage — abstraction layer between AMPs and physical disk |
| **WM COD** | Workload Management COD — CPU/I/O restriction via Priority Scheduler |
| **VODUSER** | Consumption telemetry collection account |
| **Vantage Units** | Logical I/O–based pricing unit for the Consumption Model |

> Source: TDN0009960, Abbreviations and Terms
