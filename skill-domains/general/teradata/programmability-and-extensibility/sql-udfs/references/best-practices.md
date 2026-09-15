# UDF Best Practices on Teradata

> **Source:** Teradata Vantage SQL Data Definition Language Syntax and Examples, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-Data-Definition-Language-Syntax-and-Examples  
> **Extraction date:** 2025-07  
> **Topics:** UDF Best Practices on Teradata

## Performance Guidelines

### Use INLINE TYPE 1
Always include `INLINE TYPE 1` for SQL scalar UDFs. This allows the optimizer to substitute the function body directly into the query plan, avoiding function-call overhead.

```sql
-- Good: inlinable
REPLACE FUNCTION db.my_func(x INTEGER)
RETURNS INTEGER
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
INLINE TYPE 1
RETURN (x * 2 + 1);
```

### Mark DETERMINISTIC When Possible
Deterministic functions enable the optimizer to cache results and reduce redundant computation. Only use `NOT DETERMINISTIC` when the function truly depends on external state.

### Prefer SQL UDFs Over External
SQL UDFs are:
- Faster (no context switch to UDF server)
- Inlinable by the optimizer
- Easier to maintain
- No compilation/deployment step

Use external UDFs only when SQL cannot express the logic.

### Avoid READS SQL DATA Unless Necessary
Functions that read data cannot be inlined and incur additional overhead. If possible, pass the needed data as parameters instead of reading from tables inside the UDF.

## Design Guidelines

### Naming Conventions

```
<domain>_<action>_<subject>
```

Examples:
- `fin_calc_compound_interest`
- `str_mask_email`
- `dt_business_days_between`
- `val_is_valid_phone`

### Parameter Naming
- Use descriptive names: `annual_rate` not `r`
- Include units in name when ambiguous: `amount_usd`, `duration_seconds`
- Prefix with `in_` for input clarity when names conflict with columns

### Database Organization
- Group UDFs by domain in dedicated databases: `udf_finance`, `udf_utils`, `udf_validation`
- Or use a single `udf_lib` database with naming conventions
- Keep test functions in a separate database: `udf_dev`

## Security Best Practices

### Principle of Least Privilege
```sql
-- Grant to roles, not individual users
GRANT EXECUTE FUNCTION ON udf_lib TO app_read_role;

-- Restrict DDL on UDF databases
GRANT CREATE FUNCTION ON udf_lib TO udf_developer_role;
```

### Input Validation
For external UDFs, always validate:
- NULL inputs (check null indicators)
- String lengths (prevent buffer overflow)
- Numeric ranges (prevent overflow/underflow)
- Invalid data patterns

### SQL Injection Prevention
For UDFs that construct dynamic SQL (rare but possible in MODIFIES SQL DATA functions):
- Never concatenate user input into SQL strings
- Use parameterized queries where possible
- Validate input patterns strictly

## Testing Strategies

### Unit Test Pattern
```sql
-- Test normal inputs
SELECT udf_lib.my_func(10, 20) AS result;
-- Expected: <known_value>

-- Test NULL handling
SELECT udf_lib.my_func(NULL, 20) AS result;
-- Expected: NULL (or defined behavior)

-- Test boundary values
SELECT udf_lib.my_func(2147483647, 1) AS result;
-- Expected: handle overflow gracefully

-- Test with actual table data
SELECT col1, udf_lib.my_func(col1, col2) AS computed
FROM test_table
WHERE expected_result IS NOT NULL;
```

### Performance Test Pattern
```sql
-- Compare UDF vs inline expression
EXPLAIN SELECT udf_lib.my_func(col1) FROM large_table;

-- Time comparison
SELECT COUNT(*) FROM large_table WHERE udf_lib.my_func(col1) > 0;
-- vs
SELECT COUNT(*) FROM large_table WHERE (col1 * 2 + 1) > 0;
```

## Migration and Versioning

### Versioning Strategy
- Use `REPLACE FUNCTION` for updates (atomic replacement)
- Document changes in comments or external changelog
- Test new version before replacing in production
- Keep previous version source code in version control

### Cross-Environment Deployment
```sql
-- Development
REPLACE FUNCTION udf_dev.my_func(...) ...;

-- Test after validation
REPLACE FUNCTION udf_test.my_func(...) ...;

-- Production deployment
REPLACE FUNCTION udf_prod.my_func(...) ...;
```

### Rollback Strategy
- Keep the previous version source in version control before `REPLACE FUNCTION`
- For critical UDFs, maintain a `_v1`/`_v2` naming backup during migration
- Test with `EXPLAIN` to verify optimizer behavior with the new version
- Monitor DBQL for performance regression after deployment

## Common Anti-Patterns

| Anti-Pattern | Problem | Better Approach |
|--------------|---------|-----------------|
| UDF in WHERE on large table | Full table scan, no index use | Use UDF in SELECT, filter on raw columns |
| UDF calling another UDF | Prevents inlining, compounds overhead | Combine logic into single function |
| Non-deterministic without need | Prevents optimization | Only use when truly non-deterministic |
| READS SQL DATA for lookups | Overhead per row | Pass lookup result as parameter |
| Giant monolithic UDF | Hard to test, maintain | Break into focused single-purpose functions |
| No NULL handling | Unexpected results | Always handle NULL explicitly |
| Missing SPECIFIC name | Hard to identify in traces | Always include a SPECIFIC clause |
| No input length checks (C UDFs) | Buffer overflow risk | Validate string lengths via FNC API |
