# Feature Importance Reference

> **Used by:** Step 5 parameter card (OUTPUTS and FEATURE IMPORTANCE sections) and Step 7 (reporting).
>
> **Inputs from State Manifest:** `function_name`, `model_table`, `characteristics.Native importance in output`, `characteristics.SHAP-compatible`

---

## OUTPUTS — What the model table contains

Use this to fill the **OUTPUTS** section of the parameter card after training:

| Function | `model_table` contains |
|---|---|
| `TD_GLM` | `.result` — coefficient table (one row per predictor); `.output_data` — MSE, Loglikelihood, AIC, BIC |
| `TD_DecisionForest` | Tree node structure: feature names, split conditions, split gains |
| `TD_XGBoost` | Tree node structure: feature names, split gains, boosting iteration info |
| `TD_KMeans` | Cluster centroids (one row per cluster) + WCSS — also returned inline in execution result |
| `TD_SVM` | Learned weight vector (support vectors) |
| `TD_OneClassSVM` | Support vectors for the inlier boundary |
| `TD_KNN` / `TD_NaiveBayes` | No persistent model table — scores inline; nothing to query |

---

## FEATURE IMPORTANCE — Extraction patterns

Choose the pattern based on `characteristics.Native importance in output` from the State Manifest.

### Pattern A — `coefficients` (GLM)

No data table needed — query the model table directly after training.

**Native extraction:**
```
Use MCP tool: base_readQuery with query:
  SELECT predictor, coefficient, ABS(coefficient) AS abs_coef
  FROM <model_table>
  WHERE predictor <> 'intercept'
  ORDER BY abs_coef DESC;
```

**SHAP (optional — needs a data table):**
```
Call TD_SHAP with:
  object            = <model_table>
  training_function = "TD_GLM"
  data              = <train_table>
  id_column         = <id_col>
  input_columns     = [<same columns used in training>]
  model_type        = "<Classification|Regression>"
```

Then aggregate SHAP output:
```
Use MCP tool: base_readQuery with query:
  SELECT feature_name, AVG(ABS(shap_value)) AS mean_abs_shap,
         RANK() OVER (ORDER BY AVG(ABS(shap_value)) DESC) AS imp_rank
  FROM <shap_output_table>
  GROUP BY feature_name
  ORDER BY imp_rank;
```

---

### Pattern B — `split-importance` (DecisionForest, XGBoost)

No data table needed — split gains are embedded in the model table from training.

**Step 1 — Inspect model table columns:**
```
Use MCP tool: base_tableDDL(table_name="<model_table>", database_name="<train_db>")
```
> Column names vary by Vantage version. Identify the feature name column and the importance/gain column before querying.
>
> ⚠️ **XGBoost JSON model table:** On some Vantage versions `TD_XGBoost` stores trees as a single `classification_tree VARCHAR(32000)` JSON column — there are no explicit feature or importance columns. If the DDL shows only `classification_tree`, skip the Step 2 template below and use this extraction instead:
> ```sql
>   SELECT OREPLACE(OREPLACE(
>            REGEXP_SUBSTR(classification_tree, '"attr_":"[^"]+"'),
>            '"attr_":"', ''), '"', '')                          AS feature_name,
>          COUNT(*)                                              AS tree_count,
>          SUM(CAST(OREPLACE(
>            REGEXP_SUBSTR(classification_tree, '"scoreImprove_":[0-9.]+'),
>            '"scoreImprove_":', '') AS FLOAT))                  AS total_root_gain
>   FROM <model_table>
>   WHERE tree_num >= 0
>   GROUP BY feature_name
>   ORDER BY total_root_gain DESC;
> ```
> This extracts root-split importance (the first split per boosting tree) — a reliable proxy without requiring capture-group `REGEXP_SUBSTR` (unsupported in Teradata) or JSON path functions.

**Step 2 — Extract ranked importance:**
```
Use MCP tool: base_readQuery with query:
  SELECT <feature_col>, SUM(<importance_col>) AS total_gain,
         RANK() OVER (ORDER BY SUM(<importance_col>) DESC) AS imp_rank
  FROM <model_table>
  WHERE <feature_col> IS NOT NULL
  GROUP BY <feature_col>
  ORDER BY imp_rank;
```

**SHAP (optional — needs a data table, tree-level detail available):**
```
Call TD_SHAP with:
  object            = <model_table>
  training_function = "TD_DECISIONFOREST"   ← or "TD_XGBOOST"
  data              = <train_table>
  id_column         = <id_col>
  input_columns     = [<same columns used in training>]
  model_type        = "<Classification|Regression>"
  detailed          = False                 ← set True for per-tree breakdown
```

Then aggregate as in Pattern A.

---

### Pattern C — `none` (SVM, KNN, NaiveBayes, OneClassSVM, KMeans)

No feature importance is available for this function. Show in the parameter card:

```
FEATURE IMPORTANCE:
  ← Not available — SHAP not supported and no importance data embedded in model output
     for <function_name>
```
