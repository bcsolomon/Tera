# Teradata Numeric and Character Data Types

> Source: B035-1141-111A — Teradata SQL Fundamentals; SQL Data Types and Literals; Teradata Database documentation

---

## 1. Integer Types

### Storage and Ranges

| Type | Storage | Minimum | Maximum | Notes |
|------|---------|---------|---------|-------|
| `BYTEINT` | 1 byte | -128 | 127 | Smallest integer; useful for flags and small codes |
| `SMALLINT` | 2 bytes | -32,768 | 32,767 | |
| `INTEGER` / `INT` | 4 bytes | -2,147,483,648 | 2,147,483,647 | Most common integer type |
| `BIGINT` | 8 bytes | -9,223,372,036,854,775,808 | 9,223,372,036,854,775,807 | Large counters, surrogate keys |

### Integer Literals

```sql
SELECT 42;          -- INTEGER
SELECT 3000000000;  -- exceeds INTEGER range → treated as DECIMAL
SELECT '7F'XI1;     -- BYTEINT value 127 (hex literal)
SELECT '7FFFFFFF'XI4;  -- INTEGER value 2147483647
```

### DATE Internal Representation

Teradata stores DATE as a 4-byte INTEGER using the formula:

```
(year - 1900) * 10000 + month * 100 + day
```

```sql
-- Demonstrate the internal integer format
SELECT CAST(CURRENT_DATE AS INTEGER);
-- 2026-04-30 → (2026 - 1900) * 10000 + 4 * 100 + 30 = 1260430

-- This enables integer arithmetic on dates
SELECT CURRENT_DATE - 30;  -- 30 days ago (integer subtraction)
```

---

## 2. DECIMAL / NUMERIC Type

`DECIMAL(p,s)` and `NUMERIC(p,s)` are synonyms. They store exact fixed-point numbers.

- **p** (precision): total number of digits, range 1–38
- **s** (scale): digits to the right of decimal point, range 0–p
- Default: `DECIMAL` with no arguments = `DECIMAL(5,0)`

### Precision-to-Storage Mapping

| Precision (p) | Storage (bytes) | Example |
|---------------|----------------|---------|
| 1–2 | 1 | `DECIMAL(2,0)` — tiny counters |
| 3–4 | 2 | `DECIMAL(4,2)` — percentages |
| 5–9 | 4 | `DECIMAL(9,2)` — currency amounts |
| 10–18 | 8 | `DECIMAL(18,0)` — large identifiers |
| 19–38 | 16 | `DECIMAL(38,10)` — scientific precision |

### Arithmetic Result Precision

When arithmetic is performed on DECIMAL values, the result precision and scale follow these rules:

| Operation | Result Precision | Result Scale |
|-----------|-----------------|-------------|
| `a + b` or `a - b` | `max(p1-s1, p2-s2) + max(s1, s2) + 1` | `max(s1, s2)` |
| `a * b` | `p1 + p2` (capped at 38) | `s1 + s2` |
| `a / b` | Implementation-dependent (up to 38) | Determined by divisor scale |

If the result precision exceeds 38, a numeric overflow error occurs. Use CAST to control intermediate precision.

### Common DECIMAL Pitfalls

```sql
SELECT 1 / 3;            -- Returns 0 (integer division truncates)
SELECT 1.0 / 3;          -- Returns 0.33 (DECIMAL result)
SELECT 123.45;            -- Literal type: DECIMAL(5,2), not DECIMAL(38,2)

-- SUM can overflow: SUM of DECIMAL(9,2) returns DECIMAL(9,2)
SELECT SUM(CAST(amount AS DECIMAL(18,2))) FROM large_table;
```

---

## 3. FLOAT / REAL / DOUBLE PRECISION

All three are synonyms in Teradata. They all map to IEEE 754 double-precision (8 bytes).

| Type | Storage | Approximate Range | Significant Digits |
|------|---------|-------------------|-------------------|
| `FLOAT` | 8 bytes | ±2.2×10⁻³⁰⁸ to ±1.8×10³⁰⁸ | ~15–17 |
| `REAL` | 8 bytes | Same as FLOAT | Same |
| `DOUBLE PRECISION` | 8 bytes | Same as FLOAT | Same |

