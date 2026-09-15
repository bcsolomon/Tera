# Character Sets and Encoding

> Source: *International Character Sets and the Teradata Database Engine*, 541-0004068

## Server Character Sets

Teradata supports four server character sets for storing user data. Unlike other database systems, Teradata allows specifying different server character sets **at the column level** within the same table.

| Server Character Set | Canonical Form | Encoding | Max CHAR(n) | Supported Languages |
|---|---|---|---|---|
| **UNICODE** | Yes | UTF-16 (BMP) | 32,000 chars | All languages supported by Unicode 6.0 BMP |
| **LATIN** (Teradata Latin) | Yes | ISO 8859-1 / 8859-15 | 64,000 chars | Western European (Latin1/Latin9) |
| **KANJISJIS** | Yes | Shift-JIS | 32,000 chars | Japanese |
| **GRAPHIC** | Yes | Double-byte | 32,000 chars | CJK (DB2 compatibility) |

**UNICODE is strongly recommended** for all new implementations. KANJISJIS and GRAPHIC are legacy character sets maintained for backward compatibility.

### Column-Level Character Set Specification

```sql
CREATE TABLE multilingual_data (
    id           INTEGER,
    country_code CHAR(2) CHARACTER SET LATIN,
    customer_name VARCHAR(100) CHARACTER SET UNICODE,
    address       VARCHAR(200) CHARACTER SET UNICODE,
    legacy_field  VARCHAR(50) CHARACTER SET KANJISJIS  -- avoid for new work
);
```

If no character set is specified, the column inherits the **user's default character set**:
- Standard systems default to LATIN
- Japanese systems default to UNICODE
- DBSControl field 78 can override the system default

```sql
-- Check DBSControl default character set
-- 78. Default Character Set = 0 (UNICODE) or 1 (LATIN)
```

### User Default Character Set

```sql
-- Create user with specific default character set
CREATE USER usr_unicode FROM dbc
AS PASSWORD = xxx
DEFAULT DATABASE = my_db
DEFAULT CHARACTER SET UNICODE;

-- Query default character sets for all users
SELECT UserName, DefaultCharType,
  CASE
    WHEN DefaultCharType = 1 THEN 'LATIN'
    WHEN DefaultCharType = 2 THEN 'UNICODE'
    WHEN DefaultCharType = 3 THEN 'KANJISJIS'
    WHEN DefaultCharType = 4 THEN 'GRAPHIC'
    ELSE 'UNKNOWN'
  END AS CharsetName
FROM DBC.Users
ORDER BY 1;

-- Or check your own session
HELP SESSION;
-- Look at "Default Character Type" column
```

### Internal Hex Representation

Use `CHAR2HEXINT()` to inspect the internal server encoding:

```sql
CREATE TABLE hex_demo (
    id   INTEGER,
    name VARCHAR(30) CHARACTER SET UNICODE
);

INSERT INTO hex_demo VALUES (1, 'A');
INSERT INTO hex_demo VALUES (2, 'Aあ');

SELECT name, CHAR2HEXINT(name) FROM hex_demo;
```

| Server Charset | Displayed | CHAR2HEXINT Value |
|---|---|---|
| UNICODE | `A` | `0041` |
| LATIN | `A` | `41` |
| UNICODE | `Aあ` | `00413042` |

## Session Character Sets (Client Character Sets)

A session character set defines how the Database Engine translates character data between client and server forms. The session character set is specified at connection time and controls all character conversions for that session.

### Pre-installed Session Character Sets

These four are always available without installation:

| Session Charset | Charset ID | Use Case |
|---|---|---|
| **ASCII** | — | Legacy 7-bit ASCII (do NOT use for non-ASCII data) |
| **EBCDIC** | — | Mainframe applications |
| **UTF8** | — | **Recommended** — universal multilingual support |
| **UTF16** | — | Unicode applications needing wide characters |

### Optional Session Character Sets

Additional session character sets must be loaded, installed, and activated:

```sql
-- Step 1: Load all session character sets (run on server)
-- Execute /usr/tdbms/etc/DIPCCS.bteq

-- Step 2: Install desired character sets
UPDATE DBC.CharTranslationsV
SET InstallFlag = 'Y'
WHERE CharSetName = 'LATIN1252_3A0';

-- Step 3: Activate by restarting Database Engine (tpareset)

-- Step 4: Verify installed character sets
SELECT CharSetName, CharSetId, InstallFlag
FROM DBC.CharTranslationsV
ORDER BY CharSetId;
```

