# Teradata Large Object (LOB) Reference

> Source: 541-0004240-A02 — Teradata Large Object User Guide

---

## 1. LOB Storage Model

### Subtable Architecture

LOBs are stored **outside the base row** in a separate subtable. Each LOB column in a table gets its own dedicated subtable. An **OID** (Object Identifier, 50 bytes) is stored in the base table row as a reference pointer to the actual LOB value in the subtable.

- No matter how small or how large the LOB, it is **never stored in the row itself**
- LOB data is physically stored on the **same AMP** as the base table row
- A single LOB value is stored in the subtable as a **sequence of rows with consecutive Row IDs**
- LOBs are stored in **64,000-byte sections** — this supports efficient random access to specific sections
- LOB values are fall-backed to the same AMP as the base table rows
- If a PI update causes the row to move to another AMP, the LOBs move with the row

### Section Format

Each LOB is divided into sections of up to 64,000 bytes each. The **Sequence field** (15 bits) allows up to 2^15 - 1 = 32,767 sections per LOB. At 64,000 bytes per section, the maximum (and default) LOB size is **2,097,088,000 bytes** (~2 GB).

### LOB Row ID Layout

LOB rows use a specific Row ID format (listed by decreasing significance):

| Field | Length (bits) | Description |
|-------|--------------|-------------|
| Hash value | 32 | Same as the parent row's hash value — enables Rebuild/Reconfig to use standard algorithms; also used by locking protocol (lock on parent row also locks LOB subtable entries) |
| Uniqueness | 16 | Unique value assigned when object is created. Any value not used by another row with the same row hash. Note: half the bits available compared to ordinary rows |
| Sequence | 15 | Identifies a specific section within the LOB. Value 0 = LOB header row; first data section = 1; incremented by 1 per section |
| Reserved | 1 | Reserved |

### LOB Subtable Identifiers (TAI Values)

The LOB subtable identifier is computed as:

```
(1024 × FallbackId) + 768 + (LOBSeq × 2) - 2
```

Where:
- **FallbackId** = [1..16]. Primary Data = 1, Backup = 2
- **LOBSeq** = [1..32]. LOB sequence number implicitly assigned during CREATE/ALTER TABLE (retrievable from `DBC.TVFields.LobSequenceNo`)

The primary data LOB subtable range is **1792 to 1855**.

### Disk Storage Estimate

Approximate LOB disk storage requirements:

```
N × (OIDSIZE + ((row_overhead + 64,000) × M / 64,000))
```

Where:
- **N** = number of base table rows
- **M** = average LOB size in bytes
- **OIDSIZE** = 50 bytes
- **row_overhead** = 14 bytes for NPPI tables, 16 bytes for PPI tables

### LOB Storage Types

LOBs are stored in three types of tables:

| Storage Type | When Used |
|-------------|-----------|
| Permanent table | INSERT or UPDATE of a LOB |
| LOB response spool | SELECT of a LOB value |
| LOB scratch spool | Intermediate expressions (e.g., SUBSTR result before concatenation) |

- Scratch spool tables are dropped during step cleanup
- Response spool is dropped when the request ends

### Data Dictionary

`DBC.TVFields` fields for LOBs:

| Field | Value |
|-------|-------|
| FieldType | `CO` = CLOB, `BO` = BLOB |
| MaxLength | Default 2,097,088,000 |
| FieldFormat | `X(64000)` for BLOB/CLOB Latin; `X(32000)` for CLOB UNICODE |
| LobSequenceNo | 1–32 based on CREATE/ALTER TABLE order |

---

## 2. BLOB vs CLOB

### BLOB (Binary Large Object)

- Variable length **binary** string
- First 8 bytes specify the length
- Stored in **client system format** — no translation between client and server
- Length function (`BYTES`) returns number of **bytes**
- Can be CAST to/from VARBYTE and BYTE

### CLOB (Character Large Object)

