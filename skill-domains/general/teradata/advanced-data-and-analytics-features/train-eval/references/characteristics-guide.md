# Function Characteristics Guide

> Read this guide during Step 3 after loading the function's live documentation from the MCP server.
> Extract every field from both tables below and record the complete result in `characteristics` (State Manifest).
> Steps 4c, 5, 5b, and 7 consume these values — never re-derive them from the function name or re-read the docs downstream.

## Characteristic Profile

For every parameter in the function's DESCRIPTION and PARAMETERS sections, record:

- **Required** or **Optional** (from "Required Argument." / "Optional Argument.")
- **Type** (from "Types:" line)
- **Default Value** (from "Default Value:" line — if present)
- **Permitted Values** (from "Permitted Values:" line — if present, these are the only valid values)
- **Notes / mutual exclusions** (from "Note:" block — e.g. `num_clusters` vs `centroids_data`)

> Do NOT rely on the JSON schema block — it only carries `title` and `default`.
> Always select the exact-match tool and ignore semantically similar results
> (e.g. do not confuse `TD_KMeans` with `TD_KMeansPredict` or `TD_KNN`).

Then extract and record every field in the table below:

| Characteristic | How to determine | Record as |
|---|---|---|
| Feature column type requirement | DESCRIPTION notes + parameter Types | `numeric only` or `categorical accepted` |
| `id_column` required | Is `id_column` a Required Argument? | Yes / No |
| Distance-based algorithm | KMeans, KNN → sensitive to scale differences | Yes / No |
| Supervised (needs response column) | `response_column` or equivalent is Required | Yes / No |
| Response column type constraint | Types: line of response/target parameter | `INTEGER only` / `VARCHAR accepted` / `numeric` |
| NULLs silently excluded | DESCRIPTION Notes block | Yes / No |
| Task type | Context of function | `classification` / `regression` / `clustering` / `unsupervised` / `distance` |
| Native importance in output | Does the DESCRIPTION / OUTPUTS section mention coefficients, weights, variable importance, or split gains? | `coefficients` (GLM) / `split-importance` (DecisionForest, XGBoost) / `none` |
| SHAP-compatible | Is this function one of the three values permitted by the `training_function` argument of `TD_SHAP`? (`TD_GLM`, `TD_DECISIONFOREST`, `TD_XGBOOST`) | Record the exact value to pass, e.g. `TD_DECISIONFOREST` — or `none` if not listed. Note: `detailed=True` is available for `TD_DECISIONFOREST` and `TD_XGBOOST` only. |
| Scoring function | DESCRIPTION says "model is used as input to `<X>Predict()`" | Short name, e.g. `TD_XGBoostPredict` — or `none` for KNN (scores inline) or unsupervised functions |
| `output_prob` in scoring | Does the scoring function's docstring include an `output_prob` parameter? | `yes` — required to produce class probabilities for `TD_ROC` / `no` |
| Applicable evaluators | Derived from task type | `classification` → `TD_ClassificationEvaluator` + `TD_ROC`; `regression` → `TD_RegressionEvaluator`; `clustering` → `TD_Silhouette`; `anomaly` / `unsupervised` → none |

## Data Handling Profile

> The in-database implementation of a function may behave differently from the generic ML algorithm. Only the live documentation tells you:
> - Whether this specific function handles NULLs natively, silently excludes NULL rows, or requires imputation beforehand
> - Whether any parameter (e.g. a `miss_value` or `null_handling` argument) provides a built-in workaround
> - Whether the DESCRIPTION explicitly recommends pre-processing steps (scaling, encoding, etc.)

While reading the DESCRIPTION, also note and record:

| Item to look for | Where in the documentation | Record as |
|---|---|---|
| NULL behaviour | Notes block: "rows with NULL in X are ignored" / "must be imputed" / "handled natively" | `excluded` / `impute-required` / `native` |
| Parameters that address data quality | Parameter list: any param named `miss_value`, `handle_missing`, `null_handling`, etc. | Parameter name + default |
| Explicit pre-processing recommendations | DESCRIPTION text: mentions of scaling, encoding, imputation | Note verbatim |
| Encoding requirement | Whether input columns must be numeric (most functions) or may be VARCHAR (NaiveBayes) | `numeric-only` / `varchar-ok` |
