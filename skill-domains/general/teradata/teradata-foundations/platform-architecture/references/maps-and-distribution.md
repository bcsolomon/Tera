# MAPS Architecture & Hash Distribution

## Hash Map Internals

### Hash Distribution Pipeline

```
Row → PI columns → HASHROW() → 32-bit row hash → leading 20 bits = hash bucket
→ Hash map array[hash_bucket] → AMP number
```

- **20-bit hash buckets**: Leading 20 bits of 32-bit row hash → 1,048,576 possible hash buckets
- **Hash map array**: Array of AMP numbers indexed by hash bucket
- **Cell assignment**: Same AMP appears in multiple consecutive cells (cells/AMP = 1,048,576 / num_AMPs)

### Maps System

| Map | Type | Scope |
|---|---|---|
| `TD_GlobalMap` | Contiguous | All AMPs in system |
| `TD_DataDictionaryMap` | Contiguous | DBC tables, SQL procedures, UDFs |
| `TD_Map1` | Contiguous | All user tables (system default) |
| `TD1AmpSparseMap_nNodes` | Sparse (1 AMP) | Small dimension tables |
| `TDnAmpSparseMap_nNodes` | Sparse (n AMPs) | Medium tables |

---

## Contiguous Maps

All AMPs participate. Each AMP owns a contiguous range of hash buckets.

```sql
-- Create table on specific contiguous map
CREATE TABLE mydb.orders, MAP = TD_Map1 (
    order_id INTEGER NOT NULL,
    order_date DATE,
    amount DECIMAL(13,2)
) UNIQUE PRIMARY INDEX (order_id);
```

## Sparse Maps

Subset of AMPs (from parent contiguous map). Tables placed on fewer AMPs → less overhead for small tables.

### Create Sparse Map

```sql
-- Create 64-AMP sparse map from TD_Map1
CREATE MAP My64AmpSparseMap_124Nodes FROM TD_Map1 SPARSE AMPCOUNT=64;
```

### Colocation

Tables in the same sparse map with same colocation name → placed on same AMPs → PI joins without redistribution.

```sql
-- Colocated tables share AMPs
CREATE TABLE mydb.region, MAP = TD1AmpSparseMap_4Nodes
  COLOCATE USING Co_AllRegionTables (
    r_key INTEGER, r_name VARCHAR(30)
) UNIQUE PRIMARY INDEX (r_key);

CREATE TABLE mydb.region_event, MAP = TD1AmpSparseMap_4Nodes
  COLOCATE USING Co_AllRegionTables (
    r_key INTEGER, event_date DATE
) PRIMARY INDEX (r_key);
```

### Small Table Size Threshold

Default: **128 KB per AMP** (`SMALL_TABLE_SIZE_LIMIT` in TDMaps.SettingsTbl = 131,072 bytes).

---

## Moving Tables Between Maps

### ALTER TABLE MAP

```sql
-- Move table to new map (INSERT-SELECT internally, requires 2x space)
ALTER TABLE mydb.orders MAP = My64AmpSparseMap_124Nodes;
```

### TDMaps Stored Procedures (Recommended)

```sql
-- Move table using TDMaps (no DROP TABLE privilege needed)
CALL TDMaps.MoveTablesSP(NULL, 'mydb', 'orders', 'TD_Map1');

-- Analyze which tables should move
CALL TDMaps.AnalyzeSP('MyMapList', ...);

-- Create and populate map list for analysis
CALL TDMaps.CreateMapListSP('MyMapList', NULL, MapListId);
CALL TDMaps.AddMapListSP('MyMapList', 'TD1AmpSparseMap_124Nodes');
CALL TDMaps.AddMapListSP('MyMapList', 'My64AmpSparseMap_124Nodes');
```

### WLM Classification for Table Moves

```sql
SET QUERY_BAND = 'WDClassification=MoveTableToMap;' FOR SESSION;
```

---

## Cross-Map Join Rules

1. Optimizer first considers the **source map** for the step
2. Then the **map of the table to join**
3. Then the **system-default map** (if different)
4. Sparse maps rarely chosen as destination maps
5. **Colocated tables in same sparse map** → no redistribution for PI joins
6. **Non-colocated sparse tables** → all-AMP locking on parent contiguous map

---

## DBC Views for MAPS

```sql
-- List all maps
SELECT MapName, MapNo, MapSlot, MapKind, SystemDefault
FROM DBC.Maps;
-- MapKind: C=Contiguous, S=Sparse

-- Tables NOT on system-default map
SELECT t.DatabaseName, t.TableName, m.MapName
FROM DBC.TablesV t
JOIN DBC.Maps m ON t.MapName = m.MapName
WHERE m.SystemDefault <> 'Y'
  AND m.MapKind = 'C'
  AND m.MapName <> 'TD_DataDictionaryMap'
  AND t.DatabaseName <> 'DBC'
ORDER BY 1, 2;

-- Sparse map AMP assignments
SELECT ObjectName, AmpNo, PF
FROM DBC.SparseMapAmpsV
WHERE DatabaseName = 'mydb'
ORDER BY ObjectName, AmpNo;
-- PF: P=Primary, F=Fallback, PF=Both
```

---

## DBQL MAPS Columns

### DBQLogTbl

| Column | Description |
|---|---|
| `MaxNumMapAMPs` | AMPs in largest contiguous map used by request |
| `MinNumMapAMPs` | AMPs in smallest contiguous map used |
| `SysDefNumMapAMPs` | AMPs in system-default map |
| `MaxAMPsMapNo` | Map number of largest map in request |

### Skew Calculation with MAPS

```sql
-- Standard skew (pre-MAPS):
-- Skew = MaxAmpCPUTime / (AMPCPUTime / (HASHAMP() + 1))

-- MAPS-adjusted skew:
-- Skew = MaxAmpCPUTime / (AMPCPUTime / MaxNumMapAMPs)
```

---

## DBS Control Settings for MAPS

| Setting | Values | Default | Description |
|---|---|---|---|
| MHM (#444) | 0=Disabled, 1=Enabled | Disabled on upgrade, Enabled on new install | Controls MAPS feature |
| NoDot0Backdown | True/False | — | Must be True before enabling MAPS |
| EnableARC4MHM (#482) | True/False | True | ARCMain behavior with MAPS |
| RestoreMapsOption (#483) | 0=Keep target, 1=Replace | 0 | DSA restore map handling |

---

## TDMaps.SettingsTbl

| Setting | Default | Description |
|---|---|---|
| `SMALL_TABLE_SIZE_LIMIT` | 131,072 | Max per-AMP bytes for sparse map candidate |
| `TABLE_HEADER_SIZE` | 1,024 | Table header size for simple tables |
| `SINGLE_AMP_MAP_SIZE_FACTOR` | 1 | Size multiplier for 1-AMP sparse map |
| `USE_PEAK_PERM` | Y | Use peak perm for sparse table sizing |

---

## Elasticity & Capacity

### TCore Activation Levels

| Level | Active CPU Cores | Optimizer Impact |
|---|---|---|
| Level 1 | 33% | None (AMPsPerCPU unchanged) |
| Level 2 | 55% | None |
| Level 3 | 77% | None |
| Level 4 | 100% | AMPsPerCPU > 1 — may change plans |

### Elastic TCore

Software-only CPU limiting via affinity. No restart required. Controlled by `TDEnabledCPUs` in ResUsage.

### WM COD (Capacity on Demand)

CPU hard limits via SLES control groups. Enforcement period/quota mechanism. I/O COD per-disk enforcement.

### Vantage Consumption Model

Metered by **Logical I/O** (Vantage Units). DBQL-based metering via VODUSER telemetry.
