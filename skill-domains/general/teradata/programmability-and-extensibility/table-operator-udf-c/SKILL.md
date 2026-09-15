---
name: table-operator-udf-c
description: 'Create, register, and remove C/C++ Table Operator User-Defined Functions on Teradata. Use when implementing a parallel streaming operator that takes a table as input. Table operators are fundamentally different from table functions: they declare no scalar parameters (input arrives as a streamed table expression), define their output schema dynamically through a separate contract function named in the RETURNS TABLE VARYING USING FUNCTION clause, use PARAMETER STYLE SQLTABLE, run on each AMP in parallel, and accept partitioning clauses (HASH BY, PARTITION BY, LOCAL ORDER BY). Covers the operator DDL, contract function role, the FNC_TblOp API, and the EXTERNAL NAME format. Based on Teradata SQL External Routine Programming v20.00.'
when_to_use: 'Use when the user mentions table operator UDF, PARAMETER STYLE SQLTABLE, RETURNS TABLE VARYING USING FUNCTION, contract function, streaming operator, PARTITION BY in a UDF context, HASH BY, LOCAL ORDER BY for a C operator, the FNC_TblOp API, or wants to run a C function on each AMP across a partitioned input stream.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata C/C++ Table Operator UDF

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

A **table operator** is a C/C++ function that takes a **table** as input and produces a table as
output. Unlike a table function (which takes scalar inputs and returns rows), a table operator:

- Declares no formal scalar parameters. Its input arrives as a streamed table expression at invocation
- Defines its output schema through a separate **contract function** named in the `RETURNS TABLE VARYING USING FUNCTION <contract>` clause
- Uses `PARAMETER STYLE SQLTABLE`, not `PARAMETER STYLE SQL`
- Runs on each AMP in parallel, processing the locally partitioned rows
- Reads input rows and emits output rows through the `FNC_TblOp` API rather than scalar parameters

> **Not this skill:** For functions returning rows from scalar inputs, see **table-function-udf-c**.
> For Java table operators, see **table-operator-udf-java**.

## When to Use

- Implementing a parallel per-AMP streaming transform
- Running a stateful algorithm across a partitioned input (e.g., rolling window, ML scoring)
- Processing each AMP's local data share without cross-AMP communication
- Any workload where the C function consumes rows from a table and emits rows

## DDL Syntax

A table operator is registered with an **empty parameter list**. Its output schema is determined at
plan time by a **contract function** referenced in the `USING FUNCTION` clause.

```sql
REPLACE FUNCTION mydb.udaggregation ()
    RETURNS TABLE VARYING USING FUNCTION mydb.udaggregation_contract
    LANGUAGE C
    NO SQL
    PARAMETER STYLE SQLTABLE
    EXTERNAL NAME 'CS!udaggregation!udaggregation.c!F!udaggregation';
```

- `()` empty parameter list: the operator reads input rows from the streamed input table, not from declared parameters
- `RETURNS TABLE VARYING USING FUNCTION <contract>`: the named contract function defines the output column schema dynamically
- `PARAMETER STYLE SQLTABLE`: the table operator calling convention. Input and output are handled through the `FNC_TblOp` API, not scalar parameters
- `EXTERNAL NAME 'CS!...!F!...'`: C source delivered from the client. `F!` names the C entry point

### Key DDL Differences vs Table Function

| Aspect | Table Function | Table Operator |
|--------|----------------|----------------|
| Output clause | `RETURNS TABLE (col defs)` | `RETURNS TABLE VARYING USING FUNCTION <contract>` |
| Parameter style | `PARAMETER STYLE SQL` | `PARAMETER STYLE SQLTABLE` |
| Input | Scalar parameters | Streamed input table (empty parameter list) |
| Output schema | Fixed in the DDL | Defined dynamically by the contract function |
| AMP execution | All AMPs process the same inputs | Each AMP processes its local partition |
| Partitioning | Not applicable | `HASH BY`, `PARTITION BY`, `LOCAL ORDER BY` |

## EXTERNAL NAME Format

For C source delivered from the client:

```
'CS!<symbol>!<source_path>!F!<entry_point>'
```

The `F!<entry_point>` segment names the C function that implements the operator. The contract
function is named separately in the `RETURNS TABLE VARYING USING FUNCTION` clause, not in
EXTERNAL NAME. If the operator and contract functions live in separate source files, the DDL must
reference both source files.

