# Analytic Functions Catalog — Data Preparation & Path/Pattern Discovery

All Teradata Vantage analytic functions use the table operator invocation pattern:

```sql
SELECT * FROM FunctionName (
    ON input_table [AS InputRole]
    [ON ref_table AS RefRole DIMENSION]
    [PARTITION BY col | ORDER BY col]
    USING
        Param1('value1')
        Param2('value2')
) AS alias;
```

---

## Data Preparation Functions

### Antiselect — Exclude Columns

```sql
SELECT * FROM Antiselect (
    ON input_table
    USING
        ExcludeColumns('col_to_drop1', 'col_to_drop2')
) AS t;
```

### Pack — Combine Columns into Single Column

```sql
SELECT * FROM Pack (
    ON input_table
    USING
        InputColumns('col1', 'col2', 'col3')
        OutputColumn('packed_col')
        Delimiter(',')
) AS t;
```

### Unpack — Split Column into Multiple

```sql
SELECT * FROM Unpack (
    ON input_table
    USING
        InputColumn('packed_col')
        OutputColumns('col1', 'col2', 'col3')
        OutputDataTypes('VARCHAR(50)', 'INTEGER', 'FLOAT')
        Delimiter(',')
) AS t;
```

### Pivot — Rows to Columns

```sql
SELECT * FROM Pivot (
    ON input_table
    PARTITION BY group_col
    USING
        PartitionColumns('group_col')
        TargetColumns('value_col')
        PivotColumn('category_col')
        PivotKeys('cat_A', 'cat_B', 'cat_C')
) AS t;
```

### Unpivot — Columns to Rows

```sql
SELECT * FROM Unpivot (
    ON input_table
    USING
        UnpivotColumns('jan_sales', 'feb_sales', 'mar_sales')
        AttributeColumn('month')
        ValueColumn('sales_amount')
        InputTypes('false')        -- don't include type column
) AS t;
```

### Scale — Normalize Values

```sql
SELECT * FROM Scale (
    ON input_table
    USING
        TargetColumns('feature1', 'feature2')
        ScaleMethod('RANGE')       -- RANGE, MIDRANGE, MEAN, MAXABS, ZSCORE, RESCALE
        MissValue('KEEP')          -- KEEP, OMIT, ZERO, LOCATION
) AS t;
```

### Sessionize — Session Detection

```sql
SELECT * FROM Sessionize (
    ON clickstream_data
    PARTITION BY user_id
    ORDER BY event_time
    USING
        TimeColumn('event_time')
        TimeOut(1800)              -- 30 min session gap
) AS t;
-- Adds session_id column to output
```

### Sampling — Random Sampling

```sql
-- Fraction-based
SELECT * FROM Sampling (
    ON input_data
    USING
        SampleFraction('0.1')      -- 10% sample
) AS t;

-- Count-based
SELECT * FROM Sampling (
    ON input_data
    USING
        NumSample('1000')          -- 1000 rows
) AS t;

-- Stratified
SELECT * FROM Sampling (
    ON input_data
    PARTITION BY stratum_col
    USING
        SampleFraction('0.05')
) AS t;
```

### Categorize — Bin Values

```sql
SELECT * FROM Categorize (
    ON input_table
    USING
        TargetColumn('age')
        CategoryColumn('age_group')
        CategoryBoundaries('18', '25', '35', '45', '55', '65')
) AS t;
```

### Outlier Filter

```sql
SELECT * FROM OutlierFilter (
    ON input_table
    USING
        TargetColumns('value_col')
        PercentageThreshold('0.01')    -- Remove top/bottom 1%
) AS t;
```

---

## Path & Pattern Discovery Functions

### nPath — Sequential Pattern Matching

```sql
SELECT * FROM nPath (
    ON event_data
    PARTITION BY session_id
    ORDER BY event_time
    USING
        Mode(NONOVERLAPPING)           -- or OVERLAPPING
        Pattern('A+.B+.C')
        Symbols(
            page_type = 'home' AS A,
            page_type = 'product' AS B,
            page_type = 'cart' AS C
        )
        Result(
            FIRST(A.session_id) AS session_id,
            FIRST(A.event_time) AS start_time,
            LAST(C.event_time) AS end_time,
            COUNT(B.*) AS product_views,
            ACCUMULATE(B.page_name) AS products
        )
) AS paths;
```

#### nPath Pattern Syntax

| Symbol | Meaning |
|---|---|
| `A` | Single occurrence of symbol A |
| `A+` | One or more occurrences |
| `A*` | Zero or more occurrences |
| `A?` | Zero or one occurrence |
| `.` | Concatenation (then) |
| `A\|B` | A or B |
| `A{3}` | Exactly 3 occurrences |
| `A{2,5}` | 2 to 5 occurrences |

#### nPath Result Functions

| Function | Description |
|---|---|
| `FIRST(A.col)` | First value in symbol A's matches |
| `LAST(A.col)` | Last value in symbol A's matches |
| `COUNT(A.*)` | Count of A matches |
| `ACCUMULATE(A.col)` | Array of all values |
| `MAX(A.col)` | Maximum value |
| `MIN(A.col)` | Minimum value |
| `AVG(A.col)` | Average value |
| `SUM(A.col)` | Sum value |

### Attribution — Channel Attribution

```sql
SELECT * FROM Attribution (
    ON conversion_events
    PARTITION BY user_id
    ORDER BY event_time
    USING
        ConversionEvent('event_type = ''purchase''')
        TimestampColumn('event_time')
        WindowSize('rows:10 & seconds:864000')   -- 10 days
        Model1('SEGMENT_ROWS:3', 'EXPONENTIAL:0.5')
        -- Models: SIMPLE, UNIFORM, EXPONENTIAL, WEIGHTED, FIRST_TOUCH, LAST_TOUCH
) AS attr;
```

### FP Growth — Frequent Pattern Mining

```sql
SELECT * FROM FPGrowth (
    ON transaction_items
    PARTITION BY transaction_id
    USING
        ItemColumn('item_name')
        MinSupport('0.01')         -- 1% minimum support
        MaxPatternLength(5)
) AS patterns;
```

### Path Generator / Summarizer / Starter

```sql
-- Generate paths
SELECT * FROM PathGenerator (
    ON event_data
    PARTITION BY session_id
    ORDER BY event_time
    USING
        SeqColumn('page_name')
) AS paths;

-- Summarize paths
SELECT * FROM PathSummarizer (
    ON PathGenerator(...)
    PARTITION BY 1
    USING
        SeqColumn('path')
        CountColumn('cnt')
        HashCode('true')
) AS summary;
```

ML, Text, Time Series, Graph, and Geometry functions are in the [ML/Text/Graph reference](./analytic-functions-ml-text-graph.md).
