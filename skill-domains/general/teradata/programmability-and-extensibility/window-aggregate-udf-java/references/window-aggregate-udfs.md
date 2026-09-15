# Window Aggregate UDFs (Java) Reference

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** Window Aggregate UDFs (Java) Reference

Authoritative basis: Teradata SQL External Routine Programming v20.00, window aggregate (OLAP
aggregate) sections. A Java window aggregate UDF is an aggregate UDF (`CLASS AGGREGATE`) that is
also valid when invoked under an OLAP window specification (`OVER (...)`).

## 1. Relationship to Plain Aggregates

A single Java aggregate method can serve as both a `GROUP BY` aggregate and a window aggregate.
There is no separate DDL class for windows; the function is registered with `CLASS AGGREGATE`
(optionally `CLASS AGGREGATE (interim_size)`), and the window behavior is determined by the
`OVER (...)` clause supplied at call time.

The method is a single `public static` method whose first two parameters are
`com.teradata.fnc.Phase phase` and `com.teradata.fnc.Context[] context`, followed by the input
parameters. The differences from a plain aggregate are in the phase set and in reading the
window size from the context.

## 2. Window Phase Flow

| `phase.getPhase()` | Applies to | Notes |
|--------------------|-----------|-------|
| `Phase.AGR_INIT` | all | Once per partition. `initCtx`, capture `getWindowSize()`, process first row, fall through to `AGR_DETAIL`. |
| `Phase.AGR_DETAIL` | all | Once per forward-row progression. Accumulate the input. |
| `Phase.AGR_COMBINE` | not window | Not presented under `OVER (...)`. For a window-only UDF, fall through to `AGR_FINAL` or raise an error. |
| `Phase.AGR_FINAL` | all | Compute and return the result for the current window position. |
| `Phase.AGR_NODATA` | all | No data at all in the set. |
| `Phase.AGR_MOVINGTRAIL` | moving only | Trailing-row trigger as the forward pointer reaches the end of the partition. No new values; shrink the window. |

A plain `GROUP BY` aggregate uses `AGR_INIT`/`AGR_DETAIL`/`AGR_COMBINE`/`AGR_FINAL`/`AGR_NODATA`.
A window aggregate replaces `AGR_COMBINE` (not applicable) with `AGR_MOVINGTRAIL` (moving
windows only).

## 3. Reading the Window Size

In `AGR_INIT`, call `context[0].getWindowSize()`:

| Returned value | Window type |
|----------------|-------------|
| `-1` | Cumulative |
| `-2` | Reporting |
| positive (`post - pre + 1`) | Moving |

The authoritative Java window aggregate worked example captures the window size this way and
stores it in the Serializable intermediate storage object. (Note: the
`com.teradata.fnc.Context` API page marks the window accessors as reserved, yet the worked
example actively uses `getWindowSize()`; follow the worked example.)

## 4. Intermediate Storage

State crosses phases through `context[0]`, identical to plain Java aggregates:

| Method | Purpose |
|--------|---------|
| `initCtx(Object obj)` / `initCtx(int length)` | In `AGR_INIT`, allocate and initialize the storage. Cannot exceed `interim_size` from `CLASS AGGREGATE`. |
| `getObject(int n)` / `setObject(int n, Object obj)` | Read/write the storage as a Serializable object (`n=1` is the per-partition storage area). |
| `getBytes(int n)` / `setBytes(int n, byte[] data)` | Read/write the storage as a raw byte array (use with `ByteBuffer` for performance). |

The storage object must implement `java.io.Serializable`, and every field it carries (including
any ring buffer array) must be serializable.

## 5. Supported and Unsupported Window Types

### Reporting window
`ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`. `getWindowSize()` returns `-2`. Hash
partitioning only.

### Cumulative window
`ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`, or
`ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING`. `getWindowSize()` returns `-1`. Hash
partitioning only.

### Moving window
Supported groups:
- `value PRECEDING AND CURRENT ROW`
- `CURRENT ROW AND value FOLLOWING`
- `value PRECEDING AND value FOLLOWING`
- `value PRECEDING AND value PRECEDING`
- `value FOLLOWING AND value FOLLOWING`

`getWindowSize()` returns `post - pre + 1`. Hash and range (value) partitioning are both
allowed.

### Not supported
- `ROWS BETWEEN UNBOUNDED PRECEDING AND value FOLLOWING`
- `ROWS BETWEEN value PRECEDING AND UNBOUNDED FOLLOWING`

Vantage does not check that a UDF is used with a specific window type. Validate the window size
in `AGR_INIT` and reject unsupported types. Size the return type so the largest permitted window
cannot overflow it.

## 6. Moving-Window Ring Buffer Pattern

For a moving sum, maintain a ring buffer of the last `window_size` inputs plus a running
accumulator inside the Serializable storage object:

```java
/* AGR_INIT:
     s1 = new AgrStorage(context[0].getWindowSize());
     context[0].initCtx(s1);
     // fall through

   AGR_DETAIL (moving, windowSize > 0):
     if (count == windowSize) {            // window full: drop trailing
         currentValue -= data[tptr];
         tptr = (tptr + 1) % windowSize;
     } else {
         count++;
     }
     currentValue += value;
     data[next] = value;
     next = (next + 1) % windowSize;

   AGR_DETAIL (cumulative/reporting, windowSize < 0):
     currentValue += value;

   AGR_MOVINGTRAIL:                          // no new value; shrink window
     currentValue -= data[tptr];
     tptr = (tptr + 1) % windowSize;

   AGR_FINAL:
     return currentValue; */
```

Cumulative and reporting windows do not slide, so they never receive `AGR_MOVINGTRAIL`; a single
running accumulator is sufficient.

## 7. DDL and Invocation

```sql
REPLACE FUNCTION mydb.moving_sum (value BIGINT)
RETURNS BIGINT
CLASS AGGREGATE (1000)
LANGUAGE JAVA
NO SQL
PARAMETER STYLE JAVA
EXTERNAL NAME 'MOVING_SUM_JAR:com.company.udf.MovingSum.movingSum(com.teradata.fnc.Phase, com.teradata.fnc.Context[], bigint) returns bigint';
```

The EXTERNAL NAME carries the explicit method signature
`(com.teradata.fnc.Phase, com.teradata.fnc.Context[], <sqltype>) returns <javatype>`, the same
convention as a plain Java aggregate UDF.

```sql
SELECT id,
       mydb.moving_sum(value) OVER (
           PARTITION BY grp ORDER BY ts
           ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS moving_sum
FROM measurements;
```

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Error or wrong result in `AGR_COMBINE` | Implemented combine logic for a window-only UDF, or used as `GROUP BY` | For window use, fall through to `AGR_FINAL`; for dual use, implement a correct combine |
| Wrong moving-window result | Ring buffer not draining on `AGR_MOVINGTRAIL` | Subtract the trailing value and advance `tptr` each `AGR_MOVINGTRAIL` |
| `NotSerializableException` | Storage object or a field is not Serializable | Make the storage class and all fields `Serializable` |
| Error on a particular `OVER` clause | Unsupported window type | Reject `UNBOUNDED PRECEDING AND value FOLLOWING` and `value PRECEDING AND UNBOUNDED FOLLOWING` |
| `getWindowSize()` returns a negative value unexpectedly | Cumulative (`-1`) or reporting (`-2`) window | Branch on the sign before sizing the ring buffer |
| Numeric overflow on large windows | `RETURNS` type too narrow | Widen the result type |
