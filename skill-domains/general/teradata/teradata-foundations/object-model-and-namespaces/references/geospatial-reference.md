# Teradata Geospatial Data Types — Complete Reference

> Source: 541-0007514-B02 — Teradata Spatial Features User Guide (Release 13.10)

---

## 1. Type Hierarchy

The SQL/MM standard defines geospatial types as an object-oriented class hierarchy using inheritance and subtyping with `ST_Geometry` as the base class.

```
1. ST_GEOMETRY (base class — instantiable)
   ├── 2. ST_Point
   ├── 3. ST_Curve (abstract)
   │   └── 4. ST_LineString
   ├── 5. ST_Surface (abstract)
   │   └── 6. ST_CurvePolygon
   │       └── 7. ST_Polygon
   ├── 8. ST_GeomCollection
   │   ├── 9. ST_MultiPoint
   │   ├── 10. ST_MultiCurve (abstract)
   │   │   └── 11. ST_MultiLineString
   │   └── 12. ST_MultiSurface (abstract)
   │       └── 13. ST_MultiPolygon
   └── GeoSequence (Teradata extension, subtype of ST_Geometry)
```

**Key facts:**
- `ST_Geometry` is the single instantiable type in Teradata — any column of type `ST_Geometry` can contain **any** of the geospatial subtypes
- The deprecated `ST_POINT` type was removed in Teradata 13.0; use `ST_GEOMETRY` for all spatial objects
- GeoSequence is a Teradata extension (not SQL/MM standard), treated as inheriting from ST_LineString
- Types are defined in database `SYSUDTLIB`; since Release 13.0 they are system types (improved performance)

---

## 2. Storage Format

The `ST_Geometry` UDT stores encoded within it:

| Attribute | Description |
|-----------|-------------|
| **SRID** | Spatial Reference Identifier (INTEGER) |
| **MBR** | Minimum Bounding Rectangle |
| **WKB** | Well Known Binary representation of the geometry object(s) |

**Client-side representation:**
- Default **input** format: Well Known Text (WKT)
- Default **output** format: Well Known Text (WKT)
- For import/export, both are encoded within a **CLOB** data type — this is the data type the client application processes
- `SELECT *` from a table with ST_GEOMETRY returns the geometry column as a **CLOB** (WKT)
- The `TOSQL` transform function takes WKT → geometry object (called implicitly on INSERT)
- The `FROMSQL` transform function takes geometry object → WKT (called implicitly on SELECT)

**Max size:** Up to **1,000,000 vertices** per spatial object.

---

## 3. MBR Type

`MBR` — A spatial type representing the **Minimum Bounding Rectangle** of a spatial object. Used as a filter mechanism to improve performance of spatial queries.

### Obtaining MBR

```sql
-- Get MBR from a geometry column
column_name.ST_MBR()

-- Extract MBR coordinates
column_name.ST_MBR().xmin()
column_name.ST_MBR().ymin()
column_name.ST_MBR().xmax()
column_name.ST_MBR().ymax()
```

### MBR Usage Example

```sql
SELECT aoiname, id, aoi,
       aoi.st_mbr().xmin() AS xmin,
       aoi.st_mbr().ymin() AS ymin,
       aoi.st_mbr().xmax() AS xmax,
       aoi.st_mbr().ymax() AS ymax
FROM AOI;
```

---

## 4. GeoSequence Type

GeoSequence is a **Teradata extension** — a tracking/sequence data type (subtype of ST_Geometry). Used for GPS tracking, rail tracking, RFID tracking, customer aisle tracking, etc.

### WKT Format

```
'GEOSEQUENCE( (x1 y1, x2 y2, …, xn yn), (t1, t2, …, tn), (LinkID1, LinkID2, …, LinkIDn), (UserFldCount, UserFld1_1, …, UserFld1_n, UserFld2_1, …, UserFld2_n, … ) )'
```

| Item | Description | Data Type |
|------|-------------|-----------|
| xi yi | Point i in the sequence | DOUBLE PRECISION |
| ti | Timestamp of point xi yi | yyyy-mm-dd hh:mm:ss.ms |
| LinkIDi | Link ID of point xi yi | FLOAT |
| UserFldCount | Number of user fields per point | INTEGER |
| UserFldi_j | User-defined metadata fields per point | FLOAT |

### Constructors

- WKT passed to `ST_GeomFromText` (≤64,000 bytes)
- WKT (VARCHAR(64000) or CLOB) cast to ST_Geometry
- WKT (CLOB only) passed to ToSql transform
- `GeoSequenceLOBFromRows` table UDF — reads a table with one row per observation

