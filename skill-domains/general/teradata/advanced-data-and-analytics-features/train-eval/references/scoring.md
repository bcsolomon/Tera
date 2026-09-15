# Scoring Reference

> **Used by:** Step 7b — Score Test Data.
>
> **Inputs from State Manifest:** `function_name`, `model_table`, `train_db`, `test_table`, `id_column`, `response_column`, `characteristics.output_prob in scoring`, `characteristics.Task type`
>
> **Output written to State Manifest:** `scored_table`
>
> ⚠️ **These templates are verified hints, not contracts.** Parameter names and required fields vary across Vantage versions. Always call `teradata_get_tool_schema(tool_name="<ScoringFunction>")` and reconcile against the live schema `properties` before executing. Never pass a parameter not present in `properties`.

---

## Naming convention

Always set:
```
output_table_name = scored_<test_table_shortname>_<YYYYMMDD_HHMMSS>
```
Output lands in `train_db`. Record as `scored_table` in State Manifest.

---

## Scoring call — per function

### `TD_GLM` → `TD_GLMPREDICT`

```
Call TD_GLMPREDICT with:
  input_table_name    = "<test_table>"         ← unqualified
  input_database_name = "<train_db>"
  model_table_name    = "<model_table>"        ← unqualified
  model_database_name = "<train_db>"
  id_column           = "<id_col>"
  # output_prob       = True                   ← BINOMIAL only (needed for ROC)
  # accumulate        = ["<response_col>"]     ← carry actuals for evaluation
  output_table_name   = "scored_<ts>"
  output_database_name = "<train_db>"
```

> `output_prob` is only valid when `family = BINOMIAL`. For GAUSSIAN, omit it.

---

### `TD_DecisionForest` → `TD_DecisionForestPredict`

```
Call TD_DecisionForestPredict with:
  input_table_name    = "<test_table>"
  input_database_name = "<train_db>"
  model_table_name    = "<model_table>"
  model_database_name = "<train_db>"
  id_column           = "<id_col>"
  # output_prob       = True                   ← include for classification (needed for ROC)
  # output_responses  = ["<class1>", …]       ← per-class probabilities for multiclass ROC
  # accumulate        = ["<response_col>"]
  output_table_name   = "scored_<ts>"
  output_database_name = "<train_db>"
```

> For multiclass ROC: set `output_responses` to list all class labels; each gets its own probability column. Then loop ROC per class using one-vs-rest SQL (via `base_readQuery`) before calling `TD_ROC`.

---

### `TD_XGBoost` → `TD_XGBoostPredict`

```
Call TD_XGBoostPredict with:
  input_table_name    = "<test_table>"
  input_database_name = "<train_db>"
  model_table_name    = "<model_table>"
  model_database_name = "<train_db>"
  model_order_by      = "<model_key_col>"      ← REQUIRED; use base_tableDDL on the model table and pick the PRIMARY INDEX column
  id_column           = "<id_col>"
  # model_type        = "Classification"       ← or "Regression"
  # output_prob       = True                   ← include for classification (needed for ROC)
  # output_responses  = ["<class1>", …]       ← for multiclass ROC
  # accumulate        = ["<response_col>"]
  output_table_name   = "scored_<ts>"
  output_database_name = "<train_db>"
```

---

### `TD_SVM` → `TD_SVMPredict`

```
Call TD_SVMPredict with:
  input_table_name    = "<test_table>"
  input_database_name = "<train_db>"
  model_table_name    = "<model_table>"
  model_database_name = "<train_db>"
  id_column           = "<id_col>"
  # model_type        = "Classification"       ← or "Regression"; match training task type
  # output_prob       = True                   ← classification only (needed for ROC)
  # accumulate        = ["<response_col>"]
  output_table_name   = "scored_<ts>"
  output_database_name = "<train_db>"
```

> `output_prob` requires `model_type = "Classification"`. For regression tasks, omit both.

---

### `TD_NaiveBayes` → `TD_NaiveBayesPredict`

```
Call TD_NaiveBayesPredict with:
  input_table_name    = "<test_table>"
  input_database_name = "<train_db>"
  model_table_name    = "<model_table>"
  model_database_name = "<train_db>"
  id_column           = "<id_col>"
  # numeric_inputs     = ["<num_col1>", …]   ← numeric feature columns used at training
  # categorical_inputs = ["<cat_col1>", …]   ← categorical feature columns used at training
  # output_prob        = True                 ← include for ROC evaluation
  # accumulate         = ["<response_col>"]
  output_table_name   = "scored_<ts>"
  output_database_name = "<train_db>"
```

---

### `TD_KNN` — scores inline (no separate predict)

`KNN` performs scoring during the training call itself. There is no separate predict function.
The `scored_table` is the KNN output table from Step 6.

---

### `TD_OneClassSVM` → `TD_OneClassSVMPredict`

```
Call TD_OneClassSVMPredict with:
  input_table_name    = "<test_table>"
  input_database_name = "<train_db>"
  model_table_name    = "<model_table>"
  model_database_name = "<train_db>"
  id_column           = "<id_col>"
  # accumulate         = ["<response_col>"]
  output_table_name   = "scored_<ts>"
  output_database_name = "<train_db>"
```

---

### `TD_KMeans` → `TD_KMeansPredict`

> ⚠️ **Known MCP schema quirk:** The live schema registers `input_table_name` twice — once for ModelTable (model) and once for InputTable (data). This reflects the underlying Teradata `ON … ON …` syntax. Because standard JSON parameters cannot carry duplicate keys, passing both values in a single call is unreliable — the second entry will silently overwrite the first.
>
> **Preferred alternative:** set `output_cluster_assignment = True` during training (Step 6) to obtain cluster assignments inline, avoiding this call entirely.
>
> If you must call `TD_KMeansPredict`, verify current parameter wiring with `teradata_get_tool_schema("TD_KMeansPredict")` and test with the live server before relying on the result.

```
Call TD_KMeansPredict with:
  input_table_name     = "<model_table>"       ← ModelTable (first ON clause)
  input_table_name     = "<test_table>"        ← InputTable (second ON clause) — may overwrite above in JSON
  input_database_name  = "<train_db>"
  # output_distance    = True                  ← include to output distance to nearest centroid
  # accumulate         = ["<col1>", …]
  output_table_name    = "scored_<ts>"
  output_database_name = "<train_db>"
```

> Silhouette evaluation uses the original data + cluster assignments, not a scored table.

---

## Output schema (all scorers)

The scored output table always contains at minimum:
- `id_column` — row identifier
- `prediction` (or equivalent) — predicted label / cluster / class
- Probability columns (when `output_prob=True` or `output_responses` set) — one per requested class

Inspect with `base_tableDDL` to confirm exact column names before passing to evaluators.
