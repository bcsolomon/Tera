# Teradata Association Analysis Functions

Functions for discovering frequent itemsets, association rules, and
collaborative filtering recommendations from transactional data.

---

## TD_Apriori — Frequent Itemset Mining and Association Rules

Discovers frequent patterns (itemsets) and association rules in transactional data. Classic application is market basket analysis. Supports both dense (items in one delimited cell) and sparse (one row per item) input formats.

```sql
SELECT * FROM TD_Apriori(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]
    [ OUT TABLE OutputTable('db.pattern_table') ]     -- optional; writes output to a named table
    USING
        TargetColumn('item_col')                      -- required; column containing item data; max 1
        [ IDColumn('transaction_id_col') ]            -- required for sparse input; groups items into transactions
        [ PartitionColumns('region_col', 'store_col') ] -- optional; partition input and output; max 10
        [ MaxLen(2) ]                                 -- optional; max itemset size; default 2; max 20
        [ InputDelimiter(',') ]                       -- optional; delimiter for dense input; default ','
                                                      -- only applicable for dense input format
        [ OutputDelimiter(',') ]                      -- optional; delimiter in Itemset output column; default ','
        [ PatternsOrRules('Patterns') ]               -- optional; default 'Patterns'
                                                      --   'Patterns' — frequent itemsets only
                                                      --   'Rules'    — association rules with metrics
                                                      --   'Both'     — patterns and rules
        [ Support(0.01) ]                             -- optional; min itemset frequency as proportion
                                                      -- of total transactions; range (0,1]; default 0.01
) AS t;
```

**Input formats:**

| Format | Description | IDColumn |
|--------|-------------|----------|
| Dense | One row per transaction; items in a single delimited cell in `TargetColumn` | Not used |
| Sparse | One row per item; `IDColumn` groups items into a transaction | Required |

**Output — Patterns** (`PatternsOrRules('Patterns')` or `'Both'`):

| Column | Type | Description |
|--------|------|-------------|
| `partition_column(s)` | ANY | Partition pass-through columns |
| `Itemset` | VARCHAR | Comma-separated (or `OutputDelimiter`) set of items |
| `Support` | REAL | Proportion of transactions containing this itemset |

**Output — Rules** (`PatternsOrRules('Rules')` or `'Both'`):

| Column | Type | Description |
|--------|------|-------------|
| `partition_column(s)` | ANY | Partition pass-through columns |
| `Antecedent` | VARCHAR | The "if" item(s) in the rule |
| `Consequence` | VARCHAR | The "then" item(s) in the rule |
| `Ante_ItemCnt` | — | Item count for antecedent (undocumented in source) |
| `Conse_Item_Cnt` | — | Item count for consequence (undocumented in source) |
| `cntb` | INTEGER | Co-occurrence count of antecedent and consequence |
| `Cnt_Antecedent` | INTEGER | Occurrence count of antecedent |
| `Cnt_Consequence` | INTEGER | Occurrence count of consequence |
| `Score` | REAL | `(cntb²) / (Cnt_Antecedent × Cnt_Consequence)` — product of conditional probabilities |
| `Support` | REAL | `cntb / tran_cnt` — proportion of transactions containing both items |
| `Confidence` | REAL | `cntb / Cnt_Antecedent` — proportion of antecedent transactions that also contain consequence |
| `Lift` | REAL | `support(A∩B) / (support(A) × support(B))` — >1 positive association, =1 independent, <1 negative |
| `Conviction` | REAL | `(1 - Cnt_Consequence/tran_cnt) / (1 - cntb/Cnt_Antecedent)` — implication strength |
| `Leverage` | REAL | Difference between observed co-occurrence and expected if independent |
| `Coverage` | REAL | `Cnt_Antecedent / tran_cnt` — antecedent support (proportion where rule applies) |
| `Chi_Square` | REAL | Chi-squared statistic testing independence of antecedent and consequence |

---

## TD_CFilter — Collaborative Filtering (Pairwise Item Affinity)

Computes co-occurrence statistics for every pair of items across transactions. Simpler than TD_Apriori — always produces pairwise results (no itemsets larger than 2, no rules mode). Typical use: product recommendation, market basket affinity scoring.

```sql
SELECT * FROM TD_CFilter(
    ON { db.table | db.view | (query) } AS InputTable [ PARTITION BY ANY ]
    USING
        TargetColumn('item_col')                      -- required; item column; max 1
        TransactionIDColumns('txn_id_col')            -- required; column(s) grouping items into
                                                      -- a transaction; max 2047 columns
        [ PartitionColumns('region_col') ]            -- optional; partition input and output; max 10
                                                      -- output is nondeterministic unless each
                                                      -- partition_col is unique within TransactionIDColumns
        [ MaxDistinctItems(100) ]                     -- optional; max item set size; default 100
) AS t;
```

