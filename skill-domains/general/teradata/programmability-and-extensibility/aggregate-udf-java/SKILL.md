---
name: aggregate-udf-java
description: 'Create, register, and remove Java aggregate User-Defined Functions on Teradata. Use when implementing a custom GROUP BY aggregation in Java (SUM, AVG, standard deviation, statistical functions, etc.) that must run in parallel across AMPs. Covers the single static method with Phase and Context[] parameters, the 5-phase model resolved via phase.getPhase() (AGR_INIT/AGR_DETAIL/AGR_COMBINE/AGR_FINAL/AGR_NODATA), com.teradata.fnc.Context intermediate storage (initCtx/getObject/setObject/getBytes/setBytes), JAR install lifecycle, and CLASS AGGREGATE DDL with LANGUAGE JAVA and optional interim_size. Based on Teradata SQL External Routine Programming v20.00.'
when_to_use: 'Use when the user mentions Java aggregate UDF, CLASS AGGREGATE in Java, LANGUAGE JAVA with GROUP BY, Phase.AGR_INIT/AGR_DETAIL/AGR_COMBINE/AGR_FINAL/AGR_NODATA, phase.getPhase(), com.teradata.fnc.Context, initCtx, or wants to implement a multi-phase custom aggregation in Java on Teradata.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Java Aggregate UDF

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

A Java aggregate UDF implements custom GROUP BY aggregation logic in Java. Like C aggregate UDFs,
it must support a **combine phase** so that partial AMP results can be merged into a single
final result.

A Java aggregate UDF is a **single `public static` method** whose first two parameters are a
`com.teradata.fnc.Phase` and a `com.teradata.fnc.Context[]`. Vantage invokes the method once for
each item in an aggregation group, passing the current phase each time. The method calls
`phase.getPhase()` to determine which of the five phases it is in and carries state across
phases through the `Context[]` intermediate storage.

> **Not this skill:** For C aggregate UDFs, see **aggregate-udf-c**. For Java scalar UDFs, see
> **scalar-udf-java**. For Java stored procedures, see **stored-procedure-java**.

## When to Use

- Custom aggregations that cannot be expressed with built-in Teradata aggregate functions
- Aggregations where the Java ecosystem (math libraries, statistics) is preferred over C
- GROUP BY operations requiring state that is easier to manage in Java (collections, maps, etc.)

## Core Concepts

### 5-Phase Model

Aggregate UDFs are implemented as a **single static method**. Branch on `phase.getPhase()`,
which returns one of the `com.teradata.fnc.Phase` constants:

| Value of `phase.getPhase()` | Purpose |
|-----------------------------|---------|
| `Phase.AGR_INIT` | First invocation for an aggregation group. Allocate and initialize intermediate storage with `context[0].initCtx(...)`, then **process the first detail row** (idiomatically by falling through to `AGR_DETAIL`). |
| `Phase.AGR_DETAIL` | Called once per row to aggregate. Retrieve state with `getObject`/`getBytes`, accumulate the input, store it back with `setObject`/`setBytes`. |
| `Phase.AGR_COMBINE` | Combine the results of two AMP storage areas: storage area 1 (`getObject(1)`) and storage area 2 (`getObject(2)`). |
| `Phase.AGR_FINAL` | No more input. Compute and `return` the final group result. |
| `Phase.AGR_NODATA` | Presented only when there is absolutely no data to aggregate. Return null or a default. |

`AGR_COMBINE` is critical for Teradata's parallel architecture: partial AMP aggregates must be
mergeable into a single result.

### Intermediate Storage (`com.teradata.fnc.Context`)

Each group has its own intermediate storage, accessed through `context[0]`:

| Method | Purpose |
|--------|---------|
| `initCtx(Object obj)` / `initCtx(int length)` | In `AGR_INIT`, allocate and initialize the storage from a Serializable object or a fixed byte length. Cannot exceed `interim_size` from the `CLASS AGGREGATE` clause. |
| `getObject(int n)` / `setObject(int n, Object obj)` | Read/write the storage as a Serializable object (`n=1` this AMP, `n=2` the peer AMP in `AGR_COMBINE`). |
| `getBytes(int n)` / `setBytes(int n, byte[] data)` | Read/write the storage as a raw byte array (use with `ByteBuffer` for best performance). |

