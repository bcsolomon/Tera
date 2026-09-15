# FNC API Reference — Memory, LOB, UDT, QueryBand, Tracing & EON

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** FNC API Reference: Memory, LOB, UDT, QueryBand, Tracing & EON

This reference covers all FNC subroutines available in `sqltypes_td.h` for C/C++ UDFs and external stored procedures.

---

## Memory Management

| Function | Signature | Description |
|---|---|---|
| `FNC_DefMem` | `void *FNC_DefMem(int len)` | Allocate memory for aggregate interim storage. Automatically freed at end of aggregation. **Use instead of malloc for aggregate state.** |
| `FNC_malloc` | `void *FNC_malloc(size_t size)` | General-purpose memory allocation (replaces `malloc`). |
| `FNC_free` | `void FNC_free(void *ptr)` | Free memory allocated with `FNC_malloc` (replaces `free`). |

**Important:** `malloc` and `free` are macro-redefined to `FNC_malloc` and `FNC_free` in `sqltypes_td.h`. Any call to `malloc()`/`free()` in UDF code automatically uses the Teradata-safe versions.

## Session Information

| Function | Signature | Description |
|---|---|---|
| `FNC_DbsInfo` | `void FNC_DbsInfo(const dbs_info_t *info)` | Retrieve session/user info. |

```c
typedef struct dbs_info_t {
    SQL_TEXT  UserAccount[30];   /* User account string */
    SQL_TEXT  UserName[30];      /* User name */
    int       UserId;            /* User ID */
    short     StatementNo;       /* Current statement number */
    short     Host;              /* Host ID */
    int       SessionNo;         /* Session number */
    int       RequestNo;         /* Request number */
} dbs_info_t;
```

## Tracing / Debugging

| Function | Signature | Description |
|---|---|---|
| `FNC_Trace_String` | `void FNC_Trace_String(void *TraceStr)` | Write a string to the UDF trace log. |
| `FNC_Trace_Write` | `void FNC_Trace_Write(int argc, void *argv[])` | Write multiple values to trace log. |
| `FNC_Trace_Write_DL` | `void FNC_Trace_Write_DL(int argc, void *argv[], int length[])` | Write multiple values with explicit lengths. |

## LOB (Large Object) Functions

| Function | Description |
|---|---|
| `FNC_GetLobLength(LOB_LOCATOR)` | Get byte length of a LOB. |
| `FNC_LobOpen(locator, &ctxid, start, maxlen)` | Open a LOB for reading. Returns bytes available. |
| `FNC_LobRead(ctxid, buffer, buflen, &actual)` | Read next chunk from an open LOB. Returns 0 on success. |
| `FNC_LobClose(ctxid)` | Close LOB read context. |
| `FNC_LobAppend(result_loc, data, len, &actual)` | Append data to a result LOB. |
| `FNC_LobLoc2Ref(locator, &ref)` | Convert LOB locator to a persistent reference. |
| `FNC_LobRef2Loc(&ref)` | Convert LOB reference back to a locator. |

### LOB Reading Pattern

```c
LOB_LOCATOR     loc = *input_lob_param;
LOB_CONTEXT_ID  ctx;
BYTE            buffer[8192];
FNC_LobLength_t actual;
FNC_LobLength_t total_len = FNC_GetLobLength(loc);

FNC_LobOpen(loc, &ctx, 0, total_len);
while (FNC_LobRead(ctx, buffer, sizeof(buffer), &actual) == 0 && actual > 0) {
    /* process buffer[0..actual-1] */
}
FNC_LobClose(ctx);
```

## UDT (User Defined Type) Functions

| Function | Description |
|---|---|
| `FNC_GetDistinctValue(handle, buf, bufSize, &len)` | Get the underlying value of a DISTINCT UDT. |
| `FNC_SetDistinctValue(handle, value, len)` | Set the value of a DISTINCT UDT result. |
| `FNC_GetStructuredAttribute(handle, path, buf, bufSize, &null, &len)` | Get one attribute from a STRUCTURED UDT. |
| `FNC_SetStructuredAttribute(handle, path, value, null, len)` | Set one attribute on a STRUCTURED UDT result. |
| `FNC_GetStructuredAttributeCount(handle, &count)` | Get number of attributes in a STRUCTURED UDT. |
| `FNC_GetStructuredAttributeInfo(handle, position, bufSize, &info)` | Get metadata for a specific attribute. |
| `FNC_GetDistinctInputLob(handle, &locator)` | Get LOB locator from a DISTINCT UDT. |
| `FNC_GetDistinctResultLob(handle, &result_loc)` | Get result LOB locator from a DISTINCT UDT. |
| `FNC_GetStructuredInputLobAttribute(handle, path, &null, &loc)` | Get LOB attribute from a STRUCTURED UDT. |
| `FNC_GetStructuredResultLobAttribute(handle, path, &result_loc)` | Get result LOB attribute from a STRUCTURED UDT. |
| `FNC_GetInternalValue(handle, buf, bufSize, &len)` | Get raw internal value of a UDT. |
| `FNC_SetInternalValue(handle, value, len)` | Set raw internal value of a UDT. |

