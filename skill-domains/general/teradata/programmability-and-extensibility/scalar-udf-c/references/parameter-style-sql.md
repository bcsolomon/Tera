# PARAMETER STYLE SQL — Deep Dive

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** PARAMETER STYLE SQL: Deep Dive

> Source: Teradata Database SQL External Routine Programming, sqltypes_td.h

## Overview

All C scalar UDFs on Teradata use `PARAMETER STYLE SQL`. This convention defines the exact order and types of parameters passed from the SQL engine to your C function.

## Parameter Order

For a function with N SQL parameters, the C function signature contains:

```
[N value pointers] [1 result pointer] [N+1 null indicators] [4 trailing metadata]
```

### Concrete Example — Two Parameters

```sql
CREATE FUNCTION mydb.add_values (a INTEGER, b INTEGER) RETURNS INTEGER ...
```

Maps to:

```c
void add_values(
    /* 1. Value pointers (one per SQL param, then result) */
    INTEGER  *a,                /* SQL param 1 */
    INTEGER  *b,                /* SQL param 2 */
    INTEGER  *result,           /* return value */

    /* 2. Null indicators (one per param + result) */
    int      *a_null,           /* -1 = NULL, 0 = NOT NULL */
    int      *b_null,
    int      *result_null,

    /* 3. Trailing metadata (always present, always last) */
    char      sqlstate[6],
    SQL_TEXT  extname[129],
    SQL_TEXT  specific_name[129],
    SQL_TEXT  error_msg[257]
);
```

## Null Indicators

Each null indicator is an `int *`:

| Value | Meaning |
|-------|---------|
| `-1` | The corresponding SQL value is NULL |
| `0` | The corresponding SQL value is NOT NULL |

### Checking Input Nulls

```c
if (*param1_null == -1) {
    /* param1 is NULL — do NOT dereference *param1 */
    *result_null = -1;
    return;
}
/* Safe to use *param1 here */
```

### Setting the Result Null

```c
/* Return a valid value */
*result = computed_value;
*result_null = 0;

/* Return SQL NULL */
*result_null = -1;
```

### CALLED ON NULL INPUT vs RETURNS NULL ON NULL INPUT

| DDL Clause | Behavior |
|-----------|----------|
| `CALLED ON NULL INPUT` | C function is called even when inputs are NULL — you must check indicators |
| `RETURNS NULL ON NULL INPUT` | SQL engine returns NULL without calling C — simpler but less flexible |

Use `CALLED ON NULL INPUT` when you need custom NULL handling (e.g., COALESCE-like behavior). Use `RETURNS NULL ON NULL INPUT` when any NULL input should produce NULL output.

## Trailing Metadata Parameters

These four parameters are always appended after the null indicators, in this order:

### sqlstate — Error Signaling

```c
char sqlstate[6];  /* 5 chars + null terminator */
```

- Default value: `"00000"` (success)
- Set to `"U0xxx"` to signal a user-defined error (e.g., `"U0001"`)
- Set to `"02000"` to signal "no data found"
- When sqlstate is set to an error code, the query fails and `error_msg` text is returned

```c
/* Signal an error */
strcpy(sqlstate, "U0001");
strcpy(error_msg, "Input value out of valid range");
return;
```

### extname — External Function Name

```c
SQL_TEXT extname[129];  /* read-only — the EXTERNAL NAME from DDL */
```

Useful for logging or diagnostic messages.

### specific_name — SPECIFIC Name from DDL

```c
SQL_TEXT specific_name[129];  /* read-only — the SPECIFIC name, if declared */
```

### error_msg — Error Message Text

```c
SQL_TEXT error_msg[257];  /* write this when sqlstate is set to an error code */
```

The text appears in the client error message when the UDF signals an error.

## Complete Template

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"

void my_function(
    /* Value pointers: inputs then result */
    <INPUT_TYPE1>  *param1,
    <INPUT_TYPE2>  *param2,
    <RESULT_TYPE>  *result,

    /* Null indicators: inputs then result */
    int            *param1_null,
    int            *param2_null,
    int            *result_null,

    /* Trailing metadata */
    char            sqlstate[6],
    SQL_TEXT        extname[129],
    SQL_TEXT        specific_name[129],
    SQL_TEXT        error_msg[257])
{
    /* 1. Check for NULLs */
    if (*param1_null == -1 || *param2_null == -1) {
        *result_null = -1;
        return;
    }

    /* 2. Validate inputs */
    /* ... */

    /* 3. Compute result */
    *result = /* computation */;
    *result_null = 0;

    /* 4. On error: */
    /* strcpy(sqlstate, "U0001");
       strcpy(error_msg, "Description of the problem");
       return; */
}
```

## Common Mistakes

| Mistake | Consequence | Fix |
|---------|------------|-----|
| Dereferencing value when null indicator is -1 | Undefined behavior / crash | Always check `*paramN_null == -1` first |
| Forgetting to set `*result_null = 0` | Result treated as NULL | Always set result_null to 0 for valid results |
| Wrong parameter order | Silent data corruption | Follow the exact order: values → nulls → metadata |
| Missing trailing metadata | Compilation failure | Always include all 4 trailing parameters |
| Using `printf` instead of `sqlstate`/`error_msg` | Output goes nowhere | Use the error reporting mechanism |
| Setting sqlstate without error_msg | Cryptic error for users | Always pair sqlstate with a descriptive error_msg |

## Multi-Parameter Null Check Patterns

### All-or-nothing (any NULL → return NULL)

```c
if (*p1_null == -1 || *p2_null == -1 || *p3_null == -1) {
    *result_null = -1;
    return;
}
```

### Selective NULL handling (COALESCE-like)

```c
int val1 = (*p1_null == -1) ? default_value : *p1;
int val2 = (*p2_null == -1) ? default_value : *p2;
*result = val1 + val2;
*result_null = 0;
```

### NULL propagation with partial results

```c
if (*p1_null == -1 && *p2_null == -1) {
    *result_null = -1;
    return;
}
if (*p1_null == -1) { *result = *p2; }
else if (*p2_null == -1) { *result = *p1; }
else { *result = *p1 + *p2; }
*result_null = 0;
```
