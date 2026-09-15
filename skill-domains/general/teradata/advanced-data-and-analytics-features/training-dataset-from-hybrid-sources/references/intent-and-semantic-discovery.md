# Intent and Semantic Discovery — Complete Reference

> Covers Phases 1–2 of the `training-dataset-from-hybrid-sources` pipeline: turning a vague
> business request into a machine-readable plan (problem type, expected entities, expected
> label) and expanding that plan into the concept vocabulary used to drive database and table
> discovery in later phases.

## Phase 1 — Intent Understanding

Before touching any MCP tool, infer four things from the user's request:

1. **Prediction target** — the real-world outcome the model will predict (default, churn,
   cluster membership, an anomaly flag, a demand quantity, an association rule, a text label).
2. **ML problem type** — classification, regression, clustering/segmentation, anomaly detection,
   association rules, or text classification.
3. **Candidate feature groups** — the business entities whose attributes are likely to carry
   signal (customer demographics, account/product attributes, transaction/event history,
   external enrichment).
4. **Expected label** — where the ground-truth outcome most likely lives (an EDW flag column, an
   external enrichment feed, or something that must be derived from event history).

These four values become the **output contract** of Phase 1 and are passed into Phase 2 and into
database/table discovery (Phases 3–5) as ranking inputs.

### Problem-Type Signal Table

| Request signal (trigger words) | Problem type | Typical label shape |
|---|---|---|
| "default", "churn", "will leave/cancel", "fraud is/isn't", "classify by category" | Classification | Binary or multi-class flag column |
| "forecast", "predict demand/revenue/volume", "estimate a quantity" | Regression | Continuous numeric column |
| "segment", "group customers", "find clusters/personas" | Clustering / segmentation | No label — unsupervised, entity-grain feature table only |
| "unusual", "anomalous", "outlier accounts/transactions" | Anomaly detection | No label, or a rare-positive flag used only for evaluation |
| "frequently bought together", "market basket", "association rules" | Association rules | Transaction/basket ID + item ID, no single label column |
| "classify tickets/text by topic", "sentiment of reviews" | Text classification | Categorical label attached to a text column |

### Worked Example — Patient Readmission (Classification)

Request: *"Build a patient readmission training dataset from our patient, admission, and lab
history plus the external insurance-claims feed."*

- Problem type: **Classification**
- Expected entities: patient, admission, lab, diagnosis, claims
- Expected label: most likely an external `readmit_flag`-style column on the claims feed, since
  EDW admission/lab history rarely carries a final 30-day-readmission outcome directly.

### Worked Example — Subscription Churn (Classification)

Request: *"Build a churn dataset merging streaming-usage and billing tables with support-ticket data
sitting in S3 parquet files."*

- Problem type: **Classification**
- Expected entities: subscriber, streaming usage, billing, support ticket history
- Expected label: an EDW churn/exited flag column on the subscriber entity table (e.g. `Churn` or
  `Exited`), enriched with usage and support-ticket features.

### Worked Example — Retail Recommendation (Association / Feature Table)

Request: *"Build the clickstream + purchase dataset for a recommendation model."*

- Problem type: **Association rules** (or a feature table feeding a downstream recommender)
- Expected entities: customer/session, clickstream event, purchase/order
- Expected label: none required — clickstream is event-grain and must be aggregated to a
  session or customer grain before joining onto purchases (see
  [join-key-reconciliation.md](./join-key-reconciliation.md) for the aggregation rule).

### Worked Example — Demand Forecasting (Regression)

Request: *"Find useful data for demand forecasting."*

- Problem type: **Regression**
- Expected entities: product, store/location, historical sales/orders, and any external signal
  the user names (e.g. weather, promotions)
- Expected label: a continuous quantity column such as units sold or revenue, at whatever
  grain (product-day, product-store-week) the request implies.

### Worked Example — Customer Segmentation (Clustering)

Request: *"Create customer segmentation data."*

- Problem type: **Clustering / segmentation**
- Expected entities: customer plus behavioral attributes (spend, tenure, product mix)
- Expected label: none — the dataset must be entity-grain (one row per customer) with numeric
  and categorical features suitable for clustering, never a label column.

