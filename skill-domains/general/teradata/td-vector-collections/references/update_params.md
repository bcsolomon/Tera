# Update Operations — Payload Reference

All update operations call `tdvs_update` (PATCH) unless noted otherwise. Always warn user before operations that trigger a full rebuild (re-embeds all data).

> **Critical:** `tdvs_update` requires two parameters: `collection_name` (string) and `payload` (JSON string). The payload examples below show the JSON object that must be **serialized as a string** and passed as the `payload` parameter — do NOT pass `collection_index` or `collection_parameters` as direct top-level parameters.
>
> Full `teradata_tool_call` example — note 3 opening and 3 closing braces in the payload string:
> ```json
> {"input": {"name": "tdvs_update", "parameters": {"collection_name": "finance_reports", "payload": "{\"collection_parameters\":{\"search_strategy\":{\"search_type\":\"HYBRID_SEARCH\"}}}"}}} 
> ```
> ⚠️ Count `{` and `}` inside the payload string — they must match. Three levels of nesting = three `{` and three `}`.

| Operation | Triggers rebuild? |
| --------- | --------------------- |
| Change `embedding_model` | **Yes** — re-embeds all data |
| Change `train_params` | **Yes** — re-indexes all data |
| Switch to `HYBRID_SEARCH` | No |
| Add / delete files or tables | No (incremental) |
| Change `chat_model` only | No |
| Metadata column ops | No |
| Rename / change description | No |

> **Important:** `train_params` must be nested inside `collection_parameters` (not top-level). `update_style` is **not** a valid `tdvs_update` parameter — do not include it.

---

## Collection Metadata

These are **top-level** payload keys (siblings of `collection_index` / `collection_parameters` - do NOT nest them). No rebuild.

### Rename collection

```json
{"new_collection_name": "new_name"}
```

### Change description

```json
{"collection_description": "new description text"}
```

---

## Data Operations

### Add files (FILE-CONTENT-BASED / FILE-EMBEDDING-BASED)

Tool: `tdvs_ingest_and_update` (not `tdvs_update`) — handles both ingestion and indexing in one call. See `references/ingest_params.md` for full payload shape.

### Delete files

```json
{"collection_index": {"alter_operation": "DELETE", "file_names": ["report.pdf", "old.pdf"]}}
```

### Add a table (CONTENT-BASED / EMBEDDING-BASED)

```json
{
  "collection_index": {
    "alter_operation": "ADD",
    "object_names": ["db.table"],
    "key_columns": ["id_col"],
    "data_columns": ["text_col"],
    "metadata_columns": ["optional_filter_col"]
  }
}
```

### Delete a table

```json
{"collection_index": {"alter_operation": "DELETE", "object_names": ["db.old_table"]}}
```

### Delete rows by ID (staging table)

```json
{"collection_index": {"alter_operation": "DELETE", "object_names": ["staging.ids_to_remove"]}}
```

---

## Model Changes

### Chat model only (no rebuild needed)

```json
{"collection_parameters": {"chat_model": {"model_id": "...", "model_provider": "aws", "max_tokens": 4000, "temperature": 0.2}}}
```

Omit fields the user didn't specify — don't zero them out.

### Embedding model (triggers full rebuild — confirm with user first)

```json
{"collection_parameters": {"embedding_model": {"model_id": "...", "model_provider": "aws"}}}
```

For Teradata-hosted models: add `"base_url": "http://td-host:9000"` and `"embedding_dims": 768` inside the model object.

---

## Search Strategy Changes

See `references/search_params.md` for search type behavior details.

### Switch to hybrid search (collection update required)

```json
{"collection_parameters": {"search_strategy": {"search_type": "HYBRID_SEARCH", "scoring_method": "weighted_rrf", "sparse_weight": 0.5, "rrf_normalizer": 60}}}
```

Only include `scoring_method`, `sparse_weight`, `rrf_normalizer` if user specifies them.

---

## Index / Algorithm Changes

`train_params` must be nested inside `collection_parameters`. Include only the fields the user specified — omit the rest. These changes trigger a full re-index — warn user first.

### Switch to HNSW with cosine

```json
{"collection_parameters": {"train_params": {"search_algorithm": "HNSW", "metric": "COSINE"}}}
```

### Tune HNSW params

```json
{"collection_parameters": {"train_params": {"search_algorithm": "HNSW", "metric": "COSINE", "num_layer": -1, "ef_construction": 32, "num_connPerNode": 32, "maxNum_connPerNode": 32, "num_NodesPerGraph": 10, "seed": 0, "apply_heuristics": true}}}
```

Available HNSW fields (include only what user specifies):
- `metric`: `"COSINE"`, `"DOT_PRODUCT"`, `"EUCLIDEAN"`
- `num_layer`: number of layers (-1 = auto)
- `ef_construction`: build-time search width (higher = better quality, slower build)
- `ef_search`: query-time search width (higher = better recall, slower search)  
- `num_connPerNode` / `maxNum_connPerNode`: connections per node
- `num_NodesPerGraph`: nodes per graph
- `seed`: random seed
- `apply_heuristics`: enable/disable heuristics

### Regenerate embeddings only (no index rebuild)

Tool: `tdvs_generate_embeddings` — requires two parameters: `collection_name` (string) and `payload` (JSON string).

```json
{"embedding_model": {"model_id": "amazon.titan-embed-text-v2:0"}}
```

### Rebuild index only (embeddings already current)

Tool: `tdvs_create_index` — requires two parameters: `collection_name` (string) and `payload` (JSON string).

```json
{"train_params": {"search_algorithm": "HNSW", "metric": "COSINE", "num_layer": 6, "ef_construction": 15, "num_connPerNode": 32, "maxNum_connPerNode": 32}, "search_params": {"top_k": 10, "ef_search": 32}}
```

Pass `"{}"` if user does not specify algorithm params.

---

## Metadata Column Changes

### Add filterable columns

```json
{"collection_index": {"metadata_operation": "ADD", "metadata_columns": ["page_number"], "metadata_columns_info": [{"name": "page_number", "datatype": "INTEGER"}]}}
```

Supported datatypes: `VARCHAR`, `INTEGER`, `FLOAT`, `DATE`

### Remove filterable columns

```json
{"collection_index": {"metadata_operation": "DELETE", "metadata_columns_info": [{"name": "old_tag", "datatype": "VARCHAR"}]}}
```

### Update column description

```json
{"collection_index": {"metadata_operation": "MODIFY", "metadata_columns_info": [{"name": "page_number", "datatype": "INTEGER", "description": "Page number of the pdf file"}]}}
```