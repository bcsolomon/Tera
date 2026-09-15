# Teradata Time Series Operations Reference

> Source: TDN0009627-A02 — Teradata® Time Series (Teradata 16.20)

---

## 11. DDL Operations

### CREATE TABLE ... AS

```sql
-- Copy PTI table with same definition and data
CREATE TABLE pti_tgt AS pti_src WITH DATA;

-- Create PTI table from PTI source with different PTI definition
CREATE TABLE PTI_target
AS (SELECT * FROM pti_source) WITH DATA
PRIMARY TIME INDEX (TIMESTAMP(6), DATE '2015-01-01', DAYS(1), NONSEQUENCED);

-- Create non-PTI table from PTI table (use subquery, no PTI clause)
CREATE TABLE nonpti1 AS (SELECT * FROM pti_source) WITH DATA;

-- Create PTI table from non-PTI table (PTI clause required, use subquery)
CREATE TABLE pti_tab2 AS
    (SELECT TD_TIMECODE, TD_SEQNO, C1, C2, C3 FROM nonpti1) WITH DATA
PRIMARY TIME INDEX(TIMESTAMP(6), DATE '2016-01-01', HOURS(1), SEQUENCED);
```

**Rules:**
- Source must be PTI table OR PRIMARY TIME INDEX clause must be specified
- When using WITH DATA, TD_TIMECODE values must not be < target's Time Zero
- TD_SEQNO values must not exceed target's max sequence number
- TD_TIMEBUCKET values are NOT copied — regenerated automatically
- When creating non-PTI from PTI without subquery, result IS a PTI table
- When creating PTI from non-PTI, subquery cannot include TD_TIMEBUCKET

### ALTER TABLE

```sql
-- Add title to time column (allowed)
ALTER TABLE pti_tab ADD TD_TIMECODE TITLE 'start_time';

-- Add/modify PTI index name
ALTER TABLE pti_tab MODIFY PRIMARY TIME INDEX pti_index;

-- CANNOT drop time columns
ALTER TABLE pti_tab DROP TD_TIMECODE;
-- Error 3706: The TD_TIMECODE column is a Time Series generated column and cannot be dropped.

-- CANNOT add default to time columns
ALTER TABLE pti_tab ADD TD_TIMECODE DEFAULT TIME '10:30:00';
-- Error 3706: Only TITLE | FORMAT can be added to TD_TIMECODE|TD_SEQNO in a Time Series table.
```

### SHOW TABLE

Displays CREATE TABLE DDL with auto-generated columns and PRIMARY TIME INDEX clause.

### HELP Commands

**HELP DATABASE:** Returns `Table Flavor` field — value `'S'` indicates PTI table.

**HELP TABLE:** Returns `Time Series Column Type` field:
- `TB` = TD_TIMEBUCKET
- `TC` = TD_TIMECODE
- `TN` = TD_SEQNO
- `?` (NULL) = regular columns

**HELP COLUMN:** Returns `Time Series Column Type` (same values as HELP TABLE).

**HELP INDEX:** Returns additional fields:
- `TimeZero` — the Time Zero date value
- `Timebucket` — the time bucket duration (e.g., `HOURS(1)`)
- `Column Names` — shows distribution columns (e.g., `TD_TIMEBUCKET,C1`)

### CREATE INDEX

- Secondary indexes can be created on PTI tables
- **Cannot** create secondary index on TD_TIMEBUCKET, TD_TIMECODE, or TD_SEQNO
- Join indexes and Hash indexes **cannot** be created on PTI tables

### COLLECT/HELP/DROP STATISTICS

- No syntax changes for PTI support
- Statistics may be collected on TD_TIMEBUCKET, TD_TIMECODE, and TD_SEQNO
- Evaluate whether collecting statistics benefits outweigh the cost

### NORMALIZE & EXPAND ON

```sql
-- Normalized PTI table for repeated sensor readings
CREATE TABLE flight_sensors (
    FlightID INTEGER,
    SensorID INTEGER,
    SensorData INTEGER,
    duration PERIOD(TIMESTAMP(6)),
    NORMALIZE ALL BUT(SensorData) ON duration ON MEETS OR OVERLAPS)
PRIMARY TIME INDEX (TIMESTAMP(6), DATE '2016-10-15',
                    COLUMNS(flightID, SensorID), NONSEQUENCED);
```

### Other DDL

- DROP TABLE and RENAME TABLE: no changes for PTI
- Views and Macros can be created with PTI tables
- PTI tables **cannot** be Queue tables
- Error tables can be defined on PTI tables
- TEMPORAL columns (VALIDTIME/TRANSACTIONTIME) **cannot** be used with PTI tables

