---
name: row-level-security
description: 'Implement Teradata row-level security (RLS) using CREATE CONSTRAINT, ALTER CONSTRAINT, DROP CONSTRAINT, and secure zones (CREATE ZONE, ALTER ZONE, DROP ZONE). Use when implementing row-level access controls, defining security constraint hierarchies and levels, assigning security labels to rows and users, creating secure zones for database isolation, managing RLS constraint columns in tables, or restricting data visibility based on user clearance levels.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Row-Level Security and Secure Zones

## When to Use

- Restricting row visibility based on user security clearance
- Implementing classification-based access (SECRET, CONFIDENTIAL, etc.)
- Creating security categories for compartmented access
- Isolating databases within secure zones
- Enforcing mandatory access controls beyond GRANT/REVOKE
- Complying with regulatory requirements for data segregation

## Core Concepts

### Row-Level Security (RLS) Architecture

RLS uses **security constraints** assigned to both rows and users. A user can only see rows where their clearance meets or exceeds the row's classification.

| Component | Purpose |
|-----------|---------|
| **Constraint** | Named security policy with levels/categories |
| **Levels** | Hierarchical classification (e.g., UNCLASSIFIED < CONFIDENTIAL < SECRET) |
| **Categories** | Non-hierarchical compartments (e.g., FINANCE, HR, ENGINEERING) |
| **Constraint column** | Table column storing the row's security label |
| **User assignment** | User's clearance level and category access |

### How RLS Enforces Access

1. Each row has a security label value in its constraint column
2. Each user has a security clearance level and category set
3. On SELECT/UPDATE/DELETE, the system compares user clearance to row label
4. Rows where user clearance < row classification are invisible to the user

## CREATE CONSTRAINT

```sql
CREATE CONSTRAINT constraint_name
  [VALUES (level_name value [,...]) | CATEGORY]
  [DEFAULT level_name | DEFAULT CATEGORY category_name]
;
```

### Hierarchical Constraint (Levels)

```sql
-- Classification levels (higher number = more restricted)
CREATE CONSTRAINT data_classification
  VALUES (
    UNCLASSIFIED 1,
    INTERNAL     2,
    CONFIDENTIAL 3,
    SECRET       4,
    TOP_SECRET   5
  )
  DEFAULT UNCLASSIFIED;
```

### Category Constraint

```sql
-- Non-hierarchical compartments
CREATE CONSTRAINT department_access CATEGORY;
```

## ALTER CONSTRAINT

```sql
-- Add a new level
ALTER CONSTRAINT data_classification ADD VALUES (RESTRICTED 6);

-- Remove a level (no rows can use it)
ALTER CONSTRAINT data_classification DROP VALUES (RESTRICTED);
```

## DROP CONSTRAINT

```sql
DROP CONSTRAINT constraint_name;
```

> Cannot drop a constraint that is referenced by any table column.

## Using RLS in Tables

### Adding a Constraint Column

```sql
CREATE TABLE mydb.classified_documents (
    doc_id         INTEGER NOT NULL,
    doc_title      VARCHAR(200),
    doc_content    CLOB,
    classification data_classification CONSTRAINT,
    dept_access    department_access CONSTRAINT
)
PRIMARY INDEX (doc_id);
```

### Inserting with Security Labels

```sql
-- Insert a CONFIDENTIAL document
INSERT INTO mydb.classified_documents VALUES (
    1, 'Q3 Financial Report', '...',
    CONFIDENTIAL, 'FINANCE'
);

-- Insert a SECRET document
INSERT INTO mydb.classified_documents VALUES (
    2, 'Merger Plans', '...',
    SECRET, 'EXECUTIVE'
);
```

### Assigning User Clearance

```sql
-- Grant a user CONFIDENTIAL clearance
GRANT CONSTRAINT ASSIGNMENT (data_classification, CONFIDENTIAL)
    TO analyst_user;

-- Grant category access
GRANT CONSTRAINT ASSIGNMENT (department_access, 'FINANCE')
    TO analyst_user;
```

