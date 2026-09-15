# Dynamic SQL, Cursors, and Result Sets in Teradata Stored Procedures

> **Source:** Teradata Vantage SQL Stored Procedures and Embedded SQL, Release 20.00  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/SQL-Stored-Procedures-and-Embedded-SQL  
> **Extraction date:** 2025-07  
> **Topics:** Dynamic SQL, Cursors, and Result Sets in Teradata Stored Procedures

> Source: 541-0004996 (Teradata Stored Procedure Feature User Guide), 541-0006376 (CLI and Result Sets in External and SQL Stored Procedures)

## Dynamic SQL Overview

Dynamic SQL allows stored procedures to construct and execute SQL statements at runtime. This is essential for building flexible procedures that operate on different tables, columns, or conditions determined by input parameters. Two mechanisms are available:
- **EXECUTE IMMEDIATE** — compile and execute in one step (no parameters)
- **PREPARE / EXECUTE** — compile once, execute with parameter substitution

### EXECUTE IMMEDIATE

Use `EXECUTE IMMEDIATE` for statements that require no parameter binding. The SQL text is assembled as a string and executed in a single step.

```sql
DECLARE v_sql VARCHAR(500);
SET v_sql = 'DROP TABLE ' || v_db || '.' || v_tbl;
EXECUTE IMMEDIATE v_sql;
```

### PREPARE and EXECUTE

Use `PREPARE` / `EXECUTE` when the statement needs parameter markers (`?`). The `PREPARE` statement compiles the SQL text and validates syntax. The `EXECUTE ... USING` clause substitutes parameter marker values at runtime. Data types in the `USING` clause must match the target columns — no automatic conversion occurs.

```sql
REPLACE PROCEDURE sales_update(
    IN v_table VARCHAR(30),
    IN v_item  INTEGER,
    IN v_price DECIMAL(8,2)
)
BEGIN
    DECLARE v_sql VARCHAR(200);

    -- Method 1: PREPARE with parameter markers
    SET v_sql = 'UPDATE ' || v_table
        || ' SET store_price = ? WHERE store_item = ?';
    PREPARE stmt1 FROM v_sql;
    EXECUTE stmt1 USING v_price, v_item;
    DEALLOCATE PREPARE stmt1;

    -- Method 2: EXECUTE IMMEDIATE with concatenated values
    SET v_sql = 'UPDATE ' || v_table
        || ' SET store_price = ' || TRIM(CAST(v_price AS VARCHAR(20)))
        || ' WHERE store_item = ' || TRIM(CAST(v_item AS VARCHAR(20)));
    EXECUTE IMMEDIATE v_sql;
END;
```

### Dynamic SQL via SysExec Pattern

A common utility pattern wraps `DBC.SysExecSQL` for executing arbitrary SQL, useful for administrative GRANT/CREATE/DROP statements:

```sql
REPLACE PROCEDURE SysExec(IN v_cmd VARCHAR(500))
BEGIN
    CALL DBC.SysExecSQL(v_cmd || ';');
END;

-- Usage: CALL SysExec('GRANT SELECT ON mydb.sales TO user1 WITH GRANT OPTION');
```

### Dynamic SQL Restrictions

| Restriction | Detail |
|---|---|
| EXECUTE of a macro | Not supported inside stored procedures |
| Dynamic HELP TABLE | Cannot use EXECUTE with data-returning statements like HELP TABLE |
| Multi-statement requests | Not supported inside PREPARE/EXECUTE |
| USING type matching | Data types in USING clause must match parameter markers exactly |

## Cursor Operations

Cursors process query results row by row. A cursor defines a SELECT statement, and the procedure opens it, fetches rows, and closes it.

### Declare, Open, Fetch, Close Pattern

