# Secure Zones Reference

> Source: 541-0010639-A02 — Teradata Secure Zones Orange Book (TD 15.10+)

## 1. Overview

Secure Zones provides a mechanism to organize database hierarchies into separately protected zones. Each zone functions as a virtual system — users within a zone perceive it as the entire system.

**Key capabilities:**
- Prevents data access by anyone not associated with the zone
- Prevents unauthorized access by privileged database administrators (DBA user type)
- Zone-specific objects (roles, profiles, tables) are invisible to other zones
- System-wide object names (DATABASE, USER, ROLE, PROFILE, CONSTRAINT, AUTHORIZATION, FOREIGN SERVER) must be unique across all zones

**The feature is disabled by default** and must be enabled by an authorized Teradata representative. A license may be required.

### Use Cases

| Use Case | Description |
|---|---|
| **Multinational/Conglomerate** | Subsidiaries isolated from each other; corporate-level users may access across zones as guests; zone DBAs administer within their zone |
| **Sandbox** | Isolated environment for experimentation within production; users granted explicit access; cannot grant rights to non-sandbox users |
| **Multi-tenancy** | Multiple tenants consolidated on one system; complete data segregation; tenant DBAs administer locally; use Virtual Partitions for workload isolation |

## 2. Zone DDL

### CREATE ZONE

```sql
CREATE ZONE zone_name;
CREATE ZONE zone_name ROOT root_name;
```

- Executed by user DBC or a user explicitly granted CREATE ZONE privilege
- ROOT user/database must be **empty** — no pre-existing objects, descendants, roles, profiles, or privilege grants

**Examples:**
```sql
CREATE ZONE acme ROOT acme_sysdba;   -- user as root
CREATE ZONE acme ROOT acme_db;        -- database as root
```

### ALTER ZONE

```sql
ALTER ZONE zone_name ADD ROOT root_name;
ALTER ZONE zone_name DROP ROOT;
```

- Only the **zone creator** can add or drop the ROOT
- ROOT must be empty when adding or dropping
- DROP ROOT delinks the ROOT — it does not drop the user/database

**Examples:**
```sql
ALTER ZONE acme ADD ROOT acme_db;
ALTER ZONE acme DROP ROOT;
```

### DROP ZONE

```sql
DROP ZONE zone_name;
```

- Zone must have **no guests** and **no ROOT** associated before dropping
- Revoke all guest access and delink ROOT first
- Only users with DROP ZONE privilege can drop a zone

**Keyword added:** `ROOT` (non-reserved keyword)

**Access rights added:** `CREATE ZONE`, `DROP ZONE`, `ZONE OVERRIDE`

## 3. Zone ROOT

### User as ROOT

When a user is assigned as ROOT, that user automatically becomes the zone's **primary DBA**. Primary DBA functions:
1. Create secondary DBAs and other users for the zone
2. Create zone-level objects (roles, profiles, etc.)
3. Grant zone-specific privileges to zone guests

```sql
CREATE ZONE acme ROOT acme_sysdba;
```

### Database as ROOT

Typically preferred. A database is assigned as ROOT, then a primary DBA user is created from it.

```sql
CREATE ZONE acme ROOT acme_db;

-- Create primary DBA from the ROOT database
CREATE USER acme_sysdba FROM acme_db AS
    PERM=1e6, PASSWORD=pwd;
```

All privileges on the ROOT are implicitly granted to the primary DBA.

### Best Practices

- **Use a DATABASE as zone ROOT** — create a uniquely identified user as primary DBA for auditability
- **Segregation of duties** — primary/secondary DBA users within a zone should not be granted rights to administer the zone itself
- **Zone maintenance user** — create a system-level user specifically for zone creation/dropping that is not tied to a single individual

## 4. Populating Zones

Objects created by zone users automatically belong to that zone. No DDL syntax changes are required.

- The primary DBA is the initial user (analogous to DBC in a regular system)
- All creation begins with the primary DBA and users it creates
- Zone-specific objects (tables, views, roles, profiles) are not accessible by other zones
- **System-wide object names must be unique** across all zones

**Best Practice:** Establish naming conventions to ensure uniqueness across zones (e.g., prefix with zone/tenant name).

## 5. Zone Access Control

### Zone Users

- Users within one zone **cannot** access objects in another zone
- Zone users can access objects in the same zone with required DAC privileges
- Privilege grants on zoned objects are limited to users in the same zone and zone guests
- **WITH GRANT OPTION** cannot be used when granting zoned objects to zone guests

### Zone User Access to Non-Zone Objects

Controlled by DbsControl flag #365 `AllowZUOpsInNZSpace`:
- **FALSE** (default): zone users cannot access non-zone objects
- **TRUE**: zone users with required privileges can access non-zone database objects
- Changes are effective immediately

### Zone Guests

Non-zone users can access zoned objects if granted **both** zone access and DAC privileges.

```sql
-- Zone creator grants zone access
GRANT ZONE <list of zones> TO <list of users or roles>;

-- Primary DBA grants DAC privileges
GRANT SELECT ON acme.table1 TO finance_user;
```

