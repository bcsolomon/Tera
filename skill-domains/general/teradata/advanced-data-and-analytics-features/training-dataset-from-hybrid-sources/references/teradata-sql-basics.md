# Teradata SQL Basics — Syntax Gotchas for Discovery `SELECT`s and the Materialization CTAS

> Backs the skill's standing rule — *"Every SQL statement this skill writes (Phases 4.5–10) must use
> correct, verified Teradata syntax — never assume it."* This is a **read-and-write-what-this-skill-emits**
> reference: the discovery/overlap/validation `SELECT`s (Phases 4.5, 6, 7, 8.5, 10) and the single
> `CREATE TABLE AS` (Phase 9). It is **not** a general Teradata SQL manual — only the dialect
> differences that actually bite the statements this skill generates are here.

## When to Use

- Writing a discovery, access-check, overlap, or structural-validation `SELECT` and unsure whether a
  clause is standard SQL or a Teradata-specific spelling (`QUALIFY`, `SAMPLE`, `TOP`, `MINUS`).
- Reconciling a join key and needing the exact `CAST`/`TRIM`/type-conversion behavior
  (cross-links to [join-key-reconciliation.md](./join-key-reconciliation.md)).
- A `SELECT` or the CTAS fails with a syntax error (`3706`/`3707`), a reserved-word error, or the
  `3771` illegal-expression error — see the error table at the end.

## Out of Scope (do not author these — they belong to other stages or are barred)

- **`REPLACE VIEW` / `CREATE VIEW` / macros / stored procedures** — this skill materializes a *table*,
  never a view or a routine. A view would also collide with the No-Destructive-SQL rule if it replaced
  an existing object.
- **DML — `INSERT` / `UPDATE` / `DELETE` / `MERGE`** — the skill's only write is `CREATE TABLE AS`.
- **Transaction control (`BT`/`ET`, `.LOGON`, explicit `COMMIT`)** — the MCP tools run each statement
  standalone; do not wrap emitted SQL in transaction blocks.
- **Data-prep / analytic function syntax** (`tdml_*`, window-heavy feature engineering beyond simple
  aggregation) — downstream data preparation owns it; see
  [materialization-and-validation.md](./materialization-and-validation.md).

---

## 1. Identifiers and Reserved Words

- **Quote a reserved-word identifier with double quotes**, not backticks or square brackets. If a
  discovered column or table is named after a keyword (`"date"`, `"type"`, `"value"`, `"time"`), wrap
  it: `SELECT t."date" FROM ...`. Single quotes are for **string literals only** — `WHERE state = 'CA'`.
- **Aliases that parse as keywords are rejected even after `AS`.** A short token such as `cm` can fail
  with `Error 3706/3707: … expected something … between … and the 'cm' keyword` even written `AS cm`,
  while `c`, `cust`, `ord`, `acc` work. The rule is behavioral, not a fixed blocklist: prefer a
  descriptive multi-character alias (`cust`, `ordr`, `acct`) and, if a syntax error points at an
  *alias* token, **rename the alias** before assuming the query shape is wrong. (Same gotcha called out
  in the CTAS section of [materialization-and-validation.md](./materialization-and-validation.md).)
- Identifiers are **case-insensitive**; string comparisons are case-insensitive by default under the
  common `NOT CASESPECIFIC` collation, so `WHERE name = 'smith'` may match `'Smith'`. When exact case
  matters for a join key, this is why a value that "looks equal" can still behave unexpectedly — see
  the join-key notes below.

## 2. Operators and Set Operators (dialect differences)

| Need | Teradata spelling | Note |
|---|---|---|
| Not-equal | `<>` **or** `!=` **or** `NE` | All three parse; prefer `<>` for portability. |
| Set difference | `MINUS` **or** `EXCEPT` | Both work and are synonyms; standard `EXCEPT` is fine. |
| Set intersection / union | `INTERSECT`, `UNION [ALL]` | Column count/types must line up across branches. |
| Concatenate strings | `a || b` | No `CONCAT` guarantee across versions — `||` is safest. |
| Integer/real division | `/` | `10/3` = `3` for integers; `CAST` a side to `DECIMAL` for a fraction. |

- **`NOT IN` with a NULL in the list returns no rows.** `x NOT IN (SELECT k FROM s)` yields **UNKNOWN**
  (never true) if any `k` is NULL, silently dropping every row. In overlap/anti-join probes prefer
  `NOT EXISTS` or add `WHERE k IS NOT NULL` to the subquery.

## 3. Row-Limiting: `TOP`, `SAMPLE`, `QUALIFY` — there is no `LIMIT`