### GeoSequence Methods

```sql
-- Get initial timestamp
geoseq.GetInitT()

-- Get final timestamp
geoseq.GetFinalT()

-- Get Nth timestamp (1-based)
geoseq.GetT(2)

-- Get count of user fields
geoseq.GetUserFldCount()

-- Get Nth user field value: GetUserFld(field_number, point_number)
geoseq.GetUserFld(1,1)    -- 1st user field, 1st point
geoseq.GetUserFld(2,2)    -- 2nd user field, 2nd point
```

### GeoSequence Construction from Set-Based Data

```sql
-- Source table: one row per observation
CREATE TABLE trips_set (
    id INTEGER,
    ts TIMESTAMP,
    lon FLOAT,
    lat FLOAT,
    linkid NUMERIC,
    milemarker INTEGER,
    speedlimit INTEGER
);

INSERT INTO trips_set VALUES (1, '2007-08-22 12:05:23.56', 10, 20, 1, 101, 55);
INSERT INTO trips_set VALUES (1, '2007-08-22 12:08:25.14', 30, 30, 2, 102, 65);
INSERT INTO trips_set VALUES (1, '2007-08-22 12:11:41.52', 50, 60, 3, 103, 55);

-- Target table: GeoSequence column
CREATE TABLE trips (id INTEGER, geoseq ST_GEOMETRY);

-- Build GeoSequence from rows using GeoSequenceLOBFromRows
INSERT INTO trips
WITH TS (id,ts,lon,lat,linkid,milemarker,speedlimit,cnt,seq) AS (
    SELECT t.*, COUNT(*) OVER (PARTITION BY id ORDER BY ts) AS cnt,
           ROW_NUMBER() OVER (PARTITION BY id ORDER BY ts) AS seq
    FROM trips_set AS t
)
SELECT x.out_key, x.lsx
FROM TABLE (sysspatial.GeoSequenceLOBFromRows(
    ts.id, ts.cnt, ts.seq, ts.lon, ts.lat, ts.ts, ts.linkid,
    ts.milemarker, ts.speedlimit,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
    HASH BY ts.id LOCAL ORDER BY ts.id, ts.seq ASC
) AS X;
```

### GeoSequence Decomposition to Rows

```sql
SELECT x.out_key AS id, x.x, x.y, x.ts
FROM TABLE (sysspatial.GeoSequenceToRows(trips.id, trips.geoseq)) AS x
ORDER BY id, x.ts;
```

### GeoSequence in Spatial Operations

When a GeoSequence is used in spatial relationship methods (ST_Intersection, ST_Union, etc.), it is first converted to ST_LineString (stripping sequence-specific data). A GeoSequence object is **never** returned from spatial relationship methods.

### Direct WKT Insert

```sql
INSERT INTO trips VALUES (11,
    'GEOSEQUENCE( (10 20, 30 40, 50 60), (2007-08-22 12:05:23.56, 2007-08-22 12:08:25.14, 2007-08-22 12:11:41.52), (1, 2, 3), (2, 110, 112, 141, 45, 25, 65) )'
);
```

---

## 5. Constructors

### NEW ST_Geometry Constructor Formats

```sql
NEW ST_Geometry(wkt VARCHAR(64000))
NEW ST_Geometry(wkt VARCHAR(64000), asrid INTEGER)
NEW ST_Geometry(wkt CLOB)
NEW ST_Geometry(wkt CLOB, asrid INTEGER)
NEW ST_Geometry(wkb VARBYTE(64000))
NEW ST_Geometry(wkb VARBYTE(64000), asrid INTEGER)
NEW ST_Geometry(wkb BLOB)
NEW ST_Geometry(wkb BLOB, asrid INTEGER)
NEW ST_Geometry(geomtype VARCHAR(80), xcoord DOUBLE PRECISION, ycoord DOUBLE PRECISION)
NEW ST_Geometry(geomtype VARCHAR(80), xcoord DOUBLE PRECISION, ycoord DOUBLE PRECISION, asrid INTEGER)
```

### WKT Implicit Construction

If the input field is in WKT format, **no additional type construction is required** — the implicit CAST handles it:

```sql
-- Implicit WKT (no NEW required)
INSERT INTO Stores VALUES (5, 'Polygon((1 1, 1 2, 2 2, 2 1, 1 1))');

-- Explicit NEW constructor with WKT
INSERT INTO Stores VALUES (9, NEW ST_GEOMETRY('Polygon((1 1, 1 2, 2 2, 2 1, 1 1))'));

-- NEW constructor with geomtype + coordinates
INSERT INTO Stores VALUES (11, NEW ST_GEOMETRY('ST_POINT', 10, 10));
```

