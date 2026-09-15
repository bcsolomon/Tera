# Semantic search over the CDC documents

1,274 chunks from seven CDC PDFs, embedded in-database with the BYOM ONNX model `bge-small-en-v1.5` (384 dimensions).
Search runs entirely in Teradata: the question is embedded by the same model in the same statement, then compared with
`TD_VECTORDISTANCE` using cosine distance. No external embedding service, and no volatile table, so a single
`base_readQuery` call works.

## The search statement

Replace only the question text. Double any single quotes inside it.

```sql
SELECT TOP 5 d.DOC_TITLE, ch.PAGE_NUMBER, ch.ELEMENT_TYPE,
       ABS(CAST(vd.distance AS DECIMAL(36,8))) AS dist, ch.CHUNK_TEXT
FROM TD_VECTORDISTANCE (
    ON (SELECT * FROM TD_MLDB.ONNXEmbeddings(
            ON (SELECT 1 AS id,
                       CAST('How is the standardized infection ratio calculated and when is an SIR not reported?'
                            AS VARCHAR(4000) CHARACTER SET UNICODE) AS txt) AS InputTable
            ON (SELECT model_id, model FROM BYOM.embeddings_models
                WHERE model_id = 'bge-small-en-v1.5') AS ModelTable DIMENSION
            ON (SELECT model AS tokenizer FROM BYOM.embeddings_tokenizers
                WHERE model_id = 'bge-small-en-v1.5') AS TokenizerTable DIMENSION
            USING Accumulate('id','txt') ModelOutputTensor('sentence_embedding')
                  EnableMemoryCheck('false') OutputFormat('FLOAT32(384)')
                  OverwriteCachedModel('true')) AS q) AS TargetTable
    ON CDC_HAI.doc_embeddings AS ReferenceTable DIMENSION
    USING TargetIDColumn('id') TargetFeatureColumns('[2:385]')
          RefIDColumn('id') RefFeatureColumns('[4:387]')
          DistanceMeasure('cosine') TopK(5)
) AS vd
JOIN CDC_HAI.doc_chunks ch ON ch.CHUNK_KEY = vd.reference_id
JOIN CDC_HAI.document d ON d.DOC_ID = ch.DOC_ID
ORDER BY dist;
```

Three things must not be edited casually:

- **Feature column ranges.** `'[2:385]'` for the query (which accumulates `id`, `txt`) and `'[4:387]'` for the reference
  table (which accumulates `id`, `txt`, `doc_id`, `filename`). They are 0-based positions; changing the Accumulate list
  shifts them and silently compares the wrong columns.
- **The UNICODE cast** on the question. Without it a non-ASCII character in the question fails the statement.
- **The model id in all three places.** Query and corpus must use the same model or distances are meaningless.

## Reading the results

`dist` is cosine distance, so smaller is closer. Observed behaviour on this corpus:

| Distance | Meaning |
|---|---|
| 0.10 to 0.20 | Strong match, usually the passage you want |
| 0.20 to 0.30 | Related, often useful context |
| above about 0.35 | Drifting off topic; treat with suspicion |

Chunk text is stored as `Prefix: <what this passage is>; Original: <the passage>` because the pipeline ran a contextual
chunker. Use the prefix to judge relevance and quote the text after `Original:`. `ELEMENT_TYPE='TableChunk'` marks a chunk
that came from a table (135 of them), which is where numeric detail in the guides lives.

## Verified examples

| Question | Top results |
|---|---|
| "How is the standardized infection ratio calculated and when is an SIR not reported?" | FAQ page 3 (national SIR formula, dist 0.121), Progress Report glossary page 8 (0.124), SIR Guide page 5 (0.131), SIR Guide page 12 (the predicted-below-1.0 rule, 0.135) |
| "Why did central line-associated bloodstream infections increase during the COVID-19 pandemic in 2020?" | COVID-19 Impact page 2 (47 percent Q4 increase, 65 percent in ICUs, dist 0.141), page 1 (2021 findings, 0.187), device utilization passage (0.192) |
| "What counts as a ventilator-associated event and how is VAE surveillance defined?" | Progress Report glossary page 8 (dist 0.157), FAQ page 1 (0.159), Progress Report page 2 on LTACH coverage (0.200), SIR Guide page 28 on VAE risk adjustment (0.211) |

## Scoping a search

Restrict the reference set inside the `ON` clause rather than filtering afterwards, so `TopK` applies to the subset:

```sql
    ON (SELECT * FROM CDC_HAI.doc_embeddings WHERE doc_id = 1) AS ReferenceTable DIMENSION   -- SIR Guide only
    ON (SELECT * FROM CDC_HAI.doc_embeddings WHERE doc_id IN (1,2)) AS ReferenceTable DIMENSION  -- both method guides
```

Useful scopes: `doc_id` 1 for SIR methodology, 2 for SUR methodology, 3 for the 2024 narrative, 4 for plain-language
definitions, 6 for the pandemic story. Raise `TopK` to 10 for a broad survey question, lower to 3 for a precise lookup.

## Hybrid patterns

**Number first, then method.** Answer the quantitative question from the fact tables, then search for the passage that
explains or qualifies it, and present both. Example: report the national VAE SIR of 1.105 with its interval, then search
"ventilator-associated event definition IVAC" to explain what counts as a VAE before drawing conclusions.

**Anomaly explanation.** When a structured result is surprising, search for the CDC explanation rather than inventing one.
A state with a NULL SIR pairs with the SIR Guide's predicted-below-1.0 passage; a 2020 spike pairs with the COVID-impact page.

**Definition gate.** If the question contains a term of art (hospital-onset, consistent reporter, complex admission and
readmission model, LabID event), search first so the SQL filters match CDC's definition, then query.

**Citation discipline.** One combined answer should carry: the figure with its confidence interval, the table it came from,
and the document title plus page for any quoted explanation.

## Maintenance

`doc_embeddings` is a full rebuild, not incremental: if documents are re-processed, rebuild `doc_chunks` then
`doc_embeddings` (see the build skill's `30_doc_chunks_and_embeddings.sql`). Distances are only comparable within one model,
so never mix two models in one table.