```sql
SELECT 1.23E4;       -- 12300.0 (E notation)
SELECT -5.67E-3;     -- -0.00567
```

**When to use FLOAT vs DECIMAL:** Use FLOAT for scientific/statistical data where approximate values are acceptable. Use DECIMAL for financial data requiring exact representation.

---

## 4. NUMBER Type (Oracle Compatibility)

`NUMBER` is an Oracle-compatible type with flexible precision and scale semantics.

| Declaration | Behavior |
|------------|----------|
| `NUMBER` | Floating-point decimal; no fixed precision/scale |
| `NUMBER(p)` | Fixed-point, scale = 0; equivalent to `DECIMAL(p,0)` |
| `NUMBER(p,s)` | Fixed-point; s can be negative (rounds to tens, hundreds, etc.) |
| `NUMBER(*,s)` | Precision = 38, scale = s |

### Storage

NUMBER uses 1–18 bytes (2 bytes more than the equivalent DECIMAL for the same precision, due to metadata overhead for the flexible format).

### Key Differences from DECIMAL

| Feature | DECIMAL(p,s) | NUMBER(p,s) |
|---------|-------------|-------------|
| Scale range | 0 to p | -128 to 127 (negative scale rounds to tens/hundreds) |
| Unqualified type | `DECIMAL` = `DECIMAL(5,0)` | `NUMBER` = floating decimal |
| Storage overhead | None | 2 additional bytes |
| ANSI standard | Yes | No (Oracle extension) |

---

## 5. Character Types

### CHAR(n) — Fixed-Length

- Maximum: 64,000 bytes
- Always padded with spaces to declared length
- Trailing spaces ignored in comparisons (ANSI mode) or significant (Teradata mode depends on collation)
- Default length: `CHAR` = `CHAR(1)`

### VARCHAR(n) — Variable-Length

- Maximum: 64,000 bytes
- Stores only actual characters plus 2-byte length prefix
- No padding
- Default: `VARCHAR` = `VARCHAR(1)`

### CLOB(n) — Character Large Object

- Maximum: ~2 GB
- Stored in separate LOB subtable (not inline with row)
- Cannot be used in PRIMARY INDEX, ORDER BY, GROUP BY, DISTINCT, or comparisons
- See `references/lob-reference.md` for full architecture

### GRAPHIC / VARGRAPHIC

| Type | Max Length | Description |
|------|-----------|-------------|
| `GRAPHIC(n)` | 32,000 characters | Fixed-length, 2 bytes per character |
| `VARGRAPHIC(n)` | 32,000 characters | Variable-length, 2 bytes per character |

Used primarily for legacy double-byte character data. Prefer `VARCHAR CHARACTER SET UNICODE` for new designs.

### Storage Comparison

```sql
CREATE TABLE char_demo (
    code       CHAR(10),         -- Always 10 bytes (LATIN)
    name_v     VARCHAR(100),     -- 2 + actual_length bytes
    name_u     VARCHAR(100) CHARACTER SET UNICODE,  -- 2 + actual_length * up to 3 bytes
    fixed_g    GRAPHIC(10)       -- Always 20 bytes (10 chars × 2 bytes)
);
```

---

## 6. Character Sets

### Server Character Sets

| Character Set | Bytes/Char | Description |
|--------------|-----------|-------------|
| `LATIN` | 1 | ISO 8859 Latin-1; Western European languages; default on most systems |
| `UNICODE` | Up to 3 | UTF-8 storage internally, UTF-16 for processing; full multilingual support |
| `GRAPHIC` | 2 | Fixed double-byte; used with GRAPHIC/VARGRAPHIC types |
| `KANJISJIS` | 1–2 | Japanese Shift-JIS encoding |

### Storage Multiplier Impact

The character set directly affects how many characters fit within the 64,000-byte column limit:

| Character Set | Max Characters in VARCHAR(n) | Reason |
|--------------|------------------------------|--------|
| LATIN | 64,000 | 1 byte per character |
| UNICODE | 21,333 | Up to 3 bytes per character |
| KANJISJIS | 32,000–64,000 | 1–2 bytes per character |

