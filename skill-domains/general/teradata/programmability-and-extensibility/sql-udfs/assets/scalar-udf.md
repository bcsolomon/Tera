# scalar udf

```sql
-- ============================================================
-- Teradata Scalar UDF Template
-- Replace placeholders marked with <angle_brackets>
-- ============================================================

REPLACE FUNCTION <database_name>.<function_name> (
    <param1_name>  <param1_data_type>,
    <param2_name>  <param2_data_type>
)
RETURNS <return_data_type>
SPECIFIC <specific_name>
LANGUAGE SQL
CONTAINS SQL                -- Change to READS SQL DATA if querying tables
DETERMINISTIC               -- Change to NOT DETERMINISTIC if output varies
COLLATION INVOKER
INLINE TYPE 1
RETURN (
    -- Your SQL expression here using param1_name, param2_name
    <sql_expression>
);

-- ============================================================
-- Grant execute privilege
-- ============================================================
GRANT EXECUTE FUNCTION ON <database_name>.<function_name> TO <role_or_user>;

-- ============================================================
-- Example usage
-- ============================================================
-- SELECT <database_name>.<function_name>(column1, column2) FROM my_table;
```
