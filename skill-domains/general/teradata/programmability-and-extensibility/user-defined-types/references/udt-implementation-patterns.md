# UDT Implementation Patterns — Complete Reference

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 12

## Pattern 1: Currency Type (Distinct Type, Complete Implementation)

### Step 1: Create the Distinct Type

```sql
CREATE TYPE SYSUDTLIB.usd_amount AS DECIMAL(15,2) FINAL;
```

### Step 2: Create Cast Functions

```sql
-- Cast from DECIMAL to usd_amount
CREATE FUNCTION SYSUDTLIB.decimal_to_usd(val DECIMAL(15,2))
RETURNS SYSUDTLIB.usd_amount
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
RETURNS NULL ON NULL INPUT
SQL SECURITY DEFINER
RETURN CAST(val AS SYSUDTLIB.usd_amount);

-- Cast from usd_amount to DECIMAL
CREATE FUNCTION SYSUDTLIB.usd_to_decimal(val SYSUDTLIB.usd_amount)
RETURNS DECIMAL(15,2)
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
RETURNS NULL ON NULL INPUT
SQL SECURITY DEFINER
RETURN CAST(val AS DECIMAL(15,2));
```

### Step 3: Register Casts

```sql
CREATE CAST (DECIMAL(15,2) AS SYSUDTLIB.usd_amount)
    WITH SYSUDTLIB.decimal_to_usd
    AS ASSIGNMENT;

CREATE CAST (SYSUDTLIB.usd_amount AS DECIMAL(15,2))
    WITH SYSUDTLIB.usd_to_decimal
    AS ASSIGNMENT;
```

### Step 4: Create Ordering

```sql
-- Comparison function
CREATE FUNCTION SYSUDTLIB.usd_compare(
    a SYSUDTLIB.usd_amount,
    b SYSUDTLIB.usd_amount
)
RETURNS INTEGER
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
SQL SECURITY DEFINER
RETURN CASE
    WHEN CAST(a AS DECIMAL(15,2)) < CAST(b AS DECIMAL(15,2)) THEN -1
    WHEN CAST(a AS DECIMAL(15,2)) = CAST(b AS DECIMAL(15,2)) THEN 0
    ELSE 1
END;

-- Register ordering
CREATE ORDERING FOR SYSUDTLIB.usd_amount
    ORDER FULL BY RELATIVE WITH SYSUDTLIB.usd_compare;
```

### Step 5: Use in Tables

```sql
CREATE TABLE finance_db.invoices (
    invoice_id    INTEGER NOT NULL,
    customer_id   INTEGER NOT NULL,
    invoice_date  DATE,
    amount        SYSUDTLIB.usd_amount,
    tax           SYSUDTLIB.usd_amount
)
PRIMARY INDEX (invoice_id);

-- Insert
INSERT INTO finance_db.invoices VALUES (
    1001, 42, DATE '2025-06-15',
    CAST(1500.00 AS SYSUDTLIB.usd_amount),
    CAST(135.00 AS SYSUDTLIB.usd_amount)
);

-- Query with ordering
SELECT invoice_id, amount
FROM finance_db.invoices
ORDER BY amount DESC;
```

## Pattern 2: Address Type (Structured Type with Methods)

### Step 1: Create the Structured Type

```sql
CREATE TYPE SYSUDTLIB.postal_address AS (
    line1    VARCHAR(100),
    line2    VARCHAR(100),
    city     VARCHAR(50),
    state    CHAR(2),
    zip      VARCHAR(10),
    country  CHAR(3) DEFAULT 'USA'
)
NOT FINAL
METHOD full_text() RETURNS VARCHAR(500)
    SPECIFIC full_text_method
    SELF AS RESULT;
```

### Step 2: Implement Methods

```sql
CREATE METHOD full_text()
FOR SYSUDTLIB.postal_address
RETURNS VARCHAR(500)
LANGUAGE SQL
CONTAINS SQL
DETERMINISTIC
SQL SECURITY DEFINER
RETURN TRIM(self.line1)
    || CASE WHEN self.line2 IS NOT NULL THEN ', ' || TRIM(self.line2) ELSE '' END
    || ', ' || TRIM(self.city)
    || ', ' || TRIM(self.state)
    || ' ' || TRIM(self.zip)
    || ', ' || TRIM(self.country);
```

### Step 3: Create Transforms

```sql
CREATE TRANSFORM FOR SYSUDTLIB.postal_address
    TD_INTERNAL (
        RETURN NEW postal_address(
            line1, line2, city, state, zip, country
        )
    );
```

### Step 4: Use in Tables

