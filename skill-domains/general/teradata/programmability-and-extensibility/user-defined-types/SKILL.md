---
name: user-defined-types
description: 'Create and manage Teradata user-defined types (UDTs) using CREATE TYPE DDL including structured types, distinct types, and ARRAY/VARRAY types. Also covers CREATE CAST, CREATE ORDERING, CREATE TRANSFORM, ALTER TYPE, and DROP TYPE. Use when defining custom data types, creating structured types with methods, defining distinct types for type safety, creating array types for multi-valued columns, setting up type casts and transforms, or managing UDT lifecycle.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata User-Defined Types (UDTs)

## When to Use

- Creating custom data types with domain-specific semantics
- Defining structured types with attributes and methods
- Using distinct types for type-safe columns (e.g., currency, temperature)
- Creating ARRAY/VARRAY types for multi-valued attributes
- Setting up casts between UDTs and built-in types
- Defining ordering for UDTs (for comparisons and sorting)
- Creating transforms for client-server data transfer

## UDT Categories

| Type | Purpose | Example |
|------|---------|---------|
| **Structured** | Complex types with named attributes and methods | Address, Point, Money |
| **Distinct** | Type-safe wrapper around a built-in type | USD_Amount, Celsius |
| **ARRAY/VARRAY** | Fixed or variable-length array of elements | PhoneNumbers, Tags |

## CREATE TYPE (Structured Form)

```sql
CREATE TYPE [SYSUDTLIB.]type_name AS (
    attribute_name  data_type [,...] 
)
[NOT FINAL | FINAL]
[INSTANTIABLE | NOT INSTANTIABLE]
[METHOD method_name (parameters) RETURNS return_type
    [SPECIFIC specific_name]
    [SELF AS RESULT]
    [,...]]
;
```

### Structured Type Example

```sql
CREATE TYPE SYSUDTLIB.address_type AS (
    street   VARCHAR(100),
    city     VARCHAR(50),
    state    CHAR(2),
    zip      VARCHAR(10),
    country  CHAR(3) DEFAULT 'USA'
)
NOT FINAL;
```

### Using Structured Type in a Table

```sql
CREATE TABLE mydb.customers (
    customer_id   INTEGER NOT NULL,
    customer_name VARCHAR(100),
    home_address  SYSUDTLIB.address_type,
    work_address  SYSUDTLIB.address_type
)
PRIMARY INDEX (customer_id);
```

### Accessing Structured Type Attributes

```sql
-- Insert
INSERT INTO mydb.customers VALUES (
    1, 'John Smith',
    NEW address_type('123 Main St', 'Springfield', 'IL', '62701', 'USA'),
    NEW address_type('456 Corp Ave', 'Chicago', 'IL', '60601', 'USA')
);

-- Query attributes using dot notation
SELECT customer_name,
       home_address.city,
       home_address.state
FROM mydb.customers;
```

## CREATE TYPE (Distinct Form)

```sql
CREATE TYPE [SYSUDTLIB.]type_name AS source_type FINAL;
```

### Distinct Type Examples

```sql
-- Currency type — prevents mixing dollars and euros
CREATE TYPE SYSUDTLIB.usd_amount AS DECIMAL(15,2) FINAL;
CREATE TYPE SYSUDTLIB.eur_amount AS DECIMAL(15,2) FINAL;

-- Temperature types
CREATE TYPE SYSUDTLIB.celsius AS DECIMAL(5,2) FINAL;
CREATE TYPE SYSUDTLIB.fahrenheit AS DECIMAL(5,2) FINAL;
```

### Using Distinct Types

```sql
CREATE TABLE mydb.transactions (
    txn_id     INTEGER NOT NULL,
    usd_value  SYSUDTLIB.usd_amount,
    eur_value  SYSUDTLIB.eur_amount
)
PRIMARY INDEX (txn_id);

-- This prevents accidentally comparing USD to EUR without explicit cast
```

## CREATE TYPE (ARRAY/VARRAY Form)

```sql
-- Fixed-size ARRAY
CREATE TYPE [SYSUDTLIB.]type_name AS data_type ARRAY[max_elements];

-- Variable-size VARRAY
CREATE TYPE [SYSUDTLIB.]type_name AS data_type VARRAY[max_elements];
```

### Array Type Examples

```sql
-- Array of phone numbers (up to 5)
CREATE TYPE SYSUDTLIB.phone_list AS VARCHAR(20) ARRAY[5];

-- Array of scores
CREATE TYPE SYSUDTLIB.score_array AS DECIMAL(5,2) ARRAY[100];

-- Variable-length array of tags
CREATE TYPE SYSUDTLIB.tag_list AS VARCHAR(50) VARRAY[20];
```

