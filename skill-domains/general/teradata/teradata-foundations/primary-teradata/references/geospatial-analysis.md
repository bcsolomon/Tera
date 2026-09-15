# Teradata Geospatial — ST_Geometry Types and Functions

## ST_Polygon and ST_MultiPolygon Methods

| Method | Returns | Notes |
|--------|---------|-------|
| `ST_Area()` | FLOAT | Sum for MultiPolygon; ignores z |
| `ST_Perimeter()` | FLOAT | Boundary length; ignores z |
| `ST_ExteriorRing([acurve])` | ST_LineString or ST_Polygon | Getter/setter |
| `ST_InteriorRingN([aposition])` | ST_LineString | 1-based |
| `ST_NumInteriorRing()` | INTEGER | |
| `ST_PointOnSurface()` | ST_Geometry | Guaranteed to intersect the polygon |

---


## ST_GeomCollection, ST_Multi* Methods

| Method | Returns | Notes |
|--------|---------|-------|
| `ST_GeometryN(aposition)` | ST_Geometry | 1-based; works on all Multi types |
| `ST_NumGeometries()` | INTEGER | Component count |

---


## MBR and MBB Methods

| Method | Returns | Notes |
|--------|---------|-------|
| `MBR.XMin/YMin/XMax/YMax()` | FLOAT | Coordinate accessors |
| `MBB.XMin/YMin/ZMin/XMax/YMax/ZMax()` | FLOAT | 3D coordinate accessors |
| `MBR.Intersects(other)` | INTEGER 0/1 | Tests MBR-to-MBR intersection |
| `MBB.Intersects(other)` | INTEGER 0/1 | Tests MBB-to-MBB intersection |

---


## Filtering Methods

Use these for spatial filtering — index-accelerated for geospatial NUSIs.

| Method | Input | Returns | Notes |
|--------|-------|---------|-------|
| `MBR_Filter(othergeom)` | 2D ST_Geometry | INTEGER 0/1 | MBR-to-MBR test; ignores z |
| `MBB_Filter(othergeom)` | 3D ST_Geometry | INTEGER 0/1 | MBB-to-MBB test; errors if 2D |
| `Intersects_MBB(aMBB)` | 3D Point/MultiPoint/LineString/MultiLineString | INTEGER 0/1 | Geometry vs MBB; errors if 2D |
| `Within_MBB(aMBB)` | 3D ST_Geometry | INTEGER 0/1 | Geometry within MBB; errors if 2D |

```sql
SELECT shape.MBR_Filter(NEW ST_Geometry('POLYGON((0 0, 20 0, 20 20, 0 20, 0 0))'))
FROM sample_shapes;

SELECT shape.Within_MBB(NEW MBB(0,0,0,20,20,20))
FROM sample_shapes;
```

---


## Geospatial Indexes

Create a NUSI on an ST_Geometry column to enable optimizer use:

```sql
CREATE TABLE sample_shapes (skey INTEGER, shape ST_Geometry) INDEX (shape);
-- Or as part of CREATE TABLE:
CREATE TABLE t (a INT, sp ST_GEOMETRY) INDEX(sp);
```

**Index-accelerated predicates:** `ST_Contains`, `ST_Crosses`, `ST_Distance`, `ST_3DDistance`, `ST_Equals`, `ST_Intersects`, `ST_Overlaps`, `ST_Touches`, `ST_Within`, `MBR_Filter`, `MBB_Filter`, `Within_MBB`, `Intersects_MBB`, `ST_Relate`.

**Single-table predicate form (= 1 required):**
```sql
WHERE shape.ST_Within(NEW ST_Geometry('POLYGON(...)')) = 1
```

**Distance predicate form (< constant required):**
```sql
WHERE shape.ST_Distance('POINT(10 20)') < 100.0
```

**Join predicate:** optimizer considers nested join; at least one side must have a geospatial index.
```sql
SELECT * FROM T1 INNER JOIN T2 ON T1.GeoCol.ST_Within(T2.Geom) = 1;
```

**Geospatial index restrictions:**
- Single-column NUSIs only
- Not on volatile or global temporary tables
- Not on join indexes
- Collect statistics for better optimizer decisions (same syntax as regular COLLECT STATISTICS)

---


## System Functions (TD_SYSFNLIB)

Prefer these over UDFs — system functions take priority when names conflict.

### DataSize

```sql
SELECT TD_SYSFNLIB.DataSize(shape) FROM sample_shapes;
```

Returns BIGINT bytes for ST_Geometry, JSON, XML, DATASET columns.

### MGRS Conversion

```sql
-- Point → MGRS string (precision 0=100km to 5=1m; truncates, does not round)
SELECT TO_MGRS(
  NEW ST_GEOMETRY('ST_POINT', 30, 45),
  (SELECT SRTEXT FROM SYSSPATIAL.SPATIAL_REF_SYS WHERE SRID = 1619),
  5);
-- Returns: '36TTQ6355387329'

-- MGRS string → ST_Point
SELECT FROM_MGRS(
  '36TTQ6355387329',
  (SELECT SRTEXT FROM SYSSPATIAL.SPATIAL_REF_SYS WHERE SRID = 1619),
  1619);
```