Teradata has **no `LIMIT` clause** — using it is a frequent, avoidable error. Choose:

- **`SELECT TOP n ...`** — first *n* rows; combine with `ORDER BY` for deterministic "largest/latest".
  `TOP` cannot be combined with `QUALIFY` or `SAMPLE` in the same `SELECT`.
  ```sql
  SELECT TOP 20 DatabaseName, TableName FROM DBC.TablesV WHERE TableName LIKE '%cust%';
  ```
- **`SAMPLE n` / `SAMPLE 0.01`** — a random (non-deterministic) row count or fraction, handy for a
  quick peek at an unfamiliar source during Phase 7 discovery. Do **not** use `SAMPLE` for an overlap
  count that must be exact (Phase 8.5) — it under-reports matches.
  ```sql
  SELECT * FROM <nos_db>.nos_claims_feed SAMPLE 10;   -- peek only, not a count
  ```
- **`QUALIFY`** — filters on a window function's result without a wrapping subquery (a Teradata
  extension). The clean way to pick the latest row per entity when an event-grain source has one
  "current" record you want, before aggregating:
  ```sql
  SELECT cust_id, status, snapshot_dt
  FROM <edw_db>.Customer_Status
  QUALIFY ROW_NUMBER() OVER (PARTITION BY cust_id ORDER BY snapshot_dt DESC) = 1;
  ```

## 4. `CASE`, NULLs, and the `3771` Gotcha

- **Three-valued logic.** Any comparison to `NULL` is UNKNOWN, not false. Use `IS NULL` / `IS NOT NULL`,
  and `COALESCE(col, default)` to fold NULLs. In the Phase 10 key/label null check this is why the
  `SUM(CASE WHEN k IS NULL THEN 1 ELSE 0 END)` idiom is used rather than `= NULL`.
- **`CASE` for the derived label** (Phase 8) — the only place a label is synthesized, and only from a
  user-given deterministic rule:
  ```sql
  CASE WHEN status = 'CHURNED' THEN 1 ELSE 0 END AS derived_churn_label
  ```
- **Do not put `EXISTS`/a subquery inside `CASE WHEN`** — `SUM(CASE WHEN EXISTS (...) THEN 1 END)`
  raises **`Error 3771` (illegal expression in `WHEN`)**. For a one-scan overlap probe, `LEFT JOIN` a
  `SELECT DISTINCT <key>` derived table and test `... IS NOT NULL` instead (the `DISTINCT` prevents
  fan-out). Full pattern in the Phase 8.5 block of [SKILL.md](../SKILL.md) and
  [join-key-reconciliation.md](./join-key-reconciliation.md).

## 5. Aggregation Rules (Phases 8.5 and 9)

- **Every non-aggregated `SELECT` column must appear in `GROUP BY`.** Omitting one raises
  `Error 3504 (selected non-aggregate values must be part of the associated group)`. When aggregating an
  event-grain source to entity grain, group by exactly the entity key:
  ```sql
  SELECT cust_id, COUNT(*) AS tran_count, SUM(tran_amt) AS tran_amt_sum
  FROM <edw_db>.Transactions
  GROUP BY cust_id;
  ```
- **`COUNT(*)` counts rows; `COUNT(col)` skips NULLs; `COUNT(DISTINCT col)` de-dupes.** The grain check
  in Phase 10 relies on this distinction — `COUNT(*) > COUNT(DISTINCT cust_id)` signals duplicate keys.
- **`SUM`/`AVG` over an all-NULL group returns NULL, not 0.** After a `LEFT JOIN` these NULL aggregates
  are expected coverage gaps (an entity with no events) — report them, do not `COALESCE` them to 0 here;
  imputation is downstream data-prep.

## 6. Join-Key Type Reconciliation (the dialect rules behind the cast matrix)

The join-key cast matrix in [SKILL.md](../SKILL.md) and [join-key-reconciliation.md](./join-key-reconciliation.md)
compresses these Teradata conversion facts:

- **Implicit `INTEGER`↔`VARCHAR` comparison is unsafe.** Teradata may attempt an implicit numeric
  conversion that errors on a non-numeric character value (`Error 2621/2666`), or compare as characters
  and miss matches. Always **`CAST` the character side explicitly** to a numeric type:
  `ON CAST(a.cust_id AS BIGINT) = e.cust_id`.
- **`CHAR(n)` is space-padded; `VARCHAR` is not.** A `CHAR(10)` key `'123       '` never equals a
  `VARCHAR` `'123'`. **`TRIM` both sides**: `ON TRIM(a.cust_id) = TRIM(e.cust_id)`.
