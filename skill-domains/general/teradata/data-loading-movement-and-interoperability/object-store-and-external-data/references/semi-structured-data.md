# Semi-Structured Data Processing — Complete Reference

## JSON Data Type

Teradata supports a native JSON data type for storing JSON documents:

```sql
CREATE TABLE mydb.json_docs (
    id INTEGER,
    doc JSON(16776192)           -- Max ~16 MB
) PRIMARY INDEX (id);

-- With storage format
CREATE TABLE mydb.json_docs (
    id INTEGER,
    doc JSON(16776192) CHARACTER SET LATIN STORAGE FORMAT BSON
) PRIMARY INDEX (id);
```

### Storage Formats

| Format | Description | Best For |
|---|---|---|
| `TEXT` | Plain text JSON (default) | Human-readable, debugging |
| `BSON` | Binary JSON | Faster queries, smaller storage |
| `UBJSON` | Universal Binary JSON | Balance of speed and compatibility |

## JSON Dot Notation

Access JSON fields directly with `..` (double-dot) syntax:

```sql
-- Simple field access
SELECT doc..name FROM mydb.json_docs;

-- Nested field access
SELECT doc..address..city FROM mydb.json_docs;

-- Array element access
SELECT doc..items[0]..product FROM mydb.json_docs;

-- Cast to specific type
SELECT doc..price (DECIMAL(10,2)) FROM mydb.json_docs;
SELECT doc..name (VARCHAR(100)) FROM mydb.json_docs;
SELECT doc..active (INTEGER) FROM mydb.json_docs;

-- In WHERE clause
SELECT * FROM mydb.json_docs
WHERE doc..status (VARCHAR(20)) = 'active';
```

### Dot Notation Rules

- `..` (double-dot) navigates into JSON structure
- `.` (single-dot) is the standard SQL member separator
- Array indices are zero-based: `[0]`, `[1]`, etc.
- Cast with `(type)` at the end of the path expression
- NULL returned for missing fields (no error)

## JSONPath Expressions

For complex JSON queries beyond dot notation:

```sql
-- JSONPath with JSONExtractValue
SELECT JSONExtractValue(doc, '$.store.book[0].title')
FROM mydb.json_docs;

-- JSONPath with array filtering
SELECT JSONExtractValue(doc, '$.store.book[?(@.price < 10)].title')
FROM mydb.json_docs;
```

## JSON_TABLE

Project JSON data into relational columns:

```sql
SELECT jt.*
FROM mydb.json_docs d,
TABLE (JSON_TABLE(
    d.doc, '$'
    COLUMNS (
        customer_id   INTEGER       PATH '$.id',
        name          VARCHAR(100)  PATH '$.name',
        email         VARCHAR(200)  PATH '$.contact.email',
        order_count   INTEGER       PATH '$.orders.size()',
        first_order   DATE          PATH '$.orders[0].date'
    )
    ERROR ON ERROR          -- or DEFAULT ... ON ERROR
)) AS jt;
```

### JSON_TABLE Column Types

| Column Type | Syntax | Description |
|---|---|---|
| Regular | `name TYPE PATH '$.path'` | Extract scalar value |
| Exists | `name TYPE EXISTS PATH '$.path'` | Returns TRUE/FALSE |
| Nested | `NESTED PATH '$.array[*]' COLUMNS (...)` | Unnest arrays |
| Ordinality | `name FOR ORDINALITY` | Row number |

### Nested Arrays with JSON_TABLE

```sql
SELECT jt.*
FROM mydb.json_docs d,
TABLE (JSON_TABLE(
    d.doc, '$'
    COLUMNS (
        order_id INTEGER PATH '$.order_id',
        NESTED PATH '$.items[*]' COLUMNS (
            item_num    FOR ORDINALITY,
            product     VARCHAR(100) PATH '$.product',
            quantity    INTEGER      PATH '$.qty',
            price       DECIMAL(8,2) PATH '$.price'
        )
    )
)) AS jt;
```

