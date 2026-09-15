# Database and Table Discovery — Complete Reference

> Covers Phases 3–5 of the `training-dataset-from-hybrid-sources` pipeline: ranking candidate
> databases, ranking candidate tables within them, inspecting their DDL, and the weighted
> discovery-ranking algorithm that decides which candidates to carry forward.

## Phase 3 — Database Discovery

**MCP tool:** `base_databaseList` (no arguments — lists every database/user on the system).

Score every returned database name against the concept-expansion lists produced in
[intent-and-semantic-discovery.md](./intent-and-semantic-discovery.md). A database whose name
contains one of the expansions for any expected entity (e.g. a database named `CareCloud_db`
matching the "admission"/"diagnosis" concepts, or `StreamCo_db` matching "subscription/usage") ranks
above unrelated databases. Carry forward the top-ranked databases into Phase 4 — do not stop at
the first match, since the anchor entity and its enrichment sources are often split across more
than one database (an EDW database plus a database that owns the NOS/OTF foreign objects).

### Worked Example

Request: *"Build a patient readmission training dataset from our patient, admission, and lab
history plus the external insurance-claims feed."*

| Candidate database | Concept match | Rank |
|---|---|---|
| `CareCloud_db` | name/description matches patient, admission, lab concepts | 1 |
| `PatientPortal_db` | matches "patient" only, no admission/lab/claims signal | 3 |
| `Logistics_db` | no match to any expected entity | discard |

## Phase 4 — Table Discovery

**Prefer `DBC.TablesV` over `base_tableList` for discovery.** `base_tableList(database_name)` has
**no name filter**, so on a shared/demo database it returns every object — potentially several hundred —
and that raw listing then re-enters the conversation history on every subsequent turn, multiplying
token cost and latency for the rest of the run. For concept/keyword filtering (`TableName LIKE`),
which `base_tableList` cannot do, scope a `base_readQuery` against `DBC.TablesV` instead:

```sql
-- One concept keyword
SELECT TableName, TableKind
FROM DBC.TablesV
WHERE DatabaseName = '<ranked_database>'
  AND TableName LIKE '%<concept_keyword>%' ESCAPE '\';

-- Multiple concept keywords (OR-chain built from the concept-expansion list)
SELECT TableName, TableKind
FROM DBC.TablesV
WHERE DatabaseName = '<ranked_database>'
  AND ( TableName LIKE '%patient%'   ESCAPE '\'
     OR TableName LIKE '%admission%' ESCAPE '\'
     OR TableName LIKE '%lab%'       ESCAPE '\' );
```

Run one such `base_readQuery` per ranked database from Phase 3 — the `LIKE` clauses come from the
concept-expansion list, so this returns only plausible candidates instead of the entire catalog. Fall
back to `base_tableList(database_name)` — always passing the argument, since omitting it silently
targets the session default — for a single ranked database only if keyword filtering returns nothing,
and never query `DBC.TablesV` without a `WHERE DatabaseName = ...` filter.

Score every returned table/view/foreign-table name the same way as Phase 3, against the same
concept-expansion lists. Keep every table that matches at least one expected entity, including any
foreign table that appears here — **NOS foreign tables surface in this same `DBC.TablesV` listing,
but OTF (Iceberg/Delta) tables registered through an external catalog typically do NOT** and
require a separate datalake-enumeration step. Never conclude a requested external/OTF source is
unavailable based on an empty or NOS-only `DBC.TablesV` result alone — see
[hybrid-source-discovery.md](./hybrid-source-discovery.md) Phase 7, which must run in parallel with
this phase before ruling out an external source.

### Worked Example

```sql
SELECT TableName, TableKind FROM DBC.TablesV WHERE DatabaseName = 'CareCloud_db';
-- returns: Patient, Admissions, Labs, Lab_History, Billing_Notes, Patient_Analysis, Patient_Journey
```

| Table | Concept match | Keep? |
|---|---|---|
| `Patient` | patient | Yes — anchor candidate |
| `Admissions` | admission | Yes |
| `Labs` | labs | Yes (event-grain — flag for aggregation) |
| `Lab_History` | labs | Yes (event-grain, but keyed directly by patient) |
| `Billing_Notes` | no strong match to readmission entities | No |
| `Patient_Analysis`, `Patient_Journey` | ambiguous names, no confirmed schema yet | Hold — inspect DDL before deciding |

## Phase 5 — Metadata Inspection

**MCP tool:** `base_tableDDL(db_name, table_name)` — run against every table kept from Phase 4.

Extract from the returned DDL:

- **Columns and types** — needed for Phase 6 (join-key type reconciliation) and Phase 8 (feature
  selection).
- **Primary index (PI)** — Teradata's PI is the closest analog to a primary key and is usually
  the join key or the natural entity/event identifier (e.g. `Patient` PI `patient_id`, `Admissions`
  PI `admission_id`, `Labs` PI `lab_id, admission_id`).
