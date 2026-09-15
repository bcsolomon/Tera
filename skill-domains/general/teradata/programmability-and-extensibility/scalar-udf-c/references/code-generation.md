# External UDF Code Generation Reference

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** External UDF Code Generation Reference

This reference provides the complete C/C++ type mappings, function signatures, and FNC API subroutines available in `sqltypes_td.h` for generating Teradata external UDF code.

The authoritative header is bundled at [sqltypes_td.h](./sqltypes_td.h).

## Required Setup

Every C source file for a Teradata external UDF must begin with:

```c
#define SQL_TEXT Latin_Text    /* or Unicode_Text, Kanjisjis_Text, Kanji1_Text */
#include "sqltypes_td.h"
```

`SQL_TEXT` must be defined **before** the include. It determines the character set used by text parameters.

| SQL_TEXT Value | Character Set |
|---|---|
| `Latin_Text` | Latin (single-byte, most common) |
| `Unicode_Text` | Unicode (double-byte) |
| `Kanjisjis_Text` | Kanji SJIS |
| `Kanji1_Text` | Kanji1 |

---

## SQL-to-C Type Mappings

### Integer Types

| SQL Type | C Type | C Size |
|---|---|---|
| `BYTEINT` | `BYTEINT` (`signed char`) | 1 byte |
| `SMALLINT` | `SMALLINT` (`short`) | 2 bytes |
| `INTEGER` | `INTEGER` (`int`) | 4 bytes |
| `BIGINT` | `BIGINT` (`long long`) | 8 bytes |

### Floating Point Types

| SQL Type | C Type | C Size |
|---|---|---|
| `REAL` | `REAL` (`double`) | 8 bytes |
| `DOUBLE PRECISION` | `DOUBLE_PRECISION` (`double`) | 8 bytes |
| `FLOAT` | `FLOAT` (`double`) | 8 bytes |

### Decimal / Numeric Types

| SQL DECIMAL(n,m) | C Type | C Size | Precision Range |
|---|---|---|---|
| `DECIMAL(1-2, m)` | `DECIMAL1` (`signed char`) | 1 byte | 1 ≤ n ≤ 2 |
| `DECIMAL(3-4, m)` | `DECIMAL2` (`short`) | 2 bytes | 3 ≤ n ≤ 4 |
| `DECIMAL(5-9, m)` | `DECIMAL4` (`int`) | 4 bytes | 5 ≤ n ≤ 9 |
| `DECIMAL(10-18, m)` | `DECIMAL8` (struct: `low` + `high`) | 8 bytes | 10 ≤ n ≤ 18 |
| `DECIMAL(19-38, m)` | `DECIMAL16` (struct: 4 ints) | 16 bytes | 19 ≤ n ≤ 38 |

`NUMERIC` types are identical aliases: `NUMERIC1`, `NUMERIC2`, `NUMERIC4`, `NUMERIC8`, `NUMERIC16`.

### Character Types

| SQL Type | C Type | Character Set |
|---|---|---|
| `CHAR(n)` | `CHARACTER_LATIN` / `CHARACTER_UNICODE` / etc. | Matches declared set |
| `VARCHAR(n)` | `VARCHAR_LATIN` / `VARCHAR_UNICODE` / etc. | Matches declared set |
| `BYTE(n)` | `BYTE` (`unsigned char`) | Binary |
| `VARBYTE(n)` | `VARBYTE` struct (`length` + `bytes[]`) | Binary |
| `GRAPHIC(n)` | `GRAPHIC` (`unsigned short`) | Double-byte |
| `VARGRAPHIC(n)` | `VARGRAPHIC` struct (`length` + `graphic[]`) | Double-byte |

#### VARCHAR Passing Convention

VARCHAR parameters are passed as null-terminated C strings for `PARAMETER STYLE SQL`. The length is NOT prepended — use `strlen()` to get the length.

#### VARBYTE Struct

```c
typedef struct VARBYTE {
    int    length;      /* byte length of data */
    BYTE   bytes[1];    /* actual data (variable size) */
} VARBYTE;

/* Declare a VARBYTE of known max size: */
VARBYTE_M(256) my_buffer;
```

#### VARGRAPHIC Struct