- Variable length **character** string
- First 8 bytes specify the length
- Has a server-side character data type of **LATIN** or **UNICODE**
- Stored in **Teradata internal character format** — translation occurs on the server
- Length functions (`CHARACTER_LENGTH`, `CHAR_LENGTH`) return number of **characters**
- For UNICODE CLOBs, `FNC_GetLobLength` returns `characters × 2` (byte count)
- Can be CAST to/from VARCHAR and CHAR
- Supports `CHARACTER SET` attribute (LATIN or UNICODE)
- Three possible translation types: external→internal, internal→external, internal→internal

### Data Type Codes (Client/Server Interface)

| Data Type | Code | Description |
|-----------|------|-------------|
| BLOB | 400 | BLOB data type |
| BLOB | 401 | BLOB data type, NULLable |
| BLOB as Deferred | 404 | 4-byte token for deferred client→server transfers |
| BLOB as Locator | 408 | Locator — variable length binary, first 2 bytes = length |
| CLOB | 416 | CLOB data type |
| CLOB | 417 | CLOB data type, NULLable |
| CLOB as Deferred | 420 | 4-byte token for deferred client→server transfers |
| CLOB as Locator | 424 | Locator — variable length binary, first 2 bytes = length |

---

## 3. CREATE TABLE Syntax

### Type Declaration

```sql
BINARY LARGE OBJECT | BLOB [ ( N [ K | M | G ] ) ] [attributes]
CHARACTER LARGE OBJECT | CLOB [ ( N [ K | M | G ] ) ] [attributes]
```

**N** — Maximum number of bytes that can be stored. Actual length is variable. If unspecified, defaults to maximum LOB size (2,097,088,000 bytes).

Size suffixes (ANSI standard):
- **K** = 1,024 bytes
- **M** = 1,024 × 1,024 bytes (1,048,576)
- **G** = 1,024 × 1,024 × 1,024 bytes (1,073,741,824)

### Supported Attributes

| Attribute | Notes |
|-----------|-------|
| `NULL` | A NULL LOB is represented by a NULL OID in the base table row |
| `NOT NULL` | Supported |
| `TITLE` | Supported |
| `CHARACTER SET` | Supported for CLOBs (LATIN or UNICODE) |
| `FORMAT` | Controls field-mode export (does NOT affect internal storage) |

### Default Formats

| Type | Default Format |
|------|---------------|
| `BLOB[(n)]` | `X(2n)` if n ≤ 32000; `X(64000)` if n > 32000 |
| `CLOB[(n)] CHARACTER SET LATIN` | `X(n)` if n < 64000; `X(64000)` if n ≥ 64000 |
| `CLOB[(n)] CHARACTER SET UNICODE` | `X(n)` if n < 32000; `X(32000)` if n ≥ 32000 |

> **Warning:** Default formats can cause `SELECT *` to overrun the max 64,000-byte returned row size (error 3577). Selecting two LOB columns without explicit FORMAT will trigger this.

### Unsupported DDL Attributes

- `UPPERCASE` / `CASESPECIFIC` — not supported
- `DEFAULT` / `WITH DEFAULT` — not supported
- `COMPRESS` — not supported
- Referential Integrity constraints on LOB columns
- `PRIMARY KEY` or `UNIQUE` attribute on LOB columns
- At least one column in the table **must** be a non-LOB type

### Example

```sql
CREATE TABLE orders
(
    orderkey INTEGER NOT NULL
   ,orderstatus  CHAR(1) NOT NULL CASESPECIFIC
   ,ordermessage CLOB(100M) FORMAT 'X(30)' CHARACTER SET LATIN NOT NULL
) UNIQUE PRIMARY INDEX(orderkey);
```

---

## 4. Supported Operations

### Functions and Operators ALLOWED on LOBs

| Operation | Description |
|-----------|-------------|
| `BYTES(blob_col)` | Returns the number of bytes in a BLOB |
| `CHARACTER_LENGTH(clob_col)` / `CHAR_LENGTH(clob_col)` | Returns the number of characters in a CLOB |
| `CAST` | BLOB ↔ VARBYTE ↔ BYTE; CLOB ↔ VARCHAR ↔ CHAR |
| `\|\|` (concatenation) | Concatenation operator — can combine LOBs and non-LOBs |
| `SUBSTRING` / `SUBSTR` | Extract a portion of a LOB; return type is LOB of the specified length |
| `TYPE` | Returns the data type name |
| Character set translations | LATIN ↔ UNICODE for CLOBs (server-side) |
| User Defined Functions | LOBs as input and output parameters via locator interface |
| Comparison to NULL | `IS NULL` / `IS NOT NULL` supported |
| Assignment | INSERT, UPDATE with LOB values |

