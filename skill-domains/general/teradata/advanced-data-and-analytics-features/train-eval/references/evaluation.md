# Evaluation Reference

> **Used by:** Step 7c — Evaluate Model.
>
> **Inputs from State Manifest:** `scored_table`, `test_table`, `train_db`, `id_column`, `ts`, `response_column`, `characteristics.Task type`, `characteristics.Applicable evaluators`, `characteristics.output_prob in scoring`
>
> ⚠️ **These templates are verified hints, not contracts.** Parameter names and required fields vary across Vantage versions. Always call `teradata_get_tool_schema(tool_name="<EvaluatorFunction>")` and reconcile against the live schema `properties` before executing. Never pass a parameter not present in `properties`.

---

## Choose evaluators by `characteristics.Task type`

| Task type | Evaluators to run |
|---|---|
| `classification` | `TD_ClassificationEvaluator` (always) + `TD_ROC` (when `output_prob in scoring = yes` and binary only) |
| `regression` | `TD_RegressionEvaluator` |
| `clustering` | `TD_Silhouette` (uses original data + cluster assignments, not scored_table) |
| `anomaly` / `unsupervised` | None — no standard MCP evaluator available |

---

## Classification — `TD_ClassificationEvaluator`

> ⚠️ **Pre-flight — scored table must contain the actual label, with VARCHAR-cast columns.**
> Most scoring functions (XGBoostPredict, GLMPredict, DecisionForestPredict, etc.) output only
> `id + Prediction [+ Prob]` — the original response column is **not** carried through.
> Always create a joined evaluation table with both label columns CAST to VARCHAR so that
> string `labels` values match correctly (see Type constraint note below):
> ```
> Use MCP tool: execute_sql with query:
>   CREATE TABLE <train_db>.eval_<table>_<ts> AS (
>     SELECT s.<id_col>,
>            CAST(s.<prediction_col> AS VARCHAR(64)) AS prediction_str,
>            CAST(t.<response_column> AS VARCHAR(64)) AS label_str,
>            <prob_positive_expr> AS prob_positive   ← see "ROC probability column" below;
>                                                    ← omit entirely if no prob column needed
>     FROM <train_db>.<scored_table> s
>     INNER JOIN <train_db>.<test_table> t ON s.<id_col> = t.<id_col>
>     WHERE s.<prediction_col> IS NOT NULL
>   ) WITH DATA
> ```
> Use `observation_column="label_str"` and `prediction_column="prediction_str"` for both
> `ClassificationEvaluator` and `ROC`. Use `probability_column="prob_positive"` for `ROC`.

> ⚠️ **Type constraint + label matching — always CAST to VARCHAR and always use `labels`.**
> Two independent bugs apply here:
>
> 1. **`num_labels` MCP bug:** When `labels` is null (its default), the MCP tool's internal code
>    attempts string processing on `labels` before checking for None, crashing with
>    `expected string or bytes-like object, got 'NoneType'`. Always pass `labels` explicitly
>    to bypass this code path. Do not pass `num_labels` — it is both unsafe (triggers the crash
>    when `labels` is absent) and unnecessary (the official docs state it is ignored when `labels`
>    is provided).
>
> 2. **Integer column label mismatch:** The `labels` parameter only accepts strings. If
>    `observation_column` and `prediction_column` are INTEGER, string labels like `["0","1"]`
>    produce an empty match → `collection must be a non empty list of _SQLColumnExpression
>    instances. Got []`. Fix: CAST both columns to VARCHAR in the eval table creation SQL
>    (see pre-flight above) so string labels match correctly.
>
> **Always apply both fixes together: CAST to VARCHAR + explicit `labels`.**
>
> **Eval table creation — always CAST INTEGER label columns to VARCHAR, and include
> `prob_positive` when ROC is required (see "ROC probability column" section below):**
> ```
> Use MCP tool: execute_sql with query:
>   CREATE TABLE <train_db>.eval_<table>_<ts> AS (
>     SELECT s.<id_col>,
>            CAST(s.<prediction_col> AS VARCHAR(64)) AS prediction_str,
>            CAST(t.<response_column> AS VARCHAR(64)) AS label_str,
>            <prob_positive_expr> AS prob_positive   ← see "ROC probability column" below;
>                                                    ← omit entirely if ROC not needed
>     FROM <train_db>.<scored_table> s
>     INNER JOIN <train_db>.<test_table> t ON s.<id_col> = t.<id_col>
>     WHERE s.<prediction_col> IS NOT NULL
>   ) WITH DATA
> ```
> Then pass `observation_column="label_str"`, `prediction_column="prediction_str"`, and
> `labels=["0","1"]` (string values matching the CAST output).

```
Call TD_ClassificationEvaluator with:
  data               = <eval_table>               ← joined table with VARCHAR-cast label columns
  observation_column = "label_str"                ← column name from eval table (already VARCHAR)
  prediction_column  = "prediction_str"           ← column name from eval table (already VARCHAR)
  labels             = ["<class1>", "<class2>"]   ← string values matching the CAST output
  database_name      = <train_db>
  # num_labels       = <N>                        ← ignored when labels is provided; do not use
```

Returns: per-class Precision, Recall, F1, Support in primary output; micro/macro/weighted aggregates in secondary output. Overall accuracy = sum of diagonal / total from the confusion matrix.

---

## Classification — `TD_ROC` (binary only, requires `output_prob=True` in scoring)

> ⚠️ Binary classification only. For multiclass, run ROC per class using one-vs-rest SQL first (see `references/scoring.md`).

