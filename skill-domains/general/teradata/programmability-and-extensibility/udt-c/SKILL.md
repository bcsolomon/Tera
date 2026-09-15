---
name: udt-c
description: 'Install, manage, and remove C/C++ User-Defined Types (UDTs) and User-Defined Methods (UDMs) on Teradata, including DISTINCT and STRUCTURED types with instance and constructor methods. UDTs and their methods reside in SYSUDTLIB. Covers CREATE TYPE with inline METHOD declarations (NO SQL, PARAMETER STYLE TD_GENERAL, DETERMINISTIC, LANGUAGE C), CREATE METHOD with EXTERNAL NAME CS!, the C UDM signature (UDT_HANDLE subject parameter, FNC_GetStructuredAttribute/FNC_SetStructuredAttribute), SELF AS RESULT for constructor/mutator methods, CREATE CAST, CREATE ORDERING (ORDER FULL BY MAP), CREATE TRANSFORM (TO SQL/FROM SQL), UDT privileges (UDTUSAGE/UDTTYPE/UDTMETHOD on SYSUDTLIB), and the exact teardown order (DROP CAST -> DROP ORDERING -> DROP TRANSFORM -> DROP FUNCTION -> ALTER TYPE DROP SPECIFIC METHOD -> DROP TYPE). Based on Teradata SQL External Routine Programming v20.00.'
when_to_use: 'Use when the user mentions C UDT, C UDM, structured type in C, CREATE TYPE LANGUAGE C, CREATE METHOD, instance method, constructor method, SELF AS RESULT, UDT_HANDLE, FNC_GetStructuredAttribute, PARAMETER STYLE TD_GENERAL, CREATE CAST, CREATE ORDERING, CREATE TRANSFORM, ALTER TYPE DROP METHOD, SYSUDTLIB, or wants to define a custom SQL data type backed by C code.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata C/C++ User-Defined Type (UDT)

