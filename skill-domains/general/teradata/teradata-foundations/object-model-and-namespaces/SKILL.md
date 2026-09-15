---
name: teradata-data-types
description: 'Teradata data types including numeric (BYTEINT, SMALLINT, INTEGER, BIGINT, DECIMAL/NUMERIC, FLOAT/DOUBLE, NUMBER), character (CHAR, VARCHAR, CLOB, GRAPHIC, VARGRAPHIC), date/time (DATE, TIME, TIMESTAMP, INTERVAL, PERIOD), binary (BYTE, VARBYTE, BLOB), semi-structured (JSON, XML, DATASET), geospatial (ST_Geometry), and UDTs. Use when choosing data types, converting between types, understanding storage sizes, working with DATE arithmetic, PERIOD operations, LOB handling, character sets (LATIN/UNICODE/KANJISJIS), or geospatial features.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Data Types

## When to Use

- Choosing appropriate data types for table design
- Converting between data types (CAST, implicit conversion)
- DATE/TIME arithmetic and formatting
- PERIOD data type operations (overlaps, contains, precedes)
- LOB (CLOB/BLOB) storage and retrieval
- JSON/XML column design
- Geospatial data (ST_Geometry)
- Character set selection (LATIN, UNICODE)

## Numeric Types

| Type | Storage | Range | Notes |
|---|---|---|---|
| `BYTEINT` | 1 byte | -128 to 127 | Smallest integer |
| `SMALLINT` | 2 bytes | -32,768 to 32,767 | |
| `INTEGER` / `INT` | 4 bytes | -2.1B to 2.1B | Most common integer |
| `BIGINT` | 8 bytes | -9.2×10¹⁸ to 9.2×10¹⁸ | Large integers |
| `DECIMAL(p,s)` / `NUMERIC(p,s)` | 1-16 bytes | p: 1-38, s: 0-p | Exact decimal |
| `FLOAT` / `DOUBLE PRECISION` | 8 bytes | ±2.2×10⁻³⁰⁸ to ±1.8×10³⁰⁸ | IEEE 754 |
| `REAL` | 8 bytes | Same as FLOAT | Alias |
| `NUMBER` / `NUMBER(p,s)` | 1-18 bytes | p: 1-38, s: -128 to 127 | Oracle-compatible |

### DECIMAL Storage

| Precision | Storage |
|---|---|
| 1-2 | 1 byte |
| 3-4 | 2 bytes |
| 5-9 | 4 bytes |
| 10-18 | 8 bytes |
| 19-38 | 16 bytes |

## Character Types

| Type | Max Length | Character Set | Notes |
|---|---|---|---|
| `CHAR(n)` | 64,000 bytes | LATIN or UNICODE | Fixed-length, padded |
| `VARCHAR(n)` | 64,000 bytes | LATIN or UNICODE | Variable-length |
| `CLOB(n)` | 2 GB | LATIN or UNICODE | Large text |
| `GRAPHIC(n)` | 32,000 chars | Fixed 2-byte | Fixed-length |
| `VARGRAPHIC(n)` | 32,000 chars | Fixed 2-byte | Variable-length |

### Character Sets

| Set | Bytes/Char | Use |
|---|---|---|
| `LATIN` | 1 | Western European (default on many systems) |
| `UNICODE` | Up to 3 | Multilingual (UTF-8 storage, UTF-16 processing) |
| `GRAPHIC` | 2 | Fixed double-byte |
| `KANJISJIS` | 1-2 | Japanese Shift-JIS |

```sql
CREATE TABLE t (
    name_latin  VARCHAR(100) CHARACTER SET LATIN,
    name_utf    VARCHAR(100) CHARACTER SET UNICODE
);
```

## Date/Time Types

| Type | Storage | Format | Example |
|---|---|---|---|
| `DATE` | 4 bytes | `'YYYY-MM-DD'` | `DATE '2025-06-15'` |
| `TIME` | 6 bytes | `'HH:MI:SS'` | `TIME '14:30:00'` |
| `TIME WITH TIME ZONE` | 8 bytes | `'HH:MI:SS+HH:MI'` | `TIME '14:30:00+05:30'` |
| `TIMESTAMP` | 10 bytes | `'YYYY-MM-DD HH:MI:SS'` | `TIMESTAMP '2025-06-15 14:30:00'` |
| `TIMESTAMP(n)` | 10-12 bytes | Fractional seconds (0-6) | `TIMESTAMP(6)` |
| `TIMESTAMP WITH TIME ZONE` | 12 bytes | With timezone | |

