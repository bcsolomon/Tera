# RLS and Zone Patterns — Complete Reference

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapters 17 and 21

## Pattern 1: Multi-Level Security (MLS)

Implement a traditional MLS scheme with hierarchical classification levels.

### Setup

```sql
-- Define classification hierarchy
CREATE CONSTRAINT classification
  VALUES (
    UNCLASSIFIED  10,
    INTERNAL      20,
    CONFIDENTIAL  30,
    SECRET        40,
    TOP_SECRET    50
  )
  DEFAULT UNCLASSIFIED;

-- Create table with classification column
CREATE TABLE secure_db.intelligence_reports (
    report_id       INTEGER NOT NULL,
    report_date     DATE,
    subject         VARCHAR(200),
    body            CLOB,
    source_agency   VARCHAR(50),
    classification  classification CONSTRAINT
)
PRIMARY INDEX (report_id);
```

### User Clearance Assignment

```sql
-- Analyst: sees UNCLASSIFIED + INTERNAL + CONFIDENTIAL
GRANT CONSTRAINT ASSIGNMENT (classification, CONFIDENTIAL) TO analyst_role;

-- Manager: sees up to SECRET
GRANT CONSTRAINT ASSIGNMENT (classification, SECRET) TO manager_role;

-- Director: sees everything including TOP_SECRET
GRANT CONSTRAINT ASSIGNMENT (classification, TOP_SECRET) TO director_role;
```

### Data Population

```sql
INSERT INTO secure_db.intelligence_reports VALUES
    (1, DATE '2025-06-01', 'Market Overview', '...', 'Research', UNCLASSIFIED);
INSERT INTO secure_db.intelligence_reports VALUES
    (2, DATE '2025-06-02', 'Competitor Analysis', '...', 'Intel', CONFIDENTIAL);
INSERT INTO secure_db.intelligence_reports VALUES
    (3, DATE '2025-06-03', 'Acquisition Target', '...', 'Strategy', SECRET);
INSERT INTO secure_db.intelligence_reports VALUES
    (4, DATE '2025-06-04', 'Board Plans', '...', 'Executive', TOP_SECRET);
```

### Access Verification

```sql
-- As analyst (CONFIDENTIAL clearance):
SELECT report_id, subject, classification FROM secure_db.intelligence_reports;
-- Returns: reports 1, 2 only (UNCLASSIFIED, CONFIDENTIAL)

-- As manager (SECRET clearance):
SELECT report_id, subject, classification FROM secure_db.intelligence_reports;
-- Returns: reports 1, 2, 3 (UNCLASSIFIED, CONFIDENTIAL, SECRET)

-- As director (TOP_SECRET clearance):
SELECT report_id, subject, classification FROM secure_db.intelligence_reports;
-- Returns: all 4 reports
```

## Pattern 2: Category-Based Compartmented Access

Use categories for non-hierarchical access control (e.g., department-based).

### Setup

```sql
CREATE CONSTRAINT department_compartment CATEGORY;

CREATE TABLE hr_db.employee_records (
    emp_id        INTEGER NOT NULL,
    emp_name      VARCHAR(100),
    salary        DECIMAL(12,2),
    performance   VARCHAR(20),
    dept_access   department_compartment CONSTRAINT
)
PRIMARY INDEX (emp_id);
```

### Category Assignment

```sql
-- HR can see all department data
GRANT CONSTRAINT ASSIGNMENT (department_compartment, 'HR') TO hr_role;
GRANT CONSTRAINT ASSIGNMENT (department_compartment, 'FINANCE') TO hr_role;
GRANT CONSTRAINT ASSIGNMENT (department_compartment, 'ENGINEERING') TO hr_role;

-- Finance manager sees only FINANCE
GRANT CONSTRAINT ASSIGNMENT (department_compartment, 'FINANCE') TO finance_mgr;

-- Engineering manager sees only ENGINEERING
GRANT CONSTRAINT ASSIGNMENT (department_compartment, 'ENGINEERING') TO eng_mgr;
```

### Data Population

```sql
INSERT INTO hr_db.employee_records VALUES (1, 'Alice', 120000, 'Exceeds', 'ENGINEERING');
INSERT INTO hr_db.employee_records VALUES (2, 'Bob', 95000, 'Meets', 'FINANCE');
INSERT INTO hr_db.employee_records VALUES (3, 'Carol', 110000, 'Exceeds', 'ENGINEERING');
INSERT INTO hr_db.employee_records VALUES (4, 'Dave', 130000, 'Meets', 'HR');
```

## Pattern 3: Combined Levels + Categories

Use both hierarchical levels and categories for fine-grained control.

