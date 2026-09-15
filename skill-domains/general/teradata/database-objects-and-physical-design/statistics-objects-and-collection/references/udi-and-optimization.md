# UDI Counts, Advanced Extrapolation & Statistics Management

> Source: 541-0010042 — Statistics Enhancements Version 14.10

## UDI (Update-Delete-Insert) Count Tracking

UDI counts track insert, delete, and update activity per table, enabling the optimizer to detect both data **growth** (inserts only) and data **change** (inserts + deletes), improving staleness detection and extrapolation accuracy.

### Enabling UDI Count Logging

```sql
-- Enable object use count logging for a database
BEGIN QUERY LOGGING WITH USECOUNT ON database_name;

-- Enable for all databases owned by a user
BEGIN QUERY LOGGING WITH USECOUNT ON user_name;

-- Verify logging is enabled
SELECT * FROM DBC.DBQLRulesTbl
WHERE RuleScope = 'ObjectUsage';
```

### How UDI Counts Work

1. INSERT/DELETE/UPDATE operations increment per-table counters
2. Counters cached in OUC (Object Use Count) cache on each AMP
3. Cache flushed to persistent storage on:
   - Cache full
   - Timeout (`ObjectUseCountCollectRate` default: 10 minutes)
   - Bulk activity (large INSERT-SELECT, DELETE)
4. Two counter versions maintained:
   - **System counters** — auto-reset by the database after stats collection
   - **User counters** — resettable by user

### UDI Count Validation

The optimizer cross-validates UDI counts against dynamic-AMP sampling:
- If deviation between UDI-based and sampling-based estimates is ≤5%, UDI counts are considered reliable
- If deviation >5%, the optimizer uses history-based trend extrapolation as a tiebreaker
- If neither is reliable, sampling-based estimate is used

### UDI Count Limitations

| Limitation | Detail |
|---|---|
| Aborted transactions | UDI counts may be over-reported (counts not rolled back) |
| System restarts | UDI counts may be under-reported (unflushed cache lost) |
| DBC tables | UDI counts excluded |
| Updates | UDI counts track update count but optimizer cannot extrapolate histogram changes from updates alone |

## Row Count Estimation with UDI

The optimizer estimates current row count using a priority chain:

1. **SUMMARY statistics available + UDI counts available:**
   - Compare saved insert/delete counts at collection time vs. current counts
   - Apply adjustment: `current_rows = collected_rows + (new_inserts - new_deletes)`
   - Supports **upward and downward** adjustment

2. **SUMMARY statistics available + NO UDI counts:**
   - Compare sampling-based estimate at collection time vs. current estimate
   - **Upward adjustment only** — never decreases row count

3. **History-based trend extrapolation:**
   - If reliable data change pattern established from ≥3 history records
   - Extrapolate row count from established growth/decline trend

4. **Dynamic-AMP sampling (fallback):**
   - Single-AMP sample, scale to full system
   - Least accurate, especially for compressed (BLC) and column-partitioned tables

### Row Count Estimation Comparison

| Scenario | Sampling Method | UDI Method | Actual |
|---|---|---|---|
| Fresh stats | 10,929,519 (accurate) | 10,929,519 (accurate) | 10,929,519 |
| 300K rows deleted | 10,929,519 (stale!) | 10,621,212 (accurate) | 10,621,212 |
| +900K rows added | 11,503,439 (close) | 11,521,541 (accurate) | 11,521,541 |

### Verify Extrapolated Row Count

```sql
-- Shows extrapolated row count (asterisk row)
HELP CURRENT STATS ON mydb.orders;

-- Compare to collected stats
HELP STATS ON mydb.orders;
```

## Enhanced Staleness Detection

### Without UDI (Sampling Only)

| Change Type | Detected? |
|---|---|
| Large insert | Yes |
| Small insert (< ~1% of table) | Often missed |
| Delete + equal insert (table size unchanged) | **No** |
| Large delete only | Partially (sampling may not decrease) |

### With UDI Counts

| Change Type | Detected? |
|---|---|
| Any insert (even 1 row) | Yes |
| Any delete (even 1 row) | Yes |
| Delete + insert (data change) | **Yes** — detects both separately |
| Update | Yes (but extrapolation limited) |

## THRESHOLD Skip Logic — Advanced Details

### Skip Decision Algorithm