```c
typedef struct VARGRAPHIC {
    int      length;
    GRAPHIC  graphic[1];
} VARGRAPHIC;

/* Declare a VARGRAPHIC of known max size: */
VARGRAPHIC_M(100) my_gstr;
```

### Date / Time Types

| SQL Type | C Type | Structure |
|---|---|---|
| `DATE` | `DATE` (`int`) | `(year-1900)*10000 + month*100 + day` |
| `TIME` | `ANSI_Time` | `{ DECIMAL4 seconds; BYTEINT hour, minute; }` |
| `TIMESTAMP` | `TimeStamp` | `{ DECIMAL4 seconds; SMALLINT year; BYTEINT month, day, hour, minute; }` |
| `TIME WITH TIME ZONE` | `ANSI_Time_WZone` | Adds `zone_hour`, `zone_minutes` |
| `TIMESTAMP WITH TIME ZONE` | `ANSI_TimeStamp_WZone` | Adds `zone_hour`, `zone_minutes` |

#### DATE Encoding

```c
/* DATE is an int encoded as: (year - 1900) * 10000 + month * 100 + day */
/* Example: 2026-04-27 = (2026-1900)*10000 + 4*100 + 27 = 1260427 */

/* Extract components: */
int year  = (date_val / 10000) + 1900;
int month = (date_val % 10000) / 100;
int day   = date_val % 100;
```

#### ANSI_Time Structure

```c
typedef struct ANSI_Time {
    DECIMAL4 seconds;   /* DECIMAL(8,6) — includes fractional seconds */
    BYTEINT  hour;
    BYTEINT  minute;
} ANSI_Time;
```

#### TimeStamp Structure

```c
typedef struct TimeStamp {
    DECIMAL4 seconds;   /* DECIMAL(8,6) */
    SMALLINT year;
    BYTEINT  month;
    BYTEINT  day;
    BYTEINT  hour;
    BYTEINT  minute;
} TimeStamp;
```

### Interval Types

| SQL Type | C Type |
|---|---|
| `INTERVAL YEAR` | `INTERVAL_YEAR` (`SMALLINT`) |
| `INTERVAL YEAR TO MONTH` | `IntrvlYtoM` (struct) |
| `INTERVAL MONTH` | `INTERVAL_MONTH` (`SMALLINT`) |
| `INTERVAL DAY` | `INTERVAL_DAY` (`SMALLINT`) |
| `INTERVAL DAY TO HOUR` | `IntrvlDtoH` (struct) |
| `INTERVAL DAY TO MINUTE` | `IntrvlDtoM` (struct) |
| `INTERVAL DAY TO SECOND` | `IntrvlDtoS` (struct) |
| `INTERVAL HOUR` | `HOUR` (`SMALLINT`) |
| `INTERVAL HOUR TO MINUTE` | `IntrvlHtoM` (struct) |
| `INTERVAL HOUR TO SECOND` | `IntrvlHtoS` (struct) |
| `INTERVAL MINUTE` | `MINUTE` (`SMALLINT`) |
| `INTERVAL MINUTE TO SECOND` | `IntrvlMtoS` (struct) |
| `INTERVAL SECOND` | `IntrvlSec` (struct) |

### LOB Types

| SQL Type | C Type |
|---|---|
| `BLOB` / `CLOB` (locator) | `LOB_LOCATOR` (`int`) |
| `BLOB` / `CLOB` (result locator) | `LOB_RESULT_LOCATOR` (`int`) |
| `BLOB` / `CLOB` (reference) | `LOB_REF` (64-byte struct) |

### User-Defined Types (UDT)

| Concept | C Type |
|---|---|
| UDT handle | `UDT_HANDLE` (`int`) |
| Period handle | `PDT_HANDLE` (`int`) |

---

## Scalar UDF Function Signature

### PARAMETER STYLE SQL

For each SQL parameter, the C function receives a value pointer and a null indicator pointer, plus trailing metadata parameters:

```c
void function_name(
    /* --- For each SQL parameter --- */
    <C_TYPE>      *param1,          /* pointer to parameter value */
    <C_TYPE>      *param2,
    /* ... more params ... */
    <C_TYPE>      *result,          /* pointer to return value */

    /* --- Null indicators (one per param + result) --- */
    int           *param1_null,     /* -1 = NULL, 0 = NOT NULL */
    int           *param2_null,
    /* ... */
    int           *result_null,

    /* --- Trailing metadata parameters --- */
    char           sqlstate[6],       /* set to "U0xxx" to signal error */
    SQL_TEXT       extname[129],      /* external function name */
    SQL_TEXT       specific_name[129],/* SPECIFIC name from DDL */
    SQL_TEXT       error_msg[257]     /* error message (when sqlstate set) */
);
```

**NULL handling:** Check `*paramN_null == -1` before accessing the value. Set `*result_null = -1` to return SQL NULL.

**Error reporting:** Set `sqlstate` to a user-defined error code (e.g., `"U0001"`) and fill `error_msg`.

### Complete Scalar UDF Example

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"

/*
 * safe_divide: Returns numerator/denominator, NULL on zero/NULL denominator.
 * SQL: REPLACE FUNCTION db.safe_divide(num FLOAT, den FLOAT) RETURNS FLOAT
 *      LANGUAGE C NO SQL DETERMINISTIC
 *      EXTERNAL NAME 'CS!safe_divide!safe_divide.so'
 *      PARAMETER STYLE SQL;
 */
void safe_divide(
    FLOAT         *numerator,
    FLOAT         *denominator,
    FLOAT         *result,
    int           *numerator_null,
    int           *denominator_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257])
{
    if (*numerator_null == -1 || *denominator_null == -1) {
        *result_null = -1;
        return;
    }

    if (*denominator == 0.0) {
        *result_null = -1;
        return;
    }

    *result = *numerator / *denominator;
    *result_null = 0;
}
```

---

## Aggregate UDF Phases and Signatures

Aggregate UDFs implement four phase functions. The phase is passed via `FNC_Phase`:

```c
typedef enum FNC_Phase_et {
    AGR_INIT    = 1,   /* Initialize accumulator */
    AGR_DETAIL  = 2,   /* Process each row */
    AGR_COMBINE = 3,   /* Merge partial results across AMPs */
    AGR_FINAL   = 4,   /* Compute and return final result */
    AGR_NODATA  = 5    /* No data in group */
} FNC_Phase_et;
```

### FNC_Context_t — Aggregate Context Block

```c
typedef struct FNC_Context_t {
    int          version;
    FNC_flags_t  flags;
    void        *interim1;       /* pointer to intermediate storage 1 */
    int          intrm1_length;  /* length of interim1 area */
    void        *interim2;       /* pointer to intermediate storage 2 */
    int          intrm2_length;  /* length of interim2 area */
    long         group_count;    /* number of rows in group */
    long         window_size;    /* analytical window size */
    long         pre_window;     /* pre-window row count */
    long         post_window;    /* post-window row count */
} FNC_Context_t;
```

### Aggregate Phase Function Signatures

```c
/* AGR_INIT: Allocate state with FNC_DefMem, initialize accumulators */
void agg_func(
    FNC_Phase      phase,
    FNC_Context_t *context,
    <RESULT_TYPE> *result,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257]);

/* AGR_DETAIL: Process one input row */
void agg_func(
    FNC_Phase      phase,
    FNC_Context_t *context,
    <INPUT_TYPE>  *input_val,
    <RESULT_TYPE> *result,
    int           *input_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257]);

/* AGR_COMBINE: Merge partial result from another AMP */
void agg_func(
    FNC_Phase      phase,
    FNC_Context_t *context,
    <RESULT_TYPE> *partial,
    <RESULT_TYPE> *result,
    int           *partial_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257]);

/* AGR_FINAL: Set *result to the final answer */
void agg_func(
    FNC_Phase      phase,
    FNC_Context_t *context,
    <RESULT_TYPE> *result,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257]);
