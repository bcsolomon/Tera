# Teradata Data Preparation & Feature Engineering

## Encoding Categorical Variables

### One-Hot Encoding (Manual)
```sql
SELECT id,
       CASE WHEN category = 'A' THEN 1 ELSE 0 END AS cat_A,
       CASE WHEN category = 'B' THEN 1 ELSE 0 END AS cat_B,
       CASE WHEN category = 'C' THEN 1 ELSE 0 END AS cat_C
FROM db.table;
```

### Label / Ordinal Encoding (Manual)
```sql
SELECT id, category,
       DENSE_RANK() OVER (ORDER BY category) - 1 AS category_encoded
FROM db.table;
```

### TD_OneHotEncodingFit / TD_OneHotEncodingTransform
### TD_OrdinalEncodingFit / TD_OrdinalEncodingTransform
### TD_TargetEncodingFit / TD_TargetEncodingTransform
See the Fit/Transform function section below.

---



## Reshaping

### Unpivot (Wide → Long) — Manual
```sql
SELECT id, 'jan' AS month, jan_sales AS sales FROM db.t
UNION ALL
SELECT id, 'feb', feb_sales FROM db.t
UNION ALL
SELECT id, 'mar', mar_sales FROM db.t;
```

### TD_Unpivoting (Wide → Long)
```sql
-- Basic unpivot
SELECT * FROM TD_Unpivoting(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    USING
        IDColumn('id_col')                            -- required: identifier column
        TargetColumns('jan_sales', 'feb_sales',
                      'mar_sales')                    -- required: columns to unpivot; or range e.g. '[2:4]'
        AttributeColName('month')                     -- optional: name for attribute column
                                                      -- default: 'AttributeName'
        ValueColName('sales')                         -- optional: name for value column
                                                      -- default: 'AttributeValue'
        AttributeAliasList('January', 'February',
                           'March')                   -- optional: friendly names for TargetColumns
                                                      -- must match count of TargetColumns
        Accumulate('region_col')                      -- optional: columns or range to pass through
        IncludeNulls('false')                         -- optional: include NULL values; default: 'false'
) AS t;

-- Advanced options
SELECT * FROM TD_Unpivoting(
    ON { db.table | db.view | (query) } AS InputTable PARTITION BY ANY
    USING
        IDColumn('id_col')
        TargetColumns('col1', 'col2', 'col3')         -- or range e.g. '[1:5]'
        InputTypes('true')                            -- optional: output multiple typed value columns
                                                      -- instead of single AttributeValue column
                                                      -- default: 'false'
        OutputVarchar('true')                         -- optional: cast AttributeValue to VARCHAR
                                                      -- default: 'false'; not used with InputTypes
        IndexedAttribute('false')                     -- optional: use column index instead of name
                                                      -- default: 'false'
        IncludeDataTypes('false')                     -- optional: add column with original data type
                                                      -- default: 'false'
) AS t;
```

### Pivot (Long → Wide) — Manual
```sql
SELECT id,
       SUM(CASE WHEN month = 'jan' THEN sales END) AS jan,
       SUM(CASE WHEN month = 'feb' THEN sales END) AS feb,
       SUM(CASE WHEN month = 'mar' THEN sales END) AS mar
FROM db.long_table
GROUP BY id;
```

### TD_Pivoting (Long → Wide)
```sql
-- Mode 1: PivotColumn — a column contains the pivot keys (most common)
SELECT * FROM TD_Pivoting(
    ON { db.table | db.view | (query) } AS InputTable
        PARTITION BY id_col
        ORDER BY category_col
    USING
        PartitionColumns('id_col')                    -- must match PARTITION BY; list or range
        TargetColumns('value_col')                    -- columns to pivot; list or range
        PivotColumn('category_col')                   -- column whose values become new column headers
        PivotKeys('A', 'B', 'C')                      -- which values to pivot (others ignored)
        PivotKeysAlias('cat_a', 'cat_b', 'cat_c')     -- optional: rename pivot key output columns
        DefaultPivotValues('0', '0', '0')             -- optional: fill value when pivot key is absent
        Accumulate('name_col')                        -- optional: pass-through cols; list or range
        OutputColumnNames('id', 'name', 'cat_a',
                          'cat_b', 'cat_c')           -- optional: rename all output columns
) AS t;

-- Mode 2: RowsPerPartition — no pivot key column; spread N rows into N columns
-- ORDER BY is required to ensure deterministic output
SELECT * FROM TD_Pivoting(
    ON { db.table | db.view | (query) } AS InputTable
        PARTITION BY id_col
        ORDER BY seq_col
    USING
        PartitionColumns('id_col')                    -- list or range
        TargetColumns('value_col')                    -- list or range
        RowsPerPartition(4)                           -- max rows to pivot (1-2047 without aggregation)
                                                      -- NULLs added if partition has fewer rows
                                                      -- extra rows omitted if partition has more
) AS t;

-- Mode 3: Aggregation only — no RowsPerPartition or PivotColumn
SELECT * FROM TD_Pivoting(
    ON { db.table | db.view | (query) } AS InputTable
        PARTITION BY id_col
    USING
        PartitionColumns('id_col')                    -- list or range
        TargetColumns('amount', 'quantity')           -- list or range
        Aggregation('SUM')                            -- single aggregation for all target columns
        -- or per-column: Aggregation('amount:SUM', 'quantity:MAX')
        -- options: CONCAT, UNIQUE_CONCAT, SUM, MIN, MAX, AVG
) AS t;

-- CONCAT/UNIQUE_CONCAT additional options
SELECT * FROM TD_Pivoting(
    ON { db.table | db.view | (query) } AS InputTable
        PARTITION BY id_col
    USING
        PartitionColumns('id_col')                    -- list or range
        TargetColumns('tag_col')                      -- list or range
        Aggregation('CONCAT')
        Delimiters('|')                               -- optional: default ','; or per-column 'tag_col:|'
        CombinedColumnSizes(64000)                    -- optional: default 64000 (VARCHAR)
                                                      -- use >64000 for CLOB output
        TruncateColumns('tag_col')                    -- optional: list or range; truncate if over size
) AS t;
```

