# Teradata PERIOD Data Type and Temporal Tables

> Source: Teradata SQL Data Types and Literals; Teradata Temporal Table Support; 541-0009027 — Partitioning Enhancements; TDN0009627 — Teradata Time Series

---

## 1. PERIOD Data Type

A PERIOD represents a time span with an inclusive **begin** and exclusive **end** bound — a half-open interval `[begin, end)`.

| Type | Element Type | Storage |
|------|-------------|---------|
| `PERIOD(DATE)` | DATE | 8 bytes |
| `PERIOD(TIME)` | TIME | 12 bytes |
| `PERIOD(TIME WITH TIME ZONE)` | TIME WITH TIME ZONE | 16 bytes |
| `PERIOD(TIMESTAMP)` | TIMESTAMP | 20 bytes |
| `PERIOD(TIMESTAMP WITH TIME ZONE)` | TIMESTAMP WITH TIME ZONE | 24 bytes |

### Constructors and Accessors

```sql
-- Two-argument constructor
SELECT PERIOD(DATE '2024-01-01', DATE '2025-01-01');

-- Open-ended period (end = max value of element type)
SELECT PERIOD(DATE '2024-06-15', UNTIL_CHANGED);

-- BEGIN/END accessors extract bounds
SELECT BEGIN(job_period) AS start_date, END(job_period) AS end_date
FROM employment WHERE emp_id = 1001;

-- Duration calculation
SELECT emp_id, (END(job_period) - BEGIN(job_period)) DAY(5) AS tenure_days
FROM employment;
```

### Column Definition

```sql
CREATE TABLE employment (
    emp_id     INTEGER NOT NULL,
    dept_id    INTEGER,
    job_title  VARCHAR(50),
    job_period PERIOD(DATE) NOT NULL,
    salary     DECIMAL(10,2)
) PRIMARY INDEX (emp_id);
```

---

## 2. PERIOD Predicates

| Predicate | Meaning |
|-----------|---------|
| `CONTAINS` | Period contains a value or another period |
| `OVERLAPS` | Two periods share at least one common point |
| `MEETS` | END of first equals BEGIN of second (adjacent) |
| `PRECEDES` | First ends before or when second starts |
| `SUCCEEDS` | First starts after or when second ends |
| `LDIFF` | Portion of first period before second |
| `RDIFF` | Portion of first period after second |

```sql
-- Active policies covering today
SELECT * FROM policies WHERE coverage_period CONTAINS CURRENT_DATE;

-- Contracts overlapping Q1 2025
SELECT * FROM contracts
WHERE duration OVERLAPS PERIOD(DATE '2025-01-01', DATE '2025-04-01');

-- Adjacent employment records with no gap
SELECT a.emp_id, a.job_title AS prev_job, b.job_title AS next_job
FROM employment a JOIN employment b
  ON a.emp_id = b.emp_id AND a.job_period MEETS b.job_period;

-- Periods strictly before a reference
SELECT * FROM promotions
WHERE promo_period PRECEDES PERIOD(DATE '2024-01-01', DATE '2024-04-01');
```

---

## 3. PERIOD Functions

### P_INTERSECT

Returns the overlapping portion of two periods, or NULL if no overlap.

```sql
SELECT contract_id,
       duration P_INTERSECT PERIOD(DATE '2025-01-01', DATE '2025-07-01') AS overlap
FROM contracts
WHERE duration P_INTERSECT PERIOD(DATE '2025-01-01', DATE '2025-07-01') IS NOT NULL;
```

### P_NORMALIZE

Merges adjacent or overlapping periods into the smallest set of non-overlapping periods.

```sql
SELECT customer_id, P_NORMALIZE(coverage_period) AS merged_period
FROM policies GROUP BY customer_id;
```

---

## 4. NORMALIZE ON Clause

Merges rows with adjacent or overlapping PERIOD values into consolidated rows.

```sql
-- Merge overlapping coverage per customer
SELECT customer_id, coverage_period AS normalized_period
FROM insurance_policies NORMALIZE ON coverage_period;

-- Merge per employee per department
SELECT emp_id, dept_id, job_period AS merged_period
FROM employment_history NORMALIZE ON job_period GROUP BY emp_id, dept_id;
```

### Automatic Normalization on Table Definition

```sql
CREATE TABLE flight_sensors (
    FlightID   INTEGER,
    SensorID   INTEGER,
    SensorData INTEGER,
    duration   PERIOD(TIMESTAMP(6)),
    NORMALIZE ALL BUT(SensorData) ON duration ON MEETS OR OVERLAPS
) PRIMARY TIME INDEX (TIMESTAMP(6), DATE '2016-10-15',
    COLUMNS(FlightID, SensorID), NONSEQUENCED);
-- Inserts with overlapping periods and same SensorData are auto-merged
```