### LOB Querying Examples

```sql
-- Extract portion of a LOB
SELECT orderkey, SUBSTR(ordermessage, 1, 1000) FROM orders;
-- Return type is CLOB(1000)

-- Search BLOB column (cast to comparable type)
SELECT * FROM orders WHERE CAST(ordermessage AS VARBYTE(2)) = 'D0CF'XBF;

-- Concatenate VARBYTE rows into a BLOB
SELECT ID, CAST(A AS BLOB) || CAST(B AS BLOB) || CAST(C AS BLOB)
FROM (
    SELECT a.ID
        ,MAX(CASE WHEN A.seq = 1 THEN A.bdata ELSE '0'XB END)
        ,MAX(CASE WHEN A.seq = 2 THEN A.bdata ELSE '0'XB END)
        ,MAX(CASE WHEN A.seq = 3 THEN A.bdata ELSE '0'XB END)
    FROM T A
    GROUP BY a.ID
) AS D (ID, A, B, C);
```

### Implicit Conversions

- There is no constant version of a LOB
- CHAR/BYTE and VARCHAR/VARBYTE constants are **implicitly converted** to CLOBs/BLOBs if necessary

---

## 5. Unsupported Operations

### Operators and Functions NOT Supported on LOBs

| Category | Specific Items |
|----------|---------------|
| **Comparison operators** | `=`, `<>`, `<`, `>`, `<=`, `>=`, `IN` |
| **Predicates** | `LIKE`, `EXISTS`, `NOT EXISTS` |
| **Functions** | `POSITION`, `TRIM`, `INDEX`, `MINDEX` |
| **Aggregate/Analytic functions** | All aggregate and analytical functions (unless via UDF) |
| **Clauses** | `GROUP BY`, `HAVING`, `QUALIFY`, `ORDER BY` |
| **Set operations** | `UNION`, `MINUS` (`EXCEPT`), `INTERSECT` |
| **DISTINCT** | `SELECT DISTINCT` with LOB columns |
| **WITH clause** | LOBs not supported in WITH clause |

### Feature Limitations (Not Enhanced for LOBs)

| Feature | Status |
|---------|--------|
| FastLoad | Not supported |
| MultiLoad | Not supported |
| FastExport | Not supported |
| TPump | Not supported |
| PP2 (Embedded SQL) | Not supported |
| Statistics collection on LOB columns | Not supported |
| Primary Index on LOB columns | Not supported |
| Secondary Indexes on LOB columns | Not supported |
| Partitioned Primary Indexes on LOB columns | Not supported |
| Referential Constraints | Not supported |
| Temporary and Volatile tables with LOB columns | Not supported |
| Join Indexes containing LOB columns | Not supported |
| Hash Indexes containing LOB columns | Not supported |
| Compression on LOB columns | Not supported |
| Stored Procedure IN/OUT LOB parameter types | Not supported (internal SQL on LOBs IS supported) |
| Updateable Cursors with inline BLOB in select | Not supported |

> **Note:** Missing behaviors can be provided using UDFs. LOBs can exist in rows that are joined on other (non-LOB) columns — the OIDs are just copied during joins.

---

## 6. Transfer Modes

### Overview

| Direction | Mode | Description |
|-----------|------|-------------|
| Client → Server | **Inline** | LOB data sent with non-LOB data in a single request message |
| Client → Server | **Deferred** | LOB data sent separately after request submission, in chunks |
| Client → Server | **Locator** | A previously-returned locator value is sent instead of LOB data |
| Server → Client | **Inline** | LOB data returned intermingled with non-LOB data |
| Server → Client | **Locator** | Locators returned instead of LOB values; LOBs fetched on demand |

### USING Clause Syntax (CLI)

