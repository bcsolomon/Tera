---
name: teradata-analytics
description: 'Run R and Python scripts in-database with the SCRIPT Table Operator (STO), and use Teradata Vantage 150+ built-in analytic functions. Use when executing R/Python analytics in the database, installing scripts with SYSUIF, scoring ML models, data preparation (Pivot/Unpivot/Pack/Unpack/Sessionize/Scale/Antiselect), path/pattern analysis (nPath/Attribution), graph analytics (PageRank/Shortest Path), ML (Decision Tree/Forest/GLM/KMeans/KNN/SVM/XGBoost/LASSO/PCA/NaiveBayes), text analytics (NER/Sentiment/LDA/TF-IDF/nGram), time series (ARIMA/Burst/Changepoint), or behavioral economics (Shapley Value).'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Analytics — SCRIPT Table Operator & Analytic Functions

## When to Use

- Executing R or Python scripts inside the Teradata database (SCRIPT Table Operator)
- Installing/managing R/Python scripts on database nodes
- Using 150+ built-in analytic functions (ML, text, graph, time series, path)
- Data preparation: Pivot, Unpivot, Pack, Unpack, Sessionize, Scale, Antiselect
- Path/pattern analysis: nPath, Attribution, FP Growth
- ML model training/scoring: Decision Tree, Random Forest, GLM, KMeans, XGBoost, SVM
- Text analytics: NER, Sentiment, LDA, TF-IDF
- Time series: ARIMA, Changepoint Detection, Burst
- Graph analytics: PageRank, Shortest Path, Betweenness

---

## SCRIPT Table Operator (STO)

### How It Works

The STO executes R/Python/shell scripts on each AMP of the Advanced SQL Engine. Data flows:
1. SQL query feeds rows to the STO via stdin (tab-delimited by default)
2. Script processes rows, writes results to stdout
3. STO captures stdout rows and projects them per the RETURNS clause

### Basic Syntax

```sql
SELECT result_columns
FROM SCRIPT (
    ON { table_name | (subquery) }
    [ PARTITION BY col1[, col2...] | HASH BY col1[, col2...] ]
    [ ORDER BY col1 [ASC|DESC] ]
    SCRIPT_COMMAND('command')
    RETURNS('col1 TYPE1[, col2 TYPE2, ...]')
    [ DELIMITER(',') ]
    [ QUOTECHAR('"') ]
    [ CHARSET('UTF-8') ]
)
AS alias;
```

### Data Distribution

| Clause | Behavior |
|---|---|
| `PARTITION BY col` | Groups by column — all rows with same value go to same AMP |
| `PARTITION BY 1` | All data to a single AMP (use cautiously) |
| `HASH BY col` | Hash-distribute across AMPs |
| No clause | Each AMP processes its local data |

### Script Installation

```sql
-- Grant permissions
GRANT EXECUTE PROCEDURE ON SYSUIF.INSTALL_FILE TO username;
GRANT EXECUTE PROCEDURE ON SYSUIF.REPLACE_FILE TO username;
GRANT EXECUTE PROCEDURE ON SYSUIF.REMOVE_FILE TO username;

-- Set search path
SET SESSION SEARCHUIFDBPATH = myDB;

-- Install script: INSTALL_FILE(alias, filename, 'cz!/path/to/local/file')
CALL SYSUIF.INSTALL_FILE('myscript', 'myscript.py', 'cz!/home/user/myscript.py');

-- Replace script
CALL SYSUIF.REPLACE_FILE('myscript', 'myscript.py', 'cz!/home/user/myscript.py', 1);

-- Remove script
CALL SYSUIF.REMOVE_FILE('myscript', 1);
```

### R Script Example

```sql
-- Set search path first
SET SESSION SEARCHUIFDBPATH = myDB;

-- Execute R script
SELECT *
FROM SCRIPT (
    ON mydb.input_data
    PARTITION BY group_col
    ORDER BY sort_col
    SCRIPT_COMMAND('Rscript --vanilla ./myDB/score_model.r')
    RETURNS('group_id INTEGER, prediction FLOAT, confidence FLOAT')
);
```

### Python Script Example

```sql
SELECT *
FROM SCRIPT (
    ON (SELECT customer_id, feature1, feature2 FROM mydb.features)
    PARTITION BY customer_id
    SCRIPT_COMMAND('python3 ./myDB/predict.py')
    RETURNS('customer_id INTEGER, score FLOAT, label VARCHAR(20)')
);
```

See [SCRIPT Table Operator reference](./references/script-table-operator.md) for R/Python setup, I/O patterns, debugging, and memory management.

---

## Built-in Analytic Functions

Teradata Vantage provides 150+ analytic functions as table operators. All use the same invocation pattern:

```sql
SELECT * FROM FunctionName (
    ON input_table [AS InputRole]
    [ON reference_table AS ReferenceRole]
    [PARTITION BY col | ORDER BY col]
    USING
        Param1('value1')
        Param2('value2')
) AS alias;
```

### Function Categories

| Category | Functions | Use Cases |
|---|---|---|
| **Data Prep** | Antiselect, Pack/Unpack, Pivot/Unpivot, Scale, Sessionize, Sampling | Reshape, normalize, sessionize clickstreams |
| **Path/Pattern** | nPath, Attribution, FP Growth, Path Generator/Summarizer | Clickstream analysis, marketing attribution |
| **ML — Classification** | Decision Tree/Forest, Naïve Bayes, SVM, XGBoost, AdaBoost, KNN | Predict categories |
| **ML — Regression** | GLM, Linear Regression, LASSO/LARS | Predict continuous values |
| **ML — Clustering** | KMeans, KModes, Canopy | Segment customers |
| **ML — Decomposition** | PCA, PCA Score | Dimensionality reduction |
| **Text** | NER, Sentiment, LDA, TF-IDF, nGram, Text Parser/Chunker | NLP, topic modeling |
| **Graph** | PageRank, Shortest Path, Betweenness, Eigenvector, Community | Network analysis |
| **Time Series** | ARIMA, Burst, Changepoint, FFT, VARMAX, Shapelets | Forecasting, anomaly detection |
| **Behavioral** | Shapley Value | Attribution/game theory |
| **Geometry** | Point in Polygon, Geometry Overlay | Geospatial analysis |

### Key Functions — Quick Reference

#### nPath — Pattern Matching on Sequences

```sql
SELECT * FROM nPath (
    ON clickstream_data
    PARTITION BY session_id
    ORDER BY event_time
    USING
        Mode(NONOVERLAPPING)
        Pattern('A+.B+.C')
        Symbols(
            page_type = 'landing' AS A,
            page_type = 'product' AS B,
            page_type = 'checkout' AS C
        )
        Result(
            FIRST(A.session_id) AS session_id,
            FIRST(A.event_time) AS start_time,
            LAST(C.event_time) AS end_time,
            COUNT(B.*) AS products_viewed,
            ACCUMULATE(B.page_name) AS product_pages
        )
) AS paths;
```

#### Attribution — Marketing Channel Attribution

```sql
SELECT * FROM Attribution (
    ON conversion_data
    PARTITION BY user_id
    ORDER BY event_time
    USING
        ConversionEvent('event_type = ''purchase''')
        TimestampColumn('event_time')
        WindowSize('rows:10 & seconds:864000')
        Model1('SEGMENT_ROWS:3', 'EXPONENTIAL:0.5')
) AS attr;
```

#### Decision Tree — Train and Predict

```sql
-- Train
SELECT * FROM DecisionTree (
    ON training_data AS InputTable
    OUT TABLE OutputTable(mydb.dt_model)
    USING
        ResponseColumn('target')
        NumericInputs('age', 'income', 'score')
        CategoricalInputs('region', 'segment')
        TreeType('CLASSIFICATION')
        MaxDepth(10)
        MinNodeSize(50)
) AS dt;

-- Predict
SELECT * FROM SingleTreePredict (
    ON scoring_data AS InputTable
    ON mydb.dt_model AS ModelTable DIMENSION
    USING
        AttrTableGroupByColumns('region', 'segment')
        AttrTablePIDColumns('age', 'income', 'score')
) AS predictions;
```

#### KMeans — Clustering

```sql
SELECT * FROM KMeans (
    ON input_data
    USING
        NumClusters(5)
        MaxIterNum(100)
        Threshold(0.01)
        TargetColumns('feature1', 'feature2', 'feature3')
) AS clusters;
```

#### Sessionize — Clickstream Sessions

```sql
SELECT * FROM Sessionize (
    ON clickstream_data
    PARTITION BY user_id
    ORDER BY event_time
    USING
        TimeColumn('event_time')
        TimeOut(1800)            -- 30 min timeout
) AS sessions;
```

See [Analytic Functions Catalog](./references/analytic-functions-catalog.md) for the complete function list with syntax.

See [ML Functions reference](./references/ml-functions.md) for train/predict patterns for all ML algorithms.

---

## Common Errors and Solutions

| Error | Cause | Fix |
|---|---|---|
| `Error in function SCRIPT: output could not be converted` | RETURNS type mismatch | Check script output matches RETURNS types exactly |
| `SEARCHUIFDBPATH not set` | Missing session config | `SET SESSION SEARCHUIFDBPATH = myDB;` |
| `Script not found` | Wrong path in SCRIPT_COMMAND | Verify script installed with `SYSUIF.INSTALL_FILE` |
| `Memory exceeded` | Script uses too much RAM | Reduce data per partition; check ScriptMemLimit |
| `Analytic function not found` | Missing MLE install | Verify `CALL SYSUIF.INSTALL_FILE` for MLE package |

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-analytics", path="references/FILENAME")` — do NOT call `list`.

- [SCRIPT Table Operator](./references/script-table-operator.md) — Full STO syntax, R/Python setup, I/O, memory, debugging
- [Analytic Functions — Data Prep & Path](./references/analytic-functions-catalog.md) — Data preparation functions (Antiselect, Pack/Unpack, Pivot/Unpivot, Scale, Sessionize, Sampling, Categorize, Outlier Filter) and path/pattern functions (nPath, Attribution, FP Growth, Path Gen/Sum)
- [Analytic Functions — ML, Text, Graph](./references/analytic-functions-ml-text-graph.md) — ML algorithms (DecisionTree/Forest, GLM, KMeans, KNN, SVM, XGBoost, LinReg, LASSO, PCA, NaiveBayes, AdaBoost), text analytics (NER, Sentiment, LDA, TF-IDF, nGram), time series (ARIMA, Burst, Changepoint), graph (PageRank, ShortestPath, Betweenness), geometry (PointInPolygon)
- [ML Functions](./references/ml-functions.md) — Train/predict patterns for all ML algorithms
- [STO Advanced Topics](./references/sto-advanced-topics.md) — Multi-model fitting/scoring, Map-Reduce parallelization, CALCMATRIX interaction, memory management (ScriptMemLimit), CPU/concurrency TASM setup, R/Python package installation, tdplyr/teradataml Script() integration, STO Sandbox