Note: MGRS-Old lettering for Bessel/Clarke 1866/1880 ellipsoids; MGRS-New for all others.

### GeoSequence Conversion Table Functions

```sql
-- Rows → GeoSequence (PARTITION BY in_key ORDER BY ts required)
SELECT T.trip_id, R.geom
FROM trip_data T,
     TABLE(GeoSequenceFromRows(T.trip_id, T.pcount, T.seq,
           T.x, T.y, T.t, T.link_id,
           T.speed, T.accel, T.heading,
           NULL, NULL, NULL, NULL, NULL, NULL, NULL)) R
WHERE R.out_key = T.trip_id;

-- GeoSequence → rows (out_key, point_index, x, y, ts, Link_id, UserFld1-10)
SELECT out_key, point_index, x, y, ts, Link_id, UserFld1, UserFld2
FROM TABLE(GeoSequenceToRows(9601., sample_shapes.shape)) AS ts;
```

### AggGeom — Aggregate Union or Intersection

```sql
-- Union by zip code (parallel — one row per partition value)
SELECT zipcode, geom
FROM AggGeom(
  ON (SELECT geom, zipcode FROM geom_table)
  PARTITION BY zipcode
  USING Operation('Union')
) L;

-- Global union (two-call pattern for parallel local then global aggregation)
SELECT *
FROM AggGeom(
  ON (SELECT L.*, 1 AS p
      FROM AggGeom(ON (SELECT geom FROM geom_table) USING Operation('Union')) L)
  PARTITION BY p
) G;
```

**Notes:** Non-empty GeomCollections not supported (intermediate or final). Row order can vary — results are equivalent but not identical across runs.

### GeometryToRows — Explode Geometry to Point Rows

```sql
SELECT PointsTable.*
FROM GeometryToRows(ON (SELECT geom_id, geom FROM geo_table))
AS PointsTable (geom_id1, element_id, ring_id, point_id, geomType, x, y, z)
ORDER BY 1, 2, 3, 4;
```

Returns columns: `id1, [id2,] element_id, ring_id, point_id, geomType, x, y, z`.
- `element_id`: which element within a Multi type (1-based)
- `ring_id`: ring within polygon (1=exterior, 2+=interior holes); NULL for non-polygons
- `point_id`: ordering within the element (1-based)
- First and last points of a polygon ring are identical

### PolygonSplit — Split Large Polygons

```sql
SELECT *
FROM PolygonSplit(ON (
  SELECT poly_id, geom, CAST(400 AS INTEGER) AS max_vertices
  FROM feature_tbl
  WHERE poly_id = 100
)) AS SplitTable(poly_id, sub_poly_id, splitGeom)
ORDER BY 1, 2;
```

- Recursively splits into quadrants until each sub-polygon < `max_vertices` (default 300, min 10)
- Non-polygon geometries returned unchanged
- Sub-polygon areas may not sum exactly to original (floating-point rounding)
- Output: `out_polygon_ID, sub_polygon_ID` (0-based), `split_geom`

---


## UDFs (SYSSPATIAL Schema)

Prefer instance methods or system functions over these. Qualify with `SYSSPATIAL.` to avoid ambiguity.

```sql
-- Spherical distance (Haversine) — lat/lon as separate args
SELECT SYSSPATIAL.SphericalDistance(10, 20, 20, 30);

-- Spheroidal distance — WGS84 default; fails for antipodal points
SELECT SYSSPATIAL.SpheroidalDistance(-89.39, 43.09, -87.65, 41.90);
SELECT SYSSPATIAL.SpheroidalDistance(-89.39, 43.09, -87.65, 41.90, 6378137, 298.257223563);

-- Construct from WKT VARCHAR (max 64000 bytes; prefer constructor for performance)
SELECT SYSSPATIAL.ST_GeomFromText('POINT(10 20)', 4326);

-- Construct from WKB VARBYTE (max 64000 bytes)
SELECT SYSSPATIAL.ST_GeomFromWKB(:wkb_value, 4326);
```

**GeoJSON conversion (JSON Data Type):**
```sql
GeomFromGeoJSON  -- JSON GeoJSON document → ST_Geometry
GeoJSONFromGeom  -- ST_Geometry → JSON GeoJSON document
```

---


## Tessellation (Grid-Based Spatial Indexing)

Tessellation provides an alternative spatial index approach using a multilevel grid. It is used with a pre-built index table rather than a geospatial NUSI.

### Tessellate_Index Method (on ST_Geometry)

Generates cell IDs for indexing a geometry. Call this during INSERT to populate an index table.

```sql
CREATE TABLE cities_index (skey INTEGER, cellid INTEGER);

INSERT INTO cities_index
SELECT skey,
       cityShape.Tessellate_Index(
         -180, 0, 0, 90,   -- universe: u_xmin, u_ymin, u_xmax, u_ymax
         500, 500,          -- grid: g_nx, g_ny
         1,                 -- levels
         0.01,              -- scale (must be 0 < scale < 1)
         0)                 -- shift (0=none, 1=four shifted grids per level)
FROM sample_cities;
```

