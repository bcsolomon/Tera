---
name: stored-procedure-c
description: 'Install, call, and remove C/C++ External Stored Procedures (CXSP) on Teradata. Use when writing a stored procedure in C or C++ that executes SQL via CLIv2, returns dynamic result sets, or performs procedural logic outside SQL SPL. Covers source authoring (PARAMETER STYLE TD_GENERAL and SQL, INOUT conventions), the EXTERNAL NAME format including the SP!CLI! package prefix required for CLIv2 procedures, REPLACE PROCEDURE, IN/OUT/INOUT parameter modes, SQL access clauses, the CLIv2 DBCAREA API (DBCHINI/DBCHCL, func DBFIRQ/DBFFET/DBFERQ), SP_return_result for dynamic result sets, and DROP PROCEDURE. Based on Teradata SQL External Routine Programming v20.00.'
when_to_use: 'Use when the user mentions CXSP, C external stored procedure, CREATE PROCEDURE LANGUAGE C, CLIv2 in a procedure, DBCAREA, DBCHINI, DBCHCL, SP_return_result, or wants to write procedural C code that executes SQL inside Teradata.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata C/C++ External Stored Procedure (CXSP)

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
> Use a SQL stored procedure (`stored-procedures`) or Java XSP (`stored-procedure-java`) as alternatives.

A CXSP is a C or C++ function registered as a `PROCEDURE`. It supports IN, OUT, and INOUT
parameters, can execute SQL via the CLI, and can return dynamic result sets to callers.

> **Not this skill:** For SQL stored procedures, see **stored-procedures**. For Java XSPs,
> see **stored-procedure-java**. For C scalar UDFs, see **scalar-udf-c**.

## When to Use

- Writing procedural C/C++ logic invoked via `CALL`
- Executing SQL from C/C++ code using CLIv2 (the DBCAREA API)
- Returning multiple dynamic result sets to a caller
- Accessing FNC_ API functions (session info, LOB, QueryBand, tracing)
- Replacing or updating an existing CXSP atomically

## Core Concepts

### EXTERNAL NAME: Source Spec and the CLIv2 Package Prefix

A CXSP that does **not** execute SQL uses the same source spec as a C UDF (the `!F!` component
is optional and defaults the entry point to the SQL procedure name):

```
CS!<name_on_server>!<source_path>[!F!<function_symbol>]
   ^^^^^^^^^^^^^^^^  ^^^^^^^^^^^   ^  ^^^^^^^^^^^^^^^^
   unique logical ID  .c path      |  C function entry point
                                   F = function entry-point flag (optional)
```

A CXSP that executes SQL with CLIv2 **must prefix the source spec with the `SP!CLI!`
package name** so the function is linked against the CLI-specific XSP library:

```
SP!CLI!CS!<name_on_server>!<source_path>[!F!<function_symbol>]
```

```sql
-- Executes SQL via CLIv2 -> requires the SP!CLI! prefix
EXTERNAL NAME 'SP!CLI!CS!ET001_xsp1!ET001_xsp.c';
```

All components are separated by the `!` delimiter.

### Parameter Modes

| Mode | DDL keyword | C behavior |
|------|-------------|------------|
| Input | `IN` | Read-only pointer |
| Output | `OUT` | Write-only pointer |
| Input + Output | `INOUT` | Single pointer. Read the value first, then write the output to the same pointer. |

### C Function Signature

**PARAMETER STYLE TD_GENERAL** (used in the Teradata doc examples) passes one pointer per
parameter plus `sqlstate`. NULLs are not represented, so it is the simplest style:

```c
#define SQL_TEXT Latin_Text
#include <sqltypes_td.h>
#include <string.h>

/* INOUT VARCHAR(64) -> one pointer, read then overwrite */
void xsp_getregion(VARCHAR_LATIN *region, char sqlstate[6])
{ ... }
```

**PARAMETER STYLE SQL** adds a null-indicator pointer per value parameter and trailing
metadata. Use it when the procedure must detect or emit SQL NULLs:

```c
void my_proc(
    INTEGER       *param1,       /* IN  */
    VARCHAR_LATIN *param2,       /* OUT */
    DECIMAL4      *param3,       /* INOUT */
    int           *param1_null,
    int           *param2_null,
    int           *param3_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257])
{ ... }
```