### WKB Construction

```sql
-- WKB for POINT(1 1) = 21 bytes:
-- 0101000000000000000000F03F000000000000F03F

-- NEW constructor with WKB (append XBF suffix for varbyte literal)
INSERT INTO Stores VALUES (7,
    NEW ST_GEOMETRY('0101000000000000000000F03F000000000000F03F'XBF));
```

**Important:** Implicit CAST from VARBYTE uses "header + WKB" format, not raw WKB. The NEW constructor takes raw WKB only.

### WKT Examples for All Geometry Types

```sql
CREATE TABLE tab1 (id INT, location ST_GEOMETRY);

-- ST_Point: 0-dimensional, single location
INSERT INTO tab1 VALUES (0, 'POINT(10 20)');

-- ST_LineString: 1-dimensional, sequence of points with linear interpolation
INSERT INTO tab1 VALUES (0, 'LINESTRING(1 1, 2 2, 3 3, 4 4)');

-- ST_Polygon: 2-dimensional, exterior + optional interior boundaries (holes)
INSERT INTO tab1 VALUES (0, 'POLYGON( (0 0, 0 20, 20 20, 20 0, 0 0),
                                      (5 5, 5 10, 10 10, 10 5, 5 5) )');

-- ST_GeomCollection: collection of zero or more ST_Geometry values
INSERT INTO tab1 VALUES (0, 'GEOMETRYCOLLECTION(POINT(10 10), POINT(30 30),
                              LINESTRING(15 15, 20 20))');

-- ST_MultiPoint: 0-dimensional collection of ST_Point
INSERT INTO tab1 VALUES (0, 'MULTIPOINT((1 1), (1 3), (6 3), (10 5), (20 1))');

-- ST_MultiLineString: 1-dimensional collection of ST_LineString
INSERT INTO tab1 VALUES (0, 'MULTILINESTRING((1 1, 1 3, 6 3), (10 5, 20 1))');

-- ST_MultiPolygon: 2-dimensional collection of ST_Polygon
INSERT INTO tab1 VALUES (0, 'MULTIPOLYGON(
                               ((1 1, 1 3, 6 3, 6 0, 1 1)),
                               ((10 5, 10 10, 20 10, 20 5, 10 5)) )');
```

---

## 6. Spatial Methods — Complete Catalog

Methods are invoked via dot notation: `database.table.column.method()`. Method chaining is supported when a method returns a geometry: `column.method1().method2()`.

### 6.1 ST_GEOMETRY Methods (Available on All Subtypes)

| # | Method | Returns | Description |
|---|--------|---------|-------------|
| 1.1 | `ST_Dimension()` | INTEGER | Inherent dimension of the geometry (0=point, 1=line, 2=surface) |
| 1.2 | `ST_CoordDim()` | INTEGER | Coordinate dimension |
| 1.3 | `ST_GeometryType()` | VARCHAR | Geometry type name |
| 1.4 | `ST_SRID()` | INTEGER | Spatial Reference ID |
| 1.5 | `ST_Transform(from_srtext, to_srtext)` | ST_Geometry | Transform between SRS |
| 1.6 | `ST_isEmpty()` | INTEGER | 1 if empty, 0 otherwise |
| 1.7 | `ST_isSimple()` | INTEGER | 1 if simple (no self-intersection) |
| 1.8 | `ST_isValid()` | INTEGER | 1 if valid geometry |
| 1.9 | `ST_Boundary()` | ST_Geometry | Boundary of the geometry |
| 1.10 | `ST_Envelope()` | ST_Geometry | Bounding box as geometry |
| 1.11 | `ST_ConvexHull()` | ST_Geometry | Convex hull |
| 1.12 | `ST_Buffer(distance)` | ST_Geometry | Buffer zone (Cartesian only) |
| 1.13 | `ST_Intersection(other)` | ST_Geometry | Intersection of two geometries |
| 1.14 | `ST_Union(other)` | ST_Geometry | Union of two geometries |
| 1.15 | `ST_Difference(other)` | ST_Geometry | Difference |
| 1.16 | `ST_SymDifference(other)` | ST_Geometry | Symmetric difference |
| 1.17 | `ST_Distance(other)` | FLOAT | Cartesian distance |
| 1.18 | `ST_Equals(other)` | INTEGER | 1 if spatially equal |
| 1.19 | `ST_Relate(other)` | VARCHAR | DE-9IM relationship matrix |
| 1.20 | `ST_Disjoint(other)` | INTEGER | 1 if disjoint |
| 1.21 | `ST_Intersects(other)` | INTEGER | 1 if intersects |
| 1.22 | `ST_Touches(other)` | INTEGER | 1 if touches |
| 1.23 | `ST_Crosses(other)` | INTEGER | 1 if crosses |
| 1.24 | `ST_Within(other)` | INTEGER | 1 if within |
| 1.25 | `ST_Contains(other)` | INTEGER | 1 if contains |
| 1.26 | `ST_Overlaps(other)` | INTEGER | 1 if overlaps |
| 1.27 | `ST_WKTToSQL(wkt)` | ST_Geometry | Construct from WKT |
| 1.28 | `ST_AsText()` | CLOB | Export as WKT |
| 1.29 | `ST_WKBToSQL(wkb)` | ST_Geometry | Construct from WKB |
| 1.30 | `ST_AsBinary()` | BLOB | Export as WKB |
| 1.31 | `ST_GeomFromText(wkt)` | ST_Geometry | Function: construct from WKT |
| 1.32 | `ST_GeomFromWKB(wkb)` | ST_Geometry | Function: construct from WKB |
| 1.33 | `Tessellate_index(...)` | INTEGER | Tessellation cell ID for indexing |
| — | `ST_MBR()` | MBR | Get Minimum Bounding Rectangle |

