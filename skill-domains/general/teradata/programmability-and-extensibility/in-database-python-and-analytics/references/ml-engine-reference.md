# ML Engine Function Reference

> **Source:** Teradata Vantage Analytics Database Analytic Functions  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/Analytics-Database-Analytic-Functions  
> **Extraction date:** 2025-07  
> **Topics:** ML Engine Function Reference

## Architecture Overview

The Machine Learning Engine is based on the SQL Map Reduce (SQL-MR) framework, a parallel computing model that processes data through SQL table functions. Functions execute on Kubernetes-managed analytic nodes connected to the SQL Engine via QueryGrid 2.x over InfiniBand.

### Function Types

| Type | Description | Example |
|---|---|---|
| **Row function** | Single-step parallel map task; processes each row independently | Sessionize, TextParser |
| **Partition function** | Two-step reduce; platform partitions data, function acts on each partition | nPath, Attribution |
| **Driver function** | Master task drives iterative logic with child SQL-MR mappers/reducers | KMeans, DecisionTree, GLM |

> Source: TDN0009803 Section 2.1 — Machine Learning and Graph Engine Architecture

### Key Components

- **Queen pod** — master controller; hosts driver processes, JDBC connections, contract negotiation
- **Worker pods** — execute parallel tasks; build In-Memory Analytic Tables (IMATs) for iterative processing
- **ARC** — Aster Relational Compute; lightweight PostgreSQL instance for sorting/grouping within workers
- **ICE** — Inter Cluster Express; data distribution and replication layer between workers

### Execution Flow for Driver Functions

```
Client → SQL Engine PE → Contract (PE ↔ Queen via JDBC)
  → Export (AMPs → Workers via QueryGrid)
  → Workers build IMATs, iterate until convergence
  → Import (Workers → AMPs via QueryGrid)
  → Results returned to client
```

For driver functions with `InputTable`/`OutputTable` arguments:
- **Push model** — tables from `InputTable` arguments exported to analytic nodes (like ON clause tables)
- **Pull model** — table names rewritten to reference SQL Engine; data pulled by analytic nodes during execution
- Primary result returned via outer import; secondary output tables fetched via separate JDBC session

> Source: TDN0009803 Section 3 — Teradata Vantage Execution Flow

## Function Catalog by Category

### Time Series, Path, and Attribution Functions

| Function | Description |
|---|---|
| **ARIMA / ARIMAPredict** | Autoregressive Integrated Moving Average forecasting; AR + differencing + MA components |
| **Attribution** | Credits actions resulting in an event across weight, time, and quantity dimensions |
| **Burst** | Splits time intervals into shorter subintervals; allocates values to new intervals |
| **ChangePointDetection / ChangePointDetectionRT** | Detects change points in stochastic processes or time series |
| **CCMPrepare / CCM** | Convergent cross-mapping for evaluating causal influence between time series variables |
| **DTW** | Dynamic time warping; measures similarity between sequences varying in time/speed |
| **FFT / IFFT** | Fast Fourier Transform and inverse; frequency domain analysis |
| **FrequentPaths** | Identifies frequent paths leading to outcomes (often used with nPath output) |
| **Interpolator** | Calculates missing values in time series via interpolation or aggregation |
| **nPath** | Patented sequential analysis through multi-structured data using regex pattern matching |
| **PathGenerator / PathSummarizer / PathStart / PathAnalyzer** | Clickstream path analysis pipeline |
| **SAX** | Symbolic Aggregation Approximation for large-scale time series classification and motif discovery |
| **SeriesSplitter** | Splits partitions into balanced sub-partitions for time series manipulation |
| **Sessionize** | Maps clicks in a clickstream to unique session identifiers by time window |
| **Shapelet functions** | Time series classification using contiguous subsequences (unsupervised, supervised, classifier) |
| **TimeSeriesOrders** | Automatically determines ARIMA orders (p, d, q) for univariate time series |
| **VARMAX** | Vector autoregressive moving average with exogenous variables for multivariate time series |
| **DWT / DWT2D / IDWT / IDWT2D** | Wavelet transform functions for signal decomposition and compression |

