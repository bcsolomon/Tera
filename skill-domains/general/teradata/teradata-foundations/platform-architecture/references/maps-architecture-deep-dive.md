# MAPS Architecture Deep Dive

> Source: TDN0009415 — Teradata MAPS Architecture, Version 16.20 Feature Update 2 (Orange Book by Fred Kaufmann, Carrie Ballinger)

## Purpose of MAPS

MAPS (Multiple Array of Parallel Servers) allows tables to be assigned to a subset of AMPs in the system by supporting multiple hash maps simultaneously. Two key benefits:

1. **Increased availability during system expansion** — decouple row redistribution from hardware addition, reducing downtime from hours/days to minutes
2. **Small table efficiency** — place small tables on fewer AMPs to avoid wasted all-AMP operations on AMPs with no rows

---

## Contiguous Maps

A contiguous map covers a **continuous range of AMPs**, typically all AMPs from 0 to N-1. Every AMP in the range participates in data distribution for tables assigned to that map.

### Properties

- Created by the **Reconfig utility** during system expansion or at upgrade to 16.10
- Named sequentially: `TD_Map1`, `TD_Map2`, `TD_Map3`, etc. (system-controlled naming)
- All tables in the same contiguous map have rows spread across the same AMP range
- Fallback copies reside within the same contiguous map as primary copies

### Multiple Contiguous Maps

After a system expansion, two contiguous maps exist temporarily:

```
Before expansion:  TD_Map1 = AMPs 0-15  (all user tables)
After expansion:   TD_Map1 = AMPs 0-15  (existing tables remain)
                   TD_Map2 = AMPs 0-19  (new system-default, used by new tables/spools)
```

**No performance advantage** exists in having multiple contiguous maps — more AMPs always means more parallelism. Multiple maps should be a **temporary state** lasting weeks, not months. Having tables scattered across many contiguous maps makes query tuning difficult and skew analysis confusing.

### Special Contiguous Maps

| Map | Purpose | Expansion Behavior |
|---|---|---|
| `TD_GlobalMap` | All AMPs in current configuration | Auto-expanded by Reconfig |
| `TD_DataDictionaryMap` | DBC tables, SQL procedures, UDFs | Optional expansion during Reconfig |
| `TD_Map1`, `TD_Map2`... | User tables, join indexes | Created sequentially by each Reconfig |

### Default Map Resolution Hierarchy

When a table is created without specifying a map, the system resolves the map via:

1. **Table-level** — `CREATE TABLE ... MAP = TD_Map1` (explicit)
2. **Profile-level** — Profile assigned to the user with a default map
3. **User-level** — User record with a default map
4. **System-default** — The newest contiguous map set by Reconfig

```sql
-- Create table on a specific map
CREATE TABLE mydb.orders, MAP = TD_Map1 (
    order_id INTEGER NOT NULL,
    order_date DATE,
    amount DECIMAL(13,2)
) UNIQUE PRIMARY INDEX (order_id);
```

**Recommendation:** Rely on the system-default map for new tables. This ensures maximum parallelism and avoids stale map assignments after future expansions.

---

## Sparse Maps

A sparse map uses a **single AMP or a small subset of AMPs**, selected from a parent contiguous map. Rows of sparse-map tables coexist on the same physical AMPs with rows of contiguous-map tables.

### Contiguous vs Sparse Comparison

| Property | Contiguous Maps | Sparse Maps |
|---|---|---|
| AMP coverage | All AMPs in a continuous range | 1 or a few AMPs from parent map |
| Creation | Reconfig utility or upgrade | DIPMAPS utility or `CREATE MAP` SQL |
| Table row placement | Same AMP range for all tables in map | Different tables may use different AMPs |
| Purpose | General data distribution | Small table efficiency |
| All-AMP scan | Uses all map AMPs | Uses only the sparse map's AMPs |

### Default Sparse Maps

Created automatically when MAPS is enabled:

