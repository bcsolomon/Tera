# Teradata Geospatial Indexing and Operations Reference

> Source: 541-0007514-B02 — Teradata Spatial Features User Guide (Release 13.10)

---

## 9. Tessellation Indexing

### Concept

Spatial relationship operators (e.g., ST_INTERSECTS) are expensive because:
- Cannot create PI/USI/NUSI on ST_GEOMETRY columns
- Cannot use equality join operators for spatial comparisons
- Results in table scans or product joins
- Large spatial objects are costly to transfer
- Computational geometry algorithms are inherently expensive

**Solution:** Tessellation maps geometry MBRs onto a multi-level 2D grid, enabling existing access methods and join operators.

**Guideline:** If >100,000 method invocations per node, tessellation is beneficial.

### Functions

| Function | Purpose | Returns |
|----------|---------|---------|
| `Tessellate(...)` | Join processing — returns all grid cells an MBR intersects | 1–N rows (out_key, cellid) |
| `Tessellate_index(...)` | Index maintenance — returns smallest cell containing MBR | 1 row (cellid INTEGER) |
| `Tessellate_search(...)` | Query an index — returns all cells an MBR intersects | 1–N rows (out_key, cellid) |

### Tessellate Parameters

| # | Parameter | Type | Description |
|---|-----------|------|-------------|
| 1 | in_key | NUMERIC | Relates output to input |
| 2 | o_xmin | FLOAT | Object MBR min X |
| 3 | o_ymin | FLOAT | Object MBR min Y |
| 4 | o_xmax | FLOAT | Object MBR max X |
| 5 | o_ymax | FLOAT | Object MBR max Y |
| 6 | u_xmin | FLOAT | Universe MBR min X |
| 7 | u_ymin | FLOAT | Universe MBR min Y |
| 8 | u_xmax | FLOAT | Universe MBR max X |
| 9 | u_ymax | FLOAT | Universe MBR max Y |
| 10 | g_nx | INTEGER | Grid cells in X dimension |
| 11 | g_ny | INTEGER | Grid cells in Y dimension |

### Additional Tessellate_index / Tessellate_search Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| levels | INTEGER (1–15) | Number of grid levels (always levels+1 where level 0 = entire universe) |
| scale | FLOAT (0.0–1.0) | Scaling factor between levels. E.g., g_nx=4, g_ny=4, levels=2, scale=0.5 → 4×4, 2×2, 1×1 |
| shift | INTEGER | Number of grid shifts in X/Y. 0=no shift, 1=4-for-1 shifting (4 grids) |

### Cell ID Encoding

**Tessellate:** 32-bit cell ID. Max cells: g_nx × g_ny < 4,294,967,296.

**Tessellate_index/search (shift=0):**
- Low 4 bits: level (max 16 levels)
- Upper 28 bits: cell ID. Max: g_nx × g_ny < 268,435,456

**Tessellate_index/search (shift≠0):**
- Low 4 bits: level
- Next 2 bits: shift
- Upper 26 bits: cell ID. Max: g_nx × g_ny < 67,108,864

### Cell ID Decode Queries

```sql
-- With shift
SELECT cellid MOD 16 AS level,
       (cellid / 16) MOD 4 AS shift,
       (cellid / 64) AS gridnum
FROM (SELECT sysspatial.tessellate_index(11, 11, 12, 12, 0, 0, 100, 100, 10, 10, 2, .5, 1) AS cellid) X;

-- Without shift
SELECT cellid MOD 16 AS level,
       (cellid / 16) AS gridnum
FROM (SELECT sysspatial.tessellate_index(11, 11, 12, 12, 0, 0, 100, 100, 10, 10, 2, .5, 0) AS cellid) X;
```

### Creating a Spatial Index

