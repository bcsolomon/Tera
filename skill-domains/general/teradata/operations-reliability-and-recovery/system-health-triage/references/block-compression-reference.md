# Block-Level Compression Reference

> Source: TDN0001167 (Block-Level Compression)

---

## Compression Methods Comparison

| Method | Scope | Avg Reduction | Overhead | Best For |
|---|---|---|---|---|
| **MVC** (Multi-Value) | Column — up to 255 values | 33% | None (data in table header) | CPU-bound systems (≥75%), columns with repeating values |
| **ALC** (Algorithmic) | Column — all compressible values | Varies | CPU per column access | Large CHAR/VARCHAR/BYTE, infrequent access |
| **BLC** (Block-Level) | Entire data block | ~60% | Entire block decompressed on any access | Space-constrained, ≤60% CPU utilization |

### Combining Methods

| Combination | Recommendation |
|---|---|
| **MVC + BLC** | Recommended. No double decompression penalty. MVC reduces pre-BLC size. |
| **ALC + BLC** | NOT recommended. Double decompression overhead, little benefit. |
| **MVC + ALC + BLC** | Possible but diminishing returns. |
| **Columnar Autocompression + BLC** | Compatible. Applied independently. |

---

## BLC Modes

### Table-Level Attribute Syntax

```sql
CREATE TABLE tablename, BLOCKCOMPRESSION = MANUAL
  (col1 INTEGER, col2 VARCHAR(100))
  PRIMARY INDEX (col1);

ALTER TABLE tablename, BLOCKCOMPRESSION = AUTOTEMP;
```

### Mode Descriptions

| Mode | Behavior | Requirements |
|---|---|---|
| **MANUAL** | Compressed/uncompressed via query bands, DBS Control, or Ferret. All-or-nothing per subtable. | BLC=ON + params 14–21 ≠ all NEVER/ALWAYS |
| **AUTOTEMP** | Temperature-based. Cylinders auto-compressed/uncompressed by background task. | BLC=ON + EnableTempBLC=TRUE |
| **NEVER** | Complete override — never compressed. Query bands and Ferret COMPRESS rejected. | BLC=ON |
| **ALWAYS** (16.0+) | All eligible subtables always compressed regardless of query bands. Ferret UNCOMPRESS rejected. | BLC=ON |
| **DEFAULT** | Uses DBS Control DefaultTableMode. Does NOT appear in SHOW TABLE output. | BLC=ON |

### Algorithm and Level Attributes (TD 16.0)

```sql
CREATE TABLE t, BLOCKCOMPRESSIONALGORITHM = ZLIB | ELZS_H | DEFAULT (...);
CREATE TABLE t, BLOCKCOMPRESSIONLEVEL = 1-9 | DEFAULT (...);

ALTER TABLE t, BLOCKCOMPRESSIONALGORITHM = ZLIB;
ALTER TABLE t, BLOCKCOMPRESSIONLEVEL = 5;
```

| Algorithm | Description |
|---|---|
| ZLIB | Software BLC. Always available. |
| ELZS_H | Hardware Compression Engine. Requires hardware support. |
| DEFAULT | Uses DBS Control CompressionAlgorithm setting |

Level: 1 = max speed, 9 = max compression ratio.

**ALTER TABLE IMMEDIATE is NOT allowed** when changing BlockCompression, BlockCompressionAlgorithm, or BlockCompressionLevel. Changes not retroactive — existing blocks remain in prior state.

### Querying from Data Dictionary

```sql
SELECT DatabaseName, TableName, BlockCompression,
       BlockCompressionAlgorithm, BlockCompressionLevel
FROM DBC.TablesV
WHERE BlockCompression IN ('AUTOTEMP', 'ALWAYS', 'MANUAL');
```

---

## DBS Control Compression Parameters

Access via `ctl` utility, DBS Control section 9 (Compression Fields).

### Master Switch

| # | Parameter | Default | Description |
|---|---|---|---|
| 1 | **BlockLevelCompression** | OFF | Master switch. Must be ON for any BLC. No restart needed. |

### Spool and Utility

| # | Parameter | Default | Options | Description |
|---|---|---|---|---|
| 3 | **CompressSpoolDBs** | NEVER | ALWAYS, NEVER, IFNOTCACHED | Spool table compression |
| 5 | **CompressMloadWorkDBs** | NEVER | ALWAYS, UNLESSQBNO, NEVER, ONLYIFQBYES | MultiLoad work tables |
| 6 | **CompressPJDBs** | NEVER | ALWAYS, NEVER | Permanent journal tables |

### Compression Quality

