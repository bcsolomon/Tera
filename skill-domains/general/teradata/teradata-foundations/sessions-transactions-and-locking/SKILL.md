---
name: teradata-internationalization
description: 'Configure and manage Teradata character sets, locale settings, collation, and client interface encoding. Use when setting up multi-language support, troubleshooting character encoding issues, configuring LATIN vs UNICODE vs KANJISJIS character sets, understanding server-to-client encoding conversions, or managing NLS (National Language Support) settings.'
metadata:
  author: teradata-expert
  version: "1.0"
---

# Teradata Internationalization

## When to Use

- Configuring server character sets (LATIN, UNICODE, KANJISJIS, GRAPHIC) on table columns
- Setting up or changing session character sets for client connections (UTF8, UTF16, ODBC, JDBC)
- Troubleshooting translation errors (6705, 6706, 5356) during data loading or retrieval
- Migrating columns or tables from LATIN to UNICODE character set
- Configuring Specification for Data Formatting (SDF) for locale-specific output
- Understanding export width behavior for multibyte data
- Setting up Unicode Pass Through (UPT) for supplementary Unicode characters
- Configuring collation sequences (ASCII, MULTINATIONAL, CHARSET_COLL) for sort behavior
- Working with Extended Object Names (EON) and name validation rules
- Loading UTF-8 or UTF-16 encoded data files via TPT, FastLoad, or MultiLoad
- Diagnosing character set mismatches between client applications and the Database Engine

## Core Concepts

### Character Set Architecture

Teradata uses three distinct character set layers that must be coordinated:

| Layer | Description | Configuration Level |
|---|---|---|
| **Server Character Set** | Internal storage encoding for column data (UNICODE, LATIN, KANJISJIS, GRAPHIC) | Column-level in CREATE TABLE DDL |
| **Session Character Set** | Defines client-to-server translation; also called "client character set" | Session-level (ODBC DSN, BTEQ `-c`, JDBC URL) |
| **Data Dictionary Character Set** | Encoding for object names, titles, comments | System-wide (always UNICODE internally) |

### Server Character Sets

| Server Character Set | Encoding | Use Case |
|---|---|---|
| **UNICODE** | UTF-16 (BMP) | Multilingual data — **strongly recommended** |
| **LATIN** (Teradata Latin) | ISO 8859-1/8859-15 | Single-byte Western European languages |
| **KANJISJIS** | Shift-JIS | Japanese (legacy — prefer UNICODE) |
| **GRAPHIC** | Double-byte | DB2 compatibility (CJK) |

Columns default to the user's default character set if not specified explicitly in DDL:
```sql
-- Explicit per-column character set
CREATE TABLE customer (
    id         INTEGER,
    gender     CHAR(1) CHARACTER SET LATIN,
    full_name  VARCHAR(100) CHARACTER SET UNICODE,
    address    VARCHAR(200) CHARACTER SET UNICODE
);
```

### Session Character Sets

For multilingual support, **UTF8 is strongly recommended** as the session character set. It is the de facto standard and handles all Unicode characters without locale-specific limitations.

Pre-installed session character sets (always available, no install needed): **ASCII**, **EBCDIC**, **UTF8**, **UTF16**.

Additional session character sets (e.g., KANJISJIS_0S, LATIN1252_3A0) must be loaded, installed, and activated:
```sql
-- Check installed session character sets
SELECT CharSetName, CharSetId, InstallFlag
FROM DBC.CharTranslationsV
ORDER BY CharSetId;

-- Install a session character set
UPDATE DBC.CharTranslationsV
SET InstallFlag = 'Y'
WHERE CharSetName = 'KANJISJIS_0S';
-- Requires tpareset to activate
```

### Encoding Conversion Flow

When a client sends or receives character data, conversion happens inside the Database Engine:

1. **Client → Server:** Client data in session character set → translated to server character set for storage
2. **Server → Client:** Server character set data → translated to session character set for export

If the session character set cannot represent a character in the server data, a translation error occurs (6705/6706). Using UTF8 as the session character set avoids most translation errors.

### Export Width

Export width controls how many bytes the Database Engine returns for character columns. It is governed by DBSControl field 23:

| Export Width Table | ID | Behavior |
|---|---|---|
| Expected Default | 0 | Reasonable defaults per character set |
| Compatibility Default | 1 | Unicode columns behave like Latin for legacy apps |
| Maximum Default | 2 | Maximum byte width for the character set |

For a UNICODE CHAR(n) column under UTF8 session with Expected Default, the export width is **3×n bytes** (fixed). Use VARCHAR to avoid unnecessary padding.

## Procedure: Checking Your Character Set Environment

