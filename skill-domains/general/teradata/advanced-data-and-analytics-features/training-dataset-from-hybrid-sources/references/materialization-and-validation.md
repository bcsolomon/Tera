# Materialization and Validation — Complete Reference

> Covers Phases 9–10 of the `training-dataset-from-hybrid-sources` pipeline: generating the final
> `CREATE TABLE AS` statement, indexing and collecting statistics on it, running **basic
> structural** validation (not statistical profiling), and the full Data Prep and ML Tool
> Boundaries that govern where this skill's responsibility ends.

## Phase 9 — Materialization

### Naming Contract

Every object this skill materializes must be named predictably so it can be tracked and cleaned up — a randomly
named scratch table is invisible to lifecycle tooling. Unless the user requests a specific name, apply this contract:

| Object | Name pattern |
|---|---|
| Final training table | `TDH_TRAINSET_<runtag>__<slug>` |
| Intermediate staging table/view | `TDH_STG_<runtag>__<slug>` |

- **`TDH_`** — a reserved prefix that namespaces this skill's output away from every real source; cleanup filters on
  `TableName LIKE 'TDH\_%'`.
- **`<runtag>`** — a run-scoped token the caller provides. It makes the
  name unique per run so cleanup can target exactly one run's objects. When no tag is supplied, fall back to a
  compact UTC timestamp `YYYYMMDDTHHMMSS`. Use the tag verbatim — do not abbreviate or reformat it.
- **`<slug>`** — a short `[a-z0-9_]` description of the dataset (≤ 20 chars), e.g. `patient_readmission`, `churn`.
- Keep the full identifier ≤ 128 characters (Teradata limit).
- If the user gives an explicit table name, honor it — the contract is only the default. Report the final database
  and table name back in the handoff either way.

### CTAS Skeleton

Structure the final query as a set of CTEs — one per aggregated event-grain source, plus a final
`SELECT` from the anchor joined to every entity-grain and aggregated source — wrapped in
`CREATE TABLE ... AS (...) WITH DATA`:

```sql
CREATE TABLE <target_db>.<target_table> AS (
    WITH admissions_agg AS (
        SELECT patient_id,
               COUNT(*) AS admission_count,
               SUM(los_days) AS total_los
        FROM <edw_db>.Admissions
        GROUP BY patient_id
    ),
    labs_agg AS (
        SELECT a.patient_id,
               COUNT(*) AS lab_count,
               SUM(t.lab_value) AS lab_value_sum
        FROM <edw_db>.Labs t
        JOIN <edw_db>.Admissions a
          ON t.admission_id = a.admission_id
        GROUP BY a.patient_id
    ),
    portal_events_agg AS (
        SELECT patient_id,
               COUNT(*) AS session_count,
               SUM(portal_minutes) AS portal_minutes_sum
        FROM (<otf_iceberg_read_result>) AS w
        GROUP BY patient_id
    )
    SELECT c.patient_id,
           c.age, c.sex, c.years_in_care, c.nbr_dependents,
           c.marital_status, c.region_code,
           adm.admission_count, adm.total_los,
           lb.lab_count, lb.lab_value_sum,
           b.ext_risk_score, b.num_claims_6m, b.num_er_visits_24m, b.copay_ratio,
           pe.session_count, pe.portal_minutes_sum,
           b.readmit_flag AS label
    FROM <edw_db>.Patient c
    LEFT JOIN admissions_agg adm ON c.patient_id = adm.patient_id
    LEFT JOIN labs_agg lb ON c.patient_id = lb.patient_id
    LEFT JOIN <nos_db>.nos_claims_feed b ON CAST(c.patient_id AS BIGINT) = b.patient_id
    LEFT JOIN portal_events_agg pe ON c.patient_id = pe.patient_id
) WITH DATA
PRIMARY INDEX (patient_id);

COLLECT STATISTICS COLUMN (patient_id) ON <target_db>.<target_table>;
COLLECT STATISTICS COLUMN (label) ON <target_db>.<target_table>;
```

Run the CTAS and each `COLLECT STATISTICS` through `base_executeSQL` — `base_readQuery` is
SELECT-only and rejects a `CREATE TABLE AS`/`COLLECT STATISTICS` with
`TD_TOOL_EXECUTION_ERROR: Only SELECT queries are allowed`. Use `base_readQuery` only for the
read-only `SELECT` validation queries in Phase 10.

### CTAS Syntax Gotchas

Copy the skeleton's shape rather than improvising. Two deviations (both verified on Teradata 20.00):

- **Keep the `AS ( SELECT … ) WITH DATA` parentheses** — they are required. When a CTAS errors, do not
  strip the parens to "debug" it.
  ```sql
  -- Wrong: missing parentheses
  --   Error 3707: expected something like a name or a Unicode delimited identifier or '('
  --   between the 'AS' keyword and the 'SELECT' keyword
  CREATE TABLE TDH_TRAINSET_<runtag>__<slug> AS SELECT … WITH DATA;

  -- Right
  CREATE TABLE TDH_TRAINSET_<runtag>__<slug> AS ( SELECT … ) WITH DATA
  PRIMARY INDEX (<grain_key>);
  ```
- **Give every table a descriptive, multi-character `AS <alias>`.** Some short tokens are parsed as
  keywords and rejected as aliases — e.g. `cm` fails, while `claims`, `cust`, `ord` work. This is
  environment-specific, so if a syntax error points at an *alias* token, rename it before assuming the
  query shape is wrong.
  ```sql
  -- Wrong: 'cm' parsed as a keyword
  --   Error 3706: expected something between the 'SELECT' keyword and the 'cm' keyword
  FROM <edw_db>.ClaimsMaster AS cm

  -- Right
  FROM <edw_db>.ClaimsMaster AS claims
  ```

### `CREATE TABLE AS` — Form Options

The skill emits one DDL form — `CREATE TABLE <name> AS ( <select> ) WITH DATA` — so only these options
apply. Explicit column DDL, table options (`FALLBACK`/`JOURNAL`/`CHECKSUM`/compression), identity columns,
constraints, and volatile/temporary kinds are out of scope: a raw training table is built from a `SELECT`,
never defined column by column.

- **`WITH DATA` vs `WITH DATA AND STATISTICS` vs `WITH NO DATA`.** Use `WITH DATA` (the default) to
  populate from the `SELECT`. `WITH DATA AND STATISTICS` also copies inherited statistics and column/index
  structure, reducing follow-up `COLLECT STATISTICS` work. Never use `WITH NO DATA` here — it creates an
  empty shell, but the deliverable is a *materialized* table (see the "not an unexecuted script" rule in
  [SKILL.md](../SKILL.md) Phase 9).
  ```sql
  -- Default: populate from the SELECT
  CREATE TABLE TDH_TRAINSET_<runtag>__<slug> AS ( <select> ) WITH DATA;

  -- Also copies inherited source statistics/structure
  CREATE TABLE TDH_TRAINSET_<runtag>__<slug> AS ( <select> ) WITH DATA AND STATISTICS;

  -- Never here: empty shell, no rows
  CREATE TABLE TDH_TRAINSET_<runtag>__<slug> AS ( <select> ) WITH NO DATA;
  ```

- **`SET` vs `MULTISET`.** When omitted, the kind follows the session default (`SET` in Teradata mode,
  `MULTISET` in ANSI mode). A `SET` table CTAS **silently drops fully-duplicate rows** (verified: two
  identical rows in the `SELECT` landed as one — no error is raised), quietly shrinking the row count.
  Prefer `MULTISET` unless the grain check guarantees uniqueness:
  ```sql
  CREATE MULTISET TABLE TDH_TRAINSET_<runtag>__<slug> AS ( <select> ) WITH DATA
  PRIMARY INDEX (<grain_key>);
  ```
  This is separate from the Phase 10 duplicate-**key** check, which validates the primary-index grain.

- **`PRIMARY INDEX` is chosen, not defaulted.** If omitted, Teradata picks a default PI (often the first
  column), distributing on the wrong grain. Always state it explicitly — see Primary Index Choice below.
  ```sql
  -- Wrong: no PRIMARY INDEX -> Teradata defaults to the first column
  CREATE MULTISET TABLE TDH_TRAINSET_<runtag>__<slug> AS ( <select> ) WITH DATA;

  -- Right: distribute on the entity grain key
  CREATE MULTISET TABLE TDH_TRAINSET_<runtag>__<slug> AS ( <select> ) WITH DATA
  PRIMARY INDEX (patient_id);
  ```

### CTAS Creation Errors (materialization-specific)

| Error | Symptom | Cause | Fix |
|---|---|---|---|
| `3803` | "Table '<name>' already exists" | The `TDH_TRAINSET_…` target name is already present from a prior run | Do **not** `DROP`/overwrite (No-Destructive-SQL) — materialize under a fresh `TDH_TRAINSET_<runtag>__<slug>` name, or confirm the drop with the user first |
| `5660` | "Cannot create index on LOB columns" | A `CLOB`/`BLOB` column landed in the `PRIMARY INDEX` list | Keep only the scalar grain key in `PRIMARY INDEX` |
| `2646` | "No more room in database" | The target database has no perm space for the materialized table | Materialize in a database with space (verify the default database), or report the space gap — do not silently shrink the column list |
| (silent) | Phase 10 row count is lower than the `SELECT` returns | A `SET` table CTAS silently de-duplicated fully-identical rows (no error raised) | Use `MULTISET` (above); `Error 5312` only surfaces on `INSERT … SELECT` into an existing `SET` table, not on CTAS |

### Primary Index Choice

Set `PRIMARY INDEX` to the anchor's entity key (`patient_id`, `SubscriberID`, etc.) so the training
table is distributed on the same grain as the label and every join in Phase 9 — this keeps the
table well-distributed for downstream profiling and modeling and matches the grain validated in
[join-key-reconciliation.md](./join-key-reconciliation.md).

### Collecting Statistics

Collect statistics on the primary index column and the label column at minimum; add any column
used heavily in downstream filters (e.g. `region_code`) if the request calls for segment-level
analysis.

### Train/Test Split Is Deferred

A train/test split runs on the **cleaned, feature-engineered** table, not the raw one, so
`tdml_TrainTestSplit` is out of scope here — it belongs to downstream data preparation after
profiling and cleaning. If the user asks for a ready-to-split table, materialize the raw table,
state that splitting happens post-data-prep, and hand off. Label rebalancing (for example
`tdml_SMOTE`) is likewise **out of scope** — like every other tool in the Data Prep Tool Boundary
below, it operates on the cleaned dataset and is deferred to downstream data preparation, even when
explicitly requested.

### Ready-to-Run Build Template

The fully parameterized version of the CTAS above. Fill in the placeholders, then run each step
individually and check for errors between steps. Route each statement by type: run the `SELECT`
probes/validation (Steps 1, 2, 4) through `base_readQuery`, and the non-`SELECT` statements — the
`CREATE TABLE AS` in Step 3 and the `COLLECT STATISTICS` in Step 5 — through `base_executeSQL`
(`base_readQuery` rejects non-`SELECT` statements).

Required placeholders:

| Placeholder | Meaning |
|---|---|
| `<TARGET_DB>` / `<TARGET_TABLE>` | database + name for the materialized training table (default `TDH_TRAINSET_<runtag>__<slug>` per the Naming Contract above) |
| `<EDW_DB>` | database owning the EDW anchor / dimension / event tables |
| `<ANCHOR_TABLE>` / `<ANCHOR_KEY>` | entity-grain anchor table (one row per entity) and its join key / `PRIMARY INDEX` column |
| `<DIMENSION_TABLE>` / `<DIM_FK>` | entity-grain dimension table and its key that maps to `<ANCHOR_KEY>` |
| `<EVENT_TABLE>` / `<EVENT_FK>` | event-grain table (many rows per entity — MUST be aggregated) and its bridge/anchor key |
| `<BRIDGE_TABLE>` / `<BRIDGE_KEY>` | bridge table + column when the event table doesn't key directly to `<ANCHOR_KEY>` |
| `<NOS_DB>` / `<NOS_TABLE>` | database + NOS foreign-table enrichment source (Option A) |
| `<EXTERNAL_KEY>` / `<EXTERNAL_KEY_TYPE>` | the enrichment source's join key and the anchor-key `CAST` target that matches it (e.g. `BIGINT`) |
| `<LABEL_COLUMN>` | the ML label column, usually from the enrichment source |
| `<AUTH_OBJECT>`, `<DATALAKE>`, `<NAMESPACE>`, `<OTF_TABLE>` | OTF source coordinates (Option B) |

```sql
-- Step 1: (recommended) Verify SELECT access on the source databases before building
--   (see database-and-table-discovery.md Phase 4.5 — catalog visibility is not read access).
SELECT DatabaseName, TableName, AccessRight
FROM DBC.AllRightsV
WHERE UserName = USER AND AccessRight = 'R' AND DatabaseName IN ('<EDW_DB>', '<NOS_DB>');

-- Step 2: Confirm join-key value overlap BEFORE building (Phase 8.5).
--   Near-zero overlap means the wrong anchor was chosen — re-discover; never fabricate a key.
SELECT COUNT(*) AS matched_anchor_rows
FROM <EDW_DB>.<ANCHOR_TABLE> a
WHERE EXISTS (
    SELECT 1 FROM <NOS_DB>.<NOS_TABLE> e
    WHERE CAST(a.<ANCHOR_KEY> AS <EXTERNAL_KEY_TYPE>) = e.<EXTERNAL_KEY>
);

-- Step 3: Materialize the training table. Aggregate every event-grain source to the anchor
--   grain in a CTE, then LEFT JOIN entity-grain sources onto the anchor. Choose ONE enrichment
--   variant — Option A (NOS foreign table) or Option B (OTF datalake source).

--   Option A: enrichment from a NOS foreign table (referenced by name, like a native table)
CREATE MULTISET TABLE <TARGET_DB>.<TARGET_TABLE> AS (
    WITH dimension_agg AS (
        -- Entity-grain dimension rolled up to one row per anchor key.
        SELECT <DIM_FK> AS <ANCHOR_KEY>,
               COUNT(*) AS dimension_row_count
               -- , SUM(<DIM_NUMERIC_COL>) AS dimension_numeric_sum
        FROM <EDW_DB>.<DIMENSION_TABLE>
        GROUP BY <DIM_FK>
    ),
    event_agg AS (
        -- Event-grain source aggregated to the anchor grain; bridge through <BRIDGE_TABLE>
        -- when the event table does not key directly to <ANCHOR_KEY>.
        SELECT br.<ANCHOR_KEY>,
               COUNT(*) AS event_count,
               SUM(ev.<EVENT_NUMERIC_COL>) AS event_numeric_sum
        FROM <EDW_DB>.<EVENT_TABLE> ev
        JOIN <EDW_DB>.<BRIDGE_TABLE> br
          ON ev.<EVENT_FK> = br.<BRIDGE_KEY>
        GROUP BY br.<ANCHOR_KEY>
    )
    SELECT a.<ANCHOR_KEY>,
           -- a.<ANCHOR_FEATURE_1>, a.<ANCHOR_FEATURE_2>,
           d.dimension_row_count,
           e.event_count,
           e.event_numeric_sum,
           -- x.<EXTERNAL_FEATURE_1>, x.<EXTERNAL_FEATURE_2>,
           x.<LABEL_COLUMN> AS label
    FROM <EDW_DB>.<ANCHOR_TABLE> a
    LEFT JOIN dimension_agg d ON a.<ANCHOR_KEY> = d.<ANCHOR_KEY>
    LEFT JOIN event_agg e     ON a.<ANCHOR_KEY> = e.<ANCHOR_KEY>
    -- CAST the anchor key to the external key's type (NOS Parquet-inferred types often differ).
    LEFT JOIN <NOS_DB>.<NOS_TABLE> x
      ON CAST(a.<ANCHOR_KEY> AS <EXTERNAL_KEY_TYPE>) = x.<EXTERNAL_KEY>
) WITH DATA
PRIMARY INDEX (<ANCHOR_KEY>);

--   Option B: enrichment from an OTF (Iceberg/Delta) datalake source.
--   An OTF read has no persisted name — stage it as a CTE via TD_ICEBERG_READ / TD_DELTA_READ
--   (see hybrid-source-discovery.md), aggregate to the anchor grain, then join. Comment out
--   Option A above and use this form when the enrichment source is OTF rather than NOS.
-- CREATE MULTISET TABLE <TARGET_DB>.<TARGET_TABLE> AS (
--     WITH external_agg AS (
--         SELECT ir.<EXTERNAL_KEY>,
--                COUNT(*) AS ext_event_count,
--                SUM(ir.<EXTERNAL_NUMERIC_COL>) AS ext_amount_sum
--                -- , MAX(ir.<LABEL_COLUMN>) AS label     -- if the label lives on the OTF source
--         FROM TD_OTFDB.TD_ICEBERG_READ(
--                  AUTHORIZATION(<AUTH_OBJECT>)
--                  DATALAKE('<DATALAKE>')
--                  ICEBERG_NAMESPACE('<NAMESPACE>')
--                  ICEBERG_TABLE('<OTF_TABLE>')
--              ) AS ir
--         GROUP BY ir.<EXTERNAL_KEY>
--     )
--     SELECT a.<ANCHOR_KEY>,
--            xa.ext_event_count, xa.ext_amount_sum
--            -- , xa.label
--     FROM <EDW_DB>.<ANCHOR_TABLE> a
--     LEFT JOIN external_agg xa
--       ON CAST(a.<ANCHOR_KEY> AS <EXTERNAL_KEY_TYPE>) = xa.<EXTERNAL_KEY>
-- ) WITH DATA
-- PRIMARY INDEX (<ANCHOR_KEY>);

-- Step 4: Verify the table materialized at the intended grain (one row per anchor key).
SELECT COUNT(*) AS row_count FROM <TARGET_DB>.<TARGET_TABLE>;

SELECT <ANCHOR_KEY>, COUNT(*) AS n
FROM <TARGET_DB>.<TARGET_TABLE>
GROUP BY <ANCHOR_KEY>
HAVING COUNT(*) > 1;   -- zero rows returned = correct grain

-- Step 5: Collect statistics on the PRIMARY INDEX and the label.
COLLECT STATISTICS COLUMN (<ANCHOR_KEY>) ON <TARGET_DB>.<TARGET_TABLE>;
COLLECT STATISTICS COLUMN (label) ON <TARGET_DB>.<TARGET_TABLE>;

-- Step 6: Run the validation template below, then hand off to downstream data preparation.
```

Worked example (patient-readmission), showing the placeholders filled in:

```sql
CREATE MULTISET TABLE ml_sandbox_db.TDH_TRAINSET_20260721__patient_readmission AS (
    WITH admissions_agg AS (
        SELECT patient_id, COUNT(*) AS admission_count, SUM(los_days) AS total_los
        FROM CareCloud_db.Admissions
        GROUP BY patient_id
    ),
    labs_agg AS (
        SELECT a.patient_id, COUNT(*) AS lab_count, SUM(t.lab_value) AS lab_value_sum
        FROM CareCloud_db.Labs t
        JOIN CareCloud_db.Admissions a ON t.admission_id = a.admission_id
        GROUP BY a.patient_id
    )
    SELECT c.patient_id, c.age, c.sex, c.years_in_care, c.nbr_dependents,
           c.marital_status, c.region_code,
           adm.admission_count, adm.total_los,
           lb.lab_count, lb.lab_value_sum,
           b.ext_risk_score, b.num_claims_6m, b.num_er_visits_24m, b.copay_ratio,
           b.readmit_flag AS label
    FROM CareCloud_db.Patient c
    LEFT JOIN admissions_agg adm ON c.patient_id = adm.patient_id
    LEFT JOIN labs_agg lb ON c.patient_id = lb.patient_id
    LEFT JOIN CareCloud_db.nos_claims_feed b ON CAST(c.patient_id AS BIGINT) = b.patient_id
) WITH DATA
PRIMARY INDEX (patient_id);

COLLECT STATISTICS COLUMN (patient_id) ON ml_sandbox_db.TDH_TRAINSET_20260721__patient_readmission;
COLLECT STATISTICS COLUMN (label) ON ml_sandbox_db.TDH_TRAINSET_20260721__patient_readmission;
```

Cleanup is **manual and confirmation-only** — this skill never issues destructive SQL in its
automated flow (see the No-Destructive-SQL rule in [SKILL.md](../SKILL.md)). Run
`DROP TABLE <TARGET_DB>.<TARGET_TABLE>;` only on explicit user confirmation.

## Phase 10 — Basic Structural Validation

Validate that the table is **structurally** sound — correct grain, no accidental fan-out, keys and
label populated, types as expected. This is *not* statistical profiling (distributions, class
balance, missing-value patterns, correlations) — that is downstream data preparation's job. Use
only read-only `base_readQuery` SQL plus `base_tableDDL` / `base_columnDescription`; do **not** call
any `tdml_*` profiling tool here (see the Data-Preparation Tool Boundary below).

- **Row count** — confirm the table materialized with a sane row count (close to the anchor's row
  count for an entity-grain training table):

  ```sql
  SELECT COUNT(*) AS row_count FROM <target_db>.<target_table>;
  ```

- **Grain / duplicate-key check** — the single most important structural check: confirm one row per
  anchor key (no fan-out from an un-aggregated event-grain join):

  ```sql
  SELECT patient_id, COUNT(*) AS n
  FROM <target_db>.<target_table>
  GROUP BY patient_id
  HAVING COUNT(*) > 1;
  ```

  Zero rows returned confirms the intended one-row-per-anchor-key grain.

- **Key / label null check** — the PI key must never be null, and a supervised label should be
  populated for the modelable population:

  ```sql
  SELECT
      SUM(CASE WHEN patient_id IS NULL THEN 1 ELSE 0 END) AS null_keys,
      SUM(CASE WHEN label   IS NULL THEN 1 ELSE 0 END) AS null_labels
  FROM <target_db>.<target_table>;
  ```

  Nulls in enrichment features from `LEFT JOIN`s are **expected** coverage gaps (only patients
  with recorded portal activity have a non-null `session_count`) — report the null counts per
  source, but do not "fix" them here; imputation is deferred.

- **Datatype / schema check** — confirm the materialized column types match Phase 8's selection
  (aggregated `SUM`/`COUNT` columns landed as numeric, not accidentally character) by inspecting
  `base_tableDDL(<target_db>, <target_table>)` or
  `base_columnDescription(<target_db>, <target_table>)`.

### Ready-to-Run Validation Template

The fully parameterized structural-validation suite for the table built above. This is structural
validation **only** — not statistical profiling (distribution, class-balance, correlation, and
missing-value profiling are deferred to downstream data preparation). Run each `SELECT` step through
`base_readQuery`; Step 7's `HELP TABLE` is not a `SELECT`, so run it through `base_executeSQL`
instead (`base_readQuery` rejects it with `TD_TOOL_EXECUTION_ERROR: Only SELECT queries are allowed`).

Required placeholders: `<TARGET_DB>` / `<TARGET_TABLE>` (the materialized table), `<ANCHOR_KEY>`
(the `PRIMARY INDEX` / entity key), `<LABEL_COLUMN>` (skip the label steps for unsupervised sets),
`<NULLABLE_JOIN_COLUMN>` (a column populated only via a `LEFT JOIN` enrichment source), and
`<CATEGORICAL_COLUMN>` (a categorical column to cardinality-check post-join).

```sql
-- Step 1: Row count and basic shape.
SELECT COUNT(*) AS row_count
FROM <TARGET_DB>.<TARGET_TABLE>;

-- Step 2: Grain / duplicate-key check — zero rows returned confirms one row per anchor key.
--   Duplicates usually mean an event-grain source was joined without aggregating first (fan-out).
SELECT <ANCHOR_KEY>, COUNT(*) AS n
FROM <TARGET_DB>.<TARGET_TABLE>
GROUP BY <ANCHOR_KEY>
HAVING COUNT(*) > 1;

-- Step 3: Key / label null check — the PI key must never be null; a supervised label should be
--   populated for the modelable population. (Drop the label term for unsupervised datasets.)
SELECT
    SUM(CASE WHEN <ANCHOR_KEY>   IS NULL THEN 1 ELSE 0 END) AS null_keys,
    SUM(CASE WHEN <LABEL_COLUMN> IS NULL THEN 1 ELSE 0 END) AS null_labels
FROM <TARGET_DB>.<TARGET_TABLE>;

-- Step 4: Label shape (structural) — confirms the label has more than one distinct value.
--   This is a presence/shape check, NOT class-balance profiling (that is downstream data preparation).
SELECT <LABEL_COLUMN>, COUNT(*) AS n
FROM <TARGET_DB>.<TARGET_TABLE>
GROUP BY <LABEL_COLUMN>;

-- Step 5: LEFT JOIN coverage — a non-zero null count here is usually EXPECTED (not every anchor
--   row has a matching enrichment row). Report the coverage rate; do NOT impute it here.
SELECT
    SUM(CASE WHEN <NULLABLE_JOIN_COLUMN> IS NULL THEN 1 ELSE 0 END) AS null_count,
    SUM(CASE WHEN <NULLABLE_JOIN_COLUMN> IS NOT NULL THEN 1 ELSE 0 END) AS non_null_count,
    CAST(SUM(CASE WHEN <NULLABLE_JOIN_COLUMN> IS NOT NULL THEN 1 ELSE 0 END) AS DECIMAL(10,4))
        / NULLIF(COUNT(*), 0) AS coverage_rate
FROM <TARGET_DB>.<TARGET_TABLE>;

-- Step 6: Cardinality check — confirm a categorical column's distinct count stayed reasonable
--   after joins (a join bug can silently multiply distinct value counts).
SELECT COUNT(DISTINCT <CATEGORICAL_COLUMN>) AS distinct_value_count
FROM <TARGET_DB>.<TARGET_TABLE>;

-- Step 7: Schema / datatype check — confirm aggregated SUM/COUNT columns landed as numeric
--   (not accidentally character) by inspecting the materialized table's definition.
--   HELP is not a SELECT statement — run this one through base_executeSQL, not base_readQuery.
HELP TABLE <TARGET_DB>.<TARGET_TABLE>;
```

Once these structural checks pass, hand the raw table to downstream data preparation for profiling,
cleaning, and feature engineering.

### Quality Report Contract

