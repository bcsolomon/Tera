---
name: td-vector-collections
description: "Manages Teradata vector collections: create, ingest (files or tables), search (semantic/similarity/hybrid), RAG (ask questions over documents or tables), update, delete, and permissions. Triggers on: vector store, collection, RAG, ingest, embed, index, semantic search, similarity search, hybrid search, document Q&A, answer from a PDF/file/table, query file contents, search over a database table, ask a collection, query a collection."
---

# td-vector-collections Skill

Teradata Vector collections Skill

Orchestrate `tdvs_*` MCP tools via progressive disclosure for Teradata vector store operations.

## Tool Access — Progressive Disclosure Only

All `tdvs_*` tools are accessed through four gateway tools: `teradata_list_patterns`, `teradata_search_tools`, `teradata_get_tool_schema`, `teradata_tool_call`. There is no direct-access mode. Never use `web_search` or `tool_search` to find tdvs tools.

### Mandatory sequence for every tool call

Follow these steps **in order**. Never call a tool before its schema is fetched.

1. **Read _and view the full content of_ the relevant reference file** for the operation (see table below) — do this *before* building any payload. Loading a reference is not the same as reading it (see **LOADING ≠ READING** below).
2. **Fetch the schema**: `teradata_get_tool_schema(tool_name="tdvs_X")` — required before the first call to that tool in the session.
3. **Build the payload** from the schema + reference. Match parameter names exactly. Do not guess or assume shapes.
4. **Execute**: `teradata_tool_call(input={"name": "tdvs_X", "parameters": {...}})`.

> ⛔ **SCHEMA-FIRST IS MANDATORY.** Never call `teradata_tool_call` for a tool whose schema you have not fetched this session. The correct order is *fetch schema → build payload → execute* — never *execute → hit error → then fetch schema*. If you are reading a reference or fetching a schema **because** a call already failed, you have violated this rule.

> ⛔ **LOADING ≠ READING.** Opening a `references/*.md` file may return a stored handle (a `reference_id` / "stored in memory" pointer), **not** the text itself. You have not read a reference until you have the **actual markdown content** in front of you. If a read returned only a handle, dereference it (e.g. `query_tool_result`) and view the real text **before** building any payload or choosing any tool name. Never build a payload from a handle you have not expanded. Handles can go stale ("not found") — if so, read the file again. Choosing tool names or parameter shapes without having viewed the real content is the #1 cause of failures.

> ⛔ **PAYLOAD SHAPE COMES FROM THE SCHEMA.** Body-carrying tools take one **stringified-JSON** parameter (never a raw nested object): **`payload`** — `tdvs_create`, `tdvs_update`, `tdvs_ask`, `tdvs_similarity_search`, `tdvs_prepare_response`, `tdvs_load_data`, `tdvs_create_index`, `tdvs_generate_embeddings`, `tdvs_grant_or_revoke_user_permission`, `tdvs_terminate_sessions`; **`docs_request_json`** (+ optional `files`) — `tdvs_validate_files`, `tdvs_ingest_and_update`. The schema’s description for that parameter lists the exact top-level keys and their nesting — mirror it (e.g. `top_k` → `search_params.top_k`; model dicts like `embedding_model`/`chat_model` stay nested — never flatten). Two failure modes: **`body: None` / "Field required" (422)** = you passed an object, not a string → serialize it; **`extra_forbidden` / "extra fields not permitted"** (e.g. on `top_k`, `file_paths`, `body.<key>`) = a key is flattened, mis-nested, or unsupported → re-nest or drop it.>
> **Correct `teradata_tool_call` shape for any payload-bearing tool:**
> ```json
> {"input": {"name": "tdvs_<tool>", "parameters": {"collection_name": "<name>", "payload": "{\"<key>\":{\"<nested_key>\":{\"<field>\":\"<value>\"}}}"}}}
> ```
> ⚠️ The `payload` value is a **single JSON string** — count opening `{` and closing `}` inside the payload string and confirm they match before calling.
### Caching (do each discovery step once per session)

