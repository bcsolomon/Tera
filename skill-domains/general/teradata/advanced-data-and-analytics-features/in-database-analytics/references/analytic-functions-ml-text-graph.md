# Analytic Functions — ML, Text, Time Series, Graph & Geometry

All Teradata Vantage analytic functions use the table operator invocation pattern:

```sql
SELECT * FROM FunctionName (
    ON input_table [AS InputRole]
    [ON ref_table AS RefRole DIMENSION]
    [PARTITION BY col | ORDER BY col]
    USING
        Param1('value1')
        Param2('value2')
) AS alias;
```

---

## Statistics & Machine Learning Functions

### Decision Tree (Single)

```sql
SELECT * FROM DecisionTree (
    ON training_data AS InputTable
    OUT TABLE OutputTable(mydb.dt_model)
    USING
        ResponseColumn('target')
        NumericInputs('age', 'income', 'credit_score')
        CategoricalInputs('region', 'segment', 'channel')
        TreeType('CLASSIFICATION')     -- or REGRESSION
        MaxDepth(12)
        MinNodeSize(50)
        SplitMeasure('GINI')           -- or ENTROPY, CHISQUARE
        Pruning('TRUE')
        PruningType('COST_COMPLEXITY')
) AS dt;
```

### Decision Forest (Random Forest)

```sql
SELECT * FROM DecisionForest (
    ON training_data AS InputTable
    OUT TABLE OutputTable(mydb.rf_model)
    USING
        ResponseColumn('target')
        NumericInputs('feature1', 'feature2', 'feature3')
        CategoricalInputs('cat1', 'cat2')
        TreeType('CLASSIFICATION')
        NumTrees(100)
        MaxDepth(15)
        MinNodeSize(10)
        Mtry(3)                        -- features per split
        Seed(42)
) AS rf;
```

### Single Tree / Forest Predict

```sql
SELECT * FROM SingleTreePredict (
    ON scoring_data AS InputTable
    ON mydb.dt_model AS ModelTable DIMENSION
    USING
        AttrTableGroupByColumns('region', 'segment')
        AttrTablePIDColumns('age', 'income', 'credit_score')
        Verbose('true')
) AS predictions;

SELECT * FROM DecisionForestPredict (
    ON scoring_data AS InputTable
    ON mydb.rf_model AS ModelTable DIMENSION
    USING
        NumericInputs('feature1', 'feature2', 'feature3')
        CategoricalInputs('cat1', 'cat2')
        Verbose('true')
) AS predictions;
```

### GLM — Generalized Linear Model

```sql
-- Train
SELECT * FROM GLM (
    ON training_data
    USING
        TargetColumns('revenue')
        CategoricalColumns('region', 'product_type')
        Family('GAUSSIAN')             -- GAUSSIAN, BINOMIAL, POISSON, GAMMA, INVERSE_GAUSSIAN
        Link('IDENTITY')               -- IDENTITY, LOG, LOGIT, PROBIT, COMPLEMENTARY_LOG_LOG
        MaxIterNum(25)
        Threshold(0.001)
) AS model;

-- Predict
SELECT * FROM GLMPredict (
    ON scoring_data AS InputTable
    ON mydb.glm_model AS ModelTable DIMENSION
    USING
        Accumulate('customer_id')
        Family('GAUSSIAN')
        Link('IDENTITY')
) AS predictions;
```

### KMeans — Clustering

```sql
SELECT * FROM KMeans (
    ON input_data
    USING
        NumClusters(5)
        MaxIterNum(100)
        Threshold(0.01)
        TargetColumns('feature1', 'feature2', 'feature3')
        Seed(42)
) AS clusters;
-- Output includes cluster_id for each row
```

### KNN — K-Nearest Neighbor

```sql
SELECT * FROM KNN (
    ON test_data AS TestTable
    ON training_data AS TrainingTable DIMENSION
    USING
        ResponseColumn('label')
        DistanceFeatures('f1', 'f2', 'f3')
        K(5)
        VotingWeight('DISTANCE')       -- UNIFORM or DISTANCE
) AS predictions;
```

### SVM — Support Vector Machine