> Source: TDN0009803 Table 2 — Time Series, Path, and Attribution Analysis Functions

### Statistical Analysis Functions

| Function | Description |
|---|---|
| **ApproxCardinality** | Probabilistic counting for approximate count values on large populations |
| **ApproxPercentile** | Approximate percentile computation for large datasets |
| **ConfusionMatrix** | Visualization of supervised learning algorithm performance (predicted vs actual) |
| **Correlation** | Measures strength of association between two variables |
| **CoxPH / CoxHazardRatio / CoxSurvival** | Cox proportional hazards model; hazard ratios and survival probabilities |
| **CrossValidation** | Model validation via partitioned training/test sets |
| **DistributionMatchReduce** | Goodness-of-fit tests (Anderson-Darling, Kolmogorov-Smirnov, Chi-Squared, Cramer-von Mises) |
| **FMeasure** | Hypothesis test accuracy (weighted average of precision and recall) |
| **GLM / GLMPredict / GLM2 / GLML1L2** | Generalized linear models with regularization and factorization |
| **HMM functions** | Hidden Markov Models (unsupervised, supervised, evaluator, decoder) |
| **Histogram** | Frequency distribution with automatic bin width calculation |
| **KNN** | K-Nearest Neighbor classification by majority vote of neighbors |
| **LAR / LARPredict** | Least angle regression with LASSO coefficient constraint for variable selection |
| **LikelihoodRatioTest** | Likelihood ratio test for comparing two GLM models |
| **LinReg / LinRegInternal / LinRegPredict** | Linear regression modeling and prediction |
| **Moving Average functions** | Cumulative, exponential, simple, and weighted moving averages |
| **Percentile** | Exact percentile computation |
| **PCA (PCAMap / PCAReduce / PCAScore)** | Principal component analysis for variable reduction |
| **RandomSample** | Random sampling with basic, KMeans++, and KMeans‖ methods |
| **ROC** | Receiver operating characteristic curve; TPR, FPR, AUC, Gini coefficient |
| **Sampling** | Bernoulli sampling or sampling without replacement; conditional or unconditional |
| **Shapley Value functions** | Computes Shapley values for cooperative game attribution analysis |
| **SVM functions (Sparse and Dense)** | Support vector machine classification for binary data |
| **UnivariateStatistics** | Descriptive statistics: mean, median, variance, skewness, kurtosis, percentiles, etc. |
| **VectorDistance** | Measures similarity between vectors using Euclidean distance or cosine similarity |
| **VWAP** | Volume-weighted average price over a trading horizon |

> Source: TDN0009803 Table 4 — Statistical Analysis Functions

### Text Analysis Functions

| Function | Description |
|---|---|
| **LDA / LDAInference / LDATopicSummary** | Latent Dirichlet Allocation topic modeling |
| **LevenshteinDistance** | Edit distance between strings (insertions, deletions, substitutions) |
| **NaiveBayesTextClassifier** | Text classification into categories using Naive Bayes |
| **NER functions** | Named Entity Recognition using CRF or Max Entropy models (train, extract, evaluate) |
| **nGrams** | Consecutive word sequences for language modeling and text analysis |
| **POSTagger** | Part-of-speech tagging for input text |
| **SentenceExtractor** | Extracts sentences from English text |
| **Sentiment functions** | Sentiment extraction (train, extract, evaluate) using maximum entropy classifier |
| **TextClassifier functions** | Text categorization into categories (train, classify, evaluate) |
| **TextChunker** | Divides text into syntactic phrases (noun, verb, prepositional) |
| **TextMorph** | Lemmatization using WordNet 3.0 dictionary |
| **TextParser** | Tokenizes text, optional stemming, word frequency counts |
| **TextTagger** | Tags documents according to user-defined rules |
| **TextTokenizer** | Extracts tokens from English, Chinese, or Japanese text |
| **TFIDF** | Term frequency–inverse document frequency for word importance |

> Source: TDN0009803 Table 5 — Text Analysis Functions

### Cluster Analysis Functions

