# NULL Handling and Request Cache Reference

> Sources: SQL Fundamentals (B035-1141-111A, Release 14.0), Parameterized Request Cache Enhancements (541-0006539-A02)

---

## 1. NULL Handling Rules

### NULL in Arithmetic Operations

- If **any** operand of an arithmetic operator (`+`, `-`, `*`, `/`) or function (`ABS`, `SQRT`, etc.) is NULL, the result is **NULL**
- Exception: `ZEROIFNULL(NULL)` returns **0**

```sql
SELECT 5 + NULL;          -- Result: NULL
SELECT NULL * 100;         -- Result: NULL
SELECT ABS(NULL);          -- Result: NULL
SELECT ZEROIFNULL(NULL);   -- Result: 0
```

### NULL in Comparisons

- If either operand of a comparison operator is NULL, the result is **UNKNOWN** (not TRUE or FALSE)
- Using `= NULL` or `<> NULL` returns an error recommending IS NULL / IS NOT NULL

```sql
-- All of these produce UNKNOWN (effectively FALSE in WHERE):
5 = NULL
5 <> NULL
NULL = NULL
NULL <> NULL
5 = NULL + 5

-- Correct approach:
SELECT name FROM employee WHERE deptno IS NULL;
SELECT name FROM employee WHERE jobtitle IS NOT NULL;
```

### IS NULL vs = NULL

- `= NULL` is a **value comparison** — but NULL has no value, so it is undefined and returns an error
- `IS NULL` is an **existence condition** — tests whether a column contains a null placeholder
- Always use `IS NULL` or `IS NOT NULL`, never comparison operators with NULL

### Searching for NULLs and Non-NULLs Together

The NULL condition must be separate from other conditions:

```sql
-- Correct: find employees with title 'Manager', 'Vice Pres', or NULL
SELECT name, jobtitle FROM employee
WHERE jobtitle IN ('Manager', 'Vice Pres') OR jobtitle IS NULL;

-- Including NULL in an IN list has NO effect because NULL never equals NULL or any value
```

### NULL in Aggregates

- **COUNT(*)** — **includes** NULLs (counts all rows regardless of nulls)
- **All other aggregates** (SUM, AVG, MIN, MAX, COUNT(column)) — **ignore** NULLs in their arguments

This causes apparent anomalies:

```sql
-- With NULLs in column A or B:
SUM(A) + SUM(B) <> SUM(A + B)   -- virtually always TRUE

-- Workarounds:
-- 1. Define columns as NOT NULL DEFAULT 0
-- 2. Use ZEROIFNULL inside the aggregate:
SELECT SUM(ZEROIFNULL(A) + ZEROIFNULL(B)) FROM t;
```

### NULL Sorting

| Mode | NULL Sort Position |
|---|---|
| **Teradata mode** | NULL sorts as the **lowest** value |
| **ANSI mode** | NULL sorts as the **highest** value |

- If any row has NULL in the grouped column, all NULL rows are placed into one group
- Sorting behavior varies across RDBMS vendors

### NULL and Unique Indexes

Teradata treats NULLs in unique indexes as if they are **equal** (not UNKNOWN):

- **Single-column unique index:** only ONE row may have NULL for the index value
- **Multicolumn unique index:** no two rows can have NULLs in the same columns AND equal non-null values in the other columns

Example for a two-column unique index — these rows can coexist:

| Column 1 | Column 2 |
|---|---|
| 1 | NULL |
| NULL | 1 |
| NULL | NULL |

An attempt to insert a row matching any existing combination causes a uniqueness violation.

### NULL and CASE Expressions

```sql
-- NULL and null expressions are valid as CASE test expressions
-- Use searched CASE with IS NULL for testing:
SELECT CASE
  WHEN status IS NULL THEN 'Unknown'
  WHEN status = 'A' THEN 'Active'
  ELSE 'Other'
END FROM orders;

-- NULL is valid as a THEN clause result:
SELECT CASE WHEN orders = 10 THEN NULL END FROM sales_tbl;
```

### COALESCE / NULLIF / ZEROIFNULL

```sql
-- COALESCE: returns first non-null argument; NULL only if ALL arguments are NULL
SELECT COALESCE(phone_home, phone_work, phone_cell, 'No Phone') FROM contacts;

-- NULLIF: returns NULL if both arguments are equal, otherwise returns first argument
SELECT NULLIF(actual_price, list_price) FROM products;
-- Equivalent to: CASE WHEN actual_price = list_price THEN NULL ELSE actual_price END

-- ZEROIFNULL: returns 0 if argument is NULL, otherwise returns the argument
SELECT ZEROIFNULL(bonus) FROM employee;
```

