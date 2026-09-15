# Macro Design and Security Patterns — Complete Reference

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 9

## Macro Security Model

### Privilege Delegation

Macros provide a security boundary between the caller and the underlying data:

1. The caller needs only `EXECUTE` privilege on the macro
2. The macro's **immediate owner** (the containing database or user) must hold the privileges for all statements
3. The owner must hold privileges `WITH GRANT OPTION` for non-owner access

```
User (EXECUTE on macro) → Macro (owned by database_A) → Table (database_A has SELECT WITH GRANT OPTION)
```

### Controlled Data Access Example

```sql
-- DBA creates a macro in a shared database
CREATE MACRO shared_db.m_customer_lookup (
    cust_id INTEGER
) AS (
    SELECT customer_id, customer_name, email
    FROM customer_db.customers
    WHERE customer_id = :cust_id;
);

-- Grant EXECUTE to the analyst role (no direct table access needed)
GRANT EXECUTE ON shared_db.m_customer_lookup TO analyst_role;
```

The analyst can execute the macro and retrieve the specified columns but cannot query `customer_db.customers` directly or see columns not included in the macro.

### Security Audit

```sql
-- Check who has EXECUTE on a macro
SELECT UserName, AccessRight, GrantAuthority
FROM DBC.AllRightsV
WHERE DatabaseName = 'shared_db'
  AND TableName = 'm_customer_lookup';
```

## Advanced Parameter Patterns

### Optional Parameters with Defaults

```sql
CREATE MACRO mydb.m_search (
    search_text VARCHAR(200),
    max_rows INTEGER DEFAULT 100,
    sort_col VARCHAR(30) DEFAULT 'name'
) AS (
    SELECT TOP :max_rows *
    FROM mydb.products
    WHERE product_name LIKE '%' || :search_text || '%'
    ORDER BY CASE WHEN :sort_col = 'name' THEN product_name
                  WHEN :sort_col = 'price' THEN CAST(price AS VARCHAR(20))
                  ELSE product_name END;
);
```

### Date Range Parameters

```sql
CREATE MACRO mydb.m_period_report (
    start_date DATE DEFAULT DATE - 30,
    end_date DATE DEFAULT DATE
) AS (
    SELECT order_date,
           COUNT(*) AS order_count,
           SUM(amount) AS total_amount
    FROM mydb.orders
    WHERE order_date BETWEEN :start_date AND :end_date
    GROUP BY order_date
    ORDER BY order_date;
);
```

### Parameter Type Compatibility

| Parameter Type | Accepts | Notes |
|---------------|---------|-------|
| INTEGER | Integer literals, expressions | Exact match |
| VARCHAR(n) | String literals up to n chars | Truncated if longer |
| DATE | DATE literals, DATE expressions | Format depends on session DATEFORM |
| DECIMAL(p,s) | Numeric literals with correct precision | Rounded if needed |
| TIMESTAMP | TIMESTAMP literals | Full precision |

## Multi-Statement Transaction Patterns

### Atomic Insert + Update

```sql
CREATE MACRO mydb.m_transfer_funds (
    from_acct INTEGER,
    to_acct INTEGER,
    transfer_amount DECIMAL(15,2)
) AS (
    -- Debit source account
    UPDATE mydb.accounts
    SET balance = balance - :transfer_amount
    WHERE account_id = :from_acct;

    -- Credit destination account
    UPDATE mydb.accounts
    SET balance = balance + :transfer_amount
    WHERE account_id = :to_acct;

    -- Log the transfer
    INSERT INTO mydb.transfer_log (from_account, to_account, amount, transfer_date)
    VALUES (:from_acct, :to_acct, :transfer_amount, CURRENT_TIMESTAMP);
);
```

All three statements execute in a single transaction. If any fails, the entire transaction rolls back.

### ETL Pattern

```sql
CREATE MACRO mydb.m_daily_etl (
    process_date DATE
) AS (
    -- Delete existing data for the date (idempotent reload)
    DELETE FROM mydb.daily_summary
    WHERE summary_date = :process_date;

    -- Insert new summary data
    INSERT INTO mydb.daily_summary
    SELECT :process_date, product_id,
           SUM(quantity), SUM(revenue)
    FROM mydb.sales_detail
    WHERE sale_date = :process_date
    GROUP BY product_id;
);
```

## LOCKING Patterns in Macros

### Access Lock for Reporting

```sql
CREATE MACRO mydb.m_dashboard AS (
    LOCKING mydb.orders FOR ACCESS
    LOCKING mydb.customers FOR ACCESS
    SELECT c.region,
           COUNT(DISTINCT o.customer_id) AS active_customers,
           SUM(o.amount) AS total_revenue
    FROM mydb.orders o
    JOIN mydb.customers c ON o.customer_id = c.customer_id
    WHERE o.order_date >= DATE - 30
    GROUP BY c.region;
);
```

### Row-Level Locking

```sql
CREATE MACRO mydb.m_update_status (
    order_id_param INTEGER,
    new_status VARCHAR(20)
) AS (
    LOCKING ROW FOR WRITE
    UPDATE mydb.orders
    SET status = :new_status
    WHERE order_id = :order_id_param;
);
```

## Macro vs Other Approaches

### When to Use Macros

- Simple multi-statement batches with parameters
- Security-delegated data access
- Encapsulating common report queries
- Quick server-side logic without stored procedure complexity

### When to Use Stored Procedures Instead

- Conditional logic (IF/ELSE, CASE)
- Loops and cursors
- Error handling with DECLARE HANDLER
- OUT/INOUT parameters
- Dynamic SQL
- Complex control flow

### When to Use Views Instead

- Single SELECT statement with no parameters
- Reusable query abstraction
- Transparent to the optimizer (views are expanded inline)

## Macro Naming Conventions

| Convention | Example | Purpose |
|------------|---------|---------|
| Prefix `m_` | `m_daily_report` | Identifies macros in object listings |
| Verb-based | `m_archive_orders` | Describes the action |
| Domain prefix | `m_hr_employee_search` | Groups by business domain |

## Limitations

- No control flow (IF, WHILE, LOOP)
- No error handling
- No output parameters
- No dynamic SQL
- No local variables
- Parameters are input-only
- All statements must be valid SQL (no procedural extensions)
- Maximum macro body size is limited by the DBC.TextTbl storage
