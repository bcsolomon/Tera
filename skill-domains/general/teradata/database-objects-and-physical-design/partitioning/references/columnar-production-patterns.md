# Columnar Production Patterns & Implementation Guide

> Source: TDN0009884 — Teradata Columnar Primer (2019)

## Production Use Cases

### Event Capture (Telecom/IoT)

| Aspect | Detail |
|---|---|
| Table size | ~20 TB per monthly table |
| Partitioning | Hybrid: each column in own partition + 10-minute row intervals |
| Index type | Primary AMP Index (PA) |
| Load rate | ~5 billion rows/day, 7×24×365 |
| Load method | FastLoad → staging table → INSERT-SELECT to CP |
| Retention | 1 year in database, older data moved to Hadoop via QueryGrid |
| Compression | BLC on older tables for space savings |
| Access pattern | Reports searching specific info within limited date range, few columns |
| Duration | 3+ years in production |

**Key decisions:**
- No joins between monthly CP tables (disallowed for performance)
- No UNION operations across monthly tables
- SQL procedures with volatile tables for cross-month queries
- No secondary indexes — load throughput is the priority
- Single-column partitions act as implicit secondary indexes

### Marketing Analysis (E-Commerce)

| Aspect | Detail |
|---|---|
| Table size | 250+ TB (two tables) |
| Partitioning | Hybrid: column + row by date |
| Index type | One PA, one NoPI |
| Load method | INSERT-SELECT, multiple batches/day (append-only) |
| Access pattern | Few columns, date constraint on week or small range |
| Compression | BLC on both tables → 30% physical I/O reduction |
| Duration | 6+ months in production |

**Key insight:** No ETL design changes required — existing "inserts only" approach directly compatible with CP. Most queries use one highly selective predicate on a column partition.

### Customer Analytics (Communications)

| Aspect | Detail |
|---|---|
| Users | 600 end users, 20K+ queries/month |
| Design | Consolidated monthly fact tables into single wide CP table |
| Partitioning | Column + row by month |
| Access pattern | Small subset of columns, range constraints on small time windows |
| Updates | Row-based mirror table for updates, periodic rebuild |

**Design pattern — Mirror table for updates:**
1. Maintain row-based mirror table with MVC for space savings
2. Apply all updates to row-based mirror
3. Periodically rebuild CP table from mirror via INSERT-SELECT
4. Swap new CP table in to replace current

**Known tradeoffs:**
- SELECT * is slower on CP vs row format (expected)
- Direct single-row updates perform poorly on CP
- Delete leaves dead space (logical delete only for COLUMN format)
- Two copies of data (CP + mirror) increase disk usage

## Emerging Use Cases

| Use Case | Why CP Fits | Characteristics |
|---|---|---|
| Sensor data | Append-only, wide rows, subset access | Time-based row partitioning + column partitioning |
| Clickstream | High volume, many attributes, subset analysis | Hybrid with date, no updates |
| NOS staging | External data (S3/Azure) read into persistent CP table | Large batch INSERT-SELECT from foreign tables |
| Star schema fact | Wide fact tables, dimension joins | PA for join columns, CP for column elimination |
| PNR (airline) | ~300 columns, queries use few columns | PA, BTEQ INSERT-SELECT loading |

## N-Way Join Optimization

When joining multiple small dimension tables to a large CP fact table, the n-way join optimization eliminates intermediate spool:

```
Without n-way join:
  3 dimension tables × 100 rows each
  Product join: 100 × 100 × 100 = 1,000,000 row spool
  Then join spool to fact table

With n-way join:
  All 3 dimensions held in memory: 100 + 100 + 100 = 300 rows
  Single join step to fact table
  Late materialization — no intermediate spool
```

**Result:** Exponentially smaller spool, single join operation, reduced I/O.

## PA vs PI vs NoPI Decision Guide

| Factor | NoPI | PI | PA (Recommended) |
|---|---|---|---|
| Load speed | Fastest (block-level) | Slowest (hash + sort) | Medium (hash + append) |
| Autocompression | Best (continuous append) | Worst (new container per PI value) | Good (continuous append) |
| Table size | Smallest | Largest | Medium |
| Single-AMP access | No | Yes | Yes |
| AMP-local joins | No | Yes | Yes |
| AMP-local aggregation | No | Yes | Yes |
| Container packing | Many values per container | Few values (1 per unique PI) | Many values per container |

