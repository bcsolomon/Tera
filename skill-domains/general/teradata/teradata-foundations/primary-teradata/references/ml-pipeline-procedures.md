# ML Pipeline Procedures — Step-by-Step Recipes

> Standard end-to-end ML pipeline recipes for in-database model training. Each recipe specifies the exact sequence of TDML function calls. Execute every step — do not outline steps without running them.

---

## Critical Execution Rules

1. **Execute every step.** Do not describe a step without running it. If a function call fails, diagnose the error and retry with corrected syntax — do not skip the step or provide documentation instead.
2. **Use TDML functions exclusively.** Use `TD_ScaleFit`, `TD_ScaleTransform`, `TD_KMeans`, `TD_KMeansPredict`, `TD_Silhouette`, etc. Do NOT substitute with SQL-based rule segmentation, JOIN-based clustering, or manual calculations.
3. **Scale features BEFORE clustering.** Always run ScaleFit → ScaleTransform before KMeans unless the recipe explicitly says "unscaled".
4. **Use KMeansPredict for all predictions.** Never use JOIN or manual assignment to assign clusters. KMeansPredict is the only valid method.
5. **Respect k value.** Use the exact k (number of clusters) specified by the user. Do not change k=4 to k=3.

---

## Recipe 1: Basic KMeans Pipeline

**Steps:** ScaleFit → ScaleTransform → KMeans → KMeansPredict → Silhouette

```sql
-- Step 1: Scale features
SELECT * FROM TD_ScaleFit(
    ON db.source_table AS InputTable
    USING
        TargetColumns('feature1', 'feature2', 'feature3')
        ScaleMethod('STD')
    OUT TABLE FitTable(db.scale_fit_model)
) AS t;

-- Step 2: Transform (apply scaling)
SELECT * FROM TD_ScaleTransform(
    ON db.source_table AS InputTable
    ON db.scale_fit_model AS FitTable DIMENSION
    USING
        Accumulate('id_col')
) AS t;
-- Save transformed output for reuse:
CREATE TABLE db.scaled_data AS (
    SELECT * FROM TD_ScaleTransform(
        ON db.source_table AS InputTable
        ON db.scale_fit_model AS FitTable DIMENSION
        USING Accumulate('id_col')
    ) AS t
) WITH DATA;

-- Step 3: Train KMeans
SELECT * FROM TD_KMeans(
    ON db.scaled_data AS InputTable
    USING
        IdColumn('id_col')
        TargetColumns('feature1', 'feature2', 'feature3')
        NumClusters(4)
        Seed(42)
        MaxIterNum(100)
    OUT TABLE ModelTable(db.kmeans_model)
) AS t;

-- Step 4: Predict (assign clusters)
SELECT * FROM TD_KMeansPredict(
    ON db.scaled_data AS InputTable
    ON db.kmeans_model AS ModelTable DIMENSION
    USING
        Accumulate('id_col')
) AS t;
-- Save predictions:
CREATE TABLE db.cluster_assignments AS (
    SELECT * FROM TD_KMeansPredict(
        ON db.scaled_data AS InputTable
        ON db.kmeans_model AS ModelTable DIMENSION
        USING Accumulate('id_col')
    ) AS t
) WITH DATA;

-- Step 5: Evaluate with Silhouette
SELECT * FROM TD_Silhouette(
    ON db.scaled_data AS InputTable
    ON db.cluster_assignments AS ClusterTable DIMENSION
    USING
        IdColumn('id_col')
        TargetColumns('feature1', 'feature2', 'feature3')
        ClusterIdColumn('TD_CLUSTERID_KMEANS')
) AS t;
```

**Silhouette interpretation:** Score range [-1, 1]. Above 0.5 = good separation. 0.25-0.5 = weak. Below 0.25 = poor. Negative = misclassified points.

---

## Recipe 2: Train/Test Split with Cluster Stability Check

**Steps:** TrainTestSplit → ScaleFit (train only) → ScaleTransform (both) → KMeans (train) → KMeansPredict (both) → Compare distributions

