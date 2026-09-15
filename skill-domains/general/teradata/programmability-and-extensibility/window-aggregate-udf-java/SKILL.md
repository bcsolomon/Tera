---
name: window-aggregate-udf-java
description: 'Create, register, and remove Java window aggregate User-Defined Functions on Teradata. Use when a Java aggregate UDF must also work under an OLAP window specification (OVER (PARTITION BY ... ORDER BY ... ROWS ...)) such as moving, cumulative, or reporting windows. Covers the single static method with Phase and Context[] parameters, the window phase model resolved via phase.getPhase() (AGR_INIT/AGR_DETAIL/AGR_MOVINGTRAIL/AGR_FINAL/AGR_NODATA, with AGR_COMBINE not used), reading the window size via context[0].getWindowSize(), maintaining a row cache sized to the window, JAR install lifecycle, and CLASS AGGREGATE DDL with LANGUAGE JAVA and an EXTERNAL NAME carrying the explicit method signature. Based on Teradata SQL External Routine Programming v20.00.'
when_to_use: 'Use when the user mentions Java window aggregate UDF, OLAP aggregate in Java, an aggregate UDF invoked with OVER() in Java, AGR_MOVINGTRAIL in Java, context.getWindowSize(), moving/cumulative/reporting window UDF in Java, or a custom Java aggregate that maintains a sliding window of rows.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Java Window Aggregate UDF

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

A Java window aggregate UDF is an aggregate UDF (`CLASS AGGREGATE`) that is also valid under an
OLAP window specification, that is, when invoked with an `OVER (PARTITION BY ... ORDER BY ...
ROWS ...)` clause. It uses the same single `public static` method with `Phase` and `Context[]`
parameters as a plain Java aggregate UDF, but the runtime drives a different set of phases and
exposes the window size through the context.

> **Not this skill:** For a plain `GROUP BY` aggregate in Java, see **aggregate-udf-java**. For
> C window aggregates, see **window-aggregate-udf-c**. For Java scalar UDFs, see
> **scalar-udf-java**.

## When to Use

- A custom aggregate in Java that callers invoke with `OVER (...)` (moving averages, running
  totals, sliding-window statistics)
- Aggregations whose result depends on a sliding window of ordered rows within a partition
- Extending an existing Java aggregate UDF so it behaves correctly under window semantics

## Core Concepts

### Window Phase Model

The UDF is a **single static method**. Branch on `phase.getPhase()`. Window aggregation uses a
different phase set than `GROUP BY` aggregation: there is **no `AGR_COMBINE`**, and moving
windows add **`AGR_MOVINGTRAIL`**.

| `phase.getPhase()` | Purpose |
|--------------------|---------|
| `Phase.AGR_INIT` | First invocation for a partition. Allocate and initialize storage with `context[0].initCtx(...)`, capture the window size with `context[0].getWindowSize()`, then process the first row (idiomatically by falling through to `AGR_DETAIL`). |
| `Phase.AGR_DETAIL` | Called each time the forward row progresses. Accumulate the input into the window cache. |
| `Phase.AGR_COMBINE` | **Not used** by window aggregates. In a window-only UDF, let it fall through to `AGR_FINAL` or raise an error if reached. |
| `Phase.AGR_MOVINGTRAIL` | **Moving window only.** Triggered by trailing rows as the forward pointer reaches the end of the partition. No new values are supplied; subtract the trailing value and advance the trailing pointer. |
| `Phase.AGR_FINAL` | No more input. Compute and `return` the result for the current window position. |
| `Phase.AGR_NODATA` | Presented only when there is no data at all to aggregate. Return null or a default. |

Vantage handles the `PRECEDING`/`FOLLOWING`/`CURRENT ROW` bookkeeping. The method only maintains
a cache of rows sized to the window and implements the function semantics over that cache.

### Window Size From the Context

In `AGR_INIT`, read the window size with `context[0].getWindowSize()`:

| Returned value | Window type |
|----------------|-------------|
| `-1` | Cumulative |
| `-2` | Reporting |
| positive (`post - pre + 1`) | Moving |

Use the value to size the row cache and to validate the window type. Reporting and cumulative
windows do not slide and never receive `AGR_MOVINGTRAIL`; a single running accumulator is
sufficient for them.

### Intermediate Storage (`com.teradata.fnc.Context`)

State is carried across phases through `context[0]`, exactly as for plain Java aggregates:
`initCtx(Object)` in `AGR_INIT`, then `getObject(1)` / `setObject(1, obj)` to read and write the
Serializable storage object in later phases.