| Function | Description |
|---|---|
| **Canopy** | Pre-clustering into overlapping subsets to speed downstream clustering (e.g., KMeans) |
| **GMM / GMMPredict / GMMProfile** | Gaussian Mixture Model clustering with soft assignment; includes DP-GMM variant |
| **KMeans / KMeansPlot** | Partition n observations into k clusters by nearest centroid |
| **KModes / KModesPredict** | Extension of KMeans supporting categorical data |
| **MinHash** | Locality-sensitive hashing for estimating cluster similarity (Jaccard similarity) |

> Source: TDN0009803 Table 6 — Cluster Analysis Functions

### Ensemble Methods (Decision Trees, Forests, Boosting)

| Function | Description |
|---|---|
| **AdaBoost / AdaBoostPredict** | Multiclass boosting combining weak classifiers |
| **DecisionTree / Single_Tree_Predict** | Single classification tree with GINI/entropy/chi-square impurity |
| **DecisionForest / Forest_Predict / DecisionForestEvaluator** | Random forest ensemble with bagging; variable importance evaluation |
| **XGBoost / XGBoostPredict** | Gradient boosting with decision trees; binomial/softmax loss, L2 regularization |

> Source: TDN0009803 Tables 7–8 — Naive Bayes and Ensemble Methods

### Association Analysis Functions

| Function | Description |
|---|---|
| **BasketGenerator** | Generates item subsets connected by common identifiers for market basket analysis |
| **CFilter** | Collaborative filtering with Z-Score threshold for recommendation |
| **FPGrowth** | Frequent Pattern Growth for association rule discovery using FP-Tree structure |
| **Recommender functions** | WSRecommender (weighted-sum) and KNNRecommender (optimized weights) |

> Source: TDN0009803 Table 9 — Association Analysis Functions

### Data Transformation Functions

| Function | Description |
|---|---|
| **AntiSelect** | Select all columns except specified ones |
| **ApacheLogParser** | Parses Apache log file content into structured columns |
| **ConvertToCategorical** | Converts numeric columns to VARCHAR for categorical treatment |
| **FellegiSunter / FellegiSunterPredict** | Record linkage and duplicate detection |
| **GeometryOverlay / PointInPolygon** | Geometric operations (union, intersection, etc.) and point-in-polygon tests |
| **IdentityMatch** | Fuzzy and nominal matching of entity records across data sources |
| **IPGeo** | Maps IP addresses to geographic locations |
| **JSONParser** | Extracts elements from JSON strings |
| **MultiCaseMatch** | Extended CASE matching supporting multiple matches per row |
| **MurmurHash** | Non-cryptographic hash computation for general lookups |
| **OutlierFilter** | Filters outliers using percentile, Tukey, Carling, or MAD methods |
| **Pack / Unpack** | Merges columns into delimited rows / expands packed columns |
| **Pivoting / Unpivoting** | Row-to-column and column-to-row transformations |
| **Scale functions** | Data normalization (ScaleMap, Scale, ScaleSummary, ScaleByPartition) |
| **StringSimilarity** | String similarity via Jaro, Jaro-Winkler, N-Gram, or Levenshtein distance |
| **URIPack / URIUnpack** | Assembles/disassembles hierarchical URIs |
| **XMLParser / XMLRelation** | Extracts data and structure from XML documents |

> Source: TDN0009803 Table 10 — Data Transformation Functions

## Model Training and Scoring Patterns

### Training Pattern (Driver Function)

```sql
-- Train a KMeans model on the ML Engine
SELECT *
FROM KMeans (
  ON (SELECT 1) PARTITION BY 1
  InputTable ('customer_features')
  OutputTable ('kmeans_model')
  NumberK (5)
  CentroidsTable ('initial_centroids')
  Threshold (0.001)
  MaxIterNum (50)
) AS DT;
```

### Scoring on the SQL Engine

```sql
-- Score using the model table created by ML Engine training
SELECT *
FROM DecisionTreePredict (
  ON new_data AS InputTable PARTITION BY ANY
  ON dt_model AS ModelTable DIMENSION
  IdColumn ('customer_id')
  Accumulate ('customer_id', 'region')
) AS DT;
```