Maximum of 16 additional session character sets can be installed simultaneously.

### Legacy vs Current Session Character Sets

Windows code pages evolved over time, making some legacy Teradata session character sets incompatible:

| Windows Code Page | Description | Legacy Session Charset | Current Session Charset |
|---|---|---|---|
| 1252 | Western European | LATIN1252_0A | **LATIN1252_3A0** |
| 1250 | Eastern European | LATIN1250_0A | **LATIN1250_1A0** |
| 932 | Japanese Shift-JIS | KANJISJIS_0S | **KANJI932_1S0** |
| 936 | Simplified Chinese GBK | SCHGB2312_1T0 | **SCHINESE936_6R0** |
| 949 | Korean KSC 5601 | HANGLEKSC5601_2R4 | **HANGUL949_7R0** |
| 950 | Traditional Chinese Big-5 | TCHBIG5_1R0 | **TCHINESE950_8R0** |

Legacy character sets may not support all characters defined in the corresponding Windows code page. For ANSI applications on Windows, use the current (fully compatible) session character sets.

### Setting the Session Character Set

**BTEQ:**
```bash
# Command line
bteq -c UTF8

# Within BTEQ
.SET SESSION CHARSET UTF8
```

**ODBC (Windows):** Configure in ODBC Data Source Administrator → Session Character Set dropdown.

**ODBC (Linux):** Set in `.odbc.ini`:
```ini
[my_datasource]
Driver=/usr/odbc/drivers/tdata.so
DBCName=my_server
CharacterSet=UTF8
```

**JDBC:**
```java
String url = "jdbc:teradata://myserver/CHARSET=UTF8";
Connection con = DriverManager.getConnection(url, "user", "pass");
```

### Single-Session Character Set Limitation

Only one session character set is active per session. If a UNICODE column contains German, Japanese, and Korean characters and you connect via KANJISJIS_0S, you will get translation errors for German and Korean characters because KANJISJIS_0S only covers Japanese.

**Solution:** Always use UTF8 for multilingual environments.

## Encoding Conversion Flow

### Client to Server (Inbound)

1. Client application encodes data in the session character set
2. Database Engine receives the data
3. Database Engine translates from session character set → server character set
4. Data is stored in the server character set encoding

### Server to Client (Outbound)

1. Database Engine reads data in server character set
2. Database Engine translates from server character set → session character set
3. If a character cannot be translated, error 6705/6706 is raised
4. Translated data is sent to the client

### ODBC Unicode Driver Conversion

The Teradata ODBC driver is a Unicode driver supporting both Unicode and ANSI applications:

| | Unicode App (Windows) | Unicode App (Linux) | ANSI App |
|---|---|---|---|
| **App encoding** | UTF-16 | UTF-8 | Multibyte code page |
| **ODBC APIs** | `SQLxxxW()` | `SQLxxxW()` | `SQLxxx()` / `SQLxxxA()` |
| **Recommended session** | UTF8 or UTF16 | UTF8 | Matching code page or UTF8 |

The ODBC Driver Manager (Windows) automatically converts between the ANSI Code Page (ACP) and UTF-16. On Linux, set `IANAAppCodePage` in `odbc.ini` to define the application code page.

## Export Width

Export width determines how many bytes the Database Engine returns for character data. It is controlled by DBSControl field 23 (General section).

### Export Width Tables

| Table Name | Export ID | Description |
|---|---|---|
| Expected Default | 0 | Reasonable defaults for character type and session charset |
| Compatibility Default | 1 | Unicode columns behave as if Latin (for legacy apps) |
| Maximum Default | 2 | Maximum possible byte width |

### Bytes Returned for CHAR(n) — Expected Default

| Session Charset | Server: LATIN | Server: UNICODE | Server: KANJISJIS |
|---|---|---|---|
| LATIN1252_0A | n | n | n |
| KANJISJIS_0S | n | 2×n | n |
| UTF16 | 2×n | 2×n | 2×n |
| UTF8 | 2×n | **3×n** | n |

### VARCHAR vs CHAR Behavior Under UTF8

| Data Type (UNICODE) | Bytes Returned |
|---|---|
| VARCHAR(n) | Variable: up to 3×n bytes |
| CHAR(n) | Fixed: exactly 3×n bytes (padded with spaces) |

