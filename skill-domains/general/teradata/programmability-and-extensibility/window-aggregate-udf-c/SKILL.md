---
name: window-aggregate-udf-c
description: 'Create, register, and remove C/C++ window aggregate User-Defined Functions on Teradata. Use when an aggregate UDF written in C must also work under an OLAP window specification (OVER (PARTITION BY ... ORDER BY ... ROWS ...)) such as moving, cumulative, or reporting windows. Covers the window phase model (AGR_INIT/AGR_DETAIL/AGR_MOVINGTRAIL/AGR_FINAL/AGR_NODATA, with AGR_COMBINE not used), the FNC_Context_t window fields (window_size, pre_window, post_window), maintaining a row cache sized to the window, supported and unsupported window types, CLASS AGGREGATE DDL, and OVER() invocation. Based on Teradata SQL External Routine Programming v20.00.'
when_to_use: 'Use when the user mentions C window aggregate UDF, OLAP aggregate in C, AGR_MOVINGTRAIL, window_size, pre_window, post_window, moving/cumulative/reporting window UDF, an aggregate UDF invoked with OVER(), or a custom aggregate in C that maintains a sliding window of rows.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata C/C++ Window Aggregate UDF

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

A window aggregate UDF is an aggregate UDF (`CLASS AGGREGATE`) that is also valid under an
OLAP window specification, that is, when invoked with an `OVER (PARTITION BY ... ORDER BY ...
ROWS ...)` clause. It uses the same `FNC_Phase phase` / `FNC_Context_t *fctx` calling
convention as a plain aggregate UDF, but the runtime drives a different set of phases and
populates window sizing fields in the context block.

> **Not this skill:** For a plain `GROUP BY` aggregate in C, see **aggregate-udf-c**. For
> Java window aggregates, see **window-aggregate-udf-java**. For C scalar UDFs, see
> **scalar-udf-c**.

## When to Use

- A custom aggregate in C that callers invoke with `OVER (...)` (moving averages, running
  totals, ranking-style logic, sliding-window statistics)
- Aggregations whose result depends on a sliding window of ordered rows within a partition
- Extending an existing C aggregate UDF so it behaves correctly under window semantics

## Core Concepts

### Window Phase Model

The function is a **single C function** called once per phase. Window aggregation uses a
different phase set than `GROUP BY` aggregation: there is **no `AGR_COMBINE`**, and moving
windows add **`AGR_MOVINGTRAIL`**.

| Phase | Constant | Value | Purpose |
|-------|----------|-------|---------|
| Initialize | `AGR_INIT` | 1 | Triggered once per partition at the start of a new group. Allocate and initialize intermediate storage via `FNC_DefMem`, save the first row's values, then fall through to `AGR_DETAIL`. |
| Detail | `AGR_DETAIL` | 2 | Triggered each time the forward row progresses (once per row to aggregate). Accumulate the input into intermediate storage and into the window row cache. |
| Combine | `AGR_COMBINE` | 3 | **Not used** by window aggregates. Include a case that raises an error if it is ever reached. |
| Moving trail | `AGR_MOVINGTRAIL` | 6 | **Moving window only.** Triggered by the trailing rows when the forward pointer reaches the end of the partition. No new values are supplied; adjust counts and offsets as the window shrinks toward the partition end. |
| Final | `AGR_FINAL` | 4 | Produce the final result for the current window position. Invoked when the result must be moved into the result row. |
| No data | `AGR_NODATA` | 5 | Presented only when there is no data at all to aggregate. Return NULL or a default. |

Vantage handles the `PRECEDING`/`FOLLOWING`/`CURRENT ROW` bookkeeping. Your function only
maintains a cache of rows sized to the window and implements the function semantics over that
cache.

### Window Fields in FNC_Context_t

Vantage sets these fields before invoking the function:

| Field | Meaning |
|-------|---------|
| `window_size` | `-1` for a cumulative window, `-2` for a reporting window, and `post_window - pre_window + 1` for a moving window (the `+1` is the current row). |
| `pre_window` | From the `PRECEDING` clause. Negative for a row that precedes the current row. Zero for cumulative and reporting windows. |
| `post_window` | From the `FOLLOWING` clause. Positive for a row that follows the current row. Zero for cumulative and reporting windows. |

`interim1` / `intrm1_length` carry the intermediate storage, exactly as for plain aggregates.

### Supported and Unsupported Window Types

| Window type | Aggregation group | Partitioning |
|-------------|-------------------|--------------|
| Reporting | `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING` | Hash only |
| Cumulative | `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`, or `CURRENT ROW AND UNBOUNDED FOLLOWING` | Hash only |
| Moving | `value PRECEDING AND CURRENT ROW`; `CURRENT ROW AND value FOLLOWING`; `value PRECEDING AND value FOLLOWING`; `value PRECEDING AND value PRECEDING`; `value FOLLOWING AND value FOLLOWING` | Hash and range |

Not supported: `ROWS BETWEEN UNBOUNDED PRECEDING AND value FOLLOWING` and
`ROWS BETWEEN value PRECEDING AND UNBOUNDED FOLLOWING`. Vantage does not verify that a UDF is
used with a particular window type, so consider validating `window_size` inside the function.

## Procedure: Write the C Source

This cumulative-window `dense_rank` example uses PARAMETER STYLE SQL (value pointers, null
indicators, trailing metadata). The first two parameters are always `FNC_Phase` and
`FNC_Context_t *`.

