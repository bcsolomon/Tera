---
name: train-eval
description: "Use when: user wants to train, evaluate, or interpret a Teradata in-database analytics model directly via MCP tool calls — no Python code or scripts generated. Covers any intent around clustering, classification, regression, anomaly/novelty detection, model quality assessment, feature importance, or explaining predictions. Covers: MODEL TRAINING (KMeans, DecisionForest, XGBoost, GLM, GLMPerSegment, SVM, KNN, NaiveBayes, OneClassSVM), MODEL EVALUATION (ClassificationEvaluator, RegressionEvaluator, ROC, Silhouette, TrainTestSplit), MODEL INTERPRETATION (Shap), SIMILARITY/UTILITIES (VectorDistance)."
argument-hint: "Describe what to do and which table/database (e.g. 'use KMeans to cluster retail_db.customers')"
metadata:
    author: teradata
    version: "1.0"
---

# Function Trainer — Teradata MCP Direct Execution

> ### Golden Rule
> **Always infer the user's analytical objective before considering Teradata analytical functions. Analytical functions are an implementation detail of the inferred objective, not the objective itself.**

**Design principle:** Everything runs via MCP tool calls against the live Vantage system. No Python scripts, no client-side code. The connection is assumed to be open. The agent reads live table metadata, loads function documentation from the MCP server, builds a parameter card, executes the function, saves the model, and reports a summary.

---

## Constraints (enforced throughout)

- **MCP tools only.** Never generate or suggest Python scripts or terminal commands.
- **Assumed open connection.** Do not attempt to establish, configure, or verify a Teradata connection.
- **No raw row dumps.** Never return full result sets to the user — always summarise.
- **Model persistence.** Any function that produces a model or output table MUST use `output_table_name`.
- **User constraints win.** If the user explicitly named a column, function, or parameter value, that value is used as-is. Never silently override it.
- **No verbose narration.** The agent's response to the user is limited to exactly three categories — nothing else may be shown:
  1. **Phase label** — one brief italicised line when entering a new phase, using the fixed format *`[Phase] action description…`*

     | Phase | Covers | Fires |
     |---|---|---|
     | `[Preparing]`   | Steps 3–4b: docs + DDL + row count  | Always |
     | `[Splitting]`   | Step 4c: train/test split            | Supervised only |
     | `[Training]`    | Step 6: MCP function call            | Always |
     | `[Scoring]`     | Step 7b: scoring test set            | Supervised with test set only |
     | `[Evaluating]`  | Step 7c: evaluation metrics          | Supervised with test set only |
     | `[Cleaning up]` | Step 9: dropping split table         | When split was performed |

     One line per phase only. Never repeat a phase label within the same session.

  2. **User-input prompts** — parameter cards and A/B/choice questions that require a user reply before execution can continue.
  3. **Results** — the Step 7 execution summary, Step 7c evaluation report, and Step 9 session summary.

  **Explicitly forbidden** (never show, regardless of context):
  - State Manifest declarations or variable assignments (e.g., "`source_db = customer360`")
  - Tool call narration (e.g., "Now calling…", "I will use…", "Good — documentation captured")
  - Schema analysis commentary (e.g., "Schema confirms `formula` is the correct parameter")
  - Intermediate query results or row counts outside of a result summary
  - Reasoning chains, decision explanations, or "why I chose X" statements
  - Any text between a phase label and the next user-input prompt or result

---

## State Manifest

These variables are built up through the pipeline. Each step that sets a variable **must record it explicitly here**. Downstream steps read from this manifest — never re-derive values from the user’s original request.

| Variable | Set in | Used in | Default when unset |
|---|---|---|---|
| `function_name` | Step 2 | Steps 3, 5, 6, 7 | — |
| `matched_family` | Step 2a | Step 2b | — |
| `characteristics` | Step 3 | Steps 4c, 5, 5b, 7 | — |
| `source_db` | Step 4a | Steps 4b, 4c, 5, 6 | — |
| `source_table` | Step 4a | Steps 4b, 4c, 5 | — |
| `id_column` | Step 4b | Steps 5, 6, 7b | `???` — placeholder if PI is absent or composite |
| `train_table` | Step 4c | Steps 5, 6 | `source_table` — if Step 4c skipped |
| `train_db` | Step 4c | Steps 5, 6 | `source_db` — if Step 4c skipped |
| `test_table` | Step 4c | Steps 7b, 7c, 9 | `null` — not set if Step 4c skipped |
| `model_table` | Step 6 | Steps 7, 7b, 7c, 7d, 9 | — |
| `scored_table` | Step 7b | Steps 7c, 9 | `null` — not set if Step 7b skipped |
| `eval_table` | Step 7c | Step 9 | `null` — not set if Step 7c skipped |
| `request_scope` | Step 1b | All steps | — |
| `auto_run` | Step 1b | Steps 2b, 4c, 5 | `false` |
| `t_start` | Step 1 | Step 9 | — |
| `ts` | Step 4c (supervised) or Step 6 (unsupervised) | Steps 4c, 6, 7b, 9 | — |

---