- **Foreign-key-like columns** — Teradata rarely enforces `REFERENCES` constraints in practice, so
  treat any column whose name matches another table's PI (e.g. `Admissions.patient_id` matching
  `Patient.patient_id`) as an inferred foreign key. This inference feeds directly into
  [join-key-reconciliation.md](./join-key-reconciliation.md).
- **Statistics and partitioning** — `PARTITION BY` clauses and any `COLLECT STATISTICS` targets
  already defined on the table.
- **Row estimates** — avoid a full `COUNT(*)` on very large fact/event tables purely for ranking. Use
  a space-based estimate from `DBC.TableSizeV`, and reserve an exact count for genuinely small candidates:
  ```sql
  -- Space-based size estimate (no table scan); 'bytes' is reserved, so alias as perm_bytes
  SELECT DatabaseName, TableName, SUM(CurrentPerm) AS perm_bytes
  FROM DBC.TableSizeV
  WHERE DatabaseName = '<ranked_database>' AND TableName = '<candidate_table>'
  GROUP BY DatabaseName, TableName;

  -- Exact count — only for small candidate tables
  SELECT COUNT(*) FROM <ranked_database>.<candidate_table>;
  ```

Optionally, call `base_columnDescription(db_name, table_name)` alongside `base_tableDDL` when the
DDL alone doesn't make column intent obvious — it returns per-column nullability and length that
help decide whether a column is a business feature or a housekeeping/audit column (see
[feature-and-label-selection.md](./feature-and-label-selection.md)).

## Discovery Ranking

Once a table's DDL has been inspected, score it using this weighted formula so that the final
selection is explainable rather than a guess:

| Signal | Weight | How it is measured |
|---|---|---|
| Table name similarity | 40% | Substring/fuzzy match between the table name and the concept-expansion list for the entity it is meant to satisfy |
| Column similarity | 30% | Proportion of a candidate table's columns (from `base_columnDescription`) that match expected feature-group keywords |
| Business description | 20% | Presence of a matching keyword in any DDL/table `COMMENT` text, if present |
| Joinability | 10% | Whether the candidate shares a key-like column (Phase 5 inference) with a table already selected; `base_tableAffinity(db_name, obj_name)` — "tables commonly used together" — can be used as a secondary signal here when available |

Combine the four weighted components into a single score per candidate table, and rank tables
within the same concept group by that score.

### Worked Scoring Example

Scoring three `CareCloud_db` candidates against the "labs" concept:

| Table | Name match (40%) | Column match (30%) | Description (20%) | Joinability (10%) | Score |
|---|---|---|---|---|---|
| `Labs` | 1.0 | 0.8 (`lab_value`, `lab_date`, `admission_id`) | 0.5 | 1.0 (shares `admission_id` with `Admissions`) | 0.87 |
| `Lab_History` | 0.6 (partial name match) | 0.7 (`lab_value`, `patient_id`) | 0.5 | 1.0 (shares `patient_id` with `Patient`) | 0.71 |
| `Billing_Notes` | 0.0 | 0.1 | 0.2 | 0.0 | 0.07 |

`Labs` and `Lab_History` both clear a reasonable acceptance bar and can be evaluated
against the join graph in Phase 6; `Billing_Notes` is dropped.

## Anchor Selection Must Pass a Join-Overlap Gate

Name/column similarity alone is **not** sufficient to commit an anchor. When the request names an
external source (a NOS/OTF feed, an object-store path), the selected anchor must actually *join*
that feed on overlapping key values — not merely have a plausibly-matching name. Concretely: several
databases may contain a `Patient`-like table (`CareCloud_db.Patient`, `RegionalClinic_db.Patients`, …)
that rank almost equally on name similarity, yet only one has keys that overlap the named external
feed — and the correct anchor may even score slightly *lower* on name match. Committing the
higher-named table produces a zero-overlap join.

Before committing an anchor, confirm the join with the cheap overlap probe from
[join-key-reconciliation.md](./join-key-reconciliation.md) (Phase 8.5): count how many anchor keys
match the required external source. Treat non-overlap as a **gate**, not a tie-breaker — an anchor
that does not join the named external feed must not be selected over one that does, regardless of
its name-similarity score. If the current top-ranked anchor yields ~0% overlap, drop back to the
ranked list and probe the next candidate rather than proceeding to materialization. Never resolve
a zero-overlap result by fabricating a join key or simulating the source (see the skill's Phase 7).

## Communicating Discovery Confidence

Never report a discovery failure as a dead end. If several tables plausibly match a concept,
return all of them ranked by score with the score visible, and let the user (or downstream
context) break the tie. For example, prefer:

> "I found three likely lab tables ranked by confidence: `Labs` (0.87),
> `Lab_History` (0.71), `Billing_Notes` (0.07, unlikely)."

over a bare:

> "I couldn't find transaction tables."

If the top-ranked candidate's score is materially higher than the rest, proceed with it directly
and note the alternates considered; if scores are close, surface all close candidates and continue
with the one that best satisfies the join graph in
[join-key-reconciliation.md](./join-key-reconciliation.md).