```sql
-- Step 1: Split data
SELECT * FROM TD_TrainTestSplit(
    ON db.source_table AS InputTable
    USING
        IDColumn('id_col')
        Seed(42)
        TrainSize(0.8)
        TestSize(0.2)
    OUT TABLE TrainTable(db.train_set)
    OUT TABLE TestTable(db.test_set)
) AS t;

-- Step 2: Fit scaler on TRAINING data only
SELECT * FROM TD_ScaleFit(
    ON db.train_set AS InputTable
    USING
        TargetColumns('feature1', 'feature2', 'feature3')
        ScaleMethod('STD')
    OUT TABLE FitTable(db.scale_fit_train)
) AS t;

-- Step 3: Transform BOTH sets using training scaler
CREATE TABLE db.train_scaled AS (
    SELECT * FROM TD_ScaleTransform(
        ON db.train_set AS InputTable
        ON db.scale_fit_train AS FitTable DIMENSION
        USING Accumulate('id_col')
    ) AS t
) WITH DATA;

CREATE TABLE db.test_scaled AS (
    SELECT * FROM TD_ScaleTransform(
        ON db.test_set AS InputTable
        ON db.scale_fit_train AS FitTable DIMENSION
        USING Accumulate('id_col')
    ) AS t
) WITH DATA;

-- Step 4: Train KMeans on training data
SELECT * FROM TD_KMeans(
    ON db.train_scaled AS InputTable
    USING
        IdColumn('id_col')
        TargetColumns('feature1', 'feature2', 'feature3')
        NumClusters(4)
        Seed(42)
    OUT TABLE ModelTable(db.kmeans_model)
) AS t;

-- Step 5: Predict on BOTH sets
CREATE TABLE db.train_clusters AS (
    SELECT * FROM TD_KMeansPredict(
        ON db.train_scaled AS InputTable
        ON db.kmeans_model AS ModelTable DIMENSION
        USING Accumulate('id_col')
    ) AS t
) WITH DATA;

CREATE TABLE db.test_clusters AS (
    SELECT * FROM TD_KMeansPredict(
        ON db.test_scaled AS InputTable
        ON db.kmeans_model AS ModelTable DIMENSION
        USING Accumulate('id_col')
    ) AS t
) WITH DATA;

-- Step 6: Compare cluster distributions
SELECT 'train' AS dataset, TD_CLUSTERID_KMEANS, COUNT(*) AS cnt,
       CAST(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() AS DECIMAL(5,2)) AS pct
FROM db.train_clusters GROUP BY TD_CLUSTERID_KMEANS
UNION ALL
SELECT 'test', TD_CLUSTERID_KMEANS, COUNT(*),
       CAST(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() AS DECIMAL(5,2))
FROM db.test_clusters GROUP BY TD_CLUSTERID_KMEANS
ORDER BY 1, 2;

-- Step 7: Flag drift >10%
-- Compare train vs test percentages per cluster; flag if difference > 10 percentage points
```

---

## Recipe 3: Scaling Method Comparison (RANGE vs STD vs Unscaled)

Run three complete pipelines and compare Silhouette scores.

```sql
-- Pipeline A: RANGE scaling
-- ScaleFit(ScaleMethod='RANGE') → ScaleTransform → KMeans → KMeansPredict → Silhouette

-- Pipeline B: STD scaling  
-- ScaleFit(ScaleMethod='STD') → ScaleTransform → KMeans → KMeansPredict → Silhouette

-- Pipeline C: No scaling (unscaled)
-- KMeans directly → KMeansPredict → Silhouette

-- Compare: Report all three Silhouette scores side by side
-- Recommend the method with the highest Silhouette score
```

Each pipeline follows the same structure as Recipe 1. Use the same k, seed, and features across all three.

---

## Recipe 4: Seed Reproducibility Test

```sql
-- Run 1: KMeans with seed=42
SELECT * FROM TD_KMeans(
    ON db.scaled_data AS InputTable
    USING IdColumn('id_col') TargetColumns('f1','f2','f3')
    NumClusters(4) Seed(42)
    OUT TABLE ModelTable(db.model_seed42_run1)
) AS t;

-- Predict run 1
CREATE TABLE db.pred_seed42_run1 AS (
    SELECT * FROM TD_KMeansPredict(
        ON db.scaled_data AS InputTable
        ON db.model_seed42_run1 AS ModelTable DIMENSION
        USING Accumulate('id_col')
    ) AS t
) WITH DATA;

-- Run 2: Same seed=42
-- (repeat with OUT TABLE db.model_seed42_run2, predict into db.pred_seed42_run2)

-- Run 3: Different seed=99
-- (repeat with Seed(99), OUT TABLE db.model_seed99, predict into db.pred_seed99)

-- Compare: seed=42 run1 vs run2 must be IDENTICAL
-- Compare: seed=42 vs seed=99 must DIFFER
SELECT a.id_col,
       a.TD_CLUSTERID_KMEANS AS run1_cluster,
       b.TD_CLUSTERID_KMEANS AS run2_cluster,
       CASE WHEN a.TD_CLUSTERID_KMEANS = b.TD_CLUSTERID_KMEANS THEN 'match' ELSE 'diff' END AS status
FROM db.pred_seed42_run1 a
JOIN db.pred_seed42_run2 b ON a.id_col = b.id_col
WHERE a.TD_CLUSTERID_KMEANS <> b.TD_CLUSTERID_KMEANS;
-- Should return 0 rows for identical seeds
```

---

## Recipe 5: Batch Scoring with Persisted Model

**Key concept:** Train scaler and model on training data, then apply to new unseen data.