### DATE Arithmetic

```sql
-- Teradata stores DATE as INTEGER: (year - 1900) * 10000 + month * 100 + day
SELECT CURRENT_DATE - 30;                    -- 30 days ago
SELECT order_date + INTERVAL '7' DAY;        -- 7 days later
SELECT (CURRENT_DATE - hire_date) DAY(4);    -- Days between
SELECT ADD_MONTHS(CURRENT_DATE, 3);          -- 3 months ahead
SELECT EXTRACT(YEAR FROM CURRENT_DATE);      -- Year portion
SELECT TRUNC(CURRENT_TIMESTAMP, 'DD');       -- Truncate to day
```

### DATE Formats

```sql
CREATE TABLE t (d DATE FORMAT 'MM/DD/YYYY');

-- Common formats
FORMAT 'YYYY-MM-DD'     -- ISO standard
FORMAT 'MM/DD/YYYY'     -- US format
FORMAT 'DD-MON-YYYY'    -- Oracle-like
FORMAT 'YYYYMMDD'       -- Compact
FORMAT 'E4,BM4BDD,BY4'  -- Day, Month DD, Year
```

## INTERVAL Types

```sql
INTERVAL YEAR
INTERVAL YEAR TO MONTH
INTERVAL MONTH
INTERVAL DAY
INTERVAL DAY TO HOUR
INTERVAL DAY TO MINUTE
INTERVAL DAY TO SECOND
INTERVAL HOUR
INTERVAL HOUR TO MINUTE
INTERVAL HOUR TO SECOND
INTERVAL MINUTE
INTERVAL MINUTE TO SECOND
INTERVAL SECOND
```

```sql
SELECT CURRENT_TIMESTAMP + INTERVAL '2' HOUR;
SELECT CURRENT_DATE + INTERVAL '3' MONTH;
```

## PERIOD Types

Represents a span of time with inclusive begin, exclusive end:

```sql
PERIOD(DATE)
PERIOD(TIME)
PERIOD(TIME WITH TIME ZONE)
PERIOD(TIMESTAMP)
PERIOD(TIMESTAMP WITH TIME ZONE)

CREATE TABLE employment (
    emp_id INTEGER,
    job_period PERIOD(DATE)
);

INSERT INTO employment VALUES (1, PERIOD(DATE '2020-01-15', DATE '2025-12-31'));

-- PERIOD operations
SELECT * FROM employment WHERE job_period CONTAINS CURRENT_DATE;
SELECT * FROM employment WHERE job_period OVERLAPS PERIOD(DATE '2023-01-01', DATE '2024-01-01');
SELECT * FROM employment WHERE job_period P_INTERSECT PERIOD(DATE '2024-01-01', DATE '2025-01-01') IS NOT NULL;
```

### PERIOD Predicates

| Predicate | Meaning |
|---|---|
| `CONTAINS` | Period contains a value or another period |
| `OVERLAPS` | Two periods share any time |
| `MEETS` | End of one equals start of another |
| `PRECEDES` | Period ends before another starts |
| `SUCCEEDS` | Period starts after another ends |
| `P_INTERSECT` | Intersection of two periods |
| `P_NORMALIZE` | Merge adjacent/overlapping periods |

## Binary Types

| Type | Max | Notes |
|---|---|---|
| `BYTE(n)` | 64,000 bytes | Fixed-length binary |
| `VARBYTE(n)` | 64,000 bytes | Variable-length binary |
| `BLOB(n)` | 2 GB | Large binary object |

## Semi-Structured Types

| Type | Max Size | Notes |
|---|---|---|
| `JSON(n)` | ~16 MB | Storage: TEXT, BSON, UBJSON |
| `XML(n)` | ~2 GB | XML document storage |
| `DATASET` | Variable | CSV/Avro container |

See [teradata-native-object-store](../teradata-native-object-store/SKILL.md) for JSON/XML processing details.

## Geospatial Types (ST_Geometry)

