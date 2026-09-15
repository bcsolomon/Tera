# Teradata String Functions

## Quick Reference

| Function | Syntax | Notes |
|----------|--------|-------|
| Length | `CHAR_LENGTH(str)` or `CHARACTER_LENGTH(str)` | Character count |
| Byte length | `OCTET_LENGTH(str)` | Byte count |
| Substring | `SUBSTR(str, start, length)` | 1-based index |
| Position | `INDEX(str, substring)` | Returns 0 if not found (not INSTR) |
| Concatenate | `str1 \|\| str2` or `CONCAT(a, b)` | |
| Upper/Lower | `UPPER(str)` / `LOWER(str)` | |
| Trim | `TRIM([[LEADING\|TRAILING\|BOTH] char FROM] str)` | Default trims spaces both sides |
| Left trim | `LTRIM(str [, chars])` | |
| Right trim | `RTRIM(str [, chars])` | |
| Replace | `OREPLACE(str, from, to)` | Teradata-specific; use instead of REPLACE |
| Pad left | `LPAD(str, length [, pad_char])` | |
| Pad right | `RPAD(str, length [, pad_char])` | |
| Repeat | `STRTOK_SPLIT_TO_TABLE` / manual CTE | No simple REPEAT function |
| Reverse | `REVERSE(str)` | |
| RegEx match | `REGEXP_SIMILAR(str, pattern)` | Returns 1 (match) or 0 |
| RegEx extract | `REGEXP_SUBSTR(str, pattern [, pos [, occur [, flags]]])` | |
| RegEx replace | `REGEXP_REPLACE(str, pattern, replacement [, pos [, occur [, flags]]])` | |

## Examples

```sql
-- Substring: extract first 3 characters
SELECT SUBSTR(name, 1, 3) FROM db.t;

-- Find position of substring (returns 0 if not found)
SELECT INDEX(email, '@') FROM db.t;

-- Replace a substring (Teradata uses OREPLACE, not REPLACE)
SELECT OREPLACE(phone, '-', '') FROM db.t;

-- Trim specific characters
SELECT TRIM(LEADING '0' FROM account_number) FROM db.t;

-- Pad a number to 8 digits
SELECT LPAD(CAST(id AS VARCHAR(8)), 8, '0') FROM db.t;

-- Concatenate with separator
SELECT first_name || ' ' || last_name AS full_name FROM db.t;

-- Case-insensitive search using UPPER
SELECT * FROM db.t WHERE UPPER(name) LIKE '%SMITH%';

-- Extract domain from email
SELECT SUBSTR(email, INDEX(email, '@') + 1) AS domain FROM db.t;

-- RegEx: check if value looks like a US zip code
SELECT REGEXP_SIMILAR(zip, '^[0-9]{5}(-[0-9]{4})?$') FROM db.t;

-- RegEx: extract area code from phone number
SELECT REGEXP_SUBSTR(phone, '[0-9]{3}', 1, 1) AS area_code FROM db.t;
```

## Tokenization
```sql
-- Split a delimited string into rows using STRTOK_SPLIT_TO_TABLE
SELECT token_num, tokenval
FROM TABLE(STRTOK_SPLIT_TO_TABLE(1, 'a,b,c', ',')
           RETURNS (outkey INTEGER, token_num INTEGER, tokenval VARCHAR(100))
          ) AS t;

-- Get Nth token from a delimited string
SELECT STRTOK(col, ',', 2) FROM db.t;   -- 2nd comma-delimited token
```

## Notes
- Teradata strings are 1-indexed
- `CHAR` columns are padded with spaces; use `TRIM` when comparing
- `OREPLACE` is preferred over `REPLACE` in Teradata dialects

---

# Teradata Numeric Functions

## Rounding & Truncation
```sql
ROUND(expr, n)          -- round to n decimal places
TRUNC(expr, n)          -- truncate (no rounding) to n decimal places
FLOOR(expr)             -- largest integer <= expr
CEILING(expr) / CEIL(expr) -- smallest integer >= expr
```

## Absolute Value & Sign
```sql
ABS(expr)               -- absolute value
SIGN(expr)              -- -1, 0, or 1
```

## Modulo
```sql
expr MOD divisor        -- Teradata keyword form
MOD(expr, divisor)      -- function form
-- Example: even/odd
id MOD 2 = 0            -- even rows
```

## Power & Roots
```sql
expr ** n               -- raise to power (Teradata operator)
POWER(expr, n)          -- same, ANSI form
SQRT(expr)              -- square root
EXP(expr)               -- e^expr
```

