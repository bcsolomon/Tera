# java sp

```sql
-- ============================================================
-- Teradata Java Stored Procedure Template
-- Replace placeholders marked with <angle_brackets>
-- ============================================================

-- Step 1: Install the JAR (run once)
CALL SQLJ.INSTALL_JAR(
    'CJ!<path_to_jar>/<jar_file>.jar',   -- Client: CJ!, Server: SJ!
    '<jar_name>',
    0
);

-- Step 2: Register the procedure
REPLACE PROCEDURE <database_name>.<procedure_name> (
    IN    <in_param>    <sql_data_type>,
    OUT   <out_param>   <sql_data_type>
)
LANGUAGE JAVA
MODIFIES SQL DATA                  -- or NO SQL, CONTAINS SQL, READS SQL DATA
PARAMETER STYLE JAVA
EXTERNAL NAME '<jar_name>:<package>.<ClassName>.<methodName>';

-- Step 3: Grant access
GRANT EXECUTE PROCEDURE ON <database_name>.<procedure_name> TO <role_or_user>;

-- ============================================================
-- To update the JAR:
-- ============================================================
-- CALL SQLJ.REPLACE_JAR('CJ!<new_path>/<jar_file>.jar', '<jar_name>');

-- ============================================================
-- To remove:
-- ============================================================
-- DROP PROCEDURE <database_name>.<procedure_name>;
-- CALL SQLJ.REMOVE_JAR('<jar_name>', 0);

-- ============================================================
-- Java source template:
-- ============================================================
-- public class <ClassName> {
--     public static void <methodName>(
--         int <in_param>,           // IN: normal type
--         String[] <out_param>      // OUT: single-element array
--     ) throws java.sql.SQLException {
--         java.sql.Connection con =
--             java.sql.DriverManager.getConnection("jdbc:default:connection");
--         <out_param>[0] = "result";
--     }
-- }
```
