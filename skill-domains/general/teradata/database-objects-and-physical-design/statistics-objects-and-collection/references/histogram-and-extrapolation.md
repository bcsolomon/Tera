# Histogram Internals & Stale Statistics Extrapolation

## Histogram Structure

### SHOW STATISTICS VALUES Output

```sql
SHOW STATISTICS VALUES COLUMN order_date ON mydb.orders;
```

Output sections:

#### 1. SummaryInfo Block

```
/* Data Type and Length       */ 'DA:4',
/* TimeStamp                  */ TIMESTAMP '2025-01-15 08:30:00',
/* Version                    */ 6,
/* UsageType                  */ 'S',          -- S=Summary, D=Detail
/* NumOfBiasedValues          */ 4,
/* NumOfEHIntervals           */ 300,          -- Actual equal-height intervals
/* NumOfHistoryRecords        */ 4,
/* SamplePercent              */ 0.00,         -- 0=full (100%)
/* NumOfNulls                 */ 1676709,
/* NumOfAllNulls              */ 1676709,
/* NumOfPartialNullVals       */ 0,
/* AvgAmpRPV                  */ 0.000000,
/* MinVal                     */ DATE '2020-01-01',
/* MaxVal                     */ DATE '2025-06-15',
/* ModeVal                    */ DATE '2024-12-15',
/* HighModeFreq               */ 149303,
/* NumOfDistinctVals          */ 2000,
/* NumOfRows                  */ 50000000,
/* StatsSkipCount             */ 0,            -- v6
/* SysInsertCnt               */ 0,            -- v6
/* SysDeleteCnt               */ 0,            -- v6
/* SysUpdateCnt               */ 0,            -- v6
```

#### 2. BiasedValuesAndFrequencies Block

High-frequency values extracted from the equal-height histogram for separate tracking:

```
/* BiasedValAndFreq[1] */ DATE '2024-11-30', 130500,
/* BiasedValAndFreq[2] */ DATE '2024-12-15', 149303,
/* BiasedValAndFreq[3] */ DATE '2024-12-31', 125000,
/* BiasedValAndFreq[4] */ DATE '2025-01-15', 72925,
```

#### 3. EqualHeightIntervals Block

Each interval has 6 fields:

| Field | Meaning |
|---|---|
| **MaxVal** | Maximum value in this interval |
| **ModeVal** | Most frequent value in this interval |
| **ModeValFreq** | Frequency of the mode value |
| **LowFreq** | Lowest frequency value's count |
| **OtherVals** | Number of distinct non-mode values |
| **OtherRows** | Number of non-mode rows |

```
/* Interval[1] */ DATE '2020-01-02', DATE '2020-01-02', 57, 1, 1, 1,
/* Interval[2] */ DATE '2020-01-04', DATE '2020-01-03', 411, 380, 1, 380,
/* Interval[3] */ DATE '2020-01-07', DATE '2020-01-05', 350, 290, 2, 570,
```

### XML Format

```sql
SHOW IN XML STATISTICS VALUES COLUMN order_date ON mydb.orders;
```

### Extrapolated Values

```sql
SHOW CURRENT STATISTICS VALUES COLUMN order_date ON mydb.orders;
-- MaxVal, NumOfDistinctVals, NumOfRows show extrapolated current values
```

---

## Equal-Height Histogram Interpretation

### Rows Per Value (RPV) Calculations

For an interval with the fields above:
- **Mode RPV** = ModeValFreq
- **Other RPV** = OtherRows / OtherVals (if OtherVals > 0)
- **Low RPV** = LowFreq
- **Total distinct in interval** = OtherVals + 1 (mode) + (1 if LowFreq > 0 and LowFreq ≠ ModeValFreq)

### How Optimizer Estimates Selectivity

For `WHERE order_date = DATE '2020-01-03'`:
1. Find interval containing the value (binary search on MaxVal)
2. Check if value matches ModeVal → use ModeValFreq
3. Otherwise, estimate = OtherRows / OtherVals

For `WHERE order_date BETWEEN DATE '2020-01-03' AND DATE '2020-01-07'`:
1. Find spanning intervals
2. Partial interval rows = (proportion of interval range) × total interval rows
3. Full interior intervals = sum all rows