**Zone access must be granted before DAC privileges can be granted.**

If zone access is revoked, data access is immediately disallowed even though DAC privileges remain.

```sql
REVOKE ZONE <list of zones> FROM <list of recipients>;
```

**Zone access cannot be granted to:**
- User DBC
- Zone users or roles (already in a zone)
- The zone creator
- Roles granted to the zone creator

**Maximum:** 25 zones can be granted/revoked in one statement.

**Examples:**
```sql
GRANT ZONE acme TO finance_user;
REVOKE ZONE acme FROM finance_user;
```

## 6. DBA User Type

Creates a database administrator with **restricted data access**. DBA users cannot perform DML on objects they create except in their own space.

```sql
CREATE USER acme_dba1 AS PERM=1e6, PASSWORD=pwd, DBA;
MODIFY USER acme_dba1 AS NOT DBA;
```

**DBA user restrictions:**
- Cannot access objects they created in another user's space (despite creator privileges)
- Cannot access objects in users/databases they created (despite database-level creator privileges)
- Can perform DML on objects in their own user space
- Can perform DML on objects created by others if they have required DAC privileges

**Authorization:** Only users granted EXECUTE on macro `DBC.DBAUserAdmin` can specify the DBA/NOT DBA options.

Changing DBA → NOT DBA restores access to objects created while functioning as a DBA user.

## 7. Zone-Wide vs System-Wide Privileges

| Scope | Storage | Examples |
|---|---|---|
| **System-wide** | `DBC.AccessRights.DatabaseId` = PUBLIC's internal ID | CREATE ROLE, CREATE PROFILE, MONITOR SESSION |
| **Zone-wide** | `DBC.AccessRights.DatabaseId` = zone's ID | CONSTRAINT ASSIGNMENT for RLS tables within a zone |

For zone-wide CONSTRAINT ASSIGNMENT, the privilege, security constraint, and containing database must all share the same zone ID.

### Ownership Privileges

- Ancestors above a zoned database/user that are **not** in the same zone lose ownership access
- The ROOT owner loses implicit ownership privileges on objects in the zoned descendant's space
- ARC utility: dump/restore on zoned descendants requires zone access + DUMP/RESTORE privilege; otherwise the zoned database is skipped

## 8. Zone Override Privilege

Allows users to access **all** system table rows without zone restrictions.

```sql
GRANT ZONE OVERRIDE TO <list of users or roles>;
```

**Key behaviors:**
- DBC has system-wide dictionary access including all zoned data by default
- Users with SELECT on V views need ZONE OVERRIDE for system-wide access
- Teradata Viewpoint data collection accounts may require ZONE OVERRIDE
- Users with Zone Override can enable/disable query logging without zone restrictions

## 9. External Authentication in Zones

| Feature | Zone Users | Zone Guests |
|---|---|---|
| LDAP/KRB5 authentication | Supported | Supported |
| External authorization | **NOT supported** — logon fails | Supported via external roles |

**Zone guest external authorization** requires:
- Zone access granted to external roles mapped to LDAP/Kerberos groups
- Required DAC privileges on zone objects granted to active external roles

### Trusted Sessions

Trusted user, permanent proxy user, and proxy role in a GRANT CONNECT THROUGH statement **cannot** belong to a secure zone.

```sql
-- This will FAIL if any of these belong to a zone:
GRANT CONNECT THROUGH trusted_user
    TO PERMANENT proxy_user
    WITH ROLE proxy_role;
```

Application proxy users can access zone objects if the proxy role has both zone access and DAC privileges.

## 10. System Tables and Views

### New System Tables

**DBC.Zones** — Zone object definitions

| Column | Type | Description |
|---|---|---|
| ZoneId (UPI) | BYTE(4) NOT NULL | Unique zone ID |
| ZoneNameI (USI) | VARCHAR(128) UNICODE NOT CASESPECIFIC | Zone name |
| ZoneCreatorId | BYTE(4) NOT NULL | Creator's ID |
| CreateTimeStamp | TIMESTAMP(0) NOT NULL | Creation timestamp |
| ZoneRootId | BYTE(4) | Root user/database ID |
| IsRootAUser | CHAR(1) | 'Y'=user, 'N'=database, '?'=not set |
| ZonePrimaryDBAID | BYTE(4) | Primary DBA ID |
| CommentString | VARCHAR(255) UNICODE | Comments |

**DBC.ZoneGuests** — Guest access grants

| Column | Type | Description |
|---|---|---|
| GuestID (NUPI) | BYTE(4) NOT NULL | Guest user/role ID |
| ZoneID (NUSI) | BYTE(4) NOT NULL | Zone ID |
| GrantorID | BYTE(4) NOT NULL | Grantor ID |
| CreateTimeStamp | TIMESTAMP(0) NOT NULL | Grant timestamp |

### New System Views

**DBC.ZonesV** — Columns: ZoneName, RootName, PrimaryDBAName, CreatorName, CreateTimeStamp

**DBC.ZoneGuestsV** — Columns: ZoneName, GuestName, GrantorName, GrantedTimeStamp

### Modified Tables (ZoneId column added)