---

## 5. EXPAND ON Clause

Expands each PERIOD value into multiple rows — one per unit of time. The inverse of NORMALIZE.

```sql
-- Expand price periods into one row per day
SELECT product_id, price, BEGIN(price_period) AS effective_date
FROM product_pricing EXPAND ON price_period BY INTERVAL '1' DAY;

-- Monthly employee headcount from period data
SELECT BEGIN(emp_period) AS month_start, COUNT(*) AS headcount
FROM employee_roster
EXPAND ON emp_period AS emp_period BY INTERVAL '1' MONTH
GROUP BY month_start ORDER BY month_start;

-- Hourly expansion of sensor readings
SELECT sensor_id, reading_val, BEGIN(active_span) AS hour_ts
FROM sensor_readings EXPAND ON active_span BY INTERVAL '1' HOUR;
```

**Use cases:** daily price snapshots, headcount reporting, occupancy analysis, regulatory point-in-time views.

---

## 6. Temporal Tables

Temporal tables track when data is valid (business time) and/or when it was recorded (system time).

| Type | Dimension | Managed By | Column Clause |
|------|-----------|-----------|---------------|
| **ValidTime** | Business validity | Application | `AS VALIDTIME` |
| **TransactionTime** | System recording | System (auto) | `AS TRANSACTIONTIME` |
| **Bitemporal** | Both | Both | Both columns |

```sql
-- ValidTime table
CREATE TABLE policy_vt (
    policy_id   INTEGER NOT NULL,
    customer_id INTEGER,
    policy_type CHAR(2),
    validity    PERIOD(DATE) NOT NULL AS VALIDTIME
) PRIMARY INDEX (policy_id);

-- TransactionTime table
CREATE TABLE policy_tt (
    policy_id    INTEGER NOT NULL,
    customer_id  INTEGER,
    policy_type  CHAR(2),
    sys_duration PERIOD(TIMESTAMP(6) WITH TIME ZONE) NOT NULL AS TRANSACTIONTIME
) PRIMARY INDEX (policy_id);

-- Bitemporal table
CREATE TABLE policy_bt (
    policy_id    INTEGER NOT NULL,
    customer_id  INTEGER,
    policy_type  CHAR(2),
    validity     PERIOD(DATE) NOT NULL AS VALIDTIME,
    sys_duration PERIOD(TIMESTAMP(6) WITH TIME ZONE) NOT NULL AS TRANSACTIONTIME
) PRIMARY INDEX (policy_id);
```

### Key Rules

- At most **one** VALIDTIME column and **one** TRANSACTIONTIME column per table
- TRANSACTIONTIME must be `PERIOD(TIMESTAMP WITH TIME ZONE)` — system-managed
- VALIDTIME can be `PERIOD(DATE)`, `PERIOD(TIMESTAMP)`, or `PERIOD(TIMESTAMP WITH TIME ZONE)`
- PTI tables **cannot** be temporal; they are mutually exclusive
- Column-partitioned tables **can** include temporal columns

---

## 7. Temporal DML Qualifiers

### CURRENT — Rows Valid Now

```sql
CURRENT VALIDTIME
SELECT * FROM policy_vt WHERE customer_id = 5001;

CURRENT VALIDTIME AND CURRENT TRANSACTIONTIME
SELECT * FROM policy_bt WHERE policy_id = 101;
```

### SEQUENCED — Rows Valid in a Range

Automatically adjusts period boundaries to fit the qualification range. Updates/deletes split rows at range boundaries.

```sql
SEQUENCED VALIDTIME PERIOD(DATE '2024-01-01', DATE '2025-01-01')
SELECT * FROM policy_vt WHERE customer_id = 5001;

SEQUENCED VALIDTIME PERIOD(DATE '2025-07-01', UNTIL_CHANGED)
UPDATE policy_vt SET policy_type = 'PR' WHERE policy_id = 101;

SEQUENCED VALIDTIME PERIOD(DATE '2024-06-01', DATE '2024-12-31')
DELETE FROM policy_vt WHERE policy_id = 202;
```

### NONSEQUENCED — Raw Access, No Temporal Logic

Treats temporal columns as ordinary PERIOD columns. For data correction and admin tasks.

```sql
-- See ALL rows including full history
NONSEQUENCED VALIDTIME SELECT * FROM policy_vt;

-- Directly fix a validity period
NONSEQUENCED VALIDTIME UPDATE policy_vt
SET validity = PERIOD(DATE '2023-01-01', DATE '2024-01-01')
WHERE policy_id = 303 AND validity = PERIOD(DATE '2023-01-15', DATE '2024-01-01');

-- Insert with explicit period
NONSEQUENCED VALIDTIME INSERT INTO policy_vt
VALUES (404, 6001, 'LF', PERIOD(DATE '2020-01-01', DATE '2022-12-31'));
```