```sql
-- Inline (default — no qualifier needed)
USING (A BLOB(10000), B INT)

-- Deferred
USING (A BLOB(10000) AS DEFERRED, B INT)

-- Locator
USING (A BLOB(10000) AS LOCATOR, B INT)
```

### Inline Transfer

- **Client → Server:** LOB + all other fields must fit in a single request message. Max LOB size = **MAXDATA** (~65 KB)
- **Server → Client:** No size limit (uses continue requests to handle multiple messages). LOB data is intermingled with non-LOB data across MultipartRecord parcels
- LOB must be fully materialized in client memory
- Appropriate for relatively small LOBs

### Deferred Transfer

- **Client → Server:** After the request is submitted, the server responds with an **ElicitData** parcel containing the 4-byte token placed in the data buffer. The client then sends LOB data in chunks via DBFCRQ with continuation codes (`F`=First, `I`=Intermediate, `L`=Last, `C`=Cancel)
- Appropriate for LOBs greater than MAXDATA
- LOB does NOT have to be fully materialized in memory — can be sent in chunks
- NULL LOBs still require a 4-byte token but the server will not elicit data for them

### Locator Transfer

- **Locators** are server-generated tokens (82 bytes) referencing a specific LOB value
- Locators are **unalterable** — invalidated if the source table.column.row is updated or deleted (stale OID detection, error 7516)
- Must be used from a currently open request in the **same session** as the generating SELECT

#### Locator Types

| Type | DBCAREA Setting | Validity |
|------|----------------|----------|
| **Static** (spool-related) | `return_object = 'S'` | Valid as long as the response spool exists, **even after transaction commits**. LOB value is copied to response spool |
| **Non-static** (transaction-related) | `return_object = 'T'` | Valid only while the **transaction is open** AND response spool exists. In Teradata mode, requires explicit `BT` |

#### Locator Format

| Field | Size |
|-------|------|
| Locator Length | 2 bytes |
| LOB Length | 8 bytes |
| Locator Body | remaining bytes |
| **Total** | **82 bytes** |

#### Fetching via Locator

```sql
-- Fetch a LOB using a previously-returned locator
USING (A BLOB AS LOCATOR) SELECT :A;

-- Update using a locator
USING (A BLOB AS LOCATOR) UPDATE t SET blobcolumn = :A;
```

### Response Modes

| Mode | LOB Values | Locators | Notes |
|------|-----------|----------|-------|
| **Field mode** | Yes (truncated to FORMAT) | No (error returned) | Max ~64,000 bytes; character representation |
| **Record / Indicator / Extended Indicator** | No | No | Neither LOB values nor locators allowed |
| **Multipart Indicator** (`resp_mode = 'M'`) | Yes (inline) | Yes (static or non-static) | Required mode for full LOB support |

### ANSI vs Teradata Mode Differences

| Behavior | Teradata Mode | ANSI Mode |
|----------|--------------|-----------|
| **Truncation** | Silently truncated, no error | Error 2893 "Right truncation of string data" if non-pad characters truncated |
| **Locators** | Non-static locators require explicit `BT` | Transactions not committed until explicit `COMMIT` |

---

## 7. Design Rules and Limits

### Hard Limits

| Limit | Value |
|-------|-------|
| Maximum LOB columns per table | **32** |
| Maximum LOB size | **2,097,088,000 bytes** (~2 GB) |
| Maximum NUPI duplicates (same hash) for LOB tables | **65,536** (2^16) due to 16-bit uniqueness field |
| Maximum LOB sections | **32,767** (2^15 - 1) |
| Section size | **64,000 bytes** |
| OID size | **50 bytes** |
| Locator size | **82 bytes** |
| MAXDATA (inline max) | **~65 KB** |
| MAXPARCELSIZE | **~64 KB** |
| MAXREQSIZE | **1 MB** |
| Max outstanding UDF read contexts | **2** per UDF invocation |
| Max outstanding responses per session | **16** (error 3130 if exceeded) |

### Structural Rules