```sql
-- UNICODE VARCHAR: n specifies characters, but storage is bytes
CREATE TABLE t (name VARCHAR(100) CHARACTER SET UNICODE);
-- 'name' can hold 100 characters, consuming up to 300 bytes + 2-byte length prefix

-- Character set mismatch: implicit conversion
SELECT latin_col || unicode_col FROM t;
-- LATIN auto-converts to UNICODE (widening); no data loss
-- UNICODE to LATIN may lose characters → use explicit TRANSLATE
```

### Specifying Character Set

```sql
-- Column level
CREATE TABLE t (
    name_latin   VARCHAR(100) CHARACTER SET LATIN,
    name_utf     VARCHAR(100) CHARACTER SET UNICODE
);

-- Session default character set
SET SESSION CHARACTER SET UNICODE;

-- TRANSLATE function for explicit conversion
SELECT TRANSLATE(unicode_col USING UNICODE_TO_LATIN) FROM t;
SELECT TRANSLATE(latin_col USING LATIN_TO_UNICODE) FROM t;
```

### Character Set Mismatch Pitfalls

```sql
-- Pitfall: LATIN column cannot store non-Latin characters
INSERT INTO t (name_latin) VALUES ('日本語');
-- Error: Character conversion error (cannot translate to LATIN)

-- Fix: Use UNICODE column or TRANSLATE with ON ERROR
SELECT TRANSLATE(val USING UNICODE_TO_LATIN WITH ERROR) FROM t;
```

---

## 7. Type Conversion and CAST

### Explicit CAST Syntax

```sql
CAST(expression AS target_type [FORMAT 'format_string'])
```

```sql
SELECT CAST(123 AS VARCHAR(10));          -- '123'
SELECT CAST('456' AS INTEGER);            -- 456
SELECT CAST(123.456 AS DECIMAL(10,2));    -- 123.46 (rounded)
SELECT CAST('2026-04-30' AS DATE FORMAT 'YYYY-MM-DD');
SELECT CAST(1260430 AS DATE);             -- 2026-04-30 (internal integer form)
SELECT CAST(col1 AS CHAR(20));            -- Right-padded with spaces
```

### TRYCAST (Returns NULL on Failure)

```sql
-- TRYCAST does not raise an error on conversion failure
SELECT TRYCAST('abc' AS INTEGER);         -- NULL (not an error)
SELECT TRYCAST('2026-13-01' AS DATE);     -- NULL (invalid month)
SELECT TRYCAST('123.45' AS DECIMAL(5,2)); -- 123.45
```

### Implicit Conversion Matrix

Teradata performs implicit (automatic) type conversion in expressions and assignments when types differ. The general rule is **narrower types convert to wider types**.

| From → To | BYTEINT | SMALLINT | INTEGER | BIGINT | DECIMAL | FLOAT | NUMBER | VARCHAR |
|-----------|---------|----------|---------|--------|---------|-------|--------|---------|
| **BYTEINT** | — | Auto | Auto | Auto | Auto | Auto | Auto | CAST |
| **SMALLINT** | CAST | — | Auto | Auto | Auto | Auto | Auto | CAST |
| **INTEGER** | CAST | CAST | — | Auto | Auto | Auto | Auto | CAST |
| **BIGINT** | CAST | CAST | CAST | — | Auto | Auto | Auto | CAST |
| **DECIMAL** | CAST | CAST | CAST | CAST | Auto¹ | Auto | Auto | CAST |
| **FLOAT** | CAST | CAST | CAST | CAST | CAST | — | Auto | CAST |
| **NUMBER** | CAST | CAST | CAST | CAST | Auto | Auto | — | CAST |
| **VARCHAR** | CAST | CAST | CAST | CAST | CAST | CAST | CAST | — |

- **Auto** = implicit conversion happens automatically
- **CAST** = explicit CAST required
- ¹ DECIMAL to DECIMAL auto-converts if target precision ≥ source precision

**Key rules:**
- Numeric-to-numeric: automatic widening; narrowing requires explicit CAST
- Character-to-numeric: always requires explicit CAST
- Numeric-to-character: always requires explicit CAST (use || with '' trick as shorthand)
- DATE-to-character: automatic in some contexts (e.g., concatenation), but explicit CAST is recommended

---

