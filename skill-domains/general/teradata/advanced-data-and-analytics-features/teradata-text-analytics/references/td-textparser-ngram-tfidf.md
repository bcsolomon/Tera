# Tokenization, N-grams & TF-IDF — Complete Reference

> Functions: `TD_TextParser`, `TD_NGramSplitter`, `TD_TFIDF`
> Source: Teradata Vantage In-Database Analytic Functions — Text Analytic Functions

These three functions form the core tokenization → weighting pipeline. `TD_TextParser` splits text
into tokens, `TD_NGramSplitter` produces multi-word phrases, and `TD_TFIDF` scores each token's
importance per document. All three require the UTF8 client character set and do not support
KanjiSJIS or Graphic data types.

---

## TD_TextParser

Parses a text column into tokens. Operations: tokenize, lowercase, remove punctuation, remove stop
words, stem (root form), and emit one row per token (default) or all tokens in one row.

> **Stemming note:** stems may not be real words — `communicate` → `commun`, `early` → `earli`.

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `data` | Yes | — | Input table name |
| `text_column` | Yes | — | Column to tokenize |
| `object` | No | — | Table containing stop words |
| `doc_id_column` | No | — | Column that uniquely identifies each input row (carry to output) |
| `convert_to_lowercase` | No | `True` | Lowercase the text |
| `stem_tokens` | No | `False` | Reduce tokens to root form |
| `remove_stopwords` | No | `False` | Remove stop words before parsing |
| `enforce_token_limit` | No | `False` | Error on tokens > 64K/32K vs. silently discard |
| `accumulate` | No | — | Columns to copy to output (single str or list) |
| `delimiter` | No | whitespace | Word delimiter |
| `delimiter_regex` | No | — | PCRE regex delimiter |
| `punctuation` | No | ``!#$%&()*+,-./:;?@\^_`{|}~`` | Chars replaced with space |
| `token_col_name` | No | `token` | Output token column name |
| `list_positions` | No | `False` | Output word positions as a list |
| `token_frequency` | No | `False` | Output per-token frequency |
| `output_by_word` | No | `True` | One token per row vs. all tokens in one row |
| `input_database_name` | No | — | Database of input table |
| `output_table_name` / `output_database_name` | No | — | Persist results to a table |

### Examples

Tokenize reviews, drop stop words, keep the document id and rating:

```
tdml_TextParser(
  data="reviews", input_database_name="txt",
  text_column="review_text", doc_id_column="review_id",
  remove_stopwords=True, convert_to_lowercase=True,
  accumulate=["review_id", "rating"],
  output_table_name="reviews_tokens")
```

Tokenize with stemming (for TF-IDF / classification consistency):

```
tdml_TextParser(data="reviews", text_column="review_text",
                doc_id_column="review_id", stem_tokens=True,
                remove_stopwords=True, output_table_name="reviews_stemmed")
```

### SQL fallback (if the MCP tool is unavailable)

```sql
SELECT *
FROM TD_TextParser (
  ON txt.reviews AS InputTable
  USING
    TextColumn('review_text')
    ConvertToLowerCase('true')
    RemoveStopWords('true')
    StemTokens('false')
    Accumulate('review_id','rating')
) AS dt;
```

---

## TD_NGramSplitter

Tokenizes text into n-grams (n-word phrases). More flexible than single-word tokenization — captures
phrases like "machine learning" that unigrams miss. Available on Vantage 1.1+.

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `data` | Yes | — | Input table (each row is a document) |
| `text_column` | Yes | — | Column with input text (SQL string type) |
| `grams` | Yes | — | n-gram length; single `"2"` or range `"1-3"` (positive ints, int1 ≤ int2) |
| `delimiter` | No | `[\s]+` | Word separator (char/string/regex) |
| `overlapping` | No | `True` | Allow overlapping n-grams |
| `to_lower_case` | No | `True` | Lowercase input |
| `punctuation` | No | `` `~#^&*()- `` | Punctuation removed before evaluation |
| `reset` | No | `.,?!` | Chars that end a sentence (n-grams don't span sentences) |
| `total_gram_count` | No | `False` | Return total n-gram count per row |
| `total_count_column` | No | `totalcnt` | Name for the total-count column |
| `accumulate` | No | all input cols | Columns to return per n-gram |
| `n_gram_column` | No | `ngram` | Output n-gram column name |
| `num_grams_column` | No | `n` | Output n-gram length column name |
| `frequency_column` | No | `frequency` | Count of each unique n-gram in the document |
| `input_database_name` / `output_table_name` / `output_database_name` | No | — | DB / persistence |

### Examples

Bigrams with the document id carried through:

```
tdml_NGramSplitter(data="reviews", text_column="review_text",
                   grams="2", accumulate="review_id",
                   output_table_name="reviews_bigrams")
