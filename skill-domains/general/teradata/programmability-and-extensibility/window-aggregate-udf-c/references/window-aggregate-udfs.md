# Window Aggregate UDFs (C/C++) Reference

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** Window Aggregate UDFs (C/C++) Reference

Authoritative basis: Teradata SQL External Routine Programming v20.00, window aggregate (OLAP
aggregate) sections. A window aggregate UDF is an aggregate UDF (`CLASS AGGREGATE`) that is also
valid when invoked under an OLAP window specification (`OVER (...)`).

## 1. Relationship to Plain Aggregates

A single C aggregate function can serve as both a `GROUP BY` aggregate and a window aggregate.
There is no separate DDL class for windows; the function is registered with `CLASS AGGREGATE`
(optionally `CLASS AGGREGATE (interim_size)`), and the window behavior is determined by the
`OVER (...)` clause supplied at call time.

The calling convention is identical to a plain aggregate: the first parameter is `FNC_Phase
phase`, the second is `FNC_Context_t *fctx`, followed by the input parameters and the result.
The differences are in the phase set and in the window fields the runtime populates.

## 2. Window Phase Flow

| Phase | Value | Applies to | Notes |
|-------|-------|-----------|-------|
| `AGR_INIT` | 1 | all | Once per partition. Allocate via `FNC_DefMem`, init storage, process the first row, fall through to `AGR_DETAIL`. |
| `AGR_DETAIL` | 2 | all | Once per forward-row progression. Accumulate the input. |
| `AGR_COMBINE` | 3 | not window | Never presented for window aggregates. Treat as an error. |
| `AGR_FINAL` | 4 | all | Move the computed result into the result row. |
| `AGR_NODATA` | 5 | all | No data at all in the set. |
| `AGR_MOVINGTRAIL` | 6 | moving only | Trailing-row trigger as the forward pointer reaches the end of the partition. Supplies no new values; shrink the window. |

A plain `GROUP BY` aggregate uses `AGR_INIT`/`AGR_DETAIL`/`AGR_COMBINE`/`AGR_FINAL`/`AGR_NODATA`.
A window aggregate replaces `AGR_COMBINE` (not applicable) with `AGR_MOVINGTRAIL` (moving
windows only).

## 3. FNC_Context_t Window Fields

Set by Vantage before the function is invoked:

| Field | Type | Meaning |
|-------|------|---------|
| `window_size` | int | `-1` cumulative, `-2` reporting, `post_window - pre_window + 1` moving. |
| `pre_window` | int | `PRECEDING` offset; negative; `0` for cumulative/reporting. |
| `post_window` | int | `FOLLOWING` offset; positive; `0` for cumulative/reporting. |
| `interim1` | void * | Pointer to intermediate storage (allocated with `FNC_DefMem`). |
| `intrm1_length` | int | Length of `interim1`. |
| `version` | int | Context structure version. |

Vantage performs the `PRECEDING`/`FOLLOWING`/`CURRENT ROW` bookkeeping. The UDF maintains a
cache of rows whose maximum size equals `window_size` (for moving windows) and applies the
function semantics to that cache.

## 4. Supported and Unsupported Window Types

### Reporting window
`ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`. `window_size` is `-2`. Hash
partitioning only, because the result is not order dependent.

### Cumulative window
`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`, or
`ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING`. `window_size` is `-1`. Hash partitioning
only.

### Moving window
Supported groups:
- `value PRECEDING AND CURRENT ROW`
- `CURRENT ROW AND value FOLLOWING`
- `value PRECEDING AND value FOLLOWING`
- `value PRECEDING AND value PRECEDING`
- `value FOLLOWING AND value FOLLOWING`

`window_size` is `post_window - pre_window + 1`. Hash and range (value) partitioning are both
allowed.

### Not supported
- `ROWS BETWEEN UNBOUNDED PRECEDING AND value FOLLOWING`
- `ROWS BETWEEN value PRECEDING AND UNBOUNDED FOLLOWING`

