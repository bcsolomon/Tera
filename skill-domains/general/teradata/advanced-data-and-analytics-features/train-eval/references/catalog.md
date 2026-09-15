# MCP Function Catalog

> All names are MCP tool short names (prefix `TD_`). These are the exact identifiers to pass to `search_tool()` and to invoke as MCP tool calls.
> Scoring, feature engineering, data preparation, and all other families are catalogued separately in [prep-catalog.md](prep-catalog.md) and are referenced by Step 5b for fix recommendations only.

## MODEL TRAINING

| MCP tool | Description |
|---|---|
| `TD_KMeans` | Partitions rows into k clusters based on feature similarity |
| `TD_DecisionForest` | Random forest classifier / regressor |
| `TD_XGBoost` | Gradient boosting classifier / regressor |
| `TD_GLM` | Generalized Linear Model — use `family="BINOMIAL"` for logistic regression |
| `TD_GLMPerSegment` | GLM trained independently per data segment |
| `TD_SVM` | Support Vector Machine for classification / regression |
| `TD_KNN` | k-Nearest Neighbors classification / regression |
| `TD_NaiveBayes` | Naive Bayes classifier — accepts categorical (VARCHAR) feature columns |
| `TD_OneClassSVM` | One-class SVM for novelty / anomaly detection |

## MODEL EVALUATION

| MCP tool | Description |
|---|---|
| `TD_ClassificationEvaluator` | Accuracy, precision, recall, F1, confusion matrix |
| `TD_RegressionEvaluator` | RMSE, MAE, R² for regression |
| `TD_ROC` | ROC curve and AUC for binary classifiers |
| `TD_Silhouette` | Silhouette score for clustering quality |
| `TD_TrainTestSplit` | Splits data into train and test sets |

## MODEL INTERPRETATION

| MCP tool | Description |
|---|---|
| `TD_SHAP` | SHAP values for feature importance and prediction explanation |

## SIMILARITY / UTILITIES

> ⚠️ These tools produce a **result table**, not a trainable model. They have no corresponding predict function, no SHAP compatibility, and no evaluation pipeline. Do not treat them as MODEL TRAINING candidates.

| MCP tool | Description |
|---|---|
| `TD_VectorDistance` | Computes pairwise distances between feature vectors — useful for similarity search or as input to manual kNN workflows |