```sql
-- Sparse SVM (Train)
SELECT * FROM SVMSparse (
    ON training_data
    USING
        IDColumn('id')
        AttributeNameColumn('attr_name')
        AttributeValueColumn('attr_value')
        TargetColumn('label')
        Cost(1.0)
        Bias(0)
        MaxStep(100)
) AS svm;

-- Dense SVM (Train)
SELECT * FROM SVMDense (
    ON training_data
    USING
        TargetColumns('label')
        TargetColumn('target')
        Cost(1.0)
) AS svm;
```

### XGBoost

```sql
-- Train
SELECT * FROM XGBoost (
    ON training_data AS InputTable
    OUT TABLE OutputTable(mydb.xgb_model)
    USING
        ResponseColumn('target')
        NumericInputs('f1', 'f2', 'f3')
        LossFunction('SOFTMAX')        -- SOFTMAX, SOFTPROB, LOGISTIC, BINOMIAL
        NumBoostedTrees(100)
        MaxDepth(6)
        LearningRate(0.1)
        RegularizationLambda(1)
        MinNodeSize(5)
        Seed(42)
) AS xgb;

-- Predict
SELECT * FROM XGBoostPredict (
    ON scoring_data AS InputTable
    ON mydb.xgb_model AS ModelTable DIMENSION
    USING
        NumericInputs('f1', 'f2', 'f3')
        IdColumn('customer_id')
) AS predictions;
```

### Linear Regression

```sql
SELECT * FROM LinearRegression (
    ON training_data
    USING
        TargetColumns('price')
        CategoricalColumns('neighborhood')
        Threshold(0.001)
        MaxIterNum(50)
) AS lr;
```

### LASSO / LARS

```sql
SELECT * FROM LARS (
    ON training_data
    USING
        TargetColumn('target')
        TargetColumns('f1', 'f2', 'f3', 'f4', 'f5')
        Method('LASSO')               -- LARS, LASSO, EN (Elastic Net)
        MaxIterNum(500)
) AS lasso;
```

### PCA — Principal Component Analysis

```sql
-- Compute PCA
SELECT * FROM PCA (
    ON input_data
    USING
        TargetColumns('f1', 'f2', 'f3', 'f4', 'f5')
        NumComponents(3)
) AS pca;

-- Score with PCA
SELECT * FROM PCAScore (
    ON input_data AS InputTable
    ON mydb.pca_model AS PCATable DIMENSION
    USING
        Components(3)
        Accumulate('id')
) AS scored;
```

### Naïve Bayes

```sql
-- Train
SELECT * FROM NaiveBayesClassifier (
    ON training_data
    USING
        ResponseColumn('label')
        NumericInputs('f1', 'f2')
        CategoricalInputs('cat1', 'cat2')
) AS nb;

-- Predict
SELECT * FROM NaiveBayesPredict (
    ON scoring_data AS InputTable
    ON mydb.nb_model AS ModelTable DIMENSION
    USING
        IdColumn('id')
        NumericInputs('f1', 'f2')
        CategoricalInputs('cat1', 'cat2')
) AS predictions;
```

### AdaBoost

```sql
SELECT * FROM AdaBoost (
    ON training_data AS InputTable
    OUT TABLE OutputTable(mydb.ada_model)
    USING
        ResponseColumn('target')
        NumericInputs('f1', 'f2', 'f3')
        IterNum(50)
) AS ada;
```

### Confusion Matrix

```sql
SELECT * FROM ConfusionMatrix (
    ON predictions_table
    PARTITION BY 1
    USING
        ObservationColumn('actual')
        PredictColumn('predicted')
) AS cm;
```

### Cross Validation

```sql
SELECT * FROM CrossValidation (
    ON training_data
    USING
        ResponseColumn('target')
        NumericInputs('f1', 'f2', 'f3')
        FoldNum(5)
        Algorithm('DECISION_TREE')
) AS cv;
```

---

## Text Analytics Functions

### NER — Named Entity Recognition

```sql
-- Train
SELECT * FROM NERTrainer (
    ON training_corpus
    USING
        TextColumn('sentence')
        ModelFile('ner_model.bin')
) AS ner;

-- Extract
SELECT * FROM NERExtractor (
    ON input_text AS InputTable
    ON mydb.ner_model AS ModelTable DIMENSION
    USING
        TextColumn('document_text')
) AS entities;
```