| # | Parameter | Default | Description |
|---|---|---|---|
| 7 | **MinDBSectsToCompress** | 32 (large cyl), 14 (small) | Min data block sectors to qualify for compression |
| 8 | **MinPercentCompReduction** | 20% | Block must achieve this % reduction or stored uncompressed |
| 9 | **CompressionAlgorithm** | ZLIB | ZLIB, ELZS_H, ELZS_S |
| 10 | **CompressionLevel** | 6 | 1–9. Ignored if algorithm ≠ ZLIB |
| 12 | **UncompressReservedSpace** | 5% | Stops Ferret uncompress if free cylinders fall below this % |

### Per-Subtable Control (Parameters 14–21)

| # | Parameter | Default | Scope |
|---|---|---|---|
| 14 | **CompressPermPrimaryDBs** | ONLYIFQBYES | Primary data blocks of user tables |
| 15 | **CompressPermFallbackDBs** | ONLYIFQBYES | Fallback data + ALL index subtables |
| 16 | **CompressPermPrimaryCLOBDBs** | NEVER | Primary CLOB data blocks |
| 17 | **CompressPermFallbackCLOBDBs** | NEVER | Fallback CLOB data blocks |
| 18 | **CompressGlobalTempPrimaryDBs** | NEVER | GTT primary data blocks |
| 19 | **CompressGlobalTempFallbackDBs** | NEVER | GTT fallback data blocks |
| 20 | **CompressGlobalTempPrimaryCLOBDBs** | NEVER | GTT primary CLOB data blocks |
| 21 | **CompressGlobalTempFallbackCLOBDBs** | NEVER | GTT fallback CLOB data blocks |

Each accepts: **ALWAYS** | **UNLESSQBNO** | **NEVER** | **ONLYIFQBYES**

| Option | Behavior |
|---|---|
| ALWAYS | Always compress, ignore query bands (16.0+) |
| UNLESSQBNO | Compress unless query band says NO |
| NEVER | Never compress |
| ONLYIFQBYES | Only if query band says YES |

### Temperature-Based BLC Parameters

| # | Parameter | Default | Range | Description |
|---|---|---|---|---|
| 32 | **EnableTempBLC** | FALSE | TRUE/FALSE | Enables AutoTempComp background task |
| 33 | **DefaultTableMode** | MANUAL | AUTOTEMP, MANUAL, ALWAYS, NEVER | System-wide default for tables without explicit TLA |
| 34 | **TempBLCThresh** | COLD | COLD, WARM, HOT, 0–100 | Temperature boundary. COLD = bottom 20% of perm cylinders |
| 35 | **TempBLCSpread** | 5% | 1–25% | Hysteresis — prevents compress/uncompress oscillation |
| 36 | **TempBLCInterval** | 10 min | 1–120 | Sleep between tables during AutoTempComp scan |
| 37 | **TempBLCIOThresh** | 1 | 1–1000 | I/O threshold for compression decision |
| 38 | **TempBLCPriority** | MEDIUM | LOW, MEDIUM, HIGH, RUSH | Priority of AutoTempComp task |
| 39 | **TempBLCRescanPeriod** | 7 days | 1–90 | Hibernation when at steady state |
| 40 | **CompressionZLIBMethod** | IPPZLIB | ZLIB, IPPZLIB | IPP ZLIB ~5-10% less CPU. Compatible with standard ZLIB. |
| 41 | **OverrideARCBLC** | FALSE | TRUE/FALSE | If TRUE, target DBS Control settings used on restore instead of archive BLC status |

---

## Ferret Compression Commands

### COMPRESS

```
COMPRESS "database.table" [PRIMARY | FALLBACK | FALLBACKANDCLOBS | WITHOUT CLOBS | ONLY CLOBS] [ESTIMATE]
COMPRESS "database.*"         -- all tables in database (TD 14.0+)
```

### UNCOMPRESS

```
UNCOMPRESS "database.table" [PRIMARY | FALLBACK | FALLBACKANDCLOBS | WITHOUT CLOBS | ONLY CLOBS] [ESTIMATE]
```

### Subtable Scope Matrix

| Clause | Primary | Fallback | Primary CLOB | Fallback CLOB |
|---|---|---|---|---|
| (none) | System default | System default | System default | System default |
| PRIMARY | Yes | — | Yes | — |
| FALLBACK | — | Yes | — | Yes |
| ONLY CLOBS | — | — | Yes | Yes |
| WITHOUT CLOBS | Yes | Yes | — | — |
| FALLBACKANDCLOBS | — | Yes | Yes | Yes |

### ESTIMATE Option