### NULL Replacement on Client Return (Record Mode)

When returning data in record mode, NULLs are replaced with substitute values:

| Data Type | Substitute |
|---|---|
| CHARACTER(n) | Pad character(s) |
| DATE, TIME, TIMESTAMP, INTERVAL | Pad character |
| BYTE(n) | Binary zero byte(s) |
| VARBYTE(n), VARCHAR(n) | 0-length string |
| INTEGER, SMALLINT, BIGINT, BYTEINT, FLOAT, DECIMAL | 0 |
| PERIOD(DATE) | 8 binary zero bytes |

In IndicData mode (normal CLI access), additional flags distinguish NULLs from valid values. BTEQ displays NULLs as `?`.

### DateTime and Interval NULLs

A DateTime or Interval value is either atomically null or not null — you cannot have a partially null interval (e.g., YEAR is null but MONTH is not).

---

## 2. Three-Valued Logic

SQL uses three-valued logic: TRUE, FALSE, and UNKNOWN.

### AND Truth Table

| A | B | A AND B |
|---|---|---|
| TRUE | TRUE | TRUE |
| TRUE | FALSE | FALSE |
| TRUE | UNKNOWN | UNKNOWN |
| FALSE | TRUE | FALSE |
| FALSE | FALSE | FALSE |
| FALSE | UNKNOWN | FALSE |
| UNKNOWN | TRUE | UNKNOWN |
| UNKNOWN | FALSE | FALSE |
| UNKNOWN | UNKNOWN | UNKNOWN |

### OR Truth Table

| A | B | A OR B |
|---|---|---|
| TRUE | TRUE | TRUE |
| TRUE | FALSE | TRUE |
| TRUE | UNKNOWN | TRUE |
| FALSE | TRUE | TRUE |
| FALSE | FALSE | FALSE |
| FALSE | UNKNOWN | UNKNOWN |
| UNKNOWN | TRUE | TRUE |
| UNKNOWN | FALSE | UNKNOWN |
| UNKNOWN | UNKNOWN | UNKNOWN |

### NOT Truth Table

| A | NOT A |
|---|---|
| TRUE | FALSE |
| FALSE | TRUE |
| UNKNOWN | UNKNOWN |

Key implications:
- `WHERE col = NULL` → UNKNOWN → row excluded (NOT returned)
- `WHERE NOT (col = NULL)` → NOT UNKNOWN → UNKNOWN → row still excluded
- A conditional expression with a null component evaluates to UNKNOWN

---

## 3. Parameterized Request Cache

> Source: 541-0006539-A02, Parameterized Request Cache Enhancements (TD 12.0+)

### Purpose

Prior to TD 12.0, the Parser cached all parameterized requests and reused the plan regardless of USING values. Since the Optimizer didn't know the actual values, it could miss optimizations like:
- **Partition elimination** on PPI tables
- **Join index selection** (sparse JIs)
- **NUSI selection** based on selectivity

TD 12.0 introduced **USING value peeking** — the Parser peeks at parameterized values and decides whether to generate a value-specific or generic plan.

### Specific vs Generic Plans

| Plan Type | Description |
|---|---|
| **Specific plan** | Generated using actual USING values — enables partition elimination, JI selection |
| **Generic plan** | Generated without peeking at values — same as pre-12.0 behavior |
| **SPECALWAYS** | Decision to always generate specific plans (re-parse each execution) |
| **GENALWAYS** | Decision to cache and reuse the generic plan (pre-12.0 behavior) |

### Decision Process

1. **First submission:** Parser peeks at USING values, generates a **specific plan**, caches it. Dispatcher stores parsing CPU time and runtime.
2. **Second submission:** Parser generates a **generic plan** (without peeking). Dispatcher compares CPU times.
3. **Decision:** Based on parsing overhead vs runtime benefit:
   - If specific plan runtime benefit outweighs parsing cost → **SPECALWAYS**
   - If parsing overhead is too high relative to benefit → **GENALWAYS**
   - Decision persists until the cache entry is purged

### Immediately-Cached Queries (No Peeking Needed)

