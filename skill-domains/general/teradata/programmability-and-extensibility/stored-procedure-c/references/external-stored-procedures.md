# External C/C++ Stored Procedures (CXSP): Complete Reference

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** External C/C++ Stored Procedures (CXSP): Complete Reference

## Overview

External stored procedures (CXSP) are written in C/C++ and run in the UDF/XSP server process. They can use the CLI (Call-Level Interface) to execute SQL and return dynamic result sets to callers.

## CREATE PROCEDURE Syntax

```sql
REPLACE PROCEDURE database_name.procedure_name (
    IN    param1 INTEGER,
    OUT   param2 VARCHAR(100),
    INOUT param3 DECIMAL(18,2)
)
LANGUAGE C
NO SQL                              -- or CONTAINS SQL, READS SQL DATA, MODIFIES SQL DATA
PARAMETER STYLE SQL
DYNAMIC RESULT SETS n               -- number of result sets returned (0 if none)
EXTERNAL NAME 'CS!procedure_name!xsp_src/procedure_name.c!F!procedure_name';
```

### EXTERNAL NAME Format

A procedure that does **not** execute SQL:

```
CS!<name_on_server>!<source_path>[!F!<function_symbol>]
```

A procedure that executes SQL via CLIv2 must be prefixed with the `SP!CLI!` package name so it
links against the CLI-specific XSP library:

```
SP!CLI!CS!<name_on_server>!<source_path>[!F!<function_symbol>]
```

- `CS!`: client source file; the database compiles it on first execution
- `name_on_server`: unique logical identifier for the file in the DB catalog
- `source_path`: path to the C source file on the client (relative or absolute)
- `[!F!<function_symbol>]`: optional C function entry point; defaults to the SQL procedure name when omitted
- `SP!CLI!`: required prefix only when the procedure uses CLIv2 to execute SQL

## Installation

```sql
-- 1. Register the procedure (database compiles xsp_src/my_proc.c on first execution).
--    SP!CLI! prefix is required because this procedure executes SQL via CLIv2.
REPLACE PROCEDURE mydb.my_proc (IN p1 INTEGER, OUT p2 VARCHAR(100))
LANGUAGE C
MODIFIES SQL DATA
PARAMETER STYLE TD_GENERAL
DYNAMIC RESULT SETS 1
EXTERNAL NAME 'SP!CLI!CS!my_proc!xsp_src/my_proc.c!F!my_proc';

-- 2. Grant access
GRANT EXECUTE PROCEDURE ON mydb.my_proc TO app_role;
```

## C Function Signature (PARAMETER STYLE SQL)

Same convention as external UDFs:

```c
#define SQL_TEXT Latin_Text
#include "sqltypes_td.h"

void my_proc(
    /* Value pointers for each parameter */
    INTEGER       *param1,          /* IN */
    VARCHAR_LATIN *param2,          /* OUT */
    DECIMAL4      *param3,          /* INOUT */

    /* Null indicators */
    int           *param1_null,
    int           *param2_null,
    int           *param3_null,

    /* Trailing metadata */
    char           sqlstate[6],
    SQL_TEXT       extname[129],
    SQL_TEXT       specific_name[129],
    SQL_TEXT       error_msg[257]
)
{
    /* Check NULLs */
    if (*param1_null == -1) {
        strcpy(sqlstate, "U0001");
        strcpy((char*)error_msg, "param1 cannot be NULL");
        return;
    }

    /* Set OUT parameter */
    sprintf((char*)param2, "Result: %d", *param1);
    *param2_null = 0;
}
```

## Executing SQL Within a CXSP (CLIv2)

A C/C++ external stored procedure executes SQL by following standard CLIv2 application
programming practice against a `DBCAREA` structure. There are **no** `Connection`,
`Statement`, or `ResultSet` classes. The procedure DDL must use the `SP!CLI!` EXTERNAL NAME
prefix and a SQL-access clause other than `NO SQL`.

### Overall Procedure

