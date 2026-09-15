# 8-Byte Partitioning & Advanced Partition Limits

> Source: 541-0009027 — Increased Partition Limit and other Partitioning Enhancements

## When 8-Byte Partitioning Is Used

8-byte partitioning activates automatically when defined combined partitions exceed 65,535. The original 2-byte form remains for smaller partition counts.

| Feature | 2-Byte | 8-Byte |
|---|---|---|
| Max combined partitions | 65,535 (2^16 - 1) | 9,223,372,036,854,775,807 (2^63 - 1) |
| Max partitioning levels | 15 | 62 |
| Row overhead | 2 bytes/row | 8 bytes/row |
| SI referenced rowid size | 10 bytes | 16 bytes |
| JI/HI referenced rowid size | 10 bytes | 16 bytes |
| Trigger | ≤65,535 combined | >65,535 combined |

## Row Layout Impact

- Base table rows: +8 bytes per row compared to nonpartitioned (vs +2 bytes for 2-byte)
- Secondary index referenced rowids: 16 bytes each (vs 10 bytes for 2-byte, 8 bytes for NPPI)
- Join/hash index referenced rowids: 16 bytes each (vs 10 bytes for 2-byte)

**Space calculation:** For large tables with secondary indexes, the 8-byte rowid overhead can be significant. Factor the increased SI subtable size into capacity planning.

## BIGINT and TIMESTAMP Support (14.0+)

8-byte partitioning extends RANGE_N to support BIGINT and TIMESTAMP test values:

```sql
-- BIGINT partitioning
CREATE TABLE mydb.events (
    event_id   BIGINT NOT NULL,
    event_type INTEGER,
    payload    VARCHAR(1000)
) PRIMARY INDEX (event_id)
  PARTITION BY RANGE_N(event_id BETWEEN 0 AND 1000000000000 EACH 100000);

-- TIMESTAMP partitioning
CREATE TABLE mydb.telemetry (
    sensor_id   INTEGER NOT NULL,
    reading_ts  TIMESTAMP(6) NOT NULL,
    value       DECIMAL(18,6)
) PRIMARY INDEX (sensor_id)
  PARTITION BY RANGE_N(reading_ts BETWEEN TIMESTAMP '2020-01-01 00:00:00'
      AND TIMESTAMP '2030-12-31 23:59:59' EACH INTERVAL '1' MONTH);
```

### TIMESTAMP Cast as DATE Elimination (14.0+)

Partition elimination works when TIMESTAMP is cast as DATE in the partitioning expression AND the query:

```sql
-- Table: PARTITION BY RANGE_N(CAST(start_time AS DATE AT LOCAL) BETWEEN ...)
-- Query can use CAST in predicate and still get elimination:
SELECT * FROM mydb.telemetry
WHERE CAST(reading_ts AS DATE) BETWEEN DATE '2025-03-14' AND DATE '2025-03-29';
-- → Static elimination to 16 partitions
```

## Optimizations NOT Supported with 8-Byte

| Optimization | 2-Byte | 8-Byte |
|---|---|---|
| Exclusion product join DPE | Yes | **No** |
| Full outer rowkey-based merge join with partition remapping | Yes | **No** |
| Selected partition archive/restore/copy (PARTITIONS WHERE) | Yes | **No** |
| All other join/elimination optimizations | Yes | Yes |

## Performance Considerations

### Large Partition Count Impact

With many combined partitions, these operations may be expensive without effective partition elimination:
- Primary index access (must probe each nonempty partition)
- Joins (sliding-window may not be feasible if window << nonempty partitions)
- Aggregations

**Guideline:** The PI becomes primarily useful for data distribution when partition counts are very large. Ensure queries provide effective elimination constraints.

### Rowkey-Based Merge Join Feasibility

With many partitioning levels, rowkey-based merge joins require equality conditions on ALL partitioning columns AND all PI columns — this becomes impractical with many levels.

### Empty Partition Expectations

With large partition definitions, a high percentage of partitions will be empty (this is normal and expected):