This means a UNICODE CHAR(2) column returns **6 bytes** under UTF8 session, even if data is ASCII. Solutions:

```sql
-- Option 1: TRIM trailing spaces
SELECT TRIM(field3) FROM my_table;

-- Option 2: CAST to VARCHAR
SELECT field3 (VARCHAR(2)) FROM my_table;

-- Option 3: Use TRANSLATE + CAST
SELECT TRANSLATE(field3 USING UNICODE_TO_KANJISJIS) (CHAR(2)) FROM my_table;
```

**Recommendation:** Use VARCHAR instead of CHAR for UNICODE columns to avoid export width padding issues.

## Unicode Pass Through (UPT)

UPT is a Unicode error handling feature that allows storage and retrieval of **all** Unicode characters, including those beyond BMP (supplementary planes, emoji, etc.).

### Character Categories

| Category | Count | Description |
|---|---|---|
| Teradata Supported (BMP) | ~60,992 | Standard Unicode 6.0 BMP characters |
| Pass Through Characters (PTCs) | ~1,053,000+ | Supplementary, unassigned, private use characters |
| Noncharacters | 66 | Replaced with U+FFFD (not storable) |

### Enabling UPT

```sql
-- Session level
SET SESSION CHARACTER SET UNICODE PASS THROUGH ON;

-- Verify
HELP SESSION;
-- UnicodePassThrough column: S = ON, F = OFF

-- System-wide (consult Teradata support)
```

### UPT Constraints

- **Requires** UTF8 or UTF16 session character set
- **Server character set** must be UNICODE
- **Data types:** CHAR, VARCHAR, CLOB only
- PTCs should **not** be stored in index columns
- PTCs are **not** supported in Extended Object Names
- String functions like SUBSTRING may split surrogate pairs (yielding U+FFFD)
- Inequality predicates may not work correctly with PTCs
- UPPER/LOWER have no effect on PTCs (no case mapping)

### UPT Product Support

| Product | UPT Support | How to Enable |
|---|---|---|
| Database Engine | Yes | `SET SESSION CHARACTER SET UNICODE PASS THROUGH ON/OFF` |
| BTEQ | Yes | Same SQL statement |
| ODBC Driver | Yes | Same SQL statement |
| JDBC Driver | Yes | SQL statement or `stmt.executeUpdate(...)` |
| TPT Operators | Yes | `VARCHAR UnicodePassThrough = 'ON'` in TPT script |
| FastLoad/MultiLoad | No | Not supported |
| .NET Data Provider | Yes | Same SQL statement |

### Inserting Supplementary Characters

```sql
SET SESSION CHARACTER SET UNICODE PASS THROUGH ON;

-- Insert emoji using hex constant
INSERT INTO my_table VALUES (1, 'D83DDE04'xc);  -- 😄

-- Insert using Unicode escape
INSERT INTO my_table VALUES (2, U&'\+01F604');
```

## Migrating from LATIN to UNICODE

### Pre-Migration Checks

```sql
-- Find rows with untranslatable characters
SELECT *
FROM my_table
WHERE TRANSLATE_CHK(latin_col USING LATIN_TO_UNICODE) <> 0;
```

### Migration Methods

**Method 1 — New table with INSERT-SELECT:**
```sql
CREATE TABLE my_table_new (
    id   INTEGER,
    name VARCHAR(100) CHARACTER SET UNICODE
) PRIMARY INDEX (id);

INSERT INTO my_table_new
SELECT id, name FROM my_table;
```

**Method 2 — ALTER TABLE (add/update/drop):**
```sql
ALTER TABLE my_table ADD name_unicode VARCHAR(100) CHARACTER SET UNICODE;
UPDATE my_table SET name_unicode = name;
ALTER TABLE my_table DROP name;
-- Note: column lifetime limit of 2,560 applies
```

### Migration Considerations

| Factor | Impact |
|---|---|
| **Storage** | UNICODE uses 2 bytes/char vs 1 for LATIN; size increase depends on column mix |
| **CHAR(n) max** | 64,000 for LATIN → 32,000 for UNICODE |
| **Row size** | Must remain <1 MB; prefer VARCHAR for UNICODE |
| **String literals** | Always UNICODE in SQL; use `TRANSLATE(x USING UNICODE_TO_LATIN)` for explicit LATIN |
| **ASCII session** | Never use ASCII session with UNICODE data |
| **Compression** | Use ALC (UTF8 or ZLIB) to offset storage growth |