1. Include the CLIv2 header files after `sqltypes_td.h`.
2. Declare the function per the CREATE/REPLACE PROCEDURE parameter-passing convention.
3. Initialize the `DBCAREA` with `DBCHINI`.
4. Submit each request with `DBCHCL`, setting `dbcarea.func` to the request code.

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

    /* Initialize the DBCAREA */
    dbcarea.total_len = sizeof(struct DBCAREA);
    DBCHINI(&result, cntxt, &dbcarea);

    /* Initiate a request (DBFIRQ) */
    sprintf(req, "SELECT region_id FROM regions WHERE name = '%s';", (char *)in_name);
    dbcarea.func        = DBFIRQ;
    dbcarea.req_ptr     = req;
    dbcarea.req_len     = strlen(req);
    dbcarea.change_opts = 'Y';
    DBCHCL(&result, cntxt, &dbcarea);

    /* Fetch response parcels with dbcarea.func = DBFFET, copy data to out_id,  */
    /* then end the request with dbcarea.func = DBFERQ.                          */
}
```

Calling most Teradata library (FNC_) functions from a CLIv2 XSP incurs expensive context
switches, and some require outstanding CLIv2 requests to complete first. Only `FNC_malloc`
and `FNC_free` are exempt.

### Returning Dynamic Result Sets

A result set is the response to a single SELECT. Set `SP_return_result` and `keep_resp` on the
request, and declare the count in DDL with `DYNAMIC RESULT SETS n`:

```c
sprintf(req, "SELECT * FROM inventory WHERE store_id = %d;", store);
dbcarea.func             = DBFIRQ;
dbcarea.req_ptr          = req;
dbcarea.req_len          = strlen(req);
dbcarea.change_opts      = 'Y';
dbcarea.SP_return_result = 3;     /* 3 = return to the caller of the XSP */
dbcarea.keep_resp        = 'Y';   /* 'Y' = NO SCROLL rules, 'P' = SCROLL rules */
DBCHCL(&result, cntxt, &dbcarea);
```

### Consuming Result Sets from a Called Stored Procedure

To let the XSP consume result sets created by a stored procedure it calls, set
`dynamic_result_sets_allowed = 'Y'` on the request that contains the `CALL`:

```c
dbcarea.change_opts                 = 'Y';
dbcarea.dynamic_result_sets_allowed = 'Y';
dbcarea.req_ptr                     = "CALL sp1('SEL * FROM t1');";
```

SQL stored procedures can also return dynamic result sets using PREPARE/OPEN:

```sql
REPLACE PROCEDURE get_inventory (IN in_store INTEGER)
DYNAMIC RESULT SETS 1
BEGIN
    DECLARE v_sql VARCHAR(500);
    DECLARE rs CURSOR WITH RETURN ONLY FOR prepared_stmt;

    SET v_sql = 'SELECT store, item, onhand FROM inventory WHERE store = ?';
    PREPARE prepared_stmt FROM v_sql;
    OPEN rs USING in_store;
    -- Leave cursor open; it returns to caller
END;
```

### PREPARE/OPEN Rules

1. PREPARE target must be a valid SQL statement
2. Parameter markers `?` are positional, matched left to right with USING variables
3. USING data types must exactly match the parameter marker types
4. Cannot PREPARE a HELP, SHOW, or multi-statement request
5. DEALLOCATE PREPARE releases resources after the cursor is opened
6. Multiple cursors = multiple result sets, returned in open order

## Configuration (cufconfig)

The `cufconfig` utility configures the XSP/UDF server environment on each DBS node (for
example timeouts, task counts, and Java debug settings). A CLIv2 XSP does not require a
special "default connection" setting; it executes SQL directly through the DBCAREA API
described above. Changes to `cufconfig` require restarting the UDF/XSP server.

## FNC API in External Stored Procedures

CXSPs have access to the same FNC_ API functions as C/C++ UDFs. These are documented in detail in [code-generation.md](../../teradata-udf/references/code-generation.md). Key functions available to CXSPs:

### Session Info

```c
#include "sqltypes_td.h"

void my_xsp(...) {
    dbs_info_t info;
    FNC_DbsInfo(&info);
    /* info.UserName, info.SessionNo, info.UserId, etc. */

    /* For Extended Object Names (EnableEON=TRUE): */
    dbs_info_eon_t eon_info;
    FNC_DbsInfo_EON(&eon_info);
    /* eon_info.UserName is UTF-8, up to 513 bytes */
}
```

### LOB Handling

CXSPs use the same LOB read/write pattern as UDFs:

```c
void xsp_read_lob(LOB_LOCATOR *input_lob, ...) {
    LOB_CONTEXT_ID ctx;
    BYTE buffer[8192];
    FNC_LobLength_t actual;
    FNC_LobLength_t total = FNC_GetLobLength(*input_lob);

    FNC_LobOpen(*input_lob, &ctx, 0, total);
    while (FNC_LobRead(ctx, buffer, sizeof(buffer), &actual) == 0 && actual > 0) {
        /* process buffer[0..actual-1] */
    }
    FNC_LobClose(ctx);
}
```

### Tracing

```c
#include "sqltypes_td.h"

