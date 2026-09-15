# SQL Stored Procedures (SPL) — Complete Reference

> **Source:** Teradata Vantage SQL Stored Procedures and Embedded SQL, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-Stored-Procedures-and-Embedded-SQL  
> **Extraction date:** 2025-07  
> **Topics:** SQL Stored Procedures (SPL): Complete Reference

## CREATE/REPLACE PROCEDURE Syntax

```sql
CREATE PROCEDURE database_name.procedure_name (
    [IN | OUT | INOUT] param1 data_type,
    [IN | OUT | INOUT] param2 data_type
    -- Up to 256 parameters
)
[SQL SECURITY {DEFINER | CREATOR | OWNER | INVOKER}]
[DYNAMIC RESULT SETS n]
[<SPL options>]
BEGIN
    -- declarations (must come first in each BEGIN/END block)
    -- statements
END;
```

Use `REPLACE PROCEDURE` to create or overwrite an existing procedure atomically.

### SPL Options

| Option | Description |
|---|---|
| `CONTAINS SQL` | Procedure contains SQL but does not read/modify data |
| `READS SQL DATA` | Procedure reads from tables |
| `MODIFIES SQL DATA` | Procedure inserts/updates/deletes data |

## Variable Declarations

Declarations must appear at the top of each BEGIN/END block, before any executable statements.

```sql
DECLARE variable_name data_type [DEFAULT value];
DECLARE v_count INTEGER DEFAULT 0;
DECLARE v_name VARCHAR(100) DEFAULT '';
DECLARE v_amount DECIMAL(18,2);
DECLARE v_date DATE DEFAULT CURRENT_DATE;
```

### Supported Data Types

All Teradata SQL data types are supported: INTEGER, SMALLINT, BIGINT, BYTEINT, DECIMAL(m,n), FLOAT, REAL, CHAR(n), VARCHAR(n), DATE, TIME, TIMESTAMP, INTERVAL, CLOB, BLOB, PERIOD, NUMBER, JSON.

## Control Flow

### IF / ELSEIF / ELSE

```sql
IF v_amount > 10000 THEN
    SET v_tier = 'Gold';
ELSEIF v_amount > 5000 THEN
    SET v_tier = 'Silver';
ELSE
    SET v_tier = 'Bronze';
END IF;
```

### CASE (Searched)

```sql
CASE
    WHEN v_status = 'A' THEN
        SET v_desc = 'Active';
    WHEN v_status = 'I' THEN
        SET v_desc = 'Inactive';
    ELSE
        SET v_desc = 'Unknown';
END CASE;
```

### WHILE Loop

```sql
DECLARE v_i INTEGER DEFAULT 1;
WHILE v_i <= 100 DO
    INSERT INTO numbers_table VALUES (v_i);
    SET v_i = v_i + 1;
END WHILE;
```

### FOR Loop (Cursor-Based)

The FOR loop implicitly declares a cursor, opens it, fetches each row, and closes it:

```sql
FOR rec AS
    SELECT employee_id, salary FROM employees WHERE dept_id = in_dept
DO
    -- Access columns as rec.employee_id, rec.salary
    IF rec.salary > 100000 THEN
        UPDATE employees SET bonus = rec.salary * 0.10
        WHERE employee_id = rec.employee_id;
    END IF;
END FOR;
```

### LOOP / LEAVE

```sql
label1: LOOP
    FETCH cur1 INTO v_id, v_name;
    IF SQLSTATE = '02000' THEN
        LEAVE label1;
    END IF;
    -- process row
END LOOP label1;
```

### REPEAT / UNTIL

```sql
REPEAT
    SET v_counter = v_counter + 1;
    -- process
UNTIL v_counter >= v_max
END REPEAT;
```

### ITERATE (Continue to Next Iteration)

```sql
label1: WHILE v_i < 100 DO
    SET v_i = v_i + 1;
    IF MOD(v_i, 2) = 0 THEN
        ITERATE label1;  -- skip even numbers
    END IF;
    INSERT INTO odd_numbers VALUES (v_i);
END WHILE label1;
```

### Labels

Any BEGIN/END, LOOP, WHILE, FOR, or REPEAT block can be labeled. Labels are required for LEAVE and ITERATE:

```sql
outer_block: BEGIN
    inner_loop: LOOP
        IF condition THEN LEAVE inner_loop; END IF;
        IF fatal THEN LEAVE outer_block; END IF;
    END LOOP inner_loop;
END outer_block;
```

## Cursor Operations

### Declaring Cursors

