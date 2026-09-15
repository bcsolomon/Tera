# Ingestion Edge Cases

Handle these before calling any ingest or create tool.

---

## File path issues

**User provides a folder path (not individual files)**
- `tdvs_ingest_and_update` requires explicit file paths — it cannot take a directory
- Ask: "Please list the specific files you want to ingest from that folder."
- Do not attempt to glob or list the folder yourself unless you have shell access and user confirms

**Unsupported file type**
Supported formats: `PDF`, `CSV`, `JSON`, `JSONL`, `Parquet`
- If user provides `.docx`, `.xlsx`, `.txt`, `.html`, or any other format — inform them it is not supported
- Suggest: convert to PDF or export as CSV/JSON before ingesting
- Do not attempt ingestion

**File does not exist**
- If a path looks wrong or the user is uncertain, suggest calling `tdvs_validate_files` first (see below)

---

## Validate before ingest

Use `tdvs_validate_files` when:
- User explicitly asks to validate before ingesting
- Files are coming from an unfamiliar location or format
- User is unsure if their file structure matches what the collection type expects

Call with the same `collection_name`, `files`, and `docs_request_json` as you would for ingest.
Report the validation result to the user and ask if they want to proceed.

---

## Collection name conflicts

**Before calling `tdvs_create`, always call `tdvs_list` with `authorized: true` and `search` = proposed collection name** to check if it already exists.

When a collection with the same name exists:
- Ask: "A collection named `<name>` already exists. Do you want to add files to it, or use a different name?"
- **Add files** → skip `tdvs_create`, go directly to `tdvs_ingest_and_update`
- **New name** → ask user for a new name, then proceed with create

Never silently overwrite or re-create an existing collection.

---

## Ingestion fails (status ends with `_failed`)

When `tdvs_status` returns a status ending in `_failed`:
- Stop polling immediately
- Report the full status value and any error details from the response
- Do **not** retry automatically
- Suggest the user:
  1. Check file format and encoding
  2. Verify the embedding model is accessible (call `tdvs_list_available_models` with `verify: true`)
  3. Check `tdvs_get_health` for service issues
  4. Contact support if the issue persists

---

## Ambiguous collection type

When user's description doesn't clearly indicate a type:

| Signals | Likely type |
|---------|-------------|
| "my PDF", "this CSV file", "ingest this document" | `FILE-CONTENT-BASED` |
| "my file has embeddings / vectors already" (CSV/JSON/JSONL/Parquet only — PDF not supported) | `FILE-EMBEDDING-BASED` |
| "my table", "database table", "Teradata table" | `CONTENT-BASED` |
| "my table has a vector column / embedding column" | `EMBEDDING-BASED` |

If still ambiguous after reading the signals, ask: "Is your data in files or a database table? And does it already have pre-computed embeddings?"