```sql
-- 1. Determine system language support mode
SELECT * FROM DBC.DBCInfoV;
-- Look for LANGUAGE SUPPORT MODE = Standard or Japanese

-- 2. Check default server character set (DBSControl field 78)
-- 0 = UNICODE, 1 = LATIN

-- 3. Find your user's default character set
SELECT UserName, DefaultCharType,
  CASE WHEN DefaultCharType = 1 THEN 'LATIN'
       WHEN DefaultCharType = 2 THEN 'UNICODE'
       WHEN DefaultCharType = 3 THEN 'KANJISJIS'
       WHEN DefaultCharType = 4 THEN 'GRAPHIC'
       ELSE 'UNKNOWN'
  END AS DefaultCharsetName
FROM DBC.Users
ORDER BY 1;

-- 4. Check current session character set
HELP SESSION;
```

## Procedure: Migrating a Column from LATIN to UNICODE

1. **Pre-check for untranslatable data:**
   ```sql
   SELECT * FROM my_table
   WHERE TRANSLATE_CHK(latin_col USING LATIN_TO_UNICODE) <> 0;
   ```
2. **Option A — Create new table and INSERT-SELECT:**
   ```sql
   CREATE TABLE my_table_unicode AS my_table WITH NO DATA;
   -- Redefine target columns as UNICODE, then:
   INSERT INTO my_table_unicode SELECT * FROM my_table;
   ```
3. **Option B — ALTER TABLE to add new columns, update, drop old:**
   ```sql
   ALTER TABLE my_table ADD new_col VARCHAR(100) CHARACTER SET UNICODE;
   UPDATE my_table SET new_col = old_col;
   ALTER TABLE my_table DROP old_col;
   ```

**Migration considerations:**
- UNICODE columns use 2 bytes per character (vs 1 for LATIN) — plan for storage growth
- CHAR(n) max is 32,000 for UNICODE vs 64,000 for LATIN
- Row size limit remains <1 MB — prefer VARCHAR over CHAR for UNICODE columns
- Never use ASCII session with UNICODE data

## Procedure: Enabling Unicode Pass Through (UPT)

UPT allows storage and retrieval of all Unicode characters (including supplementary/emoji) beyond BMP:

```sql
-- Enable UPT for current session
SET SESSION CHARACTER SET UNICODE PASS THROUGH ON;

-- Verify UPT status
HELP SESSION;
-- Check UnicodePassThrough column: S=ON, F=OFF

-- Insert emoji/supplementary characters
INSERT INTO my_table VALUES (1, 'D83DDE04'xc);  -- 😄
```

UPT requires UTF8 or UTF16 session character set. Pass Through Characters (PTCs) are stored as UTF-16 surrogate pairs.

## Procedure: Troubleshooting Translation Errors

| Error | Meaning | Resolution |
|---|---|---|
| **5356** | Invalid character for target character set | Filter with TRANSLATE_CHK or enable UPT |
| **6705** | Untranslatable character in request text | Switch to UTF8 session or fix SQL encoding |
| **6706** | Untranslatable character in data | Use TRANSLATE_CHK to find offending rows, then fix or filter |

```sql
-- Find rows with untranslatable characters
SELECT key_col, TRANSLATE_CHK(text_col USING UNICODE_TO_LATIN) AS err_pos
FROM my_table
WHERE TRANSLATE_CHK(text_col USING UNICODE_TO_LATIN) <> 0;
```

## Key SQL Functions

| Function | Purpose |
|---|---|
| `TRANSLATE(col USING from_TO_to)` | Convert between server character sets |
| `TRANSLATE_CHK(col USING from_TO_to)` | Check translatability (returns 0 if OK, else position of error) |
| `CHAR2HEXINT(col)` | Display internal hex representation of character data |
| `HASHBAKAMP(col)` | Hash function that respects character set encoding |

```sql
-- Convert UNICODE column to LATIN
SELECT TRANSLATE(unicode_col USING UNICODE_TO_LATIN) FROM my_table;

-- Check if all rows can translate cleanly
SELECT COUNT(*)
FROM my_table
WHERE TRANSLATE_CHK(text_col USING UNICODE_TO_LATIN) <> 0;
```

## Best Practices

- **Use UNICODE** as the server character set for all new tables
- **Use UTF8** as the session character set for all client connections
- **Prefer VARCHAR over CHAR** for UNICODE columns to avoid export width padding
- **Never use ASCII session** for non-ASCII character data
- **Enable UPT** if you need emoji or supplementary Unicode characters
- **Test with TRANSLATE_CHK** before migrating LATIN columns to UNICODE
- **Use modern Data Dictionary views** (V/VX suffix) — compatibility views are deprecated

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-internationalization", path="references/FILENAME")` — do NOT call `list`.

- [references/character-sets-and-encoding.md](references/character-sets-and-encoding.md) — Server/session/client character set details, storage sizes, encoding conversions, export width, Unicode Pass Through
- [references/locale-and-collation.md](references/locale-and-collation.md) — SDF configuration, collation sequences, date/time formatting, name validation rules, NLS settings
