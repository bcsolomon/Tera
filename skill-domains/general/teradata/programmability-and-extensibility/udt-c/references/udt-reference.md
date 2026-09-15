# UDT Reference - Teradata SQL External Routine Programming (v20.00)

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** UDT Reference - Teradata SQL External Routine Programming (v20.00)

Source: https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming

UDTs and their methods (UDMs) reside in the **SYSUDTLIB** database. `CREATE TYPE` and
`CREATE METHOD` resolve there; the `database_name` placeholder below stands for SYSUDTLIB.
Required privileges: `UDTUSAGE` (use a UDT), `UDTTYPE`/`UDTMETHOD` (define types and methods)
on SYSUDTLIB.

---

## 1. DISTINCT vs STRUCTURED UDTs

| Feature | DISTINCT UDT | STRUCTURED UDT |
|---------|-------------|----------------|
| Based on | Single predefined SQL type | Multiple named attributes |
| Example | `CREATE TYPE meter AS FLOAT FINAL` | `CREATE TYPE circle_t AS (radius FLOAT) NOT FINAL` |
| Attributes | None (single value) | One or more named fields |
| Methods | Instance methods, cast, ordering | Instance methods, cast, ordering, transform |
| `FINAL` clause | Required (`FINAL`) | Usually `NOT FINAL` to allow subtypes |
| Interoperability | NOT compatible with base type without CAST | Each attribute accessed by name |
| Common use | Type-safe domain wrappers (units of measure) | Complex domain objects (shapes, coordinates) |

---

## 2. Full Dependency Graph

The objects associated with a UDT depend on each other in this order:

```
SQLJ.INSTALL_JAR (Java only)
    └─► CREATE TYPE (declares methods inline)
            └─► CREATE METHOD (implements each declared method)
                    └─► CREATE CAST (type conversions involving this type)
                    └─► CREATE ORDERING (comparison operators for this type)
                    └─► CREATE TRANSFORM (serialization for this type)
```

**Teardown order reverses the dependency graph:**
```
DROP CAST
    └─► DROP ORDERING
            └─► DROP TRANSFORM
                    └─► DROP FUNCTION (standalone cast/comparison functions)
                    └─► ALTER TYPE … DROP SPECIFIC METHOD (instance methods)
                            └─► DROP TYPE
                                    └─► SQLJ.REMOVE_JAR (Java only)
```

---

## 3. Instance Method Syntax

Instance methods are declared **inside** `CREATE TYPE` and implemented with a separate
`CREATE METHOD` statement.

### Declaring in CREATE TYPE

```sql
CREATE TYPE database_name.circle_t AS (
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

`SPECIFIC`, `PARAMETER STYLE`, `LANGUAGE`, and (for constructor/mutator methods) `SELF AS RESULT`
are declared here, not in `CREATE METHOD`. A getter returning a predefined type (such as `area()`)
does not use `SELF AS RESULT`.

### Implementing with CREATE METHOD

```sql
CREATE METHOD area()
    RETURNS FLOAT
    FOR database_name.circle_t
EXTERNAL NAME 'CS!circle_area!udt_src/circle.c!F!circle_area';
```

`CREATE METHOD` only locates the source and binds it to the type; it does not repeat `SPECIFIC`,
`SELF AS RESULT`, `PARAMETER STYLE`, or `LANGUAGE`. Append `!F!c_function_name` to the `CS` clause
when the C entry point differs from the method name. The `SPECIFIC` name (set in `CREATE TYPE`)
uniquely identifies the method for `ALTER TYPE ... DROP SPECIFIC METHOD`.

---

## 4. CAST Method Syntax

A CAST registers a conversion between two types.

```sql
CREATE CAST (database_name.meter AS database_name.foot)
WITH SPECIFIC METHOD database_name.meter_to_foot
AS ASSIGNMENT;
```

`AS ASSIGNMENT` enables implicit casting on `=` and `INSERT ... VALUES`. Without it,
only explicit `CAST(x AS type)` works.

Drop a cast:
```sql
DROP CAST (database_name.meter AS database_name.foot);
```

---

## 5. ORDERING Method Options

ORDERING defines how two UDT values compare. v20.00 documents `ORDER FULL BY MAP`: the map
routine reads the UDT and returns a single value of a predefined comparable type, and Vantage
compares those mapped values.

| Clause | Meaning |
|--------|---------|
| `ORDER FULL BY MAP` | Map routine returns one comparable value (for example a FLOAT) used for all comparisons |
| `WITH SPECIFIC METHOD m` | Use an instance method of the UDT as the map routine |
| `WITH SPECIFIC FUNCTION f` | Use a standalone UDF as the map routine |

Distinct UDTs get ordering auto-generated; structured UDTs must supply it. Example:

```sql
CREATE ORDERING FOR database_name.circle_t
    ORDER FULL BY MAP
    WITH SPECIFIC METHOD database_name.circle_map;