> **Installation differs by platform.** All Teradata systems support external UDFs, XSPs, and UDTs,
> but not all allow the same installation process. The `CREATE`/`REPLACE ... EXTERNAL NAME` DDL in
> this skill applies to on-prem systems where you have full access to the database nodes. On
> Teradata-managed systems, direct DDL installation may be blocked for security reasons:
>
> - **VantageCloud Lake:** use the `tdextroutine` CLI to install, list, and uninstall these objects.
>   See [Create, Use, and Migrate UDFs and External Stored Procedures in VantageCloud Lake](https://docs.teradata.com/r/Lake-Using-Queries-UDFs-and-External-Stored-Procedures/Create-Use-and-Migrate-UDFs-and-External-Stored-Procedures-in-VantageCloud-Lake).
> - **VantageCloud Enterprise:** `EXTERNAL NAME` installation is supported on Compute Engine nodes
>   but not on the primary Enterprise Data Warehouse (EDW) node; that is typically handled through a
>   customer service request.
>
> Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`.

A **DISTINCT UDT** wraps a single predefined SQL type with a new type identity (incompatible
with the base type without explicit `CAST`). A **STRUCTURED UDT** is a composite type with
named attributes, backed by C methods (UDMs).

> **Not this skill:** For Java UDTs, see **udt-java**. For C scalar UDFs, see **scalar-udf-c**.

## Residence and Privileges

UDTs and their methods always reside in the **SYSUDTLIB** database. `CREATE TYPE` and
`CREATE METHOD` resolve to SYSUDTLIB; qualify with `SYSUDTLIB` (or leave unqualified) rather
than a user database. Standalone CAST/ORDERING/TRANSFORM **functions** (UDFs, not methods) may
live in a user database but are conventionally kept with the type in SYSUDTLIB.

Grant the UDT privileges on the SYSUDTLIB database:

```sql
-- To create a table with a UDT column or invoke its methods:
GRANT UDTUSAGE ON SYSUDTLIB TO app_role;
-- To create/alter the type and its methods:
GRANT UDTTYPE, UDTMETHOD ON SYSUDTLIB TO udt_developer_role;
```

`UDTUSAGE` is needed to use a UDT (table column, query, method invocation); `UDTTYPE` and
`UDTMETHOD` are needed to define types and methods.

## When to Use

- Defining a type-safe domain wrapper (e.g., `meter`, `kg`) around a numeric type
- Creating a structured geometric or measurement type with instance methods
- Registering CAST, ORDERING, or TRANSFORM for a custom type
- Tearing down a UDT and all its dependents in the correct order

## Complete Dependency Order

```
CREATE TYPE (declares methods inline)
    ↓
CREATE METHOD (implements each declared method)
    ↓
CREATE CAST (type conversions)
    ↓
CREATE ORDERING (comparison operators)
    ↓
CREATE TRANSFORM (serialization)
```

Teardown reverses this order exactly. See [Procedure: Uninstall](#procedure-uninstall).

## Procedure: Create a DISTINCT UDT

A DISTINCT type wraps one predefined type:

```sql
CREATE TYPE SYSUDTLIB.meter AS FLOAT FINAL;
```

Not compatible with plain `FLOAT`; requires an explicit `CAST` in queries. For distinct types
Vantage **automatically generates** the cast (to/from the source type), ordering, and transform
functionality, so no `CREATE METHOD` is required for basic use. You may drop the auto-generated
ordering/transform and supply your own. (Ordering is not auto-generated when the source type is
a LOB.)

## Procedure: Create a STRUCTURED UDT with C Method

### Step 1: Declare type and method signature

Declare each method inline in `CREATE TYPE` with its full attributes. `SPECIFIC`,
`PARAMETER STYLE`, `LANGUAGE`, and (for constructor/mutator methods) `SELF AS RESULT` belong
**here**, not in `CREATE METHOD`. A getter such as `area()` that returns a predefined type does
**not** use `SELF AS RESULT`.

```sql
CREATE TYPE SYSUDTLIB.circle_t AS (
    radius FLOAT
)
NOT FINAL
INSTANCE METHOD area()
    RETURNS FLOAT
    SPECIFIC area_of_circle
    NO SQL
    PARAMETER STYLE TD_GENERAL
    DETERMINISTIC
    LANGUAGE C;
```

### Step 2: Write C source for the method

A UDM receives the subject UDT instance as a `UDT_HANDLE *` (the first parameter). Read
structured attributes by name with `FNC_GetStructuredAttribute` (dereference the handle).
With `PARAMETER STYLE TD_GENERAL` the parameter list is the subject handle, the inputs, the
result pointer, and `sqlstate` (no indicator or name parameters).

```c
#define SQL_TEXT Latin_Text
#include <sqltypes_td.h>

void circle_area(UDT_HANDLE *circleUDT,
                 FLOAT      *result,
                 char        sqlstate[6])
{
    FLOAT radius;
    int   nullIndicator;
    int   length;

    /* Read the radius attribute of the subject UDT by name. */
    FNC_GetStructuredAttribute(*circleUDT, "radius", &radius, sizeof(FLOAT),
                               &nullIndicator, &length);

    *result = 3.14159265 * radius * radius;
}
```

> **Constructor / mutator methods** use `SELF AS RESULT` and take an extra `UDT_HANDLE *result`
> for the returned UDT instance; set its attributes with `FNC_SetStructuredAttribute`, for
> example `FNC_SetStructuredAttribute(*result, "radius", &newval, nullInd, sizeof(FLOAT));`.

### Step 3: Implement the method

`CREATE METHOD` only locates the source and binds it to the type. Do **not** repeat `SPECIFIC`,
`SELF AS RESULT`, `PARAMETER STYLE`, or `LANGUAGE` here; they are already fixed by `CREATE TYPE`.

```sql
CREATE METHOD area()
    RETURNS FLOAT
    FOR SYSUDTLIB.circle_t
EXTERNAL NAME 'CS!circle_area!udt_src/circle.c!F!circle_area';
```

The `CS` clause is `CS!name_on_server!source_path`; append `!F!c_function_name` when the C entry
point differs from the method name (here the C function is `circle_area`).

## Procedure: Create CAST (optional)

Registers a conversion between two types:

```sql
CREATE CAST (SYSUDTLIB.meter AS SYSUDTLIB.foot)
WITH SPECIFIC METHOD SYSUDTLIB.meter_to_foot
AS ASSIGNMENT;
```

`AS ASSIGNMENT` enables implicit casting on assignment. Without it, only `CAST(x AS type)` works.

## Procedure: Create ORDERING (optional)

Allows `ORDER BY`, `MIN`, `MAX`, and comparison operators on UDT values. The map routine reads
the UDT and returns a single value of a predefined comparable type; Vantage compares those
mapped values. v20.00 documents `ORDER FULL BY MAP`:

```sql
CREATE ORDERING FOR SYSUDTLIB.circle_t
    ORDER FULL BY MAP
    WITH SPECIFIC METHOD SYSUDTLIB.circle_map;
```

| Clause | Meaning |
|--------|---------|
| `ORDER FULL BY MAP` | The map routine returns one comparable value (for example a FLOAT) that Vantage uses for all comparisons |
| `WITH SPECIFIC METHOD m` | Use an instance method of the UDT as the map routine |
| `WITH SPECIFIC FUNCTION f` | Use a standalone UDF as the map routine |

For a structured UDT you must supply the ordering; for a distinct UDT it is auto-generated.

## Procedure: Create TRANSFORM (optional)

Defines how to serialize/deserialize the UDT for storage:

```sql
CREATE TRANSFORM FOR SYSUDTLIB.circle_t CIRCLES_XFORM (
    TO SQL   WITH SPECIFIC FUNCTION SYSUDTLIB.bytes_to_circle,
    FROM SQL WITH SPECIFIC METHOD  SYSUDTLIB.circle_to_bytes
);
```

- `TO SQL`: deserialize (predefined type to UDT, used on import/read)
- `FROM SQL`: serialize (UDT to predefined type, used on export/store)

## Procedure: Verify

```sql
HELP TYPE SYSUDTLIB.circle_t;
HELP METHOD area() FOR SYSUDTLIB.circle_t;

SELECT TypeName, DatabaseName FROM DBC.TypesV
WHERE DatabaseName = 'SYSUDTLIB' AND TypeName = 'circle_t';

SELECT FunctionName, SpecificName FROM DBC.FunctionsV
WHERE DatabaseName = 'SYSUDTLIB' AND MethodForType = 'circle_t';
```

## Procedure: Uninstall

Follow this order exactly. Skipping steps or reversing the order causes constraint errors.

```sql
-- 1. Drop CAST
DROP CAST (SYSUDTLIB.meter AS SYSUDTLIB.foot);

-- 2. Drop ORDERING
DROP ORDERING FOR SYSUDTLIB.circle_t;

-- 3. Drop TRANSFORM
DROP TRANSFORM CIRCLES_XFORM FOR SYSUDTLIB.circle_t;
-- Or all transform groups: DROP TRANSFORM ALL FOR SYSUDTLIB.circle_t;

-- 4. Drop standalone FUNCTION objects (cast UDFs, comparison functions)
DROP SPECIFIC FUNCTION SYSUDTLIB.meter_to_foot;
DROP SPECIFIC FUNCTION SYSUDTLIB.bytes_to_circle;

-- 5. Drop instance methods via ALTER TYPE (NOT DROP FUNCTION)
ALTER TYPE SYSUDTLIB.circle_t DROP SPECIFIC METHOD area_of_circle;

-- 6. Drop the type
DROP TYPE SYSUDTLIB.circle_t;
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| Type already exists | Use `REPLACE TYPE` to change it, or uninstall dependents first |
| Instance method needs new code | Use `REPLACE METHOD ... EXTERNAL NAME` to reinstall the implementation |
| Forgot `ALTER TYPE DROP METHOD` | `DROP SPECIFIC FUNCTION` does NOT work for instance methods on types |
| Type column in a table | DROP or ALTER TABLE to remove the column before DROP TYPE |
| Type used in another UDT | Drop the dependent type first |
| Missing UDT privilege | Grant `UDTUSAGE` (use) or `UDTTYPE`/`UDTMETHOD` (define) on SYSUDTLIB |
| CAST drop fails with "no such cast" | Already removed; continue to next step |
| Teradata-managed platform (VantageCloud Lake or Enterprise) | External routines are supported, but direct `EXTERNAL NAME` install may be blocked. On Lake, install/list/uninstall with the `tdextroutine` CLI. On Enterprise, install on Compute Engine nodes or via a service request (not the EDW node). Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`. |

## References


> **Access:** `skill_resource_read(action="read", skill="udt-c", path="references/FILENAME")` — do NOT call `list`.

- [UDT Reference](./references/udt-reference.md): DISTINCT vs STRUCTURED comparison, full dependency graph, instance method syntax, CAST/ORDERING/TRANSFORM options, Java UDT notes, complete circle_t DDL example
