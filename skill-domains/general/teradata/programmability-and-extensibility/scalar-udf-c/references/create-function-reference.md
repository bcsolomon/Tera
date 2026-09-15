# CREATE FUNCTION Reference — External Form (C/C++/Java)

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** CREATE FUNCTION Reference: External Form (C/C++/Java)

> Source: Teradata SQL Data Definition Language — Detailed Topics,
> CREATE FUNCTION and REPLACE FUNCTION (External Form), v20.00

---

## Full Clause Order

```sql
{CREATE | REPLACE} FUNCTION [database_name.]function_name
    ([parameter_name] parameter_type [CHARACTER SET {UNICODE|LATIN}] [,...])
RETURNS {return_type [CHARACTER SET {UNICODE|LATIN}]
        | TABLE (col_name type [,...])}
[SPECIFIC specific_function_name]
[LANGUAGE {C | CPP | JAVA}]
[{NO SQL | CONTAINS SQL | READS SQL DATA | MODIFIES SQL DATA}]
[{CALLED ON NULL INPUT | RETURNS NULL ON NULL INPUT}]
[PARAMETER STYLE {SQL | TD_GENERAL | JAVA}]
[{DETERMINISTIC | NOT DETERMINISTIC}]
[COLLATION {INVOKER | DEFINER}]
EXTERNAL NAME '<routine_string>';
```

---

## Clause Descriptions

| Clause | Default | Notes |
|--------|---------|-------|
| `SPECIFIC name` | none | Unique name within the database. Required for overloads and `CREATE CAST`/`ORDERING` references. |
| `LANGUAGE C \| CPP \| JAVA` | — | Required. C and CPP share the same `EXTERNAL NAME` format. |
| `NO SQL` | YES for external | External routines default to `NO SQL`. Specify higher access only when needed. |
| `CALLED ON NULL INPUT` | YES | UDF is called regardless of NULL inputs. Use `PARAMETER STYLE SQL` to check indicators. |
| `RETURNS NULL ON NULL INPUT` | — | Teradata returns NULL without calling the UDF when any input is NULL. Simpler but inflexible. |
| `PARAMETER STYLE SQL` | — | Full indicator-based signature. Required for safe NULL handling in C/C++. |
| `PARAMETER STYLE TD_GENERAL` | — | Simplified signature (no null indicators). Prototype use only — does not handle NULLs. |
| `PARAMETER STYLE JAVA` | — | Java boxed types; null represented by `null` reference. |
| `DETERMINISTIC` | — | Optimizer may cache results for a given input. Use for pure functions. |
| `NOT DETERMINISTIC` | — | Results may differ per call (time, random, session-dependent). |
| `COLLATION INVOKER` | YES | Character comparisons use the calling session's collation. |
| `COLLATION DEFINER` | — | Character comparisons use the function creator's session collation cross-session. |
| `CHARACTER SET UNICODE` | per session | On CHAR/VARCHAR params/return. Use for multi-byte or international data. |
| `CHARACTER SET LATIN` | per session | On CHAR/VARCHAR params/return. Default on most Teradata systems. |

---

## SPECIFIC Clause — Overload Management

The `SPECIFIC` name uniquely identifies one overload. Without it Teradata generates
an internal name; with it you control the name and can drop individual overloads.

### Create two overloads

```sql
CREATE FUNCTION mydb.add (a INTEGER, b INTEGER)
RETURNS INTEGER
SPECIFIC add_int_impl
LANGUAGE C NO SQL PARAMETER STYLE TD_GENERAL DETERMINISTIC
EXTERNAL NAME 'CS!add_int!udf_src/add_int.c';

CREATE FUNCTION mydb.add (a FLOAT, b FLOAT)
RETURNS FLOAT
SPECIFIC add_float_impl
LANGUAGE C NO SQL PARAMETER STYLE TD_GENERAL DETERMINISTIC
EXTERNAL NAME 'CS!add_float!udf_src/add_float.c';
```

### Drop one overload (other stays)

```sql
DROP SPECIFIC FUNCTION mydb.add_float_impl;
```

