---
name: teradata-security
description: 'Teradata security administration including user/role/profile management, GRANT/REVOKE privileges, access logging, row-level security (RLS), column security constraints, CREATE AUTHORIZATION for external credentials, password policies, IP restrictions, and security zones. Use when managing users/roles, granting privileges, setting up access logging, implementing row-level or column-level security, or configuring authentication.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Security

## When to Use

- Creating/managing users, roles, and profiles
- Granting and revoking privileges
- Setting up access logging (audit)
- Implementing row-level security (RLS)
- Column-level security constraints
- External credential management (CREATE AUTHORIZATION)
- Password policies and authentication
- IP restrictions and security zones

## User Management

```sql
-- Create user with space allocation
CREATE USER new_user
FROM parent_db
AS PERM = 500e6              -- 500 MB perm space
PASSWORD = 'SecurePass123'
DEFAULT DATABASE = new_user
TEMPORARY = 100e6;           -- 100 MB spool/temp

-- Modify user
MODIFY USER new_user AS PERM = 1e9;

-- Drop user (must be empty of objects)
DROP USER new_user;

-- Change password
MODIFY USER new_user AS PASSWORD = 'NewPass456';
```

## Role Management

```sql
-- Create role
CREATE ROLE analytics_role;

-- Grant privileges to role
GRANT SELECT ON mydb TO analytics_role;
GRANT EXECUTE FUNCTION ON mydb TO analytics_role;

-- Grant role to user
GRANT analytics_role TO new_user;

-- Set default role
MODIFY USER new_user AS DEFAULT ROLE = analytics_role;

-- Revoke and drop
REVOKE analytics_role FROM new_user;
DROP ROLE analytics_role;
```

## Profile Management

```sql
CREATE PROFILE standard_profile AS
    DEFAULT DATABASE = user_db
    SPOOL = 5e9                     -- 5 GB spool limit
    TEMPORARY = 1e9                  -- 1 GB temp space
    ACCOUNT = '$M';                  -- Account string

MODIFY USER new_user AS PROFILE = standard_profile;
```

## GRANT/REVOKE Privileges

### Common Privileges

```sql
-- Database-level
GRANT SELECT, INSERT, UPDATE, DELETE ON mydb TO role_name;
GRANT CREATE TABLE, CREATE VIEW ON mydb TO role_name;
GRANT ALL ON mydb TO role_name;

-- Table-level
GRANT SELECT ON mydb.customers TO role_name;
GRANT INSERT, UPDATE ON mydb.orders TO role_name;

-- Column-level
GRANT SELECT (name, email) ON mydb.customers TO role_name;

-- Procedure/function execution
GRANT EXECUTE PROCEDURE ON mydb.my_sp TO role_name;
GRANT EXECUTE FUNCTION ON mydb.my_udf TO role_name;

-- Statistics
GRANT STATISTICS ON mydb TO role_name;

-- With grant option (can re-grant to others)
GRANT SELECT ON mydb TO role_name WITH GRANT OPTION;
```

### UDF and Function Privileges

UDF privileges are distinct from table privileges and have their own auto-grant rules.

#### Privilege Behaviour

| Privilege | Scope | Auto-Granted? | Notes |
|-----------|-------|---------------|-------|
| `CREATE FUNCTION` | Database | **Never** | Must be granted explicitly; enables `CREATE/REPLACE FUNCTION` |
| `DROP FUNCTION` | Database or function | Yes — WITH GRANT OPTION on each function the user creates | Also authorises `REPLACE FUNCTION` |
| `ALTER FUNCTION` | Database only | **Never** | Changes execution mode (PROTECTED/NOT PROTECTED), triggers recompile; `GRANT ALTER FUNCTION` must target a database, not a specific function |
| `EXECUTE FUNCTION` | Database or function | Yes — WITH GRANT OPTION on each function the user creates | Required for all non-creator callers |
| `EXECUTE PROCEDURE` | Specific procedure | No | General privilege for any stored procedure; used for SQLJ JAR management |

> **Auto-grant rule:** When a user holds `CREATE FUNCTION` on a database, every function they
> create automatically receives `DROP FUNCTION` and `EXECUTE FUNCTION WITH GRANT OPTION` on
> that specific function. `CREATE FUNCTION` itself is never auto-granted.

#### Grant Statements

