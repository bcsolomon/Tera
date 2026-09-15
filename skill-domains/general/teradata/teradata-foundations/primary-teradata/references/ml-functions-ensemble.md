# Teradata Vantage ML Functions

## TD_DecisionForest — Train/Predict

Ensemble algorithm for classification and regression using random decision forests (bagging of decision trees). Supports binary and multiclass classification and regression. Trees are built in parallel across AMPs.

**Constraints:**
- All input columns must be numeric — convert categoricals before calling
- Classification: `ResponseColumn` must be INTEGER/SMALLINT/BYTEINT; max 500 classes
- Rows with NULL in any input column are skipped — use `TD_SimpleImpute` first
- No `OUT TABLE` clause — capture the model via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`

### Train

```sql
SELECT * FROM TD_DecisionForest(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    USING
        InputColumns({ 'col' | col_range }[,...])    -- required; all numeric; no double-quoted names
        ResponseColumn('response_col')               -- required; classification: INTEGER/SMALLINT/BYTEINT only
        [ ModelType('Classification'|'Regression') ] -- default 'Regression'
        [ MaxDepth(5) ]                              -- default 5; non-negative integer; tree stops at this depth
        [ MinNodeSize(1) ]                           -- default 1; stop splitting when node has <= this many rows
        [ NumTrees(-1) ]                             -- default -1 (auto); max 65536; if specified, must be >= num AMPs
        [ TreeSize(-1) ]                             -- default -1 (auto); rows per tree input sample
        [ CoverageFactor(1.0) ]                      -- default 1.0 (100%); dataset coverage level per tree
        [ MinImpurity(0.0) ]                         -- default 0.0; stop splitting at or below this impurity
        [ Mtry(-1) ]                                 -- default -1 (all features); features evaluated per split
        [ MtrySeed(1) ]                              -- default 1; random seed for Mtry
        [ Seed(1) ]                                  -- default 1; random seed for reproducibility
) AS t;
```

> **NumTrees note:** When specified, actual tree count = `Num_AMPs_with_data × (NumTrees / Num_AMPs_with_data)`. Use `SELECT HASHAMP()+1;` to get AMP count. For small datasets, distribute data to one AMP by setting all rows to the same primary index value.

**Model output schema** (save this table for use in Predict):

| Column | Type | Description |
|--------|------|-------------|
| `task_index` | SMALLINT | AMP that produced this tree |
| `tree_num` | SMALLINT | Tree identifier within the AMP |
| `tree_order` | INTEGER | Sequence number for multi-row JSON chunks |
| `classification_tree` or `regression_tree` | VARCHAR(16000) | JSON decision tree; split across rows when > 16000 bytes |

### Predict

```sql
SELECT * FROM TD_DecisionForestPredict(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn('id_col')                           -- required; unique row identifier; cannot be NULL
        [ Detailed('false') ]                        -- default false; outputs per-tree task_index/tree_num detail
        [ OutputProb('false') ]                      -- default false; classification only; must be true if using Responses
        [ Responses('class1'[,...]) ]                -- classification only; requires OutputProb('true')
        [ Accumulate({ 'col' | col_range }[,...]) ]  -- input columns to copy to output
) AS t;
```

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | same as input | Row identifier from InputTable |
| `prediction` | INTEGER (classification) / FLOAT (regression) | Predicted class or value |
| `confidence_lower` | FLOAT | When `OutputProb('false')`; for classification, equals probability of predicted class |
| `confidence_upper` | FLOAT | When `OutputProb('false')`; for classification, equals probability of predicted class |
| `prob` | FLOAT | When `OutputProb('true')` and no `Responses`; probability of predicted class |
| `prob_<response>` | FLOAT | When `OutputProb('true')` and `Responses` specified; one column per response value |
| `tree_num` | VARCHAR(30) | When `Detailed('true')`; per-tree task/tree concatenation, or `'Final'` for overall prediction |
| `accumulate_column(s)` | same as input | Columns copied from InputTable |

---


## TD_XGBoost — Train/Predict

Gradient boosted decision tree ensemble for classification and regression. Builds multiple boosted trees in parallel across AMPs. Supports multiclass classification (max 500 classes) and regression.

**Constraints:**
- InputTable: no PARTITION BY column; PARTITION BY ANY allowed
- All input columns must be numeric; no double-quoted column names
- Classification: `ResponseColumn` must be INTEGER/BIGINT/SMALLINT/BYTEINT
- No `OUT TABLE` for the model — capture via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`
- `NumParallelTrees` and `CoverageFactor` are mutually exclusive
- `ModelType` must match between Train and Predict

### Train

