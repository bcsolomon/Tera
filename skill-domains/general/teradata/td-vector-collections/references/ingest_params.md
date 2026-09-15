# `tdvs_ingest_and_update` — Parameter Reference

Use this when building `docs_request_json` for `tdvs_ingest_and_update`.

---

## Rules

**`files_parameters`:** `files_type` required. `delimiter` only for CSV (default `","`).

**`ingest_parameters` — PDF only (unstructured files that need chunking):**
- Structured files (CSV, JSON, JSONL, Parquet) do NOT need `ingest_parameters` — omit it entirely. They are already row/record-based; no chunking applies.
- For PDF: **always explicitly set `"ingestor": "unstructured"`** — do not rely on the service default (which is `"basic"` and does not support `extract_images`/`extract_tables`). Use `"basic"` only if user explicitly requests it. Use `"nv_ingest"` only if user explicitly says NV-Ingest.
- `chunk_size` default 2048. `chunk_overlap` default 300 (must be < `chunk_size`).
- `extract_images`/`extract_tables`: set `true` for multimodal PDF ingestion.
- `extract_captions`: `true` only for Mode 2 (image descriptions).
- `vlm_model`: Mode 2 only, required. Same `model_id`/`model_provider` as `chat_model` with `"model_modality": "vlm"`.
- **FILE-EMBEDDING-BASED: always omit `ingest_parameters`** regardless of file type.

**`extraction_schema`:**
- `table_name`: must be globally unique. **Always generate as `<collection_name>_<8char_uuid>`** (e.g. `my_docs_a3f7b2c1`). Internal — never ask user.
- `data_columns`: columns holding text/content from the file.
- `image_column`: required for multimodal ingestion — for PDFs when `extract_images: true`, and for structured files that have an image column.
- `embedding_columns`: **required for FILE-EMBEDDING-BASED only**. Set `"name"` to the source file's vector column/key, `"datatype"` to `"Vector"` (not `FLOAT ARRAY`). For nested keys (e.g. NV-Ingest JSON), add `"key_name"`. Omit entirely for FILE-CONTENT-BASED (embeddings are generated, not read from file).

**`storage_location`:** Always required for file ingestion. Always use `"type": "artifacts"` — resolve the filename/path the user provided to artifact UUIDs using the workspace search/list tool, then pass them in `artifact_keys`. Do **not** include `file_paths` for artifact-based ingestion — the `artifacts` variant forbids it (`extra_forbidden` on `storage_location.artifacts.file_paths`); pass only `type` and `artifact_keys`.

**`overwrite_files` / `overwrite_object`:** Both default `false`. Include and set `true` only when user explicitly requests overwriting.

**`update_params`:**
- `update_style`: `"MAJOR"` = full rebuild, `"MINOR"` = incremental. Omit to let service decide.
- Models go inside `update_params.collection_parameters`.
- Do NOT set `embedding_model` for FILE-EMBEDDING-BASED collections.
- `train_params`: include only what user specifies. See `references/update_params.md`.

---

## Example: PDF (FILE-CONTENT-BASED, from Artifactory)

```json
{
  "files_parameters": {"files_type": "pdf"},
  "storage_location": {
    "type": "artifacts",
    "artifact_keys": ["5b7a3568-bf7b-48fc-9b6e-40cd28f20a3c"]
  },
  "ingest_parameters": {
    "ingestor": "unstructured",
    "chunk_size": 2048,
    "chunk_overlap": 300
  },
  "extraction_schema": {
    "table_name": "<collection_name>_<8char_uuid>",
    "data_columns": [{"name": "text", "datatype": "VARCHAR(32000)"}]
  },
  "update_params": {
    "collection_parameters": {
      "embedding_model": {"model_id": "amazon.titan-embed-text-v2:0", "model_provider": "aws"},
      "chat_model": {"model_id": "anthropic.claude-3-haiku-20240307-v1:0", "model_provider": "aws"}
    }
  }
}
```

---

## Example: FILE-EMBEDDING-BASED JSON (pre-computed embeddings)