```sql
-- Developer role: create, replace, and drop UDFs
GRANT CREATE FUNCTION ON udf_db TO udf_developer_role;
GRANT DROP FUNCTION   ON udf_db TO udf_developer_role;

-- DBA only: alter execution mode and recompile
-- GRANT ALTER FUNCTION targets a database; the ALTER FUNCTION DDL statement targets a specific function
GRANT ALTER FUNCTION  ON udf_db TO udf_dba_role;

-- Consumer role: call all UDFs in a database
GRANT EXECUTE FUNCTION ON udf_db TO app_role;

-- Consumer role: call a specific UDF by SPECIFIC name (preferred for overloaded functions)
GRANT EXECUTE ON SPECIFIC FUNCTION udf_db.my_function_v1 TO app_role;

-- Consumer role: call a specific UDF by signature
GRANT EXECUTE FUNCTION ON udf_db.my_function(INTEGER, VARCHAR(100)) TO app_role;

-- Java UDFs: allow JAR installation and removal (EXECUTE PROCEDURE is a general privilege)
GRANT EXECUTE PROCEDURE ON SQLJ.INSTALL_JAR TO udf_developer_role;
GRANT EXECUTE PROCEDURE ON SQLJ.REMOVE_JAR  TO udf_developer_role;
```

#### UDT Privileges (Conditional)

Required only when a UDF signature includes User Defined Types. Three levels — each includes
all rights of the level below:

| Privilege | Code | Allows |
|-----------|------|--------|
| `UDTUSAGE` | `UU` | Use existing UDTs in tables, queries, UDFs, procedures; run existing methods |
| `UDTTYPE` | `UT` | All of UDTUSAGE + CREATE/DROP/ALTER TYPE, ORDERING, CAST, TRANSFORM |
| `UDTMETHOD` | `UM` | All of UDTTYPE + CREATE/ALTER/DROP METHOD |

```sql
-- Minimum: reference existing UDT types in UDF signatures
GRANT UDTUSAGE ON SYSUDTLIB TO udf_developer_role;

-- Narrow: UDTUSAGE on a single UDT only
GRANT UDTUSAGE ON TYPE SYSUDTLIB.my_type TO udf_developer_role;

-- UDT definition authors
GRANT UDTTYPE   ON SYSUDTLIB TO udf_author_role;

-- Full UDT management including methods
GRANT UDTMETHOD ON SYSUDTLIB TO udf_dba_role;
```

> `UDTUSAGE` can be granted on a specific UDT (`ON TYPE name`) or on `SYSUDTLIB`.
> `UDTTYPE` and `UDTMETHOD` must target `SYSUDTLIB` only.

#### Revoking UDF Privileges

```sql
REVOKE EXECUTE FUNCTION ON udf_db FROM app_role;
REVOKE EXECUTE ON SPECIFIC FUNCTION udf_db.my_function_v1 FROM app_role;
REVOKE CREATE FUNCTION ON udf_db FROM udf_developer_role;
REVOKE UDTUSAGE ON SYSUDTLIB FROM udf_developer_role;
```

> A REVOKE at object level cannot remove a privilege that was granted at database level.
> Always revoke at the same scope the privilege was originally granted.

### Revoke

```sql
REVOKE SELECT ON mydb FROM role_name;
REVOKE ALL ON mydb FROM role_name;
```

### Special Privileges

```sql
-- System-wide
GRANT CONNECT THROUGH trusted_user TO PERMANENT target_user;
GRANT LOGON ON ALL AS DEFAULT;

-- Administrative
GRANT DUMP, RESTORE ON mydb TO admin_role;
GRANT MONITOR, ABORT SESSION TO admin_role;
```

## Access Logging (Audit)

```sql
-- Log all access to a table
BEGIN LOGGING ON EACH ALL ON mydb.sensitive_table;

-- Log specific operations
BEGIN LOGGING ON EACH SELECT, INSERT, UPDATE, DELETE ON mydb.customers;

-- Log denials only (failed access attempts)
BEGIN LOGGING DENIALS ON EACH ALL ON mydb.secret_data;

-- Log by user/role
BEGIN LOGGING ON EACH ALL BY user_name ON mydb.customers;

-- End logging
END LOGGING ON EACH ALL ON mydb.sensitive_table;

-- View access log
SELECT * FROM DBC.AccLogTbl
WHERE LogDate >= CURRENT_DATE - 7
ORDER BY LogDate DESC, LogTime DESC;

-- View logging rules
SELECT * FROM DBC.AccLogRulesV;
```