| Gateway call | How often | Notes |
|---|---|---|
| `teradata_list_patterns()` | Once per session | tdvs tools live in the `data-insights-collections` pattern. |
| `teradata_search_tools(pattern="data-insights-collections")` | Once per session | Lists all `tdvs_*` tools. |
| `teradata_get_tool_schema(tool_name="tdvs_X")` | Once per tool per session | Reuse the cached schema for all later calls to that tool. |
| Reading a `references/*.md` file | Once per file per session | Reuse the loaded content; do not re-read on error. |

On error: read the error, fix the payload using the **already-cached** schema and reference, then retry. Do **not** re-run discovery or re-fetch schemas — they have not changed.

### Tool name reference

Use these exact names with `teradata_get_tool_schema`. When a workflow step names `tdvs_X`, fetch the schema for that exact name.

> ⛔ **DISCOVERY-FIRST FOR NAMES.** You must have run `teradata_search_tools(pattern="data-insights-collections")` this session, and may only call `tdvs_*` names that appear in its output — the table below is the canonical list. Never invent a "natural-sounding" name (e.g. `tdvs_create_collection`, `tdvs_ingest_artifacts`); pick from the table.

| Intent | Tool | Intent | Tool |
|---|---|---|---|
| Ask a question / RAG | `tdvs_ask` | Check status | `tdvs_status` |
| Similarity search (raw chunks) | `tdvs_similarity_search` | Get file metadata | `tdvs_get_file_metadata` |
| Prepare response from chunks | `tdvs_prepare_response` | Get file store entries | `tdvs_get_file_store` |
| Get collection details | `tdvs_get_details` | List available models | `tdvs_list_available_models` |
| List collections | `tdvs_list` | Grant/revoke permissions | `tdvs_grant_or_revoke_user_permission` |
| Create collection | `tdvs_create` | List user permissions | `tdvs_list_user_permissions` |
| Update collection | `tdvs_update` | Check service health | `tdvs_get_health` |
| Ingest files | `tdvs_ingest_and_update` | Validate files before ingest | `tdvs_validate_files` |
| Load data into collection | `tdvs_load_data` | Generate embeddings | `tdvs_generate_embeddings` |
| Create / rebuild index | `tdvs_create_index` | Delete collection | `tdvs_destroy` |
| List sessions | `tdvs_list_sessions` | Terminate sessions | `tdvs_terminate_sessions` |

### Reference file per operation

| Operation | Read first |
|---|---|
| Search / RAG (`tdvs_ask`, `tdvs_similarity_search`) | `references/search_params.md` |
| Update (`tdvs_update`, index/model changes) | `references/update_params.md` |
| Ingest (`tdvs_ingest_and_update`) | `references/ingest_params.md` |
| Create (`tdvs_create`) | `references/create_collection.md` |
| Model selection | `references/model_selection.md` |
| Permissions | `references/permissions.md` |
| Errors / edge cases | `references/edge_cases.md` |

## Common Patterns