## Step 1 — Parse User Intent

> **Goal:** Lock the user's stated inputs (function name, database, table, explicit parameters). These values are fixed for all subsequent steps — never re-derive them.

> **At the start of this step:** Record the current wall-clock time as `t_start` in the State Manifest. This is used to compute total session running time in the Step 9 summary.

### 1a — Re-invocation check

Before parsing as a fresh request, check whether a prior run of this skill already completed in this conversation — signals: a parameter card was confirmed in a prior turn for the same function and table, and the user's new message requests a change to one or more specific parameters (e.g. *"train again with 50 iterations"*, *"retry with seed=123"*, *"use 7 clusters instead"*).

**If re-invocation is detected:**
- Analyze the new user request and existing State Manifest variables: apply only the explicitly changed parameter(s) from the new request to avoid recomputing all.
- Always fetch a fresh `ts` from Vantage — never reuse the prior run's timestamp.
- Skip Steps 2, 3, 4a, and 4b — function and table are unchanged.
- Go directly to Step 5, showing the pre-filled card with changed parameters marked `← updated`.

**Otherwise:** proceed with fresh extraction below.

---

Extract from the user's request:

| Field | How to extract |
|---|---|
| **Function name** | Explicit if stated (e.g. "KMeans", "XGBoost"). Otherwise derive from intent keywords in Step 2. |
| **Database** | Any database name mentioned (e.g. `retail_db`, `customer360`). |
| **Table** | Any table name mentioned. May be `db.table` or just `table`. |
| **Explicit parameters** | Any column names, cluster counts, or values the user stated directly. Mark these `← from your request`. |

> These extracted values map directly to State Manifest variables: **Database** → `source_db`, **Table** → `source_table`. Step 4a confirms or resolves them if either was not mentioned by the user.

If no argument was provided at all, ask:

> "What would you like to do, and which table or database should I use?"

### 1b — Detect request scope

**Hyperparameter search guard — check first, before scope classification:**
If the user's request contains **multiple values for the same parameter** (e.g. `iter_max = 50, 100, 150`; `num_clusters = 3, 5, 7`; `seed = 42, 123`), this is a **hyperparameter search / multi-run comparison** request — it is **out of scope** for this skill. Stop immediately and inform the user:

> *"Training with multiple `<param>` values and comparing results is a hyperparameter search workflow — outside train-eval's scope. Run each configuration individually using this skill, or use a dedicated hyperparameter tuning skill."*

Do not attempt to classify scope or proceed further.

---

After extracting the inputs above, classify what the user is asking for. Record as `request_scope` in State Manifest — every subsequent step checks this before running.

| Scope | Signals | Pipeline extent |
|---|---|---|
| **`advice`** | “which function”, “best for”, “not ready to train”, “just want to know”, “recommend”, “suggest” — no table or database mentioned | Step 2 only, then stop |
| **`train`** | Named table/database + training intent, no evaluation or scoring requested | Steps 2–7 |
| **`full_pipeline`** | Named table + evaluation intent, or no explicit scope constraint | Steps 2–7c |
| **`evaluate`** | “evaluate my model”, named model table, no training intent | Steps 7b–7c only |
| **`score`** | “score this table”, “predict on”, named model + new data table | Step 7b only |

**Separately, detect auto-run intent** — record as `auto_run` in the State Manifest (orthogonal to `request_scope`):

| Signals | `auto_run` value |
|---|---|
| "proceed without confirmations", "no confirmations", "auto-run", "proceed automatically" | `true` |
| *(none of the above)* | `false` |

If `auto_run = true` and no `request_scope` was explicitly stated, default `request_scope = full_pipeline`.

> **If `request_scope = advice`:** proceed to Steps 2a and 2b only, output the compact advisory format defined in Step 2b, and **stop**. Do not proceed to Step 3. Suppress all step headers, State Manifest declarations, and the function-choice prompt from the response.

---

## Step 2 — Select the Function

If the user explicitly named a function (only exact function names such as "GLM", "XGBoost", "TD_GLM" qualify — technique keywords like "regression", "classification", "clustering" do NOT) and `request_scope ≠ advice`, go directly to Step 3.

### 2a — Map intent to function family

> **Goal:** Determine which of the three families applies. Record the result as `matched_family` — Step 2b reads only that family's section of the catalog.

This skill covers three families only. If the user's intent falls outside these, inform them it is out of scope.

| Intent keywords | Function family |
|---|---|
| segment, cluster, group, partition | MODEL TRAINING |
| classify, predict category, label, binary outcome, churn, fraud | MODEL TRAINING |
| predict a number, regression, estimate numeric outcome | MODEL TRAINING |
| novelty detection, unseen patterns, one-class, anomaly ML | MODEL TRAINING |
| nearest neighbor, feature similarity, closest match | MODEL TRAINING |
| evaluate classifier, accuracy, AUC, F1, confusion matrix | MODEL EVALUATION |
| evaluate regression, RMSE, MAE, R² | MODEL EVALUATION |
| evaluate clustering, cluster quality, silhouette | MODEL EVALUATION |
| train/test split | MODEL EVALUATION |
| feature importance, explain model, SHAP, shapley | MODEL INTERPRETATION |

