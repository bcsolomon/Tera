---
name: table-function-udf-c
description: 'Create, register, and remove C/C++ table function User-Defined Functions on Teradata. Use when implementing a function that returns multiple rows (RETURNS TABLE) via C, such as CSV parsers, JSON row generators, or time-series expanders. Covers constant mode (TBL_MODE_CONST) vs variable mode (TBL_MODE_VARY), the phase model (TBL_PRE_INIT/TBL_INIT/TBL_BUILD/TBL_FINI/TBL_END/TBL_ABORT and TBL_BUILD_EOF), FNC_GetPhase/FNC_GetPhaseEx, signaling no-more-rows with sqlstate 02000, FNC_TblControl for the controlling copy, FNC_TblOptOut, FNC_TblAllocCtx/FNC_TblGetCtx, and TABLE() invocation syntax. Based on Teradata SQL External Routine Programming v20.00.'
when_to_use: 'Use when the user mentions C table UDF, table function in C, TBL_PRE_INIT, TBL_INIT, TBL_BUILD, TBL_FINI, TBL_END, TBL_ABORT, TBL_MODE_CONST, TBL_MODE_VARY, FNC_GetPhase, FNC_GetPhaseEx, FNC_TblControl, FNC_TblOptOut, FNC_TblAllocCtx, sqlstate 02000 for table rows, or wants to generate rows from a C function.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata C/C++ Table Function UDF

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

A table function UDF returns a **set of rows** rather than a scalar. The DDL uses
`RETURNS TABLE (col1 type, ...)`. The runtime calls the function repeatedly across phases;
the function builds one row per `TBL_BUILD` call by filling the output arguments, and signals
that it has no more rows by setting `sqlstate` to `"02000"`.

> **Not this skill:** For C scalar UDFs, see **scalar-udf-c**. For C aggregate UDFs, see
> **aggregate-udf-c**. For table operators (different DDL and invocation), see
> **table-operator-udf-c**. For Java table functions, see **table-function-udf-java**.

## When to Use

- Parsing structured data (CSV, delimited strings, encoded blobs) and returning rows
- Expanding a single row into multiple rows (time-series, repeated measures, etc.)
- Implementing external data generators or iterators in C
- Any pattern where a C function must emit a variable number of result rows

## Core Concepts

### Two Modes

`FNC_GetPhase` returns the **mode**, which depends on how the function was invoked:

- **`TBL_MODE_CONST`** (constant mode): invoked with constant-expression arguments, for example
  `TABLE (mydb.split_csv('a,b,c'))`. One copy may become the **controlling copy** via
  `FNC_TblControl`. Phase flow: `TBL_PRE_INIT` -> `TBL_INIT` -> `TBL_BUILD` -> `TBL_END`
  (no `TBL_FINI`).
- **`TBL_MODE_VARY`** (variable mode): invoked with column (per-row) arguments, for example
  `TABLE (mydb.split_csv(t.csv_column))`. Adds a `TBL_FINI` phase and can loop back to
  `TBL_INIT` for the next input row. Phase flow: `TBL_PRE_INIT` -> `TBL_INIT` -> `TBL_BUILD`
  -> `TBL_FINI` -> (back to `TBL_INIT` if more input, else `TBL_END`).

### Phase Model

The runtime calls the C function repeatedly; obtain the mode and phase with
`FNC_GetPhase(&phase)`. `FNC_Phase` is an enum:

| Phase | Constant | Value | Purpose |
|-------|----------|-------|---------|
| Pre-init | `TBL_PRE_INIT` | 20 | First call. Establish global context; cannot build rows. In constant mode, optionally call `FNC_TblControl()` to become the controlling copy. |
| Init | `TBL_INIT` | 21 | Open external connections (files, sockets). Cannot build rows. In constant mode, a copy may call `FNC_TblOptOut()` to stop participating. |
| Build | `TBL_BUILD` | 22 | Fill the output arguments to build **one** row, then return (the runtime stays in `TBL_BUILD` for the next row). Set `sqlstate` to `"02000"` to signal no more rows. |
| Finalize | `TBL_FINI` | 23 | **Variable mode only.** Close connections opened in `TBL_INIT`. If more input rows remain, the runtime returns to `TBL_INIT`; otherwise it goes to `TBL_END`. |
| End | `TBL_END` | 24 | Close all external connections and release allocated memory. Not called again. |
| Abort | `TBL_ABORT` | 25 | Entered **only** when the function calls `FNC_TblAbort`. Close connections and release memory. |

