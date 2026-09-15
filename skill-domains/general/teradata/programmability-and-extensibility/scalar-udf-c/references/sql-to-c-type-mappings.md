# SQL-to-C Type Mappings for Scalar UDFs

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** SQL-to-C Type Mappings for Scalar UDFs

> Source: sqltypes_td.h, Teradata Database SQL External Routine Programming

## Required Setup

Every C source file must begin with:

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"
```

`SQL_TEXT` must be defined before the include. It determines the character set used by text parameters.

| SQL_TEXT Value | Character Set |
|---|---|
| `Latin_Text` | Latin (single-byte, most common) |
| `Unicode_Text` | Unicode (double-byte) |

## Integer Types

| SQL Type | C Type | C Underlying | Size |
|---|---|---|---|
| `BYTEINT` | `BYTEINT` | `signed char` | 1 byte |
| `SMALLINT` | `SMALLINT` | `short` | 2 bytes |
| `INTEGER` | `INTEGER` | `int` | 4 bytes |
| `BIGINT` | `BIGINT` | `long long` | 8 bytes |

## Floating Point Types

| SQL Type | C Type | C Underlying | Size |
|---|---|---|---|
| `REAL` | `REAL` | `double` | 8 bytes |
| `DOUBLE PRECISION` | `DOUBLE_PRECISION` | `double` | 8 bytes |
| `FLOAT` | `FLOAT` | `double` | 8 bytes |

## Decimal / Numeric Types

Decimal values are stored as scaled integers. The scale (number of decimal places) is implicit — you must know it from the SQL declaration.

| SQL DECIMAL(n,m) | C Type | Size | Precision Range |
|---|---|---|---|
| `DECIMAL(1-2, m)` | `DECIMAL1` (`signed char`) | 1 byte | 1 ≤ n ≤ 2 |
| `DECIMAL(3-4, m)` | `DECIMAL2` (`short`) | 2 bytes | 3 ≤ n ≤ 4 |
| `DECIMAL(5-9, m)` | `DECIMAL4` (`int`) | 4 bytes | 5 ≤ n ≤ 9 |
| `DECIMAL(10-18, m)` | `DECIMAL8` (struct) | 8 bytes | 10 ≤ n ≤ 18 |
| `DECIMAL(19-38, m)` | `DECIMAL16` (struct) | 16 bytes | 19 ≤ n ≤ 38 |

`NUMERIC` types are identical: `NUMERIC1`, `NUMERIC2`, `NUMERIC4`, `NUMERIC8`, `NUMERIC16`.

### Working with DECIMAL Values

```c
/* DECIMAL(8,2) — stored as DECIMAL4 (int)
   Value 12345.67 is stored as integer 1234567
   To get actual value: stored_value / 10^scale */

DECIMAL4 *price;    /* DECIMAL(8,2) */
double actual = (double)(*price) / 100.0;  /* divide by 10^2 */
```

## Character Types

| SQL Type | C Type (Latin) | C Type (Unicode) | Passing |
|---|---|---|---|
| `CHAR(n)` | `CHARACTER_LATIN` | `CHARACTER_UNICODE` | Fixed-width, space-padded |
| `VARCHAR(n)` | `VARCHAR_LATIN` | `VARCHAR_UNICODE` | Null-terminated string |

### VARCHAR Convention

VARCHAR parameters are passed as **null-terminated C strings** with `PARAMETER STYLE SQL`. Use `strlen()` for length, `sprintf()` or `strcpy()` for output.

```c
void upper_name(
    VARCHAR_LATIN *input,     /* null-terminated string */
    VARCHAR_LATIN *result,    /* write null-terminated string here */
    int           *input_null,
    int           *result_null,
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257])
{
    if (*input_null == -1) { *result_null = -1; return; }

    int i;
    for (i = 0; input[i]; i++) {
        result[i] = toupper((unsigned char)input[i]);
    }
    result[i] = '\0';
    *result_null = 0;
}
```

### CHAR Convention

CHAR values are **fixed-width and space-padded** to the declared length. They are NOT null-terminated.

```c
/* CHAR(10) input "Hello" is stored as "Hello     " (10 chars, space-padded) */
```

## Byte Types

| SQL Type | C Type | Structure |
|---|---|---|
| `BYTE(n)` | `BYTE` (`unsigned char`) | Fixed-width binary |
| `VARBYTE(n)` | `VARBYTE` struct | `{ int length; BYTE bytes[]; }` |

```c
/* Declare a VARBYTE buffer of known max size */
VARBYTE_M(256) my_buffer;
```

## Date / Time Types

| SQL Type | C Type | Representation |
|---|---|---|
| `DATE` | `DATE` (`int`) | Encoded integer |
| `TIME` | `ANSI_Time` | Struct with hour, minute, seconds |
| `TIMESTAMP` | `TimeStamp` | Struct with year through seconds |

### DATE Encoding

DATE is an `int` encoded as: `(year - 1900) * 10000 + month * 100 + day`

```c
/* Encode: 2026-04-27 → (2026-1900)*10000 + 4*100 + 27 = 1260427 */

/* Decode: */
int year  = (*date_val / 10000) + 1900;
int month = (*date_val % 10000) / 100;
int day   = *date_val % 100;

/* Encode: */
*result = (year - 1900) * 10000 + month * 100 + day;
```

### ANSI_Time Structure

```c
typedef struct ANSI_Time {
    DECIMAL4 seconds;   /* DECIMAL(8,6) — includes fractional seconds */
    BYTEINT  hour;
    BYTEINT  minute;
} ANSI_Time;
```

### TimeStamp Structure

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

## LOB Types

LOBs are accessed via locators, not direct pointers:

| SQL Type | C Type |
|---|---|
| `BLOB` / `CLOB` (locator) | `LOB_LOCATOR` (`int`) |
| `BLOB` / `CLOB` (result locator) | `LOB_RESULT_LOCATOR` (`int`) |

Use FNC API functions (`FNC_LobOpen`, `FNC_LobRead`, `FNC_LobClose`) to read LOB data.

## Interval Types

| SQL Type | C Type |
|---|---|
| `INTERVAL YEAR` | `INTERVAL_YEAR` (`SMALLINT`) |
| `INTERVAL YEAR TO MONTH` | `IntrvlYtoM` (struct) |
| `INTERVAL DAY` | `INTERVAL_DAY` (`SMALLINT`) |
| `INTERVAL DAY TO SECOND` | `IntrvlDtoS` (struct) |
| `INTERVAL HOUR` | `HOUR` (`SMALLINT`) |

## Size Macros

Use these macros from `sqltypes_td.h` when computing buffer sizes:

```c
SIZEOF_CHARACTER_LATIN(len)              /* len chars, no null terminator */
SIZEOF_CHARACTER_LATIN_WITH_NULL(len)    /* len chars + null terminator */
SIZEOF_VARCHAR_LATIN(len)
SIZEOF_BYTE(len)
SIZEOF_VARBYTE(len)                      /* sizeof(int) + len bytes */

SIZEOF_BYTEINT    SIZEOF_SMALLINT    SIZEOF_INTEGER    SIZEOF_BIGINT
SIZEOF_REAL       SIZEOF_FLOAT       SIZEOF_DOUBLE_PRECISION
```