```sql
-- Level constraint
CREATE CONSTRAINT data_sensitivity
  VALUES (PUBLIC 1, INTERNAL 2, RESTRICTED 3)
  DEFAULT PUBLIC;

-- Category constraint
CREATE CONSTRAINT business_unit CATEGORY;

CREATE TABLE corp_db.financial_data (
    record_id     INTEGER NOT NULL,
    period        DATE,
    metric_name   VARCHAR(100),
    metric_value  DECIMAL(18,2),
    sensitivity   data_sensitivity CONSTRAINT,
    unit_access   business_unit CONSTRAINT
)
PRIMARY INDEX (record_id);

-- User with INTERNAL clearance + EMEA unit access
-- sees only: rows where sensitivity <= INTERNAL AND unit_access = 'EMEA'
```

## Pattern 4: Secure Zone Isolation

### Multi-Tenant Isolation

```sql
-- Create databases per tenant
CREATE DATABASE tenant_alpha_db AS PERM = 1e9;
CREATE DATABASE tenant_beta_db AS PERM = 1e9;
CREATE DATABASE shared_reference_db AS PERM = 500e6;

-- Create zones
CREATE ZONE alpha_zone AS tenant_alpha_db, shared_reference_db;
CREATE ZONE beta_zone AS tenant_beta_db, shared_reference_db;

-- Create tenant users in their zones
CREATE USER alpha_admin FROM tenant_alpha_db
    AS PERM = 100e6 PASSWORD = 'pass' ZONE = alpha_zone;
CREATE USER beta_admin FROM tenant_beta_db
    AS PERM = 100e6 PASSWORD = 'pass' ZONE = beta_zone;
```

### Zone Behavior Matrix

| User | Visible Databases | Notes |
|------|-------------------|-------|
| alpha_admin | tenant_alpha_db, shared_reference_db | Zone-restricted |
| beta_admin | tenant_beta_db, shared_reference_db | Zone-restricted |
| dba (no zone) | All databases | Unrestricted |

### Zone with Sparse Maps

For physical data isolation on specific AMPs:

```sql
-- Create sparse map for the zone
CREATE MAP alpha_map AS SPARSE USING alpha_zone;

-- Create tables on the sparse map
CREATE TABLE tenant_alpha_db.data (...), MAP = alpha_map;
```

## RLS Audit and Monitoring

### Verify RLS Is Active

```sql
-- Check if a table has RLS constraint columns
SELECT ColumnName, ColumnType, ConstraintName
FROM DBC.ColumnsV
WHERE DatabaseName = 'secure_db'
  AND TableName = 'intelligence_reports'
  AND ConstraintName IS NOT NULL;
```

### Audit Constraint Usage

```sql
-- Log access attempts on RLS-protected tables
BEGIN LOGGING ON ALL ON secure_db.intelligence_reports;
```

### Monitor User Clearances

```sql
SELECT u.UserName, ca.ConstraintName, ca.LevelName
FROM DBC.UsersV u
LEFT JOIN DBC.UserConstraintAssignmentsV ca ON u.UserName = ca.UserName
ORDER BY u.UserName;
```

## Migration Strategies

### Adding RLS to Existing Tables

```sql
-- 1. Create the constraint
CREATE CONSTRAINT access_level VALUES (PUBLIC 1, PRIVATE 2) DEFAULT PUBLIC;

-- 2. Add constraint column (all rows get DEFAULT = PUBLIC)
ALTER TABLE mydb.existing_table ADD access_control access_level CONSTRAINT;

-- 3. Update rows that should be PRIVATE
UPDATE mydb.existing_table SET access_control = PRIVATE
WHERE sensitive_flag = 'Y';

-- 4. Grant user clearances
GRANT CONSTRAINT ASSIGNMENT (access_level, PRIVATE) TO admin_role;
GRANT CONSTRAINT ASSIGNMENT (access_level, PUBLIC) TO reader_role;
```

### Removing RLS from a Table

```sql
-- 1. Remove the constraint column
ALTER TABLE mydb.existing_table DROP access_control;

-- 2. Drop the constraint (if no other tables use it)
DROP CONSTRAINT access_level;
```

## Limitations

| Limitation | Detail |
|------------|--------|
| Performance | RLS adds overhead to every query — the system must evaluate constraint columns |
| Complexity | Debugging access issues requires checking both privileges and constraints |
| INSERT restrictions | Users cannot insert rows with classification above their clearance |
| UPDATE restrictions | Users cannot change a row's classification above their clearance |
| View transparency | RLS applies through views — view users see only their clearance level |
| Triggers | Cannot log DENIALS for DML operations on RLS-protected tables |