```sql
CREATE TABLE mydb.companies (
    company_id    INTEGER NOT NULL,
    company_name  VARCHAR(200),
    hq_address    SYSUDTLIB.postal_address,
    mail_address  SYSUDTLIB.postal_address
)
PRIMARY INDEX (company_id);

-- Insert using constructor
INSERT INTO mydb.companies VALUES (
    1, 'Acme Corp',
    NEW postal_address('100 Industrial Blvd', NULL, 'Austin', 'TX', '78701', 'USA'),
    NEW postal_address('PO Box 1234', NULL, 'Austin', 'TX', '78701', 'USA')
);

-- Query using dot notation
SELECT company_name,
       hq_address.city,
       hq_address.state,
       hq_address.full_text()
FROM mydb.companies;
```

## Pattern 3: Array Type for Multi-Valued Attributes

### Create Array Types

```sql
-- Phone number list
CREATE TYPE SYSUDTLIB.phone_numbers AS VARCHAR(20) ARRAY[5];

-- Email list
CREATE TYPE SYSUDTLIB.email_list AS VARCHAR(100) ARRAY[10];

-- Score history
CREATE TYPE SYSUDTLIB.scores AS DECIMAL(5,2) ARRAY[50];
```

### Use in Tables

```sql
CREATE TABLE mydb.employees (
    emp_id     INTEGER NOT NULL,
    emp_name   VARCHAR(100),
    phones     SYSUDTLIB.phone_numbers,
    emails     SYSUDTLIB.email_list
)
PRIMARY INDEX (emp_id);
```

### Array Operations

```sql
-- Insert
INSERT INTO mydb.employees VALUES (
    1, 'Alice Johnson',
    NEW phone_numbers('555-0100', '555-0101', '555-0102'),
    NEW email_list('alice@work.com', 'alice@home.com')
);

-- Access individual elements (1-based indexing)
SELECT emp_name, phones[1] AS primary_phone, emails[1] AS primary_email
FROM mydb.employees;

-- CARDINALITY — get number of elements
SELECT emp_name, CARDINALITY(phones) AS phone_count
FROM mydb.employees;
```

### VARRAY vs ARRAY

| Feature | ARRAY | VARRAY |
|---------|-------|--------|
| Size | Fixed at declaration | Variable up to max |
| Storage | All elements allocated | Only populated elements stored |
| Best for | Known fixed-size collections | Variable-size collections |

## Pattern 4: ARRAY/VARRAY for Denormalization

Replace a child table with an array column.

```sql
-- Instead of a separate order_items table:
CREATE TYPE SYSUDTLIB.item_ids AS INTEGER ARRAY[100];

CREATE TABLE mydb.orders_denorm (
    order_id     INTEGER NOT NULL,
    customer_id  INTEGER,
    order_date   DATE,
    item_list    SYSUDTLIB.item_ids
)
PRIMARY INDEX (order_id);
```

### When to Denormalize with Arrays

| Scenario | Recommended |
|----------|-------------|
| Always access parent + children together | Array may help |
| Need to query/filter by child values | Keep separate table |
| Children have their own attributes | Keep separate table |
| Few children per parent (< 10) | Array can work |
| Many children per parent (> 100) | Keep separate table |

## UDT Lifecycle Management

### Versioning Pattern

When evolving UDTs:

```sql
-- 1. Create new version
CREATE TYPE SYSUDTLIB.address_v2 AS (
    line1    VARCHAR(100),
    line2    VARCHAR(100),
    city     VARCHAR(50),
    state    CHAR(2),
    zip      VARCHAR(10),
    country  CHAR(3) DEFAULT 'USA',
    county   VARCHAR(50)  -- new attribute
)
NOT FINAL;

-- 2. Migrate tables to new type
-- (Requires column drop + add — no in-place ALTER for UDT columns)

-- 3. Drop old type when no longer referenced
DROP TYPE SYSUDTLIB.address_v1;
```

### Checking UDT Dependencies

```sql
-- Find tables using a specific UDT
SELECT DatabaseName, TableName, ColumnName
FROM DBC.ColumnsV
WHERE ColumnUDTName = 'address_type'
ORDER BY DatabaseName, TableName;

-- Find functions using a UDT
SELECT DatabaseName, TableName AS FunctionName
FROM DBC.TablesV t
JOIN DBC.TextTbl x ON t.DatabaseName = x.DatabaseName AND t.TableName = x.TableName
WHERE x.TextString LIKE '%address_type%'
  AND t.TableKind = 'F';
```

## Restrictions and Limitations

| Restriction | Detail |
|-------------|--------|
| UDT storage | UDTs are stored in SYSUDTLIB by default |
| PI columns | UDT columns cannot be part of a primary index (unless ordering is defined) |
| Indexing | Limited secondary index support on UDT columns |
| Compression | Value-list compression not supported on UDT columns |
| JSON/XML interop | Cast to VARCHAR for JSON/XML serialization |
| Maximum attributes | Structured types limited by row-size constraints |
