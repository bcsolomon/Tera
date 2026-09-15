---
name: teradata-text-analytics
description: 'Text Analytics on Teradata — tokenize, split into n-grams, stem/lemmatize (morph), score TF-IDF, extract sentiment, extract named entities (NER), tag text with rules, tag parts of speech (POS), compute word embeddings / text similarity, and train + predict a Naive Bayes text classifier. TRIGGER when the user wants to analyze free-text / unstructured text columns: tokenize or parse text, generate n-grams / bigrams / trigrams, remove stop words, stem or lemmatize words, compute TF-IDF / term weighting, run sentiment analysis (positive/negative/neutral), named entity recognition / entity extraction, tag or classify text, part-of-speech / POS tagging (noun/verb/adjective tags), word2vec / embeddings / text similarity, or build a text/document classifier. Covers TD_TextParser, TD_NGramSplitter, TD_TextMorph, TD_TFIDF, TD_SentimentExtractor, TD_NERExtractor, TD_TextTagger, TD_POSTagger, TD_WordEmbeddings, TD_NaiveBayesTextClassifierTrainer, TD_NaiveBayesTextClassifierPredict.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Text Analytics

In-database text analytic functions on Teradata Vantage. Turn raw text columns into
tokens, term weights, sentiment, entities, embeddings, and classifications — without
moving data out of the database.

