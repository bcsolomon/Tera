---
name: teradata-stored-procedures
description: 'Create, modify, debug, and call SQL stored procedures (SPL) on Teradata. Use when writing SQL stored procedures with procedural logic (IF/WHILE/FOR/LOOP/CASE), cursors, condition handling (DECLARE HANDLER, SIGNAL, SQLSTATE), dynamic SQL (PREPARE/EXECUTE), result sets, GRANT EXECUTE, and querying DBC catalog for existing procedures. For Java stored procedures see stored-procedure-java; for C/C++ external stored procedures see stored-procedure-c.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Stored Procedures

## When to Use

- Creating SQL stored procedures with procedural logic (SPL)
- Using control flow: IF/ELSE, WHILE, FOR, LOOP, CASE, REPEAT
- Declaring and using cursors to iterate result sets
- Handling errors with DECLARE HANDLER, SIGNAL, SQLSTATE
- Building dynamic SQL with PREPARE/EXECUTE/EXECUTE IMMEDIATE
- Returning dynamic result sets from procedures
- Discovering existing procedures in the DBC catalog
- Granting execution privileges on procedures

> **Not this skill:** For Java external stored procedures (JXSP), see **stored-procedure-java**.
> For C/C++ external stored procedures (CXSP), see **stored-procedure-c**.

## Stored Procedure Type

SQL stored procedures (SPL) use the SQL Procedure Language. It provides procedural control flow
(IF/WHILE/CASE), cursors, condition handlers, and dynamic SQL executed inside the database.

## Procedure: Creating a SQL Stored Procedure

1. Determine the procedure name, parameters (IN/OUT/INOUT), and database
2. Write the procedure body using SPL control flow and SQL statements
3. Use `CREATE PROCEDURE` or `REPLACE PROCEDURE`
4. Grant EXECUTE privilege to users/roles
5. Call with the `CALL` statement

### SQL Stored Procedure Syntax

```sql
REPLACE PROCEDURE database_name.procedure_name (
    IN    param1  data_type,
    OUT   param2  data_type,
    INOUT param3  data_type
)
SQL SECURITY DEFINER          -- or CREATOR, OWNER, INVOKER
BEGIN
    -- Declarations
    DECLARE local_var data_type [DEFAULT value];
    DECLARE sql_code INTEGER DEFAULT 0;
    DECLARE CONTINUE HANDLER FOR SQLSTATE '02000'
        SET sql_code = 1;

    -- Procedure body
    SET param2 = param1 * 2;
END;
```

### Parameter Modes

| Mode | Direction | Max Count |
|------|-----------|-----------|
| `IN` | Caller → Procedure (read-only) | Up to 256 total |
| `OUT` | Procedure → Caller (write-only) | |
| `INOUT` | Both directions (read-write) | |

### Security Modes

| Mode | Executes As | Use Case |
|------|-------------|----------|
| `SQL SECURITY DEFINER` | Procedure creator | Default. Controlled access |
| `SQL SECURITY CREATOR` | Same as DEFINER | Alias |
| `SQL SECURITY OWNER` | Database owner | Shared administrative procedures |
| `SQL SECURITY INVOKER` | Calling user | Caller needs own privileges |

### Control Flow Statements

```sql
-- IF/ELSEIF/ELSE
IF condition THEN statements;
ELSEIF condition THEN statements;
ELSE statements;
END IF;

-- CASE (searched)
CASE
    WHEN condition THEN statements;
    WHEN condition THEN statements;
    ELSE statements;
END CASE;

-- WHILE loop
WHILE condition DO
    statements;
END WHILE;

-- FOR loop (cursor-based)
FOR cursor_name AS SELECT col1, col2 FROM table_name
DO
    -- use cursor_name.col1, cursor_name.col2
    statements;
END FOR;

-- LOOP with LEAVE
label1: LOOP
    IF condition THEN LEAVE label1; END IF;
    statements;
END LOOP label1;

-- REPEAT
REPEAT
    statements;
UNTIL condition
END REPEAT;
```

### Cursor Operations