No compression occurs. Samples 3 data blocks per size range. Returns:
- Estimated block size reduction
- CPU usage estimate
- Cylinders required

### SHOWBLOCKS (Ferret)

```
SHOWBLOCKS "database.table"
```

Shows data block size distribution, compression status (C/PC/U/N), total blocks and cylinders.

### SHOWCOMPRESS

```
SHOWCOMPRESS          -- short: list all compressed tables with mode
SHOWCOMPRESS/L        -- long: reads ALL data blocks (time-consuming)
```

Long display adds exact compression ratio and % of blocks compressed per table.

### Ferret Behavior

- No transaction locks — table fully available during compression
- Space-conserving: processes one cylinder at a time
- TD 14.10+: auto-restarts after system restart
- TD 14.0 and earlier: requires `UpdateSpace` utility after compress/uncompress

### Error Conditions

| Condition | Result |
|---|---|
| BlockLevelCompression = OFF | Error on COMPRESS |
| Params 14–21 all NEVER (MANUAL mode) | Error compressing that subtable |
| Params 14–21 all ALWAYS (MANUAL mode) | Error uncompressing that subtable |
| Table mode = ALWAYS | Error on UNCOMPRESS |
| Table mode = NEVER | Error on COMPRESS |

---

## Query Bands for Compression

### Manual Mode

```sql
SET QUERY_BAND = 'BlockCompression=YES;' UPDATE FOR SESSION;
SET QUERY_BAND = 'BlockCompression=NO;' UPDATE FOR SESSION;
```

### BLOCKCOMPRESSION Parameter Values

| Value | Primary | Fallback | Primary CLOB | Fallback CLOB |
|---|---|---|---|---|
| YES / ALL | Yes | Yes | Yes | Yes |
| NO / NONE | — | — | — | — |
| FALLBACK | — | Yes | — | Yes |
| ONLYCLOBS | — | — | Yes | Yes |
| WITHOUTCLOBS | Yes | Yes | — | — |
| FALLBACKANDCLOBS | — | Yes | Yes | Yes |

**Rules:**
- Only honored on **EMPTY** tables. No effect on non-empty tables.
- No separate option for primary-only (unlike Ferret)
- Ignored for ALWAYS and NEVER mode tables

### Default Query Band on User

```sql
CREATE USER etl_user AS PERM=0,
  PASSWORD = etl_user,
  STARTUP = 'SET QUERY_BAND=''BLOCKCOMPRESSION=YES;'' FOR SESSION;';
```

Note: double single quotes (`''`) inside STARTUP string.

### TVS Temperature Query Bands (AutoTemp Mode)

```sql
SET QUERY_BAND = 'TVSTEMPERATURE_PRIMARY=COLD;' UPDATE FOR SESSION;
SET QUERY_BAND = 'TVSTEMPERATURE_PRIMARYCLOBS=COLD;' UPDATE FOR SESSION;
SET QUERY_BAND = 'TVSTEMPERATURE_FALLBACK=COLD;' UPDATE FOR SESSION;
SET QUERY_BAND = 'TVSTEMPERATURE_FALLBACKCLOBS=COLD;' UPDATE FOR SESSION;
```

Values: HOT, WARM, COLD. Only COLD is useful for BLC.

---

## TVS Temperature Concepts

### Temperature Boundaries

- **Cold-Warm boundary** — default bottom 20% of allocated permanent cylinders (excludes spool, GTT, WAL)
- **Warm-Hot boundary** — separates warm from hot

### How Temperature is Tracked

- Access counts tracked per cylinder, periodically reevaluated
- Both read and write I/Os increment the count
- Small cylinder read = 4 accesses (512 KB chunks)
- Large cylinder read = 24 accesses (6× larger)
- Counts produce numeric temperature per cylinder (range into billions)
- Sorted list determines boundaries
- Temperature is **relative**, not absolute
- TVS may need **a week or more** for meaningful statistics

### AutoTempComp Background Task

1. Runs independently on each AMP
2. Reads master index, examines cylinder IDs and table ID ranges
3. Checks table header for AutoTemp attribute
4. Compares cylinder temperature to TempBLCThresh
5. Compresses contiguous cylinder ranges within a table
6. Sleeps TempBLCInterval (default 10 min) between tables
7. Steady-state hibernation: TempBLCRescanPeriod (default 7 days)
8. TVS overhead: <2% system resources

### AutoTempComp — Included Subtables

Primary data, fallback data, index fallback subtables, CLOB subtables

### AutoTempComp — Excluded

Primary index subtables, DBC tables, spool, permanent journals, GTTs, MultiLoad work tables, cylinder indexes, BLOB subtables, WAL