### Scoring on the ML Engine

```sql
-- Score on ML Engine using OUT TABLE model
SELECT *
FROM Forest_Predict (
  ON test_data PARTITION BY ANY
  ON forest_model DIMENSION
  IdColumn ('id')
  Detailed ('true')
) AS DT;
```

> Source: TDN0009803 Section 7 — Model Scoring in Teradata Vantage

## SQL Engine Native Functions

The following functions are ported to execute natively as FastPath table operators inside the SQL Engine:

| Function | Category |
|---|---|
| Attribution | Path/Attribution |
| nPath | Path/Pattern |
| Sessionize | Path/Session |
| Time Series Tables & Aggregates | Time Series |
| DecisionTreePredict | Scoring |
| DecisionForestPredict | Scoring |
| GLMPredict | Scoring |
| SVMSparsePredict | Scoring |
| NaiveBayesPredict | Scoring |
| NaiveBayesTextClassifierPredict | Scoring |

These functions execute on the SQL Engine without invoking QueryGrid or analytic nodes. They use table operator syntax with the `USING` keyword and support scalar sub-queries as argument values.

> Source: TDN0009803 Table 1 — SQL Engine Functions

## Configuration and Administration

### Monitoring

- **DBQL** — query-level monitoring; extended for analytic node activity via `TD_Coprocessor_DB.QueryLog`
- **ResUsage** — system-level metrics in `TD_Coprocessor_DB` (Network, CPU, Disk, Memory)
- Query-ID shared between SQL Engine and analytic nodes for cross-engine monitoring joins
- Analytic node monitoring disabled by default; enable with admin privileges
- Queen stores statistics for 3 days by default before purge

### Logging

| Component | Command |
|---|---|
| Queen pod | `kubectl logs queen -c <container> --namespace=<name>` |
| Worker pod | `kubectl logs workerN -c <container> --namespace=<name>` |
| SQL-MR logs | `kubectl logs worker[1-n] runner --namespace=cloud-aster` |
| QueryGrid logs | Available in Viewpoint Completed Queries portlet and QGM Kibana |

### Spoolspace Guidelines

ML Engine functions may require significant spoolspace on the SQL Engine for data export. Ensure adequate spool allocation for users running analytic functions. Refer to Appendix A of TDN0009803 for per-function spoolspace guidelines.

> Source: TDN0009803 Section 5 — Manageability of Teradata Vantage

## Language and Tool Integration

### R — tdplyr Package

- R library providing 50+ functions for data manipulation and Vantage analytic function execution
- Compatible with dplyr/dbplyr verbs; virtual data frames reference SQL Engine tables
- Functions translated to Teradata SQL; executed via ODBC connection
- Works with RStudio and R Console

### Python — teradataml Package

- Python library providing 50+ functions for data management and analytic function execution
- Extends SQLAlchemy with Teradata dialect; provides Pandas-like DataFrame interface
- Lazy evaluation for exploration, transformation, and ML operations
- Compatible with JupyterLab and other Python environments

> Source: TDN0009803 Section 8 — Teradata Vantage Language and Tool Support

## Custom User Defined Functions

### SQL Engine UDFs

| UDF Type | Input | Output | Description |
|---|---|---|---|
| Scalar UDF | Scalar | Scalar | Returns single value; invoked per row (e.g., SUBSTR, ABS) |
| Aggregate UDF | Set | Scalar | Returns single result per group (e.g., SUM, AVG) |
| Table UDF | Scalar | Set | Returns table row-by-row from external sources |
| Table Operator | Set | Set | Polymorphic; supports PARTITION BY/ORDER BY; Map-Reduce style |

### ML Engine UDFs

- Custom UDFs from legacy Aster installations can be migrated and executed on the ML Engine
- Migration process documented in Teradata Vantage User Guide
- Net new custom UDF development on ML Engine not supported in initial release

> Source: TDN0009803 Section 9 — Creating Custom User Defined Functions