These queries are cached immediately because the plan is optimal for any USING values:

| Condition | Single Table in WHERE | Multiple Tables in WHERE |
|---|---|---|
| AND'ed on UPI/USI/NUPI/PPI column | **Immediately cached** | Not immediately cached |
| OR'ed on UPI/USI/NUPI/PPI column | Not immediately cached | Not immediately cached |
| AND'ed/OR'ed on NUSI column | Not immediately cached | Not immediately cached |

```sql
-- Immediately cached (single table, AND'ed equality on PI):
USING (x INT) SELECT * FROM CallDetail WHERE Customer_id = :x;
USING (x INT) SELECT * FROM SalesHistory WHERE product_code = :x AND store_number = 56;

-- NOT immediately cached (OR'ed condition):
USING (x INT) SELECT * FROM SalesHistory WHERE product_code = :x OR store_number = 56;

-- NOT immediately cached (multi-table WHERE):
USING (x INT) SELECT * FROM t1, t2 WHERE t1.c1 = t2.c1 AND t1.c1 = :x;
```

### CURRENT_DATE Resolution

Starting in TD 12.0, `CURRENT_DATE` / `DATE` is resolved to the actual date value **before** the Optimizer phase for all requests. Benefits:

**Partition elimination with CURRENT_DATE:**
```sql
-- TD 12.0+: resolves CURRENT_DATE, eliminates to 5 partitions
EXPLAIN SELECT * FROM ordertbl_ppi
WHERE o_orderdate < CURRENT_DATE AND o_orderdate > CURRENT_DATE - 30;
-- Output: "RETRIEVE step from 5 partitions of ordertbl_ppi"

-- Pre-12.0: no partition elimination
-- Output: "RETRIEVE step from all partitions of ordertbl_ppi"
```

**Join index selection with CURRENT_DATE:**
```sql
-- TD 12.0+: resolves CURRENT_DATE, picks up join index
EXPLAIN SELECT o_orderkey, o_custkey, o_orderstatus, o_totalprice, o_orderdate, ca_acctkey
FROM ordertbl, custaccounts
WHERE ordertbl.o_custkey = custaccounts.ca_custkey AND o_orderdate < CURRENT_DATE;
-- Output: "RETRIEVE step from ORDER_CUST_JI"

-- Pre-12.0: join index not picked, full table scan + merge join
```

**Cache invalidation:** When the calendar date changes, Teradata automatically recognizes cached plastic steps are no longer valid, purges the old entry, and generates a new plan.

### EXPLAIN Output Differences

- **Specific plan:** USING variable references show the **actual constant value** (e.g., `P_SIZE < 800`)
- **Generic plan:** USING variable references show the **variable name** (e.g., `P_SIZE < :x`)

```sql
-- Specific plan EXPLAIN (with value peeking, x=800):
USING(x INT) SELECT * FROM product_PPI WHERE p_size < :x;
-- "RETRIEVE step from 7 partitions... P_SIZE < 800"

-- Generic plan EXPLAIN (without peeking):
-- "RETRIEVE step from Product_PPI by way of an all-rows scan... P_SIZE < :x"
```

### DisablePeekUsing DBS Control

To revert to pre-12.0 behavior (no value peeking):

```
-- DBS Control, Performance Group:
DisablePeekUsing = TRUE    -- disable peeking (default: FALSE)
```

### Two-Time Parsing Cost

A parameterized query may be parsed **twice** before a GENALWAYS/SPECALWAYS decision is taken. This adds parsing overhead compared to pre-12.0 where parsing occurred only once. Queries with very high parsing cost that run only twice may show performance degradation on the second execution.

### Value-Based Decision Limitations

- The GENALWAYS/SPECALWAYS decision is USING-value dependent and may not produce the same decision for different USING values
- **Lost opportunity:** GENALWAYS decision when subsequent data would have benefited from a specific plan (same as pre-12.0)
- **Unnecessary overhead:** SPECALWAYS decision where specific plans provide no benefit, causing extra parsing on each execution

---

## 4. System Limits

> Source: SQL Fundamentals, Appendix C (Release 14.0)

### Table and Column Limits