### Access Behavior

```sql
-- analyst_user with CONFIDENTIAL clearance queries:
SELECT * FROM mydb.classified_documents;
-- Result: sees only rows with classification <= CONFIDENTIAL
-- The SECRET "Merger Plans" row is invisible
```

## Secure Zones

Secure zones provide database-level isolation, restricting which databases and objects are visible to zone members.

### CREATE ZONE

```sql
CREATE ZONE zone_name AS
    database_name [,...]
;
```

```sql
-- Create a zone for the finance department
CREATE ZONE finance_zone AS
    finance_db, finance_staging_db, shared_reference_db;
```

### ALTER ZONE

```sql
-- Add a database to the zone
ALTER ZONE finance_zone ADD finance_archive_db;

-- Remove a database from the zone
ALTER ZONE finance_zone DROP finance_staging_db;
```

### DROP ZONE

```sql
DROP ZONE zone_name;
```

### Assigning Users to Zones

```sql
-- Assign a user to a zone
CREATE USER zone_user
FROM finance_db
AS PERM = 100e6
PASSWORD = 'pass'
DEFAULT DATABASE = finance_db
ZONE = finance_zone;
```

### Zone Behavior
- Users in a zone can only see objects in databases within their zone
- Users outside any zone can see all databases (subject to normal privileges)
- Zone membership is independent of GRANT/REVOKE privileges
- A user can belong to only one zone

## RLS + Secure Zones Combined

```sql
-- 1. Create classification constraint
CREATE CONSTRAINT project_clearance
  VALUES (PUBLIC 1, INTERNAL 2, RESTRICTED 3)
  DEFAULT PUBLIC;

-- 2. Create zone for the project
CREATE ZONE project_alpha_zone AS project_alpha_db, shared_utils_db;

-- 3. Create table with RLS column
CREATE TABLE project_alpha_db.design_docs (
    doc_id     INTEGER NOT NULL,
    title      VARCHAR(200),
    clearance  project_clearance CONSTRAINT
)
PRIMARY INDEX (doc_id);

-- 4. Create user with zone + clearance
CREATE USER engineer_a
FROM project_alpha_db
AS PERM = 10e6
PASSWORD = 'pass'
ZONE = project_alpha_zone;

GRANT CONSTRAINT ASSIGNMENT (project_clearance, INTERNAL)
    TO engineer_a;

-- engineer_a sees: only project_alpha zone databases, and only rows with clearance <= INTERNAL
```

## Querying RLS Metadata

```sql
-- List all constraints
SELECT ConstraintName, ConstraintType
FROM DBC.SecurityConstraintsV;

-- List constraint values/levels
SELECT ConstraintName, LevelName, LevelValue
FROM DBC.SecurityConstraintLevelsV
ORDER BY ConstraintName, LevelValue;

-- List user constraint assignments
SELECT UserName, ConstraintName, LevelName
FROM DBC.UserConstraintAssignmentsV;

-- List zones
SELECT ZoneName, DatabaseName
FROM DBC.SecureZonesV;
```

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| 6927: Constraint not found | Reference to non-existent constraint | Check `DBC.SecurityConstraintsV` |
| 6928: Cannot drop constraint | Table columns reference it | Drop constraint columns first |
| 5812: Insufficient clearance | User INSERT/UPDATE with classification above their clearance | Assign appropriate clearance level |
| 6930: Zone not found | Reference to non-existent zone | Check `DBC.SecureZonesV` |

## Privileges Required

- `CONSTRAINT DEFINITION` to create/alter/drop constraints
- `CONSTRAINT ASSIGNMENT` to assign constraint levels to users
- Appropriate zone management privileges for CREATE/ALTER/DROP ZONE

## References


> **Access:** `skill_resource_read(action="read", skill="row-level-security", path="references/FILENAME")` — do NOT call `list`.

- [RLS and Zone Patterns](./references/rls-and-zone-patterns.md) — Implementation patterns for multi-level security, category-based access, and zone isolation strategies

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapters 17 and 21
