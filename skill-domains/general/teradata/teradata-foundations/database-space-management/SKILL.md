---
name: database-space-management
description: 'Create and manage Teradata databases using CREATE DATABASE, MODIFY DATABASE, DELETE DATABASE, and DROP DATABASE DDL including permanent space allocation, spool space limits, temporary space allocation, default journal tables, fallback settings, database accounting, and space usage monitoring. Use when creating databases, modifying space allocations, monitoring perm/spool/temp space usage, setting database defaults (journal, fallback, map), or cleaning up and dropping databases.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Database Space Management

## When to Use

- Creating new databases with appropriate space allocation
- Modifying perm/spool/temp space limits on existing databases
- Monitoring database space usage and identifying space pressure
- Setting database-level defaults (fallback, journal, map, account)
- Reorganizing database hierarchies (ownership)
- Cleaning up and dropping databases

## Core Concepts

### Teradata Space Model

| Space Type | Purpose | Allocation |
|------------|---------|------------|
| **Perm** (Permanent) | Stores table data, indexes, journal tables | Explicitly allocated per database |
| **Spool** | Temporary workspace for query processing | Inherited from parent or explicitly set |
| **Temp** | Global temporary table materialization | Inherited from parent or explicitly set |

### Space Inheritance

- **Perm space** is explicitly allocated to each database and subtracted from the parent
- **Spool space** is shared among all databases under the same parent (unless explicitly overridden)
- **Temp space** follows the same inheritance model as spool

## CREATE DATABASE Syntax

```sql
CREATE DATABASE database_name
  [FROM owner_database]
  AS
    [PERMANENT | PERM] = bytes
    [, SPOOL = bytes]
    [, TEMPORARY = bytes]
    [, ACCOUNT = 'account_string']
    [, DEFAULT JOURNAL TABLE = [database.]table_name]
    [, FALLBACK [PROTECTION] | NO FALLBACK [PROTECTION]]
    [, BEFORE JOURNAL | NO BEFORE JOURNAL | DUAL BEFORE JOURNAL]
    [, AFTER JOURNAL | NO AFTER JOURNAL | DUAL AFTER JOURNAL]
    [, DEFAULT MAP = map_name [COLOCATE USING colocation_name]]
    [, DEFAULT DATABASE = database_name]
    [, NO DEFAULT DATABASE]
;
```

### Common Patterns

```sql
-- Basic database creation
CREATE DATABASE analytics_db
  FROM dbc
  AS PERM = 1e9       -- 1 GB
   , SPOOL = 2e9      -- 2 GB spool limit
   , NO FALLBACK
   , NO BEFORE JOURNAL
   , NO AFTER JOURNAL;

-- Production database with fallback and journaling
CREATE DATABASE production_db
  FROM dbc
  AS PERM = 50e9      -- 50 GB
   , SPOOL = 100e9    -- 100 GB spool
   , FALLBACK
   , BEFORE JOURNAL
   , AFTER JOURNAL
   , ACCOUNT = 'PROD_TEAM';

-- Child database under an existing parent
CREATE DATABASE staging_db
  FROM analytics_db   -- space taken from analytics_db's perm
  AS PERM = 500e6     -- 500 MB
   , SPOOL = 1e9;
```

### Space Units

| Notation | Value |
|----------|-------|
| `1e6` | 1 MB (1,000,000 bytes) |
| `1e9` | 1 GB (1,000,000,000 bytes) |
| `50e6` | 50 MB |
| `500e6` | 500 MB |
| `10e9` | 10 GB |
| `1e12` | 1 TB |

## MODIFY DATABASE

```sql
MODIFY DATABASE database_name AS
    [PERM = bytes]
    [, SPOOL = bytes]
    [, TEMPORARY = bytes]
    [, ACCOUNT = 'account_string']
    [, DEFAULT JOURNAL TABLE = [database.]table_name]
    [, FALLBACK [PROTECTION] | NO FALLBACK [PROTECTION]]
    [, BEFORE JOURNAL | NO BEFORE JOURNAL]
    [, AFTER JOURNAL | NO AFTER JOURNAL]
    [, DEFAULT MAP = map_name]
;
```

### Common Modifications

```sql
-- Increase perm space
MODIFY DATABASE analytics_db AS PERM = 5e9;

-- Increase spool limit
MODIFY DATABASE analytics_db AS SPOOL = 10e9;

-- Change default fallback setting (new tables inherit this)
MODIFY DATABASE analytics_db AS FALLBACK;

-- Change default journal setting
MODIFY DATABASE analytics_db AS NO BEFORE JOURNAL, NO AFTER JOURNAL;

-- Set default map
MODIFY DATABASE analytics_db AS DEFAULT MAP = TD_DataDictionary_Map;

-- Change account string
MODIFY DATABASE analytics_db AS ACCOUNT = 'ANALYTICS_TEAM_2025';
```

> **Note:** MODIFY DATABASE changes the *maximum* allocation. If the parent doesn't have enough free perm space, the operation fails.