**Output columns** (one row per item pair per partition):

| Column | Type | Description |
|--------|------|-------------|
| `partition_column(s)` | ANY | Partition pass-through columns |
| `TD_item1` | VARCHAR | First item in the pair |
| `TD_item2` | VARCHAR | Second item in the pair |
| `cntb` | INTEGER | Co-occurrence count of both items |
| `cnt1` | INTEGER | Occurrence count of item1 |
| `cnt2` | INTEGER | Occurrence count of item2 |
| `score` | REAL | `(cntb²) / (cnt1 × cnt2)` — product of conditional probabilities |
| `support` | REAL | `cntb / tran_cnt` — proportion of transactions containing both items |
| `confidence` | REAL | `cntb / cnt1` — proportion of item1 transactions that also contain item2 |
| `lift` | REAL | `support(A∩B) / (support(A) × support(B))` — >1 positive, =1 independent, <1 negative |
| `z_score` | REAL | `(cntb - mean(cntb)) / sd(cntb)` — co-occurrence significance; not calculated if all `cntb` values are equal |

> **Notes:**
> - Always pairwise — unlike `TD_Apriori`, does not produce itemsets of size > 2 or association rules
> - `TransactionIDColumns` accepts multiple columns (composite transaction key)
> - `z_score` is null/absent when all `cntb` values are equal (sd = 0)

---

# Teradata Vantage ML Functions

## TD_KMeans — Train/Predict

Unsupervised clustering algorithm that groups observations into k clusters by minimizing total within-cluster sum of squares (WCSS). Supports random or KMeans++ centroid initialization, Vector32 UDT input, and SIMD-accelerated distance computation.

**Constraints:**
- InputTable: no PARTITION BY column; PARTITION BY ANY (with optional ORDER BY) is allowed
- `NumClusters` and `InitialCentroidsTable` are mutually exclusive — provide one or the other
- Rows with NULL in any TargetColumn are skipped
- Model persisted via `OUT TABLE ModelTable(...)` clause

> **Elbow method:** `TD_WITHINSS_KMEANS` and `Total_WithinSS` (in `TD_MODELINFO_KMEANS`) expose WCSS per cluster and overall. Run multiple `TD_KMeans` calls with different `NumClusters` values combined with `UNION ALL` to collect WCSS across K values in a single query — then plot WCSS vs K to find the elbow. See `ml-patterns` topic for a full example.

### Train

```sql
SELECT * FROM TD_KMeans(
    ON { db.table | db.view | (query) } AS InputTable   -- no PARTITION BY column; PARTITION BY ANY allowed
    [ ON { db.table | db.view | (query) } AS InitialCentroidsTable DIMENSION ]
    [ OUT [ PERMANENT | VOLATILE ] TABLE ModelTable(db.model_table) ]
    USING
        IdColumn('id_col')                               -- required; unique row identifier
        TargetColumns({ 'col' | col_range }[,...])       -- required; all numeric; NULLs skipped
        [ NumClusters(k) ]                               -- required if no InitialCentroidsTable; mutually exclusive with it
        [ InitialCentroidsMethod('random'|'kmeans++') ]  -- default 'random'; ignored if InitialCentroidsTable provided
        [ NumInit(1) ]                                   -- default 1; repeat with different seeds, return model with lowest WCSS
        [ Seed(seed) ]                                   -- non-negative integer; ignored if InitialCentroidsTable provided
        [ MaxIterNum(10) ]                               -- default 10
        [ StopThreshold(0.0395) ]                        -- default 0.0395; stop when centroid movement < this value
        [ OutputClusterAssignment('false') ]             -- default false; true = row-level assignment output (see below)
        [ DistanceMeasure('Euclidean'|'Cosine') ]        -- default 'Euclidean'
        [ NormalizedVectors('false') ]                   -- default false; only applies when DistanceMeasure='Cosine'
        [ UseSIMD('false') ]                             -- default false; SIMD acceleration for vector distance ops
) AS t;
```

**Output — `OutputClusterAssignment('false')` (default) — centroid-level:**

| Column | Type | Description |
|--------|------|-------------|
| `TD_CLUSTERID_KMEANS` | BIGINT | Cluster identifier |
| `<TargetColumns>` | REAL | Centroid value for each feature |
| `TD_SIZE_KMEANS` | BIGINT | Number of points in this cluster |
| `TD_WITHINSS_KMEANS` | REAL | Within-cluster sum of squares for this cluster |
| `<id_column>` | BYTEINT | Copied from InputTable; always NULL in centroid output |
| `TD_MODELINFO_KMEANS` | VARCHAR(128) | Model summary: Converged, NumIterations, NumClusters, Total_WithinSS, Between_SS, InitialCentroidsMethod |