```
Example: 200-AMP system, 200GB table, 100,000 combined partitions
- 100 rows/block, 100 blocks/nonempty partition/AMP
- ~99% of defined partitions are empty
- If ALL partitions were nonempty: would require 200 billion rows (20 PB)

Guideline: A nonempty combined partition on an AMP should have ≥10 data blocks
```

## Static Row Partition Elimination Rules

For RANGE_N with inequality constraints, elimination occurs when the test value is a **recognized linear, nondecreasing expression**:

| Recognized Form | Example |
|---|---|
| Direct column | `WHERE col > 5` |
| CAST/EXTRACT of linear expr | `WHERE CAST(ts AS DATE) > DATE '2025-01-01'` |
| Linear + constant | `WHERE col + 10 > 50` |
| Constant + linear | `WHERE 10 + col > 50` |
| Linear - constant | `WHERE col - 5 > 45` |
| Column * positive constant | `WHERE col * 2 > 100` |
| Column / positive constant | `WHERE col / 10 > 5` |

**Not recognized:** arbitrary function calls, column * negative constant, nonlinear expressions. CASE_N elimination is based on condition satisfiability analysis.

## ADD Option for Excess Partitions

The ADD clause reserves extra partitions for future ALTER TABLE operations without redefining:

```sql
CREATE TABLE mydb.sales (
    sale_id   INTEGER NOT NULL,
    sale_date DATE NOT NULL,
    amount    DECIMAL(13,2)
) PRIMARY INDEX (sale_id)
  PARTITION BY RANGE_N(sale_date BETWEEN DATE '2020-01-01'
      AND DATE '2025-12-31' EACH INTERVAL '1' MONTH
      ADD 24);  -- Reserve 24 extra partitions for future expansion
```

For multilevel partitioning, excess combined partitions are distributed across levels until no more can be assigned.

### EACH Optional for ALTER TABLE DROP (14.0+)

Prior to 14.0, DROP RANGE required EACH to match the original expression. From 14.0, ranges within the DROP specification are dropped regardless of EACH:

```sql
-- Pre-14.0: EACH required to match original
ALTER TABLE mydb.sales MODIFY PRIMARY INDEX
  DROP RANGE BETWEEN DATE '2020-01-01' AND DATE '2020-12-31'
      EACH INTERVAL '1' MONTH;

-- 14.0+: EACH is optional (has no effect in DROP)
ALTER TABLE mydb.sales MODIFY PRIMARY INDEX
  DROP RANGE BETWEEN DATE '2020-01-01' AND DATE '2020-12-31';
```

## System Settings for 8-Byte Partitioning

| Setting | Location | Recommendation |
|---|---|---|
| PartitioningConstraintForm | Cost Profile | Set to 1 when using 8-byte partitioning |
| PPICacheThrP | DBS Control / Cost Profile | Default usually adequate; tune if sliding-window joins underperform |
| PrimaryIndexDefault | DBS Control | No change needed for 8-byte |

## Design Methodology

Partitioning is a physical design decision. All of these must work well together:

1. **Partitioning expressions** — match query access patterns
2. **Other physical design** — PI choice, secondary indexes, join indexes
3. **Query workload** — both specific queries and overall workload mix
4. **Performance validation** — check EXPLAIN for elimination, measure before/after
5. **Data maintenance** — sliding window, archive/restore impact
6. **ALTER operations** — future partition range changes
7. **Backup/restore** — partition-level backup feasibility

**Critical:** Do not focus on a single aspect. A partition expression is only good if queries actually use it (elimination occurs) and all aspects work together based on validated tradeoffs.

### Validation Steps

1. Review EXPLAIN — look for partition elimination counts and rowkey-based merge joins
2. Measure performance before AND after for the full query workload
3. Verify maintenance process performance — do not assume partitioning improves it
4. Test with representative data volumes
5. Weigh costs (row overhead, SI overhead, maintenance complexity) against benefits (elimination, range operations)
