# Morph & Word Embeddings — Complete Reference

> Functions: `TD_TextMorph`, `TD_WordEmbeddings`
> Source: Teradata Vantage In-Database Analytic Functions — Text Analytic Functions

`TD_TextMorph` normalizes words to their morph/root forms (lemmatization). `TD_WordEmbeddings` maps
tokens or documents to vectors and computes similarity.

---

## TD_TextMorph

Generates morphs (root/lemma forms) of words. Unlike the stemmer in `TD_TextParser`, morphs are real
dictionary forms and can be constrained by part of speech.

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `data` | Yes | — | Input table |
| `word_column` | Yes | — | Column of words to morph |
| `pos` | No | all | Part of speech to output: `NOUN`, `VERB`, `ADV`, `ADJ` (str or list) |
| `single_output` | No | `False` | `True` = one morph per word; `False` = all morphs |
| `postag_column` | No | — | Column with POS tags from `TD_POSTagger` |
| `accumulate` | No | — | Columns to copy to output |
| `input_database_name` / `output_table_name` / `output_database_name` | No | — | DB / persistence |

### Examples

Single root form per token (typical for normalization before classification):

```
tdml_TextMorph(data="reviews_tokens", word_column="token",
               single_output=True, accumulate="review_id",
               output_table_name="reviews_lemmas")
```

Only verb morphs:

```
tdml_TextMorph(data="reviews_tokens", word_column="token",
               pos="VERB", single_output=True)
```

### Morph vs. stem

| Approach | Function | Output | Example |
|----------|----------|--------|---------|
| Stemming | `TD_TextParser` (`stem_tokens=True`) | May not be a real word | `earli` |
| Lemmatization | `TD_TextMorph` | Real dictionary form | `early` |

Use morph when downstream steps or humans need readable roots; use stemming for speed within a
pure ML pipeline.

---

## TD_WordEmbeddings

Represents words/documents as vectors in multi-dimensional space, where similar meanings map to
similar vectors. Requires a **pre-trained embedding model table** (each token and its vector columns,
e.g. GloVe or word2vec loaded into Vantage).

### Operations

| `operation` | Meaning |
|-------------|---------|
| `token-embedding` (default) | Vector for each token |
| `doc-embedding` | Aggregate vector for each document |
| `token2token-similarity` | Similarity between two token columns |
| `doc2doc-similarity` | Similarity between two document columns |

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `data` | Yes | — | Input table |
| `model` | Yes | — | Model table: tokens + vector columns |
| `id_column` | Yes | — | Unique row identifier in the input |
| `model_text_column` | Yes | — | Token column in `model` |
| `model_vector_columns` | Yes | — | Range/list of vector columns in `model` |
| `primary_column` | Yes | — | Input text column |
| `secondary_column` | No | — | Second text column (for `*2*-similarity` operations) |
| `operation` | No | `token-embedding` | See table above |
| `accumulate` | No | — | Columns to copy (not for `token-embedding`) |
| `convert_to_lowercase` | No | `True` | Lowercase input |
| `remove_stopwords` | No | `False` | Remove stop words (not for `token2token-similarity`) |
| `stem_tokens` | No | `False` | Reduce words to root form |
| `input_database_name` / `output_table_name` / `output_database_name` | No | — | DB / persistence |

### Examples

Document embeddings for reviews:

```
tdml_WordEmbeddings(data="reviews", model="glove_model",
                    id_column="review_id", primary_column="review_text",
                    model_text_column="word",
                    model_vector_columns=["v1","v2","v3","v4","v5"],
                    operation="doc-embedding",
                    output_table_name="reviews_docvecs")
```

Document-to-document similarity between two text columns:

```
tdml_WordEmbeddings(data="pairs", model="glove_model",
                    id_column="pair_id",
                    primary_column="text_a", secondary_column="text_b",
                    model_text_column="word",
                    model_vector_columns=["v1","v2","v3","v4","v5"],
                    operation="doc2doc-similarity", accumulate="pair_id")
```

### Notes

- The `model_vector_columns` count is the embedding dimensionality — pass every vector column.
- Closer vectors (smaller distance / higher cosine) mean higher similarity.
- Pre-load the embedding model as a Vantage table before calling; the function does not train
  embeddings from scratch.