### Qualifier Summary

| Qualifier | SELECT | UPDATE/DELETE | INSERT |
|-----------|--------|---------------|--------|
| **CURRENT** | Rows valid now | Affects rows valid now | N/A |
| **SEQUENCED** | Clips periods to range | Splits rows at boundaries | With specified validity |
| **NONSEQUENCED** | All rows, plain data | Direct modification | Explicit period values |

---

## 8. Temporal Partitioning

Separate current from historical rows using `CASE_N` on period endpoints. Use `ALTER TABLE ... TO CURRENT` to refresh partition boundaries.

```sql
CREATE MULTISET TABLE policy (
    policy_id    INTEGER,
    customer_id  INTEGER,
    policy_type  CHAR(2) NOT NULL,
    validity     PERIOD(DATE) NOT NULL AS VALIDTIME,
    sys_duration PERIOD(TIMESTAMP(6) WITH TIME ZONE) NOT NULL AS TRANSACTIONTIME
) PRIMARY INDEX (policy_id)
  PARTITION BY CASE_N(
      (END(validity) IS NULL OR END(validity) >= CURRENT_DATE AT '-12:59')
          AND END(sys_duration) >= CURRENT_TIMESTAMP,
      END(validity) < CURRENT_DATE AT '-12:59'
          AND END(sys_duration) >= CURRENT_TIMESTAMP,
      END(sys_duration) < CURRENT_TIMESTAMP);

ALTER TABLE policy TO CURRENT;  -- run periodically
```

**Best Practice:** Run `ALTER TABLE ... TO CURRENT` regularly. Delayed execution causes history rows to accumulate in the current partition, degrading query performance.

---

## 9. Temporal Constraints

`NONSEQUENCED VALIDTIME` constraints enforce no overlapping validity periods for the same key.

```sql
CREATE TABLE policy_vt (
    policy_id INTEGER NOT NULL,
    customer_id INTEGER,
    validity  PERIOD(DATE) NOT NULL AS VALIDTIME,
    NONSEQUENCED VALIDTIME UNIQUE (policy_id)
) PRIMARY INDEX (policy_id);
```

- Enforced via unique secondary index or system-defined join index
- A nonunique PI must not be on the same columns as a NONSEQUENCED VALIDTIME constraint

---

## 10. Practical Example: Insurance Policy Lifecycle

```sql
-- Create table
CREATE TABLE insurance_policies (
    policy_id    INTEGER NOT NULL,
    customer_id  INTEGER NOT NULL,
    coverage_amt DECIMAL(12,2),
    premium      DECIMAL(8,2),
    validity     PERIOD(DATE) NOT NULL AS VALIDTIME,
    NONSEQUENCED VALIDTIME UNIQUE (policy_id)
) PRIMARY INDEX (policy_id);

-- New policy, open-ended
INSERT INTO insurance_policies
VALUES (1001, 5001, 500000.00, 1200.00, PERIOD(DATE '2025-01-01', UNTIL_CHANGED));

-- Mid-year premium increase (SEQUENCED UPDATE splits the row)
SEQUENCED VALIDTIME PERIOD(DATE '2025-07-01', UNTIL_CHANGED)
UPDATE insurance_policies SET premium = 1350.00 WHERE policy_id = 1001;

-- View full history — returns two rows:
--   validity=('2025-01-01','2025-07-01') premium=1200
--   validity=('2025-07-01',UNTIL_CHANGED) premium=1350
NONSEQUENCED VALIDTIME SELECT * FROM insurance_policies WHERE policy_id = 1001;

-- Normalize overlapping supplier prices
SELECT product_id, price, price_period AS clean_period
FROM raw_pricing NORMALIZE ON price_period GROUP BY product_id, price;
```

---

## 11. PERIOD vs. PTI

| Feature | PERIOD / Temporal Tables | Primary Time Index (PTI) |
|---------|------------------------|--------------------------|
| Purpose | Business validity & system time tracking | Time series storage & analytics |
| Temporal qualifiers | CURRENT, SEQUENCED, NONSEQUENCED | Not supported |
| NORMALIZE / EXPAND ON | Supported | Supported |
| Auto-generated columns | None | TD_TIMEBUCKET, TD_TIMECODE, TD_SEQNO |
| Combined use | Cannot combine with PTI | Cannot combine with temporal |
| Best for | Slowly changing data, audit trails, policy history | High-frequency sensor/IoT data |