- At least one column in the table **must** be a non-LOB type
- LOB columns **cannot** be part of: Primary Index, Secondary Index, Partitioned Primary Index
- LOB subtables are NOT impacted by physical storage parameters (free space, block size)
- LOB subtables **are partitioned** (for PPI tables) in the same manner as the primary subtable — `ALTER TABLE` to drop a partition drops the corresponding partition in each LOB subtable
- LOBs can **accentuate storage skew** — skew in base table is magnified by LOB size, though processing skew may not follow due to OID indirection
- NUPIs with LOBs may cause congestion of LOBs on a single AMP

### Fallback Behavior

- LOB values are fall-backed to the same AMP as the base table rows
- There is no independent fallback for LOB subtables — fallback follows the base table

### Stored Procedure Restrictions

- LOBs are **not** supported as input or output parameters
- LOBs are **not** supported as local variables
- Internal SQL operations on LOBs within stored procedures **are** supported

### EXPLAIN Impact

- Operations involving a LOB column require an **End Transaction (EDT)** step for proper transaction journaling
- This is visible in EXPLAIN plans as an additional EDT step

---

## 8. Recovery Behavior

### Transaction Recovery (Transient Journal)

LOBs are **never written to the TJ** — instead, logical operations are recorded:

| Operation | TJ Behavior |
|-----------|-------------|
| **INSERT** | One TJ record per LOB column — logical UNDO of the insert |
| **DELETE** | One TJ record per LOB column — logical UNDO. LOBs are NOT physically deleted until transaction commits (before-image always exists) |
| **UPDATE** | Partial LOB updates are NOT supported. Old LOB replaced by new LOB (both exist for transaction duration). TJ records: delete record for old OID + insert record for new OID |

### Down-AMP Recovery (Change Journal)

- CJ records are generated for **each LOB row** (each section) inserted, updated, or deleted in the LOB subtable
- A LOB is treated as a **collection of rows** for CJ purposes — one CJ record per LOB section

### Permanent Journaling

- PJ records are generated for **each LOB row** (section) inserted, updated, or deleted
- LOB is treated as a collection of rows — journal records contain before/after images of LOB sections
- Tables with LOB columns have **increased PJ append and storage costs**

### Concurrency Control

- All LOB concurrency control is managed through **locks on the base table row** that references the LOB
- All LOB accesses require first reading the OID in the base table row
- **Exception:** Locators used outside the originating transaction are NOT protected by any locks
- **Stale OID detection:** Any change to a LOB's state after a reference is generated triggers error **7516** when the reference is used

---

## 9. Performance Considerations

### Copy-on-Demand Model

- Intermediate result spool files **share by OID reference** the original LOB value — minimizes copying
- LOB data is only read/copied when actually needed (e.g., by a function invocation)
- Both AMP-local and remote AMP read modes are supported

### Locator vs Inline Tradeoffs

| Approach | Pros | Cons |
|----------|------|------|
| **Inline** | Simpler; LOB data returned with query results | Must transfer all LOBs even if not needed; limited to MAXDATA for client→server |
| **Static Locator** | Valid beyond transaction; fetch on demand | LOB value copied to response spool (expensive); more overhead than non-static |
| **Non-static Locator** | Only OID copied to spool (cheapest); fetch on demand | Valid only within open transaction; requires explicit `BT` in Teradata mode |

### Key Performance Facts

1. LOBs passed to UDFs require materialization if data type conversion occurs (e.g., VARBYTE→BLOB, BLOB(200M)→BLOB(100M))
2. UDF LOB access reads an **entire disk block** even if only 1 byte is requested
3. For UDFs operating on LOBs, use **LOB value approximation** (first N bytes) to reduce I/O
4. Static locators are more expensive than non-static — LOB value must be copied to spool
5. PI operations on LOB tables require a **participating AMP End Transaction** step
6. Many duplicate row-hash values degrade performance for frequent LOB updates — uniqueness value search once 2^16 overflows
7. Queries not touching LOB columns are **not impacted**
8. PI updates may cause LOBs to be **redistributed**
9. NUPIs can cause LOB congestion on a single AMP — LOB size amplifies uneven distribution
10. LOBs stored in Permanent Journal increase PJ append and storage costs
11. Remote LOB access (cross-AMP) incurs additional message-based data transfer costs

