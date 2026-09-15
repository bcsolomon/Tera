---
name: aggregate-udf-c
description: 'Create, register, and remove C/C++ aggregate User-Defined Functions on Teradata. Use when implementing a custom aggregation (like SUM, AVG, or statistical aggregates) in C that operates on groups of rows across AMPs. Covers the 5-phase model (AGR_INIT/AGR_DETAIL/AGR_COMBINE/AGR_FINAL/AGR_NODATA), FNC_Phase parameter, FNC_Context_t state block, FNC_DefMem for intermediate storage allocation, CLASS AGGREGATE DDL with optional interim_size, and teardown. Based on Teradata SQL External Routine Programming v20.00.'
when_to_use: 'Use when the user mentions C aggregate UDF, custom aggregation in C, AGR_INIT, AGR_DETAIL, AGR_COMBINE, AGR_FINAL, AGR_NODATA, FNC_Phase, FNC_Context_t, FNC_DefMem, CLASS AGGREGATE, or wants to implement GROUP BY aggregation logic in C.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata C/C++ Aggregate UDF

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

An aggregate UDF receives a `FNC_Phase phase` as its first parameter and a
`FNC_Context_t *fctx` state block as its second. Vantage invokes the function once for each
item in a group, passing a phase indicator each time (so the function runs many times per
group, including once per detail row during `AGR_DETAIL`). It uses `FNC_DefMem` to allocate
the intermediate storage that persists across phases.

> **Not this skill:** For C scalar UDFs, see **scalar-udf-c**. For C table functions, see
> **table-function-udf-c**. For Java aggregate UDFs, see **aggregate-udf-java**.

## When to Use

- Implementing custom aggregations (running sum, custom avg, median, percentile, etc.)
- Writing aggregations that must execute in parallel across AMPs and then combine partial results
- Any GROUP BY operation that cannot be expressed with built-in Teradata aggregate functions

## Core Concepts

### 5-Phase Model

Aggregate UDFs are implemented as a **single C function** called once per phase:

| Phase | Constant | Value | Purpose |
|-------|----------|-------|---------|
| Initialize | `AGR_INIT` | 1 | Allocate intermediate storage via `FNC_DefMem`, assign the returned pointer to `fctx->interim1`, set `fctx->interim2` to NULL, initialize the state, then **process the first detail row** (idiomatically by falling through to `AGR_DETAIL`) |
| Detail | `AGR_DETAIL` | 2 | Process each subsequent input row; accumulate into `fctx->interim1`; skip NULL inputs |
| Combine | `AGR_COMBINE` | 3 | Merge AMP partial result (`fctx->interim2`) into local state (`fctx->interim1`) |
| Final | `AGR_FINAL` | 4 | Compute and write the final result from `fctx->interim1` |
| No data | `AGR_NODATA` | 5 | Presented only when there is no data at all to aggregate. Set result to NULL or a default. |

`AGR_COMBINE` is critical for Teradata's parallel architecture. Partial AMP aggregates must be mergeable into a single result.

### Context Block

```c
typedef struct FNC_Context_t {
    int   version;
    void *interim1;       /* primary accumulator (allocated in AGR_INIT) */
    int   intrm1_length;
    void *interim2;       /* partial AMP state provided by runtime in AGR_COMBINE */
    int   intrm2_length;
    long  group_count;
    /* ... additional fields */
} FNC_Context_t;
```

## Procedure: Write the C Source

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"

typedef struct {
    double sum;
    int    count;
} AggState;