---

## 12. DML Operations

### INSERT

```sql
-- Values start at TD_TIMECODE (skip TD_TIMEBUCKET)
INSERT INTO ocean_buoy(TD_TIMECODE, buoyid, temperature)
    VALUES(DATE '2017-01-01', 10, 77);

-- Positional (starting at column 2)
INSERT INTO ocean_buoy(DATE '2017-01-02', 10, 80);

-- For SEQUENCED tables, must supply TD_SEQNO
INSERT INTO ocean_buoy_seq(TIMESTAMP '2017-01-06 10:32:12.000000', 1, 111, 50);
```

**INSERT Rules:**
- Cannot insert into TD_TIMEBUCKET (system generated)
- TD_TIMECODE and TD_SEQNO are NOT NULL — values must be supplied
- TD_TIMECODE cannot be CURRENT_DATE, CURRENT_TIME, or CURRENT_TIMESTAMP
- TD_TIMECODE must be >= Time Zero of the table
- `WITH ISOLATED LOADING` not supported
- `DEFAULT VALUES` not supported

### SELECT

```sql
-- SELECT * does NOT return TD_TIMEBUCKET
SELECT * FROM ocean_buoy_seq;

-- TD_TIMECODE and TD_SEQNO can be used anywhere
SELECT td_timecode, td_seqno, buoyid FROM ocean_buoy_seq WHERE td_seqno > 2;

-- TD_TIMEBUCKET cannot be selected
SELECT TD_TIMEBUCKET FROM ocean_buoy_seq;
-- Error 3706: Select of TD_TIMEBUCKET from Time Series table is invalid.

-- TD_TIMEBUCKET cannot be in WHERE
SELECT TD_SEQNO FROM ocean_buoy_seq WHERE TD_TIMEBUCKET > 1;
-- Error 3706: TD_TIMEBUCKET cannot be referenced in WHERE clause.

-- Use TD_GETTIMEBUCKET() to retrieve bucket value
SELECT TD_GETTIMEBUCKET(td_timecode) FROM ocean_buoys;
```

### UPDATE

```sql
-- TD_TIMECODE can be updated (TD_TIMEBUCKET auto-regenerated)
UPDATE ocean_buoy SET td_timecode = DATE '2017-01-01' WHERE buoyid = 10;

-- TD_TIMEBUCKET cannot be updated
UPDATE ocean_buoy SET td_timebucket = 101;
-- Error 3706: TD_TIMEBUCKET cannot be referenced in UPDATE statement.
```

### DELETE

```sql
-- TD_TIMEBUCKET cannot be in WHERE clause
DELETE FROM ocean_buoy WHERE td_timebucket = 101;
-- Error 3706: TD_TIMEBUCKET cannot be referenced in DELETE statement.
```

### MERGE

```sql
MERGE INTO tgt_s AS tgt
USING src_s AS src
ON tgt.TD_TIMECODE = src.TD_TIMECODE AND
   tgt.TD_SEQNO = src.TD_SEQNO AND
   tgt.c1 = src.c1
WHEN MATCHED THEN UPDATE SET c2 = 70
WHEN NOT MATCHED THEN INSERT
    (src.TD_TIMECODE, src.TD_SEQNO, src.c1, src.c2);
```

**MERGE Rules:**
- TD_TIMEBUCKET cannot appear anywhere in MERGE
- Target PTI: TD_TIMEBUCKET auto-generated
- Target PTI ON clause must include equality predicates on TD_TIMECODE, TD_SEQNO (if present), and COLUMNS columns (if present)
- TD_TIMECODE value must be >= Time Zero of target

### UPSERT

```sql
UPDATE ocean_buoy_seq SET temperature = 80
    WHERE TD_TIMECODE = TIMESTAMP '2017-01-06 12:32:12.000000'
      AND td_seqno = 3
      AND buoyid = 111
ELSE
    INSERT INTO ocean_buoy_seq(TIMESTAMP '2017-01-06 12:32:12.000000', 3, 111, 80);
```

**UPSERT Rules:**
- TD_TIMEBUCKET, TD_TIMECODE, TD_SEQNO, and COLUMNS columns cannot be updated
- WHERE clause must include equality predicates on: TD_TIMECODE, TD_SEQNO (if sequenced), all COLUMNS columns

### INSERT-SELECT

- Source and target can be PTI or regular tables
- TD_TIMEBUCKET cannot be selected from or inserted into

### USING ... INSERT (JSON Import)