---

## Stale Statistics Extrapolation

### Table Row Count Estimation Process

1. Pick row count from table-level stats (or latest histogram)
2. Pick current random AMP sampling estimate
3. Compare with saved sampling estimate
4. Growth factor = new sample − saved sample → added to base row count

### Column Classification for Extrapolation

| Classification | Criteria | Extrapolation Method |
|---|---|---|
| **Rolling** | DATE/TIMESTAMP or ≥95% unique | Extend max value: `new_max = old_max + (new_rows / avg_RPV)` |
| **Static** | All other columns | Distribute evenly: `new_freq = old_freq + (growth / distinct_values)` |

### Rolling Column Example

Orders table with 1M orders/day, stats collected Jul 25. Optimizer detects 2M growth → extends max from Jul 25 to Jul 27. Query `WHERE order_date BETWEEN '2025-07-26' AND '2025-07-27'` estimates 2M rows.

### Static Column Example

100 products, growth = 2M rows → each product gets +20,000 estimated rows.

### What Gets Extrapolated

- Table row count
- Number of distinct values
- Number of nulls
- High mode frequency
- Maximum value of histogram

**Limitation:** Extrapolation works only for upward data growth. If table size is constant or decreasing, extrapolations may not occur.

### Trend-Based Extrapolation (History Records)

Optimizer retains summary info of prior histograms as **history records** on every recollection. Analyzes records to find a **linear relationship** between row count and statistics values:

```
y = slope × x + intercept
```

Where x = row count, y = statistic value (e.g., distinct values).

**Critical:** Don't DROP and recollect — you lose history records. Only drop when data pattern has fundamentally changed.

---

## UDI (Update-Delete-Insert) Counts

Object Use Count (OUC) logging tracks insert/delete/update counts per table.

### Enable UDI Tracking

```sql
-- Enable on database owning the objects
BEGIN QUERY LOGGING WITH USECOUNT ON mydb;

-- Add USECOUNT to existing logging
REPLACE QUERY LOGGING WITH <current_options>, USECOUNT ON myuser;

-- Disable
END QUERY LOGGING ON mydb;
```

### UDI vs Sampling Row Count Accuracy

| Scenario | 1-AMP Sampling | UDI Counts |
|---|---|---|
| Up-to-date stats | Accurate | Accurate |
| 300K rows deleted | Not detected | Accurate |
| 900K added after delete | Close | Accurate |

### UDI Implementation Details

- Two versions: **user** (resettable) and **system** (reset by database)
- Optimizer compares UDI estimate with sampling/history; if deviation >5%, UDI treated as invalid
- Auto-corrected on next stats collection
- OUC Cache: flushed when full, at flush timeout (`ObjectUseCountCollectRate`, default 10 min), or on bulk activity
- Limitations: over-reported after abort, under-reported after restart, doesn't track DBC tables

---

## PARTITION Statistics Details

### Row + Column Partitioned Tables

Two histograms built:
1. **Row partitioning histogram**: combined partition number + active row count (non-deleted)
2. **Column partitioning histogram**: column partition number + compression ratio per column partition

```sql
-- Collect PARTITION stats (highly optimized, reads cylinder indexes)
COLLECT STATISTICS COLUMN (PARTITION) ON mydb.orders;

-- For CP tables, collect compression ratios at column-partitioning level
COLLECT STATISTICS COLUMN (PARTITION#L1) ON mydb.cp_table;
-- (Only for column-partitioning level, NOT row-partitioning levels)
```

### PARTITION Stats Rules

- Fast operation — reads cylinder indexes, not data blocks
- **Always collect on all partitioned tables**
- Used for costing (rows, data blocks, partitions to scan)
- Refresh when 10% change at **partition level** (not table level)
- Refresh when partition changes empty ↔ nonempty
- **Must drop before ALTER TABLE partitioning, recollect after**
- Cannot collect on volatile tables or join indexes
- On non-partitioned tables: all rows treated as partition 0 — use SUMMARY instead

---

## DROP Statistics — Detailed Behavior

