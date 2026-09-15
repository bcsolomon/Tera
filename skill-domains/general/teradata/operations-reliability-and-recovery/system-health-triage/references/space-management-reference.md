# Space Management Reference — SQL SHOWBLOCKS, SHOWWHERE, and TVS

> Source: 541-0010699 (SQL SHOWBLOCKS and SQL SHOWWHERE)

---

## SQL Macros for Space Analysis

SQL replacements for Ferret SHOWBLOCKS and SHOWWHERE — accessible from standard SQL sessions.

### CreateFsysInfoTable

Creates the target table to hold SHOWBLOCKS or SHOWWHERE results.

```sql
EXEC dbc.CreateFsysInfoTable(
  'target_database',   -- Database where target table is created
  'target_table',      -- Name of the target table
  'table_type',        -- 'PERM', 'GLOBALTEMP', or 'VOLATILE'
  'flag',              -- 'Y' = drop/recreate if exists; 'N' = error if exists
  'command',           -- 'SHOWBLOCKS' or 'SHOWWHERE'
  'display'            -- 'S' (Short), 'M' (Medium), or 'L' (Long)
);
```

ANSI variant: `dbc.CreateFsysInfoTable_ANSI` (same parameters; use in ANSI session mode).

### PopulateFsysInfoTable

Runs SHOWBLOCKS or SHOWWHERE and writes results to a target table (or returns immediate results).

```sql
EXEC dbc.PopulateFsysInfoTable(
  'source_database',    -- Database containing the table to analyze
  'source_table',       -- Table to analyze (or CLASS name for SHOWWHERE)
  'command',            -- 'SHOWBLOCKS' or 'SHOWWHERE'
  'display',            -- 'S', 'M', or 'L'
  'target_database',    -- Target DB (empty string = immediate results)
  'target_table'        -- Target table (empty string = immediate results)
);
```

ANSI variant: `dbc.PopulateFsysInfoTable_ANSI`.

**Immediate results:** Pass empty strings `''` for target_database and target_table — results returned directly without creating a table.

No SYSINIT is required. Macros created by DIPSYSFNC (part of DIP). DIPANSI creates ANSI versions.

---

## Required Privileges

```sql
-- Execute macros (granted by DBC)
GRANT EXECUTE ON dbc.CreateFsysInfoTable TO <user>;
GRANT EXECUTE ON dbc.PopulateFsysInfoTable TO <user>;

-- Create target table in target database
GRANT CREATE TABLE ON <target_database> TO <user>;

-- Read source table
GRANT SELECT ON <source_database.source_table> TO <user>;

-- If target table already exists, for other users
GRANT INSERT ON <target_database.target_table> TO <user>;
GRANT DELETE ON <target_database.target_table> TO <user>;
```

**SHOWWHERE requirement:** System must run with TVS Allocation Method = `ONE_DIMENSIONAL` or TBBLC (Temperature Based BLC) enabled in DBSCONTROL. Otherwise SHOWWHERE returns an error.

---

## SHOWBLOCKS — Data Block Distribution Analysis

### Display Options

| Option | Scope | Output |
|---|---|---|
| `'S'` (Short) | Primary subtable only (TAI = 0x400) | Single row, 31 columns |
| `'M'` (Medium) | Each subtable; partially compressed produce separate C/U rows | One row per subtable |
| `'L'` (Long) | Per subtable per DB size; includes DBSize=0 row for cylinder totals | Many rows |

### Output Columns (S Display)

| Column | Description |
|---|---|
| **TableID** | Unique0, Unique1 (byte-flipped), zeros for TypeAndIndex |
| **TableIDTAI** | TypeAndIndex. S display always 1024 (0x400 = primary) |
| **CompressionMethod** | BLC table attribute: AUTOTEMP, MANUAL, ALWAYS, NEVER |
| **CompressionState** | `C` = Fully Compressed, `PC` = Partially Compressed, `U` = Uncompressed, `N` = Not Compressible |
| **EstCompRatio** | Estimated compression ratio. Samples 3 blocks per size range |
| **EstPctOfUncompDBs** | Estimated % of uncompressed data blocks |
| **PctDBsIn1to8** | % of data blocks with 1–8 sectors |
| **PctDBsIn9to24** | % of data blocks with 9–24 sectors |
| **PctDBsIn25to64** | % with 25–64 sectors |
| **PctDBsIn65to120** | % with 65–120 sectors |
| **PctDBsIn121to168** | % with 121–168 sectors |
| **PctDBsIn169to216** | % with 169–216 sectors |
| **PctDBsIn217to256** | % with 217–256 sectors |
| **PctDBsIn257to360** | % with 257–360 sectors |
| **PctDBsIn361to456** | % with 361–456 sectors |
| **PctDBsIn457to512** | % with 457–512 sectors |
| **PctDBsIn513to760** | % with 513–760 sectors |
| **PctDBsIn761to1024** | % with 761–1024 sectors |
| **PctDBsIn1025to1034** | % with 1025–1034 sectors |
| **PctDBsIn1035to1632** | % with 1035–1632 sectors |
| **PctDBsIn1633to2048** | % with 1633–2048 sectors |
| **MinDBSize** | Minimum data block size in sectors |
| **AvgDBSize** | Average data block size in sectors |
| **MaxDBSize** | Maximum data block size in sectors |
| **TotalNumDBs** | Total data blocks (aggregated across all AMPs) |
| **LrgCyls** | Large cylinders occupied |
| **SmlCyls** | Small cylinders occupied |