### 6.2 ST_Point Methods (Type 2)

| Method | Returns | Description |
|--------|---------|-------------|
| `ST_X()` | FLOAT | X coordinate (longitude) |
| `ST_Y()` | FLOAT | Y coordinate (latitude) |
| `ST_SphericalDistance(other)` | FLOAT | Geodetic distance (sphere model), meters |
| `ST_SpheroidalDistance(other)` | FLOAT | Geodetic distance (spheroid model), meters |
| `ST_SphericalBufferMBR(radius_miles)` | MBR | Spherical buffered MBR around point |
| `ST_SpheroidalBufferMBR(radius_miles)` | MBR | Spheroidal buffered MBR around point |

**Note:** `ST_X()` and `ST_Y()` are **only valid on ST_POINT** types. An error is raised if invoked on other subtypes.

### 6.3 ST_Curve / ST_LineString Methods (Types 3–4)

| Method | Returns | Description |
|--------|---------|-------------|
| `ST_Length()` | FLOAT | Length of the curve |
| `ST_StartPoint()` | ST_Point | First point |
| `ST_EndPoint()` | ST_Point | Last point |
| `ST_IsClosed()` | INTEGER | 1 if start = end |
| `ST_IsRing()` | INTEGER | 1 if closed and simple |
| `ST_NumPoints()` | INTEGER | Number of points |
| `ST_PointN(n)` | ST_Point | Nth point (1-based) |
| `ST_line_interpolate_point(fraction)` | ST_Point | Point at fraction along line |

### 6.4 ST_Surface / ST_Polygon Methods (Types 5–7)

| Method | Returns | Description |
|--------|---------|-------------|
| `ST_Area()` | FLOAT | Area of the surface |
| `ST_Perimeter()` | FLOAT | Perimeter length |
| `ST_Centroid()` | ST_Point | Geometric centroid |
| `ST_PointOnSurface()` | ST_Point | A point guaranteed on the surface |
| `ST_ExteriorRing()` | ST_LineString | Exterior boundary ring |
| `ST_NumInteriorRing()` | INTEGER | Number of interior rings (holes) |
| `ST_InteriorRingN(n)` | ST_LineString | Nth interior ring (1-based) |

### 6.5 ST_GeomCollection Methods (Type 8)

| Method | Returns | Description |
|--------|---------|-------------|
| `ST_NumGeometries()` | INTEGER | Number of geometries in collection |
| `ST_GeometryN(n)` | ST_Geometry | Nth geometry (1-based) |

### 6.6 ST_MultiCurve / ST_MultiLineString Methods (Types 10–11)

| Method | Returns | Description |
|--------|---------|-------------|
| `ST_IsClosed()` | INTEGER | 1 if all elements are closed |
| `ST_Length()` | FLOAT | Sum of lengths |

### 6.7 ST_MultiSurface / ST_MultiPolygon Methods (Types 12–13)

| Method | Returns | Description |
|--------|---------|-------------|
| `ST_Area()` | FLOAT | Sum of areas |
| `ST_Perimeter()` | FLOAT | Sum of perimeters |
| `ST_Centroid()` | ST_Point | Centroid of the multi-surface |
| `ST_PointOnSurface()` | ST_Point | A point on one of the surfaces |

