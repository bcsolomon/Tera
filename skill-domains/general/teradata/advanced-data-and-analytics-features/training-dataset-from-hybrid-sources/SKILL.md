---
name: training-dataset-from-hybrid-sources
description: 'Assembles a validated, raw training or analytics dataset from one or more Teradata/EDW tables, optionally combined with object-store (NOS) and open-table-format (OTF/Iceberg/Delta) data. Use whenever building, gathering, or finding data for a supervised or unsupervised ML task — classification, regression, clustering/segmentation, anomaly detection, association-rule mining, or text classification — including a build from a single named table; reconciling join keys across storage tiers and materializing and structurally validating the raw table before downstream data preparation.'
metadata:
  author: teradata
  version: "1.1"
---

# Training Dataset from Hybrid Sources

## When to Use

- Building a **raw** training set (classification, regression, clustering/segmentation, anomaly-detection, association-rule-mining, or text-classification) — assembled and structurally validated, not yet profiled, cleaned, or feature-engineered.
- Inferring the ML use case, feature groups, and label from a vague business request.
- Discovering candidate databases/tables and their PK/FK/stats/partitioning metadata without exact names.
- Inferring join paths across tables the user did not name, and reconciling keys across storage tiers.
- Discovering EDW data alongside object-store (NOS) and open-table-format (OTF) sources — enrichment is best-effort; an EDW-only dataset is a valid outcome.
- Materializing the joined table (`CREATE TABLE AS` + `PRIMARY INDEX` + `COLLECT STATISTICS`), running structural validation, and handing off downstream.
- Example trigger phrases: "Build a churn dataset", "Prepare fraud detection data", "Create customer segmentation data",
  "Assemble market-basket association data", "Build a support-ticket text-classification dataset", "Merge weather with sales",
  "Join clickstream with purchases", "Combine EDW with external parquet files".

> **Scope:** ends at the materialized, structurally-validated raw table. Profiling, cleaning, imputation, encoding,
> scaling, reshaping, model training/tuning/scoring, and granting access are **out of scope** — hand off, don't perform,
> even when the user insists ("go ahead and profile it", "just train it now").

## Tools & Entry Routing

**Tools (the only ones this skill calls) — call directly, no wrapper/search step:**

1. `base_databaseList()` / `base_userDatabaseList()` — rank candidate databases (Phase 3).
2. `base_tableList(database_name=…)` — list a database's tables/views (no name filter — always pass the DB).
3. `base_readQuery(sql=…)` — read-only `SELECT` only (discovery on `DBC.*`, overlap probes, Phase 10 checks).
4. `base_tableDDL(database_name=…, table_name=…)` — columns, types, PI, FKs, partitions, provenance.
5. `base_columnDescription(database_name=…, obj_name=…)` — enumerate columns for feature selection (Phase 8).
6. `base_tableAffinity(database_name=…, obj_name=…)` — co-queried tables (join-edge hints, Phase 6).
7. `base_executeSQL(sql=…)` — the **only** route for non-`SELECT`: the CTAS, `COLLECT STATISTICS`, and `HELP DATALAKE`/`HELP DATABASE`/`HELP TABLE` (see Tool Routing).

**Never bail (on a build task):** for a dataset-assembly request, always issue at least one discovery call before
concluding — never answer "tools unavailable", "cannot determine", or stop without server evidence. This does **not**
apply to governance / out-of-scope requests where the correct action is to refuse or defer **without** touching data
(e.g. a destructive-SQL demand, an access-control boundary, or a pure profiling/training ask): there, decline by name
with no tool call — issuing a discovery call just to "look busy" is itself out of policy. If a call fails, diagnose it
(wrong tool for a non-`SELECT`; datalake auth *6938*; access-denied *3523*) and continue; don't abandon the task.

**Entry routing — start from what the user already gave you (don't re-walk earlier phases):**

| The user gave you… | Enter at | First call(s) |
|---|---|---|
| Only a business goal, no names | Phase 1→3 | `base_databaseList` → `base_tableList` per candidate DB |
| A database name | Phase 4 | `base_tableList(database_name=…)` → `base_tableDDL` |
| A specific table | Phase 5 | `base_tableDDL` → `base_columnDescription` |
| A named NOS/OTF source | Phase 7 | `base_tableDDL` (NOS) or `DBC.DatalakeInfoV` + `HELP` (OTF) |
| Two+ tables to combine | Phase 6 | `base_tableDDL` each → `base_tableAffinity` → overlap probe |

Routing sets only the entry point — the Confirm-Before-Building triggers, Phase 4.5 access filtering, and the
Phase 8.5 overlap gate still apply before any table is built, and must be **executed as their own calls** (access via
`DBC.AllRightsV`, overlap via `COUNT`) — never inferred from a later query succeeding or from DDL alone.

## Core Concepts

### Storage Tiers

| Tier | What it is | How this skill discovers it |
|---|---|---|
| EDW | Native Teradata tables/views in user databases | `base_databaseList` → `base_tableList` (pass `database_name`) or a scoped `base_readQuery` on `DBC.TablesV` for `TableName LIKE` keyword filtering → `base_tableDDL` |
| NOS | Object-store data (S3, Azure Blob, GCS) exposed through foreign tables or external locations | `base_tableDDL` on the foreign table's definition; format identified as CSV, JSON, or Parquet |
| OTF | Iceberg/Delta tables registered in an external catalog | `DBC.DatalakeInfoV` (a `SELECT`, via `base_readQuery`) + `HELP DATALAKE`/`HELP DATABASE`/`HELP TABLE` (non-`SELECT`, via `base_executeSQL` — see Tool Routing); format identified as Iceberg or Delta |

Every SQL statement this skill writes (Phases 4.5–10) must use correct, verified Teradata syntax — never assume it; the Teradata-specific spellings that bite these `SELECT`s and the CTAS (no `LIMIT`; `QUALIFY`/`SAMPLE`/`TOP`; reserved-word quoting; `CAST`/`TRIM` conversion rules) are in [teradata-sql-basics.md](./references/teradata-sql-basics.md).

### Tool Routing: `base_readQuery` (SELECT-only) vs. `base_executeSQL`

`base_readQuery` runs **only** `SELECT` — it rejects anything else with `TD_TOOL_EXECUTION_ERROR: Only SELECT queries
are allowed`. Route every non-`SELECT` (Phase 9 CTAS, `COLLECT STATISTICS`, `HELP DATALAKE`/`DATABASE`/`TABLE`) through
`base_executeSQL`. Referenced below as *see Tool Routing*.

### Provenance Is Proven by DDL, Not `TableKind`

A candidate's storage tier is confirmed from its **DDL text** — an external `LOCATION` / `CREATE FOREIGN TABLE` clause
for NOS, or a datalake-catalog entry for OTF — never from `TableKind`. `TableKind` is not a reliable NOS signal: a
genuine S3-backed `CREATE FOREIGN TABLE` can report `TableKind = 'T'` (the ordinary-table code) on some instances, so a
`TableKind = 'O'` filter can silently exclude a real source.

```sql
-- ❌ Filtering on TableKind drops real S3-backed foreign tables — they can report 'T', not 'O'
SELECT DatabaseName, TableName
FROM DBC.TablesV
WHERE TableKind = 'O' AND TableName LIKE '%claims%';

-- ✅ Scan by name only, then confirm the tier from each hit's DDL
SELECT DatabaseName, TableName
FROM DBC.TablesV
WHERE TableName LIKE '%claims%';
-- then base_tableDDL(DatabaseName, TableName): an external LOCATION / CREATE FOREIGN TABLE clause ⇒ NOS
```

Cross-referenced below as *see Provenance, not `TableKind`*.

### Entity Grain vs. Event Grain

An **entity-grain** source has one row per business entity (one row per customer, one row per account) and can be
joined directly onto the anchor table. An **event-grain** source has many rows per entity (transactions, clickstream
events, support tickets) and must be aggregated up to the entity grain — via `GROUP BY` or window functions — before it
is joined. Joining an event-grain source directly onto the anchor without aggregating first causes a fan-out join that
inflates the row count and skews the label balance (see Common Errors below).

```sql
-- ❌ Event-grain table joined raw → fan-out: one Customer row becomes N, inflating the label count
SELECT c.customer_id, c.churn_flag, t.amount
FROM Customer c
JOIN Transactions t ON c.customer_id = t.customer_id;

-- ✅ Aggregate the event grain to one row per customer FIRST, then join onto the anchor
SELECT c.customer_id, c.churn_flag, t.txn_count, t.amount_sum
FROM Customer c
LEFT JOIN (
    SELECT customer_id, COUNT(*) AS txn_count, SUM(amount) AS amount_sum
    FROM Transactions
    GROUP BY customer_id
) t ON c.customer_id = t.customer_id;
```


### Anti-Fabrication (Hard Rule)

Never substitute a similarly-named internal table for a named external source, and never synthesize a join key that
discovery did not surface (no `MOD`/hash/`ROW_NUMBER`/positional pairing), simulate feature values, or force a hybrid
join to make an EDW-only result look multi-tier. Every table and column named in a join or the CTAS must have been
confirmed by an actual `base_tableDDL`/`base_tableList`/`base_columnDescription` call **this session** — never introduce
a bridge/mapping table you did not discover, and never report an overlap %, row count, or match rate that did not come
from an executed probe. When a required source or a working join cannot be found, **surface the
gap** — the exact object and the privilege to request — rather than papering over it. Full detail in Phase 7 and
[hybrid-source-discovery.md](./references/hybrid-source-discovery.md).

**Example:** ❌ inventing a `DEMO_Financial_db.Accounts` bridge (with made-up overlap stats) to link
`Customer`→`Transactions`, or `... ON MOD(a.customer_id, 1000) = b.bucket_id` → ✅ "`Customer` and `Transactions` share
no direct key and no bridge table surfaced in discovery; confirm/request the `Accounts` mapping table" — surface the gap, do not fabricate it.

### No Destructive SQL (Hard Rule)

Issue only `CREATE TABLE AS` (skill output) plus read-only `SELECT`s. Never run `DROP`/`DELETE`/`UPDATE`/`TRUNCATE`/
`REPLACE` or `CREATE` over an *existing* object — even on scratch tables — and never invoke `base_dropTable`. The
guardrail is at the **statement** level: `base_executeSQL` runs any statement, and `base_readQuery` can reach DDL/DML
paths, so avoiding one named tool is not sufficient. When a request needs a drop/rebuild over an existing object,
**stop and ask**, or materialize under a fresh `TDH_`-prefixed name (Phase 9). Holds even when the user insists.

**Example:** asked to "drop the old training table and rebuild it" → ❌ `DROP TABLE …; CREATE TABLE …` → ✅ "That would
overwrite an existing object — confirm the drop, or I'll materialize as a fresh `TDH_`-prefixed table instead."

### Confirm Before Building (ask, don't guess)

Confirm exactly these **four** decisions before materializing; for everything else, **proceed without asking**. The two
lists are exhaustive: not a pause trigger ⇒ a proceed action, even when it superficially resembles one.

**Pause and ask — only these four:**

1. **No label for a supervised request** — the user framed a **supervised/prediction** target (e.g. "predict
   churn/default/response") but no label column exists and no derivation rule was given. Present the gap and any proposed
   derivation, then wait (Phase 8). A generic "build a training/analytics set" with **no stated target** is **not** this
   trigger (see the proceed list).
2. **A *user-named* key or source returns ~0% overlap** — the user explicitly named the join key/source and the Phase 8.5
   probe finds no matches *after* any required cast. Report it and confirm the correction; never silently swap in a
   different key/source. (A mere *type* mismatch on a user-named key is **not** this trigger — see the proceed list.)
3. **No confident anchor** — several databases/tables are plausible and none clearly wins: the top candidates sit within
   a small confidence margin, or the request is open-ended ("find data to predict X") with more than one viable source
   set. Present them ranked with rationale and confirm the source set before building (Phases 3/4/7).
4. **Ambiguous entity grain** — two grains are genuinely plausible for the same request (one row per parent entity vs.
   one row per related child record). "One row each" over a parent/child pair (policies/claims, orders/line-items) is a
   mandatory pause; not finding one side's table is a discovery result to report, not a licence to pick the other.
   Surface both grains and their modeling impact, then confirm (Phase 1/6).

**Proceed without asking — do the work, then report it (never a pause trigger):**

- **Type/case mismatch on any join key** → apply the `CAST`/`TRIM` and continue — including a *user-named* key whose only
  problem is a differing type (reconcile it, don't ask; only ~0% overlap after casting escalates it to trigger 2).
- **An event-grain source** → aggregate it to the entity grain and continue.
- **A post-outcome / label-derived leakage column** → exclude it from the features and continue.
- **A `PRIMARY INDEX` choice, audit-column pruning, or a label the user specified deterministically** (an explicit rule
  mapping existing columns to the target) → apply and continue.
- **A generic "build a training/analytics set" with no stated prediction target** → materialize the raw, label-agnostic
  table (pruned projection, all rows) and leave labeling/target derivation to downstream; the absence of a label column
  is not by itself a reason to pause.
- **An inaccessible or missing *enrichment* source** → drop it, state which one and why, and continue assembling from the
  accessible sources. Stop only when *no* accessible candidate exists for a **required** feature group (then surface the
  gap per Phase 4.5 — never self-grant).
- **A *skill-chosen* candidate that fails the overlap probe** → re-rank and re-run discovery in the **same turn**; that is
  a discovery step, not a user question.

When torn between a pause trigger and a proceed action, the proceed list wins unless it squarely matches a numbered trigger.
An imperative build verb ("Build"/"Rebuild"/"assemble") **does not waive** triggers 3–4: an open-ended source set or a
genuinely ambiguous grain still pauses **before** the CTAS. Recording an unconfirmed source or grain choice in a
post-hoc `Assumptions`/`Interpretation` note *after* materializing is **not** a substitute for asking — it is a trigger violation.
A pre-existing or prior-run table is **never** the deliverable: build and structurally validate in the current session.
Run the access/overlap gates immediately **before** the CTAS — if a trigger is still open at that point, stop, do not build.

### Efficiency: Minimize Tool-Call Turns

- **Batch independent lookups** in one turn (parallel `base_tableDDL`/`base_columnDescription`); never re-fetch metadata already retrieved.
- **Probe candidates together, not one-at-a-time:** fold the Phase 4.5 access check (`DBC.AllRightsV`, `DatabaseName IN (...)`) and the Phase 8.5 overlap check (one `UNION ALL`) across all candidates into a single turn — an inaccessible candidate needs no overlap probe.

### Scope Boundary

**In scope:** the seven `base_*` tools above, plus the output `CREATE TABLE AS` + `COLLECT STATISTICS` via
`base_executeSQL`. **Out of scope:** everything in the *When to Use* scope note, plus reshaping (pivot/unpivot/sessionize)
and train/test splitting (`TrainTestSplit` or a `SAMPLE`-based split into train/test tables) and all
model prediction/scoring — an explicit "just profile/train it now" is **not** consent. The deferred data-preparation
tool inventory lives in [materialization-and-validation.md](./references/materialization-and-validation.md).

**Enforcement is on the operation, not the tool (hard rule).** Only the seven `base_*` tools above are permitted, and the
out-of-scope operations must never run by any route — including hand-written as `SELECT`/`CASE`/`UPDATE` SQL through
`base_executeSQL`. After the output CTAS, `base_executeSQL` is limited to that CTAS, its `COLLECT STATISTICS`, and `HELP`.
Any analytic/data-prep function (`tdml_*` and any `*Fit`/`*Transform`/`*Predict`/evaluator)
is out of scope — its availability in the environment is not permission to call it. When a build request is **bundled**
with downstream steps ("build it, *then* profile / clean / encode / train it"), split the request: perform only the
in-scope build and structural validation, then decline each bundled downstream step **by name** and hand it to
downstream data preparation — even when asked to do it all in the same turn.

## Procedure: Interpret the Goal (Phases 1–2)

**Phase 1 — Intent Understanding.** From the user's request, infer: the prediction target, the ML problem type, the
candidate feature groups, and the expected label. Examples: "Build a patient readmission dataset" → Classification;
entities patient, admission, lab, diagnosis, claims. "Find data for demand forecasting" → Regression (a continuous
demand quantity, not a class); feature groups sales/order history, product, inventory, promotions, calendar/seasonality.

**For a vague / no-name goal ("find data for X"), lead with the framing.** Before naming any table, your first output
must state the inferred ML problem type and expand the ask into concrete candidate feature groups, and frame the
deliverable as a *raw materialized training dataset* — not a forecast or a trained model. Then run discovery and, since
an open-ended goal is Confirm-Before-Building trigger 3, present the ranked candidate sources and confirm the source set
(and the label if ambiguous) before building. Skipping straight to specific table names is a framing failure.

**Phase 2 — Semantic Discovery.** Drive natural-language table/column discovery across Phases 2–5. Search by concept, not by exact name: expand business terms into the synonyms likely to appear as
real table/column names before querying metadata — "customer" expands to customer, client, subscriber, member, party;
"transactions" expands to transaction, payment, ledger, trx, history.

Full concept-expansion guidance and problem-type inference detail: [intent-and-semantic-discovery.md](./references/intent-and-semantic-discovery.md).

## Procedure: Discover Sources (Phases 3–5, 4.5, 7)

**Phase 3 — Database Discovery.** Prefer `base_userDatabaseList` (accessible-scoped; `base_databaseList` for a broader
scan — Phase 4.5 still confirms `SELECT`). Rank candidates against **every** required entity/feature group from Phase 1
(customer *and* account *and* the label), not just the term said aloud — a database whose name contains the business
label (`*churn*`, `*fraud*`, `*default*`) is a candidate to rank, never an automatic anchor. Picking it on name match
alone is a discovery failure; follow up on any stronger, differently-named candidate from a Phase 4/7 sweep before anchoring.

**Phase 4 — Table Discovery.** Use `base_tableList` with an explicit `database_name` to list a database's tables, or a scoped `base_readQuery` against `DBC.TablesV` (filtered by `DatabaseName` and a `TableName LIKE` keyword pattern) when you need concept-based filtering or a cross-database scan, and rank candidate tables within the
selected databases.

**Phase 4.5 — Access Filtering (read-only).** Catalog visibility is *not* read access — DDL/columns/row-estimate are
inspectable with no `SELECT` right, so anchoring on such a table fails later with *Error 3523 (access denied)*. Before
candidates reach Phase 5/6, **drop every one the session cannot read** (access-right `'R'` = `SELECT`; include
role-inherited grants via `DBC.AllRoleRightsV` + `DBC.RoleMembers`) and re-rank the readable remainder — run this check
as its own call, since a later query succeeding is not evidence the gate was applied:

```sql
-- Does the current session hold SELECT on a candidate database before anchoring on it?
SELECT DatabaseName, TableName, AccessRight
FROM DBC.AllRightsV
WHERE UserName = USER AND AccessRight = 'R' AND DatabaseName = '<candidate_db>';
```

The check reflects the **MCP session** identity (often a shared service account) — state that assumption when it may
differ from the human user. If the best candidate is inaccessible, say which and why, then continue with the next-best
(or a Phase 7 hybrid). **Granting access is out of scope** — read `DBC.AllRightsV`/`DBC.UserRightsV` only, never
`GRANT`/`CREATE AUTHORIZATION`/`CREATE ROLE`. If none is accessible, report that access must be provisioned and stop.

**Phase 5 — Metadata Inspection.** Use `base_tableDDL` on each readable candidate table to extract columns, primary
index, foreign keys, statistics, partitions, and row estimates before selecting an anchor table.

**Phase 7 — Hybrid Source Discovery.** Alongside EDW discovery, find NOS/OTF sources and read their tier/format
(CSV/JSON/Parquet, or Iceberg/Delta) from the DDL. **Enrichment is best-effort:** if no relevant or accessible external
source exists, an EDW-only dataset is a fully valid outcome — just note that no enrichment was applied. This skill
decides *which* tier (NOS or OTF) applies and writes the tier-appropriate SQL accordingly.

**When the request names an external source, discovery is required, not best-effort** — and a `DBC.TablesV` scan alone
is insufficient (NOS foreign tables surface there; OTF catalog tables do not). Exhaust this **ordered** ladder before
concluding a named source is absent; never simulate or substitute it:

1. **Native/NOS scan** — `TableName LIKE` on concept synonyms, never filtered by `TableKind`; confirm each hit with
   `base_tableDDL` (see Provenance, not `TableKind`):
   ```sql
   -- base_readQuery — one pattern per synonym, not just the literal word
   SELECT DatabaseName, TableName FROM DBC.TablesV WHERE TableName LIKE '%<concept>%';
   ```
2. **Every registered datalake** (OTF tables are not in `DBC.TablesV`) — browse **all**, never just the first
   alphabetical one; a same-topic table in one datalake is not grounds to stop:
   ```sql
   SELECT DatalakeName, OTFTableFormat FROM DBC.DatalakeInfoV;  -- base_readQuery
   HELP DATALAKE <name>;                    -- base_executeSQL (see Tool Routing)
   HELP DATABASE <name>.<namespace>;        -- base_executeSQL
   HELP TABLE <name>.<namespace>.<table>;   -- base_executeSQL
   ```
   *Error 6938 (`Authorization '<auth>' does not exist`)* on one datalake is a per-datalake break, not proof the source
   is absent — skip it, note it unreachable, keep enumerating; never `CREATE AUTHORIZATION`/`REPLACE DATALAKE` to self-repair.
3. **Raw object-store path** with no foreign-table wrapper — inspect before declaring it missing:
   ```sql
   -- base_readQuery — NOS read syntax
   READ_NOS ( ... LOCATION('/s3/<bucket>/<path>/') RETURNTYPE('NOSREAD_KEYS') )  -- or 'NOSREAD_SCHEMA'
   ```

**Never fabricate (see Anti-Fabrication).** A name-suggestive native table (`*_from_s3`, `*_parquet`, `*_external`) is
NOS/OTF only once `base_tableDDL` shows an external `LOCATION`/`CREATE FOREIGN TABLE` or a datalake entry. If a required
source can't be found or read (*Error 3523*), surface the exact object and `GRANT` — never substitute, synthesize a key,
simulate values, or self-grant. Details:
[database-and-table-discovery.md](./references/database-and-table-discovery.md),
[hybrid-source-discovery.md](./references/hybrid-source-discovery.md).

## Procedure: Reconcile Join Keys (Phase 6)

**Phase 6 — Relationship Discovery.** Infer joins from two corroborating signals: (1) declared FKs and shared key-like
columns from the Phase 5 DDL (`cust_id`, `account_id`, `subscriber_id`, `household_id`, `device_id`), and (2)
`base_tableAffinity` (tables most co-queried with a candidate — surfaces partners even with no declared FK). Use
affinity to corroborate, never as the sole basis without confirming the shared column exists in both DDLs. Build a join
graph from the anchor to every source; a "no cast needed" claim must be DDL-verified — when declared types differ
(`INTEGER` vs. `VARCHAR`, padded `CHAR` vs. `VARCHAR`), `CAST`/`TRIM` is mandatory:

```sql
-- Cast/trim BOTH sides to a common type in the JOIN's ON clause (emitted in Phase 9):
--   INTEGER vs VARCHAR:     ON CAST(a.cust_id AS BIGINT) = CAST(e.cust_id AS BIGINT)
--   padded CHAR vs VARCHAR: ON TRIM(a.cust_id)           = TRIM(e.cust_id)
```

**Preserve the entity grain — default `LEFT JOIN` from the anchor** (anchor on the left) so anchor entities are never
dropped for lacking an enrichment match; unmatched rows yield `NULL` features (the correct downstream signal). Use
`INNER JOIN` only when a source is the **sole** label provider *and* the user has been told the row count drops to the
matched subset — never merely to "ensure the label is available." State the join type and its row-count implication in the plan.

Full join-graph construction and key-type casting guidance: [join-key-reconciliation.md](./references/join-key-reconciliation.md).

## Procedure: Select Feature Columns (structural only) (Phase 8)

> **Not this skill:** profiling / cleaning / imputation / encoding / scaling / reshaping the selected columns →
> downstream data preparation — finish assembly + basic structural validation and hand off.

**Phase 8 — Feature Column Selection.** Never `SELECT *`. Use `base_columnDescription` to enumerate candidate columns
and types, then hand-pick an explicit list — **structural selection only** (all profiling, cleaning, and encoding is
deferred to downstream data preparation, see Scope Boundary). Derive a label **only** from a user-given deterministic
rule; if none exists and no rule was given, **stop before Phase 9 and ask** — never invent a threshold or proxy.

```sql
-- Emitted as the Phase 9 SELECT list — explicit columns only, never SELECT *
SELECT
    customer_id,                        -- keep: join / grain key
    tenure_months, monthly_charges,     -- keep: numeric features
    contract_type, region,              -- keep: categoricals
    CASE WHEN status = 'CHURNED' THEN 1 ELSE 0 END AS derived_churn_label
        -- label ONLY if user gave the rule; name derived_*/*_proxy; drop rows where it's undefined (NULL)
FROM ...
-- DROP: load_ts/etl_batch_id (audit), duplicate IDs, non-grain timestamps, and post-outcome leakage
--       (outcome date/amount, resolution_flag) that exists only once the outcome is known
```

Full column-selection criteria and drop rules: [feature-and-label-selection.md](./references/feature-and-label-selection.md).

## Procedure: Integrate and Materialize (Phases 8.5–9)

**Phase 8.5 — Join Overlap Validation.** A passed type check is not enough — two type-compatible keys can still cover
non-overlapping ID ranges. Before the Phase 9 CTAS, probe every anchor→source edge with an executed `COUNT` (read-only —
no table built here); schema/DDL inspection does not substitute for the probe, even when the DDL already reveals a
missing or mismatched key:

```sql
-- base_readQuery — simple per-edge overlap count
SELECT COUNT(*) AS matched
FROM <anchor> a
WHERE EXISTS (SELECT 1 FROM <source> e WHERE CAST(a.<key> AS BIGINT) = e.<key>);

-- Preferred: fold overlap + min/max key + label counts into ONE scan. Putting EXISTS inside CASE WHEN
-- raises Error 3771 (illegal expression in WHEN) — instead LEFT JOIN a DISTINCT-key derived table
-- (DISTINCT stops the join from fanning out the base count):
SELECT SUM(CASE WHEN e.<key> IS NOT NULL THEN 1 ELSE 0 END) AS matched
FROM <anchor> a
LEFT JOIN (SELECT DISTINCT <key> FROM <source>) e ON CAST(a.<key> AS BIGINT) = e.<key>;

-- Event-grain fan-out guard (separate probe) — catch inflation before it hits the table:
SELECT MAX(cnt) AS max_rows_per_key FROM (SELECT <key>, COUNT(*) cnt FROM <source> GROUP BY <key>) x;
```

**If overlap is ~0%, do not build the table** — it is a discovery signal, not a licence to improvise. Likely causes:
the wrong anchor (a different EDW table's keys usually *do* overlap), a still-missing key transform, or a decoy
look-alike — meaning you must have browsed **every** datalake/namespace from `DBC.DatalakeInfoV` (Phase 7 rung 2), not
just the first. Never fabricate a synthetic key, simulate, or drop a required source (see Phase 7). For a
**skill-chosen** candidate, re-rank and re-run discovery against the remaining Phase 3/4/7 candidates **in the same
turn — do not ask the user**; escalate only after that ranked list is fully exhausted (stopping at the first
zero-overlap to ask is premature). Still ask first when the failing key/source was **named by the user** (report the
~0% and confirm, don't substitute) or when a Confirm-Before-Building checkpoint is open (ambiguous grain / no confident
anchor).

**Phase 9 — Dataset Materialization.** Clear the gate, then execute the CTAS with `base_executeSQL` (not
`base_readQuery`):

```sql
-- GATE — all four must be cleared or STOP and ask (materializing with an open checkpoint is prohibited):
--   (a) label defined / derivation confirmed   (b) any USER-NAMED key/source that failed overlap resolved
--   (c) anchor confident (no tie)              (d) entity grain unambiguous
CREATE TABLE TDH_TRAINSET_<runtag>__<slug> AS (
    SELECT ...                              -- Phase 8 explicit column list + derived label
    FROM <anchor> a
    LEFT JOIN <enrichment> e ON ...         -- LEFT JOIN per Phase 6 (INNER only for a sole-label source)
) WITH DATA
PRIMARY INDEX (<grain_key>);                -- explicit PI
COLLECT STATISTICS COLUMN (<grain_key>) ON TDH_TRAINSET_<runtag>__<slug>;
COLLECT STATISTICS COLUMN (<label>)     ON TDH_TRAINSET_<runtag>__<slug>;   -- supervised only; skip for unsupervised
```

Rebalancing and splitting (`tdml_TrainTestSplit`) are **out of scope** — they run *after* downstream data preparation,
on the cleaned table, not this raw assembly (which ends at the CTAS + a basic `COLLECT STATISTICS` on the grain key,
plus the label when the set is supervised).

**The deliverable is a materialized, validated table — not an unexecuted script.** Actually run the CTAS. If it is
blocked by a permission / not-writable error, retry in a schema the session can write to (verify via the default
database); if none exists, surface the exact object and `GRANT` needed — never self-grant or downgrade to a script.

**Name objects predictably.** Unless the user supplies a name, use the reserved `TDH_` prefix — deliverable
`TDH_TRAINSET_<runtag>__<slug>`, staging `TDH_STG_<runtag>__<slug>` (`<runtag>` from the caller or a compact UTC
`YYYYMMDDTHHMMSS` fallback; `<slug>` a short `[a-z0-9_]` label). Report the final `database.table` in the Phase 10 handoff.

CTAS skeleton, indexing/statistics, and the fully parameterized ready-to-run build template: [materialization-and-validation.md](./references/materialization-and-validation.md) (see *Ready-to-Run Build Template*).

## Procedure: Validate and Hand Off (Phase 10)

> **Not this skill:** statistical profiling / distribution checks / imputation / outlier handling / encoding / scaling /
> reshaping the validated dataset → downstream data preparation.

**Phase 10 — Basic Structural Validation.** Run **only** structural checks via `base_readQuery` and `base_tableDDL` —
never statistical profiling here:

- **Row count vs. source cardinality** (`COUNT(*)` compare) — confirms no fan-out: the count should equal the entity cardinality, not the event cardinality.
- **Duplicate-key detection on the grain** (`GROUP BY pi HAVING COUNT(*) > 1`).
- **Null-rate on the join keys only** (`COUNT` of NULL keys).
- **Schema/type match** (`base_tableDDL` vs. the CTAS definition).

Ready-to-run checks: [materialization-and-validation.md](./references/materialization-and-validation.md) (see *Ready-to-Run Validation Template*).

**Handoff — evidence every step, then defer.** Doing the work is not enough: a reviewer (or downstream agent) only sees
what is stated, so the closing summary must name, in plain text (state it even when the step was trivial or a no-op,
e.g. "keys already matched, no cast needed"):

1. **Join-key reconciliation** — for every anchor→source edge: the key columns, their data types on each side, the cast applied (or "no cast needed"), and the measured overlap from the Phase 8.5 probe.
2. **Event-grain aggregation** — for every event-grain source: the grain it was aggregated to and the aggregate features produced (e.g. "tickets aggregated to customer grain: ticket_count, unresolved_count").
3. **PRIMARY INDEX** — the exact `PRIMARY INDEX` column(s) chosen for the materialized table.
4. **COLLECT STATISTICS** — the column(s) statistics were collected on.
5. **Handoff** — recommend downstream data preparation (profiling, cleaning, and feature engineering) as the immediate next step; note that model training is a separate downstream stage that runs after data-prep. Do not invoke any profiling or model tool.

**Answer hygiene (final message).** Send one clean, professional deliverable — never a running log of your thought
process. Three output-discipline rules:

- **No tool traces or interstitial narration.** Strip planning, self-talk, and SQL-debugging asides ("Good, the DB is
  writable", "Let's list its tables", "Now let me load the tool schemas", "SEGMENT is a reserved word — let me quote
  it"). Report the fact-based outcome, not a play-by-play of retries; if an earlier attempt was wrong, state only the
  final result.
- **Clean prose mechanics.** Open directly with the deliverable heading; write complete sentences in a neutral, precise
  tone with no slang.
- **Don't omit silently.** If an item was genuinely not applicable, say so and why.

Emit the deliverable as one fixed block (write `n/a — <reason>` when a field truly does not apply):

```text
Table: <db.table>   ·   Rows: <n> · label <balance, e.g. 18% positive, or "unlabeled">
Join edges:    <anchor→source · key · type each side · cast or "none" · Phase 8.5 overlap %>   (one per edge)
Grain agg:     <event-grain source → grain → aggregate features>   (or "none")
PRIMARY INDEX: <column(s)>   ·   COLLECT STATS: <column(s)>
Gaps surfaced: <excluded/inaccessible source + GRANT to request, or "none">   ·   Next: downstream data preparation
```

Full validation checklist and the data-preparation tool-boundary table: [materialization-and-validation.md](./references/materialization-and-validation.md).

## Quick Reference — MCP Tool per Phase

| Phase | Stage | Primary tool(s) |
|---|---|---|
| 3 | Database discovery | `base_userDatabaseList` (accessible-scoped) / `base_databaseList` |
| 4 | Table discovery | `base_tableList` (scoped by `database_name`) or `base_readQuery` on `DBC.TablesV` |
| 4.5 | Access filtering | `base_readQuery` on `DBC.AllRightsV` |
| 5 | Metadata inspection | `base_tableDDL` |
| 6 | Relationship discovery | `base_tableDDL` + `base_tableAffinity` |
| 7 | Hybrid discovery | `DBC.TablesV`, `DBC.DatalakeInfoV`, `READ_NOS` |
| 8 | Feature selection | `base_columnDescription` |
| 8.5 | Overlap validation | `base_readQuery` (COUNT probe) |
| 9 | Materialization | `base_executeSQL` (CTAS + `COLLECT STATISTICS`; `base_readQuery` is SELECT-only) |
| 10 | Structural validation | `base_readQuery`, `base_tableDDL`, `base_executeSQL` (for `HELP TABLE`) |

## Common Errors / Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Zero/near-zero rows match, or an unintended product join | Join-key type mismatch (`INTEGER` vs. `VARCHAR`, padded `CHAR`) | Explicit `CAST`/`TRIM` before joining — [join-key-reconciliation.md](./references/join-key-reconciliation.md) |
| Type-compatible keys but ~0 overlap, or no source/key found at all | Wrong anchor/decoy (a look-alike datalake or name-matched DB), or the temptation to fabricate | Run the Phase 8.5 probe; browse **every** datalake in `DBC.DatalakeInfoV` and re-rank/re-discover **in the same turn**; never manufacture a key or simulate values — surface the missing object (see Anti-Fabrication) |
| A NOS/OTF source seems missing, a `*_parquet`/`*_from_s3` look-alike used as external, or a real S3 foreign table hidden by a `TableKind` filter | Discovery stopped early, or the scan filtered on `TableKind` (a real foreign table can report `'T'`) | Exhaust the Phase 7 ladder; scan `TableName LIKE` (never `TableKind`) and confirm provenance with `base_tableDDL` (see Provenance, not `TableKind`) |
| `base_readQuery` rejects `HELP`/CTAS/`COLLECT STATISTICS`; *Error 3771* on a one-scan overlap probe; or a call fails (datalake auth *6938*, access-denied *3523*) | Wrong tool for a non-`SELECT`; an `EXISTS`/subquery inside `SUM(CASE WHEN …)`; or a failed call mistaken for an absent source | Route non-`SELECT` via `base_executeSQL` (see Tool Routing); use a standalone `COUNT(*) … WHERE EXISTS` (or `LEFT JOIN` a `SELECT DISTINCT <key>`); skip the one broken datalake and keep enumerating; drop an unreadable candidate or name the exact `GRANT` — never self-remediate |

## References


> **Access:** `skill_resource_read(action="read", skill="training-dataset-from-hybrid-sources", path="references/FILENAME")` — do NOT call `list`.

- [intent-and-semantic-discovery.md](./references/intent-and-semantic-discovery.md) (Phases 1–2) — Inferring the ML problem type and expanding business terms into search concepts.
- [database-and-table-discovery.md](./references/database-and-table-discovery.md) (Phases 3–5) — Ranking candidate databases/tables, the weighted ranking scoring, and the read-only access-check SQL.
- [join-key-reconciliation.md](./references/join-key-reconciliation.md) (Phase 6) — Building the join graph (declared FKs + `base_tableAffinity`) and casting mismatched key types.
- [hybrid-source-discovery.md](./references/hybrid-source-discovery.md) (Phase 7) — Full NOS + OTF reference: foreign-table DDL, `READ_NOS`, `DBC.DatalakeInfoV`/`HELP` discovery, `TD_ICEBERG_READ`/`TD_DELTA_READ`, type mapping, and staging into the CTAS (read-only — no `WRITE_NOS`, catalog/auth creation, or DML).
- [feature-and-label-selection.md](./references/feature-and-label-selection.md) (Phase 8) — Choosing raw feature/label columns and dropping audit/duplicate/leakage columns; the boundary to downstream data preparation.
- [teradata-sql-basics.md](./references/teradata-sql-basics.md) — Dialect gotchas for the discovery/overlap/CTAS SQL: `QUALIFY`/`SAMPLE`/`TOP` (not `LIMIT`), reserved-word quoting, `NOT IN`/NULL traps, `CAST`/`TRIM` rules, errors `3771`/`3706`.
- [materialization-and-validation.md](./references/materialization-and-validation.md) (Phases 9–10) — CTAS generation (`SET`/`MULTISET`, `WITH DATA`, creation errors), indexing/statistics, structural checks, the data-preparation tool-boundary table, and the two ready-to-run *Build* and *Validation* templates.