> **Carry forward:** Set `matched_family = <MODEL TRAINING | MODEL EVALUATION | MODEL INTERPRETATION>`. Step 2b uses this to filter the catalog — do not re-read the user's request there.

Common ambiguities — resolve before continuing (ask one focused question, max two exchanges):
- "predict" / "forecast" → classification or regression?
- "detect anomalies" → confirm ML-based novelty detection (`TD_OneClassSVM`) is what they want, not a data prep filter
- Multiple classifiers fit → ask about data size, interpretability needs, or whether a label column exists

> **Out of scope for this skill:** batch scoring of production/deployment data (Step 7b scores only the held-out test set created by Step 4c), feature engineering, data preparation, data exploration, text analytics, association analysis, hypothesis testing. For those, use the relevant preparation tools separately before invoking this skill.

### 2b — Select candidates from the catalog

> **Goal:** Using `matched_family` from Step 2a, load the catalog and read only the section for `matched_family`. Select the top 1–2 functions that best fit the intent within that family.

> **Load the catalog:** Read [`references/catalog.md`](references/catalog.md) and filter to the `matched_family` section only.

**If `request_scope = advice`** — output this compact format and stop:

```
For <use case>, the best options are:

1. TD_<X> — <brief reason>
2. TD_<Y> — <brief reason>

⚠️ <Critical pre-condition if any, e.g. severe class imbalance → consider TD_SMOTE first>

Ready to train? Come back with your table and database.
```

**All other scopes** — present with confidence score and choice prompt:

> ⚠️ **Mandatory gate — with one exception:** The function choice card MUST be shown before proceeding to Step 3 whenever the user did not supply an exact function name. Do not skip this step even when only one candidate exists or confidence is very high.
> **Exception — auto-run:** If `auto_run = true` AND top confidence ≥ 60%, auto-select the top candidate, emit a single phase-label line noting the selection, and proceed to Step 3 without waiting. If confidence < 60%, ALWAYS stop and ask regardless of `auto_run`.

```
1. TD_KMeans — Confidence: 92%
   Unsupervised clustering — groups rows by nearest centroid, no labels required.

2. TD_DecisionForest — Confidence: 45%
   Only applicable if you have a labelled target column.

Which function should I use? (1 / 2 / type a name)
```

If top confidence < 60%, ask the user to clarify before continuing.

---

## Step 3 — Load Function Documentation

> **Goal:** Extract the function’s full parameter contract and build its characteristic profile. Record the complete profile in `characteristics` (State Manifest) — do not skip this step even if the function seems familiar.

Search the full documentation from the Teradata MCP server for the selected function using a tool like `search_tool("TD_KMeans")` (use the short name without prefix).

From the result, locate the exact match for `TD_<FunctionName>` and read the full DESCRIPTION and PARAMETERS sections. For every parameter extract:

- **Required** or **Optional** (from "Required Argument." / "Optional Argument.")
- **Type** (from "Types:" line)
- **Default Value** (from "Default Value:" line — if present)
- **Permitted Values** (from "Permitted Values:" line — if present, these are the only valid values)
- **Notes / mutual exclusions** (from "Note:" block — e.g. `num_clusters` vs `centroids_data`)

> **Two-source rule — read both the docstring AND the JSON schema:**
> - **PARAMETERS docstring** → use for semantics: required/optional status, types, defaults, permitted values, mutual exclusions.
> - **JSON schema `properties`** → use as the **authoritative list of accepted parameter names**. Only pass parameters whose key appears in `properties`. Parameters described in the PARAMETERS text but absent from `properties` are not wired into the MCP tool's Pydantic model — passing them causes `Unexpected keyword argument` validation errors (e.g. XGBoost documents `input_columns` and `response_column` in its docstring but its schema only has `formula`).
> - Never pass a parameter whose name does not appear in the schema's `properties`, even if the docstring describes it.
>
> Always select the exact-match tool and ignore semantically similar results
> (e.g. do not confuse `TD_KMeans` with `TD_KMeansPredict` or `TD_KNN`).

> **Build the characteristic profile:** Read [`references/characteristics-guide.md`](references/characteristics-guide.md). Extract every field from both the Characteristic Profile table and the Data Handling Profile table. Record the complete result in `characteristics` (State Manifest). Steps 4c, 5, 5b, and 7 consume these values.

---

## Step 4 — Inspect the Table

> **Goal:** Retrieve live table structure (DDL) and row count. These two artefacts feed both the prerequisite checks in Step 4b and the parameter inference in Step 5.

### 4a — Resolve database and table (pre-flight)

Before calling any MCP tool, verify what was captured in Step 1. Apply the first matching case:

| Case | Condition | Action |
|---|---|---|
| **A** | database=known AND table=known | Proceed directly to Step 4b |
| **B** | database=known, table=unknown | `base_tableList(database_name="<database>")` → ask: "Which table contains your data?" |
| **C** | database=unknown, table=known | Ask: "Which database contains the table **`<table>`**?" |
| **D** | database=unknown AND table=unknown | Ask: "Which database and table should I use?" |