Usage note: Vantage does not check that a UDF is used with a specific window type. Validate
`fctx->window_size` in `AGR_INIT` and raise an error for unsupported window types. Size the
return type so the largest permitted window cannot overflow it.

## 5. Signatures

### PARAMETER STYLE TD_GENERAL
```c
void f( FNC_Phase       phase,
        FNC_Context_t  *fctx,
        <intype>       *input,    /* one per input parameter */
        <outtype>      *result,
        char            sqlstate[6] );
```

### PARAMETER STYLE SQL
```c
void f( FNC_Phase       phase,
        FNC_Context_t  *fctx,
        <intype>       *input,
        <outtype>      *result,
        int            *input_i,  /* null indicator per input */
        int            *result_i, /* null indicator for result */
        char            sqlstate[6],
        SQL_TEXT        fncname[129],
        SQL_TEXT        sfncname[129],
        SQL_TEXT        error_message[257] );
```

## 6. Moving-Window Ring Buffer Pattern

For a moving sum (or moving average numerator) maintain a ring buffer of the last
`window_size` input values plus a running accumulator:

```c
typedef struct {
    int     window_size;
    int     count;        /* rows seen so far, capped at window_size */
    int     next;         /* write index */
    int     tptr;         /* trailing index */
    double  current_value;
    double  data[1];      /* flexible cache, sized window_size at FNC_DefMem time */
} MOV_Storage;

/* AGR_INIT: window_size = fctx->window_size; allocate
   sizeof(MOV_Storage) + (window_size-1)*sizeof(double); init; fall through. */

/* AGR_DETAIL:
     if (count == window_size) {              // window full: drop trailing
         current_value -= data[tptr];
         tptr = (tptr + 1) % window_size;
     } else {
         count++;
     }
     current_value += *x;
     data[next] = *x;
     next = (next + 1) % window_size;
     break;

   AGR_MOVINGTRAIL:                            // no new value; shrink window
     current_value -= data[tptr];
     tptr = (tptr + 1) % window_size;
     break;

   AGR_FINAL:
     *result = current_value; */
```

Reporting and cumulative windows do not slide, so they never receive `AGR_MOVINGTRAIL`; for
those a single running accumulator is sufficient.

## 7. DDL and Invocation

```sql
REPLACE FUNCTION mydb.my_moving_sum (x FLOAT)
RETURNS FLOAT
CLASS AGGREGATE (1000)
LANGUAGE C
NO SQL
PARAMETER STYLE SQL
DETERMINISTIC
CALLED ON NULL INPUT
EXTERNAL NAME 'CS!my_moving_sum!udf_src/my_moving_sum.c';
```

```sql
SELECT id,
       mydb.my_moving_sum(value) OVER (
           PARTITION BY grp ORDER BY ts
           ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS moving_sum
FROM measurements;
```

The same function may also be used as a plain aggregate:
`SELECT grp, mydb.my_moving_sum(value) FROM measurements GROUP BY grp;` (the `GROUP BY` form
exercises the `AGR_COMBINE` path, so if the function is intended for windows only, document and
guard against `GROUP BY` use).

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Error in `AGR_COMBINE` | Used as `GROUP BY` aggregate, or combine logic missing | For window use, never reach combine; for dual use, implement a correct combine |
| Wrong moving-window result | Ring buffer not draining on `AGR_MOVINGTRAIL` | Subtract the trailing value and advance `tptr` each `AGR_MOVINGTRAIL` |
| Error on a particular `OVER` clause | Unsupported window type | Reject `UNBOUNDED PRECEDING AND value FOLLOWING` and `value PRECEDING AND UNBOUNDED FOLLOWING` |
| State lost across phases | Used `malloc` instead of `FNC_DefMem` | Allocate with `FNC_DefMem` and assign to `fctx->interim1` in `AGR_INIT` |
| Numeric overflow on large windows | `RETURNS` type too narrow | Widen the result type |
