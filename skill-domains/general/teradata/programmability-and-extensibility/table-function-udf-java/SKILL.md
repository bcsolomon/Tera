---
name: table-function-udf-java
description: 'Create, register, and remove Java table function User-Defined Functions on Teradata. Use when implementing a function that returns multiple rows (RETURNS TABLE) via Java. Covers the void method signature with one output array parameter per RETURNS TABLE column (or java.lang.Object[] for dynamic result rows), com.teradata.fnc.Tbl.getPhase()/getPhaseEx(), constant vs variable mode, the phase model (TBL_PRE_INIT/TBL_INIT/TBL_BUILD/TBL_FINI/TBL_END/TBL_ABORT and TBL_BUILD_EOF), signaling no-more-rows by throwing SQLException with SQLState 02000, Tbl.control()/optOut()/allocCtx scratchpad, JAR lifecycle, PARAMETER STYLE JAVA DDL, and TABLE() invocation. Based on Teradata SQL External Routine Programming v20.00.'
when_to_use: 'Use when the user mentions Java table UDF, LANGUAGE JAVA with RETURNS TABLE, com.teradata.fnc.Tbl, Tbl.getPhase, TBL_PRE_INIT/TBL_INIT/TBL_BUILD/TBL_FINI/TBL_END in Java, output array parameters for table rows, throwing SQLException 02000 to end rows, or wants to implement a row-generating function in Java on Teradata.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Java Table Function UDF

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

A Java table function UDF returns a **set of rows** from a Java method. The DDL uses
`RETURNS TABLE (col1 type, ...)` with `LANGUAGE JAVA` and `PARAMETER STYLE JAVA`. The Java
method returns `void` and has **one output array parameter per `RETURNS TABLE` column**. It
builds rows one at a time during the `TBL_BUILD` phase, driving the phase loop with
`com.teradata.fnc.Tbl`.

> **Not this skill:** For C table functions, see **table-function-udf-c**. For Java scalar UDFs,
> see **scalar-udf-java**. For Java aggregate UDFs, see **aggregate-udf-java**.

## When to Use

- Generating rows from Java logic (parsing, expanding, iterating over data structures)
- Using Java libraries (JSON, XML, regular expressions) to produce tabular output
- Situations where RETURNS TABLE output is needed but C implementation is not available

## Java Method Requirements

A Java table function method:

- Must be `public static` and return `void`.
- Takes the **input parameters first**, then **one output array parameter per `RETURNS TABLE`
  column**. With simple mapping the output args are primitive arrays (`int[]`, `double[]`);
  with object mapping they are object arrays (`java.lang.Integer[]`, `java.lang.String[]`).
  For a dynamic result row spec (`RETURNS TABLE VARYING COLUMNS`) the single output param is
  `java.lang.Object[]` and the actual column defs come from `Tbl.getColDef()`.
- Constructs a `com.teradata.fnc.Tbl` instance and calls `getPhase(int[])` (or
  `getPhaseEx(int[], int)`) to drive the phase loop. Only table UDFs may construct a `Tbl`.
- Builds **one row per `TBL_BUILD` call** by assigning element `[0]` of each output array.
  Signals no-more-rows by throwing `SQLException` with SQLState `"02000"`.

### Phase model

`Tbl.getPhase(int[] phase)` returns the **mode** (`Tbl.TBL_MODE_CONST` or `Tbl.TBL_MODE_VARY`)
and writes the current phase into `phase[0]`.