## DATABASE (Set Default)

```sql
-- Set the current default database for the session
DATABASE analytics_db;
```

- Subsequent unqualified object references resolve to this database
- Equivalent to `SET SESSION DATABASE = analytics_db`

## DELETE DATABASE

Deletes all objects **within** the database but keeps the database itself.

```sql
DELETE DATABASE staging_db;
```

- Drops all tables, views, macros, stored procedures, triggers within the database
- Does NOT drop child databases
- Perm space is freed
- The database object remains and can be repopulated

## DROP DATABASE

Drops the database and all objects within it.

```sql
DROP DATABASE staging_db;
```

- All objects within the database are dropped
- The database itself is removed
- Perm space is returned to the parent database
- Cannot drop a database that has child databases (drop children first)

## Monitoring Space Usage

### Database-Level Space Usage

```sql
SELECT DatabaseName,
       SUM(CurrentPerm) AS used_perm,
       SUM(MaxPerm) AS max_perm,
       CAST(SUM(CurrentPerm) AS FLOAT) / NULLIFZERO(SUM(MaxPerm)) * 100 AS pct_used,
       SUM(CurrentSpool) AS current_spool,
       SUM(MaxSpool) AS max_spool
FROM DBC.DiskSpaceV
WHERE DatabaseName = 'analytics_db'
GROUP BY DatabaseName;
```

### All Databases Space Summary

```sql
SELECT DatabaseName,
       SUM(MaxPerm) / 1e9 AS max_perm_gb,
       SUM(CurrentPerm) / 1e9 AS used_perm_gb,
       CAST(SUM(CurrentPerm) AS FLOAT) / NULLIFZERO(SUM(MaxPerm)) * 100 AS pct_full
FROM DBC.DiskSpaceV
GROUP BY DatabaseName
HAVING SUM(MaxPerm) > 0
ORDER BY pct_full DESC;
```

### Databases Near Capacity (> 80%)

```sql
SELECT DatabaseName,
       SUM(MaxPerm) / 1e9 AS max_gb,
       SUM(CurrentPerm) / 1e9 AS used_gb,
       CAST(SUM(CurrentPerm) AS FLOAT) / NULLIFZERO(SUM(MaxPerm)) * 100 AS pct_full
FROM DBC.DiskSpaceV
GROUP BY DatabaseName
HAVING CAST(SUM(CurrentPerm) AS FLOAT) / NULLIFZERO(SUM(MaxPerm)) * 100 > 80
   AND SUM(MaxPerm) > 0
ORDER BY pct_full DESC;
```

### Table-Level Space Usage

```sql
SELECT DatabaseName, TableName,
       SUM(CurrentPerm) / 1e6 AS perm_mb,
       SUM(PeakPerm) / 1e6 AS peak_perm_mb
FROM DBC.TableSizeV
WHERE DatabaseName = 'analytics_db'
GROUP BY DatabaseName, TableName
ORDER BY perm_mb DESC;
```

### Spool Usage by Session

```sql
SELECT SessionNo, UserName,
       CurrentSpool / 1e9 AS spool_gb
FROM DBC.SessionInfoV
WHERE CurrentSpool > 1e9
ORDER BY CurrentSpool DESC;
```

## Database Hierarchy

```sql
-- View database hierarchy (parent-child relationships)
SELECT DatabaseName, OwnerName, PermSpace, SpoolSpace, TempSpace
FROM DBC.DatabasesV
WHERE OwnerName = 'analytics_db'
ORDER BY DatabaseName;

-- Full hierarchy using HELP DATABASE
HELP DATABASE analytics_db;
```

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| 2646: No space | Perm space exhausted | MODIFY DATABASE to increase PERM or clean up data |
| 2662: Spool space exceeded | Query needs more spool than allowed | MODIFY DATABASE to increase SPOOL or optimize query |
| 3514: Database already exists | CREATE DATABASE with existing name | Use a different name or drop first |
| 3576: Cannot drop non-empty database | DROP DATABASE with child databases | Drop children first |
| 2634: Insufficient parent space | CREATE/MODIFY asks for more than parent has free | Free space in parent or request less |

## Space Planning Guidelines

| Workload | Perm:Spool Ratio | Notes |
|----------|------------------|-------|
| OLTP (small queries) | 1:1 | Low spool demand |
| Analytics/BI | 1:2 to 1:5 | Complex queries need more spool |
| ETL/Staging | 1:1 | Staging data ≈ final data size |
| Data Science | 1:5 to 1:10 | Large intermediate results |

## Privileges Required

- `CREATE DATABASE` on the parent database to create
- `DROP DATABASE` on the database to drop
- `MODIFY DATABASE` to modify (owner has this implicitly)

## References


> **Access:** `skill_resource_read(action="read", skill="database-space-management", path="references/FILENAME")` — do NOT call `list`.

- [Space Monitoring Queries](./references/space-monitoring-queries.md) — Comprehensive space monitoring queries, capacity planning, and alerting patterns

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 13
