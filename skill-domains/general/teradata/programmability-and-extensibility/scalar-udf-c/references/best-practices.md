# Scalar C UDF Best Practices

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** Scalar C UDF Best Practices

## Memory Management

- Scalar UDFs generally do not need dynamic memory allocation — use stack variables
- If dynamic allocation is needed, use `FNC_malloc`/`FNC_free` (redefined from standard `malloc`/`free`)
- Never allocate large buffers on the stack — UDF functions run with limited stack space
- For large string operations, use `FNC_malloc` and always `FNC_free` before returning
- `FNC_DefMem` is for aggregate UDFs only — do not use in scalar UDFs

## Input Validation

### Always Check Null Indicators

```c
/* MANDATORY: Check before accessing any parameter value */
if (*param_null == -1) {
    *result_null = -1;
    return;
}
```

Dereferencing a value pointer when its null indicator is -1 causes undefined behavior and likely crashes.

### Validate String Lengths

```c
/* Prevent buffer overflow when writing to result */
if (strlen(input) > 190) {  /* RETURNS VARCHAR(200) */
    strcpy(sqlstate, "U0003");
    strcpy(error_msg, "Input exceeds maximum length");
    return;
}
```

### Validate Numeric Ranges

```c
/* Check for overflow before arithmetic */
if (*input_val > 1073741823) {  /* INTEGER max / 2 */
    strcpy(sqlstate, "U0004");
    strcpy(error_msg, "Input too large — would overflow");
    return;
}
```

## Error Reporting

### Use sqlstate and error_msg

```c
/* Signal an error — do NOT crash, abort, or call exit() */
strcpy(sqlstate, "U0001");
strcpy(error_msg, "Clear description of the problem");
return;
```

- Use `"U0xxx"` codes for user-defined errors
- Always pair sqlstate with a descriptive error_msg
- Return immediately after setting an error

### Never Crash

| Bad Practice | What Happens | Better Approach |
|---|---|---|
| `exit(1)` | Kills the UDF server process | Use sqlstate/error_msg |
| `abort()` | Core dump | Use sqlstate/error_msg |
| `assert()` | Aborts in debug builds | Check and report via sqlstate |
| Null pointer dereference | Segfault | Check null indicators first |

## Compilation

### Let the Database Compile

C source is uploaded and compiled within the database. Do NOT:
- Compile with `gcc` on a client or build server
- Use `SYSUIF.INSTALL_FILE` (that's for Script Table Operator files, not UDFs)
- Assume specific compiler flags or versions

### Keep Source Code in Version Control

`SHOW FUNCTION` only displays the SQL DDL, not the C source code. Always maintain C source files in your version control system.

### Use REPLACE FUNCTION for Updates

```sql
REPLACE FUNCTION mydb.my_function (...)
RETURNS ...
LANGUAGE C NO SQL DETERMINISTIC
EXTERNAL NAME 'CS!my_function!my_function.c'
PARAMETER STYLE SQL;
```

REPLACE is atomic — it updates the DDL and recompiles the source in one operation.

## Performance

### When to Use C vs SQL UDFs

| Factor | C Scalar UDF | SQL Scalar UDF |
|---|---|---|
| Complex algorithms | Preferred | Not suitable |
| Simple expressions | Overhead not worth it | Preferred (INLINE TYPE 1) |
| String manipulation | Good for complex logic | Limited to SQL functions |
| Math operations | Preferred for heavy computation | Fine for simple math |
| Context switch cost | Per-invocation overhead | None (inlined) |

Use SQL UDFs when the logic can be expressed in a single SQL expression — they avoid the UDF server context switch.

### Minimize Work Per Call

- Pre-compute constants outside the function or at the top
- Avoid unnecessary string copies — write directly to the result buffer
- Use efficient algorithms — every scalar UDF call adds per-row overhead

## Security

- C UDFs run in a sandboxed UDF server process
- File system and network access may be restricted by site policy
- Never construct dynamic SQL from UDF input parameters
- Validate all inputs to prevent buffer overflows
- Use `sqlstate`/`error_msg` for error reporting — never expose internal state

## Privileges

- The UDF creator needs `CREATE FUNCTION` on the target database
- The creator receives `EXECUTE FUNCTION` automatically — no explicit GRANT needed
- Use `GRANT EXECUTE FUNCTION` only when granting access to other users or roles

## Naming Conventions

| Element | Convention | Example |
|---|---|---|
| SQL function name | lowercase with underscores | `safe_divide` |
| C function name | Must match SQL EXTERNAL NAME exactly | `safe_divide` |
| Source file name | Match function name, `.c` extension | `safe_divide.c` |
| SPECIFIC name | Function name + version suffix | `safe_divide_v1` |

## Anti-Patterns

| Anti-Pattern | Problem | Better Approach |
|---|---|---|
| Client-side `gcc` compilation | Wrong compiler/headers/architecture | Let database compile with `CS!` prefix |
| Using `SYSUIF.INSTALL_FILE` for UDFs | Files placed where UDF subsystem can't access | Not for UDFs — only for Script Table Operator |
| No null checks | Segfault on NULL inputs | Always check `*paramN_null == -1` |
| Stack-allocated large buffers | Stack overflow | Use `FNC_malloc` for large allocations |
| Hardcoded string buffer sizes | Buffer overflow on longer inputs | Use size macros or validate lengths |
| Silent failures (no error reporting) | Impossible to debug | Set `sqlstate` and `error_msg` on errors |
| Using `printf`/`fprintf` | Output goes nowhere in UDF server | Use `FNC_Trace_String` for debugging |
| Not setting `*result_null = 0` | Result appears as NULL | Always set result_null explicitly |
| C function name differs from EXTERNAL NAME | "Symbol not found" error | Names must match exactly |