```sql
-- Base table
CREATE TABLE customers (id INTEGER, location ST_GEOMETRY);

-- Index table (cellid as PI for merge-join access)
CREATE MULTISET TABLE customers_idx (
    id INTEGER NOT NULL,
    cellid INTEGER NOT NULL
) PRIMARY INDEX (cellid);

-- Trigger: maintain index on INSERT
CREATE TRIGGER mi AFTER INSERT ON customers
REFERENCING NEW TABLE AS nt
FOR EACH STATEMENT
BEGIN ATOMIC
(
    INSERT INTO customers_idx
    SELECT id,
           sysspatial.tessellate_index(
               location.st_x(), location.st_y(), location.st_x(), location.st_y(),
               -180, 0, 0, 90,
               1000, 1000,
               1, 0.01, 0)
    FROM nt;
)
END;

-- Trigger: maintain index on DELETE
CREATE TRIGGER md AFTER DELETE ON customers
REFERENCING OLD TABLE AS ot
FOR EACH STATEMENT
BEGIN ATOMIC
(
    DELETE FROM customers_idx WHERE ID IN (SELECT ID FROM ot);
)
END;
```

### Querying via Spatial Index (View Pattern)

```sql
-- AOI (Area of Interest) table
CREATE TABLE aoi (aoiname VARCHAR(32), id INTEGER, aoi ST_GEOMETRY);

-- View encapsulating index access
REPLACE VIEW CUSTOMER_AOI (custid, location, aoiname, aoi) AS
SELECT c.id, c.location, a.aoiname, a.aoi
FROM
    customers c,
    customers_idx ci,
    (SELECT aoiname, id, aoi,
            aoi.st_mbr().xmin(), aoi.st_mbr().ymin(),
            aoi.st_mbr().xmax(), aoi.st_mbr().ymax()
     FROM AOI) AS a (aoiname, id, aoi, xmin, ymin, xmax, ymax),
    TABLE (sysspatial.tessellate_search(
        a.id,
        a.xmin, a.ymin, a.xmax, a.ymax,
        -180, 0, 0, 90,
        1000, 1000,
        1, 0.01, 0)) AS T
WHERE
    c.id = ci.id
    AND ci.cellid = t.cellid
    AND t.out_key = a.id;

-- Query using the index view
SELECT aoiname, COUNT(*)
FROM customer_aoi
WHERE aoiname = 'MikesStores'
  AND location.st_intersects(aoi) = 1
GROUP BY 1;
```

### Determining Tessellation Parameters (tparms Procedure)

The `tparms` stored procedure (not installed by default — must be separately installed) analyzes data demographics and suggests tessellation parameters.

```sql
CALL tparms('mww', 'zipcode', 'location', -180, 0, 0, 90,
            minv, maxv, avgv, ccnt, stdv, meanv, skewv, settings);
```

**Output:**
| Output | Description |
|--------|-------------|
| MINV | Min objects per cell |
| MAXV | Max objects per cell |
| AVGV | Average objects per cell |
| CCNT | Count of cells with objects |
| STDV | Std deviation of objects per cell |
| MEDIANV | Median objects per cell |
| SKEWV | AMP VPROC skew (object distribution) |
| TSETTINGS | Suggested parameters string |

**Example output:**
```
TSETTINGS: TESSELLATE PARMETERS {:xmin,:ymin,:xmax,:ymax,-180.000000,.000000,.000000,90.000000,409,409,3,.20,1}
```

---

## 10. Spatial Joins

### Tessellate-Based Equality Join (Filter + Refine)

Tessellate both relations, join on cellid (equality), then refine with spatial predicate.