| Map | AMP Count | Suitable Table Size |
|---|---|---|
| `TD1AmpSparseMap_nNodes` | 1 AMP | ≤ 128 KB per AMP (after header overhead) |
| `TDnAmpSparseMap_nNodes` | n AMPs (1 per node) | ≤ 128 KB × n AMPs (multi-node systems only) |

### Suitable Candidates for Sparse Maps

- Tables with fewer rows than AMPs in the configuration
- **High-usage** dimension/lookup tables (check DBQL USECOUNT)
- Tables expected to remain small over time

**Do NOT move:**
- Empty tables (may be temporary staging targets)
- Tables likely to grow beyond the sparse map threshold
- Tables used as staging/ETL targets

```sql
-- Check candidate tables using the sizing view
SELECT * FROM TDMaps.TableToSparseMapSizingV
WHERE DatabaseName = 'mydb'
ORDER BY CurrentPermKB DESC;
```

### Creating Custom Sparse Maps

```sql
-- Create a 64-AMP sparse map from TD_Map1
CREATE MAP My64AmpSparseMap_124Nodes FROM TD_Map1 SPARSE AMPCOUNT=64;

-- Grant map to TDMaps user (required for Viewpoint portlet)
GRANT MAP My64AmpSparseMap_124Nodes TO TDMaps;
```

### Colocation in Sparse Maps

Tables in the same sparse map with the same colocation name are placed on the **same AMP(s)**, enabling local PI joins without redistribution.

```sql
-- Colocate two related small tables
CREATE TABLE mydb.region, MAP = TD1AmpSparseMap_4Nodes
  COLOCATE USING Co_AllRegionTables (
    r_key INTEGER, r_name VARCHAR(30)
) UNIQUE PRIMARY INDEX (r_key);

CREATE TABLE mydb.region_event, MAP = TD1AmpSparseMap_4Nodes
  COLOCATE USING Co_AllRegionTables (
    r_key INTEGER, event_date DATE
) PRIMARY INDEX (r_key);
```

Without colocation, two sparse-map tables joined by PI trigger **all-AMP locking** on the parent contiguous map. With colocation, locking is confined to just the sparse map AMPs.

### Viewing Sparse Map AMP Assignments

```sql
SELECT ObjectName, AmpNo, PF
FROM DBC.SparseMapAmpsV
WHERE DatabaseName = 'mydb'
ORDER BY ObjectName, AmpNo;
-- PF column: P=Primary, F=Fallback, PF=Both
```

---

## System Expansion Procedure

### Expansion Workflow with MAPS

1. Wire new nodes into configuration
2. Bring system up, run **Config** utility (defines new AMPs and PEs)
3. Run **Reconfig** utility — creates new contiguous map, updates `TD_GlobalMap`
4. Reconfig prompts for table movement strategy:

| Option | Action | Downtime Impact |
|---|---|---|
| **1. No tables** | Postpone all movement (recommended) | Minimal downtime |
| 2. Dictionary tables | Expand `TD_DataDictionaryMap` only | Moderate |
| 3. Specific user tables | Move tables listed in `DBC.ReconfigRedistOrderTbl` | Variable |
| 4. All user tables | Full redistribution during offline Reconfig | Maximum |

**Recommended:** Select option 1. Move tables online after expansion using ALTER TABLE or Viewpoint.

### Space Management During Reconfig

```
Reconfig prompts:
> "All new space to DBC?"  → Answer: NO (prorate across all databases)
> "Space adjustment %?"    → Answer: 100 (distribute new space proportionally)
> "System-default map?"    → Answer: TD_MapN (the newest, largest map)
```

Space is managed globally via `DBC.GlobalDBSpace` (global tracking) and `DBC.DatabaseSpace` (per-AMP tracking). After expansion, old AMPs remain fully packed while new AMPs are empty — ALTER TABLE requires **2× table space** to hold source and destination copies simultaneously.

### Skew Limit for Space

A configurable **skew limit** allows AMPs to exceed their per-AMP space quota by a percentage:

```sql
-- Check current skew limit
SELECT SkewLimit FROM DBC.GlobalDBSpace WHERE DatabaseName = 'mydb';
```

