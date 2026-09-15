---
name: teradata-ml-graph-engines
description: 'Use Teradata ML Engine, Graph Engine, and Function Framework Engine (FFE) for in-database machine learning, graph analytics, and function aliasing. Use when running ML model training or scoring in Vantage, performing graph traversals or community detection, configuring function aliases for analytic functions, or integrating external ML frameworks with Teradata.'
metadata:
  author: teradata-expert
  version: "1.0"
---

# Teradata ML Engine, Graph Engine, and Function Aliasing

## When to Use

- Running ML model training (Decision Trees, KMeans, GLM, XGBoost, etc.) in Vantage
- Scoring ML models on the SQL Engine or Machine Learning Engine
- Performing graph analytics (PageRank, shortest path, community detection)
- Configuring function aliases to simplify remote analytic function invocation
- Using time series, path analytics, text analytics, or statistical functions
- Integrating R (tdplyr) or Python (teradataml) with Vantage analytic functions
- Managing workload priorities for ML/Graph Engine analytic workloads
- Monitoring analytic function execution across SQL and analytic nodes

## Core Concepts

### Vantage Analytic Engines Overview

Teradata Vantage delivers analytics through three integrated engines:

| Engine | Description | Execution Location |
|---|---|---|
| **SQL Engine** | World-class Teradata Database with embedded analytic functions | SQL Engine nodes (AMPs) |
| **Machine Learning Engine** | 100+ prebuilt analytic functions via SQL-MR framework | Analytic nodes (Kubernetes) |
| **Graph Engine** | Graph analytics using Bulk Synchronous Processing (BSP) | Analytic nodes (Kubernetes) |

> Source: TDN0009803 Section 2 — Teradata Vantage Architecture

### Architecture: SQL-MR Framework

The ML and Graph Engines are based on the **SQL Map Reduce (SQL-MR)** framework — a parallel computing model for processing data through a SQL table function interface:

- **Row functions** — single-step parallel map tasks; each task processes its data subset independently, producing zero, one, or more output rows per input row
- **Partition functions** — two-step reduce tasks; platform distributes/groups data by partitioning key via ICE, ARC sorts/groups rows, then function acts on each partition
- **Driver functions** — master task drives iterative logic, invoking child SQL-MR mappers/reducers via JDBC connection back to Queen until convergence (e.g., KMeans, DecisionTree training)
- **Graph functions** — Bulk Synchronous Processing model; loads graph edge/node data into memory, iterates with global synchronization barriers, messages sent between vertices via ICE

Key internal components:
- **ARC** (Aster Relational Compute) — lightweight PostgreSQL instance for sorting/grouping on workers
- **ICE** (Inter Cluster Express) — data distribution and replication layer between workers
- **IMAT** (In-Memory Analytic Table) — temporary storage on workers for iterative model building

> Source: TDN0009803 Section 2.1 — Machine Learning and Graph Engine Architecture

### Analytic Nodes

ML and Graph Engines run on **Kubernetes-managed analytic nodes** connected to SQL Engine nodes via QueryGrid 2.x over InfiniBand:

- **Isolation** — analytic workloads run on separate hardware/software, protecting SQL Engine SLAs
- **Independent scaling** — analytic nodes hold no permanent data; scale up/down without data movement
- **Container orchestration** — Kubernetes manages pods (Queen + Workers) for engine deployment
- **Queen pod** — controls function execution, contract negotiation, monitoring
- **Worker pods** — execute parallel map/reduce/graph tasks, hold In-Memory Analytic Tables (IMATs)

### Foreign Function Execution Flow

When a client submits a query containing an ML or Graph Engine function:

1. SQL Engine parsing engine identifies the foreign function and rewrites as export + import operators
2. Contract phase — PE negotiates output schema with Queen pod via JDBC (polymorphic resolution)
3. Export phase — AMPs send input data to Worker pods over QueryGrid fabric
4. Workers build IMATs, iterate over data until convergence
5. Import phase — Workers return results to SQL Engine over QueryGrid fabric
6. Results returned to caller; only one AWT remains locked during remote execution

> Source: TDN0009803 Section 3 — Teradata Vantage Execution Flow

### Function Invocation Syntax

**Table operator syntax (SQL Engine):**

```sql
SELECT *
FROM FunctionName (
  ON input_table USING PARTITION BY col1 ORDER BY col2
  ON ref_table USING PARTITION BY DIMENSION
  argument_1 ('value_1')
  argument_2 ('value_2')
) AS DT;
```