void custom_avg(
    FNC_Phase   phase,          /* phase: always the FIRST parameter */
    FNC_Context_t *fctx,           /* state block: always the SECOND parameter */
    FLOAT         *input_val,
    FLOAT         *result,
    int           *input_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       func_name[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_message[257])
{
    AggState *state = (AggState *)fctx->interim1;

    switch (phase) {
        case AGR_INIT:
            /* FNC_DefMem allocates the intermediate storage and RETURNS a pointer
               to it. You must assign that pointer to fctx->interim1 yourself, and
               set fctx->interim2 to NULL (it is supplied by the runtime in COMBINE).
               After initializing, fall through to AGR_DETAIL to process the FIRST row. */
            state = (AggState *)FNC_DefMem(sizeof(AggState));
            if (state == NULL) {
                strcpy(sqlstate, "U0001");   /* allocation failed */
                return;
            }
            fctx->interim1 = state;
            fctx->interim2 = NULL;
            state->sum   = 0.0;
            state->count = 0;
            /* fall through */

        case AGR_DETAIL:
            if (*input_null != -1) {    /* skip NULLs */
                state->sum += *input_val;
                state->count++;
            }
            break;

        case AGR_COMBINE:
            {
                AggState *partial = (AggState *)fctx->interim2;
                state->sum   += partial->sum;
                state->count += partial->count;
            }
            break;

        case AGR_FINAL:
            if (state->count == 0) {
                *result_null = -1;
            } else {
                *result      = state->sum / state->count;
                *result_null = 0;
            }
            break;

        case AGR_NODATA:
            *result_null = -1;          /* no qualifying rows: return NULL */
            break;
    }
}
```

**Key rules:**
- `FNC_DefMem` is the **only valid allocator** for intermediate storage. Never use `malloc`. It allocates the area and **returns a pointer**; in `AGR_INIT` you assign that pointer to `fctx->interim1` and set `fctx->interim2` to NULL.
- `phase` is always the **first parameter**, `fctx` is always the **second**.
- `AGR_INIT` must allocate, initialize, **and process the first detail row**. The idiomatic way is to let `AGR_INIT` fall through into `AGR_DETAIL` (its input arguments hold the first row of the group).
- Always handle `AGR_NODATA`. It is presented only when there is no data at all to aggregate.
- Always handle `AGR_COMBINE`. Partial AMP results must be mergeable.

## Procedure: Register the DDL

```sql
REPLACE FUNCTION mydb.custom_avg (input_val FLOAT)
RETURNS FLOAT
SPECIFIC custom_avg_float_impl
LANGUAGE C
NO SQL
DETERMINISTIC
CLASS AGGREGATE
EXTERNAL NAME 'CS!custom_avg!udf_src/custom_avg.c'
PARAMETER STYLE SQL;

GRANT EXECUTE FUNCTION ON mydb.custom_avg TO app_role;
```

The `CLASS AGGREGATE` clause tells Teradata to call the function with `FNC_Phase` and `FNC_Context_t`. Add an optional interim size, for example `CLASS AGGREGATE (256)`, when the intermediate storage exceeds the 64-byte default (max 64,000 bytes).

## Procedure: Test and Verify

```sql
SELECT mydb.custom_avg(salary)  FROM employees GROUP BY department_id;

SELECT FunctionName, ExternalName, FunctionType
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND FunctionName = 'custom_avg';
```

## Procedure: Uninstall

```sql
SELECT * FROM DBC.FunctionXRefsV
WHERE UDFDatabase = 'mydb' AND UDFName = 'custom_avg';

DROP SPECIFIC FUNCTION mydb.custom_avg_float_impl;  -- drop one overload
-- OR: DROP FUNCTION mydb.custom_avg;               -- drop all overloads
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| No data to aggregate | Handle `AGR_NODATA`. Set `*result_null = -1`. |
| NULL input rows | Skip in `AGR_DETAIL` by checking `*input_null == -1` |
| Multi-AMP partial merge | `AGR_COMBINE` is mandatory. Missing it corrupts results on multi-AMP systems. |
| `malloc` instead of `FNC_DefMem` | Memory is not freed between phases. Use only `FNC_DefMem` for accumulator state. |
| C++ source | Wrap in `extern "C"`; catch all exceptions before function exits |
| Teradata-managed platform (VantageCloud Lake or Enterprise) | External routines are supported, but direct `EXTERNAL NAME` install may be blocked. On Lake, install/list/uninstall with the `tdextroutine` CLI. On Enterprise, install on Compute Engine nodes or via a service request (not the EDW node). Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`. |

## References


> **Access:** `skill_resource_read(action="read", skill="aggregate-udf-c", path="references/FILENAME")` — do NOT call `list`.

- [Aggregate UDFs](./references/aggregate-udfs.md): full 5-phase implementation guide, FNC_Context_t structure, AGR_MOVINGTRAIL for moving windows, complete worked examples
- [FNC API Reference](./references/fnc-api-reference.md): FNC_DefMem, FNC_malloc/free, session info, LOB, tracing, QueryBand, UDT functions