```
'CS!udaggregation!udaggregation.c!F!udaggregation'
```

## Execution Model

A table operator is **not** phase based. Unlike a table function (which the engine calls once per
input row), a table operator C function is called **once** per AMP. The function opens its input
streams, iterates over the rows itself, writes output rows, and closes the streams. This single-call
model lowers per-row cost and allows flexible read and write patterns.

Two C functions are involved:

| Function | When | Role |
|----------|------|------|
| Contract function | Plan time (query parse) | Inspect input columns and clauses, define the output row format |
| Operator function | Run time, once per AMP | Open, read, transform, write, and close the input and output streams |

The contract function has a scalar-UDF-like signature and reports success through its `Result`
output. The operator function takes no parameters.

## SQLTABLE Iterator API

Input and output rows are in IndicData format. The operator uses these `FNC_TblOp` functions:

| Function | Purpose |
|----------|---------|
| `FNC_TblOpGetStreamCount(&in, &out)` | Number of input and output streams |
| `FNC_TblOpGetColCount(streamNo, ISINPUT)` | Column count of a stream |
| `FNC_TblOpGetColDef(streamNo, ISINPUT, cols)` | Column definitions of a stream |
| `FNC_TblOpOpen(streamNo, 'r' or 'w', 0)` | Open a stream for read or write. Returns a handle |
| `FNC_TblOpRead(handle)` | Read the next row. Returns `TBLOP_SUCCESS` or `TBLOP_EOF` |
| `FNC_TblOpWrite(outHandle)` | Write the current output row |
| `FNC_TblOpClose(handle)` | Close a stream |
| `FNC_TblOpSetOutputColDef(streamNo, cols)` | Contract: define the output columns |
| `FNC_TblOpSetFormat(...)` | Contract: set the row and field format |

Row data is reached through the handle: `handle->row->columnptr[i]`, `handle->row->lengths[i]`, and
the null indicators with `TBLOPISNULL(handle->row->indicators, i)` and
`TBLOPSETNULL(outHandle->row->indicators, i)`.

## C Implementation Pattern

This passthrough operator copies every input column to the output. The contract function builds the
output column definitions from the input columns. The operator function streams rows through.

```c
#define SQL_TEXT Latin_Text
#include <sqltypes_td.h>

/* Plan-time: define the output row format from the input columns. */
int passthrough_contract(
    INTEGER  *Result,
    int      *indicator_Result,
    char      sqlstate[6],
    SQL_TEXT  extname[129],
    SQL_TEXT  specific_name[129],
    SQL_TEXT  error_message[257])
{
    int incount, outcount, colcount;
    FNC_TblOpColumnDef_t *iCols, *oCols;

    FNC_TblOpGetStreamCount(&incount, &outcount);
    if (incount == 0) {
        strcpy((char *)sqlstate, "U0003");
        strcpy((char *)error_message, "passthrough requires at least one input stream.");
        *Result = -1;
        return -1;
    }

    colcount = FNC_TblOpGetColCount(0, ISINPUT);
    iCols = FNC_malloc(TblOpSIZECOLDEF(colcount));
    TblOpINITCOLDEF(iCols, colcount);
    FNC_TblOpGetColDef(0, ISINPUT, iCols);

    /* Output mirrors the input columns. */
    oCols = FNC_malloc(TblOpSIZECOLDEF(colcount));
    TblOpINITCOLDEF(oCols, colcount);
    memcpy(oCols, iCols, TblOpSIZECOLDEF(colcount));

    FNC_TblOpSetOutputColDef(0, oCols);

    FNC_free(iCols);
    FNC_free(oCols);
    *Result = 1;
    return 0;
}

/* Run-time: called once per AMP. Iterate input rows and write output rows. */
void passthrough()
{
    int incount, outcount, colcount, i, rc;
    FNC_TblOpColumnDef_t *iCols;
    FNC_TblOpHandle_t *in, *out;

    FNC_TblOpGetStreamCount(&incount, &outcount);

    colcount = FNC_TblOpGetColCount(0, ISINPUT);
    iCols = FNC_malloc(TblOpSIZECOLDEF(colcount));
    TblOpINITCOLDEF(iCols, colcount);
    FNC_TblOpGetColDef(0, ISINPUT, iCols);

    in  = (FNC_TblOpHandle_t *)FNC_TblOpOpen(0, 'r', 0);
    out = (FNC_TblOpHandle_t *)FNC_TblOpOpen(0, 'w', 0);

    while ((rc = FNC_TblOpRead(in)) == TBLOP_SUCCESS) {
        for (i = 0; i < iCols->num_columns; i++) {
            out->row->columnptr[i] = in->row->columnptr[i];
            out->row->lengths[i]   = in->row->lengths[i];
            if (TBLOPISNULL(in->row->indicators, i))
                TBLOPSETNULL(out->row->indicators, i);
        }
        FNC_TblOpWrite(out);   /* emit the row */
    }

    FNC_TblOpClose(in);
    FNC_TblOpClose(out);
    FNC_free(iCols);
}
```

