# Model Selection — `tdvs_list_available_models` Usage

**Never auto-pick a model. Always confirm with the user before proceeding — even if only one model is available in a category. The list returned by `tdvs_list_available_models` is not exhaustive; users may have custom or unlisted model IDs they want to use instead.**

**CRITICAL: ALWAYS call `tdvs_list_available_models` with `verify: true`.** Never call without it — unverified calls return excessively large responses that are unusable. The `verify: true` flag returns only models that are actually accessible. Show results grouped by type (embedding / chat), then ask the user to pick.

---

## Three cases — follow exactly

### Case 1 — User provides what looks like an exact model ID

> e.g. "use amazon.titan-embed-text-v2:0", "use us.anthropic.claude-sonnet-4-5"

A model ID typically contains dots, colons, slashes, or provider prefixes (e.g. `amazon.`, `anthropic.`, `cohere.`).

**Use it directly — do not validate against `tdvs_list_available_models`.** The model may be custom or not listed. Proceed without asking.

### Case 2 — User provides a short name or partial reference (not a full ID)

> e.g. "use Titan", "use Claude Haiku", "use a gpt4o model"

1. Call `tdvs_list_available_models` with `verify: true`
2. Filter the list to candidates that match the name
3. If exactly one match → confirm with the user: "I found `<model_id>` — is that the right one? Or provide your own model ID if you have one."
4. If multiple matches → show only the matching candidates and ask the user to pick (or provide their own ID)
5. If no match → show the full list and ask the user to choose or provide their own model ID

### Case 3 — User does not mention any model

> e.g. "create a collection and ingest this file into database sans"

1. Call `tdvs_list_available_models` with `verify: true`
2. Present both lists to the user — embedding models and chat models — showing `model_id` and provider
3. Ask: "Which embedding model and chat model would you like to use? You can pick from the list below or provide your own model ID if you have one."
   - **Exactly one option in a category (after any required filtering):** Say "I found `<model_id>` as the only available option — would you like to use it, or provide your own model ID?"
   - **Zero options after filtering:** Show the full unfiltered list and ask the user to provide a model ID that fits the requirement.
4. **Do not proceed until the user explicitly confirms or provides a model ID.**

---

## When `embedding_model` is NOT needed (at create/ingest time)

- `FILE-EMBEDDING-BASED` — files already contain embeddings; ask for **chat model only**
- `EMBEDDING-BASED` — table already has a vector column; ask for **chat model only**

**However**, for these types, `embedding_model` IS required at **query time** (`tdvs_ask` / `tdvs_similarity_search`) to convert the user's text question into a vector. Ask the user which embedding model to use for queries when setting up these collection types.

---

## `model_modality` field (multimodal ingestion only)

Only set `model_modality` for multimodal ingestion — omit for all standard text workflows.

| Mode | Field | Value |
| ---- | ----- | ----- |
| Mode 1 (multimodal embeddings) | `embedding_model.model_modality` | `"multimodal"` |
| Mode 1 (multimodal embeddings) | `chat_model.model_modality` | `"vlm"` |
| Mode 2 (image descriptions) | `embedding_model.model_modality` | — omit (text embedding) |
| Mode 2 (image descriptions) | `chat_model.model_modality` | `"vlm"` |

---

## `model_provider` field

`"aws"` for Bedrock · `"azure"` for Azure OpenAI · `"gcp"` for GCP Vertex · Teradata-hosted: omit `model_provider`, use `base_url` instead.

---

## Model-related service failures

### AWS `ValidationException` — invalid model identifier (auto-retry)

If a call fails with `The provided model identifier is invalid`, retry with `us.<model_id>`, then `global.<model_id>`. If both fail, fall through to the general failure flow below.

---

### General model failures

If any `tdvs_*` call fails with an error related to a model (e.g. model not found, access denied, timeout, incompatible model, missing embedding model) **and the auto-retry above did not resolve it**:

1. Report the error clearly to the user.
2. Call `tdvs_list_available_models` with `verify: true` to get the current verified list.
3. Present the full list and ask: "The model `<model_id>` failed (or no model was provided). Please pick a model from the list below, or provide your own model ID."
4. **STOP — do not retry until the user explicitly selects or confirms a model.** Never auto-pick a model from the list, even if there is only one candidate.

---

## When `embedding_dims` is required

Include `embedding_dims` when:

- The model is custom or Teradata-hosted (not a well-known cloud model)
- User specifies a dimension value explicitly

For unknown/internal models, ask: "What are the embedding dimensions for this model?"