## JSON_SHRED_BATCH

Bulk-load JSON into relational tables:

```sql
-- Create target table first
CREATE TABLE mydb.orders (
    order_id INTEGER,
    customer VARCHAR(100),
    total DECIMAL(10,2)
) PRIMARY INDEX (order_id);

-- Shred JSON into the table
SELECT * FROM TABLE (
    JSON_SHRED_BATCH (
        ON (SELECT id, doc FROM mydb.json_staging)
        USING (
            TABLENAME = 'mydb.orders'
            MAPPING = '{
                "order_id": "$.id",
                "customer": "$.customer_name",
                "total": "$.order_total"
            }'
        )
    )
) AS shred_result;
```

## JSON Composition Functions

### JSON_COMPOSE — Build JSON from Columns

```sql
SELECT JSON_COMPOSE(
    customer_id AS "id",
    name AS "customer_name",
    email AS "email"
) AS json_doc
FROM mydb.customers;
-- Returns: {"id":1,"customer_name":"John","email":"john@example.com"}
```

### JSON_AGG — Aggregate Rows into JSON Array

```sql
SELECT customer_id,
       JSON_AGG(JSON_COMPOSE(
           product AS "product",
           amount AS "amount"
       )) AS orders_json
FROM mydb.orders
GROUP BY customer_id;
-- Returns: [{"product":"Widget","amount":10.00},{"product":"Gadget","amount":25.00}]
```

---

## XML Data Type

```sql
CREATE TABLE mydb.xml_docs (
    id INTEGER,
    doc XML(2097088000)        -- Max ~2 GB
) PRIMARY INDEX (id);
```

## XMLEXTRACT — Extract Values

```sql
-- Extract text content
SELECT XMLEXTRACT(doc, '/root/name/text()') FROM mydb.xml_docs;

-- Extract attribute
SELECT XMLEXTRACT(doc, '/root/item/@id') FROM mydb.xml_docs;

-- Extract with namespace
SELECT XMLEXTRACT(doc, '/ns:root/ns:name/text()',
    'xmlns:ns="http://example.com/schema"')
FROM mydb.xml_docs;
```

## XMLTABLE — Relational Projection

```sql
SELECT xt.*
FROM mydb.xml_docs d,
TABLE (XMLTABLE(
    '/catalog/product' PASSING d.doc
    COLUMNS
        product_id   INTEGER      PATH '@id',
        name         VARCHAR(100) PATH 'name',
        price        DECIMAL(8,2) PATH 'price',
        category     VARCHAR(50)  PATH 'category',
        in_stock     INTEGER      PATH 'inventory/@count'
)) AS xt;
```

### XMLTABLE with Default Values

```sql
SELECT xt.*
FROM mydb.xml_docs d,
TABLE (XMLTABLE(
    '/orders/order' PASSING d.doc
    COLUMNS
        order_id     INTEGER      PATH '@id',
        status       VARCHAR(20)  PATH 'status' DEFAULT 'unknown',
        priority     INTEGER      PATH 'priority' DEFAULT 0
)) AS xt;
```

## XSLT Transformation

```sql
-- Transform XML using XSLT stylesheet
SELECT XMLTRANSFORM(doc USING stylesheet)
FROM mydb.xml_docs d
CROSS JOIN mydb.xslt_sheets s;
```

## XMLSPLIT — Split Large XML Documents

Split a single large XML into multiple smaller documents:

```sql
SELECT * FROM TABLE (
    XMLSPLIT(
        ON mydb.xml_docs
        USING (
            SPLITPATH = '/root/records/record'
            MAXDOCSIZE = 1000000
        )
    )
) AS split_result;
```

---

## DATASET Functions (CSV and Avro)

### DATASET_TABLE — Query CSV/Avro as Table