```sql
REPLACE PROCEDURE process_orders(OUT v_total DECIMAL(18,2))
BEGIN
    DECLARE v_order_id INTEGER;
    DECLARE v_amount   DECIMAL(18,2);
    DECLARE v_done     INTEGER DEFAULT 0;

    DECLARE CONTINUE HANDLER FOR SQLSTATE '02000'  -- no more rows
        SET v_done = 1;

    DECLARE order_cursor CURSOR FOR
        SELECT order_id, amount FROM orders WHERE status = 'PENDING';

    SET v_total = 0;

    OPEN order_cursor;

    fetch_loop: WHILE v_done = 0 DO
        FETCH order_cursor INTO v_order_id, v_amount;
        IF v_done = 1 THEN LEAVE fetch_loop; END IF;
        SET v_total = v_total + v_amount;
    END WHILE fetch_loop;

    CLOSE order_cursor;
END;
```

### Key SQLSTATE Codes for Cursors

| SQLSTATE | Meaning |
|---|---|
| `02000` | No data found (end of result set) |
| `02001` | No more result sets available |
| `0100C` | Dynamic result sets returned from a CALL |
| `0100D` | Additional result sets still available |

### FOR Loop with Implicit Cursor

The `FOR` loop implicitly declares, opens, fetches, and closes a cursor. Access columns via `cursor_name.column_name`:

```sql
REPLACE PROCEDURE validate_accounts(OUT v_invalid_count INTEGER)
BEGIN
    SET v_invalid_count = 0;

    FOR cur_row AS acct_cursor CURSOR FOR
        SELECT account_id, first_name, last_name
        FROM new_accounts
        WHERE LENGTH(TRIM(last_name)) < 2
    DO
        SET v_invalid_count = v_invalid_count + 1;
        INSERT INTO invalid_entries VALUES (
            v_invalid_count,
            cur_row.account_id,
            cur_row.last_name || ', ' || cur_row.first_name
        );
    END FOR;
END;
```

### Updateable Cursors

Use `FOR UPDATE OF` and `WHERE CURRENT OF` for positioned updates on the current cursor row:

```sql
DECLARE price_cursor CURSOR FOR
    SELECT unit_price FROM products WHERE category = 'CLEARANCE'
    FOR UPDATE OF unit_price;

OPEN price_cursor;
WHILE v_done = 0 DO
    FETCH price_cursor INTO v_price;
    IF v_done = 1 THEN LEAVE; END IF;
    UPDATE products SET unit_price = v_price * (1 - v_pct / 100)
        WHERE CURRENT OF price_cursor;
END WHILE;
CLOSE price_cursor;
```

## Dynamic Result Sets

Stored procedures can return query results to the caller or client using cursors with the `WITH RETURN` clause. The `DYNAMIC RESULT SETS n` clause on the procedure header specifies how many result sets may be returned (0 to 15).

### Return Result Set to Caller

Use `CURSOR WITH RETURN ONLY` and open the cursor without fetching. The open cursor is returned after the procedure ends.

```sql
REPLACE PROCEDURE find_item(
    IN v_store INTEGER,
    IN v_item  VARCHAR(30)
)
DYNAMIC RESULT SETS 1
BEGIN
    DECLARE results1 CURSOR WITH RETURN ONLY FOR
        SELECT store, item, onhand
        FROM inventory
        WHERE store = v_store AND item = v_item
        ORDER BY store, item;

    OPEN results1;
END;
```

### Dynamic Result Set with PREPARE

Combine dynamic SQL with result set cursors to build flexible queries with parameter markers:

```sql
REPLACE PROCEDURE find_item_dynamic(IN v_store INTEGER)
DYNAMIC RESULT SETS 1
BEGIN
    DECLARE v_sql VARCHAR(500);
    DECLARE result_set CURSOR WITH RETURN ONLY FOR stmt1;

    SET v_sql = 'SELECT store, item, onhand FROM inventory'
        || ' WHERE store = ? ORDER BY store, item';
    PREPARE stmt1 FROM v_sql;
    OPEN result_set USING v_store;
    DEALLOCATE PREPARE stmt1;
END;
```

### Multiple Result Sets