```

---

## 6. TRANSFORM Group Syntax

A transform group maps a UDT to/from its serialized form (e.g., VARBYTE for C types).

```sql
CREATE TRANSFORM FOR database_name.circle_t MY_TRANSFORM_GROUP (
    TO SQL   WITH SPECIFIC FUNCTION database_name.deserialize_circle,
    FROM SQL WITH SPECIFIC METHOD  database_name.serialize_circle
);
```

- `TO SQL`: deserializes the predefined type into the UDT (used on import/read)
- `FROM SQL`: serializes the UDT to the predefined type (used on export/store)

Drop a transform group:
```sql
DROP TRANSFORM MY_TRANSFORM_GROUP FOR database_name.circle_t;
-- Or drop all transform groups:
DROP TRANSFORM ALL FOR database_name.circle_t;
```

---

## 7. ALTER TYPE DROP SPECIFIC METHOD

Instance methods declared on a type must be removed via `ALTER TYPE`, **not** `DROP FUNCTION`.

```sql
ALTER TYPE database_name.circle_t DROP SPECIFIC METHOD area_of_circle;
```

Common mistake: using `DROP SPECIFIC FUNCTION` for a method → this will fail.

---

## 8. Java UDT Notes

- The Java class must implement `java.io.Serializable`.
- Use boxed types for nullable parameters: `Integer`, `Double`, `Long`, `String`.
- Java EXTERNAL NAME for methods uses the same 4-part format as UDFs:
  `'JAR_ALIAS:ClassName.methodName(java.lang.Integer) returns java.lang.Integer'`
- The `DATABASE` statement before `SQLJ.INSTALL_JAR` sets the JAR's owning database.

---

## 9. Structured UDT Example - circle_t (C)

Full example showing all DDL steps:

```sql
-- 1. Create the structured type with method declaration
CREATE TYPE production.circle_t AS (
    radius FLOAT
)
NOT FINAL
INSTANCE METHOD area()
    RETURNS FLOAT
    SPECIFIC circle_area
    NO SQL
    PARAMETER STYLE TD_GENERAL
    DETERMINISTIC
    LANGUAGE C;

-- 2. Implement the method (binds source to the type)
CREATE METHOD area()
    RETURNS FLOAT
    FOR production.circle_t
EXTERNAL NAME 'CS!circle_area!udt_src/circle.c!F!circle_area';

-- 3. Register cast to FLOAT (to extract the radius value)
CREATE CAST (production.circle_t AS FLOAT)
WITH SPECIFIC METHOD production.circle_to_float;

-- 4. Register ordering
CREATE ORDERING FOR production.circle_t
    ORDER FULL BY MAP
    WITH SPECIFIC METHOD production.circle_map;

-- 5. Register transform (for storage)
CREATE TRANSFORM FOR production.circle_t CIRCLE_XFORM (
    TO SQL   WITH SPECIFIC FUNCTION production.bytes_to_circle,
    FROM SQL WITH SPECIFIC METHOD  production.circle_to_bytes
);
```

---

## 10. Related DDL Views

| View | Purpose |
|------|---------|
| `DBC.TypesV` | All registered UDTs |
| `DBC.FunctionsV` | Methods, cast functions, comparison functions |
| `DBC.ColumnsV` | Find tables with UDT columns (check before DROP TYPE) |

---

*Reference: Teradata SQL External Routine Programming, v20.00 (B035-1147)*