### attribute_info_t Structure

```c
typedef struct attribute_info_t {
    INTEGER     attrIndex;
    dtype_en    data_type;
    CHARACTER   attribute_name[256];
    SMALLINT    udt_indicator;      /* 0=None, 1=Struct, 2=Distinct, 3=Internal */
    CHARACTER   udt_type_name[256];
    INTEGER     max_length;
    BIGINT      lob_length;
    SMALLINT    total_interval_digits;
    SMALLINT    num_fractional_digits;
    charset_en  charset_code;
} attribute_info_t;
```

## QueryBand Functions

| Function | Description |
|---|---|
| `FNC_GetQueryBand(buf, bufSize, &len)` | Get raw queryband string. |
| `FNC_GetQueryBandPairs(buf, searchType, &numPairs)` | Parse queryband into name/value pairs. |
| `FNC_GetQueryBandValue(buf, searchType, name, value)` | Get a specific queryband value by name. |

```c
/* Search types for queryband functions */
typedef enum {
    QB_FIRST   = 0,   /* First available (transaction then session) */
    QB_TXN     = 1,   /* Transaction-level queryband only */
    QB_SESSION = 2    /* Session-level queryband only */
} FNC_QBSearch_et;

/* Max queryband sizes */
#define FNC_MAXQUERYBANDSIZE   4106   /* Latin */
#define FNC_MAXQUERYBANDSIZE_U 8212   /* Unicode */
```

## Calling Stored Procedures from UDFs

```c
void FNC_CallSP(
    SQL_TEXT  *SP_Name,     /* Stored procedure name */
    int       argc,         /* Number of parameters */
    void     *argv[],       /* Parameter value pointers */
    int       ind[],        /* Null indicators */
    parm_t    dtype[],      /* Parameter type descriptors */
    char     *sqlstate      /* Error state output */
);
```

### parm_t — Parameter Descriptor

```c
typedef struct parm_t {
    dtype_et    datatype;     /* Data type enum */
    dmode_et    direction;    /* IN_PM, OUT_PM, or INOUT_PM */
    charset_et  charset;
    union {
        int length;           /* For CHAR/VARCHAR/BYTE/GRAPHIC */
        int intervalrange;    /* For INTERVAL types */
        int precision;        /* For TIME/TIMESTAMP */
        struct {
            int totaldigit;   /* DECIMAL(m,n) — m */
            int fracdigit;    /* DECIMAL(m,n) — n */
        } range;
    } size;
} parm_t;
```

## Data Type Enumerations

### dtype_en — SQL Data Types

```c
typedef enum dtype_en {
    UNDEF_DT=0,   CHAR_DT=1,      VARCHAR_DT=2,     BYTE_DT=3,
    VARBYTE_DT=4,  GRAPHIC_DT=5,   VARGRAPHIC_DT=6,  BYTEINT_DT=7,
    SMALLINT_DT=8, INTEGER_DT=9,   REAL_DT=10,
    DECIMAL1_DT=11, DECIMAL2_DT=12, DECIMAL4_DT=13, DECIMAL8_DT=14,
    DATE_DT=15, TIME_DT=16, TIMESTAMP_DT=17,
    INTERVAL_YEAR_DT=18, INTERVAL_YTM_DT=19, INTERVAL_MONTH_DT=20,
    INTERVAL_DAY_DT=21, INTERVAL_DTH_DT=22, INTERVAL_DTM_DT=23,
    INTERVAL_DTS_DT=24, INTERVAL_HOUR_DT=25, INTERVAL_HTM_DT=26,
    INTERVAL_HTS_DT=27, INTERVAL_MINUTE_DT=28, INTERVAL_MTS_DT=29,
    INTERVAL_SECOND_DT=30, TIME_WTZ_DT=31, TIMESTAMP_WTZ_DT=32,
    BLOB_REFERENCE_DT=33, CLOB_REFERENCE_DT=34, UDT_DT=35,
    BIGINT_DT=36, DECIMAL16_DT=37
} dtype_en;
```

