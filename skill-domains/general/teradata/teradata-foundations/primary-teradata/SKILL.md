---
name: primary-teradata
description: >
  Provide comprehensive Teradata SQL syntax, native function usage, analytics patterns,
  ML pipelines, UAF time-series operations, geospatial queries, external data access,
  and data movement best practices. Use when generating or explaining Teradata-specific
  SQL including Vantage analytic functions, BYOM scoring, vector search, LLM integration,
  Open Table Format queries, or Native Object Store operations.
metadata:
  author: teradata
  version: "1.0"
---

# Primary Teradata SQL Reference

Comprehensive syntax and pattern reference for Teradata Vantage SQL — covering core SQL,
native analytic functions, machine learning pipelines, time-series analysis (UAF),
geospatial operations, external data formats (Iceberg/Delta/NOS), and LLM/AI integrations.

## When to Use

- Writing or reviewing **any Teradata SQL** (DDL, DML, analytics, ML)
- Generating queries that use **Vantage native table operators** (TD_*, AI_*, ST_*)
- Building **ML pipelines** (fit/transform, scoring, evaluation, micromodeling)
- Working with **UAF time-series** functions (ARIMA, DSP, forecasting)
- Querying **external data** (Iceberg, Delta Lake, NOS foreign tables)
- Implementing **vector search** or **semantic embeddings**
- Using **BYOM** for model loading and scoring (ONNX, PMML, H2O)
- Calling **AI functions** (sentiment, NER, summarization, translation)
- Optimizing queries (EXPLAIN plans, PI design, statistics collection)
- Working with **geospatial** data types and spatial functions

## Core Concepts

### Native Functions First

Teradata Vantage has built-in distributed table operators for analytics, ML, data
preparation, and search. These run across all AMPs in parallel and must always be
preferred over hand-written equivalents. See [guidelines.md](./references/guidelines.md).

### Minimize Data Movement

Teradata tables contain billions of rows. Never SELECT raw data to the agent — use
native functions that summarize and compute in-database. Chain pipeline steps as CTEs.
Use `TOP N` or `SAMPLE` when exploring. Return results, not data.

### Fit/Transform Pattern

Many Vantage ML and data-prep functions use a two-phase pattern:
1. **Fit** — learn parameters from training data (produces a model artifact)
2. **Transform** — apply learned parameters to new data

### SQL Conventions

- Use `PARTITION BY` / `ORDER BY` / `HASH BY` clauses in table operators
- Chain analytics as CTEs for multi-step pipelines
- Use `QUALIFY` for window-function filtering (Teradata extension)
- Persist large intermediate results with `CREATE TABLE ... AS`

## Tool Usage (Proxy Gateway)

Teradata is accessed through a **proxy MCP server with six gateway tools**, NOT
native tool names. Native names (`base_readQuery`, `execute_sql`, `base_tableList`,
`base_databaseList`, `base_columnDescription`, …) are **not directly callable** —
run them *through* `teradata_tool_call`.

**The six gateways:**
`teradata_tool_help`, `teradata_list_patterns`, `teradata_search_tools`,
`teradata_get_tool_schema`, `teradata_tool_call`, `teradata_cleanup_jobs`.

**How to run any Teradata operation:**

```
teradata_tool_call(input={"name": "base_readQuery", "parameters": {"query": "SELECT ..."}})
teradata_tool_call(input={"name": "execute_sql",    "parameters": {"query": "CREATE TABLE ..."}})
```

**Rules:**
- **SELECT / catalog reads → `base_readQuery`** (read-only, rejects DDL/DML).
- **DDL / DML → `execute_sql`** — the ONLY tool for `CREATE`/`GRANT`/`DROP`/`ALTER`.
  Do NOT try `base_writeQuery` or `base_executeQuery` — they are not valid.
- **Discovering tools:** `teradata_search_tools(pattern="<group-name>")` — pattern
  must fullmatch a group/tool name. Use `teradata_list_patterns()` to see valid names.
- **Async results:** most calls return `job_id` with `status:QUEUED`. Poll with
  `teradata_tool_call(job_id="<uuid>")` until `status:COMPLETED`; paginate with
  `offset=` when `has_more:true`. Force sync with `"long_running": false`.
- **Strip-prefix rule:** if a native name has a wrapper prefix (e.g.
  `mcp_td_mcp_base_readQuery`), remove only the wrapper → `base_readQuery`.
- If `teradata_tool_call` reports `tool not found ... dynamic registration failed`,
  re-issue the same call once — the gateway just needs activation.