### Using Array Types

```sql
CREATE TABLE mydb.contacts (
    contact_id    INTEGER NOT NULL,
    contact_name  VARCHAR(100),
    phones        SYSUDTLIB.phone_list
)
PRIMARY INDEX (contact_id);

-- Insert with array constructor
INSERT INTO mydb.contacts VALUES (
    1, 'Jane Doe',
    NEW phone_list('555-0100', '555-0101')
);

-- Access array elements
SELECT contact_name, phones[1], phones[2]
FROM mydb.contacts;
```

## Supporting DDL

### CREATE CAST

Defines how to convert between a UDT and another type.

```sql
CREATE CAST (source_type AS target_type)
    WITH function_name
    [AS ASSIGNMENT]
;
```

```sql
-- Cast from DECIMAL to usd_amount
CREATE CAST (DECIMAL(15,2) AS SYSUDTLIB.usd_amount)
    WITH SYSUDTLIB.decimal_to_usd
    AS ASSIGNMENT;

-- Cast from usd_amount to DECIMAL
CREATE CAST (SYSUDTLIB.usd_amount AS DECIMAL(15,2))
    WITH SYSUDTLIB.usd_to_decimal
    AS ASSIGNMENT;
```

### CREATE ORDERING

Defines comparison semantics for a UDT (required for ORDER BY, GROUP BY, indexes).

```sql
CREATE ORDERING FOR SYSUDTLIB.usd_amount
    ORDER FULL BY RELATIVE WITH SYSUDTLIB.usd_compare;
```

### CREATE TRANSFORM

Defines how to serialize/deserialize UDTs for client-server transfer.

```sql
CREATE TRANSFORM FOR SYSUDTLIB.address_type
    server_to_client (
        RETURN CAST(street || '|' || city || '|' || state AS VARCHAR(200))
    )
    client_to_server (
        -- parsing logic
    );
```

### SET TRANSFORM GROUP

```sql
SET TRANSFORM GROUP FOR TYPE SYSUDTLIB.address_type TD_INTERNAL;
```

## ALTER TYPE

```sql
-- Add an attribute to a structured type
ALTER TYPE SYSUDTLIB.address_type ADD ATTRIBUTE county VARCHAR(50);

-- Drop an attribute
ALTER TYPE SYSUDTLIB.address_type DROP ATTRIBUTE county;

-- Add a method
ALTER TYPE SYSUDTLIB.address_type ADD METHOD full_address()
    RETURNS VARCHAR(300);
```

## DROP TYPE

```sql
DROP TYPE [SYSUDTLIB.]type_name;
```

> Cannot drop a type that is referenced by tables, other types, or functions.

## Supporting Object Cleanup

```sql
DROP CAST (DECIMAL(15,2) AS SYSUDTLIB.usd_amount);
DROP ORDERING FOR SYSUDTLIB.usd_amount;
DROP TRANSFORM FOR SYSUDTLIB.address_type;
```

## Querying UDT Metadata

```sql
-- List all UDTs
SELECT TypeName, TypeKind, DatabaseName
FROM DBC.UDTInfoV
ORDER BY TypeName;

-- TypeKind values: 'S' = Structured, 'D' = Distinct, 'A' = Array

-- View UDT attributes
HELP TYPE SYSUDTLIB.address_type;

-- Show UDT definition
SHOW TYPE SYSUDTLIB.address_type;
```

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| 5604: Type already exists | CREATE TYPE with existing name | Drop first or choose a different name |
| 5605: Type not found | Reference to non-existent UDT | Check type name and database (usually SYSUDTLIB) |
| 6926: No ordering defined | ORDER BY or comparison on UDT without ordering | Create an ordering for the type |
| 7545: No cast defined | Implicit conversion attempted without cast | Create a cast between the types |

## Privileges Required

- `UDTUSAGE` on the UDT or on SYSUDTLIB to use a UDT in table columns
- `UDTTYPE` on SYSUDTLIB to create new types
- `UDTMETHOD` on SYSUDTLIB to create methods on types
- `CREATE FUNCTION` on SYSUDTLIB for cast/ordering/transform functions

## References


> **Access:** `skill_resource_read(action="read", skill="user-defined-types", path="references/FILENAME")` — do NOT call `list`.

- [UDT Implementation Patterns](./references/udt-implementation-patterns.md) — End-to-end examples of structured, distinct, and array type implementation with casts, ordering, and transforms

> Source: Teradata SQL Data Definition Language Syntax and Examples, B035-1144, Release 20.00, Chapter 12
