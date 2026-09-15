# Privilege Setup for External UDFs

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** Privilege Setup for External UDFs

Comprehensive reference for all Teradata privileges needed to create, manage, and call
external UDFs (C/C++/Java), along with the related UDT privileges their signatures may
require. Based on Teradata Vantage™ — SQL Data Control Language, B035-1149.

---

## UDF Privilege Behavior

### What Is (and Isn't) Automatically Granted

| Privilege | Auto-granted to function creator? | Auto-granted to a new database/user? | Grant scope |
|-----------|-----------------------------------|--------------------------------------|-------------|
| `CREATE FUNCTION` | **No** — must be granted explicitly | **No** | Database level only |
| `DROP FUNCTION` | **Yes** — WITH GRANT OPTION on the created function | Yes — on itself, without grant option | Database or function level |
| `EXECUTE FUNCTION` | **Yes** — WITH GRANT OPTION on the created function | **No** | Database or function level |
| `ALTER FUNCTION` | **No** — only DBC holds it implicitly | **No** | Database level only; **cannot be granted on a specific UDF** |

**Key consequences:**

- Because `CREATE FUNCTION` is never automatic, it must be explicitly granted before any user or
  role can create UDFs in a database.
- Once a user has `CREATE FUNCTION` on a database, every function they create automatically
  receives `DROP FUNCTION` and `EXECUTE FUNCTION WITH GRANT OPTION` on that specific function.
- `DROP FUNCTION` also authorises `REPLACE FUNCTION`. A user who drops a function cannot
  re-create it later without also holding `CREATE FUNCTION`.
- `ALTER FUNCTION` changes execution mode (PROTECTED ↔ NOT PROTECTED) and triggers recompile
  or re-link. Switching a UDF to NOT PROTECTED mode is high-risk; restrict this privilege to DBAs.
  **`GRANT ALTER FUNCTION` must target a database** — it cannot be granted on a specific function
  object. The `ALTER FUNCTION` DDL statement itself (e.g., `ALTER FUNCTION mydb.my_func EXECUTE
  NOT PROTECTED`) does operate on specific functions, but the privilege scope for granting is
  database-level only.

---

## Grant Statements

### Creation and Lifecycle

```sql
-- Allow creating and replacing UDFs (includes REPLACE FUNCTION)
GRANT CREATE FUNCTION ON udf_db TO udf_developer_role;

-- Allow dropping and replacing UDFs
GRANT DROP FUNCTION ON udf_db TO udf_developer_role;

-- Allow altering function properties, execution mode, recompile (DBA only)
-- Note: ALTER FUNCTION cannot be granted on a specific function
GRANT ALTER FUNCTION ON udf_db TO udf_dba_role;
```

### Consumer Grants (Execute)

Three equivalent forms — choose the narrowest scope:

```sql
-- All functions in a database
GRANT EXECUTE FUNCTION ON udf_db TO app_role;

-- One function by its SPECIFIC name (preferred for overloaded functions)
GRANT EXECUTE ON SPECIFIC FUNCTION udf_db.my_function_v1 TO app_role;

-- One function by its signature (use when specific name is unknown)
GRANT EXECUTE FUNCTION ON udf_db.my_function(INTEGER, VARCHAR(100)) TO app_role;
```

> The `SPECIFIC FUNCTION` form is the most precise: it resolves a single overloaded variant
> without listing parameter types. Use it when granting consumer access to one of several
> overloads registered under the same name.

### Java UDF JAR Management

`EXECUTE PROCEDURE` is a general privilege that applies to any stored procedure. For Java
UDF developers, grant it on the specific SQLJ procedures used to manage JARs:

```sql
-- Required before CALL SQLJ.INSTALL_JAR (also covers SQLJ.REPLACE_JAR)
GRANT EXECUTE PROCEDURE ON SQLJ.INSTALL_JAR TO udf_developer_role;

-- Required before CALL SQLJ.REMOVE_JAR
GRANT EXECUTE PROCEDURE ON SQLJ.REMOVE_JAR TO udf_developer_role;
```

These are object-level grants on system-owned procedures. A DBC administrator grants them
once per developer role.

---

## UDT Privileges (Conditional)

Required only when a UDF signature includes User Defined Types (UDTs). Standard SQL types
(INTEGER, VARCHAR, FLOAT, DATE, etc.) do not need UDT grants.

### Privilege Hierarchy