### Supported and Unsupported Window Types

| Window type | Aggregation group | Partitioning |
|-------------|-------------------|--------------|
| Reporting | `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING` | Hash only |
| Cumulative | `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`, or `CURRENT ROW AND UNBOUNDED FOLLOWING` | Hash only |
| Moving | `value PRECEDING AND CURRENT ROW`; `CURRENT ROW AND value FOLLOWING`; `value PRECEDING AND value FOLLOWING`; `value PRECEDING AND value PRECEDING`; `value FOLLOWING AND value FOLLOWING` | Hash and range |

Not supported: `ROWS BETWEEN UNBOUNDED PRECEDING AND value FOLLOWING` and
`ROWS BETWEEN value PRECEDING AND UNBOUNDED FOLLOWING`.

## Java Implementation

Moving-sum example. The storage object holds the running value plus a ring buffer of the last
`window_size` inputs.

```java
package com.company.udf;

import com.teradata.fnc.*;
import java.io.*;
import java.sql.*;

public class MovingSum {

    /* Intermediate storage: must be Serializable. */
    static class AgrStorage implements Serializable {
        long   currentValue;   /* running sum over the current window  */
        int    windowSize;     /* capacity of the ring buffer          */
        int    count;          /* rows currently in the window         */
        int    next;           /* write index                          */
        int    tptr;           /* trailing index                       */
        long[] data;           /* ring buffer of cached inputs         */

        AgrStorage(int windowSize) {
            this.windowSize = windowSize;
            /* Cumulative (-1) and reporting (-2) windows do not slide,
               so they need no ring buffer. */
            this.data = (windowSize > 0) ? new long[windowSize] : null;
        }
    }

    private static int inc(int i, int size) { return (i + 1) % size; }

    public static Long movingSum(Phase phase, Context[] context, long value)
        throws SQLException
    {
        AgrStorage s1 = null;

        /* Storage area 1 is valid in AGR_DETAIL, AGR_MOVINGTRAIL, and AGR_FINAL. */
        if (phase.getPhase() != Phase.AGR_INIT && phase.getPhase() != Phase.AGR_NODATA) {
            s1 = (AgrStorage) context[0].getObject(1);
        }

        switch (phase.getPhase()) {
            case Phase.AGR_INIT:
                s1 = new AgrStorage(context[0].getWindowSize());
                context[0].initCtx(s1);
                /* fall through to AGR_DETAIL to process the first row */

            case Phase.AGR_DETAIL:
                if (s1.windowSize < 0) {
                    /* cumulative or reporting: simple running sum */
                    s1.currentValue += value;
                } else {
                    /* moving window: drop the trailing value when full */
                    if (s1.count == s1.windowSize) {
                        s1.currentValue -= s1.data[s1.tptr];
                        s1.tptr = inc(s1.tptr, s1.windowSize);
                    } else {
                        s1.count++;
                    }
                    s1.currentValue += value;
                    s1.data[s1.next] = value;
                    s1.next = inc(s1.next, s1.windowSize);
                }
                break;

            /* Window aggregates do not combine. For a window-only UDF, fall
               through to AGR_FINAL rather than implementing combine logic. */
            case Phase.AGR_COMBINE:
            case Phase.AGR_FINAL:
                return s1.currentValue;

            case Phase.AGR_MOVINGTRAIL:
                /* No new value: shrink the window from the trailing edge. */
                s1.currentValue -= s1.data[s1.tptr];
                s1.tptr = inc(s1.tptr, s1.windowSize);
                break;

            case Phase.AGR_NODATA:
                return 0L;

            default:
                throw new SQLException("Invalid Phase", "U0005");
        }

        context[0].setObject(1, s1);
        return null;   /* ignored for INIT/DETAIL/MOVINGTRAIL */
    }
}
```

**Key rules:**
- The method is a **single `public static`** method; the first two parameters are always
  `Phase phase` and `Context[] context`, followed by the input parameters.
- Determine the phase with `phase.getPhase()`.
- In `AGR_INIT`, allocate with `initCtx`, capture `context[0].getWindowSize()`, and process the
  first row by falling through to `AGR_DETAIL`.
- Do **not** implement combine logic for a window-only UDF; `AGR_COMBINE` is not presented under
  `OVER (...)`.
- Implement `AGR_MOVINGTRAIL` only for moving windows; it supplies no new row values.
- The **intermediate storage object** must implement `java.io.Serializable` (not the UDF class).
- Fetch storage once with `getObject(1)` and write it back once with `setObject(1, s1)` after
  the switch (the `FINAL` and `NODATA` cases `return` first).