Under PARAMETER STYLE SQL, set each OUT/INOUT indicator to `-1` for NULL or `0` for not-NULL.

## Procedure: Write the C Source

### INOUT parameter pattern

An `INOUT` parameter maps to **one** pointer. Read input value first, then overwrite:

```c
void getregion(INTEGER *p_region, char sqlstate[6]) {
    int in_val  = *p_region;      /* read input */
    *p_region   = in_val + 100;   /* write output to same pointer */
}
```

### Signaling errors from a CXSP

```c
void my_proc(INTEGER *p1, char sqlstate[6], SQL_TEXT error_msg[257]) {
    if (*p1 < 0) {
        strcpy(sqlstate, "38U01");
        strcpy((char *)error_msg, "Input must be non-negative.");
        return;
    }
    /* normal logic */
}
```

## Procedure: Register the DDL

A procedure that does **not** execute SQL:

```sql
REPLACE PROCEDURE mydb.my_proc (
    IN  param1 INTEGER,
    OUT param2 VARCHAR(100)
)
LANGUAGE C                    -- or CPP for C++ source
NO SQL
PARAMETER STYLE TD_GENERAL    -- or SQL
EXTERNAL NAME 'CS!my_proc!xsp_src/my_proc.c!F!my_proc';

GRANT EXECUTE PROCEDURE ON mydb.my_proc TO app_role;
```

A procedure that executes SQL via CLIv2. Note the `SP!CLI!` prefix and a SQL-access clause
other than `NO SQL`:

```sql
REPLACE PROCEDURE mydb.lookup_region (
    IN  in_name VARCHAR(10),
    OUT out_id  VARCHAR(16000)
)
LANGUAGE C
READS SQL DATA
PARAMETER STYLE TD_GENERAL
DYNAMIC RESULT SETS 1         -- omit or set 0 when no result sets are returned
EXTERNAL NAME 'SP!CLI!CS!lookup_region!lookup_region.c';
```

**SQL access clauses:**

| Clause | Use when |
|--------|----------|
| `NO SQL` | Pure computation, no database access |
| `CONTAINS SQL` | SQL that doesn't read/write data |
| `READS SQL DATA` | SELECT inside the procedure |
| `MODIFIES SQL DATA` | INSERT/UPDATE/DELETE inside the procedure |

Use `REPLACE PROCEDURE` in almost all cases. It replaces atomically without a prior DROP.

## Procedure: Execute SQL from C (CLIv2)

A CXSP executes SQL by following standard CLIv2 programming practice against a `DBCAREA`
structure. There are **no** `Connection`/`Statement`/`ResultSet` classes. Include the CLIv2
headers after `sqltypes_td.h`, initialize a `DBCAREA` with `DBCHINI`, then submit requests
with `DBCHCL`. The procedure DDL must use the `SP!CLI!` EXTERNAL NAME prefix.

```c
#define SQL_TEXT Latin_Text
#include <sqltypes_td.h>
#include <string.h>
#include <stdio.h>
#include <coptypes.h>
#include <coperr.h>
#include <parcel.h>
#include <dbcarea.h>

void lookup_region(VARCHAR_LATIN *in_name, VARCHAR_LATIN *out_id, char sqlstate[6])
{
    DBCAREA dbcarea;
    Int32   result;
    char    cntxt[4];
    char    req[200];

    /* 1. Initialize the DBCAREA */
    dbcarea.total_len = sizeof(struct DBCAREA);
    DBCHINI(&result, cntxt, &dbcarea);

    /* 2. Build and initiate the request (DBFIRQ = Initiate Request) */
    sprintf(req, "SELECT region_id FROM regions WHERE name = '%s';", (char *)in_name);
    dbcarea.func        = DBFIRQ;
    dbcarea.req_ptr     = req;
    dbcarea.req_len     = strlen(req);
    dbcarea.change_opts = 'Y';
    DBCHCL(&result, cntxt, &dbcarea);

    /* 3. Fetch the response parcels (DBFFET), copy data to out_id ...        */
    /* 4. End the request (DBFERQ), then clean up the DBCAREA when finished.  */
}
```

