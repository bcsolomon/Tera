# Teradata Data Preparation & Feature Engineering

## Column Selection

### Antiselect — Return All Columns Except Specified
```sql
SELECT * FROM Antiselect(
    ON { db.table | db.view | (query) }
    USING
        Exclude('col1', 'col2')                       -- explicit columns or range e.g. '[1:5]'
) AS t;
```

---


## Normalization / Scaling

### Min-Max Scaling (0 to 1)
```sql
SELECT col,
       (col - MIN(col) OVER ()) / NULLIFZERO(MAX(col) OVER () - MIN(col) OVER ()) AS col_minmax
FROM db.table;
```

### Z-Score Standardization
```sql
SELECT col,
       (col - AVG(col) OVER ()) / NULLIFZERO(STDDEV_SAMP(col) OVER ()) AS col_zscore
FROM db.table;
```

### TD_ScaleFit / TD_ScaleTransform
See the Fit/Transform function section below.

### TD_VectorNormalize

Normalizes numeric columns or `VECTOR` columns using one of four approaches. Supports list or range for `IDColumns`, `TargetColumns`, and `Accumulate`.

```sql
SELECT * FROM TD_VectorNormalize(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]
    USING
        IDColumns({ 'id_col' | col_range }[,...])         -- required; unique row identifier(s)
        TargetColumns({ 'col' | col_range }[,...])        -- required; columns to normalize; supports VECTOR type
        [ Accumulate({ 'col' | col_range }[,...]) ]       -- optional; columns to pass through
        [ Approach('UNITVECTOR'|'FRACTION'|'PERCENTAGE'|'INDEX') ]  -- default 'UNITVECTOR'
        [ BaseColumn('base_col') ]                        -- required with INDEX; per-row denominator column
        [ BaseValue('base_value') ]                       -- required with INDEX; scalar denominator value
) AS t;
```

**Approach options:**

| Approach | Formula | Use case |
|----------|---------|----------|
| `UNITVECTOR` (default) | `x / L2_norm(row)` | Normalize to unit length; required before cosine similarity or HNSW indexing |
| `FRACTION` | `x / sum(row)` | Each value as a fraction of the row total |
| `PERCENTAGE` | `x / sum(row) * 100` | Each value as a percentage of the row total |
| `INDEX` | `(x - B) / V` | Normalize relative to a base; `B` from `BaseColumn`, `V` from `BaseValue` |

> **Embedding pre-processing:** use `Approach('UNITVECTOR')` with a `VECTOR` column before storing embeddings or building an HNSW index. Unit-normalized vectors enable cosine similarity via dot product. See `vector-search` topic.

---


## Binning

### Equal-Width Bins (Manual)
```sql
SELECT id, amount,
       CASE
           WHEN amount < 100  THEN 'low'
           WHEN amount < 500  THEN 'medium'
           WHEN amount < 1000 THEN 'high'
           ELSE 'very_high'
       END AS amount_bin
FROM db.table;
```

### Equal-Frequency Bins / Quantile-Based (Manual)
```sql
SELECT id, amount,
       NTILE(4)  OVER (ORDER BY amount) AS quartile,
       NTILE(10) OVER (ORDER BY amount) AS decile
FROM db.table;
```

### TD_BinCodeFit / TD_BinCodeTransform
See the Fit/Transform function section below.

---


## Dimensionality Reduction

### TD_RandomProjectionMinComponents
Calculates the minimum number of components required before running `TD_RandomProjectionFit`.
Uses the Johnson-Lindenstrauss Lemma — run this first to estimate the `NumComponents` argument.

```sql
SELECT * FROM TD_RandomProjectionMinComponents(
    ON { db.table | db.view | (query) } AS InputTable
    USING
        TargetColumns('col1', 'col2', 'col3')         -- required: columns for projection; or range
        Epsilon(0.1)                                  -- optional: distortion tolerance, range (0, 1)
                                                      -- higher value = more distortion, fewer components
                                                      -- default: 0.1
) AS t;
-- Pass the output value as NumComponents in TD_RandomProjectionFit
```

### TD_RandomProjectionFit / TD_RandomProjectionTransform
See the Fit/Transform function section below.

---

# Teradata Data Preparation & Feature Engineering

## Pipeline — Apply Multiple Transforms in One Pass

### TD_ColumnTransformer
Applies multiple Fit/Transform operations to an input table in a single step.
Each FitTable DIMENSION input is optional — include only the transforms needed.
Note: multiple `NonLinearCombineFitTable` instances are allowed; all other FitTable types allow only one.

```sql
SELECT * FROM TD_ColumnTransformer(
    ON { db.table | db.view | (query) } AS InputTable
    ON { db.table | db.view | (query) } AS BincodeFitTable DIMENSION
    ON { db.table | db.view | (query) } AS FunctionFitTable DIMENSION
    ON { db.table | db.view | (query) } AS NonLinearCombineFitTable DIMENSION
    ON { db.table | db.view | (query) } AS OneHotEncodingFitTable DIMENSION
    ON { db.table | db.view | (query) } AS OrdinalEncodingFitTable DIMENSION
    ON { db.table | db.view | (query) } AS OutlierFilterFitTable DIMENSION
    ON { db.table | db.view | (query) } AS PolynomialFeaturesFitTable DIMENSION
    ON { db.table | db.view | (query) } AS RowNormalizeFitTable DIMENSION
    ON { db.table | db.view | (query) } AS ScaleFitTable DIMENSION
    ON { db.table | db.view | (query) } AS SimpleImputeFitTable DIMENSION
    USING
        FillRowIDColumnName('row_id')                 -- optional: adds unique row ID column to output
) AS t;

-- Practical example: impute nulls, scale, and one-hot encode in one operation
SELECT * FROM TD_ColumnTransformer(
    ON db.new_data AS InputTable
    ON db.impute_fit  AS SimpleImputeFitTable DIMENSION
    ON db.scale_fit   AS ScaleFitTable DIMENSION
    ON db.onehot_fit  AS OneHotEncodingFitTable DIMENSION
) AS t;
```

---


## Feature Engineering Patterns

### Lag / Lead Features (Time Series)
```sql
SELECT id, dt, value,
       LAG(value, 1)  OVER (PARTITION BY id ORDER BY dt) AS value_lag1,
       LAG(value, 7)  OVER (PARTITION BY id ORDER BY dt) AS value_lag7,
       LEAD(value, 1) OVER (PARTITION BY id ORDER BY dt) AS value_next
FROM db.timeseries;
```

### Rolling Statistics
```sql
SELECT id, dt, value,
       AVG(value)         OVER (PARTITION BY id ORDER BY dt ROWS BETWEEN 6  PRECEDING AND CURRENT ROW) AS rolling_7d_avg,
       STDDEV_SAMP(value) OVER (PARTITION BY id ORDER BY dt ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS rolling_30d_std
FROM db.timeseries;
```

### Ratio / Interaction Features
```sql
SELECT id,
       revenue / NULLIFZERO(visits)        AS revenue_per_visit,
       clicks  / NULLIFZERO(impressions)   AS ctr,
       (revenue - cost) / NULLIFZERO(cost) AS roi
FROM db.campaign;
```

---