### Compression Warming Effect

After compression + cylinder consolidation, fewer cylinders hold same data → each cylinder accessed more frequently → appears warmer.

Example: 10 cylinders → 2 cylinders = 5× warmer per cylinder.

### AutoCylPack

Separate background task — consolidates cylinders after compression.

DBS Control: `AutoCylPackColddata = FALSE` (default). Setting TRUE allows cold cylinder consolidation (recommended).

---

## Independent Subtable Compression

### Eligible Subtables

Primary data, fallback (base + index), CLOB primary, CLOB fallback

### NOT Eligible

Primary index subtables, BLOB primary, BLOB fallback

### Fallback-Only Compression Pattern

```sql
-- DBS Control settings
-- CompressPermFallbackDBs = ONLYIFQBYES (or ALWAYS)
-- CompressPermPrimaryDBs  = NEVER

-- Via Ferret:
COMPRESS "mydb.orders" FALLBACK

-- Via Query Band:
SET QUERY_BAND = 'BlockCompression=FALLBACK;' UPDATE FOR SESSION;
```

Fallback-only compression = best compromise for read-heavy tables with fallback.

---

## Compression Ratios

### Typical Reduction

~60% space reduction (table 2.5× smaller) — Teradata Engineering estimate

### Maximum Theoretical

| Cylinder Type | Max Theoretical | Max (Frequently Modified) |
|---|---|---|
| Small | 95% | 93% |
| Large | 88% | 84% |

### Factors Reducing Compression

- Pre-existing MVC or ALC reduces additional BLC benefit
- Secondary indexes (primary index subtables never compressed)
- Smaller data blocks from block splits
- MinPercentCompReduction default 20% threshold
- Cylinder index limitations with large cylinders

### CPU Impact Examples

| Operation | Elapsed Time Change | CPU Change |
|---|---|---|
| INSERT-SELECT 607.5M rows | +133% | +667% |
| MultiLoad 15.8M rows | +74% | +829% |
| FastLoad 410.4M rows | **-17%** (faster, less I/O) | +218% |
| TPump 600K rows | +191% | +593% |
| Table scan 6B rows | +41% | +843% |

**Key rule:** CPU utilization should be ≤80% (≤60% preferred) for actively accessed compressed tables.

### Recommendation

Use **maximum allowed block size** for tables undergoing compression. Larger blocks = better ratios. Set via CREATE/ALTER TABLE or DBS Control PermDBSize.

---

## ResUsage Compression Metrics (DBC.ResUsageSVPR)

| Column | Description |
|---|---|
| FileCompDBs | Total data blocks compressed |
| FileCompDBs_HW | Blocks compressed by hardware engine (16.0) |
| FileUnCompDBs | Total data blocks uncompressed |
| FileUncompDBs_HW | Blocks uncompressed by hardware engine (16.0) |
| FilePreCompMB | MB before compression (within interval) |
| FilePostCompMB | MB after compression (within interval) |
| FileCompCPU | Compression CPU time (nanoseconds) |
| FileUncompCPU | Uncompression CPU time (nanoseconds) |
| FileCompTempDBs | Blocks compressed by AutoTempComp |
| FileUnCompTempDBs | Blocks uncompressed by AutoTempComp |
| FileTempCPU | CPU by AutoTempComp |
| FileUnCompCylMigr | Cylinder migrates during uncompress |
| FileUnCompFerretDBs | Blocks uncompressed by Ferret |
| FileCompCylMigr | Cylinder migrates during compress |
| FileCompFerretDBs | Blocks compressed by Ferret |

Only `VprType = 'AMP'` records contain compression metrics.

### Example Queries

```sql
-- Compression ratio over time
SELECT TheDate, TheTime, SUM(FilePreCompMB) AS pre_mb,
       SUM(FilePostCompMB) AS post_mb,
       CASE WHEN SUM(FilePreCompMB) > 0
            THEN (1 - SUM(FilePostCompMB) / NULLIFZERO(SUM(FilePreCompMB))) * 100
            ELSE 0 END AS comp_ratio_pct
FROM DBC.ResUsageSVPR
WHERE VprType = 'AMP' AND TheDate = CURRENT_DATE
GROUP BY TheDate, TheTime
ORDER BY TheTime;

-- AutoTempComp activity
SELECT TheDate, TheTime, VprId,
       FileCompTempDBs, FileUnCompTempDBs, FileTempCPU
FROM DBC.ResUsageSVPR
WHERE VprType = 'AMP'
  AND (FileCompTempDBs > 0 OR FileUnCompTempDBs > 0)
ORDER BY TheTime;
```