**Note:** A cylinder can contain multiple subtables/tables. Adding cylinder counts across rows may exceed actual total.

### L Display Additional Columns

| Column | Description |
|---|---|
| **DBSize** | Specific data block size in sectors for this row |
| **DBsPerSize** | Number of data blocks of this specific size |
| **PctOfDBsInSubTable** | % of this size within the subtable |
| **MinNumRowsPerDB** | Min rows per data block for this size |
| **AvgNumRowsPerDB** | Avg rows per data block |
| **MaxNumRowsPerDB** | Max rows per data block |

L display does NOT include the PctDBsInXtoY histogram columns.

**Zero DBSize Row:** For each subtable in L display, a row with `DBSize = 0` provides total cylinder counts only.

### Example Usage

```sql
-- Create target table for SHOWBLOCKS medium display
EXEC dbc.CreateFsysInfoTable('admin_db', 'sb_output', 'VOLATILE', 'Y', 'SHOWBLOCKS', 'M');

-- Populate with data for specific table
EXEC dbc.PopulateFsysInfoTable('mydb', 'orders', 'SHOWBLOCKS', 'M', 'admin_db', 'sb_output');

-- Analyze results
SELECT TableIDTAI, CompressionState, EstCompRatio, TotalNumDBs, LrgCyls
FROM admin_db.sb_output
ORDER BY TableIDTAI;

-- Quick immediate results (no target table)
EXEC dbc.PopulateFsysInfoTable('mydb', 'orders', 'SHOWBLOCKS', 'S', '', '');
```

---

## SHOWWHERE — Cylinder Location and Temperature Analysis

### Display Options

| Option | Scope | Output |
|---|---|---|
| `'S'` (Short) | System-wide summary (Vproc=-1, Drive=-1) | Minimal rows |
| `'M'` (Medium) | Per-AMP summary (Vproc=actual, Drive=-1) | A rows per grade/temp |
| `'L'` (Long) | Per-AMP per-Disk (Vproc=actual, Drive=actual) | Many rows |

### CLASS Values (SHOWWHERE Only)

Specify `'DBC'` as source_database and CLASS as source_table:

| CLASS | Scope |
|---|---|
| `CLASSPERM` | All permanent tables |
| `CLASSJRNL` | All journal tables |
| `CLASSREDRIVE` | All redrive tables |
| `CLASSGLOBALTEMP` | All global temp tables |
| `CLASSSPOOL` | All spool tables |
| `CLASSWAL` | Write Ahead Logging class |
| `CLASSALL` | All above PLUS CLASSDEPOT, WAL POOL, SPOOL POOL |

**CLASS is NOT supported for SHOWBLOCKS** — reading all Cylinder Indexes for a CLASS would be too expensive. SHOWWHERE only reads the Master Index cylinder list.

### SHOWWHERE Output Columns

| Column | Description |
|---|---|
| **Vproc** | -1 for S display; actual AMP# for M/L |
| **Drive** | -1 for S/M; actual drive# for L |
| **LrgCyls** | Large cylinders in this grade |
| **SmlCyls** | Small cylinders in this grade |
| **TableType** | Type of source table |
| **Grade** | TVS storage grade: `FAST`, `MEDIUM`, `SLOW` |
| **GradePct** | % of table's cylinders in this grade |
| **VHCyls** | VERYHOT cylinders (TIM cache) |
| **HotCyls** | HOT cylinders |
| **WarmCyls** | WARM cylinders |
| **ColdCyls** | COLD cylinders |
| **CylsinSSD** | Cylinders on SSD (15.10+, may be zeros) |
| **TemperaturesMature** | Y = meaningful temps; N = system too new to trust |

### Row Count Estimates

| TVS Method | Input | S | M | L |
|---|---|---|---|---|
| TRADITIONAL | Single Table | 1 | A | A × D |
| ONE_DIMENSIONAL | Single Table | 3 | 3 × A | 3 × A × D |

Where A = number of AMPs, D = drives per AMP.