**Driver function syntax (iterative ML algorithms):**

```sql
SELECT *
FROM KMeans (
  ON (SELECT 1) PARTITION BY 1
  InputTable ('data_points')
  OutputTable ('kmeans_model')
  NumberK (50)
  Threshold (0.001)
  MaxIterNum (20)
) AS DT;
```

**Graph function syntax:**

```sql
SELECT *
FROM PageRank (
  ON vertices_table AS vertices PARTITION BY vertex_key
  ON edges_table AS edges PARTITION BY source_vertex_key
  TargetKey ('target_vertex')
  MaxIterNum (25)
) AS DT;
```

### Function Aliasing (FFE)

Function aliases simplify remote function invocation by hiding the `@COPROCESSOR` reference:

- Without alias: `SELECT * FROM sessionize@COPROCESSOR (...)`
- With alias: `SELECT * FROM sessionize (...)`

Key details:

- Vantage ships with **prebuilt aliases** for all ML/Graph Engine functions except those ported to the SQL Engine
- Aliases resolved via search path: user default database → SYSLIB → TD_SYSFNLIB
- DDL: `CREATE FUNCTION MAPPING`, `DROP FUNCTION MAPPING`, `REPLACE FUNCTION MAPPING`
- Functions coexisting in both engines (Attribution, nPath, Sessionize, scoring functions) execute on SQL Engine by default
- To force execution on analytics nodes, use explicit `FUNCTION_NAME@COPROCESSOR` syntax
- `nPath` and `nTree` do not support aliases and always require `@COPROCESSOR` syntax

```sql
-- Create a function alias
CREATE FUNCTION MAPPING my_analytics_fn
FOR remote_function_name
SERVER coprocessor;

-- Grant execute on the alias
GRANT EXECUTE FUNCTION ON my_analytics_fn TO analytics_user;
```

Data dictionary views: `FunctionAliasV`, `FunctionAliasVX`, `FunctionAliasInfoV`, `FunctionAliasInfoVX`

> Source: TDN0009803 Section 4.4 — Foreign Function Aliasing

## ML Engine Function Categories

The ML Engine provides 100+ prebuilt analytic functions across these categories:

| Category | Key Functions | Use Cases |
|---|---|---|
| **Time Series & Path** | ARIMA, nPath, Sessionize, Attribution, DTW, SAX, Wavelets | Forecasting, clickstream analysis, behavioral analytics |
| **Statistical Analysis** | GLM, SVM, PCA, Correlation, KNN, LinReg, HMM, ROC | Regression, classification, dimensionality reduction |
| **Text Analytics** | LDA, NER, Sentiment, TFIDF, nGrams, TextClassifier | Topic modeling, entity extraction, sentiment analysis |
| **Clustering** | KMeans, KModes, GMM, Canopy, MinHash | Customer segmentation, anomaly detection |
| **Ensemble Methods** | DecisionTree, DecisionForest, XGBoost, AdaBoost | Classification, prediction with boosting/bagging |
| **Association Analysis** | FPGrowth, CFilter, Recommenders, BasketGenerator | Market basket, recommendation engines |
| **Data Transformation** | Scale, Pack/Unpack, Pivot, OutlierFilter, JSONParser | Data preparation, normalization, parsing |

> Source: TDN0009803 Section 4.2 — Machine Learning Analytic Functions

## Graph Engine Functions

The Graph Engine provides functions for network analysis using BSP:

| Category | Functions | Use Cases |
|---|---|---|
| **Centrality** | PageRank, Betweenness, Closeness, EigenVectorCentrality | Influence analysis, node importance |
| **Path/Traversal** | AllPairsShortestPath, GTree, nTree | Route optimization, cascade analysis |
| **Community** | Modularity, LocalClusteringCoefficient, LoopyBeliefPropagation | Fraud rings, social communities |
| **Ranking** | PSALSA, RandomWalkSample | Search relevance, graph sampling |

> Source: TDN0009803 Section 4.3 — Graph Engine Analytic Functions

## Model Scoring

Models can be scored on either engine:

| ML Engine Training Function | SQL Engine Scoring Function |
|---|---|
| DecisionTree | DecisionTreePredict |
| DecisionForest | DecisionForestPredict |
| GLM | GLMPredict |
| SVMSparse | SVMSparsePredict |
| NaiveBayes | NaiveBayesPredict |
| NaiveBayesTextClassifier | NaiveBayesTextClassifierPredict |