Once both are confirmed, record in the State Manifest: `source_db = <database>`, `source_table = <table>`.

> **Do not proceed past Step 4a until both `database` and `table` are resolved.** Never call `base_tableDDL` with a missing or placeholder `database_name`.

### 4b — Retrieve table structure

Once both are known:

```
Use MCP tool: base_tableDDL(table_name="<source_table>", database_name="<source_db>")
```

This returns column names, data types, and constraints (including PRIMARY INDEX).
Classify the PRIMARY INDEX result as follows — record `id_column` in the State Manifest:

| PI result | `id_column` value | Card annotation |
|---|---|---|
| Single-column PI | Use that column name | `← PRIMARY INDEX` |
| Composite PI (2+ columns) | `???` | `← PI is composite — no single column guarantees row uniqueness; use TD_FillRowID first` |
| No PI (NoPI / NOPI) | `???` | `← No PI found; use TD_FillRowID to generate a unique row ID column` |

Get an approximate row count:

```
Use MCP tool: base_readQuery(query="SELECT COUNT(*) AS n FROM <source_db>.<source_table>")
```

### Column classification from DDL types

| Type family | Role |
|---|---|
| INTEGER, BIGINT, SMALLINT, BYTEINT, FLOAT, REAL, DECIMAL, NUMERIC | Numeric → candidate `target_columns` / `input_columns` |
| VARCHAR, CHAR, CLOB | Categorical → candidate response column or exclude from numeric input |
| DATE, TIME, TIMESTAMP | Temporal → exclude from numeric feature input |
| Column name matches `*id`, `*key`, `*_sk`, `*_no` (case-insensitive) | Surrogate key → candidate `id_column`, exclude from feature columns |

---

## Step 4c — Train/Test Split Gate (supervised functions only)

> **Trigger:** Only runs when `characteristics.Task type = classification` or `regression`. Skip entirely for `clustering`, `unsupervised`, `anomaly`, and `distance`.

> **Load the split procedure:** Read [`references/split.md`](references/split.md) and follow it fully.

On completion, the following State Manifest variables are set:
- `train_table` / `train_db` — training data location; `train_db = source_db` (split always writes to the source database)
- `test_table` — held-out test data (used in Steps 7b, 7c, 9), or `null` if user chose Skip

---

## Step 5 — Build and Present the Parameter Card

> **Goal:** Pre-fill every parameter that can be inferred from prior steps. Present a complete, reviewable card and get explicit user confirmation before any execution.

> **If Step 4c ran:** `train_db` and `train_table` are already set in the State Manifest — use them directly. The EVALUATION PIPELINE block must reference `test_table` as the `newdata` for the scoring call.

Using the documentation from Step 3 and the table metadata from Step 4, build the parameter card. Pre-fill everything that can be inferred. Only ask the user for what cannot be determined.

### Inference rules

> **Schema guard:** Before placing any parameter in the card, confirm its name exists in the tool's JSON schema `properties` (verified in Step 3). Parameter names vary across functions:
> - Database parameter: some tools have `input_database_name` + `output_database_name`; others have a single `database_name` for both. Use whichever key appears in `properties`.
> - Feature/target parameters: some tools accept `input_columns` + `response_column`; others only accept `formula`. Never assume — check the schema.
> - Passing a parameter name not present in `properties` causes an `Unexpected keyword argument` Pydantic error regardless of what the docstring says.

| Parameter | Inference rule |
|---|---|
| `data` | Always: `"<train_db>.<train_table>"` — verify `data` is in schema |
| `input_database_name` / `database_name` | Check schema `properties`: use whichever key is present. Value = `train_db` |
| `id_column` | Read from State Manifest (set in Step 4b). Single-column PI → use that column. Composite PI or no PI → already `???` with note; show as-is and do not attempt to resolve. |
| `target_columns` / `input_columns` / `formula` | Check schema: use the key that is present. If schema has `formula`, express as `"<response> ~ <f1> + <f2> + …"`. If schema has `input_columns`, use a list. If > 20 candidates, list concisely and ask the user to trim. |
| `response_column` | Only include if `response_column` is in schema `properties`. If schema only has `formula`, embed the response in the formula instead. If not stated by user: VARCHAR/CHAR with lowest cardinality for classification; numeric column name suggesting a target for regression. Show as `???` if unresolvable. |
| `num_clusters` (KMeans) | If not stated: `min(10, round(sqrt(N / 2)))` where N = row count. |
| `initialcentroids_method` (KMeans) | Default to `'KMEANS++'` (better than `'RANDOM'`). |
| `num_init` (KMeans) | Default to `3` (reduces sensitivity to initialisation). |
| `seed` | Default to `42` for reproducibility. |
| `family` (GLM) | `BINOMIAL` if response column is categorical or has ≤ 2 distinct values; `GAUSSIAN` if numeric. |
| `output_table_name` | Always set — see Step 6 for naming convention. |
| `output_database_name` / `database_name` | Check schema: use the key present. Value = `train_db` (State Manifest). |
| All other optional params | Apply this priority: **(1)** user-stated value → **(2)** `Default Value:` line from the PARAMETERS docstring → **(3)** **omit the parameter entirely**. Never pass `null` and never infer `0` for a numeric param just because the MCP schema returns `default=null` — `null` in the schema means "not specified by MCP", not zero. Passing an explicit `0` overrides the TD engine's internal default (e.g. `lambda1`: engine default `0.02`, but passing `0` disables regularization entirely). Show as commented-out in the card only when a docstring default exists. |

