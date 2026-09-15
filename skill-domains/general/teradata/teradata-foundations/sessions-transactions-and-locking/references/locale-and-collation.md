# Locale and Collation

> Source: *International Character Sets and the Teradata Database Engine*, 541-0004068

## Specification for Data Formatting (SDF)

The Specification for Data Formatting (SDF) is a system-wide facility for internationalized output formatting of cultural data types: DECIMAL, BYTEINT, SMALLINT, INTEGER, REAL, DATE, TIME, and TIMESTAMP.

SDF is defined in a text file named `tdlocaledef.txt` and compiled by the `tdlocaledef` utility into an internal form used by the Database Engine.

### File Locations

| Component | Path |
|---|---|
| SDF source file | `/usr/tdbms/etc/tdlocaledef.txt` |
| tdlocaledef utility | `/usr/tdbms/bin/tdlocaledef` |

### SDF Scope

SDF defines **system-wide** formatting defaults. Every SQL statement submitted by any user and session is affected by the defaults defined in SDF. Users can override global definitions with explicit `FORMAT` and/or `CAST` statements.

### Configuring Date/Time Formatting

Localize day and month names by editing `tdlocaledef.txt`:

```
// Japanese day names
ShortDays {
  "\u65E5";   // 日 (Sun)
  "\u6708";   // 月 (Mon)
  "\u706B";   // 火 (Tue)
  "\u6C34";   // 水 (Wed)
  "\u6728";   // 木 (Thu)
  "\u91D1";   // 金 (Fri)
  "\u571F"    // 土 (Sat)
}
```

**Result:**
```sql
-- Default US English SDF
SELECT DATE (FORMAT 'EEE,BM4BDD,BYYYY');
-- Output: Thu, September 12, 1985

-- Localized Japanese SDF
SELECT DATE (FORMAT 'EEE,BM4BDD,BYYYY');
-- Output: 木, 9月 12, 1985
```

### Configuring Numeric and Currency Formatting

```
// German/Euro formatting in tdlocaledef.txt
RadixSeparator          {","}
GroupSeparator           {"."}
GroupingRule              {"3"}
Currency                 {"\u20AC"}     // € symbol
ISOCurrency              {"Euro"}
CurrencyName             {"Euro"}
CurrencyRadixSeparator   {","}
CurrencyGroupSeparator   {"."}
CurrencyGroupingRule     {"3"}
DualCurrency             {"\u20AC"}
DualISOCurrency          {"Euro"}
DualCurrencyName         {"Euro"}
```

**Result:**
```sql
-- Default US English SDF
SELECT 1234567.0 (FORMAT 'GLZZZZZZZ99D99');
-- Output: $ 1,234,567.00

-- Localized Euro SDF
SELECT 1234567.0 (FORMAT 'GLZZZZZZZ99D99');
-- Output: 1.234.567,00 €
```

### SDF with Open Access Interfaces

ODBC, JDBC, OLE DB, and .NET Data Provider do **not** apply SDF formatting automatically. To use SDF formatting through these interfaces, use an explicit CAST:

```sql
-- Works with BTEQ (uses Teradata CLI directly)
SELECT 1234567.0 (FORMAT 'G€-ZZZZZZZ99D99');

-- Required for ODBC/JDBC/Studio
SELECT CAST((1234567.0 (FORMAT 'G€-ZZZZZZZ99D99')) AS CHAR(14));
```

### Applying SDF Changes

After editing `tdlocaledef.txt`:

1. Run the `tdlocaledef` utility to compile the source into internal form
2. Restart the Database Engine for changes to take effect

## Collation Sequences

Teradata offers five standard collation sequences that control how character data is sorted and compared:

| Collation | Description | Use Case |
|---|---|---|
| **ASCII** | 7-bit ASCII binary order | Default for most systems; English-centric |
| **EBCDIC** | EBCDIC binary order | Mainframe compatibility |
| **CHARSET_COLL** | Matches the session character set order | Locale-consistent sorting per session charset |
| **JIS_COLL** | Japanese Industrial Standards order | Japanese character sorting |
| **MULTINATIONAL** | Customizable multilingual sort | User-defined sort order for international data |

### Collation Behavior

