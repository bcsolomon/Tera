---
name: teradata-capacity-consumption
description: 'Understand and manage Teradata consumption-based pricing, TCore capacity models, and usage metering. Use when configuring capacity limits, monitoring TCore consumption, understanding consumption tiers and pricing models, or planning capacity for VantageCloud deployments.'
metadata:
  author: teradata-expert
  version: "1.0"
---

# Teradata Capacity and Consumption Models

## When to Use

- Understanding TCore as a capacity metric and how it is calculated
- Choosing between capacity-based (TCore) and consumption-based (Vantage Units) pricing
- Configuring or changing Workload Management COD (WM COD) limits
- Monitoring CPU and I/O usage under TCore Activation Levels or Elastic TCore
- Setting up consumption alerts to manage costs
- Interpreting ResUsage and DBQL metrics under different capacity models
- Planning capacity for VantageCloud or IntelliFlex deployments
- Transitioning from TCore Activation Levels to Elastic TCore

## Core Concepts

### TCore

TCore is a measure of performance potential that provides a consistent consumption metric across hybrid cloud deployment options. The TCore calculation considers the number of CPU cores available and the I/O available to each core. TCore enables license portability and pricing consistency as customers move workloads between platforms.

### Capacity on Demand (COD)

COD is a grouping of technologies, each imposing a limiting effect on one or a subset of system resources (CPU, I/O, disk). COD constrains a percentage of already-installed resources, reducing initial cost with the ability to release more capacity as business needs grow.

### Three Capacity/Consumption Models

| Model | Metric | Platform | Change Method |
|---|---|---|---|
| **TCore Activation Levels** | TCore | IntelliFlex 2.1 | Restart required (CS engagement) |
| **Elastic TCore** | TCore | IntelliFlex 2.1+ | Software-only, no restart |
| **Consumption Model** | Vantage Units + TB storage | VantageCloud (as a Service) | Usage-based, no restrictions |

### Key Terms

| Term | Definition |
|---|---|
| **COD** | Capacity on Demand — technologies that restrict access to installed resources |
| **TCore** | Normalized performance measure considering CPU cores and I/O per core |
| **Vantage Units** | Logical I/O–based pricing unit for the Consumption Model |
| **EPOD** | Elastic Performance on Demand — pay-per-use billing on WM COD |
| **VODUSER** | System account for consumption telemetry collection |

### Workload Management COD (WM COD)

WM COD restricts CPU and I/O at the system level via Priority Scheduler software. It is set in 1% increments between 75% and 100% using Viewpoint Workload Designer. Changes take effect immediately — no restart required. WM COD applies only to database work; system tasks (OS, gateway) always have full hardware access.

CPU enforcement uses a quota within a timing period — when the quota of allowed CPU time is consumed within a period, all database work pauses until the next period starts. I/O enforcement restricts bandwidth per disk device independently via the TDSched module; only physical I/O is affected (cache reads are not restricted).

### EPOD (Elastic Performance on Demand)

EPOD is a pay-per-use billing model layered on WM COD. The customer purchases a baseline TCore level and can temporarily expand into elastic capacity by raising WM COD settings in Viewpoint. The Elastic Performance portlet reports hourly elastic CPU usage from ResUsageSPMA. EPOD supports WM COD, TCore Activation Levels, and Elastic TCore.

### Disk Storage COD (DS COD)

DS COD limits available disk space by having TVS/TVAM hide cylinders from each AMP's file system. Available only on on-premises systems. Activated in 5% increments; requires a planned outage for each change. On hybrid storage, space is only removed from slow and medium storage — never from fast (SSD) storage.

### TCore Activation Levels

Four hardware-based levels that disable CPU cores on IntelliFlex 2.1 nodes:

| Level | Active Cores | TIER_FACTOR |
|---|---|---|
| Level 1 | 100% | 100 |
| Level 2 | 77% | 77 |
| Level 3 | 55% | 55 |
| Level 4 | 33% | 33 |

WM COD can be layered on top for finer granularity. Effective TCore = Activation Level TCore × WM COD %.

### Elastic TCore

Uses CPU affinity (software) to restrict database tasks to a subset of cores — all cores remain physically active. Benefits: no restart, finer granularity (any TCore value), customer-controlled or Teradata-controlled changes. No query plan changes occur because hardware infrastructure appears unchanged to the optimizer. Available on IntelliFlex 2.1+ with Advanced SQL Engine 16.20 FU2.

### Vantage Consumption Model

Pricing based on actual Logical I/O usage (Vantage Units) plus provisioned storage (TB). No capacity restrictions are imposed. All Advanced SQL Engine queries, load utilities, backups, and monitoring activity count toward consumption. Available only on VantageCloud Delivered as a Service (AWS, Azure).

**Included in Vantage Units:** All SQL Engine queries, ML/Graph Engine queries, Viewpoint/monitoring, load utilities (MultiLoad, FastLoad), backup/restore, aborted queries, compression overhead, DBQL activity.

**Excluded:** Consumption collector queries (vcmuser), DICT-to-PDCR movement, system-aborted queries, ResUsage gathering, TVS background tasks.

## Procedure: Monitor Capacity via ResUsage