```sql
SELECT COUNT(*)
FROM
    -- Tessellate Customers
    (SELECT id, location,
            location.tessellate_index(-180, 0, 0, 90, 1000, 1000, 1, .1, 0) AS cellid
     FROM customers) AS C_T,

    -- Tessellate Stores (with spherical buffer MBR for 10-mile radius)
    (SELECT s.id, s.location, d.cellid
     FROM (SELECT id, location,
                  location.st_sphericalbuffermbr(10) AS mbr,
                  mbr.xmin() AS xmin, mbr.ymin() AS ymin,
                  mbr.xmax() AS xmax, mbr.ymax() AS ymax
           FROM stores) S,
          TABLE(td_sysfnlib.tessellate_search(
              s.id, s.xmin, s.ymin, s.xmax, s.ymax,
              -180, 0, 0, 90, 1000, 1000, 1, .1, 0)
          ) AS d
     WHERE d.out_key = s.id
    ) AS S_T

WHERE S_T.cellid = C_T.cellid
  AND .000622 * s_t.location.st_sphericaldistance(c_t.location) < 10;
```

**Key points:**
- Universe definition and grid cell size **must match** in both tessellations
- `ST_SphericalBufferMBR` / `ST_SpheroidalBufferMBR` simplify creating search MBRs for geodetic data
- Equality join on `cellid` enables merge join (optimizer can use RowHash match scan)
- The spatial predicate (e.g., `st_sphericaldistance`) is only evaluated for matching cells (filter + refine)

---

## 11. Access Rights

```sql
-- Grant access to spatial types (SYSUDTLIB level)
GRANT UDTUSAGE ON SYSUDTLIB TO GeoUser;

-- Grant function execution on SYSSPATIAL
GRANT EXECUTE FUNCTION ON SYSSPATIAL TO GeoUser;

-- Grant SELECT on SYSSPATIAL metadata tables
GRANT SELECT ON SYSSPATIAL TO GeoUser;

-- Grant stored procedure execution
GRANT EXECUTE PROCEDURE ON SYSSPATIAL TO GeoUser;
```

Access can be managed at the SYSUDTLIB database level or individual data type level using `UDTUSAGE`.

---

## 12. Loading Spatial Data

### BTEQ (Parameter Arrays)

```sql
CREATE SET TABLE customers, NO FALLBACK,
     NO BEFORE JOURNAL, NO AFTER JOURNAL, CHECKSUM = DEFAULT
(
    cust_id INTEGER NOT NULL,
    geom SYSUDTLIB.ST_GEOMETRY NOT NULL
);

-- BTEQ script
.set quiet on
.IMPORT DATA FILE=customers.dat
.REPEAT * PACK 1000
USING id (INTEGER)
,geom (VARCHAR(200))
INSERT INTO customers VALUES(:id, :geom);
```

### TPUMP (WKT ≤ 64,000 bytes)

```sql
.logtable lt_customers;
.logon mww13/mww,mww;

CREATE SET TABLE customers, NO FALLBACK,
     NO BEFORE JOURNAL, NO AFTER JOURNAL, CHECKSUM = DEFAULT
(
    cust_id INTEGER NOT NULL,
    lon FLOAT NOT NULL,
    lat FLOAT NOT NULL,
    geom ST_GEOMETRY
);

.BEGIN LOAD
   SESSIONS 10;
   .layout inlayout;
        .field cust_id * INTEGER;
        .field LON * FLOAT;
        .field LAT * FLOAT;

   .dml label insdml;
INSERT INTO customers VALUES(:cust_id, :LON, :LAT,
    'POINT(' || CAST(:LON AS DECIMAL(15,6)) || ' ' || CAST(:LAT AS DECIMAL(15,6)) || ')');

.import infile .\customers.dat
   layout inlayout
   apply insdml;
.end load;
.logoff;
```

### Fastload (Staging Pattern — WKB ≤ 64,000 bytes)

Spatial data uses LOB client representation → cannot directly Fastload into ST_Geometry. Load WKB into VARBYTE staging table, then INSERT-SELECT with constructor.