### Tessellate_Search UDF (SYSSPATIAL)

Table function that returns all cell IDs at each grid level that contain a given bounding rectangle. Use the same universe/grid parameters as `Tessellate_Index`. Join on `cellid` to find candidate matches.

```sql
SYSSPATIAL.Tessellate_Search (
  in_key,                          -- DECIMAL(18,0) — passed back as out_key
  o_xmin, o_ymin, o_xmax, o_ymax, -- object bounding rectangle (FLOAT)
  u_xmin, u_ymin, u_xmax, u_ymax, -- universe (FLOAT) — must match index
  g_nx, g_ny,                      -- grid divisions (INTEGER)
  levels,                           -- 1–15 (INTEGER)
  scale,                            -- 0 < scale < 1.0 (FLOAT)
  shift                             -- 0 or 1 (INTEGER)
)
```

Returns: `out_key` DECIMAL(18,0), `cellID` INTEGER.
- `cellID / 16` → cell number
- `cellID MOD 16` → grid level

```sql
-- Proximity join using tessellate index
SELECT c.skey, c.cityName, s.streetName
FROM sample_cities c
    ,cities_index ci
    ,(SELECT streetName, skey, streetShape,
             streetShape.ST_MBR_Xmin(), streetShape.ST_MBR_Ymin(),
             streetShape.ST_MBR_Xmax(), streetShape.ST_MBR_Ymax()
      FROM sample_streets)
      AS s (streetName, skey, streetShape, xmin, ymin, xmax, ymax)
    ,TABLE(SYSSPATIAL.Tessellate_Search(
             s.skey,
             s.xmin, s.ymin, s.xmax, s.ymax,
             -180, 0, 0, 90,
             500, 500,
             1, 0.01, 0)) AS t
WHERE c.skey = ci.skey
  AND ci.cellid = t.cellid
  AND t.out_key = s.skey;
```

---


## Metadata (SYSSPATIAL Database)

### GEOMETRY_COLUMNS

Tracks ST_Geometry columns and their spatial reference systems.

```sql
-- Register a new ST_Geometry column (2D)
CALL SYSSPATIAL.AddGeometryColumn(
  '',            -- catalog (empty string for Teradata)
  'mydb',        -- schema/database
  'lakes',       -- table
  'shore',       -- column
  4326,          -- SRID
  'ST_Polygon',  -- geometry type
  -180.0, -90.0, 180.0, 90.0  -- UxMin, UyMin, UxMax, UyMax (universe MBR)
);

-- Register a 3D column (adds dimensions parameter)
CALL SYSSPATIAL.AddGeometryColumn_3D('', 'mydb', 'lakes', 'shore', 3, 4326,
     'ST_Polygon', -180.0, -90.0, 180.0, 90.0);

-- Drop geometry metadata
CALL SYSSPATIAL.DropGeometryColumn('', 'mydb', 'lakes', 'shore');
```

### SPATIAL_REF_SYS

Populated by DIP during installation. Key columns: `SRID`, `AUTH_SRID`, `SRTEXT` (WKT SRS definition).

```sql
-- Look up WKT for a known SRID
SELECT SRTEXT FROM SYSSPATIAL.SPATIAL_REF_SYS WHERE AUTH_SRID = 4326;  -- WGS84
SELECT SRTEXT FROM SYSSPATIAL.SPATIAL_REF_SYS WHERE AUTH_SRID = 32616; -- UTM Zone 16N
```

---


## Common Patterns

### Proximity search (within distance)
```sql
SELECT skey FROM sample_shapes
WHERE shape.ST_Distance(NEW ST_Geometry('POINT(10 20)')) < 50.0;
```

### Point-in-polygon join
```sql
SELECT streetName, cityName
FROM sample_cities, sample_streets
WHERE streetShape.ST_Within(cityShape) = 1;
```

### Compute area and centroid
```sql
SELECT cityName,
       cityShape.ST_Area()     AS area_sq_units,
       cityShape.ST_Centroid() AS centroid
FROM sample_cities;
```

### Real-world distance between two points (WGS84)
```sql
SELECT point1.ST_SpheroidalDistance(point2)
FROM sample_points1, sample_points2;
```

### Convert to/from WKT and WKB
```sql
SELECT shape.ST_AsText()   FROM sample_shapes;  -- → CLOB WKT
SELECT shape.ST_AsBinary() FROM sample_shapes;  -- → BLOB WKB
```

### Find minimum bounding rectangle
```sql
INSERT INTO sample_MBRs SELECT skey, shape.ST_MBR() FROM sample_shapes;
```

### Aggregate all geometries into one union
```sql
SELECT *
FROM AggGeom(
  ON (SELECT L.*, 1 AS p
      FROM AggGeom(ON (SELECT geom FROM geom_table) USING Operation('Union')) L)
  PARTITION BY p
) G;
```

### Split a large polygon for performance
```sql
SELECT * FROM PolygonSplit(
  ON (SELECT poly_id, geom FROM feature_tbl)
) AS t ORDER BY 1, 2;
```