**Production consensus:** PA is almost universally used for CP tables in production deployments.

## Loading Strategy

### Recommended Pattern: Staged INSERT-SELECT

```sql
-- Step 1: FastLoad/TPT Load into row-based staging table
CREATE MULTISET TABLE mydb.staging_events (
    event_id    BIGINT,
    event_ts    TIMESTAMP,
    sensor_id   INTEGER,
    metric1     DECIMAL(18,6),
    metric2     DECIMAL(18,6),
    -- ... many columns
    metric50    DECIMAL(18,6)
) NO PRIMARY INDEX;
-- Load via FastLoad/TPT into staging

-- Step 2: INSERT-SELECT into CP table (batch)
INSERT INTO mydb.events_cp
SELECT * FROM mydb.staging_events;

-- Step 3: Drop or truncate staging
DELETE FROM mydb.staging_events ALL;
```

### Loading Rules

| Method | Supported | Notes |
|---|---|---|
| INSERT-SELECT | Yes | **Recommended** — most efficient |
| TPT Stream / array INSERT | Yes | Not recommended (slower than INSERT-SELECT) |
| BTEQ row-at-a-time | Yes | Acceptable for small volumes |
| FastLoad / TPT Load | **No** | Use staging table pattern |
| MultiLoad / TPT Update | **No** | Use staging table pattern |
| MERGE / UPSERT | **No** | Not supported for PA or NoPI |

### Why Bulk Utilities Don't Work with CP

- FastLoad/TPT Load write directly to data blocks — incompatible with container decomposition
- MultiLoad/TPT Update require in-place row modification — CP uses logical delete + re-append
- MERGE combines insert + update — update semantics don't map to CP storage

## Performance Benchmarks

### IntelliFlex 2.1 Improvements

| Improvement | Detail |
|---|---|
| In-memory optimizations | Enabled by default with ≥512GB memory/node |
| Vector instructions | Applied on predicate columns for faster CP scans |
| Load performance | 10-15% faster than previous releases |
| Query elapsed time | CP tables achieve ~½ elapsed time vs row format |

**How in-memory helps CP:** Join columns, projection columns, and predicate columns stored in separate memory areas → vector instructions applied specifically on predicate columns → faster predicate evaluation on CP tables.

## Autocompression Efficiency

### Factors That Maximize Compression

| Factor | Impact |
|---|---|
| Single column per partition | Best — homogeneous data, max compression |
| Multiple columns per partition | Worse — harder to find compression patterns |
| Many values per container | Better — more data for compression algorithms |
| PA or NoPI (append order) | Better — continuous append fills containers |
| PI (hash order) | Worse — new container per distinct PI value |

### Carry-Forward Optimization

Recent releases optimize autocompression by applying the method from the last container to the next container automatically, checking and adjusting periodically. Autocompression turns itself off if not providing value.

## Delete/Update Patterns

### Delete Semantics

- COLUMN-format partitions: **logical delete only** — bit set in delete column partition
- Space NOT reclaimed until full partition fast-path delete or table rebuild
- ROW-format partitions: physical delete (normal behavior)

### Update Pattern (for tables requiring updates)

1. Mark deleted bit in delete column partition
2. Re-insert updated row (append to end of containers)
3. Results in "dead space" growth over time

### Mitigation: Mirror Table Pattern

```sql
-- Row-based mirror with multi-value compression
CREATE TABLE mydb.events_mirror AS mydb.events_cp
  WITH DATA AND STATS
  PRIMARY INDEX (event_id);
-- Apply updates to mirror
-- Periodically rebuild CP from mirror
```

## Good CP Candidates Checklist

- [ ] MULTISET table, large (>1 GB/AMP)
- [ ] >50 columns with varying access patterns
- [ ] Queries access small subset of columns per query
- [ ] Static or append-only data
- [ ] Few or no single-row updates
- [ ] Few deletes (except row-partition fast-path)
- [ ] Queries have 1-2 highly selective predicates
- [ ] Loading via large INSERT-SELECT batches is acceptable
- [ ] Increased ETL overhead is acceptable
- [ ] Consider hybrid (column + date row partitioning) for partition elimination
