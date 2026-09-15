# Transaction and Session Reference

> Sources: SQL Fundamentals (B035-1141-111A, Release 14.0), SQL Request and Transaction Processing

---

## 1. ANSI vs Teradata Session Mode

Two session modes govern transaction behavior, character comparison defaults, and DDL handling:

| Feature | Teradata Session Mode | ANSI Session Mode |
|---|---|---|
| **Transaction start** | Implicit per request (or explicit BT/ET) | Implicit — first statement starts txn |
| **Transaction end** | End of request (implicit) or ET (explicit) | Explicit COMMIT or ROLLBACK |
| **Implicit commit** | Each request auto-commits on success | No implicit commit — must COMMIT |
| **DDL in transactions** | Must be last statement in explicit txn; not allowed in multistatement requests | Must be last statement in transaction |
| **Character comparison** | NOT CASESPECIFIC by default | CASESPECIFIC (ANSI-compliant) |
| **Duplicate row handling** | SET tables reject duplicates silently on INSERT…SELECT | SET tables return error on duplicates |
| **NULL sort order** | NULL sorts as lowest value | NULL sorts as highest value |
| **Two-Phase Commit** | Supported | NOT supported (logon aborts with error) |
| **Error handling** | Entire request/transaction rolls back | Failed statement rolls back; transaction stays open |

### Setting Session Mode

```sql
-- DBS Control: SessionMode field in DBS Control Record
-- BTEQ:
.SET SESSION TRANSACTION BTET   -- Teradata mode
.SET SESSION TRANSACTION ANSI   -- ANSI mode
-- Preprocessor2: TRANSACT(BTET) or TRANSACT(ANSI)
-- ODBC: SessionMode option in .odbc.ini
-- JDBC: TeraDataSource.setTransactMode()
```

---

## 2. Transaction Handling

### Implicit Transactions (Teradata Mode)

A request without BT/ET is an implicit transaction — it starts and completes within the SQL request:

- A single DML statement affecting one or more rows
- A macro or trigger containing one or more statements
- A multistatement request (multiple statements separated by `;`)

If any statement fails, the entire implicit transaction rolls back:
1. Back out all changes from preceding statements
2. Delete associated spooled output
3. Release associated locks
4. Bypass remaining statements

**Exception:** When a multistatement request contains only simple INSERTs, a failure of one INSERT does not roll back the entire request. Errors are reported for failed INSERTs; successful ones are retained.

### Explicit Transactions (Teradata Mode)

```sql
BEGIN TRANSACTION;
  UPDATE accounts SET balance = balance - 100 WHERE acct_id = 1001;
  UPDATE accounts SET balance = balance + 100 WHERE acct_id = 1002;
END TRANSACTION;
```

- One or more statements enclosed by `BEGIN TRANSACTION` and `END TRANSACTION`
- DDL is permitted only as the **last** statement in the series
- A DDL statement cannot be part of a multistatement request

### ANSI Mode Transactions

```sql
-- Transaction starts implicitly with first executable statement
UPDATE accounts SET balance = balance - 100 WHERE acct_id = 1001;
UPDATE accounts SET balance = balance + 100 WHERE acct_id = 1002;
COMMIT;       -- explicitly commits
-- or
ROLLBACK;     -- explicitly rolls back (ABORT is a synonym)
```

- If a session terminates with an open transaction, effects are rolled back
- DDL must be the last statement in a transaction (DATABASE and SET SESSION are DDL)

### Two-Phase Commit (2PC) — Teradata Mode Only

- Contains one or more DML statements affecting multiple databases, coordinated externally
- DDL is not valid in a 2PC transaction
- ANSI mode does NOT support 2PC (logon aborts with error)

---

## 3. Multistatement Requests

An atomic request containing multiple SQL statements separated by semicolons.

```sql
-- Syntax: statements separated by semicolons
INSERT INTO dept_summary SELECT deptno, COUNT(*) FROM employee GROUP BY deptno;
UPDATE dept_counts SET last_refresh = CURRENT_TIMESTAMP;
SELECT * FROM dept_summary ORDER BY deptno;
```

### Rules and Restrictions

- Only **one** USING modifier is permitted per multistatement request
- A multistatement request **cannot** include a DDL statement
  - Exception: one `SET QUERY_BAND … FOR TRANSACTION` is allowed as the first statement
- In stored procedures, must be delimited by `BEGIN REQUEST` and `END REQUEST`
- The entire request is treated as one implicit transaction (Teradata mode)

### Parallel Step Processing