```sql
DECLARE cursor_name CURSOR FOR
    SELECT col1, col2 FROM table_name WHERE condition;

OPEN cursor_name;
FETCH cursor_name INTO var1, var2;
-- Process rows in a WHILE loop until SQLSTATE '02000'
CLOSE cursor_name;
```

### Condition Handling

```sql
-- Continue handler: set flag and continue
DECLARE CONTINUE HANDLER FOR SQLSTATE '02000'    -- Not found
    SET v_done = 1;

-- Exit handler: execute block then exit BEGIN/END
DECLARE EXIT HANDLER FOR SQLEXCEPTION
BEGIN
    SET out_status = 'ERROR';
END;

-- Signal a custom error
SIGNAL SQLSTATE 'T0001' SET MESSAGE_TEXT = 'Custom error message';

-- Get diagnostics
GET DIAGNOSTICS EXCEPTION 1
    v_sqlstate = RETURNED_SQLSTATE,
    v_message  = MESSAGE_TEXT;
```

### Dynamic SQL

```sql
-- Execute immediately (no parameters)
EXECUTE IMMEDIATE 'DROP TABLE ' || v_table_name;

-- Prepare and execute (with parameters)
SET v_sql = 'INSERT INTO target_table VALUES (?, ?)';
PREPARE stmt FROM v_sql;
EXECUTE stmt USING var1, var2;
```

See [SQL Stored Procedures reference](./references/sql-stored-procedures.md) for complete syntax, cursor modes, and advanced patterns.

## Procedure: Discovering Stored Procedures from the Catalog

### List All Procedures in a Database

```sql
SELECT ProcedureName, NumParameters, LanguageName,
       SQLSecurityType, CreateTimeStamp
FROM DBC.FunctionsV
WHERE DatabaseName = 'database_name'
  AND FunctionType = 'P'
ORDER BY ProcedureName;
```

### Get Procedure Source Code

```sql
SHOW PROCEDURE database_name.procedure_name;
```

### Get Procedure Comments

```sql
SELECT CommentString FROM DBC.ObjectCommentsV
WHERE DatabaseName = 'database_name'
  AND ObjectName = 'procedure_name'
  AND ObjectType = 'P';
```

### Add Comment to a Procedure

```sql
COMMENT ON PROCEDURE database_name.procedure_name AS
'Description of what this procedure does, its domain, and usage.';
```

### Search Procedures by Comment

```sql
SELECT c.DatabaseName, c.ObjectName, c.CommentString
FROM DBC.ObjectCommentsV c
WHERE c.ObjectType = 'P'
  AND c.CommentString LIKE '%keyword%';
```

## Managing Stored Procedures

```sql
-- Drop a procedure
DROP PROCEDURE database_name.procedure_name;

-- Grant execute
GRANT EXECUTE PROCEDURE ON database_name.procedure_name TO role_or_user;

-- Call a procedure
CALL database_name.procedure_name(arg1, arg2);

-- Help
HELP PROCEDURE database_name.procedure_name;
```

## Common Errors and Solutions

| Error | Cause | Fix |
|-------|-------|-----|
| `SPL1027: Missing RETURN/END` | Incomplete block | Ensure every BEGIN has END |
| `SQLSTATE 02000` | No data found (cursor) | Use CONTINUE HANDLER |
| `Recursion limit exceeded` | >15 nested calls | Refactor to iterative |
| `Privilege violation` | Wrong security mode | Check SQL SECURITY clause |
| `Too many parameters` | >256 params | Reduce or use temp tables |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-stored-procedures", path="references/FILENAME")` — do NOT call `list`.

- [SQL Stored Procedures](./references/sql-stored-procedures.md): complete SPL syntax, control flow, condition handling, variable declarations, SECURITY modes
- [Dynamic SQL and Cursors](./references/dynamic-sql-and-cursors.md): dynamic SQL patterns (EXECUTE IMMEDIATE, PREPARE/EXECUTE), cursor operations (DECLARE/OPEN/FETCH/CLOSE), dynamic result sets, error handling

## Templates

- [SQL SP Template](./assets/templates/sql-sp.md)