## Logarithms
```sql
LN(expr)                -- natural log
LOG(expr)               -- log base 10
-- Custom base: LOG(expr) / LOG(base)
```

## Trigonometry
```sql
SIN(expr)  COS(expr)  TAN(expr)
ASIN(expr) ACOS(expr) ATAN(expr) ATAN2(y, x)
-- Input/output in radians
-- Degrees to radians: expr * ACOS(-1) / 180
```

## Null-Safe Arithmetic
```sql
ZEROIFNULL(expr)        -- replace NULL with 0
NULLIFZERO(expr)        -- replace 0 with NULL (useful for avoiding divide-by-zero)

-- Safe division
numerator / NULLIFZERO(denominator)
```

## Numeric Formatting
```sql
-- Cast to fixed decimal
CAST(expr AS DECIMAL(10, 2))

-- Format as string with commas / specific format
CAST(expr AS VARCHAR(20) FORMAT 'Z,ZZ9.99')
```

## Random Numbers
```sql
-- Pseudo-random float in [0, 1)
RANDOM(0, 100)          -- random integer between 0 and 100 inclusive
```

## Statistical Functions (aggregate context)
```sql
SUM(col)
AVG(col)
MIN(col) / MAX(col)
STDDEV_POP(col)         -- population standard deviation
STDDEV_SAMP(col)        -- sample standard deviation
VAR_POP(col)            -- population variance
VAR_SAMP(col)           -- sample variance

-- Approximate percentile (TD Vantage)
APPROX_PERCENTILE(col, 0.5)   -- median
APPROX_PERCENTILE(col, 0.95)  -- 95th percentile
```

## Type Conversion
```sql
CAST(expr AS INTEGER)
CAST(expr AS BIGINT)
CAST(expr AS DECIMAL(15, 4))
CAST(expr AS FLOAT)
CAST('3.14' AS DECIMAL(10, 4))
```

---

# Teradata Conditional Expressions

## CASE
```sql
-- Searched CASE
CASE
    WHEN score >= 90 THEN 'A'
    WHEN score >= 80 THEN 'B'
    WHEN score >= 70 THEN 'C'
    ELSE 'F'
END

-- Simple CASE (equality test)
CASE status
    WHEN 'A' THEN 'Active'
    WHEN 'I' THEN 'Inactive'
    ELSE 'Unknown'
END
```

## Null-Handling Functions
```sql
COALESCE(a, b, c)       -- first non-NULL value; ANSI standard
NULLIF(a, b)            -- returns NULL if a = b, otherwise a
ZEROIFNULL(expr)        -- Teradata shorthand: NULL → 0
NULLIFZERO(expr)        -- Teradata shorthand: 0 → NULL

-- Examples
COALESCE(preferred_email, work_email, personal_email)
NULLIF(status, 'N/A')                       -- treat 'N/A' as NULL
revenue / NULLIFZERO(units)                 -- safe division
SUM(ZEROIFNULL(adjustment)) + base_amount   -- null-safe sum
```

## IIF / Inline IF
Teradata does not have a native `IIF()`. Use CASE instead:
```sql
-- Instead of IIF(condition, true_val, false_val):
CASE WHEN condition THEN true_val ELSE false_val END

-- One-liner shorthand is fine
CASE WHEN is_active = 1 THEN 'Yes' ELSE 'No' END AS active_flag
```

## IN / NOT IN
```sql
WHERE status IN ('A', 'B', 'C')
WHERE region NOT IN ('West', 'East')

-- Subquery form
WHERE id IN (SELECT id FROM db.exclusions)
```

## EXISTS / NOT EXISTS
```sql
WHERE EXISTS (
    SELECT 1 FROM db.orders o WHERE o.customer_id = c.id
)
```

## BETWEEN
```sql
WHERE amount BETWEEN 100 AND 500          -- inclusive
WHERE event_date BETWEEN DATE '2024-01-01' AND DATE '2024-12-31'
```

## Conditional Aggregation
```sql
-- Count rows meeting a condition
SUM(CASE WHEN type = 'credit' THEN 1 ELSE 0 END) AS credit_count

-- Conditional sum
SUM(CASE WHEN region = 'North' THEN amount ELSE 0 END) AS north_total

-- Pivot pattern: turn row values into columns
SUM(CASE WHEN month = 1 THEN amount END) AS jan,
SUM(CASE WHEN month = 2 THEN amount END) AS feb,
SUM(CASE WHEN month = 3 THEN amount END) AS mar
```

## GREATEST / LEAST
```sql
GREATEST(a, b, c)   -- maximum of the values (ignores NULLs if any non-NULL present)
LEAST(a, b, c)      -- minimum of the values
```
