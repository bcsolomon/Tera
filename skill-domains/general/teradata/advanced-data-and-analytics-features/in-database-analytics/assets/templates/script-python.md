# script python

```sql
-- SCRIPT Table Operator Template: Python
-- Replace: <database>, <script_name>, <input_source>, <partition_col>

-- Step 1: Set search path (every session)
SET SESSION SEARCHUIFDBPATH = <database>;

-- Step 2: Install script (one-time)
CALL SYSUIF.INSTALL_FILE('<script_name>', '<script_name>.py',
                         'cz!/path/to/<script_name>.py');

-- Step 3: Execute
SELECT *
FROM SCRIPT (
    ON <input_source>
    PARTITION BY <partition_col>
    -- ORDER BY sort_col
    SCRIPT_COMMAND('python3 ./<database>/<script_name>.py')
    RETURNS('col1 INTEGER, col2 FLOAT, col3 VARCHAR(100)')
) AS results;
```