Default skew limit is 100% — an AMP can use up to 2× its calculated per-AMP quota. This prevents out-of-space errors when tables are concentrated on a subset of AMPs.

---

## Moving Tables Between Maps

### Three Methods

| Method | Best For | Statistics | DROP TABLE Privilege |
|---|---|---|---|
| **Viewpoint Maps Manager** | Batch moves with analysis | Auto-collected | Not required |
| `TDMaps.MoveTablesSP` | Individual table moves | Auto-collected | Not required (when run as TDMaps) |
| `ALTER TABLE ... MAP =` | Manual single-table moves | Must collect manually | Required |

### ALTER TABLE MAP Mechanics

The map-specific ALTER TABLE performs an **INSERT-SELECT** from the old map to the new map:

- A **read lock** is held on the source table during the INSERT-SELECT (data remains accessible)
- At completion, the lock is briefly upgraded to **exclusive** for the metadata swap
- If aborted, rollback is a quick drop of the destination copy — source data remains intact
- **Space requirement:** 2× table size (3× for NoPI/columnar tables due to intermediate sort)

```sql
-- Move a table to the new contiguous map
ALTER TABLE mydb.orders MAP = TD_Map2;

-- Recollect summary statistics after manual move
COLLECT SUMMARY STATISTICS ON mydb.orders;
```

### Using TDMaps Stored Procedures

```sql
-- Move a single table (auto-collects summary stats)
CALL TDMaps.MoveTablesSP(NULL, 'mydb', 'orders', 'TD_Map2');

-- Set query band for WLM classification of move activity
SET QUERY_BAND = 'WDClassification=MoveTableToMap;' FOR SESSION;
```

### Viewpoint Workflow

1. **Analyzer job** → evaluates tables, identifies PI join groups, recommends map assignments → output: `TDMaps.ActionsTbl`
2. **Review** → administrator reviews/modifies recommendations
3. **Mover job** → executes ALTER TABLEs via parallel workers consuming from `TDMaps.ActionQueueTbl`

**Workers:** Keep to low single digits (2 for appliances, 4 for EDW). Each worker moves one table at a time. Monitor disk usage — do not add workers once disk hits 95%.

### Handling Very Large Tables

| Strategy | When to Use |
|---|---|
| Move during Reconfig (option 3) | No free space for 2× table copy |
| Single worker in Mover job | Limited free space, need to single-thread |
| Partition split + UNION view | Partitioned table, move current partition only |

**Partition split approach:**

1. Rename `SalesData` → `Old_SalesData`
2. Create new `SalesData` in the new map
3. INSERT-SELECT current partition from `Old_SalesData`
4. DROP current partition from `Old_SalesData`
5. Create UNION view spanning both tables with date-range WHERE clauses

### Special Move Considerations

- **NoPI tables** — Reconfig cannot move them (no PI to hash); must use ALTER TABLE
- **Join indexes** — must be explicitly moved separately from base tables (not auto-moved)
- **Temporal table JIs** — system-generated JIs are auto-moved with the temporal table
- **JIs on NoPI/columnar with ROWID** — invalidated when base table moves; must rebuild
- **Secondary indexes (USI/NUSI)** — automatically moved with the base table

### Identifying Tables Not Yet Moved

```sql
SELECT t.DatabaseName, t.TableName, m.MapName
FROM DBC.TablesV t
JOIN DBC.Maps m ON t.MapName = m.MapName
WHERE m.SystemDefault <> 'Y'
  AND m.MapKind = 'C'
  AND m.MapName <> 'TD_DataDictionaryMap'
  AND t.DatabaseName <> 'DBC'
ORDER BY 1, 2;
```

### Monitoring Move Progress

```sql
-- Tables ready to move
SELECT * FROM TDMaps.ActionsTbl WHERE Status = 'Ready';

-- Tables currently in progress
SELECT * FROM TDMaps.ActionHistoryTbl WHERE Status = 'InProgress';

-- Completed moves
SELECT * FROM TDMaps.ActionHistoryTbl WHERE Status = 'Complete';

-- Failed moves (check ErrorCode)
SELECT * FROM TDMaps.ActionHistoryTbl WHERE Status = 'Failed';
```