### Worked Example — Fraud/Anomaly Detection (Anomaly Detection)

Request: *"Find unusual or anomalous accounts in our transaction data."*

- Problem type: **Anomaly detection**
- Expected entities: account/customer plus aggregated transaction behavior (amount, frequency,
  velocity, channel mix)
- Expected label: usually **none** — anomaly detection is typically unsupervised, so the dataset is
  entity-grain features only, feeding an unsupervised anomaly-detection algorithm downstream. If a rare confirmed-fraud flag exists it
  is kept for *evaluation* only, not as a training label; never fabricate one when it is absent.

### Worked Example — Support-Ticket Topic Routing (Text Classification)

Request: *"Build a dataset to classify support tickets by topic from the ticket text."*

- Problem type: **Text classification**
- Expected entities: support ticket/case, with the free-text body as the feature source and a
  topic/category column as the label
- Expected label: a categorical `category`/`topic` column attached to the ticket text. Unlike every
  other problem type, the free-text column is **kept**, not dropped — it is the primary feature and
  feeds a downstream text classifier after tokenization.

## Phase 2 — Semantic Discovery

Real table and column names rarely match the business vocabulary in a user's request. Instead of
searching for the literal words in the request, expand each expected entity into the synonyms
likely to appear as actual table or column names, and use every synonym as a candidate match in
Phases 3–5.

### Concept Expansion Table

| Concept | Expands to |
|---|---|
| customer | customer, client, subscriber, member, party |
| transactions | transaction, payment, ledger, trx, history |
| account | account, acct, policy, product holding |
| repayment / credit | credit, repayment, default, delinquency, bureau, risk |
| usage / network | usage, network, session, data, minutes, traffic |
| support | support, ticket, case, complaint, contact |
| event / clickstream | event, click, session, journey, activity, log |
| purchase / order | purchase, order, basket, cart, sale |
| location | location, store, site, region, geography, postal |
| external enrichment | bureau, external, feed, third-party, enrichment, partner |

This table is a starting point, not an exhaustive list — extend it with synonyms specific to the
domain named in the request (e.g. "policy" and "claim" for an insurance request).

### Using Expansions to Drive Discovery

Each concept's expansion list becomes a set of substrings to test against the object names
returned by `base_databaseList` (Phase 3) and the scoped `DBC.TablesV` query (Phase 4). A table
matches a concept if its name or any of its column names (from `base_columnDescription`) contains
one of the concept's expansions as a substring, case-insensitively. Do not require an exact word
match — `Customer_Master`, `customer360_account`, and `cust_id` should all match the "customer"
concept.

### Worked Walkthrough — Continuing the Patient Readmission Example

Because the request is healthcare-specific, first **extend** the generic concept vocabulary with
domain synonyms (per the note above): add `patient` to the `customer` concept, `claims`/`payer` to
`external enrichment`, and `lab`/`encounter` to `transactions`. Then:

1. Concept `customer` (extended with `patient`) → matches a table named `Patient` in a clinical
   database.
2. Concept `external enrichment` → expansions include `claims` → matches a foreign table named
   `nos_claims_feed`, which is not an EDW table at all but an external NOS feed. This is the
   signal that routes the plan into [hybrid-source-discovery.md](./hybrid-source-discovery.md) in
   Phase 7, run in parallel with EDW discovery.
3. Concept `transactions` (extended with `lab`) → matches a table named `Labs` (event-grain, keyed
   by an admission/lab identifier, not directly by patient) — flagging it for the
   entity-vs-event-grain aggregation rule described in
   [join-key-reconciliation.md](./join-key-reconciliation.md).

### Output Contract Feeding Phase 3

Phase 2 hands off a **ranked concept list per entity** — for every expected entity from Phase 1, a
list of candidate synonyms to test against database and table names. Database Discovery
(Phase 3) and Table Discovery (Phase 4) consume this list directly; see
[database-and-table-discovery.md](./database-and-table-discovery.md) for how the synonyms feed
into the weighted ranking score.