```sql
-- Check TCore Activation Level and WM COD settings
SELECT TheDate, TheTime, NodeID, NCPUs,
       WM_COD_CPU / 10.0 AS WM_CPU_Pct,
       WM_COD_IO AS WM_IO_Pct,
       TIER_FACTOR
FROM DBC.ResUsageSPMA
WHERE TheDate = CURRENT_DATE
ORDER BY TheTime DESC;

-- Monitor Elastic TCore — use TDEnabledCPUs instead of NCPUs
SELECT TheDate, TheTime, NodeID,
       NCPUs,
       TDEnabledCPUs,
       CAST(TDEnabledCPUs AS FLOAT) / NCPUs AS PctTDEnabledCPUs,
       ((CPUUServ + CPUUExec) / TDEnabledCPUs) / Secs AS CPUBusyPct
FROM DBC.ResUsageSPMA
WHERE TheDate = CURRENT_DATE
ORDER BY TheTime DESC;
```

> Source: TDN0009960, Sections 3.1–4.5

## Procedure: Check EPOD COD Fields

```sql
-- Check EPOD-relevant COD fields
SELECT TheDate, TheTime, NodeID,
       WM_COD_CPU / 10.0 AS WM_CPU_Pct,
       WM_COD_IO AS WM_IO_Pct,
       PM_COD_CPU / 10.0 AS PM_CPU_Pct,
       PM_COD_IO AS PM_IO_Pct
FROM DBC.ResUsageSPMA
WHERE TheDate = CURRENT_DATE
ORDER BY TheTime DESC;
-- Note: PM_COD_XX reports 100% under EPOD; focus on WM_COD_XX values
```

> Source: TDN0009960, Sections 2.2–2.2.3

## Procedure: Monitor Consumption (Vantage Units)

Consumption telemetry uses VODUSER with SELECT access to:
- `pdcrinfo.vod_dbqlogtbl`
- `pdcrinfo.vod_dbqlutilitytbl`
- `pdcrinfo.vod_tables`
- `pdcrinfo.resusagespma_hst`
- `dbc.tablesizev`

DBQL and PDCR logs must retain a minimum of **four months** of current data.

Set up consumption alerts via the Consumption Dashboard: navigate to Site → Alarm settings to configure Vantage Unit thresholds and email notifications.

> Source: TDN0009960, Sections 5.2.1, 5.4

## Procedure: Report Consumption by Department

1. Enable and configure the Viewpoint PDCR portlet
2. Run the daily PDCR job to populate `PdcrData.UserInfo`
3. Update the `Department` column for each user row in `PdcrData.UserInfo`
4. Maintain the table as users change departments or are added

> Source: TDN0009960, Section 5.3.2

## Controlling Consumption Costs

- **Physical design:** Use partitioning, secondary indexes, and join indexes to reduce Logical I/O
- **Statistics:** Keep statistics current to enable optimal join plans (see Automated Statistics Management)
- **Avoid:** Full table scans on large tables, product joins producing large intermediate spools
- **Workload management:** Consider throttling Native Object Store reads, SCRIPT/R table operators, and Data Lab workloads
- **Alerts:** Configure Vantage Unit alerts to detect cost spikes early
- **DBQL restrictions:** Under consumption pricing, THRESHOLD and SUMMARY logging are disallowed — test tactical application SLAs thoroughly

> Source: TDN0009960, Sections 5.2, 5.3.1

## Procedure: Transition from TCore Activation Levels to Elastic TCore

1. Upgrade to Vantage 1.1 on IntelliFlex 2.1+
2. Existing WM COD percentage remains in effect automatically
3. Same number of CPU cores enabled via software instead of hardware
4. Recommended: eliminate WM COD for pricing, increase Elastic TCore to equivalent total TCore
5. WM COD can still be used voluntarily for workload management purposes
6. Validate using `TDEnabledCPUs` in ResUsageSPMA

> Source: TDN0009960, Section 4.4

## Disk Storage COD (DS COD)

DS COD limits available disk space by hiding cylinders from AMP file systems via TVS/TVAM. Available on on-premises systems only. Activated in 5% increments; requires a planned outage for each change. DS COD does not restrict fast storage (SSD) on hybrid systems. Verify adequate free space in DBC before reducing storage capacity.

> Source: TDN0009960, Sections 2.3–2.3.3

## Key Differences

| Aspect | TCore Activation Levels | Elastic TCore | Consumption Model |
|---|---|---|---|
| Pricing unit | TCore | TCore | Vantage Units + TB |
| Restricts | CPU + I/O (all work) | CPU + I/O (database only) | Nothing |
| Change method | Restart + CS | Software, no restart | N/A |
| Query plan risk | Level 4 only | None | None |
| WM COD role | Required for fine-tuning | Optional | Optional |
| ML/Graph Engine | Not covered | Not covered | Included |

## Troubleshooting

| Symptom | Cause | Resolution |
|---|---|---|
| CPU utilization exceeds WM COD % in ResUsage | System CPU (OS, gateway) is not restricted by WM COD | Expected behavior; only database CPU is capped |
| NCPUs unchanged after Elastic TCore change | NCPUs shows physical cores; use TDEnabledCPUs instead | Query TDEnabledCPUs from ResUsageSPMA |
| Query plans change after TCore level change | Level 4 can alter AMPsPerCPU ratio | Only expected at Level 4; Levels 1–3 maintain AMPsPerCPU=1 |
| Workload hard limit over-allocates under Elastic TCore | Enforcement uses NCPUs not TDEnabledCPUs | Reduce hard limit % proportionally or update views to use TDEnabledCPUs |
| Unexpected consumption costs | Uncontrolled NOS reads, large ad-hoc queries | Set up Vantage Unit alerts; apply WM throttles |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-capacity-consumption", path="references/FILENAME")` — do NOT call `list`.

- [TCore Capacity Management Reference](references/tcore-capacity-management.md) — detailed TCore definitions, COD mechanisms, metering views, consumption management