Statements are broken down by the Parser into steps that the AMPs execute:

- Up to **20 parallel steps** per request when no redistribution channels are needed (e.g., PI equality lookups)
- Up to **10 channels** for parallel processing when redistribution is required (joins, INSERT…SELECT)
- A handshaking protocol between PE and AMP determines when the next parallel step can be dispatched
- Steps (not statements) are the unit of parallel execution

### Performance Benefits

- A 10-statement multistatement request can be up to **10× more efficient** than 10 separate requests
- Reduces processing overhead for the client, Parser, and Database Manager
- Decreases response time by reducing round-trip overhead

### Statement Independence for Simple INSERTs

When a multistatement request contains only simple INSERT statements, failure of individual INSERTs does **not** cause the entire request to roll back.

---

## 4. Iterated Requests

A single DML statement executed against multiple data records (bulk operation).

```sql
-- BTEQ example with USING clause
USING (pid INTEGER, pname CHAR(12))
INSERT INTO ptable VALUES(:pid, :pname);

-- Precede with REPEAT to pack records:
.REPEAT RECS 200 PACK 100
```

### Supported DML Statements

- ABORT, DELETE (non-positioned), EXECUTE macro_name, INSERT, MERGE, ROLLBACK, SELECT, UPDATE (including atomic UPSERT, excluding positioned UPDATE)

### Rules

- The DML statement must reference user-supplied input data (named fields in USING modifier or `?` parameter markers)
- All data records must use the same record layout
- The server processes iterated requests as if they were a single multistatement request
- Each iteration is associated with a corresponding statement number
- USING modifier with TOP n operator is **not** supported

### Tool/Interface Facilities

| Tool/Interface | Facility |
|---|---|
| CLIv2 (network) | `using_data_count` field in DBCAREA |
| CLIv2 (channel) | `Using-data-count` field in DBCAREA |
| ODBC | Parameter arrays |
| JDBC type 4 driver | Batch operations |
| OLE DB Provider | Parameter sets |
| BTEQ | `.REPEAT` command, `.SET PACK` command |

---

## 5. Session Management

### DATABASE Statement

Sets the default database for unqualified object name resolution during the current session:

```sql
DATABASE personnel;
-- Now unqualified references resolve against 'personnel' first
SELECT deptno, name FROM employee;
-- Equivalent to:
SELECT deptno, name FROM personnel.employee;
```

- You must have some privilege on an object in the target database
- Remains in effect until end of session or replaced by another `DATABASE` statement

### Default Database Resolution Order

When an unqualified object name is used, Teradata searches in this order:
1. The **default database** (set by DATABASE statement or CREATE/MODIFY USER)
2. Other databases referenced in the SQL statement
3. The **login user database** (for volatile tables)
4. The **SYSLIB database** (for C/C++ UDFs not found in default database)

If the name exists in more than one database, an **ambiguous name error** is returned.

### Establishing a Permanent Default Database

```sql
-- Set permanent default for a user (takes effect at next logon)
MODIFY USER marks AS DEFAULT DATABASE = personnel;
-- Or via profile
CREATE PROFILE std_profile AS DEFAULT DATABASE = personnel;
```

### SET SESSION Commands

```sql
SET SESSION COLLATION ASCII;           -- Change collation
SET SESSION DATEFORM ANSIDATE;         -- DATE format
SET SESSION ACCOUNT 'account_id/$H';   -- Change priority
SET SESSION CHARSET 'UTF8';            -- Client character set
```

### Session Parameters Summary

| Parameter | Options |
|---|---|
| SQL Flagger | ON / OFF (NONE, ENTRY, INTERMEDIATE) |
| Transaction Mode | ANSI (COMMIT) / Teradata (BTET) |
| Session Collation | ASCII, EBCDIC, MULTINATIONAL, HOST, CHARSET_COLL, JIS_COLL |
| Account/Priority | $R, $H, $M, $L performance groups |
| Date Form | ANSIDATE / INTEGERDATE |
| Character Set | ASCII, EBCDIC, UTF-8, UTF-16, or site-installed |

### HELP SESSION

Returns attributes in effect for the current session: transaction mode, character set, collation sequence, date form, query band.

---

## 6. Dynamic SQL

### Embedded SQL — PREPARE / EXECUTE

```sql
-- PREPARE compiles SQL text at runtime
EXEC SQL PREPARE stmt1 FROM :sql_text;
-- EXECUTE runs the prepared statement with host variables
EXEC SQL EXECUTE stmt1 USING :param1, :param2;
-- EXECUTE IMMEDIATE combines PREPARE + EXECUTE (no input variables)
EXEC SQL EXECUTE IMMEDIATE :sql_text;
```