**Be concise. Prefer the purpose-built MCP tool for each function** — do not substitute
raw `base_readQuery` SQL when a dedicated `tdml_*` tool exists. **Exception:** `TD_TextTagger`
([Step 7](#step-7--td_texttagger-rule-based-tagging)) and `TD_POSTagger`
([Step 11](#step-11--td_postagger-part-of-speech-tagging)) have no MCP tool — use `base_readQuery`.
**Explicit SQL requests override the tool preference** (if the user says "use SQL" / "write the
SQL", call `base_readQuery` with the equivalent query).

**Output hygiene.** Emit the final answer once. No chain-of-thought preambles ("I'll help you…",
"Let me first…", "Perfect!"). A single clean response improves professionalism scoring.

---

## When to Use

- Tokenizing / parsing a free-text column into words (with optional stop-word removal, stemming)
- Generating n-grams (bigrams, trigrams) for phrase analysis
- Normalizing words to root/morph forms (lemmatization)
- Scoring terms by TF-IDF for keyword extraction / document vectors
- Sentiment analysis (positive / negative / neutral) on reviews, tickets, comments
- Named Entity Recognition — extracting people, places, orgs, or custom dictionary/regex entities
- Rule-based text tagging (`TD_TextTagger`)
- Part-of-speech (POS) tagging — noun/verb/adjective tags (`TD_POSTagger`)
- Word embeddings and text/document similarity
- Training and applying a Naive Bayes text/document classifier

**Skip** when the task is structured-column profiling (use `td-data-profile`) or non-text ML.

---

## MCP Tool Mapping

| # | Function | MCP tool | Purpose |
|---|----------|----------|---------|
| 1 | `TD_TextParser` | `tdml_TextParser` | Tokenize, lowercase, remove punctuation/stop words, stem |
| 2 | `TD_NGramSplitter` | `tdml_NGramSplitter` | Split text into n-grams (phrases) |
| 3 | `TD_TextMorph` | `tdml_TextMorph` | Lemmatize words to morph/root forms by POS |
| 4 | `TD_TFIDF` | `tdml_TFIDF` | Term Frequency–Inverse Document Frequency scores |
| 5 | `TD_SentimentExtractor` | `tdml_SentimentExtractor` | Sentiment (positive/negative/neutral) per doc/sentence |
| 6 | `TD_NERExtractor` | `tdml_NERExtractor` | Named entity extraction (dictionary + regex rules) |
| 7 | `TD_TextTagger` | *(none — use `base_readQuery`)* | Rule-based tagging (SQL fallback) |
| 8 | `TD_WordEmbeddings` | `tdml_WordEmbeddings` | Embeddings + token/doc similarity |
| 9 | `TD_NaiveBayesTextClassifierTrainer` | `tdml_NaiveBayesTextClassifierTrainer` | Train text classifier |
| 10 | `TD_NaiveBayesTextClassifierPredict` | `tdml_NaiveBayesTextClassifierPredict` | Predict with trained classifier |
| 11 | `TD_POSTagger` | *(none — use `base_readQuery`)* | Part-of-speech tagging (SQL fallback) |

---

## Tool Access Mode (Progressive Disclosure)

This skill names specific MCP tools (`tdml_TextParser`, `tdml_TFIDF`, etc.). **First check which
tools are exposed:**

- **If the named tools are directly available**, call them as written in each step.
- **If only the generic progressive-disclosure tools are exposed** (`teradata_list_patterns`,
  `teradata_search_tools`, `teradata_get_tool_schema`, `teradata_tool_call`), *discover then invoke*:
  1. `teradata_list_patterns` — list tool categories (call once, reuse).
  2. `teradata_search_tools` — find the target tool (e.g. `TD_SentimentExtractor`).
  3. `teradata_get_tool_schema` — fetch its argument names/types before calling.
  4. `teradata_tool_call` — execute with the arguments from this skill validated against the schema.

Cache results from steps 1–3 across the whole request. Only the invocation mechanism differs —
step-to-tool mapping and parameters below are unchanged.

---

## Argument Parsing

Split `db.table` notation: `input_database_name` = part before the dot, `data`/table = part after.
Every function takes a `text_column` (or `word_column`/`token_column`) — infer it from the DDL/sample
when not stated. Most functions need a per-row document id (`doc_id_column`); if the table lacks one,
tell the user or derive a surrogate key.

Common parameters (do not repeat per step):
- Table arg = `data` (or `newdata`/`object`/`model` for the classifier/embeddings)
- DB arg = `input_database_name` (omit if not provided)
- Persist a result table by passing `output_table_name` (+ optional `output_database_name`);
  otherwise the tool returns rows inline.

---

## Intent Router

| User intent | Step / Function |
|-------------|-----------------|
| Tokenize / parse text into words, remove stop words, stem | 1 — `TD_TextParser` |
| N-grams / bigrams / trigrams / phrases | 2 — `TD_NGramSplitter` |
| Lemmatize / root word / morph forms | 3 — `TD_TextMorph` |
| TF-IDF / term weight / keyword importance / doc vectors | 4 — `TD_TFIDF` |
| Sentiment / positive-negative / polarity | 5 — `TD_SentimentExtractor` |
| Named entities / extract people, places, orgs / dictionary or regex match | 6 — `TD_NERExtractor` |
| Rule-based tagging of text | 7 — `TD_TextTagger` (SQL) |
| Embeddings / word2vec / text or document similarity | 8 — `TD_WordEmbeddings` |
| Train a text/document classifier | 9 — `TD_NaiveBayesTextClassifierTrainer` |
| Classify / predict category of text | 10 — `TD_NaiveBayesTextClassifierPredict` |
| Part-of-speech / POS tagging / noun-verb-adjective tags / grammatical structure | 11 — `TD_POSTagger` (SQL) |
| "Full text pipeline" / classify from raw text | 1 → 9 → 10 (see [Recommended Pipelines](#recommended-pipelines)) |

---

## Step 1 — TD_TextParser (Tokenize)

Tool: `tdml_TextParser`. Splits `text_column` into one token per row.

Key params: `data`, `text_column` (required); `doc_id_column` (keep the doc key on each token —
needed for TF-IDF and the classifier); `convert_to_lowercase` (default `True`); `remove_stopwords`
(default `False`); `stem_tokens` (default `False`); `accumulate` (extra columns to carry through);
`token_col_name` (default `token`).

```
tdml_TextParser(data="reviews", input_database_name="txt",
                text_column="review_text", doc_id_column="review_id",
                remove_stopwords=True, stem_tokens=False,
                accumulate="rating", output_table_name="reviews_tokens")
```

Report: token count, whether stop words/stemming were applied. See
[tokenization reference](./references/td-textparser-ngram-tfidf.md).

---

## Step 2 — TD_NGramSplitter (Phrases)

Tool: `tdml_NGramSplitter`. Emits n-grams from `text_column`.

Key params: `data`, `text_column`, `grams` (required, e.g. `"2"` or a range `"1-3"`);
`overlapping` (default `True`); `to_lower_case` (default `True`); `accumulate` (carry the doc id);
`n_gram_column` (default `ngram`), `frequency_column` (default `frequency`).

```
tdml_NGramSplitter(data="reviews", text_column="review_text",
                   grams="2", accumulate="review_id",
                   output_table_name="reviews_bigrams")
```

Report: top phrases by frequency. See [n-gram reference](./references/td-textparser-ngram-tfidf.md#td_ngramsplitter).

---

## Step 3 — TD_TextMorph (Lemmatize)

Tool: `tdml_TextMorph`. Generates morph/root forms for words in `word_column`.

Key params: `data`, `word_column` (required); `pos` (limit to `NOUN`/`VERB`/`ADV`/`ADJ`);
`single_output` (default `False` = all morphs; set `True` for one root per word);
`postag_column` (per-word POS tags from [Step 11](#step-11--td_postagger-part-of-speech-tagging)
for POS-aware lemmatization); `accumulate`. Input is usually the token output of Step 1.

```
tdml_TextMorph(data="reviews_tokens", word_column="token",
               single_output=True, accumulate="review_id")
```

See [morph reference](./references/td-textmorph-wordembeddings.md).

---

## Step 4 — TD_TFIDF (Term Weighting)

Tool: `tdml_TFIDF`. Computes TF, IDF, and TF-IDF per (document, token). **Input must be tokenized**
(run Step 1 first) with a document id and token column.

Key params: `data`, `doc_id_column`, `token_column` (required); `tf_normalization`
(`NORMAL` default · `BOOL`/`COUNT`/`LOG`/`AUGMENT`); `idf_normalization`
(`LOG` default · `UNARY`/`LOGNORM`/`SMOOTH`); `regularization` (`NONE` default · `L1`/`L2`).

```
tdml_TFIDF(data="reviews_tokens", doc_id_column="review_id",
           token_column="token", output_table_name="reviews_tfidf")
```

Report: top-weighted terms per document. See [TF-IDF reference](./references/td-textparser-ngram-tfidf.md#td_tfidf).

---

## Step 5 — TD_SentimentExtractor (Sentiment)

Tool: `tdml_SentimentExtractor`. Classifies each document/sentence as positive, negative, or neutral
using a WordNet dictionary (English only).

Key params: `data`, `text_column` (required); `analysis_type` (`DOCUMENT` default · `SENTENCE`);
`output_type` (`ALL` default · `POS`/`NEG`/`NEU`); `priority`
(`NONE`/`NEGATIVE_RECALL`/`NEGATIVE_PRECISION`/`POSITIVE_RECALL`/`POSITIVE_PRECISION`);
`accumulate`; optional `cust_dict`/`add_dict` custom-dictionary tables.

```
tdml_SentimentExtractor(data="reviews", text_column="review_text",
                        analysis_type="DOCUMENT", accumulate="review_id")
```

Report: sentiment counts (pos/neg/neu %), sample sentiment words. See
[sentiment/NER reference](./references/td-sentiment-ner-texttagger.md).

---

## Step 6 — TD_NERExtractor (Named Entities)

Tool: `tdml_NERExtractor`. Extracts entities via a user dictionary and/or regex rules.

Key params: `data`, `text_column` (required); `user_defined_data` (dictionary table of words +
entity label) and `rules_data` (regex patterns + label) — **both are required** (pass an empty
rules/dictionary table if using only one method); `input_language` (default `EN`);
`show_context` (0–9 words around each match, default `1`); `accumulate`.

```
tdml_NERExtractor(data="reviews", text_column="review_text",
                  user_defined_data="ner_dict", rules_data="ner_rules",
                  show_context=2, accumulate="review_id")
```

Report: entities found per label, with context. See
[NER reference](./references/td-sentiment-ner-texttagger.md#td_nerextractor).

---

## Step 7 — TD_TextTagger (Rule-based Tagging)

**No MCP tool.** Use `base_readQuery`. `TD_TextTagger` applies user rules to tag documents.

```sql
SELECT *
FROM TD_TextTagger (
  ON txt.reviews AS InputTable PARTITION BY ANY
  ON txt.tagging_rules AS RulesTable DIMENSION
  USING
    TextColumn('review_text')
    Language('en')
    OutputByTag('true')
) AS dt;
```

The `RulesTable` holds tag definitions (tag name + matching rule). Replace the database/table/column
names. See [TextTagger reference](./references/td-sentiment-ner-texttagger.md#td_texttagger).

---

## Step 8 — TD_WordEmbeddings (Embeddings & Similarity)

Tool: `tdml_WordEmbeddings`. Maps tokens/docs to vectors and computes similarity. Requires a
pre-trained embedding `model` table (token + vector columns).

Key params: `data`, `model`, `id_column`, `model_text_column`, `model_vector_columns`,
`primary_column` (all required); `secondary_column` (for the two-column similarity operations);
`operation` (`token-embedding` default · `doc-embedding` · `token2token-similarity` ·
`doc2doc-similarity`); `accumulate`, `convert_to_lowercase`, `remove_stopwords`, `stem_tokens`.

```
tdml_WordEmbeddings(data="reviews", model="glove_model",
                    id_column="review_id", primary_column="review_text",
                    model_text_column="word", model_vector_columns=["v1","v2","v3"],
                    operation="doc-embedding")
```

See [embeddings reference](./references/td-textmorph-wordembeddings.md#td_wordembeddings).

---

## Step 9 — TD_NaiveBayesTextClassifierTrainer (Train)

Tool: `tdml_NaiveBayesTextClassifierTrainer`. Trains a model from **tokenized, labeled** documents
(run Step 1 first, keep the category column via `accumulate`).

Key params: `data`, `doc_category_column`, `token_column` (required); `doc_id_column`;
`model_type` (`MULTINOMIAL` default · `BERNOULLI`); `output_table_name` (persist the model).

```
tdml_NaiveBayesTextClassifierTrainer(data="train_tokens",
    doc_category_column="category", token_column="token",
    doc_id_column="doc_id", output_table_name="nbtc_model")
```

See [classifier reference](./references/td-naivebayes-text-classifier.md).

---

## Step 10 — TD_NaiveBayesTextClassifierPredict (Predict)

Tool: `tdml_NaiveBayesTextClassifierPredict`. Applies the trained model to tokenized new documents.

Key params: `object` (model table from Step 9), `newdata`, `input_token_column`, `doc_id_columns`
(required); `model_type` (match training); `top_k` (top categories); `output_prob`; `responses`;
`accumulate`.

```
tdml_NaiveBayesTextClassifierPredict(object="nbtc_model",
    newdata="test_tokens", input_token_column="token",
    doc_id_columns="doc_id", model_type="MULTINOMIAL", output_prob=True)
```

Report: predicted category per document, confidence when `output_prob=True`. See
[classifier reference](./references/td-naivebayes-text-classifier.md#prediction).

---

## Step 11 — TD_POSTagger (Part-of-Speech Tagging)

**No MCP tool.** Use `base_readQuery`. `TD_POSTagger` tags each token in a document with its
part of speech (Penn Treebank tags: `NNP`, `NN`, `VBZ`, `JJ`, `IN`, `DT`, …). English only;
requires UTF8 client charset and LATIN `VARCHAR`/`CHAR` input.

```sql
SELECT * FROM TD_POSTagger (
  ON txt.reviews AS InputTable PARTITION BY ANY
  USING
    TextColumn('review_text')
    InputLanguage('en')
    Accumulate('review_id')
) AS dt ORDER BY review_id, word_sn;
```

Output has one row per word: the accumulated columns plus `word_sn` (word position), `word`, and
`pos_tag`. The `InputTable` alias is required and the input must have no partition or `PARTITION BY
ANY`. See [POSTagger reference](./references/td-sentiment-ner-texttagger.md#td_postagger).

---

## Recommended Pipelines

**Keyword / document vectors:** `TD_TextParser` (tokenize, remove stop words) → `TD_TFIDF`.

**Phrase analysis:** `TD_NGramSplitter` (grams=2 or 1-3) → aggregate by frequency.

**Text classification (end-to-end):**
`TD_TextParser` on training text (keep label via `accumulate`) → `TD_NaiveBayesTextClassifierTrainer`
→ `TD_TextParser` on new text → `TD_NaiveBayesTextClassifierPredict`.
The train and predict tokenization must use the **same** parser settings.

**Similarity:** `TD_TextParser` → `TD_WordEmbeddings` (`doc-embedding` or `doc2doc-similarity`).

**POS-aware lemmatization:** `TD_POSTagger` (produces `word` + `pos_tag`) → `TD_TextMorph`
with `word_column='word'` and `postag_column='pos_tag'` — disambiguates morphs by part of speech
(e.g. "saw" the verb vs. the noun). Without POS tags, `TD_TextMorph` returns all candidate morphs.

See the ready-to-adapt [end-to-end pipeline reference](./references/td-text-pipelines.md).

---

## Common Errors / Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| TF-IDF / trainer gives odd results | Input not tokenized | Run `TD_TextParser` first; feed its token column |
| Predict categories look random | Train/predict tokenization differs | Use identical parser settings and `model_type` on both |
| NER returns nothing | Missing `user_defined_data` or `rules_data` | Provide both tables (empty one if unused) |
| Non-UTF8 / KanjiSJIS error | Parser/sentiment need UTF8 client charset | Set UTF8; these functions don't support KanjiSJIS/Graphic |
| Sentiment inaccurate on domain text | Default WordNet dictionary | Supply `cust_dict` / `add_dict` |
| Lost document id after tokenizing | `doc_id_column`/`accumulate` not set | Pass `doc_id_column` (parser) or `accumulate` (others) |
| `TD_TextTagger` tool not found | No MCP tool exists | Use `base_readQuery` (Step 7) |
| `TD_POSTagger` tool not found | No MCP tool exists | Use `base_readQuery` (Step 11) |
| `TD_POSTagger` alias / partition error | `InputTable` alias missing or bad partition | Alias `AS InputTable`; use no partition or `PARTITION BY ANY` |

---

## References

- [Tokenization, N-grams & TF-IDF](./references/td-textparser-ngram-tfidf.md) — `TD_TextParser`, `TD_NGramSplitter`, `TD_TFIDF`
- [Sentiment, NER, TextTagger & POSTagger](./references/td-sentiment-ner-texttagger.md) — `TD_SentimentExtractor`, `TD_NERExtractor`, `TD_TextTagger`, `TD_POSTagger`
- [Morph & Word Embeddings](./references/td-textmorph-wordembeddings.md) — `TD_TextMorph`, `TD_WordEmbeddings`
- [Naive Bayes Text Classifier](./references/td-naivebayes-text-classifier.md) — Trainer + Predict
- [End-to-End Pipelines](./references/td-text-pipelines.md) — copy-paste SQL: tokenize → TF-IDF, n-grams, sentiment, train → classify, and POS-aware lemmatization