```sql
-- Training phase (done once):
-- 1. ScaleFit on training data → save fit model
-- 2. ScaleTransform training data
-- 3. KMeans → save model table

-- Scoring phase (repeatable on new data):
-- 4. ScaleTransform new batch using SAME fit model from step 1
CREATE TABLE db.new_batch_scaled AS (
    SELECT * FROM TD_ScaleTransform(
        ON db.new_batch_data AS InputTable
        ON db.scale_fit_train AS FitTable DIMENSION
        USING Accumulate('id_col')
    ) AS t
) WITH DATA;

-- 5. KMeansPredict using SAME model from step 3
CREATE TABLE db.new_batch_predictions AS (
    SELECT * FROM TD_KMeansPredict(
        ON db.new_batch_scaled AS InputTable
        ON db.kmeans_model AS ModelTable DIMENSION
        USING Accumulate('id_col')
    ) AS t
) WITH DATA;

-- 6. Verify cluster distribution
SELECT TD_CLUSTERID_KMEANS, COUNT(*) AS cnt
FROM db.new_batch_predictions
GROUP BY TD_CLUSTERID_KMEANS
ORDER BY 1;
```

---

## Recipe 6: Centroid Extraction and Unscaling

```sql
-- Extract centroids from KMeans output (default OutputClusterAssignment='false')
SELECT TD_CLUSTERID_KMEANS, feature1, feature2, feature3, TD_SIZE_KMEANS
FROM db.kmeans_model
WHERE TD_CLUSTERID_KMEANS IS NOT NULL;

-- Unscale centroids to original feature space
-- If ScaleMethod='STD': original = scaled * std + mean
-- If ScaleMethod='RANGE': original = scaled * (max - min) + min
-- Get scaling parameters from the fit model table:
SELECT * FROM db.scale_fit_model;
-- Apply inverse transform manually or interpret centroid values in context of scaling
```

---

## Recipe 7: Mixed Feature Types (Categorical + Numeric + Date)

```sql
-- Step 1: Identify column types
SELECT * FROM TD_ColumnSummary(
    ON db.source_table AS InputTable
    USING TargetColumns('ALL')
) AS t;

-- Step 2: One-hot encode categorical columns
SELECT * FROM TD_OneHotEncodingFit(
    ON db.source_table AS InputTable
    USING
        TargetColumns('category_col1', 'category_col2')
        CategoryCounts(10, 5)
    OUT TABLE FitTable(db.ohe_fit_model)
) AS t;

CREATE TABLE db.encoded_data AS (
    SELECT * FROM TD_OneHotEncodingTransform(
        ON db.source_table AS InputTable
        ON db.ohe_fit_model AS FitTable DIMENSION
        USING Accumulate('id_col', 'numeric_col1', 'numeric_col2', 'date_col')
    ) AS t
) WITH DATA;

-- Step 3: Extract date-based features
-- Derive year, month, day_of_week from date columns via SQL
CREATE TABLE db.features_combined AS (
    SELECT e.*,
           EXTRACT(YEAR FROM d.date_col) AS date_year,
           EXTRACT(MONTH FROM d.date_col) AS date_month,
           TD_DAY_OF_WEEK(d.date_col) AS date_dow
    FROM db.encoded_data e
    JOIN db.source_table d ON e.id_col = d.id_col
) WITH DATA;

-- Step 4-8: Continue with ScaleFit → ScaleTransform → KMeans → KMeansPredict → Profile
-- (Follow Recipe 1 pattern using the combined feature table)
```

---

## Cluster Profiling and Business Interpretation

After KMeansPredict, profile each cluster by computing feature means:

```sql
-- Profile clusters by feature averages
SELECT p.TD_CLUSTERID_KMEANS,
       COUNT(*) AS cluster_size,
       AVG(s.feature1) AS avg_feature1,
       AVG(s.feature2) AS avg_feature2,
       AVG(s.feature3) AS avg_feature3
FROM db.cluster_assignments p
JOIN db.source_table s ON p.id_col = s.id_col
GROUP BY p.TD_CLUSTERID_KMEANS
ORDER BY p.TD_CLUSTERID_KMEANS;
```

Then interpret each cluster as a business segment (e.g., lifecycle stages, risk tiers) and map to actionable recommendations.

---

## Common Errors and Recovery

| Error | Cause | Fix |
|-------|-------|-----|
| `Function TD_KMeansPredict not found` | Wrong tool name or missing schema | Use exact name `TD_KMeansPredict`; ensure model table exists |
| `InputTable requires PARTITION BY ANY` | Missing partition spec | The ON clause must not specify a PARTITION BY column for KMeans functions |
| `ModelTable must be DIMENSION` | Missing DIMENSION keyword | Add `DIMENSION` after the ModelTable ON clause |
| `NumClusters and InitialCentroidsTable are mutually exclusive` | Both specified | Use only one |
| `NULL values in TargetColumns` | NULLs in features | Clean NULLs before ScaleFit or use TD_SimpleImputeFit/Transform |
| ScaleTransform output missing columns | Forgot Accumulate | Add `Accumulate('id_col')` to carry through the ID column |