AccLogRuleTbl, AccLogTbl, ConstraintValues, Dbase, DBQLExplainTbl, DBQLObjTbl, DBQLogTbl, DBQLRuleTbl, DBQLSqlTbl, DBQLStepTbl, DBQLSummaryTbl, DBQLXMLTbl, EventLog, Profiles, Roles, SecConstraints, SessionTbl

### Modified Views

**DBC.AccLogRulesV** — Added: CZN (CreateZone), DZN (DropZone), OZN (ZoneOverride), ZoneName

**DBC.AccessLogV** — Added: ZoneName

### System Variable

`ZONE` — added for Secure Zones

## 11. Access Logging and DBQL

### Access Logging

Logging rules apply only to users/objects within the rule creator's zone.

```sql
-- NOT allowed by zone user (system-wide):
BEGIN LOGGING ON ALL;

-- Allowed (zone-scoped):
BEGIN LOGGING ON ALL ON DATABASE acme_db1;
BEGIN LOGGING ON ALL BY acme_user1;
BEGIN LOGGING ON ALL FOR CONSTRAINT acme_constr1;
```

### DBQL Logging

Scope depends on the rule creator:
- **System-wide user** (DBC or non-zone user with Zone Override) → system-wide rules
- **Zone user** → zone-scoped rules

```sql
-- Zone user: logs only users in same zone
BEGIN QUERY LOGGING ON ALL;

-- Non-zone user without Zone Override: logs only non-zone users
BEGIN QUERY LOGGING ON ALL;

-- DBC can remove all logging rules:
END QUERY LOGGING ON ALL;
```

## 12. DbsControl Settings

| Flag | Category | Default | Description |
|---|---|---|---|
| #365 AllowZUOpsInNZSpace | Internal | FALSE | Controls whether zone users can access non-zone database objects. Changes effective immediately. |

## 13. Error Messages

### DCL Messages

| Code | Message |
|---|---|
| 9867 | The executor does not have access to the zone of *user_name* |
| 9874 | Only the zone creator is allowed to alter/grant the zone *zone_name* |
| 9876 | The user or role cannot be a zone guest |
| 9878 | Guest role cannot be granted to zone creator directly or through nested role |
| 9923 | A zoned object cannot be granted WITH GRANT/ALL OPTION to a non-zoned object |
| 9924 | Too many zones listed in GRANT/REVOKE statement (max 25) |
| 9925 | A zone guest cannot be connected to zone creator directly or through nested role |

### DDL Messages

| Code | Message |
|---|---|
| 9024 | COPY operation not yet supported for zoned objects |
| 9861 | Cannot delink/drop/assign — objects still associated with root |
| 9862 | User/database is already part of another zone |
| 9863 | Cannot drop zone with root still associated |
| 9864 | A root must be defined for the zone |
| 9865 | Root for zone already exists |
| 9866 | Cannot drop zone with a guest still associated |
| 9868 | Zone creator cannot be a guest/root/admin of the zone |
| 9869 | Zone does not exist |
| 9870 | Role cannot be a zone root (only user or database) |
| 9871 | Zone guest cannot be assigned as zone root/admin |
| 9872 | Cannot delink root with primaryDBA still associated |
| 9873 | Ownership can only be transferred within the zone |
| 9875 | Primary administrator is not assigned to the zone |
| 9877 | Cannot drop user still linked to the zone |
| 9918 | Zoned users cannot be defined as trusted users |
| 9927 | Current user's zoneid does not match zoneid of profile |
| 9928 | A zone with the name already exists |
| 9929 | Current user's zoneid does not match zoneid of the role |

### Access Logging Messages

| Code | Message |
|---|---|
| 9914 | Current user's zoneid does not match zoneid of object being logged |
| 9917 | Cannot specify a user or object in a different zone |

### Other Messages

| Code | Message |
|---|---|
| 9879 | Concurrent change conflict on zone — try again |
| 9919 | Zones of constraint and target table do not match |
| 9926 | Nested Zone is currently not supported |

## 14. Best Practices

1. **Use DATABASE as zone ROOT** — create a unique user as primary DBA for proper audit trails
2. **Segregation of duties** — zone DBA users should not have zone administration privileges
3. **System-level zone admin** — create a non-individual system user for zone create/drop operations
4. **Naming conventions** — prefix object names with zone/tenant identifiers to ensure system-wide uniqueness
5. **DBA user type** — use for zone administrators who should not access data they create for others
6. **Zone Override sparingly** — grant only to accounts that genuinely need cross-zone dictionary access (e.g., Viewpoint)
7. **Workload isolation** — Secure Zones does not address workload management; use Virtual Partitions for multi-tenant workload isolation
8. **Zone access before DAC** — always grant ZONE access first, then DAC privileges
9. **No nested zones** — plan flat zone hierarchies; nesting is not supported

### Restrictions (Initial Release)

- No nested zones
- No COPY of zoned objects
- No zone-specific name uniqueness (names must be globally unique)
- No zone-wide access logging rule for all users/objects in a zone
- No external authorization of zone users
- No Trusted Sessions for zoned trusted users, permanent proxy users, or proxy roles