**Worst case:** 2048 AMPs × 64 drives × 27 rows = **3.5M rows** (CLASSALL, 1D).

### Example Usage

```sql
-- Create VOLATILE target for SHOWWHERE
EXEC dbc.CreateFsysInfoTable('admin_db', 'sw_output', 'VOLATILE', 'Y', 'SHOWWHERE', 'M');

-- Analyze specific table temperature
EXEC dbc.PopulateFsysInfoTable('mydb', 'orders', 'SHOWWHERE', 'M', 'admin_db', 'sw_output');

-- Check temperature maturity and grade distribution
SELECT Grade, GradePct, VHCyls, HotCyls, WarmCyls, ColdCyls, TemperaturesMature
FROM admin_db.sw_output;

-- System-wide CLASS analysis
EXEC dbc.PopulateFsysInfoTable('DBC', 'CLASSPERM', 'SHOWWHERE', 'S', 'admin_db', 'sw_output');
```

---

## TableID Format — Decoding Subtables

| Component | Description |
|---|---|
| **Unique0** | Byte-flipped in output |
| **Unique1** | Byte-flipped in output |
| **TypeAndIndex (TAI)** | NOT byte-flipped. Identifies the subtable. |

### Key TAI Values

| TAI (Hex) | TAI (Dec) | Subtable |
|---|---|---|
| 0x000 | 0 | Table header |
| 0x400 | 1024 | Primary data |
| 0x404 | 1028 | Secondary index |
| 0x408 | 1032 | Secondary index |
| 0x700 | 1792 | Reference/hash index |
| 0x800 | 2048 | Fallback data |
| 0x804 | 2052 | Fallback secondary index |
| 0xB00 | 2816 | Fallback reference/hash index |

---

## TVS Concepts

### Storage Grades

| Grade | Description |
|---|---|
| **FAST** | Highest-performance storage tier |
| **MEDIUM** | Mid-tier storage |
| **SLOW** | Lowest-performance storage |

### TVS Allocation Methods

| Method | Abbreviation | Behavior |
|---|---|---|
| TRADITIONAL_TERADATA | TT | Ignores grade; no cylinder migration. Tracks temp only if TBBLC enabled. |
| ONE_DIMENSIONAL | 1D | Tracks temperature AND grade. Cylinders migrate between grades by temperature. |

### Temperature Classification

| Temperature | Description |
|---|---|
| **VERYHOT** | Most frequently accessed (TIM cache) |
| **HOT** | Frequently accessed |
| **WARM** | Moderately accessed |
| **COLD** | Infrequently accessed |

Temperature determined by frequency of reads/writes to cylinders.

- **TemperaturesMature = Y** — System has enough history for meaningful temps
- **TemperaturesMature = N** — Results should NOT be trusted; need more system usage

### Cylinder Sizes

| Type | Sectors | Bytes |
|---|---|---|
| Large | 23,232 | ~11.3 MB |
| Small | 3,872 | ~1.9 MB |

### Key File System Structures

| Structure | Description |
|---|---|
| **Master Index (MI)** | Per-AMP top-level index. Entry for each cylinder. |
| **Cylinder Index (CI)** | At beginning of each cylinder. Contains Data Block Descriptors. |
| **Data Block Descriptor (DBD)** | In CI — identifies location, size, row count of each DB. |
| **Data Block (DB)** | Contains rows. Single subtable. BIG (≤1MB) or SMALL (≤128KB). |

---

## Ferret vs SQL Comparison

| Aspect | Ferret | SQL Equivalent |
|---|---|---|
| Access | Requires DBCCONS / CNS | Standard SQL sessions |
| Sessions | Limited | Many concurrent |
| Output | Text only | Query results, target tables |
| Post-processing | Difficult | Easy — SQL on target tables |
| Historical tracking | Manual | Query target over time |
| CLASS option | Both commands | SHOWWHERE only (not SHOWBLOCKS) |
| Per-AMP SHOWBLOCKS | Supported | NOT supported |

---

## Performance Considerations

### SHOWBLOCKS

- Reads all Cylinder Indexes of specified table — does NOT read Data Blocks
- Large tables may have tens of thousands of CIs
- ~11.6% wall clock increase for concurrent FTM operations
- Use `'L'` with caution on large tables

### SHOWWHERE

- Only reads Master Index cylinder list — negligible impact
- Sends to TVS for temperature/grade classification
- S and M options: negligible concurrent impact
- L option: minimal impact
- **Volume concern:** CLASSALL on large configs = millions of rows. Use VOLATILE target tables.

### Target Table Maintenance

- PERM tables require periodic purging of old rows
- VOLATILE/GLOBALTEMP auto-delete at session end
- Create separate target tables per display option (e.g., `SHOWWHERE_Output_M`)