**Other useful native tools** (all via `teradata_tool_call`): `base_databaseList`,
`base_tableList`, `base_columnDescription`, `base_tableDDL`, `base_tablePreview`.

## Reference File Protocol (MANDATORY)

This skill ships reference files containing syntax details, pipeline patterns, and
function signatures. **You MUST read them before writing SQL or doing tool discovery.**

**Tool:** `skill_resource_read`

**Path format:** All paths use the `references/` prefix. Example: `references/guidelines.md`

**Read the relevant reference(s) for the task — use exact paths from the manifest below:**
```
skill_resource_read(action="read", skill="primary-teradata", path="references/guidelines.md")
skill_resource_read(action="read", skill="primary-teradata", path="references/ml-patterns.md")
skill_resource_read(action="read", skill="primary-teradata", path="references/json-functions.md")
```

**Rules:**
- **Paths ALWAYS start with `references/`** — bare filenames will fail.
- **ALWAYS** read `references/guidelines.md` before any SQL generation — it contains
  the canonical function mappings and "native functions first" rules.
- **Read the domain-specific reference** before writing SQL — use the exact path from
  the Resource Manifest below (e.g. `references/ml-patterns.md` for ML pipelines,
  `references/uaf-estimation-arima.md` for time-series, `references/vector-search.md`
  for embeddings).
- Reference files contain the **correct syntax** — use them instead of guessing
  from `teradata_search_tools` or `teradata_tool_help` alone.
- If a reference file shows a native function (e.g. `TD_TrainTestSplit`), use that
  function — do NOT substitute hand-written alternatives like `MOD(HASHROW(...))`.
- **Do NOT call `skill_resource_read(action="list")`** — the manifest below has all paths.
  Only use `list` if you suspect a new reference was added after this skill was authored.

## Resource Manifest

All references for `primary-teradata` with exact paths for `skill_resource_read`:

| Topic | Path |
|-------|------|
| **Start here** | `references/index.md` |
| Guidelines & rules | `references/guidelines.md` |
| **Core SQL** | |
| SQL basics | `references/sql-basics.md` |
| Data types & casting | `references/data-types-casting.md` |
| Core scalar functions | `references/core-scalar-functions.md` |
| SQL functions (date/agg/window) | `references/sql-functions.md` |
| Bit/byte functions | `references/bit-byte-functions.md` |
| JSON functions | `references/json-functions.md` |
| Utility functions | `references/utility-functions.md` |
| **Data Preparation** | |
| Data exploration | `references/data-exploration.md` |
| Data cleaning | `references/data-cleaning.md` |
| Scaling & normalization | `references/data-prep-scaling.md` |
| Categorical encoding | `references/data-prep-encoding.md` |
| Imbalance handling (SMOTE) | `references/data-prep-imbalance.md` |
| Training dataset assembly | `references/training-dataset-assembly.md` |
| **Machine Learning** | |
| Linear models (GLM, SVM) | `references/ml-functions-linear.md` |
| Ensemble (XGBoost, Forest) | `references/ml-functions-ensemble.md` |
| Unsupervised (KMeans, CFilter) | `references/ml-unsupervised.md` |
| ML pipeline patterns | `references/ml-patterns.md` |
| Pipeline procedures (KMeans) | `references/ml-pipeline-procedures.md` |
| Model evaluation | `references/model-evaluation.md` |
| Hypothesis testing | `references/hypothesis-testing.md` |
| **Text & NLP** | |
| Text analytics | `references/text-analytics.md` |
| AI text analytics (LLM) | `references/ai-text-analytics.md` |
| Path analysis (nPath) | `references/path-analysis.md` |
| **Vector & Embeddings** | |
| Vector search | `references/vector-search.md` |
| Embeddings | `references/embeddings.md` |
| **UAF (Time-Series)** | |
| UAF concepts | `references/uaf-concepts.md` |
| UAF utility functions | `references/uaf-utility.md` |
| UAF data prep | `references/uaf-data-prep.md` |
| UAF estimation prep (ACF/PACF) | `references/uaf-estimation-prep.md` |
| UAF ARIMA estimation | `references/uaf-estimation-arima.md` |
| UAF regression | `references/uaf-estimation-regression.md` |
| UAF forecasting | `references/uaf-forecasting.md` |
| UAF diagnostics | `references/uaf-diagnostics.md` |
| UAF DSP & wavelets | `references/uaf-dsp-wavelets.md` |
| UAF fundamentals (FFT) | `references/uaf-fundamentals.md` |
| **Geospatial** | |
| Geospatial types | `references/geospatial-types.md` |
| Geospatial analysis | `references/geospatial-analysis.md` |
| **External Data** | |
| OTF setup (Iceberg/Delta) | `references/open-table-format-setup.md` |
| OTF query & DML | `references/open-table-format-query.md` |
| OTF admin (catalogs) | `references/open-table-format-admin.md` |
| OTF reference (types/versions) | `references/open-table-format-reference.md` |
| NOS read | `references/object-store-read.md` |
| NOS write/export | `references/object-store-write.md` |
| **Infrastructure** | |
| Authorization objects | `references/authorization-objects.md` |
| LLM providers | `references/llm-providers.md` |
| Catalog views (DBC.*) | `references/catalog-views.md` |
| Query tuning | `references/query-tuning.md` |
| **BYOM** | |
| Model loading | `references/byom-model-loading.md` |
| Model scoring | `references/byom-scoring.md` |

