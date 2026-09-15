# Teradata Time Series Reference

> Source: TDN0009627-A02 — Teradata® Time Series (Teradata 16.20)

---

## 1. Primary Time Index (PTI) Table Creation

### Syntax

```sql
CREATE TABLE table_name (
    column_definitions
)
PRIMARY TIME INDEX [index_name] (
    <timecode_dt>,
    [<timezero_date>,]
    [<timebucket_duration>,]
    [COLUMNS(column_list),]
    [SEQUENCED(max_val) | NONSEQUENCED]
);
```

### Parameters

| Parameter | Description |
|-----------|-------------|
| `<timecode_dt>` | `DATE \| TIMESTAMP(n) [WITH TIME ZONE]` — data type for the TD_TIMECODE column |
| `<timezero_date>` | `DATE` — earliest date for data collection. Default: `DATE '1970-01-01'` |
| `<timebucket_duration>` | `time_unit(n)` — interval that divides data into time buckets. Optional — omitting creates a "No Timebucket" table |
| `COLUMNS(column_list)` | Columns used for AMP distribution (in addition to or instead of time bucket) |
| `SEQUENCED(max_val)` | Adds TD_SEQNO column for row ordering. Default max: 20000. Range: 1 to 2147483647 |
| `NONSEQUENCED` | Default if omitted. Rows ordered by TD_TIMECODE only |

### Basic Example

```sql
CREATE TABLE ocean_time_series(
    buoyid INTEGER,
    salinity INTEGER,
    temperature INTEGER)
PRIMARY TIME INDEX(TIMESTAMP(6), DATE '2016-04-19', HOURS(1), SEQUENCED);
```

SHOW TABLE result:
```sql
CREATE SET TABLE DB1.ocean_time_series ,NO FALLBACK ,
     NO BEFORE JOURNAL, NO AFTER JOURNAL,
     CHECKSUM = DEFAULT, DEFAULT MERGEBLOCKRATIO, MAP = TD_MAP1
     (
      TD_TIMEBUCKET BIGINT NOT NULL GENERATED SYSTEM TIMECOLUMN,
      TD_TIMECODE TIMESTAMP(6) NOT NULL GENERATED TIMECOLUMN,
      TD_SEQNO INT NOT NULL GENERATED TIMECOLUMN,
      buoyid INTEGER,
      salinity INTEGER,
      temperature INTEGER)
 PRIMARY TIME INDEX (TIMESTAMP(6), DATE '2016-04-19', HOURS(1), SEQUENCED(20000));
```

---

## 2. Auto-Generated Columns

Every PTI table has up to 3 auto-generated columns (always columns 1, 2, 3):

| Column | Data Type | Present When | Populated By | Notes |
|--------|-----------|-------------|-------------|-------|
| `TD_TIMEBUCKET` | `BIGINT NOT NULL GENERATED SYSTEM TIMECOLUMN` | `<timebucket_duration>` is specified | System (auto-calculated) | Cannot be selected, updated, or referenced in DML. Not returned by `SELECT *` |
| `TD_TIMECODE` | Same as `<timecode_dt>` — `NOT NULL GENERATED TIMECOLUMN` | Always | User must supply value | Holds the timestamp of the observation |
| `TD_SEQNO` | `INT NOT NULL GENERATED TIMECOLUMN` | Table is `SEQUENCED` | User must supply value | Orders rows within same TD_TIMECODE. Valid range: 1 to max_val (default 20000) |

### Rules for Explicit Column Declaration

If the user specifies any auto-generated column in CREATE TABLE, **ALL** applicable auto-generated columns must be specified. Omitting one causes failure:

```sql
-- FAILS: TD_SEQNO missing for SEQUENCED table
CREATE TABLE seqtab(
    TD_TIMEBUCKET BIGINT NOT NULL GENERATED SYSTEM TIMECOLUMN,
    TD_TIMECODE TIMESTAMP(3) NOT NULL GENERATED TIMECOLUMN,
    buoyid INTEGER)
PRIMARY TIME INDEX(TIMESTAMP(3), DATE '2016-04-19', HOURS(1), SEQUENCED(500));
-- Error 3706: If SEQUENCED is specified and TD_TIMEBUCKET|TD_TIMECODE is present,
-- then TD_SEQNO column must be present.
```