Recollection is skipped only when ALL applicable thresholds evaluate as "below threshold":

```
IF time_threshold_active AND change_threshold_active:
    SKIP when (age < time_threshold) AND (data_change < change_threshold)
    COLLECT when (age ≥ time_threshold) OR (data_change ≥ change_threshold)
```

### COLLECT STATISTICS EXPLAIN Indicators

```sql
EXPLAIN COLLECT STATISTICS COLUMN order_date ON mydb.orders;
```

| EXPLAIN Message | Meaning |
|---|---|
| `"We SKIP collecting STATISTICS for ('col'), because the age of the statistics (5 days) does not exceed the user-specified time threshold of 10 days and the estimated data change of 5% does not exceed the system-determined change threshold of 20%."` | Both thresholds not met → skipped |
| `"Statistics are collected since the age of the statistics (15 days) exceeds the time threshold of 10 days"` | Time threshold exceeded → collected |
| `"Statistics are collected since the estimated update of 15% exceeds the system-determined update threshold of 5%"` | Update threshold exceeded → collected |
| `"Statistics collected since the estimated data change or system threshold could not be determined."` | Cannot evaluate → collected (safe default) |
| No threshold info | First collection, temp table, or PARTITION column |

### Scenarios Where Optimizer Cannot Determine Threshold

- OUC counts unreliable (inconsistent with sampling/trend)
- Target table too small (aggregation estimated < 0.5 seconds)
- Irregular data-change pattern in history records

### Skip Count Tracking

```sql
-- Check skip count and last submission time
SELECT DatabaseName, TableName, ColumnName,
       CAST(LastCollectTimeStamp AS DATE) AS CollectionDate,
       CAST(LastAlterTimeStamp AS DATE) AS LastSubmitDate,
       StatsSkipCount
FROM DBC.TableStatsV
WHERE ColumnName IS NOT NULL;
```

### FOR CURRENT Override

Force recollection without changing saved threshold settings:

```sql
-- Recollect now, but keep the THRESHOLD settings for future
COLLECT STATISTICS USING NO THRESHOLD FOR CURRENT
    COLUMN order_date ON mydb.orders;
```

## Identifying Used, Unused, and Missing Statistics

### Used Statistics

```sql
-- Query DBQL for statistics usage
SELECT DatabaseName, TableName, ColumnName, UsageType
FROM DBC.TableStatsV
WHERE UsageType IS NOT NULL
ORDER BY DatabaseName, TableName;
```

### Unused Statistics (Candidates for Removal)

```sql
-- Find statistics not referenced by any query in DBQL
-- (Requires DBQL logging with STATSUSAGE option enabled)
SELECT s.DatabaseName, s.TableName, s.ColumnName
FROM DBC.TableStatsV s
LEFT JOIN (
    SELECT DISTINCT DatabaseName, TableName, ColumnName
    FROM DBC.DBQLStatsUsageTbl
) u ON s.DatabaseName = u.DatabaseName
   AND s.TableName = u.TableName
   AND s.ColumnName = u.ColumnName
WHERE u.DatabaseName IS NULL
  AND s.ColumnName IS NOT NULL;
```

### Missing Statistics (Recommended by Optimizer)

```sql
-- Enable STATSUSAGE XML capture in DBQL
BEGIN QUERY LOGGING WITH STATSUSAGE XML ON database_name;

-- Query captured recommendations
SELECT QueryID,
       XMLEXTRACT(StatsUsageXML, '/StatsUsage/MissingStats') AS MissingStats
FROM DBC.DBQLStatsUsageTbl
WHERE MissingStats IS NOT NULL;
```

## Recommendations

1. **Enable DBQL USECOUNT** on all production databases — enables accurate change detection and system thresholds
2. **Use SYSTEM SAMPLE + SYSTEM THRESHOLD** as global defaults — let optimizer decide
3. **Do not DROP and recollect** — loses history records used for trend-based extrapolation
4. **Recollect after large-scale UPDATES** — neither sampling nor UDI can accurately extrapolate updated histogram values
5. **For BLC/CP tables**, keep SUMMARY statistics fresh — dynamic-AMP sampling gives poor estimates on compressed data
6. **Use HELP CURRENT STATS** and **SHOW CURRENT STATS VALUES** to verify extrapolation accuracy during diagnostics
7. **Use FOR CURRENT** to force one-time recollection without changing saved threshold settings
