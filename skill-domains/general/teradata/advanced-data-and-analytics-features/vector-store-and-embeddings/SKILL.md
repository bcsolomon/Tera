---
name: teradata-vector-embeddings
description: 'Use Teradata vector functions for embedding generation, vector normalization, exact and approximate nearest-neighbor search, and production RAG retrieval pipelines.'
metadata:
    author: teradata
    version: "1.0"
---

# Teradata Vector Search & Embeddings

> **Skill:** teradata-vector-embeddings  
> **Domain:** 12-advanced-data-and-analytics-features / 07-vector-store-and-embeddings  
> **Applies to:** Teradata Vantage 20.0+, VantageCloud Lake  

---

## Purpose

Guide agents through vector similarity search, embedding generation, and RAG (retrieval-augmented generation) pipelines using native Teradata functions. All vector operations run distributed across AMPs.

---

## When to Use

- Semantic search / document retrieval
- RAG pipelines — embed query, search corpus, return context
- Recommendation systems via similarity scoring
- Anomaly detection via vector distance
- Building and querying vector stores

---

## Core Functions

| Function | Purpose | Scale |
|----------|---------|-------|
| `TD_VectorDistance` | Exact pairwise distance (cosine, euclidean, manhattan) | Small-medium tables (O(N²)) |
| `TD_HNSW` | Build approximate nearest-neighbor index | Large-scale (millions of vectors) |
| `TD_HNSWPredict` | Search HNSW index for top-K neighbors | Fast approximate search |
| `TD_HNSWSummary` | Inspect a built HNSW index | Diagnostic |
| `AI_TEXTEMBEDDINGS` | Generate embeddings via cloud LLM | Text → vector |
| `ONNXEmbeddings` | Generate embeddings via in-database ONNX model | Text → vector (no cloud) |
| `TD_WordEmbeddings` | Static word/document embeddings (GloVe) | Token/document → vector |
| `TD_VectorNormalize` | L2 normalize vectors to unit length | Required pre-processing |

---

## Distance Measures

| Measure | Range | Best For |
|---------|-------|----------|
| `Cosine` | [0, 2] | Embeddings (direction matters); normalize first |
| `Euclidean` | [0, ∞) | Spatial data, clusters |
| `Manhattan` | [0, ∞) | Sparse features |

---

## Semantic Search (Exact)

```sql
SELECT * FROM TD_VectorDistance(
    ON db.document_embeddings AS TargetTable PARTITION BY ANY
    ON db.query_embedding AS ReferenceTable DIMENSION
    USING
        TargetIDColumn('doc_id')
        TargetFeatureColumns('embedding')    -- VECTOR column
        RefIDColumn('query_id')
        RefFeatureColumns('embedding')
        DistanceMeasure('Cosine')
        TopK(10)
) AS t
ORDER BY Distance ASC;
```

---

## HNSW Index (Approximate — Large Scale)

### Build Index

```sql
SELECT * FROM TD_HNSW(
    ON db.corpus_embeddings AS InputTable
    OUT PERMANENT TABLE ModelTable(db.hnsw_index)
    USING
        IdColumn('doc_id')
        VectorColumn('embedding')
        DistanceMeasure('cosine')
        EfConstruction(64)         -- higher = better recall, slower build
        NumConnPerNode(32)
) AS t;
```

### Search Index

```sql
SELECT * FROM TD_HNSWPredict(
    ON db.query_vectors AS InputTable
    ON db.hnsw_index AS ModelTable DIMENSION
    USING
        IdColumn('query_id')
        VectorColumn('embedding')
        TopK(10)
        EfSearch(100)              -- higher = better recall, slower search
) AS t;
```

---

## Full RAG Pipeline (Inline)

Embed query → normalize → search corpus — all in one SQL statement:

```sql
WITH query_emb AS (
    SELECT 1 AS query_id, embedding
    FROM TD_SYSFNLIB.AI_TEXTEMBEDDINGS(
        ON (SELECT 1 AS id, 'What is Teradata partitioning?' AS text_input) AS InputTable
        USING
            ApiType('azure')
            AUTHORIZATION(db.my_auth)
            ModelName('text-embedding-ada-002')
            TextColumn('text_input')
    ) AS t
),
query_norm AS (
    SELECT * FROM TD_VectorNormalize(
        ON query_emb AS InputTable PARTITION BY ANY
        USING
            IDColumns('query_id')
            TargetColumns('embedding')
            Approach('UNITVECTOR')
    ) AS t
)
SELECT * FROM TD_VectorDistance(
    ON db.corpus_embeddings AS TargetTable PARTITION BY ANY
    ON query_norm AS ReferenceTable DIMENSION
    USING
        TargetIDColumn('doc_id')
        TargetFeatureColumns('embedding')
        RefIDColumn('query_id')
        RefFeatureColumns('embedding')
        DistanceMeasure('Cosine')
        TopK(5)
) AS t
ORDER BY Distance ASC;
```

---

## Discovering Existing Vector Stores

Always check what exists before building new embeddings:

```sql
-- List vector stores and their embedding models
SELECT * FROM TD_SYSAI.TD_VectorStores ORDER BY StoreName;

-- Get model name and embedding size (must match at query time)
SELECT CollectionName, ModelName, APIType, EmbeddingSize
FROM TD_SYSAI.TD_CollectionsV
WHERE CollectionName = '<your_collection>';
```

> **Critical:** The embedding model used at corpus build time MUST match the model used at query time. Mismatched embeddings produce meaningless similarity scores.

---

## Vector Dimension Introspection

```sql
-- Get dimensions from a VECTOR column (never infer from byte size)
SELECT embedding.LENGTH() AS dims FROM db.embeddings SAMPLE 1;
```

---

## Embedding Generation

### Cloud LLM (AI_TEXTEMBEDDINGS)

```sql
SELECT * FROM TD_SYSFNLIB.AI_TEXTEMBEDDINGS(
    ON db.documents AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.my_auth)
        ModelName('text-embedding-ada-002')
        TextColumn('content')
        Accumulate('doc_id')
) AS t;
```

### In-Database ONNX (ONNXEmbeddings)

```sql
SELECT * FROM mldb.ONNXEmbeddings(
    ON db.documents AS InputTable
    ON db.onnx_model AS ModelTable DIMENSION
    ON db.tokenizer AS TokenizerTable DIMENSION
    USING Accumulate('doc_id')
) AS t;
```

See [references/embeddings.md](references/embeddings.md) for full syntax.

---

## Corpus Build Workflow

1. Source text table → `AI_TEXTEMBEDDINGS` (generate vectors)
2. → `TD_VectorNormalize(Approach('UNITVECTOR'))` (L2 normalize)
3. → `CREATE TABLE AS (...) WITH DATA` (persist corpus)
4. Optional: `TD_HNSW` → build approximate index for fast search

---

## Common Pitfalls

| Mistake | Fix |
|---------|-----|
| Skipping normalization before cosine search | Always `TD_VectorNormalize(Approach('UNITVECTOR'))` |
| Mismatched embedding models between corpus and query | Check `TD_SYSAI.TD_CollectionsV` for corpus model |
| Using `TopK(-1)` on large tables | Use `TD_HNSW` for approximate search at scale |
| Inferring dimensions from byte size | Use `embedding.LENGTH()` |

---

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-vector-embeddings", path="references/FILENAME")` — do NOT call `list`.

| File | Content |
|------|---------|
| [vector-search.md](references/vector-search.md) | Full syntax: TD_VectorDistance, TD_HNSW, TD_HNSWPredict, Update/Delete, inline RAG pipeline |
| [embeddings.md](references/embeddings.md) | AI_TEXTEMBEDDINGS, ONNXEmbeddings, TD_WordEmbeddings, corpus build workflow |

*Source: Teradata tdsql-mcp syntax library (ksturgeon-td/tdsql-mcp)*