```sql
-- Fastload into staging table
SESSIONS 2;
ERRLIMIT 25;
LOGON mww13/mww,mww;

CREATE SET TABLE customer_t
(
    cust_id INTEGER NOT NULL,
    geom VARBYTE(1000) NOT NULL
) PRIMARY INDEX (cust_id);

SET RECORD FORMATTED;
DEFINE
    CUST_ID (INTEGER),
    GEOM (VARBYTE(1000))
FILE=.\customer.dat;
BEGIN LOADING customer_t ERRORFILES Error1, Error2 CHECKPOINT 20000;
INSERT INTO customer_t(CUST_ID, GEOM) VALUES(:CUST_ID, :GEOM);
END LOADING;
LOGOFF;

-- Copy from staging to target table
CREATE SET TABLE customer
(
    cust_id INTEGER NOT NULL,
    geom ST_GEOMETRY NOT NULL
) PRIMARY INDEX (cust_id);

INSERT INTO customer SELECT cust_id, NEW ST_Geometry(GEOM) FROM customer_t;
```

**Note:** MultiLoad and Fastload are **no longer supported** for directly loading spatial data types (since 13.0).

### TDGEOIMPORT

Windows client program for loading common spatial file formats into Teradata.

**Supported formats:** ESRI Shapefiles, MapInfo TAB files, TIGER/Line files

**Requires:** Teradata JDBC driver (terajdbc4.jar, tdgssconfig.jar)

| Flag | Value | Description |
|------|-------|-------------|
| `-l` | Logon String | Format: `Database/User,Password` |
| `-n` | LayerName | Specific layer to process (omit for all layers) |
| `-f` | DataSourceName | Full path to input file/directory |
| `-s` | DatabaseName | Target database for tables |
| `-k` | keyword_map_file | Map column/table names (reserved words, embedded spaces) |
| `-p` | primary_index_file | Specify primary index per table |

**Invocation example:**
```bash
java -classpath c:\path\bin;c:\path\bin\tdgssconfig.jar;c:\path\bin\terajdbc4.jar \
    com.teradata.geo.TDGeoImport \
    -l mwww1310/mww,mww \
    -f c:\data\spatial\data\co99_d00.shp \
    -n co99_d00
```

### TDGeoExport

Creates ESRI Shapefile, TIGER, or MapInfo TAB file from Teradata data.

| Flag | Value | Description |
|------|-------|-------------|
| `-l` | Logon String | Format: `Database/User,Password` |
| `-s` | Database | Database containing the table |
| `-t` | Table | Table or view name |
| `-f` | Format | `"ESRI Shapefile"`, `"TIGER"`, `"MapInfo File"` |
| `-o` | Output Dir | Output directory |
| `-n` | LayerName | Layer name (defaults to table name) |

---

## 13. Limits and Restrictions

| Limit | Value |
|-------|-------|
| Max vertices per ST_GEOMETRY object | ~1,000,000 |
| Max WKT/WKB for TPUMP/direct load | 64,000 bytes |
| Max aggregate result size (AggGeomUnion/Intersection) | ~64,000 bytes WKB |
| Cannot create PI/USI/NUSI on ST_GEOMETRY column | Use tessellation index pattern |
| Cannot use equality join on ST_GEOMETRY | Use tessellation join pattern |
| ST_Buffer accuracy | Cartesian only — transform geodetic data to projected SRS first |
| Fastload/Multiload direct load | Not supported since 13.0 — use staging table pattern |

---

## 14. Coordinate Transforms and Reference Systems

### Three Aspects of SRS Support

1. **Transforming** spatial objects between different SRSs via `ST_Transform`
2. **Assigning** an SRID to a spatial object (during construction or explicit update only)
3. **Interpreting** vertex numeric values in the context of the SRS

### ST_Transform Method

