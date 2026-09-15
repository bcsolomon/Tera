# ALTER TABLE Partitioning, Load Utilities & Expression Rules

## Partition Expression Rules

### Allowed Expression Forms

| Form | Example | Notes |
|---|---|---|
| Direct numeric column | `PARTITION BY division_number` | Optimizer assumes 65,535 partitions (suboptimal costing) |
| Modulo | `PARTITION BY phone MOD 65535 + 1` | Limited to equality elimination only |
| Multi-column arithmetic | `PARTITION BY store * 1000 + product` | Must result in INTEGER |
| CASE_N | `PARTITION BY CASE_N(x<10, x<50, ...)` | Max 65,533 conditions (2-byte) |
| RANGE_N | `PARTITION BY RANGE_N(date BETWEEN ...)` | Best optimizer support |

### Expression Restrictions

- Result must be INTEGER (1–65,535 for 2-byte, 1–9.2×10¹⁸ for 8-byte)
- **Prohibited:** character/graphic comparison, BLOB/CLOB, UDFs, RANDOM, aggregates, analytic functions, DATE/TIME/ACCOUNT built-ins, HASHAMP/HASHBAKAMP, subqueries, ROWID/PARTITION system columns
- **Allowed:** HASHROW, HASHBUCKET
- Max constraint text: 8,192 characters
- EVL code + PPI descriptor must fit in table header (64KB or 128KB)

### Multilevel Rules

| Limit | 2-byte | 8-byte |
|---|---|---|
| Max levels | 15 | 62 |
| Max combined partitions | 65,535 | 9.2×10¹⁸ |
| Each level minimum | 2 partitions | 2 partitions |
| Combined formula | P₁ × P₂ × ... × Pₙ | Same |

### RANGE_N Test Value Types

| Type | 2-byte | 8-byte |
|---|---|---|
| BYTEINT | Yes | Yes |
| SMALLINT | Yes | Yes |
| INTEGER | Yes | Yes |
| BIGINT | No | Yes (14.0+) |
| DATE | Yes | Yes |
| TIMESTAMP | No | Yes (14.0+) |

### RANGE_N Full Syntax

```
RANGE_N(test_value BETWEEN range [, range]...
        [, NO RANGE [OR UNKNOWN]] [, UNKNOWN])

range: range_start [AND range_end] [EACH range_size_value]
```

```sql
-- Date with EACH INTERVAL
RANGE_N(sale_date BETWEEN DATE '2020-01-01'
    AND DATE '2030-12-31' EACH INTERVAL '1' MONTH,
    NO RANGE OR UNKNOWN)

-- Integer with individual ranges
RANGE_N(age BETWEEN 1 AND 17,
                    18 AND 25,
                    26 AND 59,
                    60 AND 120,
    NO RANGE OR UNKNOWN)

-- BIGINT (8-byte)
RANGE_N(big_col BETWEEN 0 AND 1000000000000 EACH 100000)

-- TIMESTAMP (8-byte)
RANGE_N(ts_col BETWEEN TIMESTAMP '2020-01-01 00:00:00'
    AND TIMESTAMP '2030-12-31 23:59:59' EACH INTERVAL '1' MONTH)
```

### CASE_N Full Syntax

```
CASE_N(condition [, condition]...
       [, NO CASE [OR UNKNOWN]] [, UNKNOWN])
```

- Conditions evaluated left to right; first TRUE returns ordinal position
- Max 65,533 conditions (2-byte) or 9.2×10¹⁸ (8-byte)

```sql
-- Sales by day of week
PARTITION BY CASE_N(
    (sale_date - DATE '1900-01-07') MOD 7 = 0,  -- Sunday → partition 1
    (sale_date - DATE '1900-01-07') MOD 7 = 6,  -- Saturday → partition 2
    NO CASE OR UNKNOWN)                          -- Weekdays → partition 3
```

## PARTITION and PARTITION#Ln System Columns

- Data type: INTEGER
- Values: 0 for NPPI, 1–65,535 for 2-byte PPI
- **Not included in SELECT \*** — must be explicitly selected
- `PARTITION#Ln` for level n in multilevel partitioning
- For CP tables, column-partitioning level always returns 1
- **Warning:** `PARTITION#Ln` values change after ALTER TABLE — do not persist in user queries

```sql
-- Select partition number
SELECT PARTITION, order_date, COUNT(*)
FROM mydb.orders
GROUP BY 1, 2
ORDER BY 1;

-- Multilevel: select specific level
SELECT PARTITION#L1 AS date_part, PARTITION#L2 AS region_part, COUNT(*)
FROM mydb.orders
GROUP BY 1, 2;
```

---