```sql
-- Drop specific column stats (SUMMARY stats NOT dropped)
DROP STATISTICS COLUMN customer_id ON mydb.orders;

-- Drop by name
DROP STATISTICS COLUMN Stats_DateKey ON mydb.orders;

-- Drop ALL stats including SUMMARY
DROP STATISTICS ON mydb.orders;
```

When dropping by explicit column/index, SUMMARY stats **remain**. Only a table-level `DROP STATISTICS ON table` removes SUMMARY.

---

## Statistics Recommendations Infrastructure

### DBQL STATSUSAGE

```sql
-- Log missing + used stats per request (XML in DBQLXMLTbl)
BEGIN QUERY LOGGING WITH STATSUSAGE ON myuser;

-- Combined with XMLPLAN for step-level recommendations
BEGIN QUERY LOGGING WITH STATSUSAGE, XMLPLAN ON myuser;
```

### Missing Statistics XML Format

```xml
<StatsMissing Importance="High">
  <RelationRef Ref="REL1"/>
  <FieldRef Ref="REL1_FLD1035"/>  <!-- column on table -->
</StatsMissing>
```

### Finding Used Statistics

```sql
SELECT DatabaseName, TableName, StatName,
       LastAccessTimeStamp, AccessCount
FROM DBC.StatUseCountV
ORDER BY AccessCount DESC;
```

### Finding Unused Statistics

```sql
SELECT d.DatabaseName, t.TVMName AS TableName,
       s.ExpressionList AS ColumnName, s.StatsName
FROM DBC.TVM t
JOIN DBC.DBase d ON t.DatabaseId = d.DatabaseId
JOIN DBC.StatsTbl s ON s.DatabaseId = d.DatabaseId AND s.ObjectId = t.TVMId
WHERE NOT EXISTS (
    SELECT 1 FROM DBC.ObjectUsage ouc
    WHERE ouc.UsageType = 'STA'
      AND ouc.DatabaseId = s.DatabaseId
      AND ouc.ObjectId = s.ObjectId
      AND COALESCE(ouc.FieldId, 0) = s.StatsId
);
```

### Tracking Skipped Recollections

```sql
SELECT DatabaseName, TableName, ColumnName,
       CAST(LastCollectTimeStamp AS DATE) AS collected,
       CAST(LastAlterTimeStamp AS DATE) AS last_submit,
       StatsSkipCount
FROM DBC.TableStatsV
WHERE ColumnName IS NOT NULL
ORDER BY StatsSkipCount DESC;
```

`LastCollectTimeStamp` updates only when stats actually collected.
`LastAlterTimeStamp` updates on every COLLECT submission (even if skipped).

### EXPLAIN Threshold Messages

```
-- Skip example:
We SKIP collecting STATISTICS for ('order_date, order_key'), because
the age of the statistics (5 days) does not exceed the user-specified
time threshold of 10 days and the estimated data change of 5% does not
exceed the system-determined change threshold of 20%.

-- Collect example:
Statistics are collected since the age of the statistics (15 days)
exceeds the time threshold of 10 days and the estimated data change
of 25% exceeds the system-determined change threshold of 20%.
```

---

## System Sample Downgrade Process

1. First collection: always **full statistics** (100%)
2. Optimizer accumulates reliable history records
3. Recognizes column characteristics (skewed, rolling, static)
4. Considers column usage data in `DBC.StatsTbl.UsageType`
5. More aggressive downgrade for summary-only usage columns
6. Determines optimal sample % and scaling formula
7. Periodically recollects full stats to verify

```sql
-- Check actual sample percentage used
SELECT DatabaseName, TableName, ColumnName, SamplePctSize AS SamplePercent
FROM DBC.TableStatsV
WHERE ColumnName IS NOT NULL AND SamplePctSize > 0;
```

---

## IPE (Incremental Planning & Execution) — Statistics Feedback

Dynamic statistics collected on spools during query execution:
- **Table-level:** Row count + spool size (negligible overhead)
- **Column-level:** NUV, HMF, null count, high AMP frequency, avg unique values/AMP

### Collection Mechanisms

| Method | Overhead | Supported Steps |
|---|---|---|
| 2-step | Negligible (before write) | RET, JIN |
| 1-step | Noticeable I/O | Other steps |

Optimizer uses spool statistics to reoptimize subsequent steps if actual cardinality deviates significantly from estimate.