### Dynamic SQL in Stored Procedures — SysExecSQL

```sql
CREATE PROCEDURE new_sales_table(my_table VARCHAR(30), my_database VARCHAR(30))
BEGIN
  DECLARE sales_columns VARCHAR(128)
    DEFAULT '(item INTEGER, price DECIMAL(8,2), sold INTEGER)';
  CALL DBC.SysExecSQL('CREATE TABLE ' || my_database || '.' || my_table || sales_columns);
END;
```

- A stored procedure can make any number of calls to `SysExecSQL`
- The request text can specify a multistatement request (delimited by `BEGIN REQUEST` / `END REQUEST`)
- Dynamic SQL statements are **not** validated at compile time
- The resulting SQL cannot have status variables, local variables, parameters, or USING/EXPLAIN modifiers
- Restrictions: Cannot specify ALTER PROCEDURE, CALL, CREATE PROCEDURE, DATABASE, EXPLAIN, HELP, OPEN, PREPARE, REPLACE PROCEDURE, SELECT, SET ROLE, SET SESSION, SHOW, or cursor statements

---

## 7. Queue Tables

Queue tables are base tables with FIFO properties for event-driven processing.

```sql
-- Create a queue table with timestamp column
CREATE TABLE event_queue, QUEUE (
  event_id   INTEGER,
  event_data VARCHAR(200),
  qits       TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6) NOT NULL
)
PRIMARY INDEX (event_id);

-- Push (FIFO insert)
INSERT INTO event_queue (event_id, event_data) VALUES (101, 'Order received');

-- Pop (consume oldest row — SELECT AND CONSUME)
SELECT AND CONSUME TOP 1 * FROM event_queue ORDER BY qits;

-- Peek (read without consuming)
SELECT * FROM event_queue ORDER BY qits;
```

- The QITS (Queue Inserted Timestamp) column provides FIFO ordering
- `SELECT AND CONSUME` returns data from the row with the oldest timestamp and deletes that row
- Use case: define a trigger on a base table to insert into the queue when an event fires; an application submits `SELECT AND CONSUME` that waits for data

---

## 8. Operator Precedence

Complete precedence table (highest to lowest):

| Precedence | Result Type | Operation |
|---|---|---|
| Highest | numeric | `+` (unary plus), `-` (unary minus) |
| | numeric | `**` (exponentiation) |
| | numeric | `*` (multiply), `/` (divide), `MOD` (modulo) |
| | numeric | `+` (add), `-` (subtract) |
| | string | `||` (concatenation) |
| | logical | `=`, `<>`, `>`, `<=`, `<`, `>=`, `IN`, `NOT IN`, `BETWEEN`, `LIKE` |
| | logical | `NOT` |
| | logical | `AND` |
| Lowest | logical | `OR` |

Operators of the same precedence are evaluated **left to right**. Parentheses override precedence (innermost first).

---

## 9. Object Naming Rules

### Name Length

- Standard: **1 to 30 characters** (in LATIN or KANJI1 internal representation)
- EON (extended object names) on newer releases: **up to 128 characters**

### Valid Characters (Unquoted Names)

- Uppercase/lowercase letters (A–Z, a–z)
- Digits (0–9)
- Special characters: `$`, `#`, `_` (dollar sign, number sign, underscore)
- Must NOT begin with a digit
- Must NOT be a reserved word
- Names are **NOT case-sensitive** (`Employee` = `EMPLOYEE` = `employee`)

### Quoted Identifiers

- Enclosed in double quotation marks: `"Current Salary"`, `"Today's Date"`
- Greatly increases the valid set of characters (spaces, special chars allowed)
- To include a quote mark in a name, double it: `"Monthly""A""Sales"`
- Quotation marks are NOT counted in the length and NOT stored in Dictionary

### Uniqueness Rules

- Databases, users, and profiles must have unique names across the system
- Tables, views, stored procedures, macros, indexes, triggers, UDFs within the same database must have unique names among each other
- Column names within a table/view must be unique
- Role names must be unique among users and databases
- Names are case-insensitive — cannot reuse a name by changing case

### Reserved Words

Use `SQLRestrictedWords` function to check if a word is restricted. New reserved words are added with each release — names valid in prior releases may become invalid. Workarounds:
- Enclose in double quotation marks
- Rename the object