`FNC_GetPhaseEx` adds `TBL_BUILD_EOF` (26) and the `TBL_NEWROW`/`TBL_NEWROWEOF`/`TBL_LASTROW`
options for functions that must know when the last qualifying row on an AMP arrives.

### Key FNC Functions

| Function | Purpose |
|----------|---------|
| `FNC_GetPhase(&phase)` | Returns the **mode** (`TBL_MODE_CONST` or `TBL_MODE_VARY`) and writes the current phase to the `FNC_Phase` pointer. |
| `FNC_GetPhaseEx(&phase, options)` | Like `FNC_GetPhase`, but adds `TBL_BUILD_EOF` and last-row awareness. |
| `FNC_TblControl(void)` | Constant mode, `TBL_PRE_INIT` only. Returns `1` if this copy becomes the controlling copy, else `0`. **Not** a row-count or more-rows signal. Can be called only once. |
| `FNC_TblOptOut()` | Constant mode, `TBL_INIT`. This copy stops participating (produces no rows on this AMP). |
| `FNC_TblAllocCtx(size)` / `FNC_TblGetCtx()` | Allocate / retrieve the per-copy scratchpad context that persists across phases. |
| `FNC_TblAllocCtrlCtx(size)` / `FNC_TblGetCtrlCtx()` | Allocate / retrieve the control scratchpad that the controlling copy uses to distribute data to other copies. |
| `FNC_TblAbort()` | Force entry into the `TBL_ABORT` phase. |

## Procedure: Write the C Source

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"
#include <string.h>

typedef struct {
    char   data[10000];   /* copy of input */
    char  *pos;           /* current parse position */
} TableCtx;