## Procedures

### Response Strategy (CRITICAL — read before every task)

Follow this decision process in order:

**Step 1 — Can I answer from this skill?**
Read the Procedures and Common Errors sections below. If they contain the
function names, syntax patterns, and pipeline steps needed, produce the answer
directly. No tool calls required. This covers most "Write SQL", "Generate",
"Show me", and "Explain" requests.

**Step 2 — Do I need more detail? → Read references.**
If the skill body gives function names but you need exact parameter signatures,
argument ordering, or edge-case syntax, read the relevant reference file using
the exact path from the Resource Manifest above:
```
skill_resource_read(action="read", skill="primary-teradata", path="references/guidelines.md")
```
Use the reference content to finalize your SQL, then respond. Do NOT proceed
to database tools — references are sufficient for generation tasks.

**Step 3 — Execute SQL only after formulating correct queries.**
Database tool calls (`teradata_tool_call`) are expensive in latency and cost.
Postpone execution until you have a fully-formed query from Steps 1–2. Typical
reasons to execute: validating results, fetching schema you cannot infer, or
confirming data exists. Do not execute speculatively or to discover syntax.

Never use database tools (`teradata_search_tools`, `teradata_get_tool_schema`)
as a way to discover syntax. The skill and its references are the syntax authority.

**Turn budget:** Steps 1–2 should complete in 1–3 turns. Do not loop through
tool-discovery calls. If you know the function name, write the SQL.

### Writing Analytics SQL

1. Identify the correct native functions from this skill's Procedures sections
2. If parameter details are unclear, read the matching reference file (Step 2 above)
3. Follow the Fit/Transform pattern for ML and data-prep operations
4. Use CTEs to chain pipeline steps
5. Output the complete SQL in a single fenced code block
6. Only execute via `teradata_tool_call` if the user explicitly asks to run it

### ML Pipeline (Classification/Regression)

1. **Explore**: `TD_ColumnSummary`, `TD_UnivariateStatistics`, `TD_Histogram`
2. **Clean**: NULL handling, deduplication, outlier filtering
3. **Prepare**: `TD_ScaleFit`/`Transform`, `TD_OneHotEncodingFit`/`Transform`, `TD_SMOTE`
4. **Split**: `TD_TrainTestSplit`
5. **Train**: `TD_XGBoost`, `TD_DecisionForest`, `TD_GLM`, `TD_LogReg`
6. **Evaluate**: `TD_ClassificationEvaluator`, `TD_ROC`, `TD_SHAP`
7. **Deploy**: CTE prediction pipeline pattern

### Time-Series Forecasting (UAF/ARIMA)

1. **Prepare**: Convert table to UAF format with `TD_CONVERTTABLEFORUAF`
2. **Diagnose stationarity**: `TD_ACF`, `TD_PACF`, `TD_DICKEY_FULLER`
3. **Difference if needed**: `TD_DIFF`, `TD_SEASONALNORMALIZE`
4. **Estimate**: `TD_ARIMAESTIMATE` or `TD_AUTOARIMA`
5. **Validate**: `TD_ARIMAVALIDATE`, `TD_FITMETRICS`
6. **Forecast**: `TD_ARIMAFORECAST` or `TD_HOLT_WINTERS_FORECASTER`

### External Data Access

- **Iceberg/Delta**: `CREATE DATALAKE` → three-tier notation → `SELECT`/DML
- **NOS Read**: `READ_NOS` for ad-hoc, `CREATE FOREIGN TABLE` for persistent
- **NOS Export**: `WRITE_NOS` to S3/Azure/GCS in Parquet/CSV/JSON

### Vector Search / RAG