| Parameter | Limit |
|---|---|
| Maximum columns per base data table or view | **2,048** |
| Maximum columns created over lifetime of a table | **2,560** |
| Maximum row size | **64,256 bytes** |
| Maximum non-LOB column size (NPPI table) | **64,244 bytes** |
| Maximum non-LOB column size (PPI table) | **64,240 bytes** |
| Maximum rows per base data table | Limited only by disk capacity |
| Maximum table header size | **1 MB** |
| Maximum LOB columns per base table | **32** |
| Maximum UDT columns per base table | **~1,600** |
| Maximum columns per primary index | **64** |
| Maximum object name size | **30 bytes** (LATIN/KANJI1) |
| Maximum values multi-value compressed per column | **255** |
| Maximum table-level CHECK constraints per table | **100** |
| Maximum referential integrity constraints per table | **64** |
| Maximum columns per foreign/parent key | **64** |

### Index Limits

| Parameter | Limit |
|---|---|
| Maximum secondary + hash + join indexes per table | **32** |
| Maximum columns per secondary index | **64** |
| Maximum columns per single table in hash/join index | **64** |
| Maximum columns in uncompressed join index | **2,048** |
| Maximum columns in compressed join index | **128** |
| Maximum reference indexes per table | **64** |
| Maximum statistics sets (multicolumn) per table | **32** (31 if PARTITION stats collected) |

### SQL Request Limits

| Parameter | Limit |
|---|---|
| Maximum SQL text size per request | **1 MB** |
| Maximum tables/single-table views per query block (join) | **128** |
| Maximum subquery nesting levels | **64** |
| Maximum tables per subquery | **128** |
| Maximum columns per ORDER BY clause | **64** |
| Maximum columns per GROUP BY clause | **64** |
| Maximum fields in a USING row descriptor | **2,543** |
| Maximum OR'ed conditions or IN list values per request | **1,048,576** |
| Maximum entries in an IN list | Unlimited (bounded by SQL text size) |
| Maximum characters per string constant | **31,000** |
| Maximum SQL activity count | **4,294,967,295** rows |
| Maximum SQL title size | **60 characters** |

### Stored Procedure and Macro Limits

| Parameter | Limit |
|---|---|
| Maximum parameters per macro | **2,048** |
| Maximum expanded text for macros/views | **2 MB** |
| Maximum parameters per SQL stored procedure | **256** |
| Maximum SQL text size in stored procedure | **64 KB** |
| Maximum open cursors per stored procedure | **15** |
| Maximum dynamic SQL requests per stored procedure | **15** |
| Maximum length of dynamic SQL request in SP | **64,256 bytes** |
| Maximum nested CALL statements | **15** |
| Maximum parameters per UDF | **128** |
| Maximum parameters per external stored procedure (C/C++) | **256** |
| Maximum parameters per external stored procedure (Java) | **255** |

### Session Limits

| Parameter | Limit |
|---|---|
| Maximum sessions per PE | **120** |
| Maximum sessions per gateway | **1,200** certified (default 600) |
| Maximum active result spool files per session | **16** |
| Maximum parallel steps per request | **20** |
| Maximum materialized global temp tables per session | **2,000** |
| Maximum volatile tables per session | **1,000** |
| Maximum open cursors per embedded SQL program | **16** |

### System-Wide Limits

| Parameter | Limit |
|---|---|
| Maximum databases + users | **4.2 × 10⁹** |
| Maximum database objects per system lifetime | **1,073,741,824** |
| Maximum AMP vprocs per system | **16,200** |
| Maximum PE vprocs per system | **2,048** |
| Maximum vprocs per system (all types) | **30,720** |
| Maximum vprocs per node | **127** |
| Maximum nodes per system | **1,024** |
| Maximum parse tree segments per request | **12,000** |
| Maximum data capacity | **~12 TB/AMP** |
| Maximum data block size | **11,894,784 bytes** |
| Maximum CLIv2 parcels per message | **256** |
| Maximum message size | **~65,000 bytes** |
| Number of hash buckets (selectable) | **65,536** or **1,048,576** |
| Number of hash values | **4.2 × 10⁹** |

### Partitioning Limits

| Parameter | Limit |
|---|---|
| Maximum combined partition number (2-byte) | **65,535** |
| Maximum combined partition number (8-byte) | **9,223,372,036,854,775,807** |
| Maximum partitioning levels (2-byte) | **15** |
| Maximum partitioning levels (8-byte) | **62** |
| Maximum column partitions per table | **2,050** (including 2 internal) |
| Maximum partitions for CASE_N expression | **2,147,483,647** |
| Maximum hash join partitions | **50** |