Key `dbcarea.func` request codes: `DBFCON` (connect), `DBFIRQ` (initiate request),
`DBFFET` (fetch a parcel), `DBFERQ` (end request). Most other FNC library functions require
outstanding CLIv2 requests to complete first; only `FNC_malloc`/`FNC_free` are exempt.

### Returning dynamic result sets

A result set is the response to a single SELECT. Set two DBCAREA options on the request and
declare the count in DDL with `DYNAMIC RESULT SETS n`:

```c
sprintf(req, "SELECT * FROM inventory WHERE store_id = %d;", store);
dbcarea.func             = DBFIRQ;
dbcarea.req_ptr          = req;
dbcarea.req_len          = strlen(req);
dbcarea.change_opts      = 'Y';
dbcarea.SP_return_result = 3;     /* see table below */
dbcarea.keep_resp        = 'Y';   /* 'Y' = NO SCROLL rules, 'P' = SCROLL rules */
DBCHCL(&result, cntxt, &dbcarea);
```

| `SP_return_result` | Result set is returned to |
|--------------------|---------------------------|
| 2 | the client application |
| 3 | the caller of the external stored procedure |
| 4 | the client application and the procedure |
| 5 | the caller and the procedure |

To consume result sets created by a stored procedure that this XSP calls, set
`dbcarea.dynamic_result_sets_allowed = 'Y'` on the request containing the `CALL`.

## Procedure: Call and Verify

```sql
CALL mydb.my_proc(10, result_var);

HELP PROCEDURE mydb.my_proc;

SELECT ProcedureName, ExternalName, LanguageName
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND ProcedureName = 'my_proc';
```

## Procedure: Uninstall

```sql
-- Check for dependents first
SELECT ProcedureName, DatabaseName FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND ProcedureName = 'my_proc';

DROP PROCEDURE mydb.my_proc;
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| Procedure already exists | Use `REPLACE PROCEDURE`. No prior DROP is needed. |
| Procedure executes SQL | Prefix EXTERNAL NAME with `SP!CLI!`; use a SQL-access clause other than `NO SQL`; execute via CLIv2 (`DBCHINI`/`DBCHCL`). |
| INOUT in C | Single pointer serves as both read and write |
| C++ source | Wrap in `extern "C"`; catch all exceptions before the function exits |
| Returning result sets | `DYNAMIC RESULT SETS n`; set `SP_return_result` and `keep_resp` on the request |
| Calling another SP from C | Submit the `CALL` via CLIv2 with `dynamic_result_sets_allowed = 'Y'` to consume its result sets |
| FNC library functions with CLIv2 | Most require outstanding CLIv2 requests to finish first; only `FNC_malloc`/`FNC_free` are exempt |
| Linking a third-party library | Append a server library item and register its location: `SL!<name>` adds `-l<name>`; add the library directory to the `cufconfig` `USRLibraryPath`; stage the library on every node (and the `udfsectsk` container for protected mode). See [Linking an External Library](./references/linking-external-libraries.md). |
| Teradata-managed platform (VantageCloud Lake or Enterprise) | External routines are supported, but direct `EXTERNAL NAME` install may be blocked. On Lake, install/list/uninstall with the `tdextroutine` CLI. On Enterprise, install on Compute Engine nodes or via a service request (not the EDW node). Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`. |

## References


> **Access:** `skill_resource_read(action="read", skill="stored-procedure-c", path="references/FILENAME")` — do NOT call `list`.

- [External Stored Procedures](./references/external-stored-procedures.md): C func signature (TD_GENERAL and SQL styles), CLIv2 DBCAREA API (DBCHINI/DBCHCL, func DBFIRQ/DBFFET/DBFERQ), dynamic result sets (SP_return_result, keep_resp), FNC_ API (session info, LOB, tracing), CLIv2 install requirements (SP!CLI! prefix), C UDF vs CXSP comparison table
- [Linking an External Library](./references/linking-external-libraries.md): attaching a third-party library to an XSP (`SL`/`SP` EXTERNAL NAME items, `cufconfig` USRLibraryPath, combining with CLIv2, header paths, node staging, protected-mode container)