1. Configure authorization object for embedding provider
2. Generate embeddings with `AI_TextEmbeddings` or `ONNXEmbeddings`
3. Store in `VECTOR(n)` column
4. Search with `TD_VectorDistance` (exact) or `TD_HNSWPredict` (approximate)

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `SELECT * FROM large_table` | Data movement violation | Use `TOP 100`, `SAMPLE`, or native summary functions |
| Hand-written aggregation loops | Ignoring native operators | Replace with `TD_UnivariateStatistics`, `TD_Histogram`, etc. |
| Missing `PARTITION BY` clause | Table operator syntax error | All TD_* functions require `PARTITION BY` (use `ANY` for single-partition) |
| Fit without Transform | Incomplete ML pipeline | Always pair Fit (training) with Transform (inference) |
| Raw ARIMA without stationarity check | Non-stationary input | Run `TD_DICKEY_FULLER` first; difference with `TD_DIFF` if needed |
| Wrong UAF input format | Table not in series format | Use `TD_CONVERTTABLEFORUAF` to reshape first |
| Missing authorization object | AI/LLM function fails | Create with `CREATE AUTHORIZATION` before calling AI_* functions |

## References

### Start Here
- [index.md](./references/index.md) — Topic index with workflow reading orders
- [guidelines.md](./references/guidelines.md) — Native functions first; canonical operation mappings

### Core SQL
- [sql-basics.md](./references/sql-basics.md) — SELECT, TOP, SAMPLE, QUALIFY, CTEs, joins
- [data-types-casting.md](./references/data-types-casting.md) — Data types, CAST, VECTOR types
- [core-scalar-functions.md](./references/core-scalar-functions.md) — String, numeric, and conditional functions
- [sql-functions.md](./references/sql-functions.md) — Date/time, aggregate, and window functions
- [bit-byte-functions.md](./references/bit-byte-functions.md) — Bit/byte manipulation
- [json-functions.md](./references/json-functions.md) — JSON DDL, extraction, shredding, publishing
- [utility-functions.md](./references/utility-functions.md) — TD_FillRowID, TD_NumApply, TD_RoundColumns

### Data Preparation & Exploration
- [data-exploration.md](./references/data-exploration.md) — Descriptive stats, sampling, histograms
- [data-cleaning.md](./references/data-cleaning.md) — NULL handling, deduplication, outlier detection
- [data-prep-scaling.md](./references/data-prep-scaling.md) — Feature scaling and normalization
- [data-prep-encoding.md](./references/data-prep-encoding.md) — Categorical encoding and fit/transform
- [data-prep-imbalance.md](./references/data-prep-imbalance.md) — TD_SMOTE and class imbalance handling
- [training-dataset-assembly.md](./references/training-dataset-assembly.md) — Hybrid-source training dataset workflow: discovery, join validation, materialization, boundary rules

### Machine Learning
- [ml-functions-linear.md](./references/ml-functions-linear.md) — Linear models: GLM, LogReg, SVM
- [ml-functions-ensemble.md](./references/ml-functions-ensemble.md) — XGBoost, DecisionForest, KNN
- [ml-unsupervised.md](./references/ml-unsupervised.md) — Clustering, association analysis, CFilter
- [ml-patterns.md](./references/ml-patterns.md) — End-to-end pipeline patterns, micromodeling
- [ml-pipeline-procedures.md](./references/ml-pipeline-procedures.md) — Step-by-step KMeans pipeline recipes, batch scoring, centroid extraction
- [model-evaluation.md](./references/model-evaluation.md) — Evaluators, ROC, Silhouette, SHAP
- [hypothesis-testing.md](./references/hypothesis-testing.md) — ANOVA, ChiSq, FTest, ZTest

### Text & NLP
- [text-analytics.md](./references/text-analytics.md) — NGramSplitter, NaiveBayesTextClassifier, NER
- [ai-text-analytics.md](./references/ai-text-analytics.md) — LLM-powered AI_* text functions
- [path-analysis.md](./references/path-analysis.md) — Attribution, Sessionize, nPath

### Vector & Embeddings
- [vector-search.md](./references/vector-search.md) — VectorDistance, HNSW approximate search
- [embeddings.md](./references/embeddings.md) — AI_TextEmbeddings, ONNXEmbeddings, WordEmbeddings