Collation affects `ORDER BY`, comparison operators, `BETWEEN`, `MIN`/`MAX`, and `GROUP BY` operations.

### Sort Order for Multibyte Data

When sorting text fields containing multibyte characters, the expected order is:

1. Numerical values
2. English letters
3. Single-byte Japanese characters (half-width Katakana)
4. Double-byte characters

### CHARSET_COLL

CHARSET_COLL provides collation matching the session character set. For example, if the session character set is `KANJIEBCDIC5035_0I`, CHARSET_COLL sorts in KANJIEBCDIC5035_0I order rather than default EBCDIC order.

### MULTINATIONAL Collation

MULTINATIONAL is the only customizable collation. Users can define the sorting specification through a collation name, allowing custom sort rules for specific language requirements.

```sql
-- Specify collation in ORDER BY
SELECT name FROM customers
ORDER BY name (CASESPECIFIC);
```

## Language Support Modes

The Database Engine supports two language support modes, configured during Sysinit:

### Standard Mode

- Supports all single-byte and multibyte character sets in data
- Default session character set: **LATIN**
- Object names limited to Teradata Latin characters (with Compatibility Standard name validation)
- During Sysinit: reply `no` to "Enable Japanese language support?"

### Japanese Mode

- Supports all single-byte and multibyte character sets in data (same as Standard)
- Default session character set: **UNICODE**
- Object names can include Japanese characters via Japanese or Unicode sessions
- Despite the name, supports all multibyte languages (Chinese, Korean, etc.)
- During Sysinit: reply `yes` to "Enable Japanese language support?"

### Checking the Current Mode

```sql
SELECT * FROM DBC.DBCInfoV;
```

| InfoKey | InfoData |
|---|---|
| VERSION | 20.00.28.42 |
| LANGUAGE SUPPORT MODE | Japanese |
| RELEASE | 20.00.28.42 |

### Impact on Default Character Sets

| Setting | Standard Mode | Japanese Mode |
|---|---|---|
| Default session charset | LATIN | UNICODE |
| Default server charset | Configurable via DBSControl field 78 | Configurable via DBSControl field 78 |

## Extended Object Names (EON)

Database Engine supports Extended Object Names, allowing Unicode characters in database, table, column, and other object names.

### Name Validation Rules

| Rule | Max Characters | Repertoire | Languages |
|---|---|---|---|
| **Globalization** (default) | 128 | Teradata Unicode 6.0 BMP | English, Japanese, Chinese, Western European, others |
| **Multinational** | 128 | Installed session charsets | Varies by installed charsets |
| **Compatibility Standard** | 30 | Teradata Latin | English, Western European |
| **Minimum** | 128 | Basic Latin | English only |

Name validation rules are a system-wide option. Object names containing characters outside 7-bit ASCII must be enclosed in double quotes:

```sql
-- Object name with accented characters (requires double quotes)
CREATE TABLE "Kundendaten_für_Müller" (
    id INTEGER,
    name VARCHAR(100) CHARACTER SET UNICODE
);

-- Query the table
SELECT * FROM "Kundendaten_für_Müller";
```

### Data Dictionary Views

The Data Dictionary stores object names as UNICODE internally. Two types of views:

| View Type | Example | Charset | Status |
|---|---|---|---|
| **Modern** (V/VX suffix) | `DBC.TablesV`, `DBC.ColumnsVX` | UNICODE | **Recommended** |
| **Compatibility** | `DBC.Tables` | Varies | **Deprecated** — will be removed |

```sql
-- Use modern views for Unicode object names
SELECT DatabaseName, TableName
FROM DBC.TablesV
WHERE DatabaseName = 'my_db';
```

### Data Dictionary Column Definitions

Object name columns in the Data Dictionary are defined as:

```
-- dbc.tvm.TVMNameI (database/table/user names)
VARCHAR(128) CHARACTER SET UNICODE UPPERCASE NOT CASESPECIFIC NOT NULL
```

## DBS Control Settings for Internationalization

### Key DBSControl Fields

| Field | Setting | Description |
|---|---|---|
| **Field 23** (General) | Export Width Table ID | Controls export width behavior (0=Expected, 1=Compatibility, 2=Maximum) |
| **Field 78** (General) | Default Character Set | System default: 0=UNICODE, 1=LATIN |

