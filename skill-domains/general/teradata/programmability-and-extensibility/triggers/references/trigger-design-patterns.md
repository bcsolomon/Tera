# Trigger Design Patterns — Complete Reference

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 22

## Pattern 1: Complete Audit Trail

Track all changes with full before/after images.

```sql
-- Audit table
CREATE MULTISET TABLE mydb.employee_audit (
    audit_id       INTEGER GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),
    audit_action   CHAR(6),
    audit_time     TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
    audit_user     VARCHAR(128) DEFAULT USER,
    emp_id         INTEGER,
    old_name       VARCHAR(100),
    new_name       VARCHAR(100),
    old_salary     DECIMAL(12,2),
    new_salary     DECIMAL(12,2),
    old_dept_id    INTEGER,
    new_dept_id    INTEGER
) PRIMARY INDEX (emp_id);

-- Combined trigger for all DML events
CREATE TRIGGER mydb.trg_emp_full_audit
  AFTER INSERT OR UPDATE OR DELETE ON mydb.employees
  REFERENCING OLD AS o NEW AS n
  FOR EACH ROW
(
    INSERT INTO mydb.employee_audit (audit_action, emp_id,
        old_name, new_name, old_salary, new_salary, old_dept_id, new_dept_id)
    VALUES (
        CASE WHEN INSERTING THEN 'INSERT'
             WHEN UPDATING THEN 'UPDATE'
             WHEN DELETING THEN 'DELETE' END,
        COALESCE(n.employee_id, o.employee_id),
        o.employee_name, n.employee_name,
        o.salary, n.salary,
        o.department_id, n.department_id
    );
);
```

### Querying the Audit Trail

```sql
-- Changes to a specific employee
SELECT audit_action, audit_time, audit_user,
       old_salary, new_salary
FROM mydb.employee_audit
WHERE emp_id = 12345
ORDER BY audit_time;

-- All salary changes in the last 24 hours
SELECT emp_id, audit_user, old_salary, new_salary, audit_time
FROM mydb.employee_audit
WHERE audit_action = 'UPDATE'
  AND old_salary <> new_salary
  AND audit_time > CURRENT_TIMESTAMP - INTERVAL '24' HOUR;
```

## Pattern 2: Cascading Deletes

Implement referential cascading that Teradata does not enforce automatically.

```sql
CREATE TRIGGER mydb.trg_cascade_delete_orders
  AFTER DELETE ON mydb.customers
  REFERENCING OLD AS deleted_customer
  FOR EACH ROW
(
    -- Delete order details first (child of orders)
    DELETE FROM mydb.order_details
    WHERE order_id IN (
        SELECT order_id FROM mydb.orders
        WHERE customer_id = deleted_customer.customer_id
    );

    -- Then delete orders
    DELETE FROM mydb.orders
    WHERE customer_id = deleted_customer.customer_id;
);
```

## Pattern 3: Maintaining Summary Tables

Keep a summary table in sync with detail table changes.

```sql
CREATE TRIGGER mydb.trg_update_daily_totals
  AFTER INSERT ON mydb.sales_detail
  REFERENCING NEW AS n
  FOR EACH ROW
(
    -- Try to update existing summary row
    UPDATE mydb.daily_sales_summary
    SET total_revenue = total_revenue + n.revenue,
        transaction_count = transaction_count + 1
    WHERE summary_date = n.sale_date
      AND store_id = n.store_id;

    -- Insert new summary row if no existing row
    INSERT INTO mydb.daily_sales_summary (summary_date, store_id, total_revenue, transaction_count)
    SELECT n.sale_date, n.store_id, n.revenue, 1
    WHERE NOT EXISTS (
        SELECT 1 FROM mydb.daily_sales_summary
        WHERE summary_date = n.sale_date AND store_id = n.store_id
    );
);
```

## Pattern 4: Data Transformation (BEFORE Trigger)

Normalize or transform data before it is stored.

```sql
CREATE TRIGGER mydb.trg_normalize_data
  BEFORE INSERT OR UPDATE ON mydb.contacts
  REFERENCING NEW AS n
  FOR EACH ROW
(
    -- Standardize phone format
    SET n.phone = REGEXP_REPLACE(n.phone, '[^0-9]', '');

    -- Uppercase email
    SET n.email = UPPER(n.email);

    -- Trim whitespace from name
    SET n.contact_name = TRIM(BOTH FROM n.contact_name);
);
```