---

## 3. Distribution Strategies

### Storage Option A — Time Bucket Only

- Rows distributed by `TD_TIMEBUCKET` only (equivalent to `PRIMARY INDEX (TD_TIMEBUCKET)`)
- No `COLUMNS` clause
- Best for: single-source continuous time series (e.g., one building's sensor data)
- All rows in one time bucket reside on the same AMP

```sql
CREATE TABLE nonseqtab1(
    buoyid INTEGER, salinity INTEGER, temperature INTEGER)
PRIMARY TIME INDEX(TIMESTAMP(6), DATE '2016-04-19', HOURS(1));
```

Explicit form:
```sql
CREATE TABLE nonseqtab1(
    TD_TIMEBUCKET BIGINT NOT NULL GENERATED SYSTEM TIMECOLUMN,
    TD_TIMECODE TIMESTAMP(6) NOT NULL GENERATED TIMECOLUMN,
    buoyid INTEGER, salinity INTEGER, temperature INTEGER)
PRIMARY TIME INDEX TimeIndex1(TIMESTAMP(6), DATE '2016-04-19', HOURS(1), NONSEQUENCED);
```

### Storage Option B — Time Bucket + Columns

- Rows distributed by `TD_TIMEBUCKET` and column values (equivalent to `PRIMARY INDEX (TD_TIMEBUCKET, col1, ...)`)
- Best for: multi-source continuous time series (e.g., multiple buoys)
- Rows for a given time bucket + series identifier reside on same AMP

```sql
CREATE TABLE nonseqtab2(
    buoyid INTEGER, salinity INTEGER, temperature INTEGER)
PRIMARY TIME INDEX(TIMESTAMP(6), DATE '2016-04-19', HOURS(1), COLUMNS(buoyid));
```

Explicit form:
```sql
CREATE TABLE nonseqtab2(
    TD_TIMEBUCKET BIGINT NOT NULL GENERATED SYSTEM TIMECOLUMN,
    TD_TIMECODE TIMESTAMP(6) NOT NULL GENERATED TIMECOLUMN,
    buoyid INTEGER, salinity INTEGER, temperature INTEGER)
PRIMARY TIME INDEX(TIMESTAMP(6), DATE '2016-04-19', HOURS(1),
                   COLUMNS(buoyid), NONSEQUENCED);
```

### Storage Option C — Columns Only (No Timebucket)

- Rows distributed by column values only (equivalent to `PRIMARY INDEX (col1, ...)`)
- No `TD_TIMEBUCKET` column in the table
- No `<timebucket_duration>` specified
- Best for: short/finite time series with logical overlay (e.g., aircraft flights)

```sql
CREATE TABLE nonseqtab3(
    buoyid INTEGER, salinity INTEGER, temperature INTEGER)
PRIMARY TIME INDEX(TIMESTAMP(6), COLUMNS(buoyid));
```

Explicit form (no TD_TIMEBUCKET):
```sql
CREATE TABLE nonseqtab3(
    TD_TIMECODE TIMESTAMP(6) NOT NULL GENERATED TIMECOLUMN,
    buoyid INTEGER, salinity INTEGER, temperature INTEGER)
PRIMARY TIME INDEX(TIMESTAMP(6), DATE '1970-01-01', COLUMNS(buoyid), NONSEQUENCED);
```

### SEQUENCED Variants

**Option A — Sequenced, time bucket only:**
```sql
CREATE TABLE seqtab1(
    buoyid INTEGER, salinity INTEGER, temperature INTEGER)
PRIMARY TIME INDEX PTI1(TIMESTAMP(6), DATE '2016-04-19', HOURS(1), SEQUENCED);
```

**Option B — Sequenced, time bucket + columns:**
```sql
CREATE TABLE seqtab2(
    buoyid INTEGER, salinity INTEGER, temperature INTEGER)
PRIMARY TIME INDEX(TIMESTAMP(6), DATE '2016-04-19', HOURS(1), COLUMNS(buoyid),
                   SEQUENCED(10000));
```

**Option C — Sequenced, columns only:**
```sql
CREATE TABLE seqtab3(
    buoyid INTEGER, salinity INTEGER, temperature INTEGER)
PRIMARY TIME INDEX(TIMESTAMP(6), DATE '2016-01-01', COLUMNS(buoyid), SEQUENCED(20000));
```

---

## 4. Time Bucket Duration Units

| Time Unit | Format Example | Short Hand Forms |
|-----------|---------------|-----------------|
| `CAL_YEARS` | `CAL_YEARS(4)` | `4cy`, `4cyear`, `4cyears` |
| `CAL_MONTHS` | `CAL_MONTHS(5)` | `5cm`, `5cmonth`, `5cmonths` |
| `CAL_DAYS` | `CAL_DAYS(6)` | `6cd`, `6cday`, `6cdays` |
| `WEEKS` | `WEEKS(3)` | `3w`, `3week`, `3weeks` |
| `DAYS` | `DAYS(5)` | `5d`, `5day`, `5days` |
| `HOURS` | `HOURS(4)` | `4h`, `4hr`, `4hrs`, `4hour`, `4hours` |
| `MINUTES` | `MINUTES(23)` | `23m`, `23mins`, `23minute`, `23minutes` |
| `SECONDS` | `SECONDS(33)` | `33s`, `33sec`, `33secs`, `33second`, `33seconds` |
| `MILLISECONDS` | `MILLISECONDS(12)` | `12ms`, `12msec`, `12msecs`, `12millisecond`, `12milliseconds` |
| `MICROSECONDS` | `MICROSECONDS(10)` | `10us`, `10usec`, `10usecs`, `10microsecond`, `10microseconds` |

---

## 5. Time Zero and Lifespan

### Time Zero

- The starting time point for time series data in the table
- Specified in `PRIMARY TIME INDEX` clause. Default: `DATE '1970-01-01'` (EPOCH)
- All `TD_TIMECODE` values must be >= Time Zero
- Best practice: set to a date just prior to when data collection starts

### Lifespan

Every PTI table has a valid time range from Time Zero to an upper limit. Use the `TD_TIMESERIES_RANGE` macro to query it:

```sql
EXEC DBC.TD_TIMESERIES_RANGE('ocean_buoy');

-- Output:
-- TD_TIMECODE_RANGE    TD_TIMECODE BETWEEN TIMESTAMP '2016-01-01 00:00:00.000000+00:00'
--                      AND TIMESTAMP '2030-08-12 14:23:21.842737+00:00'
-- TD_SEQNO_RANGE       TD_SEQNO BETWEEN 1 AND 20000 EACH 1
```

### Time Bucket Calculation

- The `<timezero_date>` and `<timebucket_duration>` divide the time continuum into consecutive time segments
- Each segment is assigned an integral time bucket number starting from Time Zero
- Rows with TD_TIMECODE falling in the same segment get the same TD_TIMEBUCKET value
- Choose duration to align with typical GROUP BY TIME queries for "Accelerated Time Range" queries (single-AMP or local aggregation)

---

## 6. GROUP BY TIME Clause

### Syntax

```sql
SELECT select_list
FROM table
[WHERE conditions]
GROUP BY TIME (timebucket_duration [AND optional_grouping_element_list])
    [USING TIMECODE(date_time_column [, seqno_column])]
    [FILL(NULLS | numeric_constant | PREV | PREVIOUS | NEXT)]
```

### Key Elements

| Element | Description |
|---------|-------------|
| `timebucket_duration` | Required. Time interval for grouping (e.g., `MINUTES(15)`, `HOURS(1)`, `DAYS(1)`). Use `*` for infinite interval (DELTA_T only) |
| `AND column_list` | Optional additional grouping columns |
| `USING TIMECODE(col)` | Specifies which column to use as timecode. **Required** for non-PTI tables or when multiple PTI tables in query. Recommended always |
| `FILL(option)` | Handles missing time buckets |

### Rules and Restrictions

- Cannot combine `GROUP BY TIME` and `GROUP BY` in the same SELECT statement (can be in nested subqueries at different levels)
- Must always have an associated TD_TIMECODE column
- `HAVING` clause is supported for filtering results
- `QUALIFY` and `WITH..BY` clauses are NOT supported
- `TD_TIMEBUCKET`, `TD_TIMECODE`, `TD_SEQNO` cannot be used as additional grouping columns
- `GROUP BY TIME(*)` = unbounded time (infinite interval) — only for `DELTA_T`
- `USING TIMECODE` is mandatory when: (i) source is non-PTI table, (ii) multiple PTI tables in source
- Can only use Time Series Aggregate functions (not traditional aggregates)

### Example

```sql
SELECT $TD_TIMECODE_RANGE, AVG(EngineTemp) FROM Table
    GROUP BY TIME (MINUTES(15) AND COUNTRY, CAR_ID)
    WHERE TD_TIMECODE BETWEEN TIMESTAMP '10-01-2016 08:00'
                         AND TIMESTAMP '10-01-2016 09:00';
```

### GROUP BY TIME Time Zero

- The earliest starting time from the WHERE clause time range(s)
- If no lower bound, uses the PTI table's Time Zero (or EPOCH for non-PTI)

---

## 7. System Virtual Columns

Two virtual columns available in GROUP BY TIME output:

| Virtual Column | Data Type | Description |
|----------------|-----------|-------------|
| `$TD_TIMECODE_RANGE` | `PERIOD` | Start and end timestamp of each GROUP BY TIME interval |
| `$TD_GROUP_BY_TIME` | `INTEGER` | Time bucket number of each GROUP BY TIME interval (starting at 1) |

### Edge Value Handling

- The range **includes** the starting time and **excludes** the ending time
- Exception: the last bucket may have identical start/end when it matches the WHERE upper bound

```sql
-- For GROUP BY TIME(HOURS(1)) with BETWEEN '08:00' AND '11:00':
-- Bucket 1: ('08:00', '09:00')  -- includes 08:00, excludes 09:00
-- Bucket 2: ('09:00', '10:00')  -- 09:00 falls HERE
-- Bucket 3: ('10:00', '11:00')
-- Bucket 4: ('11:00', '11:00')  -- only 11:00 values
```

---

## 8. FILL Clause

### Syntax

```sql
GROUP BY TIME (duration AND columns)
    FILL(NULLS | numeric_constant | PREV | PREVIOUS | NEXT)
```

### Options

| Option | Description |
|--------|-------------|
| `NULLS` | Fill missing time buckets with NULL aggregate results |
| `numeric_constant` (e.g., `0`) | Fill missing time buckets with the specified constant value |
| `PREV` / `PREVIOUS` | Fill with the previous time bucket's aggregate result |
| `NEXT` | Fill with the next time bucket's aggregate result |

### Strategies for Missing Values

1. **Ignore** — default behavior for Teradata aggregates (NULL values skipped)
2. **Remove rows** — `DELETE FROM table WHERE column IS NULL`
3. **Replace values** — `UPDATE table SET column = value WHERE column IS NULL`
4. **FILL clause** — handles missing values for entire time bucket intervals

> **Note:** `FILL(PREV)` and `FILL(NEXT)` can produce non-deterministic results when a group contains more than one row after aggregation.

---

## 9. Time Series Aggregate Functions

### New Functions (Added in 16.20)

| Function | Description |
|----------|-------------|
| `BOTTOM(n, column)` | Returns the bottom N values in the time bucket |
| `FIRST` | Returns the first value in the time bucket (by time order) |
| `TOP(n, column)` | Returns the top N values in the time bucket |
| `LAST` | Returns the last value in the time bucket (by time order) |
| `MEDIAN` | Returns the median value in the time bucket |
| `MODE` | Returns the most frequent value(s) — may return multiple rows if tie |
| `DELTA_T` | Returns Period between two events (see Section 10 below) |
| `MAD` | Mean/Median Absolute Deviation |

### Existing Functions Supporting GROUP BY TIME

| Function | Fully Parallel? |
|----------|----------------|
| `AVERAGE` / `AVG` | Yes |
| `COUNT` | Yes |
| `DESCRIBE` | — |
| `KURTOSIS` | Yes |
| `MAXIMUM` / `MAX` | Yes |
| `MINIMUM` / `MIN` | Yes |
| `PERCENTILE` | — |
| `RANK` (ANSI) | Yes |
| `SKEW` | Yes |
| `SUM` | Yes |
| `STDDEV_POP` | Yes |
| `STDDEV_SAMP` | Yes |
| `VAR_POP` | Yes |
| `VAR_SAMP` | Yes |

### Parallel vs Single-Threaded

- **Fully Parallel (FP):** Do not require entire dataset present; can compute on subsets in parallel then combine. Includes: AVG, COUNT, KURTOSIS, MAX, MIN, RANK, SKEW, STDDEV_POP, STDDEV_SAMP, SUM, VAR_POP, VAR_SAMP
- **Single Threaded (ST):** Require entire dataset sorted by time. Includes: DELTA_T, FIRST, LAST

---

## 10. DELTA_T Aggregate Function

### Purpose

Returns the starting and ending times for an event as a `PERIOD` data type. Tracks time elapsed between two events.

### Syntax

```sql
DELTA_T(
    (WHERE condition_for_start_event),
    (WHERE condition_for_end_event)
)
```

### Rules

- Cannot be combined with other aggregate functions in the same SELECT
- May appear only once in SELECT list (can be aliased)
- Time ranges must match data in source table
- Source data must be sorted by time for deterministic results
- Use `GROUP BY TIME(*)` for unbounded time interval

### Example — Package Delivery Tracking

```sql
CREATE MULTISET TABLE package_tracking_pti(
    ParcelNumber INTEGER, Status VARCHAR(512))
PRIMARY TIME INDEX (TIMESTAMP(6), DATE '2012-01-01', HOURS(1),
                    COLUMNS(ParcelNumber), NONSEQUENCED);

-- Find delivery time per parcel
SELECT ParcelNumber,
       DELTA_T((WHERE Status LIKE 'picked%up%customer'),
               (WHERE Status LIKE 'delivered%customer'))
FROM package_tracking_pti
GROUP BY TIME(* AND ParcelNumber);

-- Result:
-- ParcelNumber  DELTA_T(TD_TIMECODE)
-- 75  ('2016-10-15 08:00:00.000000-00:00', '2016-10-15 17:00:00.000000-00:00')
-- 55  ('2016-10-15 08:00:00.000000-00:00', '2016-10-15 17:00:00.000000-00:00')
```

### Extracting Duration from DELTA_T

```sql
SELECT ParcelNumber,
       INTERVAL(TSQ.DeliveryTime) HOUR AS DeliveryTimeInHours,
       TSQ.DeliveryTime AS Delivery_Date_Time
FROM (
    SELECT ParcelNumber,
           DELTA_T((WHERE Status LIKE 'picked%up%customer'),
                   (WHERE Status LIKE 'delivered%customer')) AS DeliveryTime
    FROM package_tracking_pti
    GROUP BY TIME(* AND ParcelNumber)
) AS tsq;
-- Result: DeliveryTimeInHours = 9
```

### Use Cases for DELTA_T

- Time elapsed between customer calling and reaching a representative
- Time between maximum and minimum observations (temperature, windspeed)
- Time between reporting a software defect and resolution
- Package delivery time from source to destination

---


> **See also:** [time-series-operations-reference.md](time-series-operations-reference.md) — DDL/DML operations, data loading, PTI restrictions, system functions, accelerated queries, use cases, and troubleshooting.