### Estimating Move Time

```sql
-- After at least one table has been moved, derive MB/s rate
SELECT AVG(TableSize) / AVG(ElapsedTime) AS mb_per_sec
FROM TDMaps.ActionHistoryTbl
WHERE Status = 'Complete'
  AND ElapsedTime > 300;
-- Divide target table size by this rate for estimated seconds
```

---

## Backup and Restore with MAPS

### DSA (Data Stream Architecture) — Recommended

DSA is **map-aware** and can process tables from different maps during both backup and restore.

- DSA validates which AMPs are in each table's map during the Dictionary phase (may cause that phase to run longer)
- MAP clause can be included in restore jobs to direct tables to a specific map

### Legacy ARCMain — Limited Support

ARCMain has **not been updated** for multiple maps:

- Can only operate on tables in a contiguous map equivalent to `TD_GlobalMap` (all AMPs)
- `TD_DataDictionaryMap` must be expanded to all AMPs before using ARCMain
- If any table in the job is not in the all-AMP map, the job **fails**

Controlled by DBS Control `EnableARC4MHM` (#482):

| Setting | Behavior |
|---|---|
| `True` (default) | ARCMain runs but fails if any object is not in the all-AMP map |
| `False` | ARCMain is blocked entirely; returns error |

### DSA Restore Options

Controlled by DBS Control `RestoreMapsOption` (#483):

| Option | Behavior | Best For |
|---|---|---|
| **0 — Keep target maps** (default) | Tables restored into target's system-default map; source map definitions ignored | NPARC migration to different-sized system |
| **1 — Replace maps from dump** | Source map definitions replace target's; tables retain source map assignments | Disaster recovery to identical configuration |

**Option 0 consequences:**
- All tables (including sparse map tables) go into the system-default map
- Sparse maps must be re-created and tables re-moved on the target system
- Default map assignments in Database/User/Profile records are set to NULL

**Option 1 consequences:**
- Target system mirrors source map structure exactly
- No benefit from additional AMPs on the target system
- Must run Config utility to create a new all-AMP map, then move tables

### NPARC Procedure (Data Migration)

1. Before NPARC: record all sparse maps and their table assignments
2. Run NPARC with option 0 (Keep target maps)
3. After completion: redo map grants, re-create sparse maps, re-move small tables

---

## MAPS Configuration and Administration

### Enabling MAPS

1. Set DBS Control `NoDot0Backdown = True` (prevents downgrade — irreversible)
2. Set DBS Control `MHM` (#444) to `1` (Enabled — also irreversible)
3. Run **DIPMAPS** to create default sparse maps and the TDMaps database

| DBS Control Field | Values | Default | Notes |
|---|---|---|---|
| `MHM` (#444) | 0=Disabled, 1=Enabled | Disabled on upgrade, Enabled on new install | Cannot revert to 0 |
| `NoDot0Backdown` | True/False | — | Must be True before enabling MHM |
| `EnableARC4MHM` (#482) | True/False | True | Controls legacy ARCMain behavior |
| `RestoreMapsOption` (#483) | 0=Keep target, 1=Replace | 0 | DSA restore map handling |

### TDMaps Database

Contains procedures, tables, and views for automated map management:

| Object | Purpose |
|---|---|
| `MoveTablesSP` | Move a single table to a new map (+ summary stats collection) |
| `ManageMoveTablesSP` | Queue manager for batch moves |
| `AnalyzeSP` | Analyze tables and recommend map assignments |
| `CreateMapListSP` | Create a named list of maps for analysis |
| `AddMapListSP` | Add a map to an existing map list |
| `StopMoveTablesSP` | Gracefully stop a running Mover job |
| `CleanUpMoveTablesSP` | Clean up after abort/restart |
| `ActionsTbl` | Planned actions from Analyzer |
| `ActionHistoryTbl` | Historical move results (status, elapsed time, errors) |
| `ActionQueueTbl` | Active queue for Mover workers |
| `SettingsTbl` / `SettingV` | Configuration settings for sparse map sizing |
| `TableToSparseMapSizingV` | View to identify sparse map candidates |

### Security and Access Control

```sql
-- Grant map to a user (required to use MAP clause in CREATE/ALTER)
GRANT MAP TD_Map2 TO username;

-- Create and drop map privileges
GRANT CREATE MAP TO admin_user;
GRANT DROP MAP TO admin_user;
```

- Default map does not require an explicit grant
- `TDMaps` user has special privileges (no DROP TABLE needed for MoveTablesSP)
- Sparse maps can be associated with **secure zones**; contiguous maps cannot
- Sparse maps can only be granted within the same secure zone

### Viewing Map Metadata

```sql
-- List all maps with properties
SELECT MapName, MapNo, MapSlot, MapKind, SystemDefault
FROM DBC.Maps;

-- MapKind: C=Contiguous, S=Sparse
-- SystemDefault: Y=current system-default map
```

---

## Query Behavior with MAPS

### Cross-Map Joins

When a query joins tables from different maps, the optimizer:

1. Considers the **source map** for the step
2. Considers the map of the **table to be joined**
3. Considers the **system-default map** if different from both

The system-default map (largest AMP count) is typically chosen as the destination for redistributions.

### PI Join Impact

Two tables sharing the same PI but in **different contiguous maps** cannot do a local PI join — different hash maps produce different AMP assignments for the same PI value. This becomes a PI-to-Non-PI join requiring redistribution.

**Mitigation:** Move related tables that frequently participate in PI joins to the same map at the same time.

### Skew Interpretation

After expansion with tables in multiple maps, reported skew increases because:

```
Standard:  Skew = MaxAmpCPUTime / (AMPCPUTime / (HASHAMP() + 1))
                  ← denominator uses ALL AMPs, inflating apparent skew

MAPS-adjusted:  Skew = MaxAmpCPUTime / (AMPCPUTime / MaxNumMapAMPs)
                       ← denominator uses only the AMPs in the query's map
```

Use `MaxNumMapAMPs` and `MinNumMapAMPs` from `DBQLogTbl` for accurate skew calculations.

### WLM Considerations

- "All AMPs" classification is **map-specific** — a scan of a 6-AMP sparse map counts as all-AMP
- TASM skew exceptions are calculated based on AMPs active in the step, not all system AMPs
- Table moves classify to the `WD-MapsMover` workload (Timeshare High by default)

---

## Data Dictionary Map Considerations

### Pros of Expanding TD_DataDictionaryMap

- Required if using legacy ARCMain (dictionary must be in all-AMP map)
- Benefits X-View queries that do all-AMP scans/aggregations on DBC tables

### Cons of Expanding TD_DataDictionaryMap

- Extends Reconfig downtime (must move all DBC tables, procedures, UDFs, source code)
- Most DBC access is single-AMP express requests — more AMPs provide no benefit
- DBC tables are generally small/moderate in size

### Recommendation

Defer dictionary expansion unless you rely on ARCMain or have heavy X-View usage. If expanding, first trim monitoring tables (`DBQLogTbl`, `ResUsageSPVR`) to minimize redistribution time. Dictionary expansion can always be done later via a standalone Reconfig run.

---

## Administrator Checklist

Post-expansion ongoing tasks:

1. Verify all tables are being moved to the new system-default map on schedule
2. Drop old contiguous maps once empty (drop child sparse maps first)
3. Monitor sparse map table sizes via `TDMaps.TableToSparseMapSizingV`
4. Identify new small-table candidates for sparse maps
5. Review Profile/User default map assignments after each expansion
6. Recollect statistics on tables moved manually (auto-collected by MoveTablesSP)
7. Keep PI-joined tables in the same map — move them together

### Loading Considerations

- TPT Load/Update operators use the target table's map automatically
- Maximum utility sessions = number of AMPs in the target table's map
- For multi-target TPT Update, max sessions = common AMPs across all target maps
- Work tables and error tables are placed in the same map as the target table