## Row-Level Security (RLS)

```sql
-- Create security constraint
CREATE CONSTRAINT security_constraint
    COLUMN security_level
    VALUES ('PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'SECRET')
    DEFAULT 'PUBLIC';

-- Apply to table
ALTER TABLE mydb.documents
    ADD security_constraint
    FOR INSERT, SELECT, UPDATE, DELETE;

-- Grant access levels
GRANT CONSTRAINT security_level VALUES ('PUBLIC', 'INTERNAL')
    TO standard_role;
GRANT CONSTRAINT security_level VALUES ('PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'SECRET')
    TO admin_role;
```

## CREATE AUTHORIZATION (External Credentials)

```sql
-- Store credentials for external access (NOS, LDAP, etc.)
CREATE AUTHORIZATION mydb.s3_auth
AS DEFINER TRUSTED
USER 'access_key'
PASSWORD 'secret_key';

-- Invoker-based (each user provides own credentials)
CREATE AUTHORIZATION mydb.ext_auth
AS INVOKER TRUSTED
USER ''
PASSWORD '';

-- Drop authorization
DROP AUTHORIZATION mydb.s3_auth;

-- Replace authorization
REPLACE AUTHORIZATION mydb.s3_auth
AS DEFINER TRUSTED
USER 'new_access_key'
PASSWORD 'new_secret_key';
```

## Catalog Views

| View | Content |
|---|---|
| `DBC.UsersV` | All users |
| `DBC.RolesV` | All roles |
| `DBC.RoleMembers` | Role→user mappings |
| `DBC.ProfilesV` | All profiles |
| `DBC.AllRightsV` | All granted privileges |
| `DBC.UserRightsV` | User-specific privileges |
| `DBC.AllRoleRightsV` | Role-specific privileges |
| `DBC.AccLogTbl` | Access log entries |
| `DBC.AccLogRulesV` | Active logging rules |
| `DBC.LogOnOffV` | Logon/logoff history |

```sql
-- List all privileges for a user
SELECT * FROM DBC.AllRightsV WHERE UserName = 'target_user';

-- List role memberships
SELECT * FROM DBC.RoleMembers WHERE RoleName = 'analytics_role';

-- Check who has access to a table
SELECT UserName, AccessRight FROM DBC.AllRightsV
WHERE DatabaseName = 'mydb' AND TableName = 'customers';
```

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| `Insufficient privileges` | Missing GRANT | Grant required privilege to user/role |
| `User already exists` | Duplicate CREATE USER | Use MODIFY USER instead |
| `Database not empty` | DROP USER with objects | Drop all objects first |
| `Invalid password` | Password policy violation | Check complexity requirements |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-security", path="references/FILENAME")` — do NOT call `list`.

Load these files for detailed technical reference on specific topics:

- **references/authentication-and-tdgss.md** — TDGSS architecture and all mechanisms (TD2, LDAP, KRB5, SPNEGO, TDNEGO), mechanism ranking (KRB5=40, SPNEGO=65, LDAP=70, TD2=20), TDNEGO auto-negotiation protocol, LDAP configuration (TdgssUserConfigFile.xml properties, binding methods, directory setup), identity maps and canonicalization, authorization mode (directory→TD mapping), SSL/TLS for LDAP, client auth syntax (BTEQ/CLI/JDBC/ODBC/.NET LOGMECH), tdsbind testing, troubleshooting
- **references/secure-zones.md** — Secure Zones for data isolation and multi-tenancy, zone DDL (CREATE/ALTER/DROP ZONE), ROOT management, zone users vs guests, GRANT/REVOKE ZONE, DBA user type (CREATE USER ... DBA), zone-wide vs system-wide privileges, Zone Override privilege, external auth restrictions, system tables (DBC.Zones, DBC.ZoneGuests), DbsControl flag #365
- **[UDF Privilege Setup](../../programmability-and-extensibility/scalar-udf-c/references/privilege-setup.md)** — Complete UDF grant/revoke guide: auto-grant rules, SPECIFIC FUNCTION syntax, UDT privilege hierarchy (UDTUSAGE/UDTTYPE/UDTMETHOD), DBC.AllRightsV privilege codes, REVOKE scope rules. Source: Teradata SQL Data Control Language, B035-1149