```sql
-- Import JSON data into PTI table
.import vartext file = JsonBuoy.dat

USING (RAWBUOY VARCHAR(500), buoyid INT)
INSERT INTO ocean_buoy_no_seq(TD_TIMECODE, buoyid, temperature)
VALUES (CAST(CAST(:RAWBUOY AS JSON(500)).TS.Arriving_timestamp AS TIMESTAMP(6)),
        :buoyid,
        CAST(:RAWBUOY AS JSON(500)).TS.temperature);
```

---

## 13. Loading Data

### Supported Utilities

| Utility | Supported? |
|---------|-----------|
| Fastload | Yes |
| MloadX | Yes |
| TPT (Teradata Parallel Transporter) | Yes |
| Fastexport (extract) | Yes |
| Multiload | **No** — use MloadX instead |

**Key Rule:** TD_TIMEBUCKET column value cannot be loaded — it is system generated.

### Fastload Example

```
.logon <server_name>/<user_name>, <password>
DROP TABLE error01;
DROP TABLE error02;

BEGIN LOADING eq_t
errorfiles error01, error02;

set record vartext "," display_errors nostop;
DEFINE
 ts             (VARCHAR(100)),
 latitude       (VARCHAR(100)),
 longitude      (VARCHAR(100)),
 depth          (VARCHAR(100)),
 mag            (VARCHAR(100))

FILE=EQ3.data;

INSERT INTO eq_t VALUES (:ts, :latitude, :longitude, :depth, :mag);
END LOADING;
LOGOFF;
.QUIT;
```

### TPT Example

TPT script defines schema, DDL operator, Load operator, and File Reader operator. The INSERT statement in the APPLY step skips TD_TIMEBUCKET:

```
INSERT INTO PARTY_nonseq_06 (TD_TIMECODE, PARTY_ID, PARTY_TYPE_CD, ...)
VALUES (:TD_TIMECODE, :PARTY_ID, :PARTY_TYPE_CD, ...);
```

Run with: `tbuild -f script.tpt`

---

## 14. PTI Restrictions (Complete List)

| Restriction | Description |
|-------------|-------------|
| No regular PI/NOPI | A PTI table cannot also be a regular PI or NOPI table |
| No Join Indexes | Join indexes cannot be created on PTI tables |
| No Hash Indexes | Hash indexes cannot be created on PTI tables |
| No Row/Column Partitioning | PTI tables cannot include PPI (row or column partitioning) |
| No Temporal Tables | Cannot have VALIDTIME or TRANSACTIONTIME columns |
| No Queue Tables | PTI tables cannot be queue tables |
| No Load Isolation | `WITH ISOLATED LOADING` not supported |
| No Secondary Index on Time Columns | Cannot create secondary index on TD_TIMEBUCKET, TD_TIMECODE, or TD_SEQNO |
| No TD_TIMEBUCKET in DML | Cannot SELECT, INSERT, UPDATE, DELETE, or reference TD_TIMEBUCKET in WHERE |
| No CURRENT_TIMESTAMP for TD_TIMECODE | Cannot use CURRENT_DATE/TIME/TIMESTAMP for TD_TIMECODE |
| No DEFAULT VALUES insert | `INSERT...DEFAULT VALUES` not allowed |
| No GROUP BY with GROUP BY TIME | Cannot combine traditional GROUP BY and GROUP BY TIME in same SELECT |
| No QUALIFY/WITH..BY | Not supported with GROUP BY TIME |
| No Multiload | Use MloadX protocol instead |

---

## 15. System Functions and Macros

### TD_GETTIMEBUCKET()