## Procedure: Build the JAR

```bash
javac com/company/udf/MovingSum.java
jar cf moving_sum.jar com/company/udf/MovingSum.class
```

## Procedure: Install the JAR

```sql
GRANT EXECUTE PROCEDURE ON SQLJ.INSTALL_JAR TO udf_developer_role;
GRANT EXECUTE PROCEDURE ON SQLJ.REMOVE_JAR  TO udf_developer_role;

DATABASE mydb;
CALL SQLJ.INSTALL_JAR('CJ!/path/to/moving_sum.jar', 'MOVING_SUM_JAR', 0);
```

## Procedure: Register the DDL

```sql
REPLACE FUNCTION mydb.moving_sum (value BIGINT)
RETURNS BIGINT
CLASS AGGREGATE (1000)
LANGUAGE JAVA
NO SQL
PARAMETER STYLE JAVA
EXTERNAL NAME 'MOVING_SUM_JAR:com.company.udf.MovingSum.movingSum(com.teradata.fnc.Phase, com.teradata.fnc.Context[], bigint) returns bigint';
```

The `CLASS AGGREGATE` clause makes Teradata invoke the method with the aggregate phase protocol
(passing `Phase` and `Context[]`); the window behavior comes from the `OVER (...)` clause at call
time, not from a separate class. Add an interim size, for example `CLASS AGGREGATE (1000)`, when
the row cache plus accumulators exceed the 64-byte default (max 64,000 bytes). For Java
aggregate UDFs the EXTERNAL NAME carries the **explicit method signature**
`(com.teradata.fnc.Phase, com.teradata.fnc.Context[], <sqltype>) returns <javatype>`.

## Procedure: Invoke With a Window

```sql
-- Cumulative window (running total)
SELECT id, mydb.moving_sum(value) OVER (
           PARTITION BY grp ORDER BY ts
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
FROM measurements;

-- Moving window (trailing 3 rows)
SELECT id, mydb.moving_sum(value) OVER (
           PARTITION BY grp ORDER BY ts
           ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
FROM measurements;
```

## Procedure: Verify and Uninstall

```sql
SELECT FunctionName, ExternalName, FunctionType, LanguageName
FROM DBC.FunctionsV
WHERE DatabaseName = 'mydb' AND FunctionName = 'moving_sum';

DROP FUNCTION mydb.moving_sum;
CALL SQLJ.REMOVE_JAR('MOVING_SUM_JAR', 0);
```

## Edge Cases

| Situation | Action |
|-----------|--------|
| `AGR_COMBINE` under `OVER (...)` | Not presented for window aggregates. For a window-only UDF, fall through to `AGR_FINAL`. |
| Moving window | Implement `AGR_MOVINGTRAIL`; maintain a ring buffer of `getWindowSize()` rows. |
| Cumulative or reporting window | `getWindowSize()` returns `-1` or `-2`; no ring buffer or `AGR_MOVINGTRAIL` needed. |
| Unsupported window type | `UNBOUNDED PRECEDING AND value FOLLOWING` and `value PRECEDING AND UNBOUNDED FOLLOWING` are rejected. Validate the window size to fail fast. |
| State must cross phases | The **intermediate storage object** must implement `Serializable`; all its fields must be serializable. |
| Group with no rows | Handle `Phase.AGR_NODATA`; return null or a sentinel. |
| Possible overflow | Pick a `RETURNS` type sized for the largest allowable window. |
| Storage larger than `interim_size` | Increase the `CLASS AGGREGATE (size)` value; `initCtx` cannot exceed it. |
| Teradata-managed platform (VantageCloud Lake or Enterprise) | External routines are supported, but direct `EXTERNAL NAME` install may be blocked. On Lake, install/list/uninstall with the `tdextroutine` CLI. On Enterprise, install on Compute Engine nodes or via a service request (not the EDW node). Identify the platform with `SELECT InfoData FROM DBC.DBCInfoV WHERE InfoKey = 'PLATFORM';`. |

## References


> **Access:** `skill_resource_read(action="read", skill="window-aggregate-udf-java", path="references/FILENAME")` — do NOT call `list`.

- [Window Aggregate UDFs (Java)](./references/window-aggregate-udfs.md): full phase flow, getWindowSize semantics, moving-window ring-buffer pattern, supported/unsupported window types, EXTERNAL NAME signature convention, and the complete worked example
