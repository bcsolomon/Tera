# Statistics Collection Deep Dive

## COLLECT STATISTICS — Full Syntax

```sql
COLLECT [SUMMARY] STATISTICS
    [USING option [AND option]...]
    {  COLUMN expr [[AS] stats_name]
     | COLUMN (expr [, expr]) [[AS] stats_name]
     | INDEX index_name
     | INDEX (col_list)
    }
    [, ...]
    ON [TEMPORARY] [database_name.]table_name
    [FROM [source_database_name.]source_table_name];
```

## USING Options — Complete Reference

### SAMPLE Options

| Option | Description | When to Use |
|---|---|---|
| `SAMPLE` | System-determined sample % | Default recommendation for large tables |
| `SYSTEM SAMPLE` | Same as SAMPLE | Synonym |
| `SAMPLE n PERCENT` | User-specified (2–100%) | When you need specific coverage |
| `NO SAMPLE` | Force full collection (100%) | When precision required |
| `SYSTEM SAMPLE PERCENT` | Revert to system default | Reset previously overridden sample |

System sample starts at 100% (first collection), then auto-downgrades if: column characteristics are predictable, history records exist (≥30 days), and usage is summary-only.

**Never downgraded:** Small tables, skewed columns, columns in partitioning expressions, columns needing detailed histogram usage.

### MAXINTERVALS Options

| Option | Value | Description |
|---|---|---|
| `MAXINTERVALS n` | 0–500 | Number of equal-height intervals |
| `SYSTEM MAXINTERVALS` | N/A | Revert to system default (250) |

Default: **250**. Set 0 for demographics-only (no histogram). Prior to 12.0: max was 200.

### MAXVALUELENGTH Options

| Option | Value | Description |
|---|---|---|
| `MAXVALUELENGTH n` | 1–max column size | Max bytes/chars stored per value |
| `SYSTEM MAXVALUELENGTH` | N/A | Revert to system default |

Default: **25** (bytes for non-char, characters for single-column CHAR/VARCHAR LATIN, Unicode characters for non-LATIN).

```sql
-- Fix truncation for wide columns
-- If first 25 chars of UserName are identical for all users, histogram unreliable
COLLECT STATISTICS USING MAXVALUELENGTH 50 COLUMN UserName ON Users;
```

For multicolumn statistics, MAXVALUELENGTH applies to the concatenated byte length of all columns.

### THRESHOLD Options

| Option | Description |
|---|---|
| `THRESHOLD n PERCENT` | Skip if data changed < n% |
| `THRESHOLD n DAYS` | Skip if collected < n days ago |
| `SYSTEM THRESHOLD` | System-determined change threshold |
| `NO THRESHOLD` | Always recollect, never skip |
| `NO THRESHOLD PERCENT` | Disable change threshold |
| `NO THRESHOLD DAYS` | Disable time threshold |
| `SYSTEM THRESHOLD PERCENT` | System-determined change threshold |
| `SYSTEM THRESHOLD DAYS` | System-determined time threshold |

Combine with AND: `USING THRESHOLD 10 PERCENT AND THRESHOLD 15 DAYS`

**Skip logic:** Recollection skipped only if **both** time-based AND change-based thresholds evaluate as "below threshold."