| Phase | Mode | Action |
|-------|------|--------|
| `TBL_PRE_INIT` | both | Establish global context; no rows. Allocate scratchpad via `Tbl.allocCtx(obj)`. Constant mode: call `Tbl.control()` to become the controlling copy. |
| `TBL_INIT` | both | Open resources. Constant mode: a copy with nothing to do may call `Tbl.optOut()`. |
| `TBL_BUILD` | both | Fill each output array `[0]` to emit one row, **or** throw `SQLException(..., "02000")` when no more rows. |
| `TBL_FINI` | variable only | Clear the scratchpad before the next input row; loops back to `TBL_INIT` if more input, else `TBL_END`. |
| `TBL_END` | both | Release resources; normal completion. |
| `TBL_ABORT` | both | Release resources; entered only after `Tbl.abort()`. |
| `TBL_BUILD_EOF` | with `getPhaseEx(TBL_LASTROW)` | Emit a final summary row, or throw `"02000"`. |

```java
package com.company.udf;

import com.teradata.fnc.Tbl;
import java.io.Serializable;
import java.sql.SQLException;

public class SplitCSV {

    /* Scratchpad retained across TBL_BUILD calls. Must be Serializable. */
    static class ParseState implements Serializable {
        String[] tokens;
        int      pos;
        ParseState(String csv) {
            tokens = (csv == null) ? new String[0] : csv.split(",", -1);
        }
    }

    /*
     * One output array parameter (colValue) for the single RETURNS TABLE column.
     * The method returns void and fills colValue[0] once per TBL_BUILD call.
     */
    public static void splitRows(String csvInput, String[] colValue)
        throws SQLException
    {
        Tbl   tbl   = new Tbl();
        int[] phase = new int[1];
        int   mode  = tbl.getPhase(phase);   /* mode = TBL_MODE_CONST or TBL_MODE_VARY */

        switch (phase[0]) {
            case Tbl.TBL_PRE_INIT:
                /* Allocate scratchpad; no rows here. */
                tbl.allocCtx(new ParseState(csvInput));
                if (mode == Tbl.TBL_MODE_CONST) {
                    tbl.control();   /* optionally become the controlling copy */
                }
                break;

            case Tbl.TBL_INIT:
                /* Open resources. Constant-mode copy with nothing to do can opt out. */
                if (mode == Tbl.TBL_MODE_CONST && csvInput == null) {
                    tbl.optOut();
                }
                break;

            case Tbl.TBL_BUILD:
                ParseState st = (ParseState) tbl.getCtxObject();
                if (st == null || st.pos >= st.tokens.length) {
                    throw new SQLException("no more rows", "02000");  /* end of rows */
                }
                colValue[0] = st.tokens[st.pos].trim();   /* build one row */
                st.pos++;
                tbl.setCtxObject(st);                      /* persist position */
                break;

            case Tbl.TBL_FINI:
                /* Variable mode only: clear scratchpad before next input row. */
                break;

            case Tbl.TBL_END:
            case Tbl.TBL_ABORT:
                /* Release any open resources. */
                break;
        }
    }
}
```

**Rules:**
- The method returns `void`. **Output args follow the input args**, one array per `RETURNS TABLE` column.
- Build a row by assigning `outputArg[0]`; `TBL_BUILD` is called repeatedly, once per emitted row.
- Signal end-of-rows by `throw new SQLException(msg, "02000")` in `TBL_BUILD` (not by returning).
- Retain state between iterations with `Tbl.allocCtx(obj)` (in `TBL_PRE_INIT`) plus
  `getCtxObject()` / `setCtxObject(obj)`; the state class must implement `Serializable`.
- `TBL_FINI` occurs in **variable mode only**. Use `getPhaseEx(phase, Tbl.TBL_LASTROW)` to also
  receive `TBL_BUILD_EOF` for emitting a final summary row.
- Do not open a `jdbc:default:connection` to emit rows; rows are produced by filling output args.

## Procedure: Build the JAR

`com.teradata.fnc.Tbl` lives in the Teradata-provided UDF Java library; place it on the
compile classpath (no JDBC driver is required for table UDFs).

```bash
javac -cp .:/path/to/tdgss/fnc.jar com/company/udf/SplitCSV.java

jar cf split_csv.jar com/company/udf/SplitCSV*.class
```