## Pattern 5: Conditional Trigger with WHEN Clause

Fire only when specific conditions are met.

```sql
-- Only fire for significant salary changes (> 10%)
CREATE TRIGGER mydb.trg_salary_alert
  AFTER UPDATE OF (salary) ON mydb.employees
  REFERENCING OLD AS o NEW AS n
  FOR EACH ROW
  WHEN (ABS(n.salary - o.salary) / NULLIFZERO(o.salary) > 0.10)
(
    INSERT INTO mydb.salary_alerts (emp_id, old_salary, new_salary, change_pct, alert_time)
    VALUES (n.employee_id, o.salary, n.salary,
            (n.salary - o.salary) / NULLIFZERO(o.salary) * 100,
            CURRENT_TIMESTAMP);
);
```

## Pattern 6: Statement-Level Batch Triggers

More efficient than row-level for batch operations.

```sql
-- Log batch insert statistics
CREATE TRIGGER mydb.trg_batch_insert_log
  AFTER INSERT ON mydb.transactions
  REFERENCING NEW_TABLE AS new_rows
  FOR EACH STATEMENT
(
    INSERT INTO mydb.batch_log (
        batch_time, table_name, operation,
        row_count, min_amount, max_amount, total_amount
    )
    SELECT CURRENT_TIMESTAMP, 'transactions', 'INSERT',
           COUNT(*), MIN(amount), MAX(amount), SUM(amount)
    FROM new_rows;
);
```

## Performance Optimization

### Disable During Bulk Loads

```sql
-- Before bulk load
ALTER TRIGGER mydb.trg_orders_audit DISABLED;
ALTER TRIGGER mydb.trg_cascade_status DISABLED;

-- Perform bulk load
-- ... FastLoad / TPT / MultiLoad ...

-- Re-enable after load
ALTER TRIGGER mydb.trg_orders_audit ENABLED;
ALTER TRIGGER mydb.trg_cascade_status ENABLED;
```

### Row-Level vs Statement-Level Performance

| Scenario | Row-Level | Statement-Level |
|----------|-----------|-----------------|
| Single-row DML | Similar cost | Similar cost |
| 1,000-row batch | 1,000 trigger executions | 1 trigger execution |
| 1M-row bulk load | 1M trigger executions (very slow) | 1 trigger execution |

**Rule of thumb:** Use statement-level triggers with transition tables (NEW_TABLE/OLD_TABLE) for tables that receive batch DML.

### Trigger Chain Limits

- Teradata supports trigger cascading (trigger A fires, modifies table B, which fires trigger B)
- Maximum cascade depth is system-configurable (default typically 16)
- Deep cascading chains are difficult to debug and maintain
- Prefer flatter designs with statement-level triggers

## INSERTING / UPDATING / DELETING Predicates

Use these built-in predicates in combined triggers to determine which event fired:

```sql
CASE WHEN INSERTING THEN 'INSERT'
     WHEN UPDATING  THEN 'UPDATE'
     WHEN DELETING  THEN 'DELETE'
END
```

These predicates are only valid inside trigger bodies.

## Trigger and Transaction Interaction

- Triggers execute within the same transaction as the triggering statement
- If the trigger action fails, the entire triggering statement is rolled back
- BEFORE triggers that execute ABORT roll back the triggering statement
- AFTER triggers that fail also roll back the triggering statement and its effects
- Explicit COMMIT/ROLLBACK is not allowed inside triggers

## Column-Specific Triggers

Fire only when specific columns are modified:

```sql
CREATE TRIGGER mydb.trg_price_change
  AFTER UPDATE OF (unit_price, list_price) ON mydb.products
  REFERENCING OLD AS o NEW AS n
  FOR EACH ROW
  WHEN (o.unit_price <> n.unit_price OR o.list_price <> n.list_price)
(
    INSERT INTO mydb.price_history (product_id, old_price, new_price, change_date)
    VALUES (n.product_id, o.unit_price, n.unit_price, CURRENT_DATE);
);
```

The `OF (column_list)` clause means the trigger fires only when those specific columns appear in the UPDATE SET clause.