**Step 0 (always do first for existing collections):**
- User named collection → use it directly (skip status check — the service validates readiness and will return an error if the collection is not ready or doesn't exist).
- Unknown collection name → `tdvs_list` (always with `authorized: true`), show matches (name, type, status, last_updated).
  - **If user provided a file path:** For each `ready` collection in the results, call `tdvs_get_file_metadata` with `search` = the filename (basename of the file path) to verify whether the file actually exists in that collection.
    - **File found in one or more collections:** Present only the collections that contain the file. Ask: "Your file `<filename>` was found in these collections: `<list>`. Would you like to query one of these, or create a new collection?"
    - **File not found in any collection:** Inform the user: "Your file `<filename>` was not found in any existing collection." Then offer: "Would you like to ingest it into one of the existing collections, or create a new collection?"
  - **If user did NOT provide a file path (general query):** Show all matches and **STOP — ask the user to confirm which collection to use before proceeding, even if only one match is found.** Do not proceed until the user explicitly confirms.
  - No matches → create (Workflows 1–3). Suggest a name derived from file stem or table name (lowercase, underscores, no spaces) and **ask user to confirm or provide a different name** before calling `tdvs_create`.

**Polling:** After any create/ingest/index operation, poll `tdvs_status` every 60s until `ready`. Timeout ≠ failure. On `*_failed`: stop, report, see `references/edge_cases.md`.

## Workflows

### 1: File-Based Collection

Use when: user mentions a file by name or path (PDF, CSV, JSON, JSONL, Parquet). **All file ingestion goes through Artifactory** — always resolve the file to an artifact UUID first.

**FILE-CONTENT-BASED:** Files with raw text to embed (PDF, CSV, JSON, JSONL, Parquet).

**FILE-EMBEDDING-BASED:** Files already contain pre-computed embeddings — CSV, JSON, JSONL, Parquet only (PDF not supported). No embedding model needed at ingest; user must provide `embedding_model` at query time to embed the search question.

> Read `references/edge_cases.md` first (folder paths, unsupported formats, name conflicts). If "multimodal": read Multimodal section in `references/ingest_params.md`, ask which mode (multimodal embeddings or image descriptions) before proceeding.

> **⚠️ PROHIBITED — for all file ingestion:**
> - Do NOT download the file
> - Do NOT construct or pass file paths (local or remote)
> - Do NOT create temporary files
> - Do NOT read file content
>
> The vectorstore service downloads files internally using artifact keys only.

1. **Resolve artifact UUID** → use the workspace search/list tool with the filename (or basename of the path the user provided) to look up its Artifactory artifact UUID(s).
2. Select models → `tdvs_list_available_models` (always with `verify: true`) + `references/model_selection.md` (skip embedding model for FILE-EMBEDDING-BASED). **STOP — present ALL available models to the user, highlight the recommended embedding model (and chat model if applicable), and ask for confirmation before proceeding.** Do not call `tdvs_create` until the user confirms or selects a different model.
3. Create → `tdvs_create` per `references/create_collection.md`
4. Ingest → `tdvs_ingest_and_update` — pass all resolved artifact UUIDs in `docs_request_json` under `storage_location` with `"type": "artifacts"`, and do **not** include `file_paths` (the `artifacts` storage variant forbids it — `extra_forbidden` on `storage_location.artifacts.file_paths`). See `references/ingest_params.md` for full payload shape.
5. Poll until ready

### 2–3: Table-Based Collection

**CONTENT-BASED (Workflow 2):** User has a table with text columns to embed.

**EMBEDDING-BASED (Workflow 3):** User's table already has an embedding column (no embedding model needed).

1. Select models → `tdvs_list_available_models` (always with `verify: true`) + `references/model_selection.md` (skip embedding model for EMBEDDING-BASED). **STOP — present ALL available models to the user, highlight the recommended embedding model (and chat model if applicable), and ask for confirmation before proceeding.** Do not call `tdvs_create` until the user confirms or selects a different model.
2. Create → `tdvs_create` per `references/create_collection.md` → relevant section. Indexing starts automatically.
3. Poll until ready

### 4: Update Existing Collection

> Do Step 0 first. Follow the **mandatory sequence** (read `references/update_params.md` → fetch `tdvs_update` schema → build payload → execute). Never guess payload shapes.

> **Critical:** For all `tdvs_update` calls, pass two parameters: `collection_name` (string) and `payload` (JSON string). The "Key payload" column below shows the JSON object to serialize as a string for the `payload` parameter. See `references/update_params.md` for full details.

| User intent | Tool | Key payload (exact shape — do not guess) |
|---|---|---|
| Rename collection | `tdvs_update` | `{"new_collection_name": "..."}` (top-level key) |
| Change description | `tdvs_update` | `{"collection_description": "..."}` (top-level key) |
| Add files | `tdvs_ingest_and_update` | Resolve file name → artifact UUID first (workspace search/list tool), then see `references/ingest_params.md` |
| Delete files | `tdvs_update` | `{"collection_index": {"alter_operation": "DELETE", "file_names": [...]}}` |
| Add table | `tdvs_update` | `{"collection_index": {"alter_operation": "ADD", "object_names": [...], "key_columns": [...], "data_columns": [...]}}` |
| Delete table/rows | `tdvs_update` | `{"collection_index": {"alter_operation": "DELETE", "object_names": [...]}}` |
| Load from staging | `tdvs_load_data` | CollectionIndex payload |
| Change chat model | `tdvs_update` | `{"collection_parameters": {"chat_model": {"model_id": "...", "model_provider": "aws"}}}` |
| Change embedding model | `tdvs_update` | `{"collection_parameters": {"embedding_model": {"model_id": "...", "model_provider": "aws"}}}` ⚠️ |
| Change search strategy to hybrid | `tdvs_update` | `{"collection_parameters": {"search_strategy": {"search_type": "HYBRID_SEARCH"}}}` |
| Change index algo/metric | `tdvs_update` | `{"collection_parameters": {"train_params": {"search_algorithm": "HNSW", "metric": "COSINE"}}}` ⚠️ |
| Regenerate embeddings | `tdvs_generate_embeddings` | `{"embedding_model": {"model_id": "..."}}` |
| Rebuild index only | `tdvs_create_index` | `{}` or `{"train_params": {...}}` |
| Metadata column ops | `tdvs_update` | `{"collection_index": {"metadata_operation": "ADD\|DELETE\|MODIFY", "metadata_columns": [...], "metadata_columns_info": [...]}}` |

⚠️ = warn user first (re-embeds all data), proceed only on confirmation. Poll after any indexing op.

### 5: Search (RAG or Similarity)

> Follow the **mandatory sequence**: read `references/search_params.md` → fetch the schema for `tdvs_ask` (or `tdvs_similarity_search`) → build the payload → execute. Do not call the tool before the reference and schema are loaded.

1. Step 0 (file-metadata verification is built into Step 0 when user provides a file path). **If collection was resolved via `tdvs_list` (not explicitly named by user), confirm with the user before querying.**
2. **Always read `references/search_params.md` first** — pass any user-specified search type or params in the payload exactly as documented there.
3. **Embedding model check:** For any model selection, confirmation, or failure handling — read and follow `references/model_selection.md` exactly before calling any search tool.
4. Choose tool by user intent:
   - **Default: `tdvs_ask`** — use whenever the user asks a question or wants an answer. Keywords like "similarity confidence", "threshold", or "top_k" are search *parameters*, not a request for raw chunks — still use `tdvs_ask`.
   - **`tdvs_similarity_search`** — only when the user explicitly asks for raw chunks, source passages, or matching documents (not an answer).
   - **`tdvs_similarity_search` → `tdvs_prepare_response`** — when user wants to see chunks first, then get an answer.

Note: `chat_model` override works for `tdvs_ask` and `tdvs_prepare_response` only.

### 6: Delete Collection

**ONLY** when user explicitly says delete/destroy/drop collection. Never infer from file deletion.

1. Step 0 → list all collection names to be destroyed.
2. **⛔ STOP — warn user this is irreversible, list every collection name, then ask for confirmation. Do NOT call `tdvs_destroy` until the user confirms in a subsequent message.**
3. After user confirms → `tdvs_destroy` each collection.

### 7: Permissions

1. Step 0
2. Read `references/permissions.md`
3. `tdvs_list_user_permissions` or `tdvs_grant_or_revoke_user_permission`

## Status Values

`initialized` (no data) · `ingested` (no index yet) · `embedding` (indexing) · `ready` (queryable) · `ingestion_failed` · `destroying`

## Safety

- `tdvs_destroy` is irreversible — see Workflow 6 for required confirmation steps.
- Unexpected tool behavior → call `tdvs_get_health` first.