# Teradata SQL Syntax Reference — Topic Index

Use [<name>.md](./references/<name>.md) to load any topic below.

> **Always prefer native Teradata functions over hand-written SQL.** Before writing analytics, transformation, ML, or search SQL, see [guidelines.md](guidelines.md) to see the canonical mapping of common operations to native functions. Native table operators run distributed across all AMPs and outperform equivalent manual SQL.
>
> **Minimize data movement.** Teradata tables can contain billions of rows. Never SELECT raw data to the agent for processing — use native functions that summarize and compute in-database. Chain pipeline steps as CTEs. Persist large outputs with OUT TABLE. Return results, not data.

## Start Here
| Topic | Description |
|-------|-------------|
| `guidelines` | **Native functions first** — canonical mapping of common SQL patterns to native Teradata functions; when to use each |

## Core SQL
| Topic | Description |
|-------|-------------|
| `sql-basics` | SELECT syntax, TOP N, SAMPLE, QUALIFY, CTEs, joins |
| `data-types-casting` | Data types, CAST / type conversion patterns, VECTOR and Vector32 embedding types |
| `core-scalar-functions` | CASE, COALESCE, NULLIFZERO, ZEROIFNULL, NULLIF; string functions (SUBSTR, INDEX, OREPLACE, TRIM); numeric functions (ROUND, MOD, LOG, ABS) |

## Functions
| Topic | Description |
|-------|-------------|
| `bit-byte-functions` | Bit/byte manipulation: BITAND, BITOR, BITXOR, BITNOT, SHIFTLEFT/RIGHT, ROTATELEFT/RIGHT, GETBIT, SETBIT, COUNTSET, SUBBITSTR, TO_BYTE |
| `json-functions` | JSON data type, DDL, storage formats (text/BSON/UBJSON), extraction (JSONExtractValue, JSONExtract, dot notation, JSONPath), validation, publishing (JSON_AGG, JSON_COMPOSE, JSON_PUBLISH), shredding (INSERT JSON, JSON_TABLE, TD_JSONSHRED, JSON_SHRED_BATCH), inspection, and conversion |
| `sql-functions` | Date/time literals, arithmetic, formatting, EXTRACT; aggregate functions (GROUP BY, COUNT, SUM, AVG, percentiles, GROUPING SETS); window functions (ROW_NUMBER, RANK, LAG/LEAD, running totals, QUALIFY) |

## Analytics & ML
| Topic | Description |
|-------|-------------|
| `guidelines` | Reusable two-phase Fit/Transform pattern; canonical mapping of common SQL patterns to native Teradata functions |
| `ml-functions-linear` | Linear models: TD_GLM, TD_LogReg, TD_SVM, scoring |
| `ml-functions-ensemble` | Ensemble and instance-based: TD_XGBoost, TD_DecisionForest, TD_KNN, scoring |
| `data-exploration` | Descriptive stats, sampling, histogram, correlation, MovingAverage, TD_UnivariateStatistics, TD_Histogram, TD_QQNorm |
| `data-cleaning` | NULL handling, deduplication, string cleaning, outlier detection, type validation |
| `data-prep-scaling` | Feature scaling and normalization: TD_ScaleFit/Transform, TD_RowNormalizeFit/Transform |
| `data-prep-encoding` | Categorical encoding: TD_OneHotEncodingFit/Transform, TD_OrdinalEncodingFit/Transform, TD_TargetEncodingFit/Transform |
| `data-prep-imbalance` | Class imbalance handling: TD_SMOTE oversampling, TD_NonLinearCombineFit/Transform |
| `utility-functions` | TD_FillRowID, TD_NumApply, TD_RoundColumns, TD_StrApply |
| `text-analytics` | Text tokenization, classification, and entity extraction: TD_NgramSplitter, TD_NaiveBayesTextClassifier, TD_NERExtractor |
| `hypothesis-testing` | Statistical hypothesis tests: TD_ANOVA, TD_ChiSq, TD_FTest, TD_ZTest |
| `ml-unsupervised` | Clustering (TD_KMeans, TD_OneClassSVM), frequent itemsets (TD_Apriori), collaborative filtering (TD_CFilter) |
| `path-analysis` | Event sequence analysis: Attribution, Sessionize, nPath |
| `model-evaluation` | Model evaluation and explainability: TD_TrainTestSplit, TD_ClassificationEvaluator, TD_RegressionEvaluator, TD_ROC, TD_Silhouette, TD_SHAP |
| `ml-patterns` | End-to-end ML pipeline patterns: CTE prediction pipeline, elbow method, train/evaluate/retrain loop, class imbalance workflow, micromodeling |
| `ml-pipeline-procedures` | Step-by-step KMeans pipeline recipes, batch scoring, centroid extraction |
| `training-dataset-assembly` | Hybrid-source training dataset workflow: discovery, join validation, materialization, boundary rules |
| `vector-search` | Vector similarity search: TD_VectorDistance (exact), TD_HNSW/TD_HNSWPredict (approximate), KMeans IVF pattern |
| `embeddings` | Embedding generation: AI_TextEmbeddings (cloud/NIM REST), ONNXEmbeddings (in-database BYOM), TD_WordEmbeddings; store → normalize → index → search pipeline |
| `ai-text-analytics` | LLM-powered text analytics: AI_AnalyzeSentiment, AI_AskLLM, AI_DetectLanguage, AI_ExtractKeyPhrases, AI_MaskPII, AI_RecognizeEntities, AI_RecognizePIIEntities, AI_TextClassifier, AI_TextSummarize, AI_TextTranslate |

## Unbounded Array Framework (UAF)
| Topic | Description |
|-------|-------------|
| `uaf-concepts` | **Start here for UAF** — SERIES_SPEC, MATRIX_SPEC, ART_SPEC, GENSERIES_SPEC, EXECUTE FUNCTION INTO ART, ART layers, TD_EXTRACT_RESULTS |
| `uaf-utility` | UAF general utility functions: TD_CONVERTTABLEFORUAF, TD_COPYART, TD_SINFO, TD_MINFO, TD_ISFINITE/ISINF/ISNAN, TD_INPUTVALIDATOR, TD_PLOT, TD_IMAGE2MATRIX, TD_MATRIX2IMAGE, TD_TRACKINGOP, TD_FILTERFACTORY1D |
| `uaf-data-prep` | UAF data preparation and anomaly detection: TD_RESAMPLE, TD_BINARYSERIESOP, TD_BINARYMATRIXOP, TD_GENSERIES4FORMULA, TD_MATRIXMULTIPLY, TD_IQR |
| `uaf-estimation-prep` | UAF estimation preparation: TD_ACF, TD_PACF, TD_DIFF, TD_UNDIFF, TD_SEASONALNORMALIZE, TD_UNNORMALIZE, TD_POWERTRANSFORM, TD_SMOOTHMA |
| `uaf-estimation-arima` | ARIMA estimation and validation: TD_ARIMAESTIMATE, TD_ARIMAVALIDATE, TD_AUTOARIMA |
| `uaf-estimation-regression` | UAF regression: TD_LINEAR_REGR, TD_MULTIVAR_REGR |
| `uaf-forecasting` | UAF series forecasting: TD_ARIMAFORECAST, TD_HOLT_WINTERS_FORECASTER, TD_MAMEAN, TD_SIMPLEEXP, TD_DTW |
| `uaf-diagnostics` | UAF diagnostic statistical tests: TD_DICKEY_FULLER, TD_DURBIN_WATSON, TD_BREUSCH_GODFREY, TD_BREUSCH_PAGAN_GODFREY, TD_WHITES_GENERAL, TD_GOLDFELD_QUANDT, TD_PORTMAN, TD_FITMETRICS, TD_SELECTION_CRITERIA, TD_CUMUL_PERIODOGRAM, TD_SIGNIF_PERIODICITIES, TD_SIGNIF_RESIDMEAN |
| `uaf-dsp-wavelets` | UAF digital signal processing: TD_DFFT/DFFT2, TD_IDFFT/IDFFT2, TD_DFFTCONV/DFFT2CONV, TD_CONVOLVE/CONVOLVE2, TD_DWT/DWT2D, TD_IDWT/IDWT2D, TD_POWERSPEC, TD_LINESPEC, TD_GENSERIES4SINUSOIDS, TD_SAX, TD_WINDOWDFFT |
| `uaf-fundamentals` | UAF formula syntax: operators, precedence, math and trigonometric functions, FFT/DFT fundamentals, variable naming conventions for FORMULA(...) parameters |

## Geospatial
| Topic | Description |
|-------|-------------|
| `geospatial-types` | ST_Geometry types, MBR/MBB, WKT/WKB formats, spatial DDL |
| `geospatial-analysis` | Spatial relationships (ST_Within, ST_Contains, ST_Distance), geospatial indexes, tessellation, AggGeom, GeometryToRows, PolygonSplit, MGRS conversion, SYSSPATIAL metadata |

## External Data
| Topic | Description |
|-------|-------------|
| `open-table-format-setup` | REPLACE AUTHORIZATION, REPLACE DATALAKE, IAM roles, ALTER DATALAKE, DBC.DataLakesV |
| `open-table-format-query` | Three-part naming, HELP DATALAKE/DATABASE/TABLE, time travel, DML, COLLECT STATS on OTF |
| `open-table-format-admin` | AWS Glue, Hive Metastore, Polaris, Unity Catalog, Lake Formation, BigLake, OAuth |
| `open-table-format-reference` | Iceberg v2/Delta v3 versions, type mappings, TLS 1.2, OTF stats, compression, retention |
| `object-store-read` | READ_NOS for ad-hoc reads and schema discovery, CREATE FOREIGN TABLE for persistent access; Parquet/CSV/JSON; PATHPATTERN partition pruning |
| `object-store-write` | WRITE_NOS export to S3/Azure/GCS in Parquet/CSV/JSON |

## Reference
| Topic | Description |
|-------|-------------|
| `catalog-views` | DBC.* system views for schema discovery |
| `query-tuning` | EXPLAIN, PI design, collect stats, query rewrite tips |
| `authorization-objects` | CREATE/REPLACE/GRANT authorization objects for external service credentials (AI functions, external procedures) |
| `llm-providers` | LLM provider argument blocks for AI functions — Azure, AWS Bedrock, GCP, NVIDIA NIM, LiteLLM |
| `byom-model-loading` | Loading PMML, H2O MOJO, ONNX, Dataiku, DataRobot, and MLeap models into Teradata BYOM tables; conversion workflow for ONNX embedding models |
| `byom-scoring` | BYOM scoring: PMMLPredict, H2OPredict, ONNXPredict, DataikuPredict, DataRobotPredict, MLeapPredict; NLP transformers: ONNXSeq2Seq, ONNXClassification |

---

## Workflows — Start Here for Common Use Cases

Recommended topic reading order for common end-to-end tasks. Load these topics in sequence for full context.

| Use Case | Topic sequence |
|----------|---------------|
| **Classification (fraud, churn, risk)** | `data-exploration` → `data-cleaning` → `data-prep-scaling` → `data-prep-encoding` → `guidelines` → `ml-functions-linear` → `model-evaluation` → `ml-patterns` |
| **Regression (price, demand, forecast)** | `data-exploration` → `data-cleaning` → `data-prep-scaling` → `ml-functions-linear` → `model-evaluation` → `ml-patterns` |
| **Clustering (segmentation)** | `data-exploration` → `data-prep-scaling` → `ml-unsupervised` → `ml-patterns` (elbow method) → `model-evaluation` (Silhouette) |
| **Operationalize a trained model** | `guidelines` → `ml-patterns` (CTE prediction pipeline) |
| **Text classification / NLP** | `data-cleaning` → `text-analytics` → `model-evaluation` |
| **LLM-powered text analytics** | `authorization-objects` → `llm-providers` → `ai-text-analytics` |
| **PII detection / masking** | `authorization-objects` → `llm-providers` → `ai-text-analytics` (AI_MaskPII, AI_RecognizePIIEntities) |
| **Imbalanced classes** | `data-prep-imbalance` (TD_SMOTE) → `ml-patterns` (class imbalance workflow) → `model-evaluation` |
| **Micromodeling (per-segment models)** | `ml-functions-linear` (TD_GLM) → `ml-patterns` (micromodeling) |
| **Semantic search / RAG embeddings** | `authorization-objects` → `llm-providers` → `embeddings` → `vector-search` |
| **In-database ONNX inference** | `byom-model-loading` → `embeddings` (ONNXEmbeddings) → `vector-search` |
| **Query Iceberg / Delta Lake tables** | `open-table-format-setup` → `open-table-format-query` |
| **Import NOS data into Vantage** | `object-store-read` (foreign table → CAST view → permanent table) |
| **Export Vantage data to S3/Azure/GCS** | `object-store-write` (WRITE_NOS) |
| **Time series forecasting (ARIMA)** | `uaf-concepts` → `uaf-data-prep` → `uaf-estimation-prep` → `uaf-estimation-arima` → `uaf-forecasting` → `uaf-diagnostics` |
| **Regression on ordered series** | `uaf-concepts` → `uaf-data-prep` → `uaf-estimation-regression` (TD_LINEAR_REGR / TD_MULTIVAR_REGR) → `uaf-diagnostics` |
| **Frequency / spectral analysis** | `uaf-concepts` → `uaf-dsp-wavelets` (TD_DFFT, TD_POWERSPEC, TD_LINESPEC) |
| **Digital signal filtering** | `uaf-concepts` → `uaf-utility` (TD_FILTERFACTORY1D) → `uaf-dsp-wavelets` (TD_CONVOLVE) |
| **Training dataset from hybrid sources** | `training-dataset-assembly` → `data-exploration` → `data-cleaning` |
| **KMeans pipeline (step-by-step)** | `ml-pipeline-procedures` → `ml-unsupervised` → `model-evaluation` |

---
> **Adding topics:** Drop a new `.md` file into `src/tdsql_mcp/syntax/` and it appears here
> automatically — no code changes needed.
