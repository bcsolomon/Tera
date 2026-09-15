# Feature and Label Selection — Complete Reference

> Covers Phase 8 of the `training-dataset-from-hybrid-sources` pipeline: enumerating candidate
> columns and deciding — **structurally** — which to keep or drop and which column is the label,
> before the final table is materialized in Phase 9. Statistical profiling, cleaning, imputation,
> outlier handling, encoding, and scaling are explicitly **out of scope** here and are deferred to
> the downstream data-preparation stage (see the closing boundary table).

## Enumerating Candidates

Call `base_columnDescription(db_name, table_name)` against every table selected in the join plan
from [join-key-reconciliation.md](./join-key-reconciliation.md). This returns every column with
its type and nullability and is the starting inventory for triage — never `SELECT *` blindly into
the final training table.

## Keep-List Heuristics by Problem Type

Which raw feature families to keep is driven by the problem type inferred in
[intent-and-semantic-discovery.md](./intent-and-semantic-discovery.md). This is a structural
starting point — the decision is about *presence and role*, not measured predictive power (which
downstream data preparation assesses later):

| Problem type | Keep (raw feature families) | Label column | Free-text handling |
|---|---|---|---|
| Classification | Entity attributes + aggregated event behavior + external enrichment | One binary/multi-class flag | Drop unless request is text |
| Regression | Same as classification, plus time/seasonality keys if the target is time-indexed | One continuous numeric column | Drop |
| Clustering / segmentation | Numeric + low-cardinality categorical entity attributes | None (unsupervised) | Drop |
| Anomaly detection | Aggregated behavior features (amount, frequency, velocity) | None (or eval-only rare flag) | Drop |
| Association rules | Basket/transaction id + item id at event grain (no roll-up) | None | Drop |
| Text classification | The free-text body column | One categorical topic/label | **Keep** — it is the feature |

Two structural rules cut across every row: keep exactly **one** copy of each join key (the anchor's
PI), dropping redundant same-key columns pulled in from joined tables; and for every event-grain
source that has been aggregated, keep the aggregates and drop the raw per-event columns they were
built from.

## Column Triage Rules

**Keep** columns that plausibly carry predictive signal for the inferred problem type:
demographic/business attributes (income, age, tenure), product/account attributes, and any
external enrichment feature.

**Drop** columns that add no modeling value:

- Audit/lineage columns (`created_by`, `updated_at`, `load_ts`, `etl_batch_id`).
- Duplicate identifier columns already consumed as join keys in Phase 6 (keep the anchor's key,
  drop redundant copies from joined tables unless needed for traceability).
- Free-text or narrative columns not in scope for the current problem type (e.g. a free-text
  notes field, unless the request is explicitly a text-classification problem).
- Timestamps that only served to build an aggregation and add no signal once aggregated (e.g. a
  raw `lab_time` once lab counts/sums have been computed).

### Worked Example — Patient Readmission

- `Patient`: keep `age`, `sex`, `years_in_care`, `nbr_dependents`, `marital_status`,
  `postal_code`, `region_code`; keep `patient_id` as the join/PI key.
- `Admissions`: aggregate to `patient_id` grain (count of admissions, sum of `prior_los`/
  `los_days`); drop raw `admit_date` per row once rolled up (keep an aggregated
  "average length of stay" feature instead, if needed).
- `Labs` / `Lab_History`: aggregate to `patient_id` grain (lab count, sum/avg
  `lab_value`); drop raw `panel`, `lab_code`, `lab_time` unless the request specifically calls
  out panel behavior as a feature.
- `nos_claims_feed`: keep `ext_risk_score`, `num_claims_6m`, `num_er_visits_24m`,
  `copay_ratio`; keep `readmit_flag` as the **label**.
- `patient_portal_events`: aggregate to `patient_id` grain (session count, sum `portal_minutes`).
- `Billing_Notes`: out of scope for this request (dropped in
  [database-and-table-discovery.md](./database-and-table-discovery.md)).

## Structural Drop-List Patterns

Decide keep/drop from column **names, types, and role in the join graph** — not from statistical
profiling. The following name/type patterns are safe structural drops at this stage:

| Pattern | Examples | Why drop (structurally) |
|---|---|---|
| Audit / lineage columns | `created_by`, `updated_at`, `load_ts`, `etl_batch_id`, `dw_*` | Housekeeping, no business meaning |
| Redundant join-key copies | a joined table's `patient_id` when the anchor's `patient_id` is already the PI | Duplicate identifier already consumed in Phase 6 |
| Raw event timestamps consumed by aggregation | `lab_time` once `lab_count` / `lab_value_sum` exist | The signal now lives in the aggregate, not the raw row |
| Free-text / narrative columns (non-text-classification requests) | `billing_note`, `notes` | Not a structured feature unless the request is text classification |
| Constant / system-populated flags with a single legal value | `record_status = 'A'` on every row by design | No variance by construction |

**Keep** everything else that plausibly carries signal — demographic/business attributes,
product/account attributes, aggregated event features, and external enrichment features — and let
downstream data preparation decide, from real statistics, which survivors are actually low-value.
Do **not** run `tdml_GetFutileColumns`, `tdml_ColumnSummary`, `tdml_CategoricalSummary`, or
`tdml_UnivariateStatistics` here to make that call, and do **not** impute, filter outliers, encode,
or scale the survivors — those are profiling and transformation steps that belong to the next stage.