## ALTER TABLE Partitioning Operations

### Empty Table: Full Respecification

When the table is empty, PI and partitioning expressions can be completely changed:

```sql
-- Change from NPPI to PPI
ALTER TABLE mydb.staging
  MODIFY PRIMARY INDEX (order_id)
  PARTITION BY RANGE_N(order_date BETWEEN DATE '2020-01-01'
      AND DATE '2030-12-31' EACH INTERVAL '1' MONTH);

-- Change from PPI to NPPI
ALTER TABLE mydb.staging
  MODIFY PRIMARY INDEX (order_id)
  NOT PARTITIONED;
```

### Populated Table: DROP/ADD RANGE

Only ranges at the **ends** of the partitioning expression can be dropped/added:

```sql
-- Roll forward: drop oldest month, add future month, delete dropped rows
ALTER TABLE mydb.orders MODIFY PRIMARY INDEX
  DROP RANGE BETWEEN DATE '2020-01-01' AND DATE '2020-01-31'
      EACH INTERVAL '1' DAY
   ADD RANGE BETWEEN DATE '2031-01-01' AND DATE '2031-01-31'
      EACH INTERVAL '1' DAY
  WITH DELETE;

-- Roll forward with archive to save table
ALTER TABLE mydb.orders MODIFY PRIMARY INDEX
  DROP RANGE BETWEEN DATE '2020-01-01' AND DATE '2020-12-31'
      EACH INTERVAL '1' MONTH
   ADD RANGE BETWEEN DATE '2031-01-01' AND DATE '2031-12-31'
      EACH INTERVAL '1' MONTH
  WITH INSERT INTO mydb.orders_archive;
```

### Multilevel ALTER

```sql
-- Modify level 1 (may change partition count)
ALTER TABLE mydb.orders MODIFY PRIMARY INDEX
  DROP RANGE#L1 WHERE PARTITION#L1=1
   ADD RANGE#L1 BETWEEN 41 AND 60 EACH 10;

-- Modify level 2 (partition count must stay same)
ALTER TABLE mydb.orders MODIFY PRIMARY INDEX
  DROP RANGE#L2 WHERE PARTITION#L2=1
   ADD RANGE#L2 BETWEEN 100 AND 104;

-- Combined multilevel ALTER
ALTER TABLE mydb.orders MODIFY PRIMARY INDEX
  DROP RANGE#L1 WHERE PARTITION=1 ADD RANGE#L1 BETWEEN 41 AND 60 EACH 10,
  DROP RANGE#L2 WHERE PARTITION#L2=1 ADD RANGE#L2 BETWEEN 100 AND 104
  WITH DELETE;
```

### ALTER TABLE Restrictions (Populated Table)

| Restriction | Detail |
|---|---|
| Only first level may change count | Other levels: partition count must remain same |
| CASE_N cannot be altered | Must be empty to change CASE_N expression |
| Number of levels cannot change | Must be empty to add/remove levels |
| Product must stay ≤ 65,535 (2-byte) | Each level ≥ 2 |
| Must drop PARTITION stats first | Recollect after ALTER completes |
| Uses EXCLUSIVE lock | Table inaccessible during execution |

### DROP ≠ DELETE

**Critical:** DROP RANGE does not necessarily delete rows. Rows only deleted if they don't satisfy the new expression. Rows may move to NO RANGE or added ranges.

### Performance Optimization for ALTER

```sql
-- Step 1: Delete data with WRITE lock (users can still read)
DELETE FROM mydb.orders WHERE order_date < DATE '2020-02-01';

-- Step 2: Drop PARTITION stats
DROP STATISTICS ON mydb.orders COLUMN (PARTITION);

-- Step 3: ALTER with EXCLUSIVE lock (fast, no data to move)
ALTER TABLE mydb.orders MODIFY PRIMARY INDEX
  DROP RANGE BETWEEN DATE '2020-01-01' AND DATE '2020-01-31'
      EACH INTERVAL '1' DAY
   ADD RANGE BETWEEN DATE '2031-02-01' AND DATE '2031-02-28'
      EACH INTERVAL '1' DAY;

-- Step 4: Recollect stats
COLLECT STATISTICS COLUMN (PARTITION) ON mydb.orders;
COLLECT STATISTICS COLUMN (order_date) ON mydb.orders;
```

### REVALIDATE PRIMARY INDEX

```sql
ALTER TABLE mydb.orders REVALIDATE PRIMARY INDEX;
ALTER TABLE mydb.orders REVALIDATE PRIMARY INDEX WITH DELETE;
ALTER TABLE mydb.orders REVALIDATE PRIMARY INDEX WITH INSERT INTO mydb.save_table;
```