```sql
-- Static cursor
DECLARE cur1 CURSOR FOR
    SELECT col1, col2 FROM table_name WHERE condition;

-- Scroll cursor (allows repositioning)
DECLARE cur2 SCROLL CURSOR FOR
    SELECT col1 FROM table_name;
```

### Cursor with Result Set Return

Five return modes:

```sql
-- 1. Normal (no return — SP reads data only)
DECLARE cur1 CURSOR FOR SELECT ...;

-- 2. Return Only to Caller (SP cannot read, caller gets data)
DECLARE cur2 CURSOR WITH RETURN ONLY TO CALLER FOR SELECT ...;

-- 3. Return Only to Client (SP cannot read, client gets data, skips intermediate SPs)
DECLARE cur3 CURSOR WITH RETURN ONLY FOR SELECT ...;

-- 4. Return to Caller (SP can read AND send to caller)
DECLARE cur4 CURSOR WITH RETURN TO CALLER FOR SELECT ...;

-- 5. Return to Client (SP can read AND send to client)
DECLARE cur5 CURSOR WITH RETURN FOR SELECT ...;
```

### Open / Fetch / Close

```sql
OPEN cur1;

fetch_loop: LOOP
    FETCH cur1 INTO v_col1, v_col2;
    IF SQLSTATE = '02000' THEN   -- no more data
        LEAVE fetch_loop;
    END IF;
    -- process v_col1, v_col2
END LOOP fetch_loop;

CLOSE cur1;
```

### Scroll Cursor Positioning

```sql
FETCH FIRST FROM cur2 INTO v_val;
FETCH LAST FROM cur2 INTO v_val;
FETCH NEXT FROM cur2 INTO v_val;
FETCH PRIOR FROM cur2 INTO v_val;
FETCH ABSOLUTE 5 FROM cur2 INTO v_val;
FETCH RELATIVE -2 FROM cur2 INTO v_val;
```

### Allocating Result Sets from Called Procedures

When a called procedure returns dynamic result sets:

```sql
CALL sub_procedure();

-- Check if result sets are available (SQLSTATE '0100C')
IF SQLSTATE = '0100C' THEN
    alloc_loop: LOOP
        ALLOCATE rs_cursor CURSOR FOR PROCEDURE sub_procedure;
        IF SQLSTATE = '02001' THEN   -- no more result sets
            LEAVE alloc_loop;
        END IF;

        fetch_loop: LOOP
            FETCH rs_cursor INTO v_col1, v_col2;
            IF SQLSTATE = '02000' THEN
                CLOSE rs_cursor;
                LEAVE fetch_loop;
            END IF;
            -- process row
        END LOOP fetch_loop;
    END LOOP alloc_loop;
END IF;
```

### SQLSTATE Codes for Cursors

| SQLSTATE | Meaning |
|---|---|
| `02000` | No data found (end of cursor) |
| `02001` | No more result sets to allocate |
| `0100C` | Called procedure has result sets available |
| `0100D` | Additional result sets remain |

## Dynamic Result Sets

To return result sets to the caller/client:

```sql
REPLACE PROCEDURE find_by_store (IN in_store INTEGER)
DYNAMIC RESULT SETS 1
BEGIN
    DECLARE stmt_str VARCHAR(500);
    DECLARE rs_cursor CURSOR WITH RETURN ONLY FOR stmt1;

    SET stmt_str = 'SELECT store, item, onhand FROM inventory'
                || ' WHERE store = ? ORDER BY store, item';
    PREPARE stmt1 FROM stmt_str;
    OPEN rs_cursor USING in_store;
    -- Do NOT close the cursor — it returns to the caller
    DEALLOCATE PREPARE stmt1;
END;
```

Multiple result sets: use multiple cursors. The order they are opened determines the order they are returned.

## Condition Handling

### DECLARE HANDLER

```sql
-- Continue handler: execute action, then resume at next statement
DECLARE CONTINUE HANDLER FOR SQLSTATE '02000'
    SET v_done = 1;

-- Exit handler: execute action, then exit current BEGIN/END block
DECLARE EXIT HANDLER FOR SQLEXCEPTION
BEGIN
    INSERT INTO error_log VALUES (CURRENT_TIMESTAMP, 'Error occurred');
    SET out_status = -1;
END;

-- Handler for specific condition name
DECLARE divide_by_zero CONDITION FOR SQLSTATE '22012';
DECLARE EXIT HANDLER FOR divide_by_zero
    SET out_result = 0;
```

### Handler Target Conditions

