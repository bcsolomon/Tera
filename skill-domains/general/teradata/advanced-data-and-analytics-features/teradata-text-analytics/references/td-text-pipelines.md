# Teradata Text Analytics — End-to-End Pipeline Reference

Ready-to-adapt SQL for the common text-analytics pipelines. **Prefer the MCP tools**
(`tdml_TextParser`, `tdml_TFIDF`, `tdml_NaiveBayesTextClassifierTrainer`, …) when available —
this SQL is the fallback / reference form. `TD_TextTagger` and `TD_POSTagger` have **no MCP
tool**, so always run those via `base_readQuery`.

Replace these placeholders throughout:

| Placeholder | Meaning |
|-------------|---------|
| `txt` | database name |
| `reviews` | source text table (`review_id`, `review_text`, `[rating]`) |
| `train_docs` | labeled training table (`doc_id`, `body`, `category`) |
| `test_docs` | new documents to classify (`doc_id`, `body`) |

Pipelines:

- **A.** Tokenize → TF-IDF (keyword / document vectors)
- **B.** N-grams (phrase analysis)
- **C.** Sentiment (document polarity)
- **D.** Tokenize → Train → Tokenize → Predict (text classification)
- **E.** POS-tag → Morph (POS-aware lemmatization)

---

## A. Keyword / Document-Vector Pipeline: Tokenize → TF-IDF

```sql
-- 1) Tokenize (lowercase + remove stop words), keep the document id
CREATE TABLE txt.reviews_tokens AS (
  SELECT *
  FROM TD_TextParser (
    ON txt.reviews AS InputTable
    USING
      TextColumn('review_text')
      ConvertToLowerCase('true')
      RemoveStopWords('true')
      StemTokens('false')
      Accumulate('review_id')
  ) AS dt
) WITH DATA;

-- 2) TF-IDF scores per (review_id, token)
SELECT *
FROM TD_TFIDF (
  ON txt.reviews_tokens AS InputTable
  USING
    DocIdColumn('review_id')
    TokenColumn('token')
    TFNormalization('NORMAL')
    IDFNormalization('LOG')
    Regularization('L2')
) AS dt
ORDER BY review_id, tf_idf DESC;
```

---

## B. Phrase Analysis: N-grams (bigrams) by frequency

```sql
SELECT ngram, SUM(frequency) AS total_freq
FROM TD_NGramSplitter (
  ON txt.reviews AS InputTable
  USING
    TextColumn('review_text')
    Grams('2')
    Overlapping('true')
    ToLowerCase('true')
    Accumulate('review_id')
) AS dt
GROUP BY ngram
ORDER BY total_freq DESC;
```

---

## C. Sentiment: document-level polarity

```sql
SELECT *
FROM TD_SentimentExtractor (
  ON txt.reviews AS InputTable
  USING
    TextColumn('review_text')
    AnalysisType('DOCUMENT')
    Accumulate('review_id')
) AS dt;
```

---

## D. Text Classification: Tokenize → Train → Tokenize → Predict

```sql
-- 1) Tokenize labeled training docs (keep doc_id + category)
CREATE TABLE txt.train_tokens AS (
  SELECT *
  FROM TD_TextParser (
    ON txt.train_docs AS InputTable
    USING
      TextColumn('body')
      ConvertToLowerCase('true')
      RemoveStopWords('true')
      Accumulate('doc_id','category')
  ) AS dt
) WITH DATA;

-- 2) Train the Naive Bayes text classifier -> model table
CREATE TABLE txt.nbtc_model AS (
  SELECT *
  FROM TD_NaiveBayesTextClassifierTrainer (
    ON txt.train_tokens AS InputTable
    USING
      DocCategoryColumn('category')
      TokenColumn('token')
      DocIdColumn('doc_id')
      ModelType('MULTINOMIAL')
  ) AS dt
) WITH DATA;

-- 3) Tokenize new docs with the SAME settings as training
CREATE TABLE txt.test_tokens AS (
  SELECT *
  FROM TD_TextParser (
    ON txt.test_docs AS InputTable
    USING
      TextColumn('body')
      ConvertToLowerCase('true')
      RemoveStopWords('true')
      Accumulate('doc_id')
  ) AS dt
) WITH DATA;

-- 4) Predict category per document (top 3 with probabilities)
SELECT *
FROM TD_NaiveBayesTextClassifierPredict (
  ON txt.test_tokens AS InputTable PARTITION BY doc_id
  ON txt.nbtc_model  AS Model DIMENSION
  USING
    InputTokenColumn('token')
    DocIdColumns('doc_id')
    ModelType('MULTINOMIAL')
    TopK(3)
    OutputProb('true')
) AS dt;
```

> The train and predict tokenization **must use identical parser settings** and the same
> `ModelType`, or predictions will look random.

---

## E. POS-Aware Lemmatization: POS-tag → Morph

`TD_POSTagger` has no MCP tool; run step 1 via `base_readQuery`.

```sql
-- 1) Tag each word with its part of speech (emits word_sn, word, pos_tag)
CREATE TABLE txt.reviews_pos AS (
  SELECT *
  FROM TD_POSTagger (
    ON txt.reviews AS InputTable PARTITION BY ANY
    USING
      TextColumn('review_text')
      InputLanguage('en')
      Accumulate('review_id')
  ) AS dt
) WITH DATA;

-- 2) Lemmatize using the POS tags so morphs are disambiguated by part of speech
SELECT *
FROM TD_TextMorph (
  ON txt.reviews_pos AS InputTable
  USING
    WordColumn('word')
    POSTagColumn('pos_tag')
    SingleOutput('true')
    Accumulate('review_id','word_sn')
) AS dt
ORDER BY review_id, word_sn;
```