```c
#define SQL_TEXT Latin_Text
#include <sqltypes_td.h>
#include <stdio.h>
#include <string.h>

typedef struct agr_storage {
    int cr;    /* current rank  */
    int pv;    /* previous value */
} AGR_Storage;

void dense_rank( FNC_Phase       phase,
                 FNC_Context_t  *fctx,
                 INTEGER        *x,
                 INTEGER        *result,
                 int            *x_i,
                 int            *result_i,
                 char            sqlstate[6],
                 SQL_TEXT        fncname[129],
                 SQL_TEXT        sfncname[129],
                 SQL_TEXT        error_message[257] )
{
    AGR_Storage *s1 = fctx->interim1;

    switch (phase) {
        case AGR_INIT:
            /* This UDF supports only the cumulative window type. */
            if (fctx->window_size != -1) {
                strcpy((char *)error_message, "Only cumulative window type supported");
                strcpy(sqlstate, "U0001");
                return;
            }
            if ((s1 = FNC_DefMem(sizeof(AGR_Storage))) == NULL) {
                strcpy(sqlstate, "U0002");
                return;
            }
            fctx->interim1 = s1;
            s1->cr = 1;
            s1->pv = *x;
            /* fall through to AGR_DETAIL to process the first row */

        case AGR_DETAIL:
            if (*x != s1->pv) {
                s1->cr++;
                s1->pv = *x;
            }
            break;

        case AGR_FINAL:
            *result = s1->cr;
            break;

        /* Window aggregates never receive AGR_COMBINE; AGR_MOVINGTRAIL is for
           moving windows only. Raise an error for any unexpected phase. */
        case AGR_COMBINE:
        case AGR_MOVINGTRAIL:
        default:
            sprintf((char *)error_message, "phase is %d", phase);
            strcpy(sqlstate, "U0005");
            return;
    }
}
```

For a **moving** window, also implement `AGR_MOVINGTRAIL`: maintain a ring buffer of the last
`window_size` rows, subtract the trailing row's contribution when the window slides past it,
and in `AGR_MOVINGTRAIL` keep subtracting trailing contributions as the window diminishes near
the partition end.

**Key rules:**
- `phase` is always the **first** parameter, `fctx` the **second**.
- `FNC_DefMem` is the only valid allocator for intermediate storage; assign its return to
  `fctx->interim1` in `AGR_INIT`. Never use `malloc`.
- `AGR_INIT` runs once per partition: allocate, initialize, save the first row, then fall
  through to `AGR_DETAIL`.
- Do **not** implement combine logic. Treat `AGR_COMBINE` as an error.
- Implement `AGR_MOVINGTRAIL` only for moving windows; it supplies no new row values.
- Read `fctx->window_size` (and `pre_window`/`post_window` for moving windows) to size the row
  cache and to validate the window type.

## Procedure: Register the DDL

A window aggregate UDF is registered exactly like a plain aggregate UDF, with `CLASS AGGREGATE`.
The window behavior comes from how callers invoke it, not from a separate class.

```sql
REPLACE FUNCTION mydb.dense_rank (x INTEGER)
RETURNS INTEGER
CLASS AGGREGATE (1000)
LANGUAGE C
NO SQL
PARAMETER STYLE SQL
DETERMINISTIC
CALLED ON NULL INPUT
EXTERNAL NAME 'CS!dense_rank!udf_src/dense_rank.c';

GRANT EXECUTE FUNCTION ON mydb.dense_rank TO app_role;
```

Add an interim size, for example `CLASS AGGREGATE (1000)`, when the row cache plus accumulators
exceed the 64-byte default (max 64,000 bytes). Choose a `RETURNS` type wide enough for the
largest allowable window to avoid overflow.

## Procedure: Invoke With a Window

```sql
-- Cumulative window
SELECT item, mydb.dense_rank(value) OVER (
           PARTITION BY grp ORDER BY value
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
FROM measurements;

-- Moving window (3-row trailing average style aggregate)
SELECT item, mydb.my_moving_sum(value) OVER (
           PARTITION BY grp ORDER BY ts
           ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
FROM measurements;
```

## Procedure: Verify and Uninstall

```sql
SELECT FunctionName, ExternalName, FunctionType
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND FunctionName = 'dense_rank';

DROP FUNCTION mydb.dense_rank;
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| `AGR_COMBINE` reached | Window aggregates never combine. Set an SQLSTATE and return an error. |
| Moving window | Implement `AGR_MOVINGTRAIL`; maintain a ring buffer of `window_size` rows. |
| Cumulative or reporting window | `window_size` is `-1` or `-2`; `pre_window`/`post_window` are zero; no `AGR_MOVINGTRAIL`. |
| Unsupported window type | `UNBOUNDED PRECEDING AND value FOLLOWING` and `value PRECEDING AND UNBOUNDED FOLLOWING` are rejected. Validate `window_size` to fail fast. |
| Possible overflow | Pick a `RETURNS` type sized for the largest allowable window. |
| `malloc` instead of `FNC_DefMem` | State is not preserved across phases. Use only `FNC_DefMem`. |
| C++ source | Wrap in `extern "C"`; catch all exceptions before returning. |
| Teradata-managed platform (VantageCloud Lake or Enterprise) | External routines are supported, but direct `EXTERNAL NAME` install may be blocked. On Lake, install/list/uninstall with the `tdextroutine` CLI. On Enterprise, install on Compute Engine nodes or via a service request (not the EDW node). Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`. |

## References


> **Access:** `skill_resource_read(action="read", skill="window-aggregate-udf-c", path="references/FILENAME")` — do NOT call `list`.

- [Window Aggregate UDFs](./references/window-aggregate-udfs.md): full phase flow, FNC_Context_t window fields, moving-window ring-buffer pattern, supported/unsupported window types, partitioning rules, TD_GENERAL and SQL signatures, and complete worked examples
