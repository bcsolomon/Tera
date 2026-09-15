# Table Options — Complete Reference

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 3

## FALLBACK Protection

FALLBACK maintains a duplicate copy of each row on a different AMP from the primary copy. If an AMP fails, the system accesses the fallback copy.

```sql
-- Enable fallback
CREATE TABLE t1 (...), FALLBACK [PROTECTION];

-- Disable fallback
CREATE TABLE t1 (...), NO FALLBACK [PROTECTION];
```

### Rules
- FALLBACK doubles the storage requirement for the table
- Default depends on the database-level FALLBACK setting
- Volatile tables cannot have FALLBACK
- FALLBACK is recommended for production tables on systems without RAID protection

## Journal Tables

Journals record before-images and after-images of rows modified by transactions for recovery purposes.

### BEFORE JOURNAL

```sql
-- Enable single before-image journal
CREATE TABLE t1 (...), BEFORE JOURNAL;

-- Dual before-image journal (local + fallback)
CREATE TABLE t1 (...), DUAL BEFORE JOURNAL;

-- Disable
CREATE TABLE t1 (...), NO BEFORE JOURNAL;
```

### AFTER JOURNAL

```sql
-- Enable single after-image journal
CREATE TABLE t1 (...), AFTER JOURNAL;

-- Dual after-image
CREATE TABLE t1 (...), DUAL AFTER JOURNAL;

-- Disable
CREATE TABLE t1 (...), NO AFTER JOURNAL;
```

### LOG Option

```sql
CREATE TABLE t1 (...), LOG;      -- Enable transaction logging
CREATE TABLE t1 (...), NO LOG;   -- Disable transaction logging
```

- `NO LOG` suppresses transient journal entries for the table
- Use `NO LOG` only for staging tables where recovery is not needed

## CHECKSUM

Verifies data integrity when reading data blocks from disk.

```sql
CREATE TABLE t1 (...), CHECKSUM = DEFAULT;  -- Use system default
CREATE TABLE t1 (...), CHECKSUM = ON;       -- Enable per-block checksum
CREATE TABLE t1 (...), CHECKSUM = OFF;      -- Disable checksum
```

- Slight CPU overhead when ON
- Recommended for critical tables

## FREESPACE

Reserves a percentage of each cylinder for future inserts, reducing full-cylinder reorganizations.

```sql
CREATE TABLE t1 (...), FREESPACE = 20 PERCENT;
CREATE TABLE t1 (...), FREESPACE = 0;  -- No reserved space
```

- Valid range: 0–75 percent
- Higher values reduce reorganizations but waste disk space
- Useful for tables with heavy INSERT activity

## MERGEBLOCKRATIO

Controls when the system merges partially filled data blocks within a cylinder.

```sql
-- Use system default (typically merges at 50% empty)
CREATE TABLE t1 (...), DEFAULT MERGEBLOCKRATIO;

-- Set explicit threshold
CREATE TABLE t1 (...), MERGEBLOCKRATIO = 30 PERCENT;

-- Disable merging
CREATE TABLE t1 (...), NO MERGEBLOCKRATIO;
```

### Rules
- Valid range: 1–100 percent
- Lower values = fewer merges but more wasted space
- Higher values = more merges but better space utilization
- `NO MERGEBLOCKRATIO` disables merge operations entirely

## DATABLOCKSIZE

Specifies the range for data block sizes.

```sql
-- Use system default
CREATE TABLE t1 (...), DATABLOCKSIZE = DEFAULT;

-- Set explicit min/max
CREATE TABLE t1 (...),
  MINIMUM DATABLOCKSIZE = 4096 BYTES,
  MAXIMUM DATABLOCKSIZE = 131072 BYTES;

-- Combined specification
CREATE TABLE t1 (...), DATABLOCKSIZE = 65536 BYTES;
```

### Valid Ranges
| Parameter | Minimum | Maximum |
|-----------|---------|---------|
| MINIMUM DATABLOCKSIZE | 4096 bytes | 131072 bytes |
| MAXIMUM DATABLOCKSIZE | 4096 bytes | 1048576 bytes |
| DATABLOCKSIZE | 4096 bytes | 1048576 bytes |

- Block sizes must be multiples of 512 bytes
- Larger blocks improve sequential scan performance
- Smaller blocks improve random access performance

## Block Compression

Compresses entire data blocks (not individual column values).

```sql
-- System decides whether to compress (recommended)
CREATE TABLE t1 (...), BLOCKCOMPRESSION = DEFAULT;

-- Auto-temperature based: hot data uncompressed, warm/cold compressed
CREATE TABLE t1 (...), BLOCKCOMPRESSION = AUTOTEMP;

-- Manual: always compress
CREATE TABLE t1 (...), BLOCKCOMPRESSION = MANUAL;

-- Never compress
CREATE TABLE t1 (...), BLOCKCOMPRESSION = NEVER;
```

### AUTOTEMP Options

```sql
BLOCKCOMPRESSION = AUTOTEMP (
    THRESHOLD = 86400,       -- seconds before compression kicks in (default 86400 = 1 day)
    REGRANULARITY = 3600     -- recheck interval in seconds
)
```

### Decision Guide

| Option | Best For |
|--------|----------|
| `DEFAULT` | Most tables — system chooses based on access patterns |
| `AUTOTEMP` | Large tables with mixed hot/cold data |
| `MANUAL` | Cold/archival tables where CPU trade-off is acceptable |
| `NEVER` | Performance-critical hot tables where CPU must be minimized |

## MAP and Colocation

```sql
-- Assign table to a specific map
CREATE TABLE t1 (...), MAP = TD_DataMap1;

-- Assign with colocation (tables in same colocation group are co-located on same AMPs)
CREATE TABLE t1 (...), MAP = SparseMap1 COLOCATE USING my_colocation_group;
```

### Rules
- Contiguous maps use all AMPs; sparse maps use a subset
- Colocation ensures tables in the same group share the same AMP distribution
- Useful for optimizing joins between related tables

## Isolated Loading

```sql
-- Enable for all DML
CREATE TABLE t1 (...), WITH CONCURRENT ISOLATED LOADING FOR ALL;

-- Enable for INSERT only
CREATE TABLE t1 (...), WITH CONCURRENT ISOLATED LOADING FOR INSERT;

-- Disable
CREATE TABLE t1 (...), WITH NO ISOLATED LOADING;
```

### Rules
- Allows concurrent utility loads while queries are running
- Required for TPT Stream and MultiLoad concurrent operations
- Cannot be used with queue tables

## Combined Example

```sql
CREATE MULTISET TABLE mydb.sales_fact,
    FALLBACK,
    NO BEFORE JOURNAL,
    NO AFTER JOURNAL,
    CHECKSUM = DEFAULT,
    FREESPACE = 10 PERCENT,
    DEFAULT MERGEBLOCKRATIO,
    BLOCKCOMPRESSION = AUTOTEMP,
    MAP = TD_DataDictionary_Map
(
    sale_id       INTEGER NOT NULL,
    sale_date     DATE FORMAT 'YYYY-MM-DD' NOT NULL,
    customer_id   INTEGER NOT NULL,
    product_id    INTEGER NOT NULL,
    quantity      INTEGER DEFAULT 1,
    unit_price    DECIMAL(12,2),
    total_amount  DECIMAL(15,2)
)
PRIMARY INDEX (customer_id)
PARTITION BY RANGE_N(sale_date BETWEEN DATE '2020-01-01'
    AND DATE '2030-12-31' EACH INTERVAL '1' MONTH);
```
