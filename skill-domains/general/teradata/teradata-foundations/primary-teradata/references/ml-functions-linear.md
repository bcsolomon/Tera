# Teradata Vantage ML Functions

## TD_GLM — Train/Predict

Generalized Linear Model supporting regression (Gaussian family) and binary classification (Binomial family / logistic regression). Uses Stochastic Gradient Descent (SGD) for optimization.

**Two operating modes:**
- **PARTITION BY ANY** — trains a single model on the full dataset; supports LocalSGD for faster convergence on large clusters
- **PARTITION BY key (Micromodeling)** — trains one independent model per partition value in parallel; accepts optional per-partition `AttributeTable` (feature subset) and `ParameterTable` (parameter overrides)

**Constraints:**
- `AS InputTable` alias is mandatory
- All input columns must be numeric
- Classification (`Binomial`): response values must be 0 or 1
- No `OUT TABLE` for the model itself — capture via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`
- `MetaInformationTable` (training progress) available as `OUT TABLE` for PARTITION BY ANY only

### Train

**Mode 1 — PARTITION BY ANY (single model):**

```sql
SELECT * FROM TD_GLM(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]  -- AS InputTable mandatory
    [ OUT TABLE MetaInformationTable(db.meta_table) ]
    USING
        InputColumns({ 'col' | col_range }[,...])
        ResponseColumn('response_col')
        [ Family('Gaussian'|'Binomial') ]            -- default 'Gaussian'; Binomial = logistic regression
        [ BatchSize(10) ]                            -- default 10; 0 = full batch Gradient Descent
        [ MaxIterNum(300) ]                          -- default 300
        [ RegularizationLambda(0.02) ]               -- default 0.02; 0 = no regularization
        [ Alpha(0.15) ]                              -- default 0.15 (15% L1, 85% L2); only when Lambda > 0
        [ IterNumNoChange(50) ]                      -- default 50; 0 = no early stopping
        [ Tolerance(0.001) ]                         -- default 0.001; min loss improvement to continue
        [ Intercept('true') ]                        -- default true
        [ ClassWeights('0:1.0,1:1.0') ]              -- Binomial only; format 'class:weight,...'
        [ LearningRate('constant'|'optimal'|'invtime'|'adaptive') ]  -- default 'invtime' (Gaussian) / 'optimal' (Binomial)
        [ InitialEta(0.05) ]                         -- default 0.05; initial learning rate
        [ DecayRate(0.25) ]                          -- default 0.25; invtime and adaptive only
        [ DecaySteps(5) ]                            -- default 5; adaptive only
        [ Momentum(0) ]                              -- default 0 (disabled); recommended range 0.6–0.95
        [ Nesterov('true') ]                         -- default true; only effective when Momentum > 0
        [ LocalSGDIterations(0) ]                    -- default 0 (disabled); recommended 10 when enabled
        [ StepwiseDirection('forward'|'backward'|'both'|'bidirectional') ]
        [ MaxStepsNum(5) ]                           -- default 5; 0 = run until convergence
        [ InitialStepwiseColumns({ 'col' | col_range }[,...]) ]
) AS t;
```

**Mode 2 — PARTITION BY key (Micromodeling — one model per partition, trained in parallel):**

```sql
SELECT * FROM TD_GLM(
    ON { db.table | db.view | (query) } AS InputTable
        PARTITION BY partition_col [ ORDER BY id_col ]  -- ORDER BY ensures determinism when BatchSize < partition rows
    [ ON { db.table | db.view | (query) } AS AttributeTable
        PARTITION BY partition_col ]                    -- optional; per-partition feature subset
    [ ON { db.table | db.view | (query) } AS ParameterTable
        PARTITION BY partition_col ]                    -- optional; per-partition parameter overrides
    USING
        InputColumns({ 'col' | col_range }[,...])
        ResponseColumn('response_col')
        [ PartitionColumn('partition_col') ]            -- required only if partition col uses unicode/foreign chars
        [ Family('Gaussian'|'Binomial') ]
        [ BatchSize(10) ]
        [ MaxIterNum(300) ]
        [ RegularizationLambda(0.02) ]
        [ Alpha(0.15) ]
        [ IterNumNoChange(50) ]
        [ Tolerance(0.001) ]
        [ Intercept('true') ]
        [ ClassWeights('0:1.0,1:1.0') ]
        [ LearningRate('constant'|'optimal'|'invtime'|'adaptive') ]
        [ InitialEta(0.05) ]
        [ DecayRate(0.25) ]
        [ DecaySteps(5) ]
        [ Momentum(0) ]
        [ Nesterov('true') ]
        [ IterationMode('Batch'|'Epoch') ]              -- default 'Batch'; Micromodeling only
) AS t;
```

> `StepwiseDirection`, `MaxStepsNum`, `InitialStepwiseColumns`, and `LocalSGDIterations` are PARTITION BY ANY only. `IterationMode` is Micromodeling only.

**Model output — PARTITION BY ANY:**

| Column | Type | Description |
|--------|------|-------------|
| `attribute` | SMALLINT | Index: 0=intercept, positive=predictor, negative=model metric |
| `predictor` | VARCHAR | Predictor or metric name |
| `estimate` | FLOAT | Predictor weight or numeric metric value |
| `value` | VARCHAR | String metric value (e.g., `SQUARED_ERROR`, `L2`) |

**Model output — Micromodeling** (partition column prepended):

| Column | Type | Description |
|--------|------|-------------|
| `partition_by_column` | varies | Partition identifier |
| `attribute` | SMALLINT | Same as above |
| `predictor` | VARCHAR | Same as above |
| `estimate` | FLOAT | Same as above |
| `value` | VARCHAR | Same as above |

**MetaInformationTable** (optional `OUT TABLE`, PARTITION BY ANY only):

| Column | Type | Description |
|--------|------|-------------|
| `iteration` | INTEGER | Iteration number |
| `num_rows` | BIGINT | Rows processed |
| `eta` | FLOAT | Learning rate for this iteration |
| `loss` | FLOAT | Loss value |
| `best_loss` | FLOAT | Best loss up to this iteration |
| `Step` | INTEGER | [StepwiseDirection only] Step number |
| `SubStep` | INTEGER | [StepwiseDirection only] Feature sequence number |
| `Description` | VARCHAR | [StepwiseDirection only] Stage description; `+feature` = added, `-feature` = removed |
| `Score` | FLOAT | [StepwiseDirection only] Model score at each substep |
| `Model` | VARCHAR | [StepwiseDirection only] Variable names in model at this step |

**AttributeTable schema** (Micromodeling):

| Column | Type | Description |
|--------|------|-------------|
| `partition_by_column` | varies | Partition identifier |
| `attribute_column` | VARCHAR | Feature column names for this partition; column must be named `attribute_column`; no duplicates |

**ParameterTable schema** (Micromodeling):

| Column | Type | Description |
|--------|------|-------------|
| `partition_by_column` | varies | Partition identifier |
| `parameter_column` | VARCHAR | Parameter name (column must be named `parameter_column`) |
| `value_column` | VARCHAR | Parameter value (column must be named `value_column`) |

### Predict

**Mode 1 — PARTITION BY ANY:**

```sql
SELECT * FROM TD_GLMPredict(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn('id_col')                           -- required; unique row identifier
        [ Family('Gaussian'|'Binomial') ]            -- must match Family used in TD_GLM training
        [ OutputProb('false') ]                      -- default false; Binomial only
        [ Responses('0'[,'1']) ]                     -- Binomial only; requires OutputProb('true')
        [ Accumulate({ 'col' | col_range }[,...]) ]
) AS t;
```

**Mode 2 — Micromodeling:**

```sql
SELECT * FROM TD_GLMPredict(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY partition_col
    ON { db.table | db.view | (query) } AS ModelTable PARTITION BY partition_col  -- PARTITION BY, not DIMENSION
    USING
        IDColumn('id_col')
        [ PartitionColumn('partition_col') ]         -- required only if partition col uses unicode/foreign chars
        [ Family('Gaussian'|'Binomial') ]
        [ OutputProb('false') ]
        [ Responses('0'[,'1']) ]
        [ Accumulate({ 'col' | col_range }[,...]) ]
) AS t;
```

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | any | Unique observation identifier |
| `partition_by_column` | varies | [Micromodeling only] Model identifier |
| `prediction` | FLOAT | Predicted value |
| `prob` | FLOAT | [When `OutputProb('true')` and no `Responses`] Probability of predicted class (Binomial only) |
| `prob_0` | FLOAT | [When `Responses` specified] Probability of class 0 |
| `prob_1` | FLOAT | [When `Responses` specified] Probability of class 1 |
| `accumulate_column(s)` | any | Columns copied from InputTable |

---


## TD_NaiveBayes — Train/Predict

Probabilistic classifier based on Bayes' theorem. Assumes input variables are conditionally independent given the outcome. Supports both numeric and categorical inputs in dense (one column per feature) or sparse (attribute name/value pairs) format.

**Constraints:**
- Dense: at least one of `NumericInputs` or `CategoricalInputs` required
- Sparse: `AttributeNameColumn` + `AttributeValueColumn` required, plus one of `NumericAttributes`, `CategoricalAttributes`, or `AttributeType`
- No `OUT TABLE` clause — capture model via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`