```

### Ordered Aggregate (Analytical) Flags

For `FunctionType = 'B'` (ordered aggregate / window functions), `FNC_Context_t.flags` provides:

```c
typedef struct {
    unsigned unused   : 30;
    unsigned excl_row : 1;  /* 1 = exclude current row from window */
    unsigned last_row : 1;  /* 1 = this is the last row in the group */
} FNC_flags_t;
```

Use `context->window_size`, `context->pre_window`, and `context->post_window` for window frame bounds.

---

## Table UDF Phases and Signatures

Table UDFs operate in phases, producing rows iteratively:

```c
typedef enum FNC_Phase_et {
    TBL_PRE_INIT = 20,   /* One-time setup before init */
    TBL_INIT     = 21,   /* Initialize for a new row set */
    TBL_BUILD    = 22,   /* Produce output rows (called repeatedly) */
    TBL_FINI     = 23,   /* Finalize after last row produced */
    TBL_END      = 24,   /* Cleanup */
    TBL_ABORT    = 25    /* Abort/error cleanup */
} FNC_Phase_et;
```

### Table UDF Control Functions

| Function | Description |
|---|---|
| `FNC_GetPhase(&Phase)` | Get current phase and argument mode (TBL_MODE_VARY or TBL_MODE_CONST) |
| `FNC_TblControl()` | Signal that TBL_BUILD has more rows to produce |
| `FNC_TblAllocCtrlCtx(length)` | Allocate persistent context across phases (per-control) |
| `FNC_TblGetCtrlCtx()` | Retrieve per-control context |
| `FNC_TblAllocCtx(length)` | Allocate persistent context per-AMP |
| `FNC_TblGetCtx()` | Retrieve per-AMP context |
| `FNC_TblOptOut()` | Signal that this AMP has no output rows |
| `FNC_TblAbort()` | Signal abort from within table function |
| `FNC_TblGetColDef()` | Get runtime column definitions (dynamic output) |
| `FNC_TblGetNodeData()` | Get AMP/node topology |
| `FNC_AMPInfo()` | Get AMP information |
| `FNC_TblFirstParticipant()` | Check if this is the first participating AMP |

---

## Size Macros

Use these macros when allocating buffers or computing sizes:

```c
/* Character / String sizes */
SIZEOF_CHARACTER_LATIN(len)              /* len chars, no null terminator */
SIZEOF_CHARACTER_LATIN_WITH_NULL(len)    /* len chars + null terminator */
SIZEOF_CHARACTER_UNICODE(len)
SIZEOF_VARCHAR_LATIN(len)
SIZEOF_VARCHAR_UNICODE(len)
SIZEOF_BYTE(len)
SIZEOF_VARBYTE(len)                      /* sizeof(int) + len bytes */

/* Numeric sizes */
SIZEOF_BYTEINT      SIZEOF_SMALLINT     SIZEOF_INTEGER    SIZEOF_BIGINT
SIZEOF_REAL         SIZEOF_FLOAT        SIZEOF_DOUBLE_PRECISION
SIZEOF_DECIMAL1     SIZEOF_DECIMAL2     SIZEOF_DECIMAL4
SIZEOF_DECIMAL8     SIZEOF_DECIMAL16

/* Date/Time sizes */
SIZEOF_DATE         SIZEOF_ANSI_Time    SIZEOF_TimeStamp
SIZEOF_ANSI_Time_WZone                  SIZEOF_ANSI_TimeStamp_WZone
```

---

## Code Generation Checklist

When generating C code for a Teradata external UDF:

1. **Define SQL_TEXT** before including `sqltypes_td.h`
2. **Map each SQL parameter** to its C type using the tables above
3. **Include null indicator parameters** (`int *`) for every input and the result
4. **Include trailing metadata parameters**: `sqlstate[6]`, `extname[129]`, `specific_name[129]`, `error_msg[257]`
5. **Check null indicators** (`== -1`) before accessing parameter values
6. **Set result_null** to 0 (not null) or -1 (null) before returning
7. **Use `FNC_DefMem`** for aggregate interim storage (not malloc)
8. **Use `FNC_malloc`/`FNC_free`** for general allocations (or just `malloc`/`free` — they're redefined)
9. **Report errors** via `sqlstate` + `error_msg`, never via return codes
10. **Match the EXTERNAL NAME** in DDL to the exact C function name

See [FNC API Reference](./fnc-api-reference.md) for memory management, LOB, UDT, QueryBand, tracing, EON, and UDF vs CXSP applicability.