| Privilege | Code | What it allows | Grant scope |
|-----------|------|----------------|-------------|
| `UDTUSAGE` | `UU` | Use existing UDTs in tables, queries, UDFs, and procedures; execute existing methods | `SYSUDTLIB` database **or** a specific UDT |
| `UDTTYPE` | `UT` | Everything in UDTUSAGE + CREATE/DROP/ALTER TYPE, CREATE/DROP ORDERING, CREATE/DROP CAST, CREATE/DROP TRANSFORM | `SYSUDTLIB` database only |
| `UDTMETHOD` | `UM` | Everything in UDTTYPE + CREATE/ALTER/DROP METHOD | `SYSUDTLIB` database only |

- `UDTUSAGE` is the minimum for UDF developers who reference existing UDT types.
- `UDTTYPE` is for teams that also author or maintain UDT definitions.
- `UDTMETHOD` is for full UDT library management, including method authorship.

### What UDTUSAGE Does and Does Not Allow

| Allowed | Not Allowed |
|---------|------------|
| CREATE/ALTER TABLE with UDT columns | CREATE new UDTs |
| Reference a UDT in a query, UDF, or procedure | DROP existing UDTs |
| Execute methods associated with a UDT | CREATE, ALTER, or DROP methods |
| | ALTER ordering, casting, or transform behavior |

For nested structured UDTs, privileges are **not** inherited from parent types. Grant
`UDTUSAGE` on each component UDT explicitly, or grant on the entire `SYSUDTLIB` database.

### UDT Grant Statements

```sql
-- UDTUSAGE on all UDTs (most common for UDF developers)
GRANT UDTUSAGE ON SYSUDTLIB TO udf_developer_role;

-- UDTUSAGE on a specific named UDT (narrow scope)
GRANT UDTUSAGE ON TYPE circle TO udf_developer_role;
GRANT UDTUSAGE ON TYPE SYSUDTLIB.square TO udf_developer_role;

-- UDTTYPE: create and modify UDT definitions
GRANT UDTTYPE ON SYSUDTLIB TO udf_author_role;

-- UDTMETHOD: full UDT management (with re-grant ability)
GRANT UDTMETHOD ON SYSUDTLIB TO udf_dba_role WITH GRANT OPTION;

-- CREATE/DROP FUNCTION in SYSUDTLIB (for UDFs registered in SYSUDTLIB)
GRANT CREATE FUNCTION ON SYSUDTLIB TO udf_developer_role;
GRANT DROP FUNCTION ON SYSUDTLIB TO udf_developer_role;
```

---

## WITH GRANT OPTION

Append `WITH GRANT OPTION` to allow the recipient to re-grant the privilege:

```sql
GRANT CREATE FUNCTION ON udf_db TO team_lead WITH GRANT OPTION;
```

Only user DBC and the object owner have an implicit `WITH GRANT OPTION`. All other users
must receive it explicitly if they need to delegate.

---

## Revoking Privileges

```sql
-- Revoke execute on all functions in a database
REVOKE EXECUTE FUNCTION ON udf_db FROM app_role;

-- Revoke execute on a specific function
REVOKE EXECUTE ON SPECIFIC FUNCTION udf_db.my_function_v1 FROM app_role;

-- Revoke CREATE FUNCTION
REVOKE CREATE FUNCTION ON udf_db FROM udf_developer_role;

-- Revoke UDT privilege
REVOKE UDTUSAGE ON SYSUDTLIB FROM udf_developer_role;
```

> **Revocation scope rule:** A REVOKE at object level cannot remove a privilege that was
> originally granted at the database level. Revoke at the same scope the privilege was granted.

---

## Checking Effective Privileges

```sql
-- All privileges on functions in a database
SELECT AccessRight, GrantorName, UserName, TableName
FROM DBC.AllRightsV
WHERE DatabaseName = 'udf_db'
ORDER BY TableName, AccessRight;

-- Check if a user has EXECUTE FUNCTION on a specific function
SELECT AccessRight, UserName
FROM DBC.AllRightsV
WHERE DatabaseName = 'udf_db'
  AND TableName = 'my_function'
  AND AccessRight IN ('EF', 'CF', 'DF', 'AF');
```

**Privilege codes in DBC.AccessRights:**

| Code | Privilege |
|------|-----------|
| `CF` | CREATE FUNCTION |
| `DF` | DROP FUNCTION |
| `EF` | EXECUTE FUNCTION |
| `AF` | ALTER FUNCTION |
| `UU` | UDTUSAGE |
| `UT` | UDTTYPE |
| `UM` | UDTMETHOD |
| `EP` | EXECUTE PROCEDURE |

---

## References

- Teradata Vantage™ — SQL Data Control Language, B035-1149
  (https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-Data-Control-Language)
- Teradata Vantage™ — SQL Data Definition Language Syntax and Examples, B035-1144
- Teradata Vantage™ — SQL External Routine Programming, B035-1147