- Model tables created via `OUT TABLE` argument are stored on the SQL Engine
- File-based models (NERTrainer, SentimentTrainer, TextClassifierTrainer) stored on analytic node Linux filesystem
- Any ML Engine model can also be scored on the ML Engine itself

> Source: TDN0009803 Section 7 — Model Scoring in Teradata Vantage

## Workload Management for Analytic Functions

- **QGLimit system throttle** — limits concurrent ML/Graph Engine requests (default: 10)
- ML Engine internal limit: 32 total active functions (including child functions spawned by drivers)
- Priority coordination: SQL Engine workload name passed to ML Engine via QueryGrid; mapped to service classes (HighClass/DefaultClass/LowClass/DenyClass)
- **DenyClass** activates when analytic node disk usage exceeds 80%, blocking all work except DROP/TRUNCATE
- In-database analytic functions consume significant CPU — use throttles with low concurrency limits

> Source: TDN0009803 Section 6 — Workload Management in Teradata Vantage

## Monitoring Analytic Workloads

- **DBQL QueryLog** — query-level metrics exported from Queen to `TD_Coprocessor_DB.QueryLog` on SQL Engine
- **ResUsage tables** — system-level metrics in `TD_Coprocessor_DB.ResUsageNetwork`, `ResUsageCpu`, `ResUsageDisk`, `ResUsageMemory`
- Query-ID passed from SQL Engine to analytic nodes enables cross-engine join of monitoring data
- Monitoring disabled by default on analytic nodes; enable via admin privileges
- Queen logs: `kubectl logs queen -c <container> --namespace=<name>`
- Worker logs: `kubectl logs workerN -c <container> --namespace=<name>`
- Statistics purged from Queen after 3 days by default; export to SQL Engine for persistence
- Use `QGExecuteForeignQuery()` to move metrics from analytics nodes to SQL Engine (runs every 24 hours by default)

> Source: TDN0009803 Section 5 — Manageability of Teradata Vantage

## Nondeterministic Results

Some functions produce different results across runs due to:

- Random algorithm components (DecisionForest, RandomSample, Canopy) — use `seed` argument for repeatability
- Nondeterministic data transfer order between SQL Engine and analytic nodes — use `ORDER BY` after `PARTITION BY` or `SequenceInputBy` argument

> Source: TDN0009803 Section 7.3 — Nondeterministic Results

## Security for Analytic Functions

- SQL Engine provides authentication/authorization for the Vantage platform
- Supported methods: TD2, LDAP, Kerberos
- GRANT/REVOKE privileges on function aliases to control analytic function access
- Data encrypted in transit over QueryGrid InfiniBand fabric
- Analytic node OS hardened per CIS/DISA STIG standards
- File-based models (NERTrainer, SentimentTrainer) stored per-user on analytic node Linux filesystem

> Source: TDN0009803 Section 10 — Security in Teradata Vantage

## Troubleshooting

| Symptom | Cause | Resolution |
|---|---|---|
| "Admission Denied" error | DenyClass activated (disk >80%) | Wait for cleanup daemon; DROP/TRUNCATE unneeded tables |
| Function not found | Missing alias or wrong search path | Check SYSLIB for alias; use explicit `@COPROCESSOR` syntax |
| Slow analytic function | Data redistribution overhead | Check input data size; consider in-database scoring if available |
| Different results across runs | Nondeterministic data transfer | Add `ORDER BY` clause or `SequenceInputBy` argument |
| High SQL Engine CPU during analytics | In-database function execution | Apply TASM throttles; limit concurrency to low single digits |
| JVM startup latency | Kubernetes container cold start | Expected overhead; plan for latency in tactical workloads |

## Language and Tool Integration

- **R** — `tdplyr` package: R interface to Vantage analytic functions via ODBC; compatible with dplyr/dbplyr verbs
- **Python** — `teradataml` package: Python interface via SQLAlchemy dialect; Pandas-like DataFrame abstraction
- **Workbenches** — Teradata Studio, JupyterLab, RStudio, Teradata AppCenter

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-ml-graph-engines", path="references/FILENAME")` — do NOT call `list`.

- [ML Engine Function Catalog](references/ml-engine-reference.md) — complete function listing by category
- [Graph Engine and FFE Reference](references/graph-engine-and-ffe.md) — graph functions, FFE details, administration