### Drop all overloads

```sql
DROP FUNCTION mydb.add;
```

### Grant on a specific overload

```sql
GRANT EXECUTE ON SPECIFIC FUNCTION mydb.add_int_impl TO app_role;
```

---

## CHARACTER SET on Parameters

Use when the function handles multi-byte (Unicode) or explicitly Latin character data:

```sql
CREATE FUNCTION mydb.to_upper (s CHAR(100) CHARACTER SET UNICODE)
RETURNS CHAR(100) CHARACTER SET UNICODE
SPECIFIC to_upper_unicode_impl
LANGUAGE C NO SQL PARAMETER STYLE SQL CALLED ON NULL INPUT DETERMINISTIC
EXTERNAL NAME 'CS!to_upper!udf_src/to_upper.c';
```

Omitting `CHARACTER SET` inherits the session default (usually LATIN on on-premises systems).
Mismatch between caller's collation and function's CHARACTER SET causes implicit CAST overhead.

---

## Scalar Function Body Patterns

Four patterns cover all cases. `IsNull = -1`, `IsNotNull = 0`.

### Pattern 1 — Success (normal return)

```c
*result     = computed_value;
*result_ind = IsNotNull;          /* = 0 */
return;
/* Do NOT set sqlstate — leave at "00000" (default success) */
```

### Pattern 2 — Return NULL (SQL style only)

```c
*result_ind = IsNull;             /* = -1 */
return;
/* Do NOT write *result — it is ignored when result_ind == IsNull */
/* Do NOT set sqlstate — returning NULL is not an error */
```

### Pattern 3 — Signal an error (result is discarded)

```c
strcpy(sqlstate, "38001");                              /* 38001–38999: user-defined error */
strcpy((char *)error_message, "Short description.");    /* max 256 chars */
return;
/* result and result_ind are IGNORED when sqlstate is an error code */
```

### Pattern 4 — Signal a warning (result IS used)

```c
*result     = computed_value;
*result_ind = IsNotNull;
strcpy(sqlstate, "01H01");                              /* 01H01–01H99: user warning */
strcpy((char *)error_message, "Warning description.");
return;
/* result IS read despite the non-zero sqlstate */
```

---

## sqlstate Code Reference

| Code range | Category | Result used? | Notes |
|-----------|----------|-------------|-------|
| `"00000"` | Success | Yes | Default — never set explicitly on success |
| `"01H01"`–`"01H99"` | User-defined warning | **Yes** | Write result before setting sqlstate |
| `"22001"` | String data right truncation | No | Standard SQL data exception |
| `"22003"` | Numeric value out of range | No | Standard SQL data exception |
| `"22004"` | NULL value not allowed | No | Use when NULL input is rejected |
| `"22012"` | Division by zero | No | Standard SQL data exception |
| `"38001"`–`"38999"` | User-defined error | No | User-assignable range |

> Use `"38xxx"` for domain errors. Use `"22xxx"` only when the condition exactly
> matches the standard SQL data-exception meaning.

---

## Body Restrictions

These operations are **forbidden** inside any C UDF body. Violating them can crash
the AMP or corrupt results across rows:

| Forbidden | Consequence |
|-----------|-------------|
| `exit()`, `abort()`, `_exit()` | Terminates the entire AMP vproc |
| `printf()`, `fprintf()`, `fopen()`, `fwrite()`, `fread()` | I/O is unavailable inside the DBS engine |
| Static or global variables used for state | UDF calls are independent; statics persist across rows and corrupt results |
| `malloc()` without matching `free()` | Memory leak in the AMP |
| Dereferencing a NULL-indicated pointer | Segfault on the AMP — always check indicator first |
| Infinite loops or unbounded computation | UDF called once per qualifying row; blocks AMP throughput |

**Safe C library calls:** `strcpy`, `strlen`, `strcmp`, `strncpy`, `memcpy`, `memset`,
`sprintf`, `strtol`, `strtod`, `abs`, `fabs`, and standard math functions.

---

*Reference: Teradata SQL External Routine Programming, v20.00 (B035-1147)*