## Procedure: Install the JAR

```sql
GRANT EXECUTE PROCEDURE ON SQLJ.INSTALL_JAR TO udf_developer_role;
GRANT EXECUTE PROCEDURE ON SQLJ.REMOVE_JAR  TO udf_developer_role;

DATABASE mydb;
CALL SQLJ.INSTALL_JAR('CJ!/path/to/split_csv.jar', 'SPLIT_CSV_JAR', 0);
```

## Procedure: Register the DDL

```sql
REPLACE FUNCTION mydb.split_csv (csv_input VARCHAR(10000))
RETURNS TABLE (col_value VARCHAR(1000))
SPECIFIC split_csv_impl
LANGUAGE JAVA
NO SQL
PARAMETER STYLE JAVA
EXTERNAL NAME 'SPLIT_CSV_JAR:com.company.udf.SplitCSV.splitRows';

GRANT EXECUTE FUNCTION ON mydb.split_csv TO app_role;
```

### EXTERNAL NAME Format

Simple mapping (no parameter types listed):

```
'<JAR_ALIAS>:<FullyQualifiedClassName>.<methodName>'
```

With **object mapping** the signature lists every parameter type, including the output
array params (one per `RETURNS TABLE` column):

```
'SPLIT_CSV_JAR:com.company.udf.SplitCSV.splitRows(java.lang.String, java.lang.String[])'
```

## Procedure: Call the Table Function

```sql
-- Expand CSV column into rows
SELECT t.col_value
FROM TABLE (mydb.split_csv('apple,banana,cherry')) AS t;

-- Join with a source table
SELECT s.id, t.col_value
FROM source_table s,
     TABLE (mydb.split_csv(s.csv_column)) AS t;
```

## Procedure: Verify and Uninstall

```sql
SELECT FunctionName, ExternalName, LanguageName
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND FunctionName = 'split_csv';

SELECT * FROM DBC.FunctionXRefsV
WHERE UDFDatabase = 'mydb' AND UDFName = 'split_csv';

DROP SPECIFIC FUNCTION mydb.split_csv_impl;
-- OR:
DROP FUNCTION mydb.split_csv;

CALL SQLJ.REMOVE_JAR('SPLIT_CSV_JAR', 0);
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| No more rows to emit | Throw `new SQLException(msg, "02000")` in `TBL_BUILD` (do not just return) |
| NULL input | Produce zero rows by throwing `"02000"` on the first `TBL_BUILD` (or `optOut()` in constant mode) |
| Retaining state across rows | Allocate a `Serializable` scratchpad via `Tbl.allocCtx()` in `TBL_PRE_INIT`; read/write with `getCtxObject()`/`setCtxObject()` |
| Output column count mismatch | Provide exactly one output array param per `RETURNS TABLE` column (or `Object[]` + `getColDef()` for dynamic) |
| Final summary row needed | Use `getPhaseEx(phase, Tbl.TBL_LASTROW)` and emit it in `TBL_BUILD_EOF` |
| Cleanup | Release resources in `TBL_END` and `TBL_ABORT`; not automatic |
| JAR already installed | Use `SQLJ.REPLACE_JAR` to update in place, or `REMOVE_JAR` then `INSTALL_JAR` |
| Teradata-managed platform (VantageCloud Lake or Enterprise) | External routines are supported, but direct `EXTERNAL NAME` install may be blocked. On Lake, install/list/uninstall with the `tdextroutine` CLI. On Enterprise, install on Compute Engine nodes or via a service request (not the EDW node). Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`. |

## References


> **Access:** `skill_resource_read(action="read", skill="table-function-udf-java", path="references/FILENAME")` — do NOT call `list`.

- [External UDFs](./references/external-udfs.md): full Java UDF development guide, com.teradata.fnc.Tbl phase model, scratchpad context, constant vs variable mode, Java UDF vs JXSP comparison, privilege matrix