Retrieves the TD_TIMEBUCKET column value (since it can't be selected directly).

```sql
-- Syntax
TD_SYSFNLIB.TD_GETTIMEBUCKET([<table_name>.TD_TIMECODE])

-- Examples
SELECT TD_GETTIMEBUCKET(td_timecode) FROM ocean_buoys;
SELECT TD_GETTIMEBUCKET(ocean_buoys.td_timecode) FROM ocean_buoys;

-- In WHERE clause
SELECT buoyid FROM ocean_buoys WHERE TD_GETTIMEBUCKET(td_timecode) > 200;
```

### TD_TIME_BUCKET_NUMBER()

Generic function to calculate a time bucket number from parameters (not tied to a specific PTI table).

```sql
-- Syntax
TD_SYSFNLIB.TD_TIME_BUCKET_NUMBER(<timeZero>, <timeCode>, <timebucket_duration>)

-- Example
SELECT TD_SYSFNLIB.TD_TIME_BUCKET_NUMBER(
    TIMESTAMP '1900-01-01 10:30:00.000000',
    TIMESTAMP '2006-06-06 06:06:06.006002',
    CAL_YEARS(10));
-- Result: 11
```

Can be used with HASHROW, HASHBUCKET, or HASHAMP to check row distribution.

### TD_TIMESERIES_RANGE Macro

Shows valid ranges for TD_TIMECODE and TD_SEQNO in a PTI table.

```sql
-- Syntax
EXEC DBC.TD_TIMESERIES_RANGE('[<database_name>.]<table_name>');

-- Example
EXEC DBC.TD_TIMESERIES_RANGE('ocean_buoy');
-- TD_TIMECODE_RANGE: BETWEEN TIMESTAMP '2016-01-01 00:00:00.000000+00:00'
--                    AND TIMESTAMP '2030-08-12 14:23:21.842737+00:00'
-- TD_SEQNO_RANGE:    BETWEEN 1 AND 20000 EACH 1
```

---

## 16. Time Series Analysis for Non-PTI Tables

GROUP BY TIME can be used on regular (non-PTI) tables:

- `USING TIMECODE` clause is **required** to identify the timecode column
- All Time Series aggregate functions are supported
- Processing is optimized for PTI but fully supported for non-PTI
- Implicit NOT NULL filter added for TIMECODE/SEQNO columns
- Extends time series analytics to existing tables (DBQL, RSS, etc.)

```sql
SELECT $TD_TIMECODE_RANGE, AVG(some_metric)
FROM regular_table
WHERE date_col BETWEEN ... AND ...
GROUP BY TIME(HOURS(1))
USING TIMECODE(date_col);
```

---

## 17. Accelerated (Aligned) Time Range Queries

When every GROUP BY TIME interval falls wholly within a single PTI time bucket, the query is "Aligned" or "Accelerated":

- **Single AMP operation** when filtering on both timecode range and a specific COLUMNS value
- **All-AMP with local aggregation** when querying all COLUMNS values
- Works even when the query time scope crosses distribution boundaries, as long as individual GROUP BY TIME intervals are aligned

```sql
-- Table: HOURS(4) buckets distributed by BuoyID
CREATE TABLE PTI_1 (BuoyID INTEGER, Temp FLOAT, Velocity FLOAT)
   PRIMARY TIME INDEX(TIMESTAMP(0), DATE '1970-01-01', HOURS(4), COLUMNS(BuoyID));

-- Single AMP (specific BuoyID, 30-min groups within 4-hour bucket)
SELECT AVG(Temp), MAX(Velocity) FROM PTI_1
   WHERE TD_TIMECODE BETWEEN TIMESTAMP '2017-01-01 09:00:00' AND '2017-01-01 12:00:00'
     AND BuoyID = 33
   GROUP BY TIME (MINUTES(30) AND BUOYID);

-- All-AMP with local aggregation (all BuoyIDs)
SELECT AVG(Temp), MAX(Velocity) FROM PTI_1
   WHERE TD_TIMECODE BETWEEN TIMESTAMP '2017-01-01 09:00:00' AND '2017-01-01 12:00:00'
   GROUP BY TIME (MINUTES(30) AND BUOYID);
```

**Best practice:** Choose PTI time bucket duration so typical queries are aligned.

---

## 18. Space Requirements

| Source Table | Target PTI Table | Extra Storage |
|-------------|-----------------|---------------|
| Traditional PI | PTI with time bucket | 14 bytes/row (6 + 8) |
| PPI-2 | PTI with time bucket | 14 bytes/row |
| PPI-8 | PTI with time bucket | 8 bytes/row |
| Traditional PI | No-timebucket PTI | 6 bytes/row |
| PPI-2 | No-timebucket PTI | 6 bytes/row |
| PPI-8 | No-timebucket PTI | 0 bytes/row |

---

## 19. EXPLAIN Output Enhancements

When `DIAGNOSTIC VERBOSE EXPLAIN` is ON:
- Time Zero specification used in aggregate calculation
- Optimization plan for single-threaded aggregate execution
- Each aggregate tagged as fully parallel or single threaded
- Sorting/redistribution before aggregation (for ST aggregates)
- Sorting/redistribution after aggregation (for FILL directive)

---

## 20. Use Case Examples

### Outlier Detection (Standard Deviation + Mean)

```sql
-- Using TOP/BOTTOM with STDDEV_SAMP to find outliers > 2.5 standard deviations
SELECT Measurements.TD_TIMECODE, Measurements.ObservationID, Measurements.Magnitude
FROM (
    SELECT TSQ.TCR, TSQ.ObservationID, TSQ.Top_Bottom_Magnitude,
           TSQ.Avg_Magnitude, TSQ.STD
    FROM (
        SELECT $TD_TIMECODE_RANGE AS TCR, ObservationID,
               STDDEV_SAMP(magnitude) AS STD,
               AVG(magnitude) AS Avg_Magnitude,
               TOP(1, magnitude) AS Top_Bottom_Magnitude
        FROM Measurements
        WHERE TD_TIMECODE BETWEEN TIMESTAMP '2017-04-24 08:00:00'
                             AND TIMESTAMP '2017-04-24 10:00:00'
        GROUP BY TIME(MINUTES(30) AND ObservationID) USING TIMECODE(TD_TIMECODE)
        UNION
        SELECT $TD_TIMECODE_RANGE AS TCR, ObservationID,
               STDDEV_SAMP(magnitude) AS STD,
               AVG(magnitude) AS Avg_Magnitude,
               BOTTOM(1, magnitude) AS Top_Bottom_Magnitude
        FROM Measurements
        WHERE TD_TIMECODE BETWEEN TIMESTAMP '2017-04-24 08:00:00'
                             AND TIMESTAMP '2017-04-24 10:00:00'
        GROUP BY TIME(MINUTES(30) AND ObservationID) USING TIMECODE(TD_TIMECODE)
    ) AS TSQ
    WHERE (ABS(TSQ.Top_Bottom_Magnitude - TSQ.Avg_Magnitude) > (2.5 * TSQ.STD))
       OR (ABS(TSQ.Avg_Magnitude - TSQ.Top_Bottom_Magnitude) > (2.5 * TSQ.STD))
) AS TSQ2, Measurements
WHERE Measurements.Magnitude = TSQ2.Top_Bottom_Magnitude;
```

### DELTA_T — Min/Max Temperature Timing (Deterministic)

```sql
SELECT $TD_TIMECODE_RANGE, $TD_GROUP_BY_TIME, t1.BUOYID,
       DELTA_T((WHERE TEMPERATURE = MIN_TEMP), (WHERE TEMPERATURE = MAX_TEMP))
FROM (
    SELECT MIN(TEMPERATURE) AS MIN_TEMP, MAX(TEMPERATURE) AS MAX_TEMP, BUOYID
    FROM OCEAN_BUOYS_DELTA_T
    WHERE TD_TIMECODE BETWEEN TIMESTAMP '2014-01-06 08:00:00'
                         AND TIMESTAMP '2014-01-06 10:30:00'
    GROUP BY TIME (MINUTES(30) AND BUOYID)
) AS t1, OCEAN_BUOYS_DELTA_T
WHERE t1.buoyid = OCEAN_BUOYS_DELTA_T.buoyid
GROUP BY TIME(MINUTES(30) AND t1.buoyid)
ORDER BY t1.buoyid;
```

### Deterministic Results Best Practices

- The timecode field used for ordering must be directly correlated to the values being aggregated
- Be cautious when joining PTI with non-PTI tables
- ORDER BY only affects client output order, not DELTA_T input ordering
- Extract sample data to understand TIMECODE correlations
- FILL(PREV) and FILL(NEXT) can also produce non-deterministic results

---

## 21. Time Series Data Categories

| Class | Name | Description | Example |
|-------|------|-------------|---------|
| I | 7/24 Infinite Time Series | Continuous, ongoing data collection | River monitoring buoys, building sensors |
| II | Time Series with Logical Overlay | Defined start/end with logical progression | Aircraft flights, automobile trips |
| III | Fixed Size (Scientific Trace) | Fixed-length traces | Seismic traces, ultrasound scans, electron microscope |

---

## 22. Troubleshooting Reference

### Error 3706 — CREATE TABLE fails with partial auto-generated columns
**Cause:** Specified some but not all applicable auto-generated columns.
**Fix:** Specify all of TD_TIMEBUCKET, TD_TIMECODE, and TD_SEQNO (if SEQUENCED).

### Error 4358 — TD_TIMECODE|TD_SEQNO out of range
**Cause:** TD_TIMECODE before Time Zero, or TD_SEQNO exceeds maximum.
**Fix:** Use `EXEC DBC.TD_TIMESERIES_RANGE('table_name')` to find valid ranges.

### Warning 4001 — Time Series Auxiliary Cache Warning
**Cause:** Multiple aggregate functions (e.g., two MODE calls) each return multiple rows per time bucket.
**Fix:** Separate aggregate functions into individual queries. Results with multiple multi-result aggregates are non-deterministic.

### Non-deterministic DELTA_T/FIRST/LAST results
**Cause:** Timecode column not directly correlated to aggregated values (often from joins with derived tables).
**Fix:** Ensure the USING TIMECODE column comes from the same table as the data being aggregated; correlate tables properly via joins.