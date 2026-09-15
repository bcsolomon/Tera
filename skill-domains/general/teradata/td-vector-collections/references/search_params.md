# Ask / Similarity Search — Payload Reference

---

## Full `teradata_tool_call` examples — copy these patterns exactly

### Hybrid search with file filter (most common complex call):
```json
{"input":{"name":"tdvs_ask","parameters":{"collection_name":"finance_reports","payload":"{\"question\":\"What were QCT revenues?\",\"search_strategy\":{\"search_type\":\"HYBRID_SEARCH\"},\"filter_params\":{\"condition\":{\"key\":\"filename\",\"match\":{\"like\":\"Qualcomm\"}},\"style\":\"PRE-FILTERING\"}}"}}}
```

### Simple ask (no filter, no search strategy):
```json
{"input":{"name":"tdvs_ask","parameters":{"collection_name":"finance_reports","payload":"{\"question\":\"What was Meta revenue in Q1?\"}"}}}
```

### Ask with search strategy only (no filter):
```json
{"input":{"name":"tdvs_ask","parameters":{"collection_name":"finance_reports","payload":"{\"question\":\"What were earnings?\",\"search_strategy\":{\"search_type\":\"HYBRID_SEARCH\"}}"}}}
```

### Similarity search with filter:
```json
{"input":{"name":"tdvs_similarity_search","parameters":{"collection_name":"finance_reports","payload":"{\"question\":\"cloud ARR growth\",\"search_params\":{\"top_k\":5},\"filter_params\":{\"condition\":{\"key\":\"filename\",\"match\":{\"like\":\"Teradata\"}},\"style\":\"PRE-FILTERING\"}}"}}}
```

> ⚠️ Count `{` and `}` inside the payload string — they MUST be equal. The hybrid+filter example above has 5 opening and 5 closing braces in the payload.

---

## Search type behavior

**If user specifies a search type, always pass `search_strategy.search_type` in the payload — do not fall back to collection defaults.** Also pass any type-specific params the user provides. Omit `search_strategy` only when user does not mention a search type.

- **`SEMANTIC_SEARCH`** — default. No special handling.
- **`RELEVANCE_SEARCH`** — works on any collection. Optional params: `relevance_top_k`, `relevance_search_threshold`.
- **`HYBRID_SEARCH`** — requires collection configured for hybrid. If not configured, inform user and offer to update or use semantic/relevance instead. Wait for confirmation before calling `tdvs_update`. Optional params: `scoring_method` (`"weighted_sum"`, `"rrf"`, or `"weighted_rrf"`), `sparse_weight`, `rrf_normalizer`.

---

## Payload structure

```json
{
  "question": "...",
  "search_params": {
    "top_k": 5
  },
  "search_strategy": {
    "search_type": "SEMANTIC_SEARCH | HYBRID_SEARCH | RELEVANCE_SEARCH",
    "maximal_marginal_relevance": false,
    "lambda_multiplier": 0.5
  },
  "filter_params": {
    "condition": {"key": "<col>", "match": {"value": "<val>"}},
    "style": "PRE-FILTERING"
  },
  "embedding_model": {"model_id": "...", "model_provider": "aws"},
  "ranking_model": {"model_id": "...", "model_provider": "aws"},
  "chat_model": {"model_id": "...", "model_provider": "aws", "max_tokens": 500, "temperature": 0.3}
}
```

> **Only include fields the user explicitly requests or that are required.** Service has sensible defaults for everything else.

**Note:** `embedding_model` at query time is **required** for `FILE-EMBEDDING-BASED` / `EMBEDDING-BASED` collections. `question_vector` can replace `question` to search by a pre-computed vector directly.

---

## Field reference

| Field | Where | Include when |
|-------|-------|--------------|
| `question` | top-level | Required (or use `question_vector`) |
| `question_vector` | top-level | User provides a raw embedding vector to search by — **must be a JSON-serialized string, e.g. `"[0.1, 0.2, ...]"`** |
| `search_params.top_k` | nested | User explicitly requests a result count |
| `search_params.search_threshold` | nested | User explicitly requests a confidence floor |
| `search_strategy.search_type` | nested | **Must include when user specifies a search type** — "semantic" → `SEMANTIC_SEARCH`, "hybrid" → `HYBRID_SEARCH`, "relevance" → `RELEVANCE_SEARCH`. Omit only when user doesn't mention one. |
| `search_strategy.sparse_weight` | nested | Hybrid only — if user provides a value |
| `search_strategy.scoring_method` | nested | Hybrid only — `"weighted_sum"` (default), `"rrf"`, or `"weighted_rrf"` |
| `search_strategy.rrf_normalizer` | nested | Hybrid only — if user provides a value (used with `weighted_rrf`) |
| `search_strategy.relevance_top_k` | nested | Relevance only — if user provides a value |
| `search_strategy.relevance_search_threshold` | nested | Relevance only — if user provides a value |
| `search_strategy.maximal_marginal_relevance` | nested | User mentions "diverse" or "varied" results |
| `search_strategy.lambda_multiplier` | nested | Only with MMR — 0.0 = max diversity, 1.0 = max relevance |
| `filter_params` | top-level | User filters by a field value |
| `embedding_model` | top-level | **Required** for `FILE-EMBEDDING-BASED` / `EMBEDDING-BASED` collections (converts question text to vector) |
| `ranking_model` | top-level | User mentions reranking — call `tdvs_list_available_models` first |
| `chat_model` | top-level | Per-query model/temp/tokens override (`tdvs_ask` / `tdvs_prepare_response` only) |

---

## Filter conditions

> **Before filtering — get the real column names first:** Call `tdvs_get_details` with `get_details=true` (pass a boolean `true`) and read the `metadata_columns` list it returns. Use one of those exact names as the filter `key`. If the column you need isn't in that list, offer to add it via `tdvs_update` or proceed without the filter.

All examples use `"style": "PRE-FILTERING"` (default). Use `"POST-FILTERING"` for better recall at cost of possibly fewer than `top_k` results.

```json
// Exact match
{"condition": {"key": "category", "match": {"value": "electronics"}}, "style": "PRE-FILTERING"}

// LIKE — no % wildcards (service wraps automatically)
{"condition": {"key": "title", "match": {"like": "policy"}}, "style": "PRE-FILTERING"}

// Numeric range — use "range" not "match"; combine operators in one dict
{"condition": {"key": "price", "range": {"gte": 20, "lte": 100}}, "style": "PRE-FILTERING"}

// AND
{"condition": {"and": [{"key": "category", "match": {"value": "electronics"}}, {"key": "year", "range": {"gt": 2023}}]}, "style": "PRE-FILTERING"}

// OR
{"condition": {"or": [{"key": "category", "match": {"value": "legal"}}, {"key": "category", "match": {"value": "compliance"}}]}, "style": "PRE-FILTERING"}
```

`match`: `value`, `not value`, `empty`, `null`, `any`, `except`, `like`, `not like`
`range`: `gt`, `gte`, `lt`, `lte` (combinable; don't mix `gt`+`gte` or `lt`+`lte`)
Logical: `and`, `or`, `not` (nestable)