void my_xsp(...) {
    /* Simple string trace */
    FNC_Trace_String("Entering my_xsp");

    /* Structured trace with explicit lengths */
    void *args[2];
    int lens[2];
    INTEGER val = 42;
    char msg[] = "debug point";
    args[0] = &val; lens[0] = sizeof(INTEGER);
    args[1] = msg;  lens[1] = strlen(msg);
    FNC_Trace_Write_DL(2, args, lens);
}
```

Trace output requires a trace table:

```sql
CREATE SET GLOBAL TEMPORARY TRACE TABLE tracetbl,
    FALLBACK, CHECKSUM = DEFAULT, LOG;

SET SESSION FUNCTION TRACE USING '' FOR TABLE tracetbl;

CALL my_xsp();

SELECT * FROM tracetbl;
```

### Calling Other Stored Procedures

A CXSP calls another stored procedure by submitting a `CALL` request through CLIv2. To consume
any dynamic result sets the called procedure creates, set `dynamic_result_sets_allowed = 'Y'`
on the request:

```c
dbcarea.func                        = DBFIRQ;
dbcarea.change_opts                 = 'Y';
dbcarea.dynamic_result_sets_allowed = 'Y';
dbcarea.req_ptr                     = "CALL mydb.other_proc(100);";
dbcarea.req_len                     = strlen(dbcarea.req_ptr);
DBCHCL(&result, cntxt, &dbcarea);
```

## CLIv2 (Call-Level Interface) for SQL Execution

A CXSP executes SQL through CLIv2 against a `DBCAREA` structure. `DBCHINI` initializes the
DBCAREA; `DBCHCL` performs each call with the request code in `dbcarea.func`. There are no
C++ wrapper classes.

```c
#include <coptypes.h>
#include <coperr.h>
#include <parcel.h>
#include <dbcarea.h>