For multiple input streams, loop over each stream index from `FNC_TblOpGetStreamCount` and track end
of file per stream. See the references for the multiple-input and cogroup patterns.

## Invocation Syntax

A table operator is named directly in the `FROM` clause. Input arrives through one or more `ON`
clauses (a table, a view, or a query expression). There is no `TABLE OPERATOR` wrapper keyword and
no `TABLE (...)` input wrapper.

```sql
-- Single input, hash-partitioned and locally ordered
SELECT t.*
FROM mydb.passthrough (
    ON (SELECT row_id, value FROM source_table)
    HASH BY row_id
    LOCAL ORDER BY row_id
) AS t;

-- Partition by a key column, alias the output columns
SELECT t.region, t.amount
FROM mydb.passthrough (
    ON (SELECT region, amount FROM mydb.raw_data)
    PARTITION BY region
    LOCAL ORDER BY amount
) AS t (region, amount);
```

A table operator can take up to 16 `ON` clauses (multiple input streams) and custom name-value
clauses through a `USING` clause. The caller needs `EXECUTE FUNCTION` on the operator or its
containing database.

## Procedure: Verify and Uninstall

```sql
SELECT FunctionName, ExternalName, FunctionType
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND FunctionName = 'passthrough';

SELECT * FROM DBC.FunctionXRefsV
WHERE UDFDatabase = 'mydb' AND UDFName = 'passthrough';

DROP FUNCTION mydb.passthrough;
```

You cannot drop, alter, or rename the contract function directly. Dropping the table operator drops
its contract function. Altering or recompiling the operator does the same to the contract function.

## Edge Cases

| Situation | Action |
|-----------|--------|
| At least one input stream required | Check `FNC_TblOpGetStreamCount`; fail the contract if `incount == 0` |
| Multiple input streams | Open each with `FNC_TblOpOpen(i, 'r', 0)`; track `TBLOP_EOF` per stream |
| Reopen an input stream | Allowed. Each open resets the read position to the start |
| LOB columns | Stream with `FNC_LobOpen_CL`, `FNC_LobRead`, `FNC_LobAppend` into the output locator |
| Operator and contract in separate files | Reference both source files in the DDL |
| C++ source | Wrap in `extern "C"`; catch all exceptions before returning |
| Teradata-managed platform (VantageCloud Lake or Enterprise) | External routines are supported, but direct `EXTERNAL NAME` install may be blocked. On Lake, install/list/uninstall with the `tdextroutine` CLI. On Enterprise, install on Compute Engine nodes or via a service request (not the EDW node). Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`. |

## References


> **Access:** `skill_resource_read(action="read", skill="table-operator-udf-c", path="references/FILENAME")` — do NOT call `list`.

- [External UDFs](./references/external-udfs.md): full C/C++ development guide, parameter style, privilege matrix, EXTERNAL NAME format details, troubleshooting
- [FNC API Reference](./references/fnc-api-reference.md): FNC_TblOp iterator and contract functions (FNC_TblOpGetStreamCount, FNC_TblOpOpen, FNC_TblOpRead, FNC_TblOpWrite, FNC_TblOpClose, FNC_TblOpGetColDef, FNC_TblOpSetOutputColDef); memory, LOB, QueryBand functions
- Teradata SQL External Routine Programming, C Table Operators: https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming/C/C-User-Defined-Functions/Table-Operators

