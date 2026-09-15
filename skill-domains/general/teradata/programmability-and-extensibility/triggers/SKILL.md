---
name: triggers
description: 'Create and manage Teradata triggers using CREATE TRIGGER, REPLACE TRIGGER, ALTER TRIGGER, and DROP TRIGGER DDL. Use when implementing BEFORE or AFTER triggers for INSERT, UPDATE, or DELETE events, using row-level or statement-level triggers, referencing OLD and NEW transition values, creating cascading data modifications, enforcing complex business rules via triggers, enabling or disabling triggers, or auditing data changes automatically.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Triggers

## When to Use

- Automatically enforcing business rules on data changes
- Auditing INSERT, UPDATE, or DELETE operations
- Cascading changes to related tables
- Maintaining derived or denormalized data
- Implementing complex validation beyond CHECK constraints
- Enabling or disabling triggers for bulk load operations

## Core Concepts

### Trigger Types

| Type | Fires | Use Case |
|------|-------|----------|
| BEFORE | Before the triggering DML executes | Validation, default-setting, data transformation |
| AFTER | After the triggering DML executes | Auditing, cascading updates, notifications |

### Trigger Granularity

| Granularity | Keyword | Fires |
|-------------|---------|-------|
| Row-level | `FOR EACH ROW` | Once per affected row |
| Statement-level | `FOR EACH STATEMENT` | Once per triggering statement |

## CREATE TRIGGER Syntax

```sql
CREATE TRIGGER [database_name.]trigger_name
  { BEFORE | AFTER } { INSERT | UPDATE | DELETE }
  [OF (column_name [,...])]
  ON [database_name.]table_name
  REFERENCING { OLD [AS] old_name | NEW [AS] new_name
              | OLD_TABLE [AS] old_table_name
              | NEW_TABLE [AS] new_table_name } [...]
  FOR EACH { ROW | STATEMENT }
  [WHEN (condition)]
  ( triggered_action ; [triggered_action ;] ... )
;
```

### REPLACE TRIGGER

```sql
REPLACE TRIGGER [database_name.]trigger_name
  AFTER UPDATE ON [database_name.]table_name
  ...
;
```

## Transition References

| Reference | Available For | Granularity | Contains |
|-----------|--------------|-------------|----------|
| `OLD` | UPDATE, DELETE | Row-level | Pre-change column values |
| `NEW` | INSERT, UPDATE | Row-level | Post-change column values |
| `OLD_TABLE` | UPDATE, DELETE | Statement-level | All pre-change rows as a table |
| `NEW_TABLE` | INSERT, UPDATE | Statement-level | All post-change rows as a table |

## Common Patterns

### Audit Trail Trigger

```sql
CREATE TRIGGER mydb.trg_orders_audit
  AFTER INSERT OR UPDATE OR DELETE ON mydb.orders
  REFERENCING OLD AS old_row NEW AS new_row
  FOR EACH ROW
(
    INSERT INTO mydb.orders_audit (
        audit_action,
        order_id,
        old_amount,
        new_amount,
        changed_by,
        changed_at
    )
    VALUES (
        CASE WHEN INSERTING THEN 'INSERT'
             WHEN UPDATING THEN 'UPDATE'
             WHEN DELETING THEN 'DELETE'
        END,
        COALESCE(new_row.order_id, old_row.order_id),
        old_row.amount,
        new_row.amount,
        USER,
        CURRENT_TIMESTAMP
    );
);
```

### BEFORE Trigger for Validation

```sql
CREATE TRIGGER mydb.trg_validate_salary
  BEFORE INSERT OR UPDATE OF (salary) ON mydb.employees
  REFERENCING NEW AS new_row
  FOR EACH ROW
  WHEN (new_row.salary < 0 OR new_row.salary > 1000000)
(
    ABORT 'Salary must be between 0 and 1,000,000';
);
```

### BEFORE Trigger for Default Setting