### Sentiment Extraction

```sql
-- Train
SELECT * FROM SentimentTrainer (
    ON labeled_reviews
    USING
        TextColumn('review_text')
        SentimentColumn('sentiment')
        ModelFile('sentiment_model.bin')
) AS trainer;

-- Extract
SELECT * FROM SentimentExtractor (
    ON reviews AS InputTable
    ON mydb.sentiment_model AS ModelTable DIMENSION
    USING
        TextColumn('review_text')
) AS sentiments;
```

### LDA — Topic Modeling

```sql
SELECT * FROM LDA (
    ON document_term_matrix
    USING
        TopicNum(20)
        DocIDColumn('doc_id')
        WordColumn('term')
        CountColumn('term_count')
        MaxIterNum(50)
        Seed(42)
) AS topics;
```

### TF-IDF

```sql
SELECT * FROM TFIDF (
    ON (
        SELECT doc_id, term, term_count FROM doc_terms
    ) AS tf
    ON (
        SELECT term, COUNT(DISTINCT doc_id) AS df FROM doc_terms GROUP BY term
    ) AS df DIMENSION
    USING
        TfColumn('term_count')
        DfColumn('df')
        NumDocs(10000)
        OutputType('TFIDF')
) AS tfidf;
```

### nGram

```sql
SELECT * FROM NGram (
    ON input_text
    USING
        TextColumn('text')
        Grams('2', '3')               -- bigrams and trigrams
        Delimiter(' ')
        Accumulate('doc_id')
) AS ngrams;
```

---

## Time Series Functions

### ARIMA

```sql
-- Train
SELECT * FROM ARIMA (
    ON time_series_data
    PARTITION BY series_id
    ORDER BY time_period
    USING
        TimeColumn('time_period')
        ResponseColumn('value')
        Order('1', '1', '1')           -- p, d, q
        SeasonalOrder('0', '1', '1')   -- P, D, Q
        Period(12)                     -- seasonal period
        MaxIterNum(100)
) AS model;

-- Predict
SELECT * FROM ARIMAPredict (
    ON mydb.arima_model AS ModelTable
    USING
        StepsAhead(12)
) AS forecast;
```

### Burst Detection

```sql
SELECT * FROM Burst (
    ON time_series_data
    PARTITION BY series_id
    ORDER BY time_period
    USING
        TimeColumn('time_period')
        ValueColumn('event_count')
        NumStates(2)
        Gamma(1.0)
) AS bursts;
```

### Changepoint Detection

```sql
SELECT * FROM ChangePointDetection (
    ON time_series_data
    PARTITION BY series_id
    ORDER BY time_period
    USING
        ValueColumn('metric_value')
        SegmentationMethod('NORMAL_DISTRIBUTION')
        MaxChangeNum(10)
        Penalty('BIC')
) AS changepoints;
```

---

## Graph Functions

### PageRank

```sql
SELECT * FROM PageRank (
    ON edges_table AS Edges
    ON vertices_table AS Vertices DIMENSION
    USING
        TargetKey('target_id')
        SourceKey('source_id')
        Accumulate('vertex_name')
        DampFactor(0.85)
        MaxIterNum(100)
        Threshold(0.001)
) AS pr;
```

### Shortest Path

```sql
SELECT * FROM AllPairsShortestPath (
    ON edges_table
    USING
        TargetKey('target_id')
        SourceKey('source_id')
        EdgeWeight('weight')
        MaxDistance(10)
) AS sp;
```

### Betweenness Centrality

```sql
SELECT * FROM Betweenness (
    ON edges_table AS Edges
    ON vertices_table AS Vertices DIMENSION
    USING
        TargetKey('target_id')
        SourceKey('source_id')
        Accumulate('vertex_name')
) AS bc;
```

---

## Geometry Functions

### Point in Polygon

```sql
SELECT * FROM PointInPolygon (
    ON points_data AS SourceTable
    ON polygons_data AS ReferenceTable DIMENSION
    USING
        SourceLocationColumn('latitude', 'longitude')
        ReferenceLocationColumn('polygon_wkt')
        ReferenceNameColumns('region_name')
        Accumulate('point_id')
) AS pip;
```
