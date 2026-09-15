# sql sp

```sql
-- ============================================================
-- Teradata SQL Stored Procedure Template
-- Replace placeholders marked with <angle_brackets>
-- ============================================================

REPLACE PROCEDURE <database_name>.<procedure_name> (
    IN    <in_param>    <data_type>,
    OUT   <out_param>   <data_type>,
    INOUT <inout_param> <data_type>
)
SQL SECURITY DEFINER              -- or CREATOR, OWNER, INVOKER
-- DYNAMIC RESULT SETS 1          -- Uncomment if returning result sets
BEGIN
    -- ========== Variable Declarations ==========
    DECLARE v_sqlcode INTEGER DEFAULT 0;
    DECLARE v_done    INTEGER DEFAULT 0;

    -- ========== Condition Handlers ==========
    DECLARE CONTINUE HANDLER FOR SQLSTATE '02000'   -- No data found
        SET v_done = 1;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        SET <out_param> = 'ERROR';
        -- Log error if needed:
        -- INSERT INTO error_log VALUES (CURRENT_TIMESTAMP, 'Error in <procedure_name>');
    END;

    -- ========== Procedure Body ==========

    -- Your logic here
    SET <out_param> = <expression>;

END;

-- ============================================================
-- Grant execute privilege
-- ============================================================
GRANT EXECUTE PROCEDURE ON <database_name>.<procedure_name> TO <role_or_user>;

-- ============================================================
-- Example call
-- ============================================================
-- CALL <database_name>.<procedure_name>(input_val, output_var, inout_var);
```