```sql
CREATE TRIGGER mydb.trg_set_defaults
  BEFORE INSERT ON mydb.orders
  REFERENCING NEW AS new_row
  FOR EACH ROW
(
    SET new_row.created_date = CURRENT_DATE;
    SET new_row.status = COALESCE(new_row.status, 'PENDING');
    SET new_row.created_by = USER;
);
```

### Cascading Update Trigger

```sql
CREATE TRIGGER mydb.trg_cascade_status
  AFTER UPDATE OF (status) ON mydb.orders
  REFERENCING NEW AS new_row
  FOR EACH ROW
  WHEN (new_row.status = 'CANCELLED')
(
    UPDATE mydb.order_details
    SET status = 'CANCELLED'
    WHERE order_id = new_row.order_id;
);
```

### Statement-Level Trigger with Transition Tables

```sql
CREATE TRIGGER mydb.trg_batch_audit
  AFTER INSERT ON mydb.orders
  REFERENCING NEW_TABLE AS inserted_rows
  FOR EACH STATEMENT
(
    INSERT INTO mydb.batch_audit_log (batch_time, row_count, total_amount)
    SELECT CURRENT_TIMESTAMP, COUNT(*), SUM(amount)
    FROM inserted_rows;
);
```

## ALTER TRIGGER

```sql
-- Disable a trigger (e.g., before bulk load)
ALTER TRIGGER mydb.trg_orders_audit DISABLED;

-- Re-enable a trigger
ALTER TRIGGER mydb.trg_orders_audit ENABLED;
```

## DROP TRIGGER

```sql
DROP TRIGGER [database_name.]trigger_name;
```

## RENAME TRIGGER

```sql
RENAME TRIGGER [database_name.]old_name TO new_name;
```

## Querying Trigger Metadata

```sql
-- List triggers on a table
SELECT TriggerName, EnableFlag, ActionTime, TriggerEvent
FROM DBC.TriggersV
WHERE DatabaseName = 'mydb'
  AND SubjectTableName = 'orders';

-- Show trigger definition
SHOW TRIGGER mydb.trg_orders_audit;

-- Help trigger
HELP TRIGGER mydb.trg_orders_audit;
```

## Trigger Execution Order

- Multiple triggers on the same table and event execute in creation order
- BEFORE triggers execute before the DML modifies the base table
- AFTER triggers execute after the DML completes
- All triggers execute within the same transaction as the triggering DML

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| 3706: Syntax error | Invalid trigger syntax | Validate the triggered action SQL separately |
| 5765: Trigger already exists | CREATE TRIGGER with existing name | Use REPLACE TRIGGER |
| 3932: Trigger cannot reference itself | Trigger action modifies its own subject table | Redesign to avoid circular triggers |
| 3524: Trigger action error | Invalid column reference in OLD/NEW | Check column names in REFERENCING clause |

## Restrictions

- Triggers cannot reference the subject table in AFTER triggers (no recursive triggers)
- Maximum of one BEFORE and one AFTER trigger per event per table (can combine INSERT/UPDATE/DELETE)
- Triggers cannot contain DDL statements
- Triggers cannot contain COMMIT or ROLLBACK
- Triggers on views are not supported

## Performance Considerations

- Row-level triggers add overhead per row — significant for large batch operations
- Disable triggers before bulk loads: `ALTER TRIGGER ... DISABLED`
- Statement-level triggers are more efficient for batch operations
- Trigger actions are part of the triggering transaction — they hold locks

## Privileges Required

- `CREATE TRIGGER` on the subject table's database
- Appropriate DML privileges on tables referenced in the triggered action
- `DROP TRIGGER` or `DROP TABLE` to drop a trigger

## References


> **Access:** `skill_resource_read(action="read", skill="triggers", path="references/FILENAME")` — do NOT call `list`.

- [Trigger Design Patterns](./references/trigger-design-patterns.md) — Advanced trigger patterns for auditing, cascading, validation, and performance optimization

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 22
