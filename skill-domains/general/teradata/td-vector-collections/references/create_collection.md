# `tdvs_create` — Collection Payload Shapes by Type

Pass `collection_name` as path param, `payload` as JSON body.
When type is ambiguous, see `references/edge_cases.md` → "Ambiguous collection type".

**Global rule:** `target_database` — include only if user explicitly provides it; never ask for it; the service defaults it internally.

---

## FILE-CONTENT-BASED / FILE-EMBEDDING-BASED

```json
{
  "collection_type": "FILE-CONTENT-BASED | FILE-EMBEDDING-BASED",
  "target_database": "<if user provides>",
  "collection_description": "<optional>"
}
```

- FILE-CONTENT-BASED: raw text files (PDF, CSV, JSON, JSONL, Parquet). Models set during `tdvs_ingest_and_update`, not here.
- FILE-EMBEDDING-BASED: files with pre-computed embeddings — **CSV, JSON, JSONL, Parquet only (PDF not supported)**. Do NOT include `embedding_model`.

**Required:** `collection_type` only.

---

## CONTENT-BASED

DB table(s) with text columns to embed. Indexing starts automatically — no separate ingest step.

```json
{
  "collection_type": "CONTENT-BASED",
  "target_database": "<if user provides>",
  "collection_description": "<optional>",
  "collection_index": {
    "collection_type": "CONTENT-BASED",
    "object_names": ["<db>.<table>"],
    "key_columns": ["<primary_key_col>"],
    "key_columns_info": [
      {"name": "<col>", "datatype": "VARCHAR(128)", "description": "<optional>"}
    ],
    "data_columns": ["<text_col>"],
    "data_columns_info": [
      {"name": "<col>", "datatype": "VARCHAR(4000)", "description": "<optional>"}
    ],
    "metadata_columns": ["<filterable_col>"],
    "metadata_columns_info": [
      {"name": "<col>", "datatype": "VARCHAR(512)", "description": "<optional>"}
    ]
  },
  "collection_parameters": {
    "embedding_model": {"model_id": "<chosen>", "model_provider": "<aws|azure|gcp>"},
    "chat_model": {"model_id": "<chosen>", "model_provider": "<aws|azure|gcp>"},
    "train_params": {"search_algorithm": "HNSW", "metric": "cosine"},
    "search_params": {"top_k": 10},
    "search_strategy": {"search_type": "semantic_search", "maximal_marginal_relevance": false}
  }
}
```

**Required:** `collection_type`, `object_names`, `data_columns`
**Optional:** `key_columns`, `target_database`, `collection_description`, `metadata_columns`/`metadata_columns_info`, `collection_parameters` (including `train_params` for index algorithm at creation time)

- Multiple tables: list all in `object_names`. If columns differ per table, ask user.
- Multiple text columns: list all in `data_columns` — all get embedded.
- `*_columns_info`: include only when user provides descriptions or datatypes.

---

## EMBEDDING-BASED

DB table with pre-computed embedding column. Indexing starts automatically — no separate ingest step.

```json
{
  "collection_type": "EMBEDDING-BASED",
  "target_database": "<if user provides>",
  "collection_description": "<optional>",
  "collection_index": {
    "object_names": ["<db>.<table>"],
    "embedding_columns": ["<vector_col>"],
    "key_columns": ["<primary_key_col>"],
    "data_columns": ["<source_text_col>"],
    "metadata_columns": ["<filterable_col>"]
  },
  "collection_parameters": {
    "chat_model": {"model_id": "<chosen>", "model_provider": "<aws|azure|gcp>"},
    "search_params": {"top_k": 5},
    "search_strategy": {"search_type": "semantic_search", "maximal_marginal_relevance": false}
  }
}
```

**Required:** `collection_type`, `object_names`, `embedding_columns`, `data_columns`, `key_columns`
**Do NOT include** `embedding_model` — embeddings are pre-computed.

---

## Questions to ask before `tdvs_create`

**All types:** collection name (per Step 0 in SKILL.md). Models (per `references/model_selection.md`).

**CONTENT-BASED / EMBEDDING-BASED additionally:**
- Which table(s)? (`object_names` as `db.table` or just table name)
- Which column(s) contain text? (`data_columns`)
- Primary key column? (`key_columns`) — optional, ask only if relevant
- (EMBEDDING-BASED) Vector column? (`embedding_columns`)
- Filterable columns? (`metadata_columns`) — ask only if user mentions filtering