```sql
-- CSV file
SELECT dt.*
FROM TABLE (
    DATASET_TABLE (
        ON (SELECT csv_data FROM mydb.raw_files)
        USING (
            FORMAT = 'CSV'
            HEADER = 'TRUE'
            DELIMITER = ','
        )
        RETURNS (
            col1 VARCHAR(100),
            col2 INTEGER,
            col3 DECIMAL(10,2)
        )
    )
) AS dt;

-- Avro data
SELECT dt.*
FROM TABLE (
    DATASET_TABLE (
        ON (SELECT avro_data FROM mydb.raw_files)
        USING (
            FORMAT = 'AVRO'
        )
    )
) AS dt;
```

### DATASET_PUBLISH — Convert to CSV/Avro

```sql
-- Convert relational data to CSV
SELECT * FROM TABLE (
    DATASET_PUBLISH (
        ON (SELECT * FROM mydb.source_table)
        USING (
            FORMAT = 'CSV'
            HEADER = 'TRUE'
            DELIMITER = ','
        )
    )
) AS pub;

-- Convert to Avro
SELECT * FROM TABLE (
    DATASET_PUBLISH (
        ON (SELECT * FROM mydb.source_table)
        USING (
            FORMAT = 'AVRO'
        )
    )
) AS pub;
```

### CSV_TO_AVRO — Transform CSV to Avro

```sql
SELECT * FROM TABLE (
    CSV_TO_AVRO (
        ON mydb.csv_staging
        USING (
            AVRO_SCHEMA = '{"type":"record","name":"rec","fields":[
                {"name":"id","type":"int"},
                {"name":"name","type":"string"}
            ]}'
        )
    )
) AS converted;
```

---

## NOS + Semi-Structured Data Patterns

### Query JSON from S3 via Foreign Table

```sql
-- Create foreign table
CREATE FOREIGN TABLE mydb.ext_json_events
USING (
    LOCATION = '/s3/bucket.s3.amazonaws.com/events/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'JSON'
)
NO PRIMARY INDEX;

-- Query with dot notation
SELECT payload..event_type (VARCHAR(50)) AS event_type,
       payload..user_id (INTEGER) AS user_id,
       payload..timestamp (TIMESTAMP) AS event_ts
FROM mydb.ext_json_events
WHERE payload..event_type (VARCHAR(50)) = 'purchase';
```

### Shred NOS JSON into Relational Table

```sql
-- Read from S3 and insert into relational table
INSERT INTO mydb.events (event_type, user_id, event_ts)
SELECT payload..event_type (VARCHAR(50)),
       payload..user_id (INTEGER),
       payload..timestamp (TIMESTAMP)
FROM (
    LOCATION = '/s3/bucket.s3.amazonaws.com/events/'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_RECORD'
) AS nos_data;
```

### Query CSV from S3 via READ_NOS

```sql
SELECT payload..col1 (VARCHAR(100)) AS name,
       payload..col2 (INTEGER) AS quantity
FROM (
    LOCATION = '/s3/bucket.s3.amazonaws.com/csv_data/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'CSV'
    HEADER = 'TRUE'
    ROWFORMAT = '{"field_delimiter":","}'
    RETURNTYPE = 'NOSREAD_RECORD'
) AS csv_data;
```

## Approach Comparison

| Task | NOS Approach | In-Database Approach |
|---|---|---|
| Query external JSON | READ_NOS + dot notation | Load → JSON column + dot notation |
| Flatten JSON arrays | READ_NOS + JSON_TABLE | JSON column + JSON_TABLE |
| Bulk load JSON | READ_NOS INSERT-SELECT | Staged JSON + JSON_SHRED_BATCH |
| Query external CSV | READ_NOS STOREDAS CSV | Load → DATASET_TABLE |
| Process XML | N/A (XML not in NOS) | XML column + XMLTABLE |
| Export as JSON | WRITE_NOS STOREDAS JSON | JSON_COMPOSE + export |
