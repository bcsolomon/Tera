---
name: teradata-data-preparation
description: 'Use native Teradata data exploration, cleaning, and feature engineering functions to prepare high-volume datasets in-database for analytics and machine learning workflows.'
metadata:
    author: teradata
    version: "1.0"
---

# Teradata Data Preparation & Feature Engineering

> **Skill:** teradata-data-preparation  
> **Domain:** 12-advanced-data-and-analytics-features / 06-feature-store  
> **Applies to:** Teradata Vantage 17.10+, VantageCloud Lake  

---

## Purpose

Guide agents through in-database data exploration, cleaning, and feature engineering using native Teradata functions. All operations run distributed across AMPs — never pull raw data to the client for processing.

> **Rule:** Always prefer native Teradata functions over hand-written SQL equivalents. Native table operators run distributed across all AMPs and outperform manual SQL. See [references/guidelines.md](references/guidelines.md) for the full operation-to-function mapping.

---

## When to Use This Skill

- Before ML training: explore → clean → engineer features → train
- Data quality assessment on new or unfamiliar tables
- Feature engineering for classification, regression, or clustering pipelines
- Reshaping data (pivot/unpivot) for reporting or analytics input

---

## Workflow: Explore → Clean → Prepare

### Phase 1 — Data Exploration

Use native functions to understand data before transforming it.

| Task | Function | Reference |
|------|----------|-----------|
| Column-level summary statistics | `TD_ColumnSummary` | [data-exploration.md](references/data-exploration.md) |
| Univariate distribution analysis | `TD_UnivariateStatistics` | [data-exploration.md](references/data-exploration.md) |
| Histogram / frequency binning | `TD_Histogram` | [data-exploration.md](references/data-exploration.md) |
| Q-Q normality check | `TD_QQNorm` | [data-exploration.md](references/data-exploration.md) |
| Pairwise correlation matrix | `TD_Correlation` | [data-exploration.md](references/data-exploration.md) |
| Moving/rolling average | `TD_MovingAverage` | [data-exploration.md](references/data-exploration.md) |

```sql
-- Quick column summary (replaces manual COUNT/AVG/STDDEV per column)
SELECT * FROM TD_ColumnSummary(
    ON db.my_table AS InputTable PARTITION BY ANY
    USING TargetColumns('[1:20]')
) AS t;
```

### Phase 2 — Data Cleaning

| Task | Function | Reference |
|------|----------|-----------|
| Outlier detection and removal | `TD_OutlierFilterFit` / `TD_OutlierFilterTransform` | [data-cleaning.md](references/data-cleaning.md) |
| NULL imputation | `TD_SimpleImputeFit` / `TD_SimpleImputeTransform` | [data-cleaning.md](references/data-cleaning.md) |
| Find rows with missing values | `TD_GetRowsWithMissingValues` | [data-cleaning.md](references/data-cleaning.md) |
| Identify useless columns | `TD_GetFutileColumns` | [data-cleaning.md](references/data-cleaning.md) |
| Fuzzy string matching | `StringSimilarity` | [data-cleaning.md](references/data-cleaning.md) |
| Type conversion | `TD_ConvertTo` | [data-cleaning.md](references/data-cleaning.md) |
| Deduplication | `ROW_NUMBER() + QUALIFY` pattern | [data-cleaning.md](references/data-cleaning.md) |

### Phase 3 — Feature Engineering

| Task | Function | Reference |
|------|----------|-----------|
| Z-score / min-max scaling | `TD_ScaleFit` / `TD_ScaleTransform` | [data-prep.md](references/data-prep.md) |
| Vector normalization (L2) | `TD_VectorNormalize` | [data-prep.md](references/data-prep.md) |
| Equal-width/frequency binning | `TD_BinCodeFit` / `TD_BinCodeTransform` | [data-prep.md](references/data-prep.md) |
| One-hot encoding | `TD_OneHotEncodingFit` / `TD_OneHotEncodingTransform` | [data-prep.md](references/data-prep.md) |
| Ordinal encoding | `TD_OrdinalEncodingFit` / `TD_OrdinalEncodingTransform` | [data-prep.md](references/data-prep.md) |
| Target encoding | `TD_TargetEncodingFit` / `TD_TargetEncodingTransform` | [data-prep.md](references/data-prep.md) |
| Pivot (long → wide) | `TD_Pivoting` | [data-prep.md](references/data-prep.md) |
| Unpivot (wide → long) | `TD_Unpivoting` | [data-prep.md](references/data-prep.md) |
| Polynomial features | `TD_PolynomialFeaturesFit` / `TD_PolynomialFeaturesTransform` | [data-prep.md](references/data-prep.md) |
| SMOTE oversampling | `TD_SMOTE` | [data-prep.md](references/data-prep.md) |
| Apply multiple transforms | `TD_ColumnTransformer` | [data-prep.md](references/data-prep.md) |
| Dimensionality reduction | `TD_PCA` / `TD_PCATransform` | [data-prep.md](references/data-prep.md) |
| Row-level normalization | `TD_RowNormalizeFit` / `TD_RowNormalizeTransform` | [data-prep.md](references/data-prep.md) |

---