```sql
-- Check current DBSControl settings (requires DBA access)
-- Field 23: Export Width Table ID = 0 (Expected Defaults)
-- Field 78: Default Character Set = 0 (UNICODE)
```

### Setting Export Width at User Level

Export width can also be configured per user to avoid changing table definitions:

```sql
-- Create a view with appropriate TRIM/CAST for export width management
CREATE VIEW my_view AS
SELECT id,
       TRIM(char_col) AS char_col,  -- Remove padding
       varchar_col
FROM my_table;
```

## Character Set Considerations for SQL

### String Literals Are Always UNICODE

In SQL processing, string literals are always treated as UNICODE. When comparing against LATIN columns, implicit translation occurs:

```sql
-- Implicit UNICODE-to-LATIN translation for comparison
WHERE latin_column = 'abc'

-- Explicit LATIN literal (avoids implicit translation)
WHERE latin_column = TRANSLATE('abc' USING UNICODE_TO_LATIN)

-- CASE expression with explicit translation
CASE
  WHEN latin_col = TRANSLATE('-1' USING UNICODE_TO_LATIN)
  THEN TRANSLATE(' ' USING UNICODE_TO_LATIN)
  ELSE latin_col
END
```

### SQL Keywords Must Be Single-Byte

Although CJK character sets support full-width English letters, all SQL keywords and syntax **must** use half-width (single-byte) ASCII characters.

### Euro Symbol in Object Names

To use the Euro symbol (€) in object names:
- System must be initialized as Standard
- Session charset must support €: LATIN1252, LATIN9, UTF8, UTF16, or a custom charset with € support

```sql
-- With UTF8 session
CREATE TABLE "€_pricing" (
    id INTEGER,
    amount DECIMAL(18,2)
);
```

## ODBC Configuration for Linux

### Key odbc.ini Parameters

| Parameter | Description | Example |
|---|---|---|
| `CharacterSet` | Session character set name | `UTF8`, `KANJISJIS_0S` |
| `IANAAppCodePage` | Application code page (numeric) | `2024` (Japanese CP932) |
| `KanjiFormat` | Legacy kanji format (deprecated) | `SJIS`, `EUC` |
| `ClientKanjiFormat` | Output conversion format (deprecated) | `SJIS`, `EUC` |

```ini
# Recommended: UTF8 configuration
[my_teradata]
Driver=/usr/odbc/drivers/tdata.so
DBCName=my_server
CharacterSet=UTF8

# Japanese Shift-JIS configuration
[my_teradata_jp]
Driver=/usr/odbc/drivers/tdata.so
DBCName=my_server
CharacterSet=KANJISJIS_0S
IANAAppCodePage=2024
```

### Linux Environment Variables for UTF-8

```bash
export LANG=en_US.utf8
export LC_ALL=en_US.utf8
```

## JDBC Configuration

The Teradata JDBC driver supports UTF8 and UTF16 session character sets for any language:

```java
// UTF8 session (recommended)
String url = "jdbc:teradata://myserver/CHARSET=UTF8";
Connection con = DriverManager.getConnection(url, "user", "pass");

// Or use TeraDataSource.setCharSet() method
TeraDataSource ds = new TeraDataSource();
ds.setCharSet("UTF8");
```

The JDBC driver automatically converts between UTF-8 and UTF-16 when sending/receiving data. Maximum SQL request text length is ~500,000 characters (1 million bytes / 2 bytes per UTF-16 character).

## Best Practices Summary

1. **Use UNICODE server character set** for all new tables and columns
2. **Use UTF8 session character set** as the default for all client connections
3. **Design Unicode end-to-end** for global data warehouse implementations
4. **Prefer VARCHAR over CHAR** for UNICODE columns to avoid export width padding
5. **Do not use ASCII session** for non-ASCII character data
6. **Enable Unicode Pass Through** if you need to store emoji or supplementary characters
7. **Use modern Data Dictionary views** (V/VX suffix) instead of compatibility views
8. **Set DBSControl field 78** to UNICODE (0) for system-wide default character set
9. **Test with TRANSLATE_CHK** before migrating columns from LATIN to UNICODE
10. **Use UTF8 ALC compression** to offset UNICODE storage overhead for mostly-ASCII data