## 8. Type Precedence in Mixed Expressions

When an expression combines different numeric types, the result type is determined by precedence (highest wins):

| Precedence (high→low) | Type |
|----------------------|------|
| 1 (highest) | `NUMBER` (floating) |
| 2 | `FLOAT` / `REAL` / `DOUBLE PRECISION` |
| 3 | `NUMBER(p,s)` (fixed) |
| 4 | `DECIMAL(p,s)` / `NUMERIC(p,s)` |
| 5 | `BIGINT` |
| 6 | `INTEGER` |
| 7 | `SMALLINT` |
| 8 (lowest) | `BYTEINT` |

```sql
-- INTEGER + DECIMAL → DECIMAL (DECIMAL wins)
SELECT 10 + CAST(5.5 AS DECIMAL(5,1));  -- Result: DECIMAL

-- DECIMAL + FLOAT → FLOAT (FLOAT wins)
SELECT CAST(10.5 AS DECIMAL(5,1)) + 1.0E0;  -- Result: FLOAT

-- INTEGER + BIGINT → BIGINT
SELECT CAST(1 AS INTEGER) + CAST(2 AS BIGINT);  -- Result: BIGINT
```

---

## 9. DATE, TIME, and TIMESTAMP Types

### Storage Summary

| Type | Storage | Default Format | Fractional Precision |
|------|---------|---------------|---------------------|
| `DATE` | 4 bytes | `'YYYY-MM-DD'` | N/A |
| `TIME` | 6 bytes | `'HH:MI:SS'` | 0–6 (default 6) |
| `TIME WITH TIME ZONE` | 8 bytes | `'HH:MI:SS±HH:MI'` | 0–6 |
| `TIMESTAMP` | 10 bytes | `'YYYY-MM-DD HH:MI:SS'` | 0–6 (default 6) |
| `TIMESTAMP(n)` | 10–12 bytes | Fractional seconds | n = 0–6 |
| `TIMESTAMP WITH TIME ZONE` | 12 bytes | With timezone offset | 0–6 |

### DATE Arithmetic

```sql
-- Integer arithmetic (Teradata extension)
SELECT CURRENT_DATE - 30;                    -- 30 days ago
SELECT CURRENT_DATE + 7;                     -- 7 days ahead

-- INTERVAL arithmetic (ANSI standard)
SELECT CURRENT_DATE + INTERVAL '3' MONTH;
SELECT CURRENT_TIMESTAMP + INTERVAL '2' HOUR;
SELECT order_date + INTERVAL '7' DAY;

-- Difference between dates
SELECT (CURRENT_DATE - hire_date) DAY(4);    -- Days between as INTERVAL DAY
SELECT CAST(CURRENT_DATE - hire_date AS INTEGER);  -- Days between as integer

-- Useful functions
SELECT ADD_MONTHS(CURRENT_DATE, 3);          -- 3 months ahead
SELECT EXTRACT(YEAR FROM CURRENT_DATE);      -- Year component
SELECT EXTRACT(MONTH FROM CURRENT_DATE);     -- Month component
SELECT TRUNC(CURRENT_TIMESTAMP, 'DD');       -- Truncate to midnight
SELECT TRUNC(CURRENT_TIMESTAMP, 'MM');       -- Truncate to first of month
```

### FORMAT Clause

```sql
CREATE TABLE events (
    event_date DATE FORMAT 'MM/DD/YYYY',
    event_ts   TIMESTAMP(3) FORMAT 'YYYY-MM-DDBHH:MI:SS.S(3)'
);

-- Common DATE formats
FORMAT 'YYYY-MM-DD'        -- ISO 8601: 2026-04-30
FORMAT 'MM/DD/YYYY'        -- US: 04/30/2026
FORMAT 'DD-MON-YYYY'       -- Oracle-style: 30-APR-2026
FORMAT 'YYYYMMDD'          -- Compact: 20260430
FORMAT 'E4,BM4BDD,BY4'     -- Full text: Wednesday, April 30, 2026
FORMAT 'YY/MM/DD'          -- Short year: 26/04/30
```

---

## 10. INTERVAL Types (All 13)

INTERVAL types represent a duration. There are two families:

### Year-Month Intervals (4 types)