```sql
CREATE TABLE locations (
    id INTEGER,
    point_loc ST_GEOMETRY(16776192)
);

INSERT INTO locations VALUES (1, NEW ST_GEOMETRY('POINT(-96.8 32.7)'));

-- Spatial methods
SELECT point_loc.ST_X(), point_loc.ST_Y() FROM locations;
SELECT a.id FROM locations a, regions b
WHERE a.point_loc.ST_Within(b.boundary) = 1;
```

### Geometry Types

`POINT`, `LINESTRING`, `POLYGON`, `MULTIPOINT`, `MULTILINESTRING`, `MULTIPOLYGON`, `GEOMETRYCOLLECTION`

## Type Conversion

```sql
-- Explicit CAST
SELECT CAST(col1 AS VARCHAR(20));
SELECT CAST('2025-06-15' AS DATE FORMAT 'YYYY-MM-DD');
SELECT CAST(123.456 AS DECIMAL(10,2));

-- TRYCAST (returns NULL on failure instead of error)
SELECT TRYCAST('abc' AS INTEGER);  -- Returns NULL
```

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `Numeric overflow` | Value exceeds type range | Use larger type (INTEGER→BIGINT) |
| `String truncation` | VARCHAR too short | Increase length |
| `Invalid date` | Bad date format | Check FORMAT specification |
| `Character conversion` | LATIN←→UNICODE mismatch | TRANSLATE or explicit CAST with charset |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-data-types", path="references/FILENAME")` — do NOT call `list`.

Load these files for detailed technical reference on specific topics:

- **references/lob-reference.md** — BLOB/CLOB storage model (separate subtables, OID, 64K sections, ~2 GB max), supported vs unsupported operations, transfer modes (inline/deferred/locator), design limits (32 LOB columns, 16-bit uniqueness), CREATE TABLE syntax, recovery behavior, UDF interface, error codes
- **references/numeric-and-character-types.md** — Integer types (BYTEINT through BIGINT) with storage/ranges, DATE internal representation, DECIMAL/NUMERIC precision and storage tiers, NUMBER (Oracle-compatible), FLOAT/REAL/DOUBLE, character types (CHAR/VARCHAR/CLOB/GRAPHIC/VARGRAPHIC), character sets (LATIN/UNICODE/GRAPHIC/KANJISJIS), TRANSLATE function, implicit/explicit type conversion rules, TRYCAST
- **references/geospatial-reference.md** — ST_Geometry type hierarchy (Point through GeometryCollection), all constructors (WKT/WKB), complete spatial methods catalog (relationship tests, measurements, manipulation, accessors), MBR and GeoSequence types, spatial joins, metadata tables, loading utilities, coordinate transforms, access rights
- **references/geospatial-indexing-reference.md** — Tessellation-based spatial indexing (Tessellate, Tessellate_index, Tessellate_search functions), multi-level 2D grid concepts, tessellation parameters, spatial index creation and maintenance, performance guidelines for large-scale spatial queries
- **references/period-and-temporal.md** — PERIOD data type (DATE/TIME/TIMESTAMP variants), constructors (UNTIL_CHANGED), BEGIN/END accessors, predicates (CONTAINS, OVERLAPS, MEETS, PRECEDES, SUCCEEDS), P_INTERSECT/P_NORMALIZE functions, NORMALIZE ON clause for merging overlapping periods, EXPAND ON clause for expanding periods into rows, temporal tables (VALIDTIME, TRANSACTIONTIME, bitemporal), CURRENT/SEQUENCED/NONSEQUENCED DML qualifiers, temporal partitioning with ALTER TABLE TO CURRENT, NONSEQUENCED VALIDTIME constraints, PERIOD vs PTI comparison
- **references/time-series-reference.md** — Primary Time Index (PTI) tables, CREATE TABLE syntax with all parameters, auto-generated columns (TD_TIMEBUCKET/TD_TIMECODE/TD_SEQNO), distribution strategies (A/B/C), GROUP BY TIME clause, FILL clause for missing values, 22+ time series aggregate functions, DELTA_T, PTI restrictions, system functions
- **references/time-series-operations-reference.md** — PTI DDL operations (CREATE TABLE AS, ALTER TABLE), DML operations (INSERT/SELECT, UPDATE, DELETE, MERGE), loading data via Fastload/TPT, PTI-specific rules and restrictions, non-PTI to PTI conversion, TD_TIMEBUCKET regeneration