Multiple cursors can be returned. Open order determines return order:

```sql
REPLACE PROCEDURE store_report(IN v_store INTEGER)
DYNAMIC RESULT SETS 2
BEGIN
    DECLARE rs_inventory CURSOR WITH RETURN ONLY FOR
        SELECT item, onhand FROM inventory WHERE store = v_store;

    DECLARE rs_sales CURSOR WITH RETURN ONLY FOR
        SELECT item, total_sales FROM sales WHERE store = v_store;

    OPEN rs_inventory;
    OPEN rs_sales;
END;
```

### Result Set Return Options

| Option | SP Reads Data? | Returned To | Use Case |
|---|---|---|---|
| `WITH RETURN ONLY TO CALLER` | No | Calling SP | Pass results to parent procedure |
| `WITH RETURN ONLY TO CLIENT` | No | Client app | Skip intermediate procedures |
| `WITH RETURN TO CALLER` | Yes | Calling SP | SP reads some rows, caller gets rest |
| `WITH RETURN TO CLIENT` | Yes | Client app | SP reads some rows, client gets rest |
| *(no RETURN clause)* | Yes | Not returned | SP processes all rows internally |

When a cursor uses `RETURN TO` (without ONLY), the procedure can fetch rows and position within the result set. The caller begins reading from where the procedure stopped.

### Scrollable Result Set Cursors

Add `SCROLL` to allow the caller to navigate backward. Without it, the caller reads forward-only from the current position:

```sql
DECLARE results1 SCROLL CURSOR WITH RETURN TO CALLER FOR
    SELECT id, name FROM employees ORDER BY id;
```

### Consuming Result Sets from a Called Procedure

Use `ALLOCATE ... CURSOR FOR PROCEDURE` to consume result sets returned by a called procedure:

```sql
REPLACE PROCEDURE consume_results(OUT v_total DECIMAL(18,2))
READS SQL DATA
BEGIN
    DECLARE v_store VARCHAR(20);
    DECLARE v_sales INTEGER;
    DECLARE v_price DECIMAL(8,2);
    SET v_total = 0;

    CALL sales_procedure();

    IF SQLSTATE = '0100C' THEN   -- result sets returned
        rs_loop: LOOP
            ALLOCATE my_cursor CURSOR FOR PROCEDURE sales_procedure;
            IF SQLSTATE = '02001' THEN LEAVE rs_loop; END IF;  -- no more
            fetch_loop: LOOP
                FETCH my_cursor INTO v_store, v_sales, v_price;
                IF SQLSTATE = '02000' THEN
                    CLOSE my_cursor;
                    LEAVE fetch_loop;
                END IF;
                SET v_total = v_total + v_sales * v_price;
            END LOOP fetch_loop;
        END LOOP rs_loop;
    END IF;
END;
```

### Security with Dynamic Result Sets

Use `SQL SECURITY OWNER` to let users receive result sets without direct table access:

```sql
REPLACE PROCEDURE secure_list()
DYNAMIC RESULT SETS 1
SQL SECURITY OWNER
BEGIN
    DECLARE sal_cursor CURSOR WITH RETURN ONLY FOR
        SELECT id, sal FROM salary;
    OPEN sal_cursor;
END;

-- User can CALL but has no SELECT on the salary table
GRANT EXECUTE PROCEDURE ON payroll.secure_list TO app_user;
```

## Error Handling and GET DIAGNOSTICS

### Handler Types

| Handler Type | Behavior |
|---|---|
| `CONTINUE HANDLER` | Executes handler action, then resumes at the next statement |
| `EXIT HANDLER` | Executes handler action, then exits the current BEGIN/END block |

### Declaring Handlers and Conditions

```sql
DECLARE divide_by_zero CONDITION FOR SQLSTATE '22012';
DECLARE EXIT HANDLER FOR divide_by_zero SET v_result = 0;

DECLARE CONTINUE HANDLER FOR SQLSTATE '42000'
BEGIN
    SET v_error_flag = 1;
    SET v_error_state = '42000';
END;

DECLARE EXIT HANDLER FOR SQLEXCEPTION
    SET v_status = 'FAILED';
```

