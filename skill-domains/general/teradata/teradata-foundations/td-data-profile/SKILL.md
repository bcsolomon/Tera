---
name: td-data-profile
description: Data Profiling & Quality for Teradata tables. TRIGGER when user asks to profile, inspect, explore, summarize, sample, preview, or assess a Teradata table; user asks for sample rows / preview / top N rows; user asks about the Primary Index, indexes, DDL, table definition, constraints, column types, nulls, fill rate, missing values, statistics, distributions, value distribution / how values are distributed / what values or categories are present / frequency counts / value counts for a column, cardinality, duplicates, outliers, histograms, column summary, data quality, or table structure on a Teradata table. SKIP when user is querying data for business results (not inspecting the table itself).
argument-hint: <table_name> [database_name]
---

# Data Profiling & Quality

**Keep total response ≤ 1500 tokens. Be concise.**

**Prefer the purpose-built specified MCP tool(s) for each step — use it for that intent rather than substituting `base_readQuery` (raw SQL like `SELECT TOP n`). In particular, sample/preview requests should use `base_tablePreview`. Fallback: if the required tool fails repeatedly (2+ attempts), you may use `base_readQuery` as a last resort and note that you did so.**

**Explicit SQL requests override the tool preference.** When the user explicitly asks to "use SQL", "write a SQL query", "calculate using SQL", or otherwise requests the SQL method, use `base_readQuery` with an explicit query (see Step 8 / Appendix) — do NOT substitute a purpose-built profiling tool, even when one exists for that intent.

**Output hygiene.** Emit the final answer exactly once. Do NOT include chain-of-thought preambles ("I'll help you…", "Let me first…", "Perfect!", "Excellent!"), and do NOT repeat the answer block. A single, clean response improves professionalism scoring.

## Tool Access Mode (Progressive Disclosure)

This skill names specific MCP tools (`base_tableDDL`, `base_tablePreview`, `TD_ColumnSummary`, `TD_UnivariateStatistics`, `TD_CategoricalSummary`, `TD_Histogram`, `base_readQuery`, etc.). **First check which tools are exposed:**

- **If the named tools are directly available**, call them directly as written in each step.
- **If only the generic progressive-disclosure tools are exposed** (`teradata_list_patterns`, `teradata_search_tools`, `teradata_get_tool_schema`, `teradata_tool_call`), you must *discover then invoke* each named tool through them. Wherever a step says "Tool: `X`", resolve and run `X` with this sequence:
  1. `teradata_list_patterns` — list the available tool categories/patterns. (Call once and reuse; no need to repeat per step.)
  2. `teradata_search_tools` — find the target tool (e.g. `TD_ColumnSummary`) within the relevant category.
  3. `teradata_get_tool_schema` — fetch that tool's argument names and types before calling it.
  4. `teradata_tool_call` — execute the tool with the arguments from this skill (see Common Tool Parameters) validated against the schema.

**Efficiency:** Cache results from steps 1–3 across the whole request — call `teradata_list_patterns` at most once, and only re-run `teradata_search_tools` / `teradata_get_tool_schema` for a tool you have not yet resolved. When a step runs multiple named tools (or steps run in parallel), resolve each tool's schema first, then batch the `teradata_tool_call` invocations. The step-to-tool mapping, parameters, and fallback rules below are unchanged — only the *invocation mechanism* differs in this mode.

## Argument Parsing

Split `db.table` notation: `database_name` = part before dot, `table_name` = part after. Infer from natural language when not explicit.

Target: **$table_name**; database: **$database_name** (if provided)

## Common Tool Parameters

All MCP calls use these parameters — do not repeat them in each step:
- Table arg (`data` / `newdata` / `table_name` / `obj_name`) = `$table_name`
- DB arg (`input_database_name` / `db_name`) = `$database_name` (omit if not provided)
- Derive `target_columns` lists (all / numeric / categorical) from Step 1 `base_tableDDL` and pass them as a list in one call

## Mode Selection

Default to **Steps 1–3** for generic requests ("profile", "data quality", "check this table", "profile the table X"). **Do NOT auto-run the full pipeline (Steps 4/6/7) for a bare "profile" request** — stop after Steps 1–3 and offer to explore specific aspects (stats, categories, histograms). Run the full pipeline only when explicitly requested ("full profile", "all steps", "complete profile").

| User Intent | Steps |
|-------------|-------|
| Full profile / all steps | 1–4, 6–8 + Summary |
| Generic profile / data quality | 1–3 |
| Structure / column types | 1 |
| Primary Index / index / DDL / constraints | 1 |
| Sample / preview | 2 |
| Nulls / missing values / fill rate (per column) | 3 |
| Count of rows with at least one missing / null value | 5 |
| Column stats / min-max / percentiles | 4 |
| Cardinality / distinct count / "how many distinct" for a column | 6 |
| Categorical breakdown / value counts / % share of a category | 6 |
| Top-N values by frequency / count for a column | 6 |
| Histograms / distribution / skew | 4, 7 |
| Duplicates | Step 8 (duplicates) |
| Pattern / format validation | Step 8 (patterns) |
| Outliers | 4, 7 |
| Segmented / group-by comparison of stats between subgroups (e.g. churned vs retained, metric BY category) | 8 (base_readQuery) |
| Explicit "using SQL" / "write a SQL query" request | 8 (base_readQuery) |

**Parallelism:** When both steps are in-scope, run Steps 3 and 4 concurrently. When both steps are in-scope, run Steps 6 and 7 concurrently. Step 5 is never part of a parallel batch.

---

## Step 1 — Structure

Tool: `base_tableDDL` (preferred; fall back to `base_readQuery` only if it fails repeatedly)

This is the source for **Primary Index**, indexes, constraints, and column types — read them from the DDL. Do NOT query `DBC.IndicesV` / `DBC.ColumnsV` via `base_readQuery` for these; use `base_tableDDL`.

Report: column count, type breakdown (numeric/string/date), nullable columns, Primary Index (when asked).

If the table does not exist or returns no DDL, stop and report that the object was not found (check `$database_name`/`$table_name`). If Step 2 returns zero rows, report the table is empty and skip Steps 3–8.

---

## Step 2 — Sample

Tool: `base_tablePreview` (preferred for sampling rows; fall back to `base_readQuery` only if it fails repeatedly)

Report: anomalies, empty fields, formatting issues.

---

## Step 3 — Column Summary

Tool: `TD_ColumnSummary` — all columns (preferred; fall back to `base_readQuery` only if it fails repeatedly)

Report: null rate >20% (quality risk), constants (1 distinct value), overall fill rate.

---

## Step 4 — Univariate Statistics

Tool: `TD_UnivariateStatistics` — numeric columns, `stats`=`"ALL"` (preferred; fall back to `base_readQuery` only if it fails repeatedly)

By default, exclude ID/key/surrogate columns (e.g. PRIMARY INDEX, `*_id`) — stats on identifiers are usually meaningless. **Exception:** when the user asks for "all numeric columns" or names a specific numeric identifier column, include it (report its stats and note it is an identifier). Do not silently drop a column the user explicitly asked about.

Report: min/max ranges, suspicious values, high std dev (outlier risk), percentile spread.

---

## Step 5 — Inspect Rows with Nulls *(optional — investigative only)*

Tool: `TD_GetRowsWithMissingValues` — all columns (preferred; fall back to `base_readQuery` only if it fails repeatedly)

**Run when the user asks about rows with missing values** — either to see the actual incomplete records ("show me the rows with missing values", "which records are incomplete") OR to count them ("how many rows have at least one missing value / null"). This is the correct tool for row-level missing-value questions; Step 3 (`ColumnSummary`) only gives per-column null counts and cannot answer how many *rows* have any null (a row may be null in several columns, so per-column counts cannot be summed). Do NOT run this in a standard profile.

Report: count of rows with at least one missing value; when records are requested, a sample of returned rows and which columns are null in those rows.

---

## Step 6 — Categorical Summary

Tool: `TD_CategoricalSummary` — string/categorical columns (preferred; fall back to `base_readQuery` only if it fails repeatedly)

This is the tool for **distinct count / cardinality** ("how many distinct products"), **value counts / % share of a category** ("what % are senior citizens"), and **top-N values by frequency** ("top 5 countries by count") — use it instead of `COUNT(DISTINCT …)` or `GROUP BY … ORDER BY count` raw SQL, unless the user explicitly requested SQL (see the Explicit SQL rule).

Report: cardinality per column, value frequencies/percentages, dominant values >80%, high-cardinality columns (likely IDs). When no single value exceeds 80%, state explicitly that no category dominates.

---

## Step 7 — Histograms

Tool: `TD_Histogram` — numeric columns, `method_type`=`"STURGES"` (preferred; fall back to `base_readQuery` only if it fails repeatedly)

Exclude ID/key/surrogate columns — histograms on identifiers add no insight.

Report: distribution shape (uniform/skewed/bimodal), outlier bins, skewed columns.

---

## Step 8 — SQL Pattern Checks

Tool: `base_readQuery`

Use the fully qualified name `$database_name.$table_name` when `$database_name` is provided; otherwise use `$table_name` alone.

**Derive filter logic from the data, not assumptions.** Before counting a business condition (e.g. cancellations, returns, invalid rows), inspect Step 1 DDL + Step 2 sample to find the correct identifying column/pattern. Many datasets flag records by a code in an identifier (e.g. cancellations marked by `InvoiceNo LIKE 'C%'`), which is not the same as a negative-quantity heuristic. Confirm the row/record count against the actual table (`SELECT COUNT(*)`) rather than reusing a remembered figure.

**Duplicates** (replace `<col_list>` with all column names — Teradata does not support GROUP BY ALL):
```sql
SELECT COUNT(*) AS dup_groups, COALESCE(SUM(cnt - 1), 0) AS dup_rows
FROM (
  SELECT <col_list>, COUNT(*) AS cnt
  FROM $database_name.$table_name GROUP BY <col_list> HAVING cnt > 1
) t
```

**String patterns:** Use `REGEXP_SUBSTR` to count values not matching an expected format on string columns. Example (email):
```sql
SELECT COUNT(*) AS total,
       SUM(CASE WHEN REGEXP_SUBSTR(<col>, '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$') IS NULL
                THEN 1 ELSE 0 END) AS invalid_format
FROM $database_name.$table_name WHERE <col> IS NOT NULL
```
Adapt the pattern for phone/date/zip columns as needed.

---

## Final Summary

Summarize only the steps executed. State negative findings explicitly (e.g. "no extreme outliers detected", "no dominant value >80%", "0 rows with missing values") and never contradict yourself (do not open with "Yes, there are outliers" then conclude there are none). Include:
- Row/column counts, overall fill rate
- Flagged columns: null >20%, constants, high-cardinality, outlier risk, skew, dominant value >80%
- Duplicate count (if checked)
- Quality score (based on overall fill rate = non-null cells ÷ total cells across profiled columns): 🟢 >90% · 🟡 70–90% · 🔴 <70%
- 3–5 actionable recommendations

---

## Appendix — Fallback SQL (Teradata)

**Use ONLY when a step's preferred tool fails repeatedly (2+ attempts).** Replace `<col>` and `$database_name.$table_name`. Verified for Teradata 17.x.

**Step 1 — Structure**
```sql
SELECT ColumnName, ColumnType, ColumnLength, Nullable, DefaultValue
FROM DBC.ColumnsV
WHERE DatabaseName = '$database_name' AND TableName = '$table_name'
ORDER BY ColumnId;
-- or: SHOW TABLE $database_name.$table_name;
```

**Step 2 — Sample** (do not combine TOP and SAMPLE)
```sql
SELECT * FROM $database_name.$table_name SAMPLE 10;
-- or: SELECT TOP 10 * FROM $database_name.$table_name;
```

**Step 3 — Column Summary** (per column)
```sql
SELECT COUNT(*) AS total_rows, COUNT(<col>) AS non_null,
       COUNT(*) - COUNT(<col>) AS null_count,
       CAST(COUNT(<col>) AS DECIMAL(18,4)) / NULLIFZERO(COUNT(*)) AS fill_rate,
       COUNT(DISTINCT <col>) AS distinct_vals
FROM $database_name.$table_name;
```

**Step 4 — Univariate Statistics** (numeric; percentiles via QUANTILE — Teradata has no PERCENTILE_CONT)
```sql
SELECT MIN(<col>) AS min_v, MAX(<col>) AS max_v,
       AVG(<col>) AS mean_v, STDDEV_SAMP(<col>) AS std_v
FROM $database_name.$table_name;
-- percentile rank per row: SELECT <col>, QUANTILE(100, <col>) FROM $database_name.$table_name;
```

**Step 5 — Rows with Nulls**
```sql
SELECT TOP 20 * FROM $database_name.$table_name
WHERE <col_a> IS NULL OR <col_b> IS NULL OR <col_c> IS NULL;
```

**Step 6 — Categorical Summary** (per string column)
```sql
SELECT <col> AS category, COUNT(*) AS freq,
       CAST(COUNT(*) AS DECIMAL(18,4)) / SUM(COUNT(*)) OVER () AS pct
FROM $database_name.$table_name
GROUP BY <col> ORDER BY freq DESC;
```

**Step 7 — Histograms** (WIDTH_BUCKET on 16.20+/17.x; else manual bucketing)
```sql
SELECT WIDTH_BUCKET(<col>, (SELECT MIN(<col>) FROM $database_name.$table_name),
                            (SELECT MAX(<col>) FROM $database_name.$table_name), 10) AS bin,
       COUNT(*) AS freq
FROM $database_name.$table_name GROUP BY 1 ORDER BY 1;
-- older releases:
-- SELECT CAST((<col> - mn) / NULLIFZERO((mx - mn) / 10) AS INT) AS bin, COUNT(*) AS freq
-- FROM $database_name.$table_name
-- CROSS JOIN (SELECT MIN(<col>) AS mn, MAX(<col>) AS mx FROM $database_name.$table_name) b
-- GROUP BY 1 ORDER BY 1;
```