**When needed:**
- After system upgrade
- Partitioning uses CURRENT_DATE/CURRENT_TIMESTAMP
- After altering partitioning expressions
- Dictionary columns show 0 for PIColumnCount/PartitioningLevels

---

## Statistics on PARTITION System Column

```sql
-- Fast operation (reads cylinder indexes, not data)
COLLECT STATISTICS COLUMN (PARTITION) ON mydb.orders;

-- For CP tables, collect compression ratios:
COLLECT STATISTICS COLUMN (PARTITION#L1) ON mydb.cp_table;
-- (Only for column-partitioning level, NOT for row-partitioning levels)
```

### Rules

- `PARTITION` stats used for **costing** (rows, data blocks, partitions to scan)
- Partitioning column stats used for **cardinality estimation**
- Refresh when: **10% change at the partition level** (not table level)
- Refresh when: partition changes empty ↔ nonempty
- **Must drop PARTITION stats before ALTER TABLE**, recollect after
- Cannot collect PARTITION stats on volatile tables or join indexes
- Without PARTITION stats: optimizer estimates rows/partition = total rows / adjusted count

### Multicolumn Stats Including PARTITION

```sql
-- Useful when all columns have equality predicates
COLLECT STATISTICS COLUMN (PARTITION, order_date) ON mydb.orders;
```

---

## Load Utilities with PPI

### Utility Support Matrix

| Utility | PPI Support | JI Maintained? | Notes |
|---|---|---|---|
| BTEQ, SQL Assistant | Yes | Yes | Standard row-at-a-time |
| TPump | Yes | Yes | See serialization warning |
| MultiLoad | Yes | No (no JI tables) | Must supply all PI + partitioning columns |
| FastLoad | Yes | No (no JI tables) | Benefits from partition elimination |
| FastExport | Yes | N/A | Benefits from partition elimination |

### MultiLoad Requirements

- DELETE/UPDATE IMPORT task: must supply values for **all PI and partitioning columns**
- PI and partitioning columns **may not be updated** in UPDATE task

### TPump Serialization Warning

Fine-grained partitions (e.g., daily with few rows per day) can cause data block serialization:
- Few rows per partition per AMP → few blocks per partition
- Multiple TPump sessions contend for same blocks
- **Workaround:** Use coarser partitions or single-session TPump for small tables

### INSERT into Empty Partitions Optimization

INSERT-SELECT into empty partitions avoids transient journaling if:
1. Target table must NOT have referential integrity
2. Range of source partition numbers must NOT include any nonempty partition's internal number

---

## Backup/Restore of Selected Partitions

```sql
-- Archive specific partitions
ARCHIVE DATA TABLES (mydb.orders)
  PARTITIONS WHERE (order_date BETWEEN DATE '2025-01-01' AND DATE '2025-03-31');

-- Restore specific partitions
RESTORE DATA TABLES (mydb.orders)
  PARTITIONS WHERE (order_date BETWEEN DATE '2025-01-01' AND DATE '2025-03-31')
  FROM ARCHIVE FILE = backup_file;

-- Archive all partitions
ARCHIVE DATA TABLES (mydb.orders) ALL PARTITIONS;

-- Archive qualified (nonempty) partitions
ARCHIVE DATA TABLES (mydb.orders) QUALIFIED PARTITIONS;
```

### Gotchas

- Wrong partition spec → wrong data restored
- Date boundaries may shift after repartition
- UTILVERSION tracks DDL changes

---

## Locking Considerations

- Locking is **unchanged** for PPI tables
- PI/USI specified → rowhash lock; otherwise → full-table lock
- **Cannot lock individual partitions**
- Use **views** to restrict access to specific partitions:

```sql
-- View for read access to current year
CREATE VIEW mydb.v_orders_current AS
  SELECT * FROM mydb.orders
  WHERE order_date >= DATE '2025-01-01';

-- Grant on view only
GRANT SELECT ON mydb.v_orders_current TO read_role;
```

---

## NPPI vs PPI Selection Guide

| Operation | NPPI | PPI (PI includes part cols) | PPI (PI excludes part cols) |
|---|---|---|---|
| PI equality (no date) | Single-AMP, direct | Same, 1 partition | Probes ALL partitions |
| PI equality + date | Same | Same, 1 partition | Probes eliminated set |
| Range scan on date | Full table scan | Partition elimination | Partition elimination |
| INSERT (SET table) | Dup check entire table | Dup check single partition | Dup check single partition |
| DELETE range | All-AMP scan | Optimized whole-partition delete | Same |
| Merge join | Standard | Rowkey merge (if same PPI) | Sliding-window |
| SI access | Standard | SI rowid elimination (V2R6+) | Same |
