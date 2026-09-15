# Naive Bayes Text Classifier — Complete Reference

> Functions: `TD_NaiveBayesTextClassifierTrainer`, `TD_NaiveBayesTextClassifierPredict`
> Source: Teradata Vantage In-Database Analytic Functions — Text Analytic Functions

A two-step supervised text classifier. The trainer computes token-category conditional probabilities,
prior probabilities, and missing-token probabilities; the predictor applies that model to classify new
documents. **Both steps require tokenized input** — run `TD_TextParser` first, and use identical
tokenization for training and prediction.

---

## Model types

| `model_type` | Use when |
|--------------|----------|
| `MULTINOMIAL` (default) | Token counts matter (typical for document classification) |
| `BERNOULLI` | Only token presence/absence matters (short texts, binary features) |

Use the **same `model_type`** in both trainer and predict.

---

## Training

### `TD_NaiveBayesTextClassifierTrainer` parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `data` | Yes | — | Tokenized, labeled training data |
| `doc_category_column` | Yes | — | Column with the document category/label |
| `token_column` | Yes | — | Column with tokens |
| `doc_id_column` | No | — | Column with the document identifier |
| `model_type` | No | `MULTINOMIAL` | `MULTINOMIAL` or `BERNOULLI` |
| `input_database_name` / `output_table_name` / `output_database_name` | No | — | DB / persist the model |

The model output has three key columns by default: token, category, and probability/count — in that
column order (relevant when overriding `model_*_column` in predict).

### Example

Tokenize labeled documents first (keep the label via `accumulate`):

```
tdml_TextParser(data="train_docs", text_column="body",
                doc_id_column="doc_id", remove_stopwords=True,
                accumulate=["doc_id","category"],
                output_table_name="train_tokens")
```

Then train and persist the model:

```
tdml_NaiveBayesTextClassifierTrainer(
    data="train_tokens",
    doc_category_column="category",
    token_column="token",
    doc_id_column="doc_id",
    model_type="MULTINOMIAL",
    output_table_name="nbtc_model")
```

---

## Prediction

### `TD_NaiveBayesTextClassifierPredict` parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `object` | Yes | — | Model table from the trainer |
| `newdata` | Yes | — | Tokenized new documents |
| `input_token_column` | Yes | — | Token column in `newdata` |
| `doc_id_columns` | Yes | — | Document identifier column(s) |
| `model_type` | No | `MULTINOMIAL` | Must match training |
| `top_k` | No | all | Number of most-likely categories to output with log-likelihoods |
| `model_token_column` | No | 1st model col | Token column in `object` |
| `model_category_column` | No | 2nd model col | Category column in `object` |
| `model_prob_column` | No | 3rd model col | Token-count/probability column in `object` |
| `output_prob` | No | `False` | Output probabilities |
| `responses` | No | — | List of responses (categories) to output |
| `accumulate` | No | — | Columns from `newdata` to copy to output |
| `input_database_name` / `output_table_name` / `output_database_name` | No | — | DB / persistence |

### Example

Tokenize new documents with the **same** parser settings as training:

```
tdml_TextParser(data="test_docs", text_column="body",
                doc_id_column="doc_id", remove_stopwords=True,
                accumulate="doc_id", output_table_name="test_tokens")
```

Predict categories, returning the top 3 with probabilities:

```
tdml_NaiveBayesTextClassifierPredict(
    object="nbtc_model",
    newdata="test_tokens",
    input_token_column="token",
    doc_id_columns="doc_id",
    model_type="MULTINOMIAL",
    top_k=3, output_prob=True,
    output_table_name="test_predictions")
```

Output has one row per document (or per top-k category) with the predicted category and, when
`output_prob=True`, its log-likelihood / probability.

---

## End-to-end checklist

1. `TD_TextParser` on training text → keep `doc_id` and `category` via `accumulate`.
2. `TD_NaiveBayesTextClassifierTrainer` → persist model with `output_table_name`.
3. `TD_TextParser` on new text → **same** lowercase / stop-word / stem settings.
4. `TD_NaiveBayesTextClassifierPredict` → same `model_type` as step 2.

### Common pitfalls

| Pitfall | Fix |
|---------|-----|
| Predictions look random | Train/predict tokenization or `model_type` differ — make them identical |
| Every doc gets the majority class | Class imbalance or too few tokens — clean/stopword-filter, add data |
| Model table columns unmapped | Override `model_token_column` / `model_category_column` / `model_prob_column` |
| Category label lost after tokenizing | Add it to `accumulate` in the training `TD_TextParser` call |