> ⚠️ **`positive_class` type-coercion trap:** The MCP layer coerces string `"1"` to integer `1`,
> which fails with `TDML_2008 Invalid type`. **Omit `positive_class` entirely** when the positive
> class label is `1` — the parameter defaults to `'1'` automatically. Only pass `positive_class`
> when the label is a non-integer string (e.g. `'fraud'`, `'Yes'`).

### ROC probability column — choose the correct expression for `<prob_positive_expr>`

The `probability_column` passed to `TD_ROC` **must** be P(positive_class). How to obtain it
depends on which scoring function was used and how `output_prob` / `output_responses` were set.
Inspect the scored table DDL first, then choose the matching path:

| Scoring function | Scored with | `<prob_positive_expr>` in eval table SQL |
|---|---|---|
| Any function | `output_responses=["<positive_class>"]` | `s.<prob_class_col>` ← inspect DDL for exact column name; it is P(positive_class) directly |
| XGBoostPredict | `output_prob=True`, no `output_responses` | `CASE WHEN CAST(s.<prediction_col> AS INTEGER) = <pos_int> THEN s.Prob ELSE 1.0 - s.Prob END` ← documented to output P(predicted_class) |
| TD_DecisionForestPredict | `output_prob=True`, no `output_responses` | Inspect DDL — DecisionForest outputs one probability column per class; use the column for the positive class directly |
| TD_GLMPREDICT (BINOMIAL) | `output_prob=True`, no `output_responses` | Inspect DDL — GLM outputs P(class=1) directly for binary; **do not** apply CASE WHEN |
| TD_SVMPredict | No `output_prob` support | Skip ROC entirely |

> **Recommended:** always set `output_responses=["<positive_class>"]` in the scoring call
> (Path A above). This gives an unambiguous named column regardless of function and eliminates
> the need to reason about P(predicted_class) vs P(positive_class) at evaluation time.

```
Call TD_ROC with:
  data               = <eval_table>               ← same joined table used for ClassificationEvaluator
  probability_column = "prob_positive"             ← P(positive_class) column from eval_table
  observation_column = "label_str"                ← VARCHAR-cast actual label column in eval_table
  # positive_class   = "<label>"                  ← omit when positive class = 1 (default '1')
                                                  ← only pass for non-integer string labels
  database_name      = <train_db>
```

Returns: TPR/FPR at each threshold, AUC, Gini coefficient.

> If `output_prob in scoring = no` for this function (e.g. SVM), skip ROC entirely and note in the evaluation report.

---

## Regression — `TD_RegressionEvaluator`

> ⚠️ **Always pass an explicit `metrics` list.** Omitting `metrics` requests all 14 metrics by
> default, which includes `AR2` and `FSTAT`. These two metrics require additional parameters
> (`independent_features_num` for AR2; both `independent_features_num` and `freedom_degrees`
> for FSTAT) that the live schema marks as optional but Vantage enforces as required when those
> metrics are computed. Passing an explicit list that excludes AR2 and FSTAT avoids this trap
> entirely without relying on the schema being correct.
>
> **If the user explicitly requests AR2 or FSTAT**, add to the call:
> ```
>   independent_features_num = <k>          ← number of features used in training
>   freedom_degrees          = [<k>, <n-k-1>]  ← numerator df=k, denominator df=n-k-1
> ```
> where `k` = number of input features and `n` = number of rows in the scored/test set.

```
Call TD_RegressionEvaluator with:
  input_table_name   = "<scored_table>"      ← unqualified table name
  input_database_name = "<train_db>"
  observation_column = "<response_column>"
  prediction_column  = "<prediction_col>"   ← inspect scored_table DDL to confirm name
  metrics            = ["MAE", "MSE", "RMSE", "MSLE", "RMSLE", "R2", "EV", "ME", "MAPE", "MPE"]
  output_table_name  = "eval_<table>_<ts>"
  output_database_name = "<train_db>"
```

Returns: MAE, MSE, RMSE, MSLE, RMSLE, R², EV, ME, MAPE, MPE.

---

## Clustering — `TD_Silhouette`

> Does not use `scored_table`. Uses the original training data + cluster assignment column.

```
Call TD_Silhouette with:
  data              = <source_table>          ← original data (not scored_table)
  id_column         = <id_col>
  cluster_id_column = "<cluster_col>"         ← cluster assignment column; check scored_table or
                                                 training output (if output_cluster_assignment=True)
  target_columns    = [<same columns used in training>]
  database_name     = <source_db>
```

`output_type` options:
- `SCORE` (default) — single overall average silhouette score
- `CLUSTER_SCORES` — per-cluster average scores
- `SAMPLE_SCORES` — per-row scores

---

## Evaluation report format

After running all applicable evaluators, report:

```
✓ Evaluation complete

  Model     : <function_name>  (<model_table>)
  Test set  : <train_db>.<test_table>  (N_test rows)
  Scored as : <train_db>.<scored_table>

  --- Classification results ---
  Accuracy          : 0.87
  F1 (weighted)     : 0.86
  Precision (macro) : 0.85
  Recall (macro)    : 0.84
  AUC               : 0.91   ← ROC (binary only)

  --- OR Regression results ---
  RMSE : 4.21
  MAE  : 3.18
  R²   : 0.79

  --- OR Clustering results ---
  Silhouette (avg) : 0.63
```

Always suggest the next logical step:
- Classification/Regression: "Run `references/feature-importance.md` to inspect which features drove these results"
- Clustering: "Review per-cluster feature distributions with `TD_UnivariateStatistics`"