### Benchmark Reference

Test environment: 1-way 1000MHz client (W2K), 4-way 256MHz 4400 server (MPRAS), 10Mbps Ethernet

| Operation | LOB Size | Mode | Throughput (MB/s) |
|-----------|----------|------|-------------------|
| Insert 300 LOBs | 60 KB | Inline | 0.65 |
| Insert 300 LOBs | 60 KB | Deferred | 0.65 |
| Insert 20 LOBs | 16 MB | Deferred (64K buffer) | 2.64 |
| Insert 10 LOBs | 536 MB | Deferred (64K buffer) | 2.89 |
| Select 20 LOBs | 16 MB | Inline | 3.8 |
| Select 20 LOBs | 16 MB | Deferred Static | 5.52 |
| Select 20 LOBs | 16 MB | Deferred Non-Static | 6.67 |

---

## 10. UDF LOB Interface

### General Principles

- UDF LOB interface is based on **LOB locators** — enables manipulation without loading entire object into memory
- `AS LOCATOR` must be specified for each LOB parameter and return value in the CREATE FUNCTION DDL
- A locator is valid only in the scope of the UDF to which it is passed
- Aggregate UDFs can convert locators to persistent references (`LOB_REF`) for use across calls

### UDF CREATE FUNCTION Examples

```sql
-- Scalar UDF with LOB parameters
CREATE FUNCTION ResizeImage (Image BLOB AS LOCATOR, Factor FLOAT)
    RETURNS BLOB AS LOCATOR
    LANGUAGE C
    NO SQL
    PARAMETER STYLE SQL
    EXTERNAL;

-- Aggregate UDF
CREATE FUNCTION MAX_BLOB(X BLOB AS LOCATOR)
    RETURNS BLOB AS LOCATOR
    CLASS AGGREGATE(600)
    LANGUAGE C
    NO SQL
    PARAMETER STYLE SQL
    EXTERNAL;

-- Multi-input scalar UDF
CREATE FUNCTION concat3
    (A BLOB AS LOCATOR,
     B VARBYTE(64000),
     C BLOB AS LOCATOR)
    RETURNS BLOB AS LOCATOR
    LANGUAGE C
    NO SQL
    EXTERNAL
    PARAMETER STYLE TD_GENERAL;
```

### C Data Types (sqltypes_td.h)

| Type | Description |
|------|-------------|
| `LOB_LOCATOR` (long) | Argument type when parameter declared with `AS LOCATOR`. Valid within scope of UDF call |
| `LOB_RESULT_LOCATOR` (long) | Return value type for LOB return with `AS LOCATOR`. Used with `FNC_LobAppend` |
| `LOB_CONTEXT_ID` (long) | Handle returned by `FNC_LobOpen`, used by `FNC_LobRead` and `FNC_LobClose` |
| `FNC_LobLength_t` (unsigned long) | Return type of length functions |
| `LOB_REF` (struct, OIDSIZE bytes) | Persistent object reference valid for duration of request. For aggregate/ordered analytic UDFs only |

### LOB Access Functions

| Function | Description |
|----------|-------------|
| `FNC_GetLobLength` | Returns length in bytes. For UNICODE CLOB = characters × 2. Does NOT cause a disk read |
| `FNC_LobOpen` | Establishes read context with starting offset and max length. Max 2 outstanding contexts per UDF (error 7555 if exceeded). Returns length of data stream |
| `FNC_LobRead` | Sequential read using context. Returns actual bytes read in `*actual_length` |
| `FNC_LobClose` | Releases read context resources. All contexts closed implicitly on UDF return. Explicit close needed only when max contexts reached and another LOB must be read |
| `FNC_LobAppend` | Appends bytes to result LOB. Only for UDFs returning a LOB type. In aggregate UDFs, only in `AGR_FINAL` phase. Truncation if result exceeds max length |
| `FNC_LobLoc2Ref` | Converts locator → persistent `LOB_REF`. Aggregate/ordered analytic UDFs only (error if called from scalar UDF) |
| `FNC_LobRef2Loc` | Converts `LOB_REF` → locator. Aggregate/ordered analytic UDFs only |

