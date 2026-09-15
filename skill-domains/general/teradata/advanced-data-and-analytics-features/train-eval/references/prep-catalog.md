# Preparation & Supporting Functions — MCP Tool Reference

This file catalogues the MCP tools available for data preparation, scoring, exploration, and supporting analytics. It is referenced by the function-trainer skill's Step 4b cross-reference checks to provide fix recommendations. It is **not** part of the skill's execution scope.

> Current (TD_-prefixed) tools use prefix `TD_`. Legacy MLE-path tools have no prefix.

---

## MODEL SCORING
Functions that score new data using a trained model.

| MCP tool | Paired trainer |
|---|---|
| `TD_KMeansPredict` | `TD_KMeans` |
| `TD_XGBoostPredict` | `TD_XGBoost` |
| `TD_SVMPredict` | `TD_SVM` |
| `TD_OneClassSVMPredict` | `TD_OneClassSVM` |
| `TD_DecisionForestPredict` | `TD_DecisionForest` |
| `TD_GLMPREDICT` | `TD_GLM` |
| `TD_NaiveBayesPredict` | `TD_NaiveBayes` |
| `TD_GLMPredictPerSegment` | `TD_GLMPerSegment` |

## MLE SCORING
Functions that score using MLE-path model objects.

| MCP tool | Paired trainer |
|---|---|
| `DecisionForestPredict` | `TD_DecisionForest` (legacy path) |
| `GLMPredict` | `TD_GLM` (legacy path) |
| `NaiveBayesTextClassifierPredict` | `TD_NaiveBayesTextClassifierTrainer` |
| `SVMSparsePredict` | `TD_SVM` (sparse format) |

---

## FEATURE ENGINEERING TRANSFORM
Fit/Transform pairs. Run Fit first to compute parameters, then Transform to apply.

| Fit tool | Transform tool | Purpose |
|---|---|---|
| `TD_ScaleFit` | `TD_ScaleTransform` | Numeric scaling (min-max, z-score) — **required before KMeans, KNN, VectorDistance** |
| `TD_SimpleImputeFit` | `TD_SimpleImputeTransform` | Impute missing values (mean, median, mode) |
| `TD_OutlierFilterFit` | `TD_OutlierFilterTransform` | Remove outlier rows by statistical threshold |
| `TD_OneHotEncodingFit` | `TD_OneHotEncodingTransform` | One-hot encode categorical columns |
| `TD_OrdinalEncodingFit` | `TD_OrdinalEncodingTransform` | Ordinal encode ordered categorical columns |
| `TD_TargetEncodingFit` | `TD_TargetEncodingTransform` | Target (mean) encode categorical columns |
| `TD_BinCodeFit` | `TD_BinCodeTransform` | Discretize continuous values into bins |
| `TD_RowNormalizeFit` | `TD_RowNormalizeTransform` | Row-level normalization |
| `TD_RandomProjectionFit` | `TD_RandomProjectionTransform` | Dimensionality reduction via random projection |
| `TD_PolynomialFeaturesFit` | `TD_PolynomialFeaturesTransform` | Polynomial feature expansion |
| `TD_NonLinearCombineFit` | `TD_NonLinearCombineTransform` | Non-linear feature combinations |

## FEATURE ENGINEERING UTILITY

| MCP tool | Description |
|---|---|
| `TD_SMOTE` | Synthetic minority over-sampling for class imbalance |
| `TD_TFIDF` | TF-IDF vectorization — text to numeric features |
| `TD_FillRowID` | Adds a unique row ID column — **use when id_column is missing** |
| `TD_ColumnTransformer` | Apply different transforms to different column groups |
| `TD_FunctionFit` | Generic fit wrapper |
| `TD_FunctionTransform` | Generic transform wrapper |
| `TD_Pivoting` | Pivot rows to columns |
| `TD_Unpivoting` | Unpivot columns to rows |
| `TD_RandomProjectionMinComponents` | Minimum components for a given tolerance |
| `TD_NumApply` | Apply a numeric function to selected columns |
| `TD_StrApply` | Apply a string function to selected columns |
| `TD_RoundColumns` | Round numeric column values |
| `Antiselect` | Drop specified columns |
| `Pack` | Pack multiple columns into one |
| `Unpack` | Unpack a packed column into multiple columns |

---

## DATA EXPLORATION

| MCP tool | Description |
|---|---|
| `TD_UnivariateStatistics` | Descriptive statistics (mean, stddev, min, max) per column |
| `TD_CategoricalSummary` | Frequency and cardinality for categorical columns |
| `TD_ColumnSummary` | Column datatypes and NULL / non-NULL counts |
| `TD_Histogram` | Frequency distribution |
| `TD_QQNorm` | Quantile-quantile normality assessment |
| `MovingAverage` | Rolling / moving average smoothing |
| `TD_WhichMax` | Rows containing the maximum value in a column |
| `TD_WhichMin` | Rows containing the minimum value in a column |
| `TD_GetRowsWithMissingValues` | Returns rows containing NULL values |

## DATA CLEANING

| MCP tool | Description |
|---|---|
| `TD_GetRowsWithoutMissingValues` | Returns rows with no NULL values |
| `TD_GetFutileColumns` | Identifies zero / near-zero variance columns |
| `TD_ConvertTo` | Type conversion for columns |
| `StringSimilarity` | Fuzzy / exact string similarity scoring |

---

## HYPOTHESIS TESTING

| MCP tool | Description |
|---|---|
| `TD_ANOVA` | Analysis of variance |
| `TD_Chisq` | Chi-squared test of independence |
| `TD_FTest` | F-test for variance equality |
| `TD_ZTest` | Z-test for proportions or means |

---

## TEXT ANALYTIC

| MCP tool | Description |
|---|---|
| `TD_TextParser` | Tokenizes and parses text documents |
| `NGramSplitter` | Splits text into n-gram tokens |
| `TD_SentimentExtractor` | Rule-based sentiment scoring |
| `TD_WordEmbeddings` | Word embedding computation |
| `TD_NaiveBayesTextClassifierTrainer` | Trains a Naive Bayes text classifier |
| `NaiveBayesTextClassifierPredict` | Predicts using NaiveBayesTextClassifierTrainer model |
| `TD_NERExtractor` | Named entity recognition |
| `TD_TextMorph` | Text transformation / morphological analysis |

---

## ASSOCIATION ANALYSIS

| MCP tool | Description |
|---|---|
| `TD_Apriori` | Association rule mining (market basket analysis) |
| `TD_CFilter` | Collaborative filtering for item-based recommendations |

---

## PATH AND PATTERN ANALYSIS

| MCP tool | Description |
|---|---|
| `nPath` | Pattern matching along ordered event paths / sequences |
| `Sessionize` | Groups events into sessions by time gap |
| `Attribution` | Marketing attribution across event sequences |