SRS is passed **by value** (not by reference, since Teradata doesn't support external data access from methods):

```sql
-- Transform from WGS84 (geodetic) to UTM16 (projected), buffer, transform back
column.st_transform(X.srtext, Y.srtext)
       .st_buffer(10000)
       .st_transform(Y.srtext, X.srtext) AS buffered_geom

-- With SRS lookup
FROM sysspatial.SPATIAL_REF_SYS X,
     sysspatial.SPATIAL_REF_SYS Y
WHERE X.AUTH_SRID = 32616  -- UTM Zone 16 / WGS84
  AND Y.AUTH_SRID = 4326   -- WGS84
```

### SRID Rules

- During all ST_GEOMETRY operations, if SRID identifiers of input objects **do not match**, the method returns an **error**
- User must explicitly transform to a common SRS before comparison
- SRID can only be assigned during construction or via explicit update — **no column-level SRID specification**

### Distance Methods

| Method | Coordinate System | Description |
|--------|-------------------|-------------|
| `ST_Distance(other)` | Cartesian | Distance based on Cartesian coordinates |
| `ST_SphericalDistance(other)` | Geodetic (sphere) | Point-to-point distance, earth modeled as sphere. Returns meters |
| `ST_SpheroidalDistance(other)` | Geodetic (spheroid) | Point-to-point distance, earth modeled as flattened sphere. Accepts radius and flattening inputs. Returns meters |

### WGS84 SRS Definition (AUTH_SRID = 4326)

```sql
SELECT * FROM sysspatial.SPATIAL_REF_SYS WHERE AUTH_SRID = 4326;
-- SRID: 1619, AUTH_NAME: EPSG, AUTH_SRID: 4326
-- SRTEXT:
GEOGCS["WGS 84",
    DATUM["WGS_1984",
        SPHEROID["WGS 84", 6378137, 298.257223563]
    ],
    PRIMEM["Greenwich", 0],
    UNIT["degree", 0.0174532925199433]
]
```

| Component | Value | Description |
|-----------|-------|-------------|
| Semi-major axis | 6378137 m | Equatorial radius |
| Inverse flattening | 298.257223563 | Spheroid shape |
| Unit conversion | 0.0174532925199433 | Degrees → radians |

### Unit Conversion Factors

| Input Unit | Output Unit | Factor |
|------------|-------------|--------|
| 1 Degree | Radians | 0.0174533 |
| 1 Kilometer | Miles | 0.62137 |
| 1 Mile | Feet | 5,280 |
| 1 Meter | Feet | 3.281 |

All ST_GEOMETRY measurement methods return values in the **units of the spatial object's coordinate system**.

---

## Query Examples

### Point-in-Polygon

```sql
SELECT c.cust_id, co.name
FROM customers c, counties co
WHERE co.geom.ST_INTERSECTS(c.geom) = 1;
```

### Close Customers (Spheroidal Distance)

```sql
SELECT c1.cust_id, c2.cust_id,
       c1.geom.ST_SpheroidalDistance(c2.geom) AS distance
FROM customers c1, customers c2
WHERE c1.cust_id < c2.cust_id
  AND distance <= 10000.0;
```

### Intersection with Method Chaining

```sql
SELECT a.AOI.st_intersection(b.AOI) AS Intersects
FROM Stores a, Stores b
WHERE a.id = 5 AND b.id = 6
  AND a.AOI.st_intersection(b.AOI).st_area() > 0.2;
```

### Transform + Buffer + Transform

```sql
SELECT c1.cust_id,
       c1.geom.st_transform(X.srtext, Y.srtext)
              .st_buffer(10000)
              .st_transform(Y.srtext, X.srtext) AS geom
FROM customers c1,
     sysspatial.SPATIAL_REF_SYS X,
     sysspatial.SPATIAL_REF_SYS Y
WHERE X.AUTH_SRID = 32616   -- UTM Zone 16
  AND Y.AUTH_SRID = 4326;   -- WGS84
```

---

## Glossary

| Term | Definition |
|------|------------|
| MBR | Minimum Bounding Rectangle |
| SRS | Spatial Reference System |
| SRID | Spatial Reference Identifier |
| WKT | Well Known Text |
| WKB | Well Known Binary |
| Tessellate | A pattern of shapes covering a plane without gaps or overlaps |
| EPSG | European Petroleum Survey Group (SRS registry) |