# Train/Test Split Procedure

> **Trigger:** Only execute this procedure when `characteristics.Task type = classification` or `regression` (from State Manifest). Skip entirely for `clustering`, `unsupervised`, `anomaly`, and `distance` task types.
>
> **Inputs from State Manifest:** `source_db`, `source_table`, `id_column` (from DDL)
>
> **Outputs written to State Manifest:** `train_table`, `train_db`, `test_table`

---

## Step 4c-1 — Confirm output location

`TD_TrainTestSplit` writes its output to the database specified by `output_database_name`, which defaults to `input_database_name` when omitted — so passing `input_database_name = source_db` is sufficient to land output in `source_db`. No `SELECT DATABASE` call is needed.

> ⚠️ Do **not** use `SELECT DATABASE` to determine the output location. The current session default database may differ from `source_db`, causing table-not-found errors in the subsequent CREATE TABLE statements.

---

## Step 4c-2 — Ask the user

```
Before training, has your data already been split into train and test sets?

  A) Yes — I already have separate train and test tables
  B) No  — split it now using TD_TrainTestSplit
  C) Skip — train on the full table (not recommended for model evaluation)
```

**A** → ask: "What are the names of your train and test tables, and which database are they in?"
Validate both exist:
```
base_tableDDL(table_name="<train_table>", database_name="<db>")
base_tableDDL(table_name="<test_table>",  database_name="<db>")
```
Set in State Manifest: `train_table`, `test_table`, `train_db`. Proceed to Step 5.

**B** → proceed to Step 4c-3.
> **Auto-run shortcut:** If `auto_run = true` AND the user's request explicitly stated an intent to split (e.g. "split", "split data", "train/test split"), auto-select **B** and proceed to Step 4c-3 without asking. If no explicit split intent was stated, still ask — the choice cannot be safely inferred.

**C** → set `train_table = source_table`, `train_db = source_db`, `test_table = null`.
Note in the parameter card that no split was performed; EVALUATION PIPELINE block will show `← no test table available`. Proceed to Step 5.

---

## Step 4c-3 — Fetch timestamp

**Before presenting the card**, fetch the current timestamp from Vantage and record it as `ts`
in the State Manifest. This value is reused for all table names in Steps 4c, 6, 7b, and 9.

```
Use MCP tool: base_readQuery with query:
  SELECT CAST(CURRENT_TIMESTAMP(0) AS VARCHAR(20)) AS ts
```
Reformat the result (e.g. `2026-07-16 16:04:22`) → `20260716_160422`.

> ⚠️ Never derive the timestamp from context or use a guessed value. Querying it from Vantage
> ensures uniqueness and avoids collisions with tables from earlier sessions on the same day.

## Step 4c-4 — Present the Split Card

> ⚠️ **Guardrails:**
> - `input_table_name` must be the **unqualified table name only** — never `db.table`. The source database is passed separately via `input_database_name`.
> - `output_table_name` is unqualified. The output database is controlled by `output_database_name` (defaults to `input_database_name` when omitted).
> - `id_column` is **required** when `seed` is set — without it the split is non-deterministic across sessions.
> - `stratify_column` — classification only; omit for regression (continuous targets have no classes to balance).

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 4c: Train/Test Split — TD_TrainTestSplit              │
│  SOURCE:  <source_db>.<source_table>  (N rows)              │
│  OUTPUT → <source_db>                                       │
└─────────────────────────────────────────────────────────────┘

REQUIRED:
  input_table_name    = "<source_table>"    ← unqualified name only
  input_database_name = "<source_db>"      ← source database
  id_column           = "<id_col>"         ← PRIMARY INDEX — required for deterministic seed

OPTIONAL — defaults shown, override if needed:
  train_size       = 0.75                   ← 75% for training
  test_size        = 0.25                   ← 25% for testing  (train_size + test_size must = 1.0)
  seed             = 42                     ← reproducible split; requires id_column above
  # stratify_column = "<response_col>"      ← RECOMMENDED for classification: preserves class
                                               balance across train and test sets

SPLIT OUTPUT (intermediate — written to <source_db>):
  output_table_name = "split_<table>_<ts>"   ← single table; both sets tagged
                                               ← dropped in Step 9 (end-of-workflow cleanup)

EXTRACTED TABLES (created after split — also in <source_db>):
  train_table = "train_<table>_<ts>"   ← used for training  (TD_IsTrainRow = 1)  — kept
  test_table  = "test_<table>_<ts>"    ← used for scoring + evaluation  (TD_IsTrainRow = 0)  — kept
```

> Reply **ok** to execute, or change any value above.
> **Auto-run:** If `auto_run = true` and no field above shows `???`, treat this card as confirmed and proceed directly to Step 4c-5 without waiting.

---

## Step 4c-5 — Execute the split (after user confirms)

Run in sequence — **do not proceed to the next call if any step fails**.

**Step 1 — Run TrainTestSplit:**
```
Call TD_TrainTestSplit with:
  input_table_name    = "<source_table>"               ← unqualified
  input_database_name = "<source_db>"
  id_column           = "<id_col>"
  seed                = 42
  output_table_name   = "split_<table>_<ts>"           ← use `ts` from State Manifest
  output_database_name = "<source_db>"
  # stratify_column   = "<response_col>"               ← include if user confirmed above
```

**Step 2 — Extract train table:**
```
Use MCP tool: execute_sql with query:
  CREATE TABLE <source_db>.train_<table>_<ts> AS (
    SELECT * FROM <source_db>.split_<table>_<ts>
    WHERE TD_IsTrainRow = 1
  ) WITH DATA
```

**Step 3 — Extract test table:**
```
Use MCP tool: execute_sql with query:
  CREATE TABLE <source_db>.test_<table>_<ts> AS (
    SELECT * FROM <source_db>.split_<table>_<ts>
    WHERE TD_IsTrainRow = 0
  ) WITH DATA
```

**Step 4 — Verify row counts:**
```
Use MCP tool: base_readQuery with query:
  SELECT TD_IsTrainRow, COUNT(*) AS row_count
  FROM <source_db>.split_<table>_<ts>
  GROUP BY 1 ORDER BY 1
```

**Step 5 — Report and update State Manifest:**

Report to the user:
```
✓ Split complete

  Source  : <source_db>.<source_table>  (N total rows)
  Train   : <source_db>.train_<table>_<ts>  — N_train rows  (N_train/N %)
  Test    : <source_db>.test_<table>_<ts>   — N_test rows   (N_test/N %)
  Intermediate: split_<table>_<ts>  (kept until Step 9 cleanup)

  Training will use: <source_db>.train_<table>_<ts>
```

Update State Manifest:
- `train_table = train_<table>_<ts>`
- `test_table  = test_<table>_<ts>`
- `train_db    = source_db`