void split_csv(
    VARCHAR_LATIN *csv_input,
    VARCHAR_LATIN *col_value,       /* output column */
    int           *csv_input_null,
    int           *col_value_null,
    char           sqlstate[6],
    SQL_TEXT       func_name[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_message[257])
{
    TableCtx  *ctx;
    char      *delim;
    FNC_Phase  phase;
    FNC_Mode   mode;

    mode = FNC_GetPhase(&phase);

    switch (phase)
    {
        case TBL_PRE_INIT:
            /* Establish global context. Cannot build rows yet. */
            FNC_TblAllocCtx(sizeof(TableCtx));
            break;

        case TBL_INIT:
            /* Open external resources here. Cannot build rows yet. */
            ctx = (TableCtx *)FNC_TblGetCtx();
            if (*csv_input_null == -1) {
                if (mode == TBL_MODE_CONST)
                    FNC_TblOptOut();            /* this copy produces no rows */
                ctx->pos = NULL;
                break;
            }
            strncpy(ctx->data, (const char *)csv_input, sizeof(ctx->data) - 1);
            ctx->data[sizeof(ctx->data) - 1] = '\0';
            ctx->pos = ctx->data;
            break;

        case TBL_BUILD:
            ctx = (TableCtx *)FNC_TblGetCtx();
            if (ctx->pos == NULL || *ctx->pos == '\0') {
                strcpy(sqlstate, "02000");      /* no more rows: advance phase */
                break;
            }
            delim = strchr(ctx->pos, ',');
            if (delim != NULL) {
                *delim = '\0';
                strncpy((char *)col_value, ctx->pos, 1000);
                ctx->pos = delim + 1;
            } else {
                strncpy((char *)col_value, ctx->pos, 1000);
                ctx->pos = NULL;
            }
            *col_value_null = 0;                /* one row built; stays in TBL_BUILD */
            break;

        case TBL_FINI:
            /* Variable mode only: close per-input-row resources. The runtime
               returns to TBL_INIT if more input rows remain. */
            break;

        case TBL_END:
        case TBL_ABORT:
            /* Close external connections and release any memory you allocated.
               (The FNC_TblAllocCtx scratchpad is reclaimed by the runtime.) */
            break;
    }
}
```

**Key rules:**
- Use `FNC_GetPhase(&phase)` to retrieve the phase; its return value is the **mode**
  (`TBL_MODE_CONST` / `TBL_MODE_VARY`). Table UDFs do **not** receive a phase parameter.
- Build exactly **one** row per `TBL_BUILD` call by filling the output arguments and setting
  their null indicators (`0` = not NULL, `-1` = NULL); the runtime calls `TBL_BUILD` again for
  the next row. Set `sqlstate` to `"02000"` to signal there are no more rows.
- `FNC_TblControl()` designates the **controlling copy** (constant mode, `TBL_PRE_INIT` only);
  it is not a more-rows signal.
- `FNC_TblOptOut()` (constant mode, `TBL_INIT`) makes this copy produce no rows on its AMP.
- `TBL_FINI` exists in **variable mode only**. `TBL_END` and `TBL_ABORT` must close external
  connections and free resources; cleanup is **not** automatic.

## Procedure: Register the DDL

```sql
REPLACE FUNCTION mydb.split_csv (csv_input VARCHAR(10000))
RETURNS TABLE (col_value VARCHAR(1000))
SPECIFIC split_csv_varchar_impl
LANGUAGE C
NO SQL
NOT DETERMINISTIC
EXTERNAL NAME 'CS!split_csv!udf_src/split_csv.c'
PARAMETER STYLE SQL;

GRANT EXECUTE FUNCTION ON mydb.split_csv TO app_role;
```

## Procedure: Call the Table Function

```sql
-- Lateral join to expand rows
SELECT s.col_value
FROM TABLE (mydb.split_csv('apple,banana,cherry')) AS s;

-- Join with a base table
SELECT t.id, s.col_value
FROM source_table t,
     TABLE (mydb.split_csv(t.csv_column)) AS s;
```

## Procedure: Verify and Uninstall

```sql
-- Verify
SELECT FunctionName, ExternalName, FunctionType
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND FunctionName = 'split_csv';

-- Check for dependent objects before dropping
SELECT * FROM DBC.FunctionXRefsV
WHERE UDFDatabase = 'mydb' AND UDFName = 'split_csv';

-- Drop one overload
DROP SPECIFIC FUNCTION mydb.split_csv_varchar_impl;
-- OR drop all overloads
DROP FUNCTION mydb.split_csv;
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| NULL input | Detect in `TBL_INIT` with the null indicator; in constant mode call `FNC_TblOptOut()` |
| No rows produced | Set `sqlstate` to `"02000"` on the first `TBL_BUILD` call without filling outputs |
| End of rows | Set `sqlstate` to `"02000"` in `TBL_BUILD` (not `FNC_TblControl`) |
| Buffer overflow on output | Validate length before `strncpy` into output VARCHAR |
| Multi-input (variable mode) | After `TBL_FINI`, the runtime returns to `TBL_INIT` for the next input row; reset context |
| Need controlling copy | Call `FNC_TblControl()` in `TBL_PRE_INIT` (constant mode); distribute data via `FNC_TblAllocCtrlCtx` |
| Cleanup | Close connections and free memory in `TBL_END` (and `TBL_ABORT`); it is not automatic |
| C++ source | Wrap in `extern "C"`; catch all exceptions before returning |
| Teradata-managed platform (VantageCloud Lake or Enterprise) | External routines are supported, but direct `EXTERNAL NAME` install may be blocked. On Lake, install/list/uninstall with the `tdextroutine` CLI. On Enterprise, install on Compute Engine nodes or via a service request (not the EDW node). Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`. |

## References


> **Access:** `skill_resource_read(action="read", skill="table-function-udf-c", path="references/FILENAME")` — do NOT call `list`.

- [External UDFs](./references/external-udfs.md): full C/C++/Java development guide, table function section, privilege matrix, troubleshooting
- [FNC API Reference](./references/fnc-api-reference.md): FNC_TblControl, FNC_TblOptOut, FNC_TblAllocCtx, FNC_TblGetCtx, FNC_GetPhase signatures; memory, LOB, UDT, QueryBand functions