- **`DECIMAL` vs `INTEGER` id** — cast both to `BIGINT` to avoid scale surprises:
  `ON CAST(a.id AS BIGINT) = CAST(e.id AS BIGINT)`.
- **A cast on a join column can prevent single-partition access** but is correct over a silently-wrong
  match — correctness first; this raw-assembly skill does not tune the join.

## 7. String, Date, and Type Functions Used in Discovery

- **`TRIM(x)`**, **`SUBSTRING(x FROM 1 FOR n)`** (1-based, not 0-based), **`POSITION(sub IN x)`**,
  **`CHARACTER_LENGTH(x)`** — standard forms that work; `SUBSTR(x, 1, n)` also parses.
- **`UPPER`/`LOWER`** normalize case for a case-sensitive comparison when the collation is `CASESPECIFIC`.
- **Date/timestamp literals are typed**: `DATE '2024-01-01'`, `TIMESTAMP '2024-01-01 00:00:00'`. Bare
  `'2024-01-01'` in a comparison relies on implicit conversion — prefer the typed literal.
- **`CURRENT_DATE`, `CURRENT_TIMESTAMP`** (no parentheses) give the session date/time; **`ADD_MONTHS(d, n)`**
  and `INTERVAL '30' DAY` do date arithmetic. These appear only if a discovered source needs a date
  filter for a peek — the skill does not compute time-based features (that is downstream).
- **`CAST(x AS <type>)`** is the portable converter; `x (BIGINT)` postfix casting also works in Teradata
  but `CAST` is clearer in emitted SQL.

## 8. `LIKE` Patterns for `DBC` Metadata Scans

- `%` = any run of characters, `_` = one character. Concept scans use `TableName LIKE '%<concept>%'`.
- **Escape a literal underscore** in an object-name filter with `ESCAPE`: `LIKE 'TDH\_%' ESCAPE '\'` —
  otherwise `_` matches any single character. This matters for the `TDH_` cleanup filter and any scan
  of names that legitimately contain `_`.
- `DBC` views compared here are case-insensitive by default, so `LIKE '%CUST%'` and `'%cust%'` match the
  same names — no need to try both cases.

---

## Common SQL Syntax Errors (discovery `SELECT`s and the CTAS)

| Error | Symptom | Cause | Fix |
|---|---|---|---|
| `3706` / `3707` | "expected something like a name … between … and the '<tok>' keyword" | A reserved-word alias/identifier, a missing `AS ( … ) WITH DATA` paren in the CTAS, or `LIMIT` used | Rename the alias / quote the identifier; keep the CTAS `AS ( SELECT … ) WITH DATA` parens; replace `LIMIT` with `TOP`/`SAMPLE`/`QUALIFY` |
| `3771` | "illegal expression in the WHEN clause" | `EXISTS`/subquery inside `SUM(CASE WHEN EXISTS (...) …)` in a one-scan overlap probe | Use a standalone `COUNT(*) … WHERE EXISTS`, or `LEFT JOIN (SELECT DISTINCT <key> …)` and test `IS NOT NULL` — Phase 8.5 |
| `3504` | "selected non-aggregate values must be part of the associated group" | A `SELECT` column missing from `GROUP BY` when aggregating an event-grain source | Add every non-aggregated column to `GROUP BY` (usually just the entity key) |
| `2621` / `2666` | Bad-character / invalid-conversion during a comparison | Implicit `VARCHAR`→numeric conversion on a non-numeric join value | `CAST` the character side explicitly; verify the key is actually numeric before casting |
| Reserved-word | A keyword-named column/table rejected unquoted | `"date"`, `"type"`, `"value"` used without double quotes | Double-quote the identifier; single quotes are for string literals only |
| Empty anti-join | `NOT IN (subquery)` returns zero rows unexpectedly | A `NULL` in the `NOT IN` subquery makes the predicate UNKNOWN | Use `NOT EXISTS`, or add `WHERE <key> IS NOT NULL` to the subquery |

## See Also

- [join-key-reconciliation.md](./join-key-reconciliation.md) — full join-graph construction and the cast/trim rules summarized in §6.
- [materialization-and-validation.md](./materialization-and-validation.md) — the CTAS form, `SET`/`MULTISET`, `WITH DATA` options, and CTAS-specific errors.
- [database-and-table-discovery.md](./database-and-table-discovery.md) — the `DBC` metadata `SELECT`s that these `LIKE`/`TOP` rules apply to.