```sql
SELECT * FROM TD_XGBoost(
    ON { db.table | db.view | (query) } AS INPUTTABLE [ PARTITION BY ANY ]  -- no PARTITION BY column
    [ OUT [ PERMANENT | VOLATILE ] TABLE MetaInformationTable(db.meta_table) ]
    USING
        InputColumns({ 'col' | col_range }[,...])    -- required; all numeric; no double-quoted names
        ResponseColumn('response_col')               -- required; classification: INTEGER/BIGINT/SMALLINT/BYTEINT only
        [ ModelType('Classification'|'Regression') ] -- default 'Regression'
        [ MaxDepth(5) ]                              -- default 5; tree depth stopping criterion
        [ MinNodeSize(1) ]                           -- default 1; min node size stopping criterion
        [ NumParallelTrees(-1) ]                     -- default -1 (= num AMPs with data); range 1–10000
                                                     -- also accepts legacy name NumBoostedTrees
                                                     -- mutually exclusive with CoverageFactor
        [ CoverageFactor(1.0) ]                      -- default 1.0 (100%); mutually exclusive with NumParallelTrees
        [ NumBoostRounds(10) ]                       -- default 10; boosting iterations; range 1–100000
                                                     -- also accepts legacy name IterNum
        [ LearningRate(0.5) ]                        -- default 0.5; per-step shrinkage; range (0, 1]
                                                     -- also accepts legacy name ShrinkageFactor
        [ RegularizationLambda(1) ]                  -- default 1; L2 regularization; range [0, 100000]; 0 = none
        [ ColumnSampling(1.0) ]                      -- default 1.0; feature fraction per boost; range (0, 1]
        [ MinImpurity(0.0) ]                         -- default 0.0; stop splitting below this impurity
        [ TreeSize(-1) ]                             -- default -1 (auto); rows per tree input sample
        [ BaseScore(0) ]                             -- default 0 (Regression); 0.5 (Classification, must be in range (0,1))
        [ Seed(1) ]                                  -- default 1; random seed for column sampling
) AS t;
```

> **Small datasets / imbalanced classes:** Redistribute input to one AMP so each tree trains on a representative sample. Add a new column (e.g., `pi_col`) populated with a constant value and define it as the primary index — do not repurpose an existing column. For large clusters with small datasets, or classification with imbalanced classes, this redistribution significantly improves model quality.

**Model output schema** (save via `CREATE TABLE AS (...) WITH DATA` or `INSERT/SELECT`):

| Column | Type | Description |
|--------|------|-------------|
| `task_index` | SMALLINT | AMP that produced this tree |
| `tree_num` | SMALLINT | Boosted tree identifier |
| `iter` | SMALLINT | Boosting round number |
| `class_num` | SMALLINT | [Classification only] Class index; range [0, K-1] for K classes |
| `tree_order` | SMALLINT | Sequence number for multi-chunk JSON |
| `regression_tree` or `classification_tree` | VARCHAR(32000) | JSON decision tree per chunk |

**MetaInformationTable schema** (OUT TABLE — training accuracy per iteration):

| Column | Type | Description |
|--------|------|-------------|
| `task_index` | SMALLINT | AMP identifier |
| `iter` | SMALLINT | Boosting round number |
| `tree_num` | SMALLINT | Boosted tree identifier |
| `mse` / `accuracy` | DOUBLE | Regression: MSE per iteration; Classification: accuracy per iteration |
| `average residuals` / `deviance` | DOUBLE | Regression: avg residuals; Classification: deviance |

### Predict

```sql
SELECT * FROM TD_XGBoostPredict(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION
    USING
        IDColumn({ 'id_col' | id_col_range })        -- required; no double-quoted names
        [ ModelType('Classification'|'Regression') ] -- default: DOUBLE output; 'Classification' = INTEGER output
        [ NumParallelTrees(1000) ]                   -- default 1000; limits trees loaded; fewer = faster but less accurate
                                                     -- also accepts legacy name NumBoostedTrees
        [ NumBoostRounds(10) ]                       -- default 10; limits iterations per tree; fewer = faster but less accurate
                                                     -- also accepts legacy name IterNum
        [ OutputProb('false') ]                      -- default false; Classification only
        [ Responses('response'[,...]) ]              -- Classification only; requires OutputProb('true')
        [ Accumulate({ 'col' | col_range }[,...]) ]
) AS t;
```

> **Performance note:** `NumParallelTrees` and `NumBoostRounds` limit how much of the model is loaded at predict time — reducing either speeds up prediction but may reduce accuracy. When the model exceeds available memory, trees are cached in local spool, further impacting performance.

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | same as input | Unique row identifier |
| `prediction` | DOUBLE PRECISION (default) / INTEGER (when `ModelType('Classification')`) | Predicted value or class |
| `confidence_lower` | DOUBLE PRECISION | When `OutputProb('false')`; for classification, equals probability of predicted class |
| `confidence_upper` | DOUBLE PRECISION | When `OutputProb('false')`; for classification, equals probability of predicted class |
| `prob` | DOUBLE PRECISION | When `OutputProb('true')` and no `Responses`; probability of predicted class |
| `prob_response` | DOUBLE PRECISION | When `OutputProb('true')` and `Responses` specified; one column per response value |
| `accumulate_column(s)` | same as input | Columns copied from InputTable |