## Fit/Transform Pattern

Most data preparation functions follow a two-phase Fit/Transform pattern:

1. **Fit** — learns parameters from training data (means, std devs, bin edges, encoding maps)
2. **Transform** — applies those parameters to training or new data

```sql
-- Step 1: Fit — learn scaling parameters
CREATE TABLE db.scale_fit AS (
    SELECT * FROM TD_ScaleFit(
        ON db.train_data AS InputTable PARTITION BY ANY
        USING
            TargetColumns('col1', 'col2', 'col3')
            ScaleMethod('STD')                  -- Z-score: (x - mean) / stddev
    ) AS t
) WITH DATA;

-- Step 2: Transform — apply to training data
SELECT * FROM TD_ScaleTransform(
    ON db.train_data AS InputTable PARTITION BY ANY
    ON db.scale_fit AS FitTable DIMENSION
    USING
        Accumulate('id', 'label')
) AS t;

-- Step 3: Transform — apply SAME parameters to new/test data
SELECT * FROM TD_ScaleTransform(
    ON db.test_data AS InputTable PARTITION BY ANY
    ON db.scale_fit AS FitTable DIMENSION
    USING
        Accumulate('id')
) AS t;
```

> **Critical:** Always save the Fit table and reuse it for test/production data. Never re-fit on test data — that causes data leakage.

See [references/fit-transform-pattern.md](references/fit-transform-pattern.md) for the complete pattern reference.

---

## TD_ColumnTransformer — Apply Multiple Transforms in One Pass

When a pipeline requires scaling + encoding + other transforms, use `TD_ColumnTransformer` to apply all saved FitTables in a single query:

```sql
SELECT * FROM TD_ColumnTransformer(
    ON db.raw_data AS InputTable PARTITION BY ANY
    ON db.scale_fit AS ScaleFitTable DIMENSION
    ON db.encode_fit AS OneHotEncodingFitTable DIMENSION
    ON db.bin_fit AS BinCodeFitTable DIMENSION
    USING
        Accumulate('id', 'label')
) AS t;
```

---

## TD_VectorNormalize — Embedding Pre-Processing

Required before cosine similarity or HNSW indexing:

```sql
SELECT * FROM TD_VectorNormalize(
    ON db.embeddings AS InputTable PARTITION BY ANY
    USING
        IDColumns('doc_id')
        TargetColumns('embedding')        -- supports VECTOR type
        Approach('UNITVECTOR')            -- L2 normalization to unit length
) AS t;
```

| Approach | Formula | Use Case |
|----------|---------|----------|
| `UNITVECTOR` | `x / L2_norm(row)` | Embedding normalization for cosine similarity |
| `FRACTION` | `x / sum(row)` | Value as fraction of row total |
| `PERCENTAGE` | `x / sum(row) * 100` | Value as percentage of row total |
| `INDEX` | `(x - B) / V` | Normalize relative to a base value |

---

## Utility Functions

| Function | Purpose | Reference |
|----------|---------|-----------|
| `TD_FillRowID` | Add sequential row IDs to a result set | [utility-functions.md](references/utility-functions.md) |
| `TD_NumApply` | Apply a numeric expression to multiple columns | [utility-functions.md](references/utility-functions.md) |
| `TD_RoundColumns` | Round multiple numeric columns at once | [utility-functions.md](references/utility-functions.md) |
| `TD_StrApply` | Apply string operations to multiple columns | [utility-functions.md](references/utility-functions.md) |
| `Antiselect` | SELECT all columns except specified ones | [data-prep.md](references/data-prep.md) |

---

## Common Pitfalls

| Mistake | Fix |
|---------|-----|
| Re-fitting on test data | Save the Fit table; reuse it for all Transform calls |
| Manual Z-score with window functions | Use `TD_ScaleFit(ScaleMethod('STD'))` — distributes across AMPs |
| Manual CASE-based one-hot encoding | Use `TD_OneHotEncodingFit` — handles unknown categories |
| Pulling data to client for pandas transforms | Use native functions — data stays on platform |
| SMOTE on full dataset (train + test) | Split first with `TD_TrainTestSplit`, then SMOTE on train only |

---

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-data-preparation", path="references/FILENAME")` — do NOT call `list`.

| File | Content |
|------|---------|
| [data-prep.md](references/data-prep.md) | Full syntax: scaling, binning, encoding, pivoting, polynomial features, SMOTE, PCA |
| [data-cleaning.md](references/data-cleaning.md) | Full syntax: imputation, outlier detection, dedup, fuzzy matching, type conversion |
| [data-exploration.md](references/data-exploration.md) | Full syntax: column summary, univariate stats, histogram, correlation, moving average |
| [fit-transform-pattern.md](references/fit-transform-pattern.md) | Fit/Transform pattern reference and FitTable naming conventions |
| [utility-functions.md](references/utility-functions.md) | TD_FillRowID, TD_NumApply, TD_RoundColumns, TD_StrApply |
| [guidelines.md](references/guidelines.md) | Native function guidelines — canonical mapping of SQL operations to native functions |

---

*Source: Teradata tdsql-mcp syntax library (ksturgeon-td/tdsql-mcp)*
