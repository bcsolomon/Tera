---
name: teradata-ai-llm-functions
description: 'Use Teradata AI SQL functions for in-database LLM-driven NLP tasks such as sentiment, summarization, translation, entity recognition, and prompt-based analysis with provider-backed authorization.'
metadata:
    author: teradata
    version: "1.0"
---

# Teradata AI/LLM SQL Functions

> **Skill:** teradata-ai-llm-functions  
> **Domain:** 12-advanced-data-and-analytics-features / 08-ai-sql-and-llm-integration  
> **Applies to:** Teradata Vantage 20.0+, VantageCloud Lake  

---

## Purpose

Guide agents through using Teradata's in-database AI functions that call LLM endpoints to perform NLP tasks directly in SQL. All functions run as table operators — no data leaves the database for processing.

> **Prerequisites:** An authorization object and LLM provider must be configured before using AI functions. See [references/authorization-objects.md](references/authorization-objects.md) and [references/llm-providers.md](references/llm-providers.md).

---

## Function Summary

| Function | Task | Reference |
|----------|------|-----------|
| `AI_AnalyzeSentiment` | Classify text as positive / negative / neutral | [ai-text-analytics.md](references/ai-text-analytics.md) |
| `AI_AskLLM` | Free-form LLM prompt against text data (RAG Q&A) | [ai-text-analytics.md](references/ai-text-analytics.md) |
| `AI_DetectLanguage` | Detect language of input text | [ai-text-analytics.md](references/ai-text-analytics.md) |
| `AI_ExtractKeyPhrases` | Extract key phrases from text | [ai-text-analytics.md](references/ai-text-analytics.md) |
| `AI_MaskPII` | Detect and mask personally identifiable information | [ai-text-analytics.md](references/ai-text-analytics.md) |
| `AI_RecognizeEntities` | Identify named entities (people, places, orgs) | [ai-text-analytics.md](references/ai-text-analytics.md) |
| `AI_RecognizePIIEntities` | Identify PII entities with type and position | [ai-text-analytics.md](references/ai-text-analytics.md) |
| `AI_TextClassifier` | Classify text into user-defined categories | [ai-text-analytics.md](references/ai-text-analytics.md) |
| `AI_TextSummarize` | Summarize input text | [ai-text-analytics.md](references/ai-text-analytics.md) |
| `AI_TextTranslate` | Translate text between languages | [ai-text-analytics.md](references/ai-text-analytics.md) |

---

## Common Pattern

All AI functions share this call structure:

```sql
SELECT * FROM TD_SYSFNLIB.AI_FunctionName(
    ON db.my_table AS InputTable
    USING
        -- Provider config (required)
        ApiType('azure'|'aws'|'gcp'|'nim'|'litellm')
        AUTHORIZATION(db.my_auth_object)
        DeploymentId('gpt-4o')            -- or ModelName for non-Azure

        -- Function-specific args
        TextColumn('text_col')
        Accumulate('id_col', 'other_col')
) AS t;
```

> **Schema qualifier required:** All functions use `TD_SYSFNLIB.<FunctionName>(...)`.  
> **No PARTITION BY:** These functions manage parallelism internally.

---

## Authorization Setup

```sql
-- Create authorization object (stores API credentials securely)
CREATE AUTHORIZATION db.my_azure_auth
    USER 'api-key-placeholder'
    PASSWORD 'your-azure-api-key';

-- Grant to users who need AI functions
GRANT EXECUTE ON db.my_azure_auth TO analyst_role;
```

See [references/authorization-objects.md](references/authorization-objects.md) for full syntax.

---

## Provider Configuration

| Provider | ApiType | Key Args |
|----------|---------|----------|
| **Azure OpenAI** | `'azure'` | `DeploymentId`, `ResourceName`, `ApiVersion` |
| **AWS Bedrock** | `'aws'` | `ModelName`, `Region`, `AccessKeyId`, `SecretAccessKey` |
| **GCP Vertex AI** | `'gcp'` | `ModelName`, `ProjectId`, `Region` |
| **NVIDIA NIM** | `'nim'` | `ModelName`, `BaseUrl` |
| **LiteLLM** | `'litellm'` | `ModelName`, `BaseUrl` |

See [references/llm-providers.md](references/llm-providers.md) for complete provider syntax.

---

## Key Use Cases

### Sentiment Analysis

```sql
SELECT * FROM TD_SYSFNLIB.AI_AnalyzeSentiment(
    ON db.customer_reviews AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.my_auth)
        DeploymentId('gpt-4o')
        TextColumn('review_text')
        Accumulate('review_id', 'customer_id')
) AS t;
```

### RAG Question Answering (AI_AskLLM)

Two-table input: questions + context data, co-partitioned by key:

```sql
SELECT * FROM TD_SYSFNLIB.AI_AskLLM(
    ON db.questions AS InputTable PARTITION BY qid
    ON db.documents AS ContextTable PARTITION BY doc_id
    USING
        ApiType('azure')
        AUTHORIZATION(db.my_auth)
        DeploymentId('gpt-4o')
        TextColumn('question')
        ContextColumn('doc_text')
        Prompt('Answer using only the provided data.\nQuestion: #QUESTION#\nData: #DATA#')
        QUESTIONPOSITION('#QUESTION#')
        DATAPOSITION('#DATA#')
        Accumulate('qid', 'question')
) AS t;
```

> **DATAPOSITION is required** — it is missing from Teradata documentation but must be specified. Omitting it causes an error.

### PII Detection and Masking

```sql
-- Detect and mask PII
SELECT * FROM TD_SYSFNLIB.AI_MaskPII(
    ON db.customer_notes AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.my_auth)
        DeploymentId('gpt-4o')
        TextColumn('note_text')
        Accumulate('note_id')
) AS t;
```

### Text Classification (Custom Categories)

```sql
SELECT * FROM TD_SYSFNLIB.AI_TextClassifier(
    ON db.support_tickets AS InputTable
    USING
        ApiType('azure')
        AUTHORIZATION(db.my_auth)
        DeploymentId('gpt-4o')
        TextColumn('description')
        ClassificationLabels('billing', 'technical', 'feature_request', 'complaint')
        Accumulate('ticket_id')
) AS t;
```

---

## Common Pitfalls

| Mistake | Fix |
|---------|-----|
| Omitting `TD_SYSFNLIB.` schema prefix | Always use `TD_SYSFNLIB.AI_FunctionName(...)` |
| Adding PARTITION BY to AI functions | Don't — they manage parallelism internally |
| Omitting DATAPOSITION in AI_AskLLM | Always specify `DATAPOSITION('#DATA#')` |
| Inconsistent sentiment label casing | Normalize with `LOWER()` in downstream logic |
| No authorization object | Create with `CREATE AUTHORIZATION` and grant to users |

---

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-ai-llm-functions", path="references/FILENAME")` — do NOT call `list`.

| File | Content |
|------|---------|
| [ai-text-analytics.md](references/ai-text-analytics.md) | Full syntax for all 10 AI functions with examples |
| [llm-providers.md](references/llm-providers.md) | Provider config blocks for Azure, AWS, GCP, NIM, LiteLLM |
| [authorization-objects.md](references/authorization-objects.md) | CREATE/REPLACE/GRANT authorization objects |

*Source: Teradata tdsql-mcp syntax library (ksturgeon-td/tdsql-mcp)*