### UAF (Unbounded Array Framework)
- [uaf-concepts.md](./references/uaf-concepts.md) — SERIES_SPEC, MATRIX_SPEC, ART layers
- [uaf-utility.md](./references/uaf-utility.md) — UAF utility and conversion functions
- [uaf-data-prep.md](./references/uaf-data-prep.md) — Resampling, binary operations, anomaly detection
- [uaf-estimation-prep.md](./references/uaf-estimation-prep.md) — ACF, PACF, differencing, smoothing
- [uaf-estimation-arima.md](./references/uaf-estimation-arima.md) — ARIMA estimation and validation
- [uaf-estimation-regression.md](./references/uaf-estimation-regression.md) — Linear and multivariate regression
- [uaf-forecasting.md](./references/uaf-forecasting.md) — ARIMA forecast, Holt-Winters, DTW
- [uaf-diagnostics.md](./references/uaf-diagnostics.md) — Statistical diagnostic tests
- [uaf-dsp-wavelets.md](./references/uaf-dsp-wavelets.md) — Wavelets, convolution, SAX
- [uaf-fundamentals.md](./references/uaf-fundamentals.md) — FFT/DFT and formula syntax rules

### Geospatial
- [geospatial-types.md](./references/geospatial-types.md) — ST_Geometry types, WKT/WKB, MBR
- [geospatial-analysis.md](./references/geospatial-analysis.md) — Spatial functions, tessellation, indexing

### External Data
- [open-table-format-setup.md](./references/open-table-format-setup.md) — REPLACE AUTHORIZATION, REPLACE DATALAKE, IAM roles, ALTER DATALAKE, DBC.DataLakesV
- [open-table-format-query.md](./references/open-table-format-query.md) — Three-part naming, HELP DATALAKE/DATABASE/TABLE, time travel, DML, COLLECT STATS on OTF
- [open-table-format-admin.md](./references/open-table-format-admin.md) — AWS Glue, Hive Metastore, Polaris, Unity Catalog, Lake Formation, BigLake, OAuth
- [open-table-format-reference.md](./references/open-table-format-reference.md) — Iceberg v2/Delta v3 versions, type mappings, TLS 1.2, OTF stats, compression, retention
- [object-store-read.md](./references/object-store-read.md) — READ_NOS, foreign tables, PATHPATTERN
- [object-store-write.md](./references/object-store-write.md) — WRITE_NOS export to cloud storage

### Infrastructure & Security
- [authorization-objects.md](./references/authorization-objects.md) — CREATE/GRANT AUTHORIZATION
- [llm-providers.md](./references/llm-providers.md) — Provider argument blocks for AI functions
- [catalog-views.md](./references/catalog-views.md) — DBC.* system views for schema discovery
- [query-tuning.md](./references/query-tuning.md) — EXPLAIN, PI design, statistics, rewrites

### BYOM (Bring Your Own Model)
- [byom-model-loading.md](./references/byom-model-loading.md) — PMML, ONNX, H2O model import
- [byom-scoring.md](./references/byom-scoring.md) — PMMLPredict, ONNXPredict, H2OPredict

## Templates

### Basic Analytics Query
```sql
SELECT * FROM TD_UnivariateStatistics(
    ON my_db.my_table AS InputTable PARTITION BY ANY
    USING TargetColumns('[1:10]')
) AS t;
```

### ML Training Pipeline (CTE Pattern)
```sql
-- Split → Train → Score → Evaluate
WITH split AS (
    SELECT * FROM TD_TrainTestSplit(
        ON my_db.features PARTITION BY ANY
        USING IDColumn('id') TestFraction(0.2) Seed(42)
    ) AS t
),
model AS (
    SELECT * FROM TD_XGBoost(
        ON split AS InputTable WHERE TD_IsTrainRow = 1 PARTITION BY ANY
        USING ResponseColumn('target') NumericInputs('[3:20]')
    ) AS t
)
SELECT * FROM TD_XGBoostPredict(
    ON split AS InputTable WHERE TD_IsTrainRow = 0 PARTITION BY ANY
    ON model AS ModelTable DIMENSION
    USING IDColumn('id') NumericInputs('[3:20]')
) AS t;
```

### UAF ARIMA Forecast
```sql
-- Convert → Estimate → Forecast
WITH series AS (
    SELECT * FROM TD_CONVERTTABLEFORUAF(
        ON my_db.timeseries PARTITION BY series_id ORDER BY ts
        USING ValueColumn('value') TimeColumn('ts')
    ) AS t
),
arima AS (
    SELECT * FROM TD_ARIMAESTIMATE(
        ON series PARTITION BY series_id
        USING ArimaOrder(1,1,1) SeasonalArimaOrder(1,1,1,12)
    ) AS t
)
SELECT * FROM TD_ARIMAFORECAST(
    ON arima PARTITION BY series_id
    USING Steps(12) IncludeHistory('true')
) AS t;
```
