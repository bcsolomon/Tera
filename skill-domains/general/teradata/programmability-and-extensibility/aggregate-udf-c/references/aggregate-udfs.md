# Aggregate UDFs on Teradata

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** Aggregate UDFs on Teradata

## Overview

Aggregate UDFs extend Teradata's built-in aggregation functions (SUM, AVG, COUNT, etc.) with custom logic. They are implemented as external functions in C or C++ and operate on groups of rows, producing a single result per group. Teradata's parallel architecture (multiple AMPs) means the aggregate function must support a **combine phase** to merge partial results.

## Architecture

Aggregate UDFs are implemented as a **single C function** that Vantage invokes once for each item in an aggregation group, passing a phase indicator each time. The phase is passed as `FNC_Phase phase` (the first parameter) — not retrieved via `FNC_GetPhase()`, which is a table UDF API. State is carried across phases through `FNC_Context_t *fctx`.

| Phase Constant | Value | Purpose |
|----------------|-------|---------|
| `AGR_INIT` | 1 | Allocate the intermediate storage with `FNC_DefMem`, assign the returned pointer to `fctx->interim1`, set `fctx->interim2` to NULL, initialize the state, then process the first detail row (idiomatically by falling through to `AGR_DETAIL`) |
| `AGR_DETAIL` | 2 | Process each subsequent input row; accumulate into `fctx->interim1`; skip NULL inputs |
| `AGR_COMBINE` | 3 | Merge partial AMP result (`fctx->interim2`) into local state (`fctx->interim1`) |
| `AGR_FINAL` | 4 | Compute and return the final result from `fctx->interim1` |
| `AGR_NODATA` | 5 | Presented only when there is no data at all to aggregate; set result to NULL or a default |

`AGR_MOVINGTRAIL` (value 6) is used only for moving-window aggregate extensions.

### Context Block (`FNC_Context_t`)

```c
typedef struct FNC_Context_t {
    int   version;
    FNC_flags_t flags;
    void *interim1;       /* primary state pointer (allocated and assigned in AGR_INIT) */
    int   intrm1_length;  /* size of interim1 area */
    void *interim2;       /* secondary partial state (populated by runtime in AGR_COMBINE) */
    int   intrm2_length;
    long  group_count;
    long  window_size;
    long  pre_window;
    long  post_window;
} FNC_Context_t;
```

## SQL Registration Syntax

```sql
REPLACE FUNCTION database_name.custom_avg (
    input_val FLOAT
)
RETURNS FLOAT
LANGUAGE C
NO SQL
DETERMINISTIC
CLASS AGGREGATE
EXTERNAL NAME 'CS!custom_avg!udf_src/custom_avg.c'
PARAMETER STYLE SQL;
```

### External Name Format

```
CS!<name_on_server>!<source_path>           -- source file delivered from client (DB compiles)
CO!<name_on_server>!<object_path.o>!F!<fn>  -- pre-compiled .o object from client
SP!<package_path.so>                        -- .so package pre-distributed to all server nodes
SP!<package_path.so>!F!<fn>                 -- package + explicit entry point override
```

- `CS!` — client source file; the database compiles it at installation (`CREATE`/`REPLACE FUNCTION`) time
- `CO!` — client `.o` relocatable object; database links it server-side
- `SP!` — server-side `.so` package that must already be distributed to **all nodes** before the DDL runs; distribute via `CALL SYSLIB.installsp(...)`, PCL, or FTP; cannot combine with other file clauses but can combine with `F!`
- `name_on_server` — the unique logical identifier for the installed file in the DB catalog
- `F!func_name` — overrides the C function entry point symbol (defaults to the SQL function name)
- `CLASS AGGREGATE` clause in DDL tells Teradata to call the function with `FNC_Phase phase` and `FNC_Context_t *fctx`

## C Implementation Pattern

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"

typedef struct {
    double sum;
    int    count;
} AggState;

void custom_avg(
    FNC_Phase   phase,          /* runtime-provided phase — first parameter */
    FNC_Context_t *fctx,           /* context block — carry state across phases */
    FLOAT         *input_val,      /* input argument */
    FLOAT         *result,         /* output result */
    int           *input_null,     /* null indicator for input (-1 = NULL) */
    int           *result_null,    /* null indicator for result (-1 = NULL) */
    char           sqlstate[6],
    SQL_TEXT       func_name[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_message[257])
{
    AggState *state = (AggState *) fctx->interim1;

    switch (phase)
    {
        case AGR_INIT:
            /* FNC_DefMem allocates the intermediate storage and RETURNS a pointer.
               Assign it to fctx->interim1 yourself and set fctx->interim2 to NULL
               (the runtime supplies interim2 in AGR_COMBINE). Then fall through to
               AGR_DETAIL to process the FIRST detail row of the group. */
            state = (AggState *) FNC_DefMem(sizeof(AggState));
            if (state == NULL) {
                strcpy(sqlstate, "U0001");
                return;
            }
            fctx->interim1 = state;
            fctx->interim2 = NULL;
            state->sum   = 0.0;
            state->count = 0;
            /* fall through */

        case AGR_DETAIL:
            /* Accumulate one row (skip NULLs) */
            if (*input_null != -1) {
                state->sum += *input_val;
                state->count++;
            }
            break;

        case AGR_COMBINE:
            /* Merge partial result from another AMP (runtime provides it in fctx->interim2) */
            {
                AggState *other = (AggState *) fctx->interim2;
                state->sum   += other->sum;
                state->count += other->count;
            }
            break;

        case AGR_FINAL:
            /* Compute and return result */
            if (state->count == 0) {
                *result_null = -1;
            } else {
                *result      = (FLOAT)(state->sum / state->count);
                *result_null = 0;
            }
            break;

        case AGR_NODATA:
            /* The aggregate set is empty (no rows to aggregate) */
            *result_null = -1;
            break;
    }
}
```

## Installation Steps

```sql
-- 1. Register (and compile) the aggregate function
--    The database compiles udf_src/custom_avg.c at CREATE/REPLACE FUNCTION time,
--    then links and distributes the object to all nodes.
REPLACE FUNCTION mydb.custom_avg (input_val FLOAT)
RETURNS FLOAT
LANGUAGE C
NO SQL
DETERMINISTIC
CLASS AGGREGATE
EXTERNAL NAME 'CS!custom_avg!udf_src/custom_avg.c'
PARAMETER STYLE SQL;

-- 2. Grant access
GRANT EXECUTE FUNCTION ON mydb.custom_avg TO public;
```

## Usage

```sql
-- Like any built-in aggregate
SELECT department, mydb.custom_avg(salary) AS avg_salary
FROM employees
GROUP BY department;

-- With HAVING
SELECT department, mydb.custom_avg(salary) AS avg_salary
FROM employees
GROUP BY department
HAVING mydb.custom_avg(salary) > 50000;
```

## Important Notes

- `FNC_Phase` is `typedef BYTE` — the phase is passed **by value** as the first argument (NOT via `FNC_GetPhase()`, which is the table UDF API).
- `FNC_DefMem` is the **only valid allocator** for aggregate state in `AGR_INIT`; memory is freed automatically by the runtime.
- The `AGR_COMBINE` phase is critical for correctness: Teradata distributes rows across AMPs in parallel, and partial results must be mergeable.
- Always handle `AGR_NODATA` — it is presented only when there is no data at all to aggregate (the aggregate set is empty).
- Keep the `AggState` struct small; the structure must serialize correctly across AMP boundaries for the combine phase.
- Test with multi-AMP data distribution (hash-distributed tables) to verify `AGR_COMBINE` correctness.
- Verify with `DBC.FunctionsV` after registration:

```sql
SELECT FunctionName, FunctionType, ExternalName
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND FunctionName = 'custom_avg';
```