void my_xsp(...) {
    DBCAREA dbcarea;
    Int32   result;
    char    cntxt[4];

    /* Initialize the DBCAREA */
    dbcarea.total_len = sizeof(struct DBCAREA);
    DBCHINI(&result, cntxt, &dbcarea);

    /* Initiate a request */
    char *sql = "SELECT col1, col2 FROM my_table;";
    dbcarea.func        = DBFIRQ;          /* Initiate Request */
    dbcarea.req_ptr     = sql;
    dbcarea.req_len     = strlen(sql);
    dbcarea.change_opts = 'Y';
    DBCHCL(&result, cntxt, &dbcarea);

    /* Fetch response parcels */
    dbcarea.func = DBFFET;                 /* Fetch */
    DBCHCL(&result, cntxt, &dbcarea);
    while (result == 0) {
        /* Process the returned parcel in dbcarea.fet_data_ptr */
        DBCHCL(&result, cntxt, &dbcarea);
    }

    /* End the request */
    dbcarea.func = DBFERQ;                 /* End Request */
    DBCHCL(&result, cntxt, &dbcarea);
}
```

### Result Set Options (DBCAREA Fields)

| DBCAREA Field | Value | Description |
|---|---|---|
| `SP_return_result` | 2 | Return the result set to the client application |
| | 3 | Return the result set to the caller of the external stored procedure |
| | 4 | Return to the client application and the procedure |
| | 5 | Return to the caller and the procedure |
| `keep_resp` | `'Y'` | Returned rows follow NO SCROLL cursor rules |
| | `'P'` | Returned rows follow SCROLL cursor rules |
| `dynamic_result_sets_allowed` | `'Y'`/`'N'` | Whether this procedure consumes result sets from a called SP |

### CLIv2 Request Codes (dbcarea.func)

| Constant | Description |
|---|---|
| `DBFCON` | Connect |
| `DBFIRQ` | Initiate request (submit SQL) |
| `DBFFET` | Fetch the next response parcel |
| `DBFERQ` | End request |
| `DBFABT` | Abort the current request |

## Updating External SPs

```sql
-- Simply replace the procedure with a new source path (DB recompiles).
-- SP!CLI! prefix because this procedure executes SQL via CLIv2.
REPLACE PROCEDURE mydb.my_proc (IN p1 INTEGER, OUT p2 VARCHAR(100))
LANGUAGE C
MODIFIES SQL DATA
PARAMETER STYLE TD_GENERAL
DYNAMIC RESULT SETS 1
EXTERNAL NAME 'SP!CLI!CS!my_proc!xsp_src/my_proc_v2.c!F!my_proc';
```

## Security

- CXSPs run in a sandboxed UDF/XSP server process (`udfsectsk` in protected mode)
- Execution mode: `EXECUTE PROTECTED` (default) or `EXECUTE NOT PROTECTED`
- External security context: `EXTERNAL SECURITY DEFINER [authorization_name]` or `EXTERNAL SECURITY INVOKER`
- File system access requires an OS account plus a CREATE AUTHORIZATION object
- Network access may be restricted by site policy

```sql
-- Create authorization for file access
CREATE AUTHORIZATION mydb.file_auth
AS DEFINER
USER 'os_username'
PASSWORD 'os_password';
```

## C External SP vs C UDF: Key Differences

Both use the same C language environment (`sqltypes_td.h`, FNC_ API, PARAMETER STYLE SQL), but serve different purposes:

| Aspect | C UDF | C External SP (CXSP) |
|---|---|---|
| **Purpose** | Per-row computation in SQL expressions | Procedural logic invoked via CALL |
| **Types** | Scalar (`CS!`), Table (`CS!`), Aggregate (`CS!`) | Stored Procedure (`CS!`) |
| **Invocation** | `SELECT func(col) FROM t` | `CALL proc(args)` |
| **Return** | Via result parameter (scalar), rows (table) | Via OUT/INOUT params + result sets |
| **SQL access** | `NO SQL` only (scalar/aggregate) | `NO SQL` through `MODIFIES SQL DATA` |
| **SQL execution** | Not available | CLIv2 (`DBCHINI`/`DBCHCL` against a `DBCAREA`) |
| **Dynamic result sets** | Table UDFs produce rows | `DYNAMIC RESULT SETS 0-15` |
| **FNC_ API** | Full access (memory, LOB, UDT, trace, QueryBand, table/aggregate phases) | Same, except no table/aggregate phase functions |
| **Installation** | `CS!` source delivery; DB compiles on first execution | Same |
| **EXTERNAL NAME** | `'CS!name!src/file.c'` (scalar/aggregate) / `'CS!name!src/file.c!F!entry'` | `'CS!name!xsp_src/file.c!F!entry'`; prefix `SP!CLI!` when using CLIv2 |
| **Execution** | Per-row (inline with query) | Per-CALL (procedural) |
| **Aggregate phases** | AGR_INIT → AGR_DETAIL → AGR_COMBINE → AGR_FINAL / AGR_NODATA | N/A |
| **Table phases** | TBL_PRE_INIT → TBL_INIT → TBL_BUILD → TBL_FINI → TBL_END | N/A |
| **Method signature** | Value ptrs + null indicators + trailing metadata | Same convention |
| **Context persistence** | `FNC_DefMem` (aggregate), `FNC_TblAllocCtx` (table) | Scoped to single CALL |

### Shared FNC API (Both UDFs and CXSPs)

| Category | Functions |
|---|---|
| Memory | `FNC_DefMem`, `FNC_malloc`, `FNC_free` |
| Session info | `FNC_DbsInfo`, `FNC_DbsInfo_EON` |
| Tracing | `FNC_Trace_String`, `FNC_Trace_Write`, `FNC_Trace_Write_DL` |
| LOB | `FNC_GetLobLength`, `FNC_LobOpen`, `FNC_LobRead`, `FNC_LobClose`, `FNC_LobAppend`, `FNC_LobLoc2Ref`, `FNC_LobRef2Loc` |
| UDT | `FNC_GetDistinctValue`, `FNC_SetDistinctValue`, `FNC_GetStructuredAttribute`, `FNC_SetStructuredAttribute`, ... |
| QueryBand | `FNC_GetQueryBand`, `FNC_GetQueryBandPairs`, `FNC_GetQueryBandValue` |

### UDF-Only FNC API

| Category | Functions |
|---|---|
| Aggregate control | `FNC_DefMem` (state allocation in AGR_INIT), `FNC_Context_t` struct (`interim1`/`interim2` state fields); phase received as `FNC_Phase` first parameter |
| Table UDF control | `FNC_GetPhase` (returns mode; writes `FNC_Phase` via pointer), `FNC_TblControl`, `FNC_TblAllocCtx`, `FNC_TblGetCtx`, `FNC_TblAllocCtrlCtx`, `FNC_TblGetCtrlCtx`, `FNC_TblOptOut`, `FNC_TblAbort`, `FNC_TblGetColDef`, `FNC_TblGetNodeData`, `FNC_AMPInfo`, `FNC_TblFirstParticipant` |
| Table operators (EON) | `FNC_TblOp*` functions |

### CXSP-Only Capabilities

| Category | Mechanism |
|---|---|
| SQL execution | CLIv2 (`DBCHINI`/`DBCHCL` against a `DBCAREA`) |
| Dynamic result sets | `DYNAMIC RESULT SETS n` + `SP_return_result` / `keep_resp` on the request |
| Abort a request | CLIv2 `DBFABT` |