### Parameter card format

Present this to the user before executing.

The card has **six sections** — always include all that apply:

1. **REQUIRED / OPTIONAL / MODEL OUTPUT** — standard parameter fields (always present)
2. **OUTPUTS** — what the model table physically contains; always shown for MODEL TRAINING functions; derived from the DESCRIPTION / OUTPUTS section read in Step 3
3. **FEATURE IMPORTANCE** — shown only when `Native importance in output` ≠ `none` OR `SHAP-compatible` ≠ `none`; omit with a `← N/A` note otherwise
4. **EVALUATION PIPELINE** — shown when `Applicable evaluators` ≠ none; include the scoring call and all applicable evaluator calls; pre-fill `output_prob=True` hint when `output_prob in scoring = yes` and task is classification

```
┌─────────────────────────────────────────────────────────────┐
│  FUNCTION: TD_<FunctionName>                                │
│  TABLE:    <train_db>.<train_table>  (N rows)               │
└─────────────────────────────────────────────────────────────┘

REQUIRED — fill in any ???:
  data                 = "<train_db>.<train_table>"  ← inferred
  id_column            = <col>                      ← PRIMARY INDEX
  target_columns       = [col1, col2, col3, …]      ← N numeric non-key columns
  num_clusters         = <value>                    ← inferred from row count  (or ???)

OPTIONAL — defaults shown, override if needed:
  initialcentroids_method = KMEANS++                (RANDOM | KMEANS++)
  iter_max                = 10
  num_init                = 3
  threshold               = 0.0395
  seed                    = 42
  output_cluster_assignment = False

MODEL OUTPUT:
  output_table_name    = <funcname>_<tablename>_YYYYMMDD_HHMMSS  ← auto-generated
  output_database_name = "<train_db>"

# Excluded from target_columns — add back above if needed:
# <col>   ← surrogate key (*id / *key / *_sk)
# <col>   ← temporal type (DATE / TIMESTAMP)
# <col>   ← categorical type (VARCHAR / CHAR)

OUTPUTS — what the model table contains:
  output_table_name  stores cluster centroids and WCSS per cluster
  ← query directly: SELECT * FROM <output_table_name> to inspect centroids
  ← WCSS is returned inline in the execution result

FEATURE IMPORTANCE:
  ← KMeans is unsupervised — no coefficients, split gains, or SHAP support

EVALUATION PIPELINE:
  1. (Optional) Score new data:
       TD_KMeansPredict(object=<output_table_name>, newdata=<new_table>,
                          id_column=<id_col>, ...)
     OR set output_cluster_assignment = True above to get assignments inline

  2. Evaluate cluster quality:
       TD_Silhouette(
         data              = <original_table>,
         id_column         = <id_col>,
         cluster_id_column = <cluster_assignment_column>,
         target_columns    = [<same columns used in training>]
       )
```

> **For supervised functions (GLM, DecisionForest, XGBoost, SVM, KNN, NaiveBayes, OneClassSVM):**
>
> - **OUTPUTS and FEATURE IMPORTANCE sections:** Read [`references/feature-importance.md`](references/feature-importance.md). Choose the pattern based on `characteristics.Native importance in output` (Pattern A = coefficients, Pattern B = split-importance, Pattern C = none).
>
> - **EVALUATION PIPELINE (classification):** Step 1 = scoring function with `output_prob=True` (when applicable); Step 2 = `TD_ClassificationEvaluator` + `TD_ROC` (binary only; requires probability column from Step 1)
> - **EVALUATION PIPELINE (regression):** Step 1 = scoring function; Step 2 = `TD_RegressionEvaluator`
> - **EVALUATION PIPELINE (anomaly / OneClassSVM):** Step 1 = `TD_OneClassSVMPredict`; Step 2 = none (no standard MCP evaluator)

Wait for the user to confirm or correct before proceeding.

> If any REQUIRED field still shows `???` after the user replies, ask for it explicitly
> before executing. Never execute with a `???` placeholder.
> **Auto-run exception:** If `auto_run = true` AND no field shows `???`, treat the card as confirmed and proceed without waiting. If any REQUIRED field is `???`, ALWAYS stop and ask — executing with a placeholder is never safe regardless of `auto_run`.

Once the card is confirmed, ask:

```
Parameter card confirmed.

Before executing, would you like a data quality check on the confirmed columns?
I will scan for NULLs, scale imbalances, and type issues — and recommend any
transformation steps if needed. This may take a moment depending on table size.

  A) Yes — run the check first
  B) No  — execute TD_<FunctionName> now
```