### SIGNAL and RESIGNAL

`SIGNAL` raises a user-defined error. `RESIGNAL` re-raises an error from within a handler, optionally modifying the message.

```sql
REPLACE PROCEDURE check_input(IN v_divisor INTEGER, OUT v_result INTEGER)
BEGIN
    DECLARE divide_by_zero CONDITION FOR SQLSTATE '22012';
    DECLARE EXIT HANDLER FOR divide_by_zero
        SET v_result = 0;

    IF v_divisor = 0 THEN
        SIGNAL divide_by_zero;
    ELSE
        SET v_result = 100 / v_divisor;
    END IF;
END;
```

RESIGNAL re-raises from within a handler, optionally changing the condition. A continue handler can escalate to an exit handler via RESIGNAL when the error is unrecoverable.

### GET DIAGNOSTICS

`GET DIAGNOSTICS` retrieves information about the most recently executed statement or exception. Always call it first in a handler before other SQL resets the diagnostic area.

```sql
GET DIAGNOSTICS v_rowcount = ROW_COUNT;              -- statement area
GET DIAGNOSTICS v_num = NUMBER;                       -- exception count
GET DIAGNOSTICS EXCEPTION 1                           -- exception area
    v_sqlstate = RETURNED_SQLSTATE,
    v_message  = MESSAGE_TEXT;
```

#### Statement Diagnostic Fields

| Field | Description |
|---|---|
| `ROW_COUNT` | Rows affected by previous DELETE, INSERT, UPDATE, SELECT INTO, or CALL |
| `NUMBER` | Total exception/completion conditions stored in diagnostics area |
| `COMMAND_FUNCTION` | Identification of the SQL statement executed |
| `COMMAND_FUNCTION_CODE` | Numeric code identifying the SQL statement type |
| `MORE` | 'Y' if more conditions exist than stored; 'N' otherwise |
| `TRANSACTION_ACTIVE` | 1 if a transaction is active; 0 otherwise |

#### Exception Diagnostic Fields

| Field | Description |
|---|---|
| `RETURNED_SQLSTATE` | SQLSTATE value from the statement or SIGNAL/RESIGNAL |
| `MESSAGE_TEXT` | Error or warning message text |
| `MESSAGE_LENGTH` | Length of MESSAGE_TEXT in characters |
| `CLASS_ORIGIN` | 'ISO 9075' for standard; 'Teradata' for implementation-defined |
| `SUBCLASS_ORIGIN` | 'ISO 9075' for standard; 'Teradata' for implementation-defined |
| `CONDITION_IDENTIFIER` | Condition name from SIGNAL/RESIGNAL (default NULL) |
| `CONDITION_NUMBER` | Position in diagnostics stack (1 to N, max 16) |

### Complete Error Handling Example

```sql
REPLACE PROCEDURE robust_insert(
    IN  v_id    INTEGER,
    IN  v_name  VARCHAR(100),
    OUT v_status VARCHAR(50),
    OUT v_message VARCHAR(200)
)
BEGIN
    DECLARE v_rowcount INTEGER;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        GET DIAGNOSTICS EXCEPTION 1
            v_status  = RETURNED_SQLSTATE,
            v_message = MESSAGE_TEXT;
    END;

    INSERT INTO customers (id, name) VALUES (v_id, v_name);
    GET DIAGNOSTICS v_rowcount = ROW_COUNT;

    IF v_rowcount = 1 THEN
        SET v_status  = '00000';
        SET v_message = 'Insert successful';
    ELSE
        SIGNAL SQLSTATE 'T0001'
            SET MESSAGE_TEXT = 'Unexpected row count: ' || TRIM(CAST(v_rowcount AS VARCHAR(10)));
    END IF;
END;
```