| Condition | Matches |
|---|---|
| `SQLSTATE 'xxxxx'` | Specific SQLSTATE code |
| `SQLEXCEPTION` | Any error (SQLSTATE class 02-FF except 00, 01, 02) |
| `SQLWARNING` | Any warning (SQLSTATE class '01') |
| `NOT FOUND` | No data (SQLSTATE class '02') |
| `condition_name` | User-declared condition |

### Nested Handlers

Handlers can be nested in inner BEGIN/END blocks. An inner handler overrides an outer handler for the same condition within its scope:

```sql
BEGIN
    DECLARE EXIT HANDLER FOR SQLSTATE '23505'
        SET v_status = 'outer duplicate';
    -- outer statements...

    L1: BEGIN
        DECLARE CONTINUE HANDLER FOR SQLSTATE '23505'
        BEGIN
            INSERT INTO error_tbl VALUES ('inner duplicate');
        END;
        -- inner statements get the CONTINUE handler
    END L1;
END;
```

### SIGNAL and RESIGNAL

```sql
-- Signal a custom error
SIGNAL SQLSTATE 'T0001'
    SET MESSAGE_TEXT = 'Invalid input: value must be positive';

-- Resignal from within a handler (escalate/re-raise)
DECLARE CONTINUE HANDLER FOR SQLSTATE '22012'
    IF v_param < 1 THEN
        RESIGNAL SQLSTATE '22003';  -- escalate to out-of-range
    END IF;
```

SIGNAL can set: `MESSAGE_TEXT`, `CLASS_ORIGIN`, `SUBCLASS_ORIGIN`.

### GET DIAGNOSTICS

```sql
-- Statement area: row count from previous DML
GET DIAGNOSTICS v_rowcount = ROW_COUNT;

-- Exception area: error details in a handler
GET DIAGNOSTICS EXCEPTION 1
    v_sqlstate = RETURNED_SQLSTATE,
    v_message  = MESSAGE_TEXT,
    v_origin   = CLASS_ORIGIN;
```

Up to 16 condition areas are available (for nested handlers).

## Dynamic SQL

### EXECUTE IMMEDIATE

For one-shot statements with no parameters:

```sql
EXECUTE IMMEDIATE 'DROP TABLE ' || v_table_name;
EXECUTE IMMEDIATE 'CREATE TABLE ' || v_db || '.' || v_name || ' (id INTEGER)';
```

### PREPARE / EXECUTE / USING

For parameterized or reusable statements:

```sql
SET v_sql = 'UPDATE ' || v_table || ' SET price = ? WHERE item_id = ?';
PREPARE stmt1 FROM v_sql;
EXECUTE stmt1 USING v_new_price, v_item_id;
DEALLOCATE PREPARE stmt1;
```

### Rules and Limitations

- Parameter marker `?` types must match USING values exactly (no auto-conversion)
- Cannot EXECUTE a HELP statement or macro
- Multi-statement requests not supported with EXECUTE
- EXECUTE IMMEDIATE is equivalent to `DBC.SysExecSQL`

## Recursion

- Maximum nesting depth: **15 levels** for recursive/nested calls
- A warning is generated when creating a recursive procedure (can be ignored)
- To avoid the warning, create an empty stub procedure first

```sql
REPLACE PROCEDURE recurse_proc (INOUT depth INTEGER)
BEGIN
    INSERT INTO depth_log VALUES (depth);
    SET depth = depth + 1;
    IF depth < 15 THEN
        CALL recurse_proc(depth);
    END IF;
END;
```

## Triggers and Stored Procedures

Stored procedures can be called from triggers to encapsulate complex logic:

```sql
REPLACE TRIGGER record_access
AFTER INSERT ON data_table
REFERENCING NEW AS newrow
FOR EACH ROW
(CALL record_access_sp(newrow.col1, newrow.col2));
```

This avoids repeated parsing of SQL statements in the trigger body.

## Multi-Statement Requests

Supported inside stored procedures:

```sql
BEGIN REQUEST
    INSERT INTO table1 VALUES (v1);
    INSERT INTO table2 VALUES (v2);
END REQUEST;
```

## Key SQLSTATE Classes

| Class | Meaning |
|---|---|
| `00` | Successful completion |
| `01` | Warning |
| `02` | No data |
| `22` | Data exception (overflow, divide by zero, truncation) |
| `23` | Constraint violation (unique, foreign key) |
| `42` | Syntax error or access rule violation |
| `53` | Insufficient resources |
| `T0` | User-defined error range (Teradata) |