- **A** → proceed to Step 5b.
- **B** → skip to Step 6.
- **`auto_run = true`:** auto-select **B** and skip to Step 6.

---

## Step 5b — Data Preparation Recommendations (optional)

> Runs this step only when the user selects **A** after the parameter card.

> **Goal:** Scan the confirmed columns against the function's documented requirements and **recommend** (not execute) any data/feature transformation operations needed before training. This step calls `TD_UnivariateStatistics` to observe column statistics and produces a list of recommended prep tools — it does **not** run `ScaleFit`, `ScaleTransform`, `OrdinalEncodingFit`, or any other transformation itself. Those must be applied separately before re-invoking this skill.

### Algorithm-family baseline

Use this as the starting calibration, overridden by whatever the live documentation says:

| Algorithm family | Functions | Scaling | NULL handling | Encoding |
|---|---|---|---|---|
| Tree-based | XGBoost, DecisionForest | Not required — scale-invariant | Check docs — in-DB version may differ | Required for categorical features |
| Linear / Distance-based | GLM, SVM, KNN, KMeans | **Essential** — sensitive to feature magnitude | Required | Required for categorical features |
| Probabilistic | NaiveBayes | Not required | Required | VARCHAR features accepted natively |
| Anomaly | OneClassSVM | Recommended | Required | Required |

> **The live documentation overrides this baseline.** If the DESCRIPTION says the function handles NULLs natively or has a built-in `miss_value`-type parameter, record that and lower the severity accordingly.

### 5b-1 — Gather column statistics

Call `TD_UnivariateStatistics` on the **confirmed** feature columns from the parameter card:

```
Call TD_UnivariateStatistics with:
  data                = "<train_db>.<train_table>"
  target_columns      = [<confirmed feature columns from parameter card>]
  input_database_name = "<train_db>"
```

Record per column:

| Statistic | Used for |
|---|---|
| `min` / `max` | Scale check — compare ranges across columns |
| `null_count` | NULL check — any > 0 triggers review |
| `stddev` | Futile column check — stddev = 0 means zero variance |

> Fallback if unavailable: `base_readQuery` — `SELECT MIN(<col>), MAX(<col>), COUNT(*) - COUNT(<col>) AS nulls FROM <db>.<table>` per column.

For the response column (classification): `base_readQuery`: `SELECT COUNT(DISTINCT <response_col>) FROM <db>.<table>`

### 5b-2 — Run targeted checks

Run only the checks that apply to this function's characteristics (from `characteristics` in State Manifest):

| Check | Applies when | Evidence source | Decision rule |
|---|---|---|---|
| Feature columns are numeric | Feature type = `numeric only` | DDL column types | Flag any VARCHAR, CHAR, DATE, TIMESTAMP |
| `id_column` exists | `id_column` required = Yes | DDL PRIMARY INDEX | If absent → recommend `TD_FillRowID` |
| NULLs present in feature columns | NULL behaviour = `excluded` or `impute-required` | `null_count` from UnivariateStatistics | Any column with null_count > 0 |
| Features on incompatible scales | Distance-based = Yes | `min`/`max` from UnivariateStatistics | Flag if max range ratio across columns > 10× |
| Response column type correct | Supervised = Yes | DDL column types | Must match doc constraint |
| Response cardinality reasonable | Task = `classification` | `COUNT(DISTINCT)` | Warn if > 20 distinct values |

### 5b-3 — Output

**If no issues found** → report *"All checks passed — data looks ready."* then proceed to Step 6.

**If issues found** → show only the failing items, grounded in doc finding + observed value:

```
⚠️  <N> recommendation(s) before running TD_<FunctionName> on <train_db>.<train_table>:

  REQUIRED — <Issue title>
    Doc says: <what the function documentation states>
    Table has: <observed value, e.g. income: 20,015–199,989 vs age: 18–75 (ratio: ~3,157×)>
    Fix: <specific MCP tool(s)>

  RECOMMENDED — <Issue title>
    Doc says: <finding from documentation>
    Table has: <observation>
    Fix: <tool(s)>

Proceed anyway?  Yes — execute with current data  /  No — apply fixes first
```

- **Yes** → proceed to Step 6; annotate unresolved issues as `# ⚠️` comments in the output.
- **No** → stop. List only the specific tools the user needs to run before re-invoking this skill.

---

## Step 6 — Execute via MCP Tool Call

> **Goal:** Issue a single MCP tool call with the confirmed parameters and persist the model to a timestamped output table.

### Model output naming convention

**Step 1 — Fetch the timestamp from Vantage** (skip if `ts` already set in State Manifest from Step 4c):
```
Use MCP tool: base_readQuery with query:
  SELECT CAST(CURRENT_TIMESTAMP(0) AS VARCHAR(20)) AS ts
```
Reformat the result (e.g. `2026-07-16 16:04:22`) by removing hyphens, replacing the space
with `_`, and removing colons: → `20260716_160422`. Record as `ts` in the State Manifest.

> ⚠️ Never derive the timestamp from context or use a guessed value. Always query it from
> Vantage to ensure uniqueness and avoid collisions with tables from earlier sessions.

**Step 2 — Set output table name:**
```
output_table_name    = <function_shortname>_<table_shortname>_<ts>
output_database_name = <train_db>
```

Examples (with a Vantage-sourced `ts = 20260716_160422`):
- `kmeans_customers_20260716_160422`
- `xgboost_transactions_20260716_160422`
- `decisionforest_retail_20260716_160422`

### Invoke the MCP tool

Call the Teradata MCP tool for the selected function by its short name `TD_<FunctionName>`.
Pass all confirmed parameter values. Do not pass `null` for optional parameters unless
the user explicitly cleared them — omit them instead (defaults will apply).

Example for KMeans:
```
Call TD_KMeans with:
  data                     = "customers"
  id_column                = "customer_id"
  target_columns           = ["age", "annual_income", "spending_score"]
  num_clusters             = 5
  initialcentroids_method  = "KMEANS++"
  num_init                 = 3
  seed                     = 42
  output_cluster_assignment = True
  output_table_name        = "kmeans_customers_20260708_143022"
  output_database_name     = "retail_db"
  input_database_name      = "retail_db"
```

---

## Step 7 — Report Results

> **Goal:** Deliver a function-appropriate summary — never raw rows. Always close with the logical next step (evaluate → predict → explain).

After execution, report a concise summary — **never dump raw rows**.

### What to report per function

| Function | Report |
|---|---|
| **KMeans** | Iterations to convergence, WCSS, cluster sizes (row count per cluster via `base_readQuery`) |
| **DecisionForest / XGBoost** | Training deviance/accuracy; top 5 features by split-gain importance with inline bar chart (see format below) — follow Pattern B in [`references/feature-importance.md`](references/feature-importance.md); suggest `TD_SHAP` if `characteristics.SHAP-compatible = TD_DECISIONFOREST` / `TD_XGBOOST` |
| **GLM** | Model convergence status; top 5 predictors by `ABS(coefficient)` — follow Pattern A in [`references/feature-importance.md`](references/feature-importance.md); suggest `TD_SHAP` with `training_function="TD_GLM"` |
| **SVM** | Model convergence status, support vector count from model table; note that SHAP is not available for SVM |
| **OneClassSVM** | Number of inliers vs outliers |
| **SMOTE** | Original minority count, synthetic rows generated, new class distribution |
| **ScaleFit / ImputeFit / EncodingFit** | Parameters computed, columns processed, nulls found |
| **TrainTestSplit** | Train set size, test set size, split ratio |
| **ClassificationEvaluator / ROC** | Accuracy, precision, recall, F1, AUC |
| **RegressionEvaluator** | RMSE, MAE, R-squared |
| **Silhouette** | Average silhouette score, score per cluster |
| **Statistics (UnivariateStatistics, Histogram, etc.)** | Summary table — show inline, it is already compact |

### Summary report format

**Feature importance bar chart (DecisionForest / XGBoost / GLM):**
Scale bars proportionally to the top value. Use Unicode block characters:
`█` = 1 unit, `▌` = 0.5 unit, `▏` = 0.25 unit. Cap at 20 blocks for the top feature;
scale all others relative to it. Show `(not selected as root split)` when gain = 0.

```
  Top features by root-split gain:
    1. pclass  — 16.77  ████████████████████
    2. age     —  1.08  █
    3. fare    —  0.64  ▌
    4. sibsp   —  0.18  ▏
    5. parch   —  0.00  (not selected as root split)
```

**Full summary format — KMeans example:**
```
✓ Execution complete

  Function  : TD_KMeans
  Table     : retail_db.customers  (4,521 rows)
  Converged : 7 iterations
  WCSS      : 142.8

  Cluster sizes:
    Cluster 1 — 1,203 rows
    Cluster 2 —   987 rows
    Cluster 3 —   876 rows
    Cluster 4 — 1,104 rows
    Cluster 5 —   351 rows

  Model saved as: retail_db.kmeans_customers_20260708_143022

  Next steps:
    • Run TD_Silhouette on the model to evaluate cluster quality
    • Run TD_KMeansPredict to score new data against this model
```

**Full summary format — XGBoost / DecisionForest example:**
```
✓ Execution complete

  Function  : TD_XGBoost
  Table     : <train_db>.<train_table>  (N rows used — M excluded due to NULL <col>)  # ⚠️ if applicable
  Iterations: <n>  (converged)
  Final deviance: <val>  (started: <val> — <pct>% improvement)

  Top features by root-split gain:
    1. <col>  — <gain>  ████████████████████
    2. <col>  — <gain>  ██
    3. <col>  — <gain>  █
    4. <col>  — <gain>  ▌
    5. <col>  — <gain>  (not selected as root split)

  Model saved as: <train_db>.<model_table>

  Next: scoring held-out test set → evaluation (ClassificationEvaluator + ROC)
```

Always suggest a logical next step (e.g. evaluate → predict → explain).

> **For supervised functions where `test_table` ≠ `null`:** proceed directly to Step 7b to score the held-out test set. Do not stop after Step 7.