Report back to the user: the target database/table name, final row count, full column list, the
label column and whether it is populated (a plain distinct-value count, not a statistical profile),
which structural checks passed, any nulls introduced by `LEFT JOIN`s and why they are expected, and
any columns dropped during Phase 8 triage with a one-line structural reason. Then name the next
step explicitly: **hand off to downstream data preparation** for profiling, cleaning, and feature
engineering.

## Data-Preparation Tool Boundary in Full

This skill's automated flow calls **only**: the seven `base_*` discovery/DDL/validation tools and
`base_executeSQL` (CTAS + `COLLECT STATISTICS` + `HELP`). Every profiling, cleaning, feature-engineering,
reshaping, and label-rebalancing (`tdml_SMOTE`) tool below is
**out of scope** — recognize the request, finish materialization + basic structural validation, and
hand off by naming the downstream data-preparation stage instead of invoking it. This boundary holds
even when the user explicitly insists. Model training, prediction, and scoring belong to a separate
downstream ML stage reached only after data-prep — this skill only assembles and validates the raw dataset.

### Data Prep Tool Boundary → downstream data preparation

| Activity | Tools deferred (never invoked here) |
|---|---|
| Column/statistical profiling | `tdml_ColumnSummary`, `tdml_CategoricalSummary`, `tdml_UnivariateStatistics`, `tdml_Histogram`, `tdml_GetFutileColumns` |
| Distribution / normality / statistical tests | `tdml_QQNorm`, `tdml_Histogram`, `tdml_ZTest`, `tdml_FTest`, `tdml_ANOVA` |
| Missing-value detection & imputation | `tdml_GetRowsWithMissingValues`/`tdml_GetRowsWithoutMissingValues`, `tdml_SimpleImputeFit`/`Transform` |
| Outlier handling | `tdml_OutlierFilterFit`/`Transform` |
| Scaling & encoding | `tdml_ScaleFit`/`Transform`, `tdml_RowNormalizeFit`/`Transform`, `tdml_OneHotEncodingFit`/`Transform`, `tdml_TargetEncodingFit`/`Transform`, `tdml_OrdinalEncodingFit`/`Transform`, `tdml_BincodeFit`/`Transform`, `tdml_PolynomialFeaturesFit`/`Transform`, `tdml_ColumnTransformer` |
| Reshaping | `tdml_Pivoting`, `tdml_Unpivoting`, `tdml_Pack`, `tdml_Antiselect`, `tdml_ConvertTo` |
| Time-series / sessionized features | `tdml_MovingAverage`, `tdml_Sessionize` |
| Train/test split | `tdml_TrainTestSplit` (runs on the cleaned/engineered table, *after* data-prep) |

The moment a request crosses into profiling, cleaning, feature engineering, or reshaping, stop and
hand off to downstream data preparation — see the Common Errors table in [SKILL.md](../SKILL.md).
Model training runs only after data-prep, in a separate ML stage.

## Worked End-to-End Example — Subscription Churn Validation

1. Materialize `SubscriberID` (PI), demographic/billing columns from `Subscriber_Churn`, streaming
   features from `nos_stream_usage`, and aggregated ticket features (count, unresolved count)
   from `stream_support_tickets`, with `Churn` as the label.
2. A `SELECT Churn, COUNT(*) AS n ... GROUP BY Churn` confirms the label is populated with more
   than one distinct value (structural check); deeper class-balance profiling is left to
   downstream data preparation.
3. A key/label null check confirms that only the subset of subscribers with recorded support tickets
   have non-null aggregated ticket features — expected, since `stream_support_tickets` is a
   LEFT JOIN enrichment source not present for every subscriber; the nulls are reported, not imputed.
4. Duplicate-detection query confirms zero duplicate `SubscriberID` rows in the final table.
5. Report the dataset back to the user with row count, label distinct-value counts, and the columns
   retained from each source tier (EDW, NOS, OTF), then hand off to downstream data preparation.
