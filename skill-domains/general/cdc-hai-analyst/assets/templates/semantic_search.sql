-- Template: semantic search over the CDC documents in CDC_HAI.
-- Edit ONLY the question text (double any single quotes) and optionally TopK / the doc_id scope.
-- Do not change the feature-column ranges: '[2:385]' matches Accumulate('id','txt');
-- '[4:387]' matches Accumulate('id','txt','doc_id','filename') in doc_embeddings.
-- Scope options: doc_id 1 SIR Guide, 2 SUR Guide, 3 2024 Progress Report, 4 FAQ,
--                5 Reports and Data, 6 COVID-19 Impact, 7 Figure 1.

SELECT TOP 5
       d.DOC_TITLE,
       ch.PAGE_NUMBER,
       ch.ELEMENT_TYPE,
       ABS(CAST(vd.distance AS DECIMAL(36,8))) AS dist,
       ch.CHUNK_TEXT
FROM TD_VECTORDISTANCE (
    ON (SELECT * FROM TD_MLDB.ONNXEmbeddings(
            ON (SELECT 1 AS id,
                       CAST('<YOUR QUESTION HERE>' AS VARCHAR(4000) CHARACTER SET UNICODE) AS txt
               ) AS InputTable
            ON (SELECT model_id, model FROM BYOM.embeddings_models
                 WHERE model_id = 'bge-small-en-v1.5') AS ModelTable DIMENSION
            ON (SELECT model AS tokenizer FROM BYOM.embeddings_tokenizers
                 WHERE model_id = 'bge-small-en-v1.5') AS TokenizerTable DIMENSION
            USING
                Accumulate('id','txt')
                ModelOutputTensor('sentence_embedding')
                EnableMemoryCheck('false')
                OutputFormat('FLOAT32(384)')
                OverwriteCachedModel('true')
        ) AS q
    ) AS TargetTable
    ON CDC_HAI.doc_embeddings AS ReferenceTable DIMENSION
    -- narrow the corpus instead of filtering afterwards, so TopK applies to the subset:
    -- ON (SELECT * FROM CDC_HAI.doc_embeddings WHERE doc_id IN (1,2)) AS ReferenceTable DIMENSION
    USING
        TargetIDColumn('id') TargetFeatureColumns('[2:385]')
        RefIDColumn('id')    RefFeatureColumns('[4:387]')
        DistanceMeasure('cosine')
        TopK(5)
) AS vd
JOIN CDC_HAI.doc_chunks ch ON ch.CHUNK_KEY = vd.reference_id
JOIN CDC_HAI.document   d  ON d.DOC_ID     = ch.DOC_ID
ORDER BY dist;

-- Reading results: dist is cosine distance, smaller is closer.
--   0.10-0.20 strong match | 0.20-0.30 related context | >0.35 suspect.
-- CHUNK_TEXT is stored as 'Prefix: <context>; Original: <passage>'; quote the part after 'Original:'
-- and cite DOC_TITLE plus PAGE_NUMBER, never the S3 filename.