### UDF Performance Tips

- Avoid unnecessary type conversions (e.g., define overloaded UDF accepting VARBYTE to avoid implicit VARBYTE→BLOB conversion which creates a temp BLOB on disk)
- Omit length specification in parameter declaration to avoid truncation checks (accepts max-length LOB)
- For aggregate UDFs, store first N bytes of LOB in interim data area to avoid re-reading LOBs from remote AMPs

---

## 11. LOB Error Codes

| Error | Code | Context |
|-------|------|---------|
| ERRTEQMANYLOBFIELDS | 5659 | Too many LOB fields |
| ERRTEQLOBINDEX | 5660 | LOB index error |
| ERRTEQLOBCOLLSTAT | 5661 | LOB collect statistics |
| ERRTEQLOBNUM | 5662 | LOB number error |
| ERRTEQLOBNUMC | 5663 | LOB numeric error |
| ERRTEQLOBAGR | 5664 | LOB aggregate error |
| ERRTEQLOBOLAP | 5665 | LOB OLAP error |
| ERRTEQDLOBINDX | 5666 | LOB index error |
| ERRTEQLOBORDERBY | 5670 | LOB in ORDER BY |
| ERRTEQLOBWITH | 5671 | LOB in WITH clause |
| ERRTEQLOBFIELDMODE | 5673 | LOB field mode error |
| ERRTEQLOBRECMODE | 5674 | LOB in Record/Indicator mode (not allowed) |
| ERRTEQLOBKEEPRESP | 5675 | LOB keep response error |
| ERRTEQLOBCOMPARE | 5689 | LOB comparison not supported |
| ERRTEQLOBRESPBUF | 5778 | LOB response buffer error |
| ERRAMPSTALE | 7516 | Stale OID — LOB value modified after reference generated |
| ERRAMPCTLOBCOUNT | 7517 | LOB count error |
| ERRAMPCTPRMFALLOBCOUNT | 7518 | Primary/fallback LOB count |
| ERRAMPCTLOBORDER | 7519 | LOB order error |
| ERRAMPCTLOBDUP | 7520 | LOB duplicate error |
| ERRAMPCTLOBPRMAMP | 7521 | LOB primary AMP error |
| ERRAMPCTLOBFALAMP | 7522 | LOB fallback AMP error |
| ERRAMPCTLOBSUBTBL | 7523 | LOB subtable error |
| ERRAMPCTLOBDROWOID | 7524 | LOB row OID error |
| ERRAMPCTLOBNOFAL | 7525 | LOB no fallback |
| ERRAMPCTLOBNOPRM | 7526 | LOB no primary |
| ERRAMPCTLOBOIDTAGS | 7527 | LOB OID tags error |

### Common Errors in Practice

| Error | When |
|-------|------|
| 3577 | Row size overflow — SELECT * with default LOB format exceeds 64K row limit |
| 2655 | Invalid parcel sequences during Load — USING clause specifies LOB type in BTEQ |
| 2893 | Right truncation of string data (ANSI mode only) |
| 3130 | Response limit exceeded — 16 outstanding responses per session (close streams/result sets) |
| 7516 | Stale OID — locator used after source LOB was updated/deleted |
| 7555 | Context cannot be allocated — exceeded 2 read contexts per UDF |

---

## 12. Glossary

| Term | Definition |
|------|-----------|
| **LOB** | Large Object — includes BLOBs and CLOBs |
| **OID** | Object Identifier — 50-byte reference stored in base table row pointing to LOB subtable value. Never manipulated by application developers |
| **Locator** | Externalized 82-byte reference to a LOB value (not the same as OID). Contains consistency information. Used for efficient client/server transfers |
| **Section** | Storage unit within the LOB subtable — up to 64,000 bytes each |
| **Chunk** | Subset of LOB value transferred during client/server interactions |
| **MAXDATA** | Maximum inline LOB data from client to server — ~65 KB |
| **MAXPARCELSIZE** | Maximum parcel size — ~64 KB |
| **MAXREQSIZE** | Maximum client→server request message size — 1 MB |
| **OIDSIZE** | Size of an OID — 50 bytes |