### UTF8 Algorithmic Compression for UNICODE Columns

```sql
CREATE TABLE customer_compressed (
    id       INTEGER,
    name     VARCHAR(100) CHARACTER SET UNICODE
        COMPRESS USING TransUnicodeToUTF8
        DECOMPRESS USING TransUTF8ToUnicode,
    address  VARCHAR(200) CHARACTER SET UNICODE
        COMPRESS USING TransUnicodeToUTF8
        DECOMPRESS USING TransUTF8ToUnicode
) PRIMARY INDEX (id);
```

UTF8 compression achieves ~50% savings when data is mostly ASCII. For CJK ideographic characters (3 bytes in UTF8 vs 2 in UTF16), compression is skipped on those rows automatically.

## Data Loading with Unicode

### Byte Order Mark (BOM)

| Encoding | BOM | Notes |
|---|---|---|
| ANSI | None | |
| UTF-16 LE | `0xFFFE` | Windows standard |
| UTF-16 BE | `0xFEFF` | |
| UTF-8 | `0xEFBBBF` | Teradata tools auto-detect and skip BOM |

### Loading UTF-8 Data

```bash
# BTEQ with UTF8 session
bteq -c UTF8 < load_script.bteq

# TPT: specify UTF8 in the operator
VARCHAR SessionCharSet = 'UTF8'
```

### UTF-16 Endianness

| Endianness | Platforms |
|---|---|
| UTF16-LE (Little Endian) | Windows, Linux, Solaris Opteron |
| UTF16-BE (Big Endian) | Solaris SPARC, AIX, HP-UX, IBM Mainframe |

If transferring UTF-16 data files between platforms, ensure endianness matches or convert before loading.

### Filtering Invalid Characters During Loading

Translation errors (5356, 6705, 6706) occur when data contains:
- Characters undefined in the code page
- Replacement characters (U+001A or U+FFFD)
- Characters outside Unicode 6.0 BMP (without UPT)
- Malformed UTF-8 sequences

**Translation Access Modules** filter and convert source data to UTF8 before passing to load utilities. Invalid characters are replaced with a user-defined replacement character.

**Translation UDFs** validate and translate character data within SQL:
```sql
-- Use with TPT Update/Stream/Inserter operators
INSERT INTO target_table
SELECT id, TranslateUDF(source_col) FROM source_table;
```

## Changing a Column's Character Set

You cannot directly `ALTER TABLE` to change a column's character set. Use one of these approaches:

```sql
-- Option 1: New table approach
CREATE TABLE new_table AS (
    SELECT id,
           CAST(latin_col AS VARCHAR(100) CHARACTER SET UNICODE) AS col_unicode
    FROM old_table
) WITH DATA;

-- Option 2: Add column, update, drop
ALTER TABLE my_table ADD col_new VARCHAR(100) CHARACTER SET UNICODE;
UPDATE my_table SET col_new = col_old;
ALTER TABLE my_table DROP col_old;
```

## NOS (Native Object Store) Character Set Requirements

When creating foreign tables for NOS access to S3 or Azure, multibyte character columns **must** use UNICODE:

```sql
-- Correct: UNICODE for multibyte NOS columns
CREATE FOREIGN TABLE nos_data (
    location VARCHAR(2048) CHARACTER SET UNICODE,
    name     VARCHAR(100) CHARACTER SET UNICODE
)
USING (
    LOCATION ('/s3/bucket/path/data.csv')
    ROWFORMAT ('{"character_set":"UTF8"}')
    STOREDAS ('TEXTFILE')
);

-- NOT allowed: locale-specific character sets (KANJISJIS, etc.)
```

## Troubleshooting Translation Errors

| Error | Cause | Resolution |
|---|---|---|
| **5356** | Invalid character for target charset | Use TRANSLATE_CHK to locate; filter or enable UPT |
| **6705** | Request text contains untranslatable chars | Switch to UTF8 session; verify SQL file encoding |
| **6706** | Data contains untranslatable chars | Use TRANSLATE_CHK to find rows; fix source data or use translation UDFs |

```sql
-- Find the position of the first untranslatable character
SELECT key_col,
       TRANSLATE_CHK(text_col USING UNICODE_TO_LATIN) AS error_position
FROM my_table
WHERE TRANSLATE_CHK(text_col USING UNICODE_TO_LATIN) <> 0;
```