---

---

# Teradata Fit/Transform Pattern

Many Teradata native analytic functions follow a two-phase pattern:

- **Fit**: Runs against training data and outputs a "model" — a result set of learned parameters.
- **Transform**: Takes new input data plus the Fit output, applies the learned transformation.

This separation allows the model to be trained once and reused across many datasets, environments,
or time periods without re-running the Fit step.

---

## Model Storage Options

The output of a Fit function is a standard result set and can be stored or passed in three ways:

### 1. Dedicated table per model
```sql
-- Store the Fit output as its own table
CREATE TABLE db.my_model AS (
    SELECT * FROM TD_SomeFit(
        ON db.training_data AS InputTable PARTITION BY ANY
        USING TargetColumns('col1', 'col2')
    ) AS t
) WITH DATA;

-- Reference it in Transform
SELECT * FROM TD_SomeTransform(
    ON db.new_data AS InputTable PARTITION BY ANY
    ON db.my_model AS ModelTable DIMENSION
    USING TargetColumns('col1', 'col2')
) AS t;
```

### 2. Shared model registry table (governed workflow)
```sql
-- Insert multiple Fit results into a central registry with a model identifier
INSERT INTO db.model_registry
SELECT 'outlier_model_v1' AS model_id, t.*
FROM TD_SomeFit(
    ON db.training_data AS InputTable PARTITION BY ANY
    USING TargetColumns('col1', 'col2')
) AS t;

-- Transform filters the registry by model_id
SELECT * FROM TD_SomeTransform(
    ON db.new_data AS InputTable PARTITION BY ANY
    ON (SELECT * FROM db.model_registry
        WHERE model_id = 'outlier_model_v1') AS ModelTable DIMENSION
    USING TargetColumns('col1', 'col2')
) AS t;
```

This pattern enables enterprise ML governance:
- Models treated as first-class data assets
- Full lineage, versioning, and history in a single table
- Swap model versions by changing the filter — no code changes needed

### 3. Inline subquery (no persistence)
```sql
-- Pass the Fit result directly into Transform as a subquery
SELECT * FROM TD_SomeTransform(
    ON db.new_data AS InputTable PARTITION BY ANY
    ON (
        SELECT * FROM TD_SomeFit(
            ON db.training_data AS InputTable PARTITION BY ANY
            USING TargetColumns('col1', 'col2')
        ) AS t
    ) AS ModelTable DIMENSION
    USING TargetColumns('col1', 'col2')
) AS t;
```

Useful for one-off transformations where persisting the model is not needed.

---

## Known Fit/Transform Pairs

| Fit | Transform | Purpose |
|-----|-----------|---------|
| `TD_OutlierFilterFit` | `TD_OutlierFilterTransform` | Detect and remove outliers |
| `TD_SimpleImputeFit` | `TD_SimpleImputeTransform` | Impute missing values |
| `TD_ScaleFit` | `TD_ScaleTransform` | Normalize / scale numeric columns |

---

## Key Notes

- The Fit output schema must match what the Transform function expects on its `ModelTable` input.
- The `ModelTable` ON clause always takes `DIMENSION` — this tells Teradata the model is a small
  broadcast table, not a partitioned input.
- When using a shared registry, ensure the filter on `ModelTable` returns rows for only one model —
  mixing model rows will produce incorrect results.
