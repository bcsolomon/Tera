# taule udf

```sql
-- ============================================================
-- Teradata Table UDF Template
-- Replace placeholders marked with <angle_brackets>
-- ============================================================

REPLACE FUNCTION <database_name>.<function_name> (
    <param1_name>  <param1_data_type>
)
RETURNS TABLE (
    <output_col1>  <output_col1_type>,
    <output_col2>  <output_col2_type>,
    <output_col3>  <output_col3_type>
)
LANGUAGE SQL
READS SQL DATA              -- Table UDFs typically read data
DETERMINISTIC
COLLATION INVOKER
RETURN (
    SELECT <col1>, <col2>, <col3>
    FROM <source_table>
    WHERE <filter_column> = <param1_name>
);

-- ============================================================
-- Grant execute privilege
-- ============================================================
GRANT EXECUTE FUNCTION ON <database_name>.<function_name> TO <role_or_user>;

-- ============================================================
-- Example usage (Table UDFs are used in FROM clause with TABLE keyword)
-- ============================================================
-- SELECT * FROM TABLE(<database_name>.<function_name>('param_value')) AS t;
```