| Type | Example Value | Notes |
|------|--------------|-------|
| `INTERVAL YEAR` | `INTERVAL '5' YEAR` | Single-field: years only |
| `INTERVAL YEAR TO MONTH` | `INTERVAL '5-03' YEAR TO MONTH` | 5 years, 3 months |
| `INTERVAL MONTH` | `INTERVAL '63' MONTH` | Single-field: months only |

### Day-Time Intervals (10 types)

`INTERVAL DAY`, `INTERVAL DAY TO HOUR`, `INTERVAL DAY TO MINUTE`, `INTERVAL DAY TO SECOND`, `INTERVAL HOUR`, `INTERVAL HOUR TO MINUTE`, `INTERVAL HOUR TO SECOND`, `INTERVAL MINUTE`, `INTERVAL MINUTE TO SECOND`, `INTERVAL SECOND`

```sql
SELECT INTERVAL '30 12:30:45' DAY TO SECOND;  -- 30 days, 12h, 30m, 45s
SELECT INTERVAL '720:30' HOUR TO MINUTE;      -- 720 hours, 30 minutes
```

### INTERVAL Precision and Rules

The leading field has a precision qualifier (default 2). `INTERVAL DAY` = `INTERVAL DAY(2)`, max 99 days. Use `DAY(3)` for up to 999, `DAY(4)` for up to 9999.

```sql
SELECT INTERVAL '365' DAY(3);   -- OK: 3-digit precision
SELECT INTERVAL '45.123456' SECOND(2,6);  -- Fractional seconds
```

**Key rules:**
- Year-month and day-time intervals **cannot be mixed** in arithmetic
- `TIMESTAMP - TIMESTAMP = INTERVAL`; `TIMESTAMP + INTERVAL = TIMESTAMP`
- An INTERVAL value is atomically null or not null (no partial nulls)

---

## 11. Common Pitfalls Summary

| Category | Pitfall | Fix |
|----------|---------|-----|
| Numeric | `SELECT 1/3` → 0 (integer division) | Use `1.0/3` or CAST to DECIMAL |
| Numeric | SUM of DECIMAL(9,2) overflows | `SUM(CAST(col AS DECIMAL(18,2)))` |
| Numeric | `0.1+0.2 <> 0.3` (FLOAT rounding) | Use DECIMAL for exact comparisons |
| Numeric | Value exceeds column type range | Use BIGINT or wider DECIMAL |
| Character | INSERT truncation on VARCHAR | Increase column length |
| Character | LATIN column, UNICODE data | Use UNICODE column or TRANSLATE |
| Character | CHAR trailing space comparison | Behavior differs in ANSI vs Teradata mode |
| Character | `WHERE clob_col = 'x'` | CLOBs do not support direct comparison |
| Date/Time | `date1 - date2` returns integer | Use `(date1 - date2) DAY` for INTERVAL |
| Date/Time | FORMAT mismatch on INSERT | Match FORMAT to input data pattern |
| Date/Time | TIMESTAMP(0) loses fractional seconds | Use TIMESTAMP(6) for microseconds |
| Date/Time | `INTERVAL '100' DAY` exceeds precision(2) | Specify `DAY(3)` or higher |

---

## 12. Quick Reference: Choosing the Right Type

| Use Case | Recommended Type |
|----------|------------------|
| Boolean flag / status codes | `BYTEINT` (1 byte, 0/1) |
| Row counts, IDs | `INTEGER` (4 bytes) |
| Surrogate keys (large tables) | `BIGINT` (8 bytes) |
| Currency / financial | `DECIMAL(18,2)` (exact) |
| Scientific measurements | `FLOAT` (approximate, wide range) |
| Oracle migration | `NUMBER` (compatible semantics) |
| Short text | `VARCHAR(n)` (variable length) |
| Fixed-length codes | `CHAR(n)` (predictable storage) |
| Multilingual text | `VARCHAR(n) CHARACTER SET UNICODE` |
| Large documents | `CLOB` (up to 2 GB) |
| Date-only values | `DATE` (4 bytes, supports arithmetic) |
| High-precision timestamps | `TIMESTAMP(6)` (microseconds) |
| Duration / elapsed time | `INTERVAL DAY TO SECOND` |
