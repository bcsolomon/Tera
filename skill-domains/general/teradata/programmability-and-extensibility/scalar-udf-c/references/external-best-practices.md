# External UDF Best Practices

> **Source:** Teradata Vantage SQL External Routine Programming, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-External-Routine-Programming  
> **Extraction date:** 2025-07  
> **Topics:** External UDF Best Practices

## C/C++ Specific

### Memory Management
- **Always use `FNC_DefMem`** for aggregate interim storage — automatically freed
- Use `FNC_malloc`/`FNC_free` for general allocations (or `malloc`/`free` — they're redefined)
- Never allocate large buffers on the stack in UDF functions

### Input Validation
- **Always check null indicators** (`*paramN_null == -1`) before accessing values
- Validate string lengths before copying — prevent buffer overflows
- Validate numeric ranges to prevent overflow/underflow
- Use `sqlstate`/`error_msg` for error reporting — never crash or abort

### Aggregate UDF Testing
- Test with multi-AMP data distribution to verify COMBINE phase correctness
- Test with empty groups (AGR_NODATA phase)
- Test with all-NULL inputs in the DETAIL phase
- Verify partial result serialization in COMBINE matches your accumulator format

### Compilation
- Always compile with `-shared -fPIC` on Linux
- Use `-I/opt/teradata/client/include` for the `sqltypes_td.h` header path
- Test on the same OS/architecture as the Teradata nodes

## Java Specific

### Null Handling
- Use wrapper classes (`Integer`, `Double`) instead of primitives when parameters can be NULL
- Return `null` to produce a SQL NULL result
- Specify nullable types in EXTERNAL NAME when needed

### JAR Management
- Package dependencies in the same tar.gz archive
- Use `SQLJ.INSTALL_JAR('CJ!path/to/file.jar', 'alias', 0)` for Java UDFs and JXSPs (`SYSUIF.INSTALL_FILE` is only for the SCRIPT table operator)
- Verify class names are case-sensitive matches

## General

### Performance
- Prefer SQL UDFs when SQL can express the logic — no context switch overhead
- External UDFs incur UDF server process overhead per invocation
- Minimize memory allocation in DETAIL phase (allocate once in INIT)

### Security
- External UDFs run sandboxed in the UDF server process
- File system and network access may be restricted by site policy
- Validate all inputs to prevent buffer overflows in C code
- Never construct dynamic SQL from UDF inputs

### Deployment
- Use REPLACE FUNCTION for atomic updates
- Test on development systems before production
- Keep source code in version control — `SHOW FUNCTION` only shows DDL, not C source
- Document the compilation and packaging steps

## Anti-Patterns

| Anti-Pattern | Problem | Better Approach |
|---|---|---|
| `malloc()` for aggregate state | Memory leak risk | Use `FNC_DefMem` — auto-freed |
| No null checks in DETAIL phase | Segfault on NULL inputs | Always check `*input_null == -1` |
| Stack-allocated large buffers | Stack overflow | Use `FNC_malloc` for large allocations |
| COMBINE ignores NULLs | Wrong aggregate results | Handle `*partial_null == -1` |
| Hardcoded string sizes | Buffer overflow on longer inputs | Use size macros from sqltypes_td.h |
| No error reporting | Silent failures | Set `sqlstate` and `error_msg` on errors |
