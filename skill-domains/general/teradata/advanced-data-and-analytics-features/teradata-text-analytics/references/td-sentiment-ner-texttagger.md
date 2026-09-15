# Sentiment, NER, TextTagger & POSTagger — Complete Reference

> Functions: `TD_SentimentExtractor`, `TD_NERExtractor`, `TD_TextTagger`, `TD_POSTagger`
> Source: Teradata Vantage In-Database Analytic Functions — Text Analytic Functions

These functions extract meaning from text: sentiment polarity, named entities, rule-based tags, and
part-of-speech tags. `TD_SentimentExtractor` and `TD_NERExtractor` have MCP tools; `TD_TextTagger`
and `TD_POSTagger` do not — use `base_readQuery`.

---

## TD_SentimentExtractor

Extracts sentiment (positive / negative / neutral) of each document or sentence using a WordNet
dictionary plus negation words (no, not, neither, never, …). English only.

### Negation handling

- `-1` if sentiment is negated — "I am not happy"
- `-1` if sentiment and negation are separated by one word — "I am not very happy"
- `+1` if separated by two or more words — "I am not saying I am happy"

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `data` | Yes | — | Input table |
| `text_column` | Yes | — | Column with text to analyze |
| `cust_dict` | No | — | Custom dictionary table (replaces default) |
| `add_dict` | No | — | Additional entries added to cust/default dictionary |
| `analysis_type` | No | `DOCUMENT` | `DOCUMENT` (whole doc) or `SENTENCE` (per sentence) |
| `priority` | No | `NONE` | `NONE`, `NEGATIVE_RECALL`, `NEGATIVE_PRECISION`, `POSITIVE_RECALL`, `POSITIVE_PRECISION` |
| `output_type` | No | `ALL` | `ALL`, `POS`, `NEG`, `NEU` |
| `accumulate` | No | — | Columns to copy to output |
| `input_database_name` / `output_table_name` / `output_database_name` | No | — | DB / persistence |

### Limits

- Max sentiment word in dictionary: 128 chars. Max `sentiment_words` output: 32000 chars.
- Max sentence / `content` length: 32000 chars. Up to 10 words per sentiment phrase.
- Requires UTF8 client charset; no PTCs, KanjiSJIS, or Graphic types.

### Examples

Document-level sentiment on reviews:

```
tdml_SentimentExtractor(data="reviews", text_column="review_text",
                        analysis_type="DOCUMENT", accumulate="review_id")
```

Return only negative results, maximizing recall:

```
tdml_SentimentExtractor(data="tickets", text_column="body",
                        output_type="NEG", priority="NEGATIVE_RECALL",
                        accumulate="ticket_id")
```

Output includes the sentiment polarity, a confidence/strength, and the matched sentiment words.
Aggregate the polarity column for pos/neg/neu percentages.

---

## TD_NERExtractor

Named Entity Recognition using user-defined dictionary words and/or regex patterns. Both a dictionary
table and a rules table are required arguments — supply an empty table for the method you don't use.

### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `data` | Yes | — | Input table |
| `text_column` | Yes | — | Column searched for entities |
| `user_defined_data` | Yes | — | Table of words + entity label (dictionary NER) |
| `rules_data` | Yes | — | Table of regex patterns + entity label (rule NER) |
| `input_language` | No | `EN` | Language of input text |
| `show_context` | No | `1` | Words before/after each match (positive, < 10); ellipsis if fewer exist |
| `accumulate` | No | — | Columns to copy to output |
| `input_database_name` / `output_table_name` / `output_database_name` | No | — | DB / persistence |

Each input table also accepts `*_partition_column` / `*_order_column` arguments for `data`,
`user_defined_data`, and `rules_data`.

### Dictionary and rules tables

- **`user_defined_data`** — one row per known entity: the word/phrase and its label
  (e.g. `Teradata` → `ORG`, `California` → `LOCATION`).
- **`rules_data`** — one row per regex pattern and its label
  (e.g. `\d{3}-\d{2}-\d{4}` → `SSN`, `[A-Z0-9._%+-]+@[A-Z0-9.-]+` → `EMAIL`).

### Example

```
tdml_NERExtractor(data="reviews", text_column="review_text",
                  user_defined_data="ner_dict", rules_data="ner_rules",
                  input_language="EN", show_context=2,
                  accumulate="review_id", output_table_name="reviews_entities")
```

Output includes the matched entity, its label, position, and surrounding context. Group by label to
count entity types.

---

## TD_TextTagger

Applies user-defined rules to tag documents. **No MCP tool** — call via `base_readQuery`.
`TD_TextTagger` reads an input table plus a rules (DIMENSION) table of tag definitions.

### SQL syntax

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

### Rules table

Each rule row typically defines a tag name and a matching expression (keyword, dictionary, or pattern
rule). Consult the tagging-rule syntax for the installed Vantage version. Example intent:

| tag | rule |
|-----|------|
| `complaint` | contains ("refund" OR "broken" OR "worst") |
| `praise` | contains ("excellent" OR "love" OR "great") |

### Notes

- Use `OutputByTag('true')` to emit one row per matched tag per document.
- Filter tags downstream with a normal `WHERE` clause on the output.
- Because there is no MCP tool, always run this through `base_readQuery`; if the user explicitly
  wants tagging without SQL, explain that `TD_TextTagger` is only available via SQL in this environment.

---

## TD_POSTagger

Tags each token in a document with its part of speech, supporting grammatical-structure analysis and
POS-pattern extraction. **No MCP tool** — call via `base_readQuery`. English only.

### SQL syntax

```sql
SELECT * FROM TD_POSTagger (
  ON txt.reviews AS InputTable PARTITION BY ANY
  USING
    TextColumn('review_text')
    [ InputLanguage('en') ]
    [ Accumulate('review_id' [,...]) ]
) AS dt ORDER BY review_id, word_sn;
```

Callable from a `SELECT` FROM clause or inside a `CREATE TABLE` / `CREATE VIEW` statement.

### Arguments

| Element | Required | Default | Description |
|---------|----------|---------|-------------|
| `ON … AS InputTable` | Yes | — | Input table/view/query. Alias `InputTable` is mandatory; use no partition or `PARTITION BY ANY` |
| `TextColumn` | Yes | — | Column holding the input text (`VARCHAR`/`CLOB`) |
| `InputLanguage` | No | `'en'` | Language of input text; only English supported |
| `Accumulate` | No | — | Columns copied through to the output |

### Output

| Column | Data type | Description |
|--------|-----------|-------------|
| accumulate columns | ANY | Columns copied from input |
| `word_sn` | INTEGER | Word serial number (position in the text) |
| `word` | VARCHAR(2048) | Token extracted from the input text |
| `pos_tag` | VARCHAR(20) | Part-of-speech tag of the word |

### POS tags

Uses Penn Treebank-style tags, e.g. `NNP` (proper noun), `NN` (noun), `NNS` (plural noun),
`VBZ`/`VBN`/`VBG` (verb forms), `JJ` (adjective), `IN` (preposition), `DT` (determiner),
`CC` (conjunction), `PRP$` (possessive pronoun), `O` (other/punctuation).

### Notes

- Requires the UTF8 client character set for UNICODE data.
- Supported input datatypes: `VARCHAR`/`CHAR` **CHARACTER SET LATIN** only (no PTCs / KanjiSJIS / Graphic).
- Feed `word` + `pos_tag` into `TD_TextMorph`'s `POSTagColumn` argument for POS-aware lemmatization.
- Because there is no MCP tool, always run this through `base_readQuery`.