**FOR CURRENT:** Override threshold for current statement only (don't save):
```sql
COLLECT STATISTICS USING NO THRESHOLD FOR CURRENT
    COLUMN order_date ON Orders;
```

### ThresholdSignature in DBC.StatsTbl

| Setting | Signature | Meaning |
|---|---|---|
| None | NULL | Falls back to DBS Control |
| `SYSTEM THRESHOLD` | `SCTnnnn.nnSTTnnnn` | System change + system time |
| `THRESHOLD 10 PERCENT` | `UCT0010.00STTnnnn` | User 10% change, system time |
| `NO THRESHOLD` | `UCTnoneþþþUTTnone` | Never skip |

### Global Threshold DBS Control Settings

| Field | Default | Description |
|---|---|---|
| `DefaultTimeThreshold` | 0 | Default time threshold (days). 0=disabled |
| `DefaultUserChangeThreshold` | 0 | Default change %. 0=disabled |
| `SysChangeThresholdOption` | 0 | 0/1=with DBQL. 2=without DBQL. 3=disabled |
| `SysSampleOption` | 0 | 0/1=system sample up to 100%. 2=always full |

---

## Collection Performance Optimizations

### Rollup Aggregations

When single-column and multicolumn stats on same columns collected together, multicolumn aggregation is rolled up to produce single-column stats — avoids rereading the base table:

```sql
COLLECT STATISTICS
    COLUMN (corp_cust_nbr, ctry_cd),
    COLUMN corp_cust_nbr,
    COLUMN ctry_cd
    ON customer;
-- One scan: CPU improvement ~49%, I/O improvement ~92%
```

### Pre-Aggregations

For multiple single-column stats, optimizer pre-aggregates on combined columns then rolls up each:

```sql
COLLECT STATISTICS
    COLUMN val_dt,
    COLUMN ctry_cd
    ON customer;
-- Pre-aggregates on (val_dt, ctry_cd), rolls up
-- CPU improvement ~32%, I/O improvement ~23%
```

### Cost-Based Access Paths

Optimizer considers join indexes, hash indexes, covering indexes as data sources for stats collection:

```sql
CREATE JOIN INDEX cust_ji AS
  SELECT cust_id, org_unit_id FROM customer
  PRIMARY INDEX (cust_id);

-- Optimizer reads compact JI instead of wide base table
COLLECT STATISTICS COLUMN org_unit_id ON customer;
-- CPU improvement ~64%
```

---

## SUMMARY Statistics

SUMMARY statistics contain only table-level info (row count, avg block size, avg row size) — **no histogram**.

```sql
COLLECT SUMMARY STATISTICS ON mydb.orders;
-- Fast, minimal resource impact
-- Preferred way to update optimizer row count estimate
```

- Automatically collected whenever any column/index stats are collected
- For non-partitioned tables, use SUMMARY instead of PARTITION for row count updates
- **Do not copy/transfer** SUMMARY stats between tables — always recollect natively

---

## Column Ordering for Multicolumn Statistics

Column ordering is honored. Different ordering on recollection causes error:

```sql
-- First collection
COLLECT STATISTICS COLUMN (order_date, order_key) ON Orders;

-- This FAILS:
COLLECT STATISTICS COLUMN (order_key, order_date) ON Orders;
-- *** Failure 3706: Multiple statistics with different column ordering
-- on the same set of columns are not allowed.
```

**Guideline:** For predicates with both single-table and join columns, place **single-table predicate columns as leading columns**.

---

## Named Statistics

```sql
-- Create named stats
COLLECT STATISTICS COLUMN (order_date, order_key) AS Stats_DateKey ON Orders;

-- Recollect by name (no need to repeat columns)
COLLECT STATISTICS COLUMN Stats_DateKey ON Orders;

-- Drop by name
DROP STATISTICS COLUMN Stats_DateKey ON Orders;
```

Rules:
- Must follow standard database object naming rules
- No duplicate names within a table
- Name cannot match any column name
- Not supported for volatile tables
- **Mandatory for expression statistics** (non-column references)

---

## Expression Statistics — Detailed Rules

### Supported Expressions

- CASE expressions
- String functions: SUBSTRING, TRIM, UPPER, LOWER
- EXTRACT (MONTH/YEAR/DAY FROM date)
- Arithmetic: MOD, +, -, *, /
- BEGIN/END of PERIOD columns
- UDT member access: `CustAddress.zip`
- Deterministic UDF calls

### NOT Supported

- PERIOD type directly → error 6969
- UDT column directly → error 5770
- Non-deterministic UDFs → error 3706

```sql
-- PERIOD columns — use BEGIN/END
COLLECT STATISTICS
    COLUMN BEGIN(Policy_Duration) AS Stats_BegDuration,
    COLUMN END(Policy_Duration) AS Stats_EndDuration
    ON Policy_Types;

-- UDT member access
COLLECT STATISTICS COLUMN CustAddress.zip AS Stats_Zip ON Customer;

-- Deterministic UDF
COLLECT STATISTICS
    COLUMN months_between(BEGIN(dur), END(dur)) AS Stats_MonthsBetween
    ON Policy_Types;
```

### Column vs Expression Statistics Guidance

| Predicate Pattern | Recommended |
|---|---|
| Simple arithmetic (`price * 1.1 > 100`) | Column stats (optimizer does constant move-around) |
| EXTRACT / SUBSTRING / CASE | Expression stats |
| TRIM / UPPER that don't change demographics | Column stats sufficient |
| Complex multi-function | Expression stats |

---

## Copy/Transfer Statistics

```sql
-- Copy stats from source to target (preserves USING options)
COLLECT STATISTICS ON target_table FROM source_table;

-- Copy at CREATE TABLE time
CREATE TABLE new_table AS source_table WITH STATS;
```

**Warnings:**
- Do NOT copy SUMMARY statistics between tables — recollect natively
- Do NOT copy PARTITION statistics when partitioning expressions differ

---

## Statistics Privileges

| Operation | Privilege Required |
|---|---|
| COLLECT STATISTICS | STATISTICS only |
| DROP STATISTICS | STATISTICS only |
| SHOW STATISTICS (no VALUES) | Any privilege on object |
| SHOW STATISTICS VALUES | SELECT or DUMP on object |
| HELP STATISTICS | Any privilege |

---

## Statistics Cache

Dedicated cache (separate from dictionary cache).

| Setting | Default | Range |
|---|---|---|
| `NumStatisticsCacheSegs` | 4 (= 4 MB) | 2–200 |

Each segment = 1 MB. Increase if cache hit ratio < 25% (logged in software event logs).

---

## Statistics Versions

| Version | Release | Key Changes |
|---|---|---|
| 1 | V2R1 | Initial, max 100 intervals |
| 2 | V2R5 | Sampling fields added |
| 3 | 12.0 | NumAllNulls, AvgAMPRPV; default max intervals = 200 |
| 4 | 12.0.3 | AllAMPSampleEst, OneAMPSampleEst for growth detection |
| 5 | 14.0 | New layout, larger values, modifiable intervals, history records, SUMMARY |
| 6 | 14.10 | UDI counts, StatsSkipCount, IsSampleFollowingTrend |

Version 6 activated by `NoDot0BackDown = TRUE` in DBS Control.
