---
name: teradata-byom
description: 'Use Teradata Bring Your Own Model (BYOM) capabilities to load externally trained models and run in-database scoring for PMML, ONNX, H2O, and related model formats at scale.'
metadata:
    author: teradata
    version: "1.0"
---

# Teradata BYOM — Bring Your Own Model

> **Skill:** teradata-byom  
> **Domain:** 12-advanced-data-and-analytics-features / 10-byom-model-scoring  
> **Applies to:** Teradata Vantage 17.10+, VantageCloud Lake  

---

## Purpose

Guide agents through loading externally trained ML models into Teradata and scoring in-database data without moving it off-platform. BYOM supports PMML, H2O MOJO, ONNX, Dataiku, DataRobot, and MLeap model formats.

---

## When to Use

- Score data using models trained in external frameworks (scikit-learn, XGBoost, H2O, PyTorch, TensorFlow)
- Run inference at Teradata scale without data extraction
- Deploy models trained in notebooks or MLOps pipelines directly to the database
- NLP inference using ONNX transformer models (sequence-to-sequence, classification, embeddings)

---

## Model Loading

Models are stored in BLOB tables. Standard schema:

```sql
CREATE TABLE db.my_models (
    model_id  VARCHAR(128),
    model     BLOB(2G)             -- the serialized model file
) UNIQUE PRIMARY INDEX (model_id);

-- Load from client file (BTEQ, TPT, or Python)
-- Python example:
-- import teradataml; model_df.to_sql('my_models', con=engine, if_exists='append')
```

See [references/byom-model-loading.md](references/byom-model-loading.md) for format-specific loading instructions.

---

## Scoring Functions

| Function | Model Format | Schema | Reference |
|----------|-------------|--------|-----------|
| `PMMLPredict` | PMML (scikit-learn, R, SAS) | `mldb` | [byom-scoring.md](references/byom-scoring.md) |
| `H2OPredict` | H2O MOJO (open source + DAI) | `mldb` | [byom-scoring.md](references/byom-scoring.md) |
| `ONNXPredict` | ONNX (numeric/tabular) | `mldb` | [byom-scoring.md](references/byom-scoring.md) |
| `DataikuPredict` | Dataiku export | `mldb` | [byom-scoring.md](references/byom-scoring.md) |
| `DataRobotPredict` | DataRobot export | `mldb` | [byom-scoring.md](references/byom-scoring.md) |
| `MLeapPredict` | MLeap (Spark pipelines) | `mldb` | [byom-scoring.md](references/byom-scoring.md) |

### NLP / Transformer Scoring (ONNX)

| Function | Task | Reference |
|----------|------|-----------|
| `ONNXEmbeddings` | Generate embeddings from text | [byom-scoring.md](references/byom-scoring.md) |
| `ONNXSeq2Seq` | Sequence-to-sequence (translation, summarization) | [byom-scoring.md](references/byom-scoring.md) |
| `ONNXClassification` | Text classification | [byom-scoring.md](references/byom-scoring.md) |

---

## Common Scoring Pattern

All BYOM functions share the same two-table pattern:

```sql
SELECT * FROM [mldb.]PMMLPredict(
    ON db.input_data AS InputTable
    ON db.my_models AS ModelTable DIMENSION
    USING
        Accumulate('*')                    -- required: copy input columns to output
) AS t;
```

### Multiple Models — Select by ID

```sql
SELECT * FROM PMMLPredict(
    ON db.input_data AS InputTable
    ON (SELECT * FROM db.my_models WHERE model_id = 'fraud_rf_v2') AS ModelTable DIMENSION
    USING
        Accumulate('customer_id', 'amount')
        ModelOutputFields('predicted_class', 'probability_fraud')
) AS t;
```

---

## Output Formats

| Parameter | Effect |
|-----------|--------|
| No `ModelOutputFields` | Returns `prediction` + `json_report` (all model outputs as JSON) |
| With `ModelOutputFields` | Returns named columns — suppresses `json_report` |

```sql
-- JSON output (default)
SELECT customer_id, prediction, json_report FROM PMMLPredict(...) AS t;

-- Named columns
SELECT * FROM PMMLPredict(
    ON ... USING
        Accumulate('customer_id')
        ModelOutputFields('predicted_species', 'probability_setosa', 'probability_versicolor')
) AS t;
```

---

## H2O with Explainability

```sql
SELECT * FROM H2OPredict(
    ON db.churn_data AS InputTable
    ON db.h2o_models AS ModelTable DIMENSION
    USING
        Accumulate('customer_id', 'actual_churn')
        ModelType('DAI')
        EnableOptions('contributions')    -- feature contribution per prediction
) AS t;
```

---

## ONNX Input Tensor Mapping

For complex ONNX models, map input columns to tensors:

```sql
SELECT * FROM ONNXPredict(
    ON db.features AS InputTable
    ON db.onnx_model AS ModelTable DIMENSION
    USING
        Accumulate('id')
        ModelInputFieldsMap('float_input=feat1,feat2,feat3')
) AS t;

-- Inspect mapping without scoring
SELECT * FROM ONNXPredict(
    ON db.features AS InputTable
    ON db.onnx_model AS ModelTable DIMENSION
    USING
        Accumulate('id')
        ShowModelInputFieldsMap('true')
) AS t;
```

---

## Common Pitfalls

| Mistake | Fix |
|---------|-----|
| Missing `Accumulate` | Required for all BYOM functions — use `'*'` for all columns |
| Using `OverwriteCachedModel` routinely | Only when replacing an updated model — can cause OOM in concurrent queries |
| H2O DAI missing license in ModelTable | Include license key column or separate license table |
| ONNX column name mismatch | Use `ShowModelInputFieldsMap('true')` to inspect expected mapping |
| Model caching issues (all-zero probabilities) | Set `UseCache('false')` for H2OPredict |

---

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-byom", path="references/FILENAME")` — do NOT call `list`.

| File | Content |
|------|---------|
| [byom-model-loading.md](references/byom-model-loading.md) | Model table schemas, loading instructions per format (PMML, H2O, ONNX, Dataiku, DataRobot, MLeap) |
| [byom-scoring.md](references/byom-scoring.md) | Full syntax for all scoring functions, NLP transformers, output formats, caching |

*Source: Teradata tdsql-mcp syntax library (ksturgeon-td/tdsql-mcp)*