### Method Inheritance Rule

If a method is available on a supertype, it is available on all subtypes. If a method is only on a subtype, it is **not** valid on the supertype (error raised).

---

## 7. Spatial Aggregates

### AggGeomUnion

Returns an ST_Geometry that is the **union** of all input geometries.

```sql
SELECT AggGeomUnion(geom_column) FROM table_name WHERE ...;
```

### AggGeomIntersection

Returns an ST_Geometry that is the **intersection** of all input geometries.

```sql
SELECT AggGeomIntersection(geom_column) FROM table_name WHERE ...;
```

**Notes:**
- Since 13.10, aggregates accept `ST_Geometry` directly (no need to CAST to VARBYTE)
- Ported to `TD_SYSFNLIB` for fast-path performance; `SYSSPATIAL` versions kept for backward compatibility
- **Limit:** Combined objects must total ≤ ~64,000 bytes WKB. Exceeding this produces:
  ```
  *** Failure 9134 AggGeomUnion: WKB representation would overflow max varbinary allowed.
  ```

### TD_SYSFNLIB Functions (Fast-Path)

These functions reside in `TD_SYSFNLIB` and should be used instead of `SYSSPATIAL` equivalents:

- `AggGeomIntersection`
- `AggGeomUnion`
- `GeoSequenceFromRows`
- `GeoSequenceToRows`
- `Tessellate`
- `Tessellate_search`

**Warning:** If a user-developed UDF has the same name as a fast-path function in the current database or SYSLIB, the fast-path function is ignored.

---

## 8. Metadata Tables

### sysspatial.geometry_columns

Stores information about database tables containing geometry columns. Maintained via stored procedures `AddGeometryColumn` and `DropGeometryColumn`.

```sql
CREATE SET TABLE sysspatial.geometry_columns, FALLBACK,
     NO BEFORE JOURNAL, NO AFTER JOURNAL, CHECKSUM = DEFAULT
(
    F_TABLE_CATALOG    VARCHAR(256) CHARACTER SET LATIN NOT CASESPECIFIC NOT NULL,
    F_TABLE_SCHEMA     VARCHAR(128) CHARACTER SET UNICODE NOT CASESPECIFIC NOT NULL,
    F_TABLE_NAME       VARCHAR(128) CHARACTER SET UNICODE NOT CASESPECIFIC NOT NULL,
    F_GEOMETRY_COLUMN  VARCHAR(128) CHARACTER SET UNICODE NOT CASESPECIFIC NOT NULL,
    COORD_DIMENSION    INTEGER,
    SRID               INTEGER,
    GEOM_TYPE          VARCHAR(30) CHARACTER SET LATIN NOT CASESPECIFIC NOT NULL,
    UxMin              FLOAT,
    UyMin              FLOAT,
    UxMax              FLOAT,
    UyMax              FLOAT,
    FOREIGN KEY (SRID) REFERENCES SYSSPATIAL.spatial_ref_sys (SRID)
)
UNIQUE PRIMARY INDEX GC_PK (F_TABLE_CATALOG, F_TABLE_SCHEMA, F_TABLE_NAME, F_GEOMETRY_COLUMN);
```

**Note:** The `UxMin/UyMin/UxMax/UyMax` columns store the universe MBR coordinates (added in 13.0+). Currently, metadata in this table is **not used** by spatial routines.

### sysspatial.spatial_ref_sys

Stores Spatial Reference System definitions (from EPSG). Used by `ST_TRANSFORM` for coordinate transformations. Loaded during installation.

```sql
CREATE SET TABLE sysspatial.spatial_ref_sys, FALLBACK,
     NO BEFORE JOURNAL, NO AFTER JOURNAL, CHECKSUM = DEFAULT
(
    SRID       INTEGER NOT NULL PRIMARY KEY,
    AUTH_NAME  VARCHAR(256) CHARACTER SET LATIN,
    AUTH_SRID  INTEGER,
    SRTEXT     VARCHAR(2048) CHARACTER SET LATIN
)
UNIQUE PRIMARY INDEX (AUTH_SRID);
```

### Finding Tables with Spatial Columns

```sql
SELECT columntype, databasename, tablename, columnname
FROM dbc.columns
WHERE columntype = 'ut'
  AND columnudtname IN ('st_geometry', 'st_point')
  AND databasename NE 'sysudtlib';
```

---


> **See also:** [geospatial-indexing-reference.md](geospatial-indexing-reference.md) — Tessellation indexing, spatial joins, loading data, coordinate transforms, limits, and query examples.