**Output — `OutputClusterAssignment('true')` — row-level assignment:**

| Column | Type | Description |
|--------|------|-------------|
| `<id_column>` | any | Row identifier from InputTable |
| `TD_CLUSTERID_KMEANS` | BIGINT | Cluster assigned to this row |

**InitialCentroidsTable schema:**

| Column | Type | Description |
|--------|------|-------------|
| `Initial_Clusterid_Column` | BYTEINT/SMALLINT/INTEGER/BIGINT | Unique centroid identifier |
| `<TargetColumns>` | numeric | Initial centroid values; must match TargetColumns in InputTable |

### Predict

```sql
SELECT * FROM TD_KMeansPredict(
    ON { db.table | db.view | (query) } AS InputTable   -- no PARTITION BY column; PARTITION BY ANY allowed
    ON { db.table | db.view | (query) } AS ModelTable DIMENSION  -- must be DIMENSION; no PARTITION BY column
    USING
        [ OutputDistance('false') ]                      -- default false; include distance to assigned centroid
        [ Accumulate({ 'col' | col_range }[,...]) ]
        [ UseSIMD('false') ]                             -- default false; match UseSIMD used in TD_KMeans
) AS t;
```

**Predict output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `<id_column>` | any | Row identifier; carried through from model — no IDColumn argument needed |
| `TD_CLUSTERID_KMEANS` | BIGINT | Cluster assigned to this row |
| `TD_DISTANCE_KMEANS` | REAL | Distance to assigned cluster centroid; only when `OutputDistance('true')` |
| `<accumulate_column(s)>` | any | Columns copied from InputTable |

---


## TD_KNN — K-Nearest Neighbors

Supervised classification and regression using nearest neighbors. **Does not follow the Train/Predict pattern** — KNN is a lazy learner that stores no model. The TrainingTable is passed directly as a DIMENSION input at prediction time; all distance computation happens then. There is no model table to save or reuse.

**Constraints:**
- `InputColumns` must match by **name and datatype** in both TestTable and TrainingTable
- `IDColumn` must be unique in both tables
- `ResponseColumn` class labels must be numeric; required for Classification/Regression; invalid for Neighbors
- `EmitNeighbors` cannot be set to false for `Neighbors` model type
- `OutputProb` and `Responses` are Classification only

```sql
SELECT * FROM TD_KNN(
    ON { db.table | db.view | (query) } AS TestTable PARTITION BY ANY
    ON { db.table | db.view | (query) } AS TrainingTable DIMENSION  -- training data passed directly; no model table
    USING
        IDColumn('id_col')                               -- required; unique identifier in both tables
        InputColumns({ 'col' | col_range }[,...])        -- required; must match by name AND datatype in both tables
        [ ModelType('Classification'|'Regression'|'Neighbors') ]  -- default 'Classification'
        [ K(5) ]                                         -- default 5; range 1–100
        [ ResponseColumn('response_col') ]               -- required for Classification/Regression; invalid for Neighbors
        [ VotingWeight(0) ]                              -- default 0 (uniform); weight = 1/distance^voting_weight
        [ Tolerance(0.0000001) ]                         -- default 0.0000001; distance floor when VotingWeight > 0
        [ OutputProb('false') ]                          -- default false; Classification only
        [ Responses('class1'[,...]) ]                    -- when OutputProb('true'); integer class labels; max 1000
        [ EmitNeighbors('false') ]                       -- default false; always true for Neighbors model type
        [ EmitDistances('false') ]                       -- default false
        [ Accumulate({ 'col' | col_range }[,...]) ]
) AS t;
```

**Output columns:**

| Column | Type | Description |
|--------|------|-------------|
| `id_column` | same as TestTable IDColumn | Test row identifier |
| `prediction` | same as ResponseColumn | Predicted value (Classification/Regression only) |
| `prob` | DOUBLE PRECISION | When `OutputProb('true')` and no `Responses`; probability of predicted class |
| `prob_k` | DOUBLE PRECISION | When `Responses` specified; one column per response class |
| `neighbor_idk` | same as TrainingTable IDColumn | ID of neighbor k; when `EmitNeighbors('true')` |
| `neighbor_distk` | DOUBLE PRECISION | Euclidean distance of neighbor k; when `EmitDistances('true')` |
| `accumulate_column(s)` | same as input | Columns copied from TestTable |

---