```json
{
  "files_parameters": {"files_type": "json"},
  "storage_location": {
    "type": "artifacts",
    "artifact_keys": ["<resolved-uuid>"]
  },
  "extraction_schema": {
    "table_name": "my_docs_a3f7b2c1",
    "data_columns": [{"name": "text", "datatype": "VARCHAR(32000)"}],
    "embedding_columns": [{"name": "embeddings", "datatype": "Vector"}]
  },
  "update_params": {
    "collection_parameters": {
      "chat_model": {"model_id": "anthropic.claude-3-haiku-20240307-v1:0", "model_provider": "aws"}
    }
  }
}
```

No `ingest_parameters` — omitted for FILE-EMBEDDING-BASED. No `embedding_model` — vectors come from the file's `embedding_columns`.

---

## Example: CSV (structured, FILE-CONTENT-BASED)

```json
{
  "files_parameters": {"files_type": "csv", "delimiter": ","},
  "storage_location": {
    "type": "artifacts",
    "artifact_keys": ["<resolved-uuid>"]
  },
  "extraction_schema": {
    "table_name": "records_b4e9c1d7",
    "data_columns": [{"name": "title", "datatype": "VARCHAR(200)"}, {"name": "body", "datatype": "VARCHAR(4000)"}]
  },
  "update_params": {
    "collection_parameters": {
      "embedding_model": {"model_id": "amazon.titan-embed-text-v2:0", "model_provider": "aws"}
    }
  }
}
```

No `ingest_parameters` — structured files don't need chunking.

---

## Multimodal Ingestion

When user says "multimodal" without specifying which type, ask:

> "There are two multimodal approaches — which would you prefer?
>
> 1. **Multimodal embeddings** — images embedded directly using a multimodal embedding model. Best for visual similarity search. Works with any file type.
> 2. **Image descriptions** — a VLM converts images to text captions first, then embedded as text. Best for RAG/Q&A over document content. PDF only."

### Mode 1: Multimodal embeddings — all file types

For PDFs, set `extract_images: true` in `ingest_parameters`. For structured files, the source already has an image column — just specify it via `image_column` (no `ingest_parameters` needed).

```json
{
  "files_parameters": {"files_type": "pdf"},
  "storage_location": {"type": "artifacts", "artifact_keys": ["<resolved-uuid>"]},
  "ingest_parameters": {
    "extract_images": true,
    "extract_tables": true
  },
  "extraction_schema": {
    "table_name": "<collection_name>_<8char_uuid>",
    "data_columns": [{"name": "text", "datatype": "VARCHAR(32000)"}],
    "image_column": [{"name": "image_data", "datatype": "CLOB"}]
  },
  "update_params": {
    "collection_parameters": {
      "embedding_model": {"model_id": "<chosen>", "model_provider": "aws", "model_modality": "multimodal"},
      "chat_model": {"model_id": "<chosen>", "model_provider": "aws", "model_modality": "vlm"}
    }
  }
}
```

### Mode 2: Image descriptions (captions) — PDF only

```json
{
  "files_parameters": {"files_type": "pdf"},
  "storage_location": {"type": "artifacts", "artifact_keys": ["<resolved-uuid>"]},
  "ingest_parameters": {
    "extract_images": true,
    "extract_tables": true,
    "extract_captions": true,
    "vlm_model": {"model_id": "<same as chat_model>", "model_provider": "aws", "model_modality": "vlm"}
  },
  "extraction_schema": {
    "table_name": "<collection_name>_<8char_uuid>",
    "data_columns": [{"name": "text", "datatype": "VARCHAR(32000)"}],
    "image_column": [{"name": "image_data", "datatype": "CLOB"}]
  },
  "update_params": {
    "collection_parameters": {
      "embedding_model": {"model_id": "<chosen>", "model_provider": "aws"},
      "chat_model": {"model_id": "<chosen>", "model_provider": "aws", "model_modality": "vlm"}
    }
  }
}
```

**Mode 2 notes:** `vlm_model` in `ingest_parameters` is required (same model as `chat_model`). Embedding model is text-only — do NOT set `model_modality: "multimodal"`. `image_column` is mandatory for both modes.