## Java Implementation

```java
package com.company.udf;

import com.teradata.fnc.*;
import java.io.*;
import java.sql.*;

/**
 * Arithmetic sum aggregate UDF.
 * Reference: https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/
 *   SQL-External-Routine-Programming/UDF-Code-Examples/
 *   Java-Aggregate-Function-Arithmetic-Sum
 */
public class ArithSum {

    /* Intermediate storage object: must be Serializable so it can be
       shipped across AMPs for the AGR_COMBINE phase. */
    static class AgrStorage implements Serializable {
        long total;
        AgrStorage(long t) { total = t; }
    }

    public static Long arithSum(Phase phase, Context[] context, long value)
        throws SQLException
    {
        AgrStorage s1 = null;
        AgrStorage s2 = null;

        /* Storage area 1 is valid in AGR_DETAIL, AGR_COMBINE, and AGR_FINAL.
           Fetch it once here for those phases. */
        if (phase.getPhase() > Phase.AGR_INIT && phase.getPhase() < Phase.AGR_NODATA) {
            s1 = (AgrStorage) context[0].getObject(1);
        }

        switch (phase.getPhase()) {
            case Phase.AGR_INIT:
                /* Allocate and initialize storage, then fall through to
                   AGR_DETAIL to process the FIRST detail row of the group. */
                s1 = new AgrStorage(0);
                context[0].initCtx(s1);
                /* fall through */

            case Phase.AGR_DETAIL:
                /* value cannot be null: NULLs are excluded from aggregation */
                s1.total += value;
                break;

            case Phase.AGR_COMBINE:
                /* Storage area 2 (the peer AMP result) is valid only here */
                s2 = (AgrStorage) context[0].getObject(2);
                s1.total += s2.total;
                break;

            case Phase.AGR_FINAL:
                return s1.total;

            case Phase.AGR_NODATA:
                return null;                    /* no rows: SQL NULL */

            default:
                throw new SQLException("Invalid Phase", "U0005");
        }

        /* Save the updated storage area back (reached after INIT/DETAIL and COMBINE) */
        context[0].setObject(1, s1);
        return null;   /* return value is ignored for INIT/DETAIL/COMBINE */
    }
}
```

**Key rules:**
- The method is a **single `public static`** method; the first two parameters are always
  `Phase phase` and `Context[] context`, followed by the input parameters (max 128).
- Determine the phase with `phase.getPhase()`, never with method-name conventions.
- Fetch storage area 1 (`getObject(1)`) **once** for the `AGR_DETAIL`/`AGR_COMBINE`/`AGR_FINAL`
  phases, and write it back **once** with `setObject(1, s1)` after the switch (the `FINAL` and
  `NODATA` cases `return` before that point).
- `AGR_INIT` must allocate (`initCtx`), initialize, **and process the first detail row** (the
  idiom is to fall through into `AGR_DETAIL`).
- The **intermediate storage object** must implement `java.io.Serializable` (not the UDF class
  itself), because the runtime ships it across AMPs for `AGR_COMBINE`.
- With **primitive** input parameters, NULL rows are excluded from the aggregation, so no null
  check is needed. `import com.teradata.fnc.*` for `Phase`/`Context`; throw `SQLException` with
  an SQLSTATE for the default case.

### Phase Method Summary

| `phase.getPhase()` | C equivalent | Action |
|--------------------|--------------|--------|
| `Phase.AGR_INIT` | `AGR_INIT` | `initCtx`, init, process first row |
| `Phase.AGR_DETAIL` | `AGR_DETAIL` | Accumulate one input row |
| `Phase.AGR_COMBINE` | `AGR_COMBINE` | Merge storage area 2 into area 1 |
| `Phase.AGR_FINAL` | `AGR_FINAL` | Return the final aggregated result |
| `Phase.AGR_NODATA` | `AGR_NODATA` | Aggregate set is empty |

## Procedure: Build the JAR

```bash
javac com/company/udf/ArithSum.java
jar cf arith_sum.jar com/company/udf/ArithSum.class
```

## Procedure: Install the JAR

```sql
-- Grant once per developer role
GRANT EXECUTE PROCEDURE ON SQLJ.INSTALL_JAR TO udf_developer_role;
GRANT EXECUTE PROCEDURE ON SQLJ.REMOVE_JAR  TO udf_developer_role;

DATABASE mydb;
CALL SQLJ.INSTALL_JAR('CJ!/path/to/arith_sum.jar', 'ARITH_SUM_JAR', 0);
```

## Procedure: Register the DDL

```sql
REPLACE FUNCTION mydb.arith_sum (input_val BIGINT)
RETURNS BIGINT
SPECIFIC arith_sum_bigint_impl
LANGUAGE JAVA
NO SQL
CLASS AGGREGATE
PARAMETER STYLE JAVA
EXTERNAL NAME 'ARITH_SUM_JAR:com.company.udf.ArithSum.arithSum';
```

The `CLASS AGGREGATE` clause tells Teradata to invoke the function with the aggregate phase
protocol (passing `Phase` and `Context[]`). Add an optional interim size, for example
`CLASS AGGREGATE (256)`, when the intermediate storage exceeds the 64-byte default (max
64,000 bytes); the value limits what `initCtx` may allocate.

For Java aggregate UDFs the EXTERNAL NAME references the **JAR alias, class, and method**
(`JAR_ALIAS:package.Class.method`). With **primitive** input parameters, Teradata excludes NULL
rows from the aggregation automatically, so `CALLED ON NULL INPUT` and explicit null checks are
not needed. (Use boxed Java types with `CALLED ON NULL INPUT` only if the method must observe
and act on NULL inputs.)

## Procedure: Test and Verify

```sql
SELECT mydb.arith_sum(salary)
FROM employees
GROUP BY department_id;

SELECT FunctionName, ExternalName, FunctionType, LanguageName
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND FunctionName = 'arith_sum';
```

## Procedure: Uninstall

```sql
SELECT * FROM DBC.FunctionXRefsV
WHERE UDFDatabase = 'mydb' AND UDFName = 'arith_sum';

DROP SPECIFIC FUNCTION mydb.arith_sum_bigint_impl;
-- OR:
DROP FUNCTION mydb.arith_sum;

CALL SQLJ.REMOVE_JAR('ARITH_SUM_JAR', 0);
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| Storage retrieved in `AGR_COMBINE` is null | Storage area 2 (`getObject(2)`) is the peer AMP result; guard before accessing fields |
| Group with no rows | Handle `Phase.AGR_NODATA`. Return `null` or a sentinel value. |
| State must cross AMPs | The **intermediate storage object** must implement `Serializable` (not the UDF class). All its fields must be serializable. |
| Performance-critical storage | Use `initCtx(int length)` with a byte array and `getBytes`/`setBytes` + `ByteBuffer` instead of an object. |
| Storage larger than `interim_size` | Increase the `CLASS AGGREGATE (size)` value; `initCtx` cannot exceed it. |
| Unknown phase value | `throw new SQLException("Invalid Phase", "38U05")` in the `default` case. |
| JAR already installed | `CALL SQLJ.REMOVE_JAR('ALIAS', 0)` then reinstall; or use `REPLACE_JAR` |
| Teradata-managed platform (VantageCloud Lake or Enterprise) | External routines are supported, but direct `EXTERNAL NAME` install may be blocked. On Lake, install/list/uninstall with the `tdextroutine` CLI. On Enterprise, install on Compute Engine nodes or via a service request (not the EDW node). Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`. |

## References


> **Access:** `skill_resource_read(action="read", skill="aggregate-udf-java", path="references/FILENAME")` — do NOT call `list`.

- [External UDFs](./references/external-udfs.md): general C/C++/Java UDF development guide, EXTERNAL NAME format, type mappings, JAR install lifecycle, and troubleshooting