```

Unigrams through trigrams in one call:

```
tdml_NGramSplitter(data="reviews", text_column="review_text",
                   grams="1-3", overlapping=True, accumulate="review_id")
```

---

## TD_TFIDF

Computes Term Frequency–Inverse Document Frequency for each (document, token) pair — the standard
weighting for keyword extraction and document vectors. **Input must be tokenized first** (run
`TD_TextParser`), with one token per row plus a document-id column.

TF-IDF rewards tokens frequent in a document but rare across the corpus:

$$\text{tfidf}(t,d) = \text{tf}(t,d) \times \text{idf}(t)$$

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `data` | Yes | — | Tokenized input (one token per row) |
| `doc_id_column` | Yes | — | Column identifying each document |
| `token_column` | Yes | — | Column with tokens |
| `tf_normalization` | No | `NORMAL` | `NORMAL` (count / doc length) · `BOOL` (0/1) · `COUNT` (raw) · `LOG` · `AUGMENT` |
| `idf_normalization` | No | `LOG` | `LOG` · `UNARY` (idf=1) · `LOGNORM` · `SMOOTH` |
| `regularization` | No | `NONE` | Normalize the TF-IDF vector: `NONE` · `L1` · `L2` |
| `accumulate` | No | — | Extra columns to carry through |
| `input_database_name` / `output_table_name` / `output_database_name` | No | — | DB / persistence |

Output columns: `doc_id`, `token`, `tf`, `idf`, `tf_idf`.

### Normalization guidance

| Goal | Setting |
|------|---------|
| Balanced default for most corpora | `tf_normalization=NORMAL`, `idf_normalization=LOG` |
| Presence-only features (short texts) | `tf_normalization=BOOL` |
| Cosine-similarity-ready document vectors | `regularization=L2` |
| Rare-token emphasis dampened | `idf_normalization=SMOOTH` |

### Example

Tokenize, then score TF-IDF and keep the top terms per document:

```
tdml_TextParser(data="reviews", text_column="review_text",
                doc_id_column="review_id", remove_stopwords=True,
                output_table_name="reviews_tokens")

tdml_TFIDF(data="reviews_tokens", doc_id_column="review_id",
           token_column="token", tf_normalization="NORMAL",
           idf_normalization="LOG", regularization="L2",
           output_table_name="reviews_tfidf")
```

### SQL fallback

```sql
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

### Common issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| All IDF values equal | Single document, or `idf_normalization=UNARY` | Provide a multi-document corpus; use `LOG` |
| Weights not comparable across docs | No vector normalization | Set `regularization=L2` |
| Empty / wrong scores | Input not tokenized | Run `TD_TextParser` first and feed its token column |

Computes Term Frequency (TF), Inverse Document Frequency (IDF), and TF-IDF per (document, token).
**Input must already be tokenized** — run `TD_TextParser` first and feed the token column plus a
document id.

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `data` | Yes | — | Tokenized input (doc id + token) |
| `doc_id_column` | Yes | — | Document identifier column |
| `token_column` | Yes | — | Token column |
| `tf_normalization` | No | `NORMAL` | TF method: `BOOL`, `COUNT`, `NORMAL`, `LOG`, `AUGMENT` |
| `idf_normalization` | No | `LOG` | IDF method: `UNARY`, `LOG`, `LOGNORM`, `SMOOTH` |
| `regularization` | No | `NONE` | TF-IDF regularization: `L2`, `L1`, `NONE` |
| `accumulate` | No | — | Extra columns to copy through |
| `input_database_name` / `output_table_name` / `output_database_name` | No | — | DB / persistence |

### Normalization guidance

- **TF** — `NORMAL` (count ÷ doc length) suits most cases; `LOG` dampens frequent terms; `BOOL`
  is presence/absence; `AUGMENT` guards against long-document bias.
- **IDF** — `LOG` (default) is standard; `SMOOTH` avoids divide-by-zero for unseen terms.
- **Regularization** — `L2` normalizes document vectors to unit length (good before cosine similarity).

### Example

```
tdml_TFIDF(data="reviews_tokens", doc_id_column="review_id",
           token_column="token",
           tf_normalization="NORMAL", idf_normalization="LOG",
           regularization="L2", output_table_name="reviews_tfidf")
```

Output columns include the document id, token, TF, IDF, and TF-IDF score. Rank by TF-IDF descending
per document for the top keywords.