Column **aggregation** — rolling an event-grain source up to the anchor grain — is part of assembly
and stays in scope. Column **transformation** — imputing, scaling, encoding, or binning those
aggregates — does not: it is the first job of downstream data preparation.

## Selecting the Label Column

The label frequently lives on the **narrowest, most specific enrichment source** rather than the
EDW anchor table itself — e.g. `readmit_flag` on `nos_claims_feed`, or `Churn` directly on
`StreamCo_db.Subscriber_Churn`. Identify it **structurally**: confirm the column exists, is
non-null on the anchor population, and has the shape the inferred problem type needs (a
binary/multi-class flag for classification, a continuous numeric column for regression, none for
clustering/anomaly/association).

A single read-only `SELECT ... GROUP BY <label>` is an acceptable structural sanity check that the
label is present and has more than one distinct value:

```sql
SELECT readmit_flag, COUNT(*) AS n
FROM <nos_db>.nos_claims_feed
GROUP BY readmit_flag;
```

Deeper class-balance *profiling*, and any decision to rebalance (`tdml_SMOTE`), re-weight, or drop
a degenerate label, is deferred — surface an obviously skewed count to the user and to
downstream data preparation rather than silently correcting it here. Clustering, anomaly-detection,
and pure association requests have **no** label column: for those, confirm the assembled table is
entity-grain with the required feature columns and stop.

### When No Label Column Exists Anywhere

A supervised request (classification/regression) sometimes names a business concept — "churn,"
"fraud," "default" — that has no literal column anywhere in the discovered EDW/NOS/OTF sources,
even after Phases 3/4/7 are exhausted against every ranked candidate. This is a discovery outcome,
not licence to invent one: **do not derive a proxy label and materialize it into the Phase 9 CTAS
on your own initiative.** A label is a business-target decision — unlike picking a raw feature
column, it directly defines what the eventual model predicts, and a wrong guess here silently
corrupts every downstream training run.

When this happens:

1. **Report the gap explicitly** — name every candidate table/column checked and confirm none carries
   the requested concept (e.g., "checked `Patient`, `Admissions`, `Patient_Analysis`,
   `Patient_Journey` — none has a readmission flag; `nos_claims_feed.readmit_flag` is a related but
   distinct concept — a paid-claim indicator, not a 30-day readmission").
2. **If a plausible derivation exists** from columns that *are* present (e.g., "a second admission
   within 30 days of discharge" as a readmission proxy derived from `Admissions.admit_date`),
   **propose the exact logic and ask for confirmation before adding it** — do not add it to the CTAS
   speculatively and ask afterward.
3. **Only after confirmation**, add the derived column to the Phase 9 CTAS under a name that
   unmistakably marks it as a derived proxy (e.g. `derived_readmit_flag_proxy`), never under a name
   indistinguishable from a real, source-provided label (plain `readmit_flag` or `readmitted`).
4. If the user declines or no derivation is proposed, materialize the dataset **without** a label
   column and state that the deliverable is label-less pending a confirmed target definition — this
   is a valid, honest outcome, the same way an EDW-only dataset is valid when no external
   enrichment exists.

This rule sits alongside the Anti-Fabrication hard rule in the main `SKILL.md`: a fabricated feature
value or synthetic join key corrupts the *inputs*; an unconfirmed proxy label corrupts the *target*
— both are prohibited without the same transparency-and-confirmation step.

## Worked End-to-End Example — Final Column Decision (Patient Readmission)

Final SELECT list for the Phase 9 CTAS: `patient_id` (PI/join key), `age`, `sex`,
`years_in_care`, `nbr_dependents`, `marital_status`, `region_code`, aggregated admission
count/length-of-stay, aggregated lab count/avg, `ext_risk_score`, `num_claims_6m`,
`num_er_visits_24m`, `copay_ratio`, aggregated portal-event count/minutes, and `readmit_flag` as
the label — feeding directly into
[materialization-and-validation.md](./materialization-and-validation.md).

## In Scope vs. Out of Scope for Phase 8

| In scope here (structural selection) | Deferred to downstream data preparation |
|---|---|
| Enumerate columns via `base_columnDescription` | Statistical column profiling (`tdml_ColumnSummary`, `tdml_UnivariateStatistics`) |
| Drop audit/lineage, redundant-key, consumed-timestamp, out-of-scope free-text columns by name/type | Drop *low-value* columns by measured statistics (`tdml_GetFutileColumns`, `tdml_CategoricalSummary`) |
| Aggregate event-grain sources up to the anchor grain | Impute nulls (`tdml_SimpleImputeFit`/`Transform`), filter outliers (`tdml_OutlierFilterFit`/`Transform`) |
| Identify the label column and confirm it is present with > 1 value | Encode/scale features (`tdml_OneHotEncodingFit`, `tdml_ScaleFit`, `tdml_TargetEncodingFit`, …) and class-balance profiling |

Cross this line only to *assemble* the raw table; every transformation of the assembled values is
the next stage's responsibility. The full Data Prep and ML Tool Boundary tables live in
[materialization-and-validation.md](./materialization-and-validation.md).