### dmode_en / charset_en

```c
typedef enum dmode_en { UNDEF_PM=0, IN_PM=1, INOUT_PM=2, OUT_PM=3 } dmode_en;
typedef enum charset_en { UNDEF_CT=0, LATIN_CT=1, UNICODE_CT=2, KANJISJIS_CT=3, KANJI1_CT=4 } charset_en;
```

## Extended Object Names (EON) API

When `EnableEON=TRUE`, object names can be up to 128 Unicode characters (513 UTF-8 bytes including null terminator). Use `_EON` variants of FNC functions.

### FNC_DbsInfo_EON

```c
typedef struct dbs_info_eon_t {
    char     UserAccount[513];   /* UTF-8, null-terminated */
    char     UserName[513];
    int      UserId;
    short    StatementNo;
    short    Host;
    int      SessionNo;
    int      RequestNo;
} dbs_info_eon_t;

void FNC_DbsInfo_EON(dbs_info_eon_t *info);
```

### TD_ANYTYPE and Structured Type Functions (EON)

| Function | Description |
|---|---|
| `FNC_GetAnyTypeParamInfo_EON(paramNo, &info)` | Get type info for `TD_ANYTYPE` param. UDT names up to 513 bytes. |
| `FNC_GetStructuredAttributeInfo_EON(handle, pos, bufSize, &info)` | Get attribute metadata with extended names. |
| `FNC_GetArrayTypeInfo_EON(paramNo, &info)` | Get element type info for ARRAY param. |

### Table Operator Functions (EON)

| Function | Description |
|---|---|
| `FNC_TblOpGetColDef()` | Get input column definitions with UTF-8 names. |
| `FNC_TblOpSetOutputColDef(numCols, defs)` | Define output columns for dynamic schema. |
| `FNC_TblOpGetHashByDef()` | Get HASH BY clause column definitions. |
| `FNC_TblOpSetHashByDef(numCols, defs)` | Set HASH BY clause column definitions. |
| `FNC_TblOpGetLocalOrderByDef()` | Get LOCAL ORDER BY clause columns. |
| `FNC_TblOpSetLocalOrderByDef(numCols, defs)` | Set LOCAL ORDER BY clause columns. |
| `FNC_TblOpGetCustomKeyInfoAt(index, keyBuf, size, &numValues)` | Get custom clause key name by index. |
| `FNC_TblOpGetCustomKeyInfoOf(key, &numValues)` | Get value count for a named custom key. |
| `FNC_TblOpGetCustomValuesOf(key, valueBuf, size, valueIndex)` | Get custom clause value at index. |

### EON Compatibility Notes

- EON functions available on DBS versions with `EnableEON=TRUE`
- Legacy functions continue to work but truncate names to 30 characters
- Always prefer `_EON` variants for new code
- EON functions return UTF-8 regardless of `SQL_TEXT` setting

## FNC API Applicability: UDFs vs External Stored Procedures

| FNC API Category | UDFs | CXSPs | Notes |
|---|---|---|---|
| Memory (`FNC_DefMem`, `FNC_malloc`, `FNC_free`) | Yes | Yes | `FNC_DefMem` primarily for aggregate UDFs |
| Session info (`FNC_DbsInfo`, `_EON`) | Yes | Yes | |
| Tracing (`FNC_Trace_*`) | Yes | Yes | |
| LOB (`FNC_Lob*`) | Yes | Yes | |
| UDT (`FNC_Get/SetDistinct/Structured*`) | Yes | Yes | |
| QueryBand (`FNC_GetQueryBand*`) | Yes | Yes | |
| Table UDF control (`FNC_Tbl*`) | Yes | No | Table UDFs only |
| Table operator (`FNC_TblOp*`) | Yes | No | Table operators only |
| Table UDF phase (`FNC_GetPhase`/`FNC_GetPhaseEx`) | Yes | No | Table UDFs/operators only; returns mode + phase |
| Aggregate phase (`FNC_Phase` parameter) | Yes | No | Aggregate UDFs receive the phase as their 1st parameter, not via `FNC_GetPhase` |
| `FNC_CallSP` | Yes | Yes | For XSPs that do not use CLIv2 |
| CLI (`DBCHINI`/`DBCHCL`/`DBCAREA`) | No | Yes | CXSPs that execute SQL via CLIv2 |