### Train

**Dense input (one column per feature):**

```sql
SELECT * FROM TD_NaiveBayes(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        ResponseColumn('response_col')
        [ NumericInputs({ 'col' | col_range }[,...]) ]       -- at least one of NumericInputs or
        [ CategoricalInputs({ 'col' | col_range }[,...]) ]   -- CategoricalInputs required for dense
) AS t;
```

**Sparse input (attribute name/value pairs):**

```sql
SELECT * FROM TD_NaiveBayes(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        ResponseColumn('response_col')
        AttributeNameColumn('attr_name_col')                 -- required for sparse
        AttributeValueColumn('attr_value_col')               -- required for sparse
        { [ NumericAttributes('attr1'[,...]) ]               -- name specific numeric attributes
          [ CategoricalAttributes('attr1'[,...]) ]           -- name specific categorical attributes
        | AttributeType('ALLNUMERIC'|'ALLCATEGORICAL')       -- or declare all as one type
        }
) AS t;
```

**Model output schema** (save via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`):

| Column | Type | Description |
|--------|------|-------------|
| `class` | VARCHAR | Response value |
| `variable` | VARCHAR | Attribute name |
| `type` | VARCHAR | `'NUMERIC'` or `'CATEGORICAL'` |
| `category` | VARCHAR | NULL for NUMERIC; category value for CATEGORICAL |
| `cnt` | BIGINT | Observation count for this class/variable/category |
| `sum` | REAL | NUMERIC: sum of variable values; CATEGORICAL: NULL |
| `sumsq` | REAL | NUMERIC: sum of squared values; CATEGORICAL: NULL |
| `totalcnt` | BIGINT | Total observation count |
| `smoothingfactor` | REAL | NUMERIC: NULL; CATEGORICAL: smoothing factor |

### Predict

**Dense input:**

```sql
SELECT * FROM TD_NaiveBayesPredict(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn('id_col')                                   -- required
        [ Responses('response1'[,...]) ]
        [ OutputProb('false') ]
        [ Accumulate({ 'col' | col_range }[,...]) ]
        [ NumericInputs({ 'col' | col_range }[,...]) ]       -- at least one of NumericInputs or
        [ CategoricalInputs({ 'col' | col_range }[,...]) ]   -- CategoricalInputs required for dense
) AS t;
```

**Sparse input:**

```sql
SELECT * FROM TD_NaiveBayesPredict(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn('id_col')
        [ Responses('response1'[,...]) ]
        [ OutputProb('false') ]
        [ Accumulate({ 'col' | col_range }[,...]) ]
        AttributeNameColumn('attr_name_col')                 -- required for sparse
        AttributeValueColumn('attr_value_col')               -- required for sparse
) AS t;
```

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | any | Row identifier |
| `Prediction` | VARCHAR | Predicted class |
| `Loglik` | REAL | When no `Responses`; log likelihood of predicted value |
| `Prob` | REAL | When no `Responses` and `OutputProb('true')`; probability of predicted value |
| `Loglik_<response_i>` | REAL | When `Responses` specified; log likelihood per response value |
| `Prob_<response_i>` | REAL | When `Responses` specified and `OutputProb('true')`; probability per response value |
| `accumulate_column(s)` | any | Columns copied from InputTable |

---


## TD_OneClassSVM — Train/Predict

Linear SVM for anomaly/novelty detection. All training data is assumed to belong to a single class (value 1) — no `ResponseColumn` needed. At predict time, outputs `1` (normal) or `0` (outlier). Uses the same Minibatch SGD engine as TD_GLM; see TD_GLM for SGD parameter details.

**Constraints:**
- `AS InputTable` alias is mandatory
- PARTITION BY ANY only — no micromodeling support
- No `ResponseColumn` — one-class training only
- No `OUT TABLE` for the model — capture via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`
- `Nesterov` defaults to `false` here (unlike TD_GLM which defaults to `true`)

### Train

```sql
SELECT * FROM TD_OneClassSVM(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY  -- AS InputTable mandatory
    [ OUT TABLE MetaInformationTable(db.meta_table) ]
    USING
        InputColumns({ 'col' | col_range }[,...])     -- required; no ResponseColumn needed
        [ BatchSize(10) ]                             -- default 10; 0 = full batch Gradient Descent
        [ MaxIterNum(300) ]                           -- default 300
        [ RegularizationLambda(0.02) ]                -- default 0.02; 0 = no regularization
        [ Alpha(0.15) ]                               -- default 0.15 (15% L1, 85% L2); only when Lambda > 0
        [ IterNumNoChange(50) ]                       -- default 50; 0 = no early stopping
        [ Tolerance(0.001) ]                          -- default 0.001
        [ Intercept('true') ]                         -- default true
        [ LearningRate('constant'|'optimal'|'invtime'|'adaptive') ]  -- default 'invtime'
        [ InitialEta(0.05) ]                          -- default 0.05
        [ DecayRate(0.25) ]                           -- default 0.25; invtime and adaptive only
        [ DecaySteps(5) ]                             -- default 5; adaptive only
        [ Momentum(0) ]                               -- default 0 (disabled); recommended range 0.6–0.95
        [ Nesterov('false') ]                         -- default false; only effective when Momentum > 0
        [ LocalSGDIterations(0) ]                     -- default 0 (disabled); recommended 10 when enabled
) AS t;
```

**Model output schema** (save via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`):

| Column | Type | Description |
|--------|------|-------------|
| `attribute` | SMALLINT | Index: 0=intercept, positive=predictor, negative=model metric |
| `predictor` | VARCHAR | Predictor or metric name |
| `estimate` | FLOAT | Predictor weight or numeric metric value |
| `value` | VARCHAR | String metric value (e.g., `HINGE` for LossFunction, `L2` for Regularization) |

**MetaInformationTable schema:**

| Column | Type | Description |
|--------|------|-------------|
| `iteration` | INTEGER | Iteration (epoch) number |
| `num_rows` | BIGINT | Total rows processed |
| `eta` | FLOAT | Learning rate for this iteration |
| `loss` | FLOAT | Loss value |
| `best_loss` | FLOAT | Best loss up to this iteration |

### Predict

```sql
SELECT * FROM TD_OneClassSVMPredict(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn('id_col')                           -- required; unique row identifier
        [ OutputProb('false') ]                      -- default false
        [ Responses('0'[,'1']) ]                     -- requires OutputProb('true'); 0 = outlier, 1 = normal
        [ Accumulate({ 'col' | col_range }[,...]) ]
) AS t;
```

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | any | Unique observation identifier |
| `prediction` | FLOAT | `0` = outlier, `1` = normal observation |
| `prob` | FLOAT | When `OutputProb('true')` and no `Responses`; probability of predicted class |
| `prob_0` | FLOAT | When `Responses` specified; probability of class 0 (outlier) |
| `prob_1` | FLOAT | When `Responses` specified; probability of class 1 (normal) |
| `accumulate_column(s)` | any | Columns copied from InputTable |

---


## TD_SVM — Train/Predict

Linear SVM for binary classification (hinge loss) and regression (epsilon-insensitive loss). Uses the same Minibatch SGD engine as TD_GLM and TD_OneClassSVM. Classification supports binary response only (0 or 1).

**Constraints:**
- `AS InputTable` alias is mandatory
- PARTITION BY ANY only — no micromodeling support
- Classification: response values must be 0 or 1 (binary only)
- No `OUT TABLE` for the model — capture via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`
- `Nesterov` defaults to `false` (unlike TD_GLM which defaults to `true`)
- `ModelType` must match between Train and Predict

### Train

```sql
SELECT * FROM TD_SVM(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY  -- AS InputTable mandatory
    [ OUT TABLE MetaInformationTable(db.meta_table) ]
    USING
        InputColumns({ 'col' | col_range }[,...])
        ResponseColumn('response_col')               -- required; classification: 0 or 1 only
        [ ModelType('Classification'|'Regression') ] -- default 'Classification'
        [ Epsilon(0.1) ]                             -- default 0.1; Regression only; epsilon-insensitive loss threshold
        [ BatchSize(10) ]                            -- default 10; 0 = full batch Gradient Descent
        [ MaxIterNum(300) ]                          -- default 300
        [ RegularizationLambda(0.02) ]               -- default 0.02; 0 = no regularization
        [ Alpha(0.15) ]                              -- default 0.15 (15% L1, 85% L2); only when Lambda > 0
        [ IterNumNoChange(50) ]                      -- default 50; 0 = no early stopping
        [ Tolerance(0.001) ]                         -- default 0.001
        [ Intercept('true') ]                        -- default true
        [ ClassWeights('0:1.0,1:1.0') ]              -- Classification only; format 'class:weight,...'
        [ LearningRate('constant'|'optimal'|'invtime'|'adaptive') ]  -- default 'invtime' (Regression) / 'optimal' (Classification)
        [ InitialEta(0.05) ]                         -- default 0.05
        [ DecayRate(0.25) ]                          -- default 0.25; invtime and adaptive only
        [ DecaySteps(5) ]                            -- default 5; adaptive only
        [ Momentum(0) ]                              -- default 0 (disabled); recommended range 0.6–0.95
        [ Nesterov('false') ]                        -- default false; only effective when Momentum > 0
        [ LocalSGDIterations(0) ]                    -- default 0 (disabled); recommended 10 when enabled
) AS t;
```

**Model output schema** (save via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`):

| Column | Type | Description |
|--------|------|-------------|
| `attribute` | SMALLINT | Index: 0=intercept, positive=predictor, negative=model metric |
| `predictor` | VARCHAR | Predictor or metric name |
| `estimate` | FLOAT | Predictor weight or numeric metric value |
| `value` | VARCHAR | String metric value (e.g., `HINGE` for Classification, `EPSILON_INSENSITIVE` for Regression, `L2` for Regularization) |

**MetaInformationTable schema:**

| Column | Type | Description |
|--------|------|-------------|
| `iteration` | INTEGER | Iteration (epoch) number |
| `num_rows` | BIGINT | Total rows processed |
| `eta` | FLOAT | Learning rate for this iteration |
| `loss` | FLOAT | Loss value |
| `best_loss` | FLOAT | Best loss up to this iteration |

### Predict

```sql
SELECT * FROM TD_SVMPredict(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn('id_col')                           -- required; unique row identifier
        [ ModelType('Classification'|'Regression') ] -- default 'Classification'; must match TD_SVM training
        [ OutputProb('false') ]                      -- default false; Classification only
        [ Responses('0'[,'1']) ]                     -- requires OutputProb('true'); values 0 or 1
        [ Accumulate({ 'col' | col_range }[,...]) ]
) AS t;
```

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | same as input | Unique observation identifier |
| `prediction` | SMALLINT (Classification) / FLOAT (Regression) | Predicted class or value |
| `prob` | FLOAT | When `OutputProb('true')` and no `Responses`; probability of predicted class |
| `prob_0` | FLOAT | When `Responses` specified; probability of class 0 |
| `prob_1` | FLOAT | When `Responses` specified; probability of class 1 |
| `accumulate_column(s)` | any | Columns copied from InputTable |

---