---

## Step 7b — Score Test Data (supervised functions only)

> **Trigger:** Only runs when `test_table` ≠ `null` AND `characteristics.Task type = classification` or `regression`.
> Skip for `clustering`, `anomaly`, `unsupervised`, or when `test_table = null`.

> **Load the scoring procedure:** Read [`references/scoring.md`](references/scoring.md) and follow the section for `function_name`.
>
> ⚠️ **Schema-first rule:** The call templates in `scoring.md` are verified hints, not contracts. Before executing, call `teradata_get_tool_schema(tool_name="<ScoringFunction>")` and reconcile parameter names against the live schema `properties`. Never pass a parameter not present in `properties` — the templates may be outdated for the current Vantage version.

On completion, update State Manifest:
- `scored_table` — output table containing predictions (and probability columns if `output_prob=True`)

---

## Step 7c — Evaluate Model (supervised functions only)

> **Trigger:** Only runs when `scored_table` is set (Step 7b completed).
> For clustering: runs when `model_table` is set and `characteristics.Task type = clustering` (uses original data, not scored_table).

> **Load the evaluation procedure:** Read [`references/evaluation.md`](references/evaluation.md) and follow the section for `characteristics.Task type`.
>
> ⚠️ **Schema-first rule:** The call templates in `evaluation.md` are verified hints, not contracts. Before executing each evaluator, call `teradata_get_tool_schema(tool_name="<EvaluatorFunction>")` and reconcile parameter names against the live schema `properties`. Never pass a parameter not present in `properties` — the templates may be outdated for the current Vantage version.

After delivering the evaluation report, if `test_table` is set (a train/test split was performed in Step 4c), prompt the user:

> When you're done reviewing the results, reply **done** and I'll clean up the intermediate split table.

**When the user replies "done":** execute Step 9.

---

## Step 8 — Error Handling

> **Goal:** Report failures verbatim with a specific likely cause. Never retry silently or guess at a fix without telling the user.

| Situation | Action |
|---|---|
| Function not found in MCP server | Inform the user. Verify the function name spelling against the catalogue in Step 2. |
| Required parameter still missing after user reply | Ask for it specifically — do not attempt execution. |
| Table or column not found | Use `base_tableDDL` to re-verify. Show the actual column list to the user. |
| Execution error from MCP | Report the error message verbatim. Suggest likely cause (wrong type, NULL in target columns, missing id_column). Do not retry silently. |
| Output table already exists | Adjust the timestamp suffix by one second and retry once. If it still fails, ask the user to choose a different model name. |

---

## Step 9 — End-of-Workflow Cleanup

> **Goal:** Report all tables created during this session with their purpose. Run when the user signals the workflow is complete. No DROP operations are issued — cleanup of any unwanted tables is the user's responsibility.

> **Applies to all workflows.** Include only rows for tables that were actually created — derive from State Manifest: omit split/train/test rows if `test_table = null`, omit scored row if `scored_table = null`, omit eval row if `eval_table = null`.

### Tables created this session

| Table | Purpose | Still needed? |
|---|---|---|
| `split_<table>_<ts>` | Intermediate split output — rows tagged by set | No — train and test sets already extracted |
| `train_<table>_<ts>` | Training data | Yes — needed to reproduce training |
| `test_<table>_<ts>` | Held-out test data | Yes — needed for future scoring and evaluation |
| `<func>_<table>_<ts>` | Trained model | Yes — needed to score new data |
| `scored_<table>_<ts>` | Predictions with probabilities | Yes — needed for evaluation and audit |
| `eval_<table>_<ts>` | Evaluation join table | Yes — useful for re-querying metrics |

### Session summary

After reporting the artifacts above, record `t_end` = current wall-clock time and report a full session summary. Collect all values from the State Manifest and the evaluation results:

```
**Session summary**

| Artifact | Location |
|---|---|
| Intermediate split (no longer needed) | `<train_db>.split_<table>_<ts>` ← remove when convenient |
| Train set (~N_train rows)  | `<train_db>.<train_table>` |
| Test set  (~N_test rows)   | `<train_db>.<test_table>` |
| <FunctionName> model       | `<train_db>.<model_table>` |
| Scored test set            | `<train_db>.<scored_table>` |
| Evaluation join table      | `<train_db>.<eval_table>` |
| **Accuracy / F1 / AUC**    | **<accuracy>%** · F1 <f1> · AUC <auc>  ← classification |
| **RMSE / R²**              | **<rmse>** · R² <r2>                   ← regression only |
| Execution time             | ~<elapsed> s  (Step 1 start → Step 9 complete) |
```

> Omit the `Intermediate split`, `Train set`, and `Test set` rows if `test_table = null`.
> Omit the `Scored test set` row if `scored_table = null`.
> Omit the `Evaluation join table` row if `eval_table = null`.
> Show only the metrics row that matches `characteristics.Task type` — omit the other.
> **Execution time:** `t_end` (current time at Step 9) − `t_start` (recorded at Step 1 start, from State Manifest). This covers the full session from first user intent to cleanup.
