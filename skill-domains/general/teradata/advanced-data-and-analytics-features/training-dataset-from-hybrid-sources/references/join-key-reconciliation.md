# Join Key Reconciliation — Complete Reference

> Covers Phase 6 of the `training-dataset-from-hybrid-sources` pipeline: turning the set of
> discovered tables into a connected join graph, choosing the anchor table, and resolving key
> type/format mismatches before any join is executed.

## Building the Join Graph

Treat every table kept from [database-and-table-discovery.md](./database-and-table-discovery.md)
as a node. Add an edge between two tables whenever they share a key-like column, using the PI and
inferred-foreign-key information gathered in Phase 5. Two columns are considered the same key when
they match on:

- **Exact name match** — e.g. `cust_id` appearing in both tables.
- **Common suffix/prefix pattern** — e.g. `acct_nbr` vs. `account_number`, `CustomerID` vs.
  `cust_id`.

### Common Key-Naming Patterns

| Business concept | Typical column name patterns |
|---|---|
| Customer | `cust_id`, `customer_id`, `CustomerID`, `client_id` |
| Account | `acct_nbr`, `account_id`, `account_number` |
| Subscriber | `subscriber_id`, `SubscriberID` (streaming/SaaS) |
| Household | `household_id`, `hh_id` |
| Device | `device_id`, `imei`, `msisdn` |
| Transaction | `tran_id`, `transaction_id`, `trx_id` |

### Worked Example — Building the Patient-Readmission Graph

Nodes and edges discovered for the patient-readmission request:

```
Patient (patient_id) ── patient_id ──> Admissions (patient_id, admission_id)
Admissions (admission_id) ── admission_id ──> Labs (admission_id)
Patient (patient_id) ── patient_id ──> Lab_History (patient_id)
Patient (patient_id) ── patient_id ──> nos_claims_feed (patient_id)         [NOS, external]
Patient (patient_id) ── patient_id ──> patient_portal_events (patient_id)   [OTF/Iceberg, external]
```

`Admissions` is a **bridge table**: `Labs` cannot join directly to `Patient` because it is
keyed by `admission_id`, not `patient_id`. Without `Admissions` in the graph, `Labs` would be a
disconnected node and must either be dropped or re-discovered through a bridging table.

## Choosing the Anchor Table

The anchor is the table at the **grain the final training row must represent** — usually the
entity carrying (or nearest to) the label. In the patient-readmission example the label
(`readmit_flag`) lives on the external `nos_claims_feed` table, but the anchor is still
`Patient`, because every other source (admissions, labs, claims, portal events) resolves back
to `patient_id` and the training table should have one row per patient. Pick the anchor from the
join graph, not from whichever table happens to hold the label.

## Verifying Join Key Compatibility

Before writing any join, compare the column type recorded in Phase 5's `base_tableDDL` output on
both sides of every edge in the graph. Mismatches are common and expected, especially between EDW
native tables and NOS/OTF external sources, because:

- NOS foreign tables often have their column types **inferred from the underlying Parquet/CSV/JSON
  schema**, which can differ in width or type family from the EDW column it is meant to join to
  (for example, a Parquet-inferred `BIGINT` on a foreign table joining to an EDW `INTEGER` column,
  or a numeric ID that was written to the object store as a string).
- OTF Iceberg/Delta reads (see [hybrid-source-discovery.md](./hybrid-source-discovery.md)) return
  whatever type the source catalog declared, which may not match the EDW convention.

Always `CAST` explicitly in the join predicate rather than relying on implicit conversion:

```sql
-- EDW patient.patient_id is INTEGER; NOS claims feed's patient_id was inferred as BIGINT.
SELECT c.*, b.ext_risk_score, b.readmit_flag
FROM CareCloud_db.Patient c
LEFT JOIN nos_claims_feed b
  ON CAST(c.patient_id AS BIGINT) = b.patient_id;
```

```sql
-- Streaming EDW SubscriberID is VARCHAR(10); confirm the NOS/OTF side is also VARCHAR and TRIM
-- both sides in case of trailing padding differences introduced by the source file format.
SELECT t.*, n.avg_bitrate_kbps, n.buffering_events_30d
FROM StreamCo_db.Subscriber_Churn t
LEFT JOIN nos_stream_usage n
  ON TRIM(t.SubscriberID) = TRIM(n.SubscriberID);
```

## Verifying Join Key Value Overlap (Phase 8.5)

A matching **type** is necessary but not sufficient. Two keys can be perfectly type-compatible and
still describe **non-overlapping populations** — the anchor's ids sit in one range and the external
source's ids in another, so the join returns (almost) no matches. This is the single most common
cause of a corrupted hybrid dataset, and it must be caught *before* materialization, not after.

Probe every anchor→source edge with a cheap match count before writing the CTAS:

```sql
-- How many anchor entities actually match the external feed?
SELECT COUNT(*) AS matched
FROM CareCloud_db.Patient a
WHERE EXISTS (
    SELECT 1 FROM nos_claims_feed e
    WHERE CAST(a.patient_id AS BIGINT) = e.patient_id
);
```

Interpret the result:

- **Healthy overlap** (a large fraction of anchor rows match) → proceed to the join.
- **Zero / near-zero overlap** → **stop. Do not build the table.** This is a discovery signal, not
  a licence to improvise. The most likely cause is that the **wrong anchor** was chosen: another
  `Patient`-like table in a different database usually *does* overlap the named external feed.
  Return to [database-and-table-discovery.md](./database-and-table-discovery.md), re-rank, and
  probe the next candidate anchor. Only after an exhaustive re-discovery finds no overlapping
  anchor may you surface the mismatch to the user and ask them to point to the correct source or
  provide a mapping table.

### Prohibited responses to zero overlap

None of the following are ever acceptable — each silently fabricates the data contract:

- **Synthesizing a join key** to force a match: `MOD(id, N) + offset`, a hash, `ROW_NUMBER()`, or
  any random/positional pairing between anchor and external rows. The resulting "enriched" features
  are not truly tied to the correct entities.
- **Simulating the external source** from unrelated columns (or from thin air) because the real one
  wasn't found.
- **Dropping the required external source** and shipping the dataset without it (or building from
  the external table alone and discarding the EDW anchor) as if the request were satisfied.

When a legitimate join genuinely cannot be established, the correct deliverable is a clear
statement of the missing overlap/object plus a request for the correct source or a mapping table —
never a fabricated or simulated one.

## Handling Disconnected Join Graphs

If a discovered table shares no key with any other table in the graph:

1. First check whether a **bridge table** exists among already-discovered candidates (as
   `Accounts` bridges `Customer` to `Transactions`). If so, add it to the join graph.
2. If no bridge exists, return to [intent-and-semantic-discovery.md](./intent-and-semantic-discovery.md)
   Phase 2 and expand the concept list to search for a bridging entity explicitly (e.g. search for
   an "account" or "policy" concept if a "transaction" table won't connect to "customer" directly).
3. If still no bridge is found, drop the disconnected table from the plan and note it as excluded,
   rather than forcing an unrelated join that would inflate or corrupt row counts.

## Composite and Multi-Column Keys

Some event-grain tables are keyed by more than one column (e.g. `Lab_History` PI
`patient_id, lab_id`). When joining on a composite key, join on **all** key columns together, not
just the leading one — a partial composite join silently turns a many-to-one relationship into an
unintended many-to-many join and multiplies row counts:

```sql
-- Far-side table keyed by two columns (e.g. patient_id + admission_id).

-- WRONG — joining on the leading key only:
SELECT ...
FROM Admissions p
JOIN <event_table> c
  ON p.patient_id = c.patient_id;

-- RIGHT — join on every key column:
SELECT ...
FROM Admissions p
JOIN <event_table> c
  ON p.patient_id = c.patient_id
 AND p.admission_id = c.admission_id;
```

## Entity Grain vs. Event Grain Reminder

Any table on the far side of a join that has **more than one row per anchor key** (e.g. many
`Labs` rows per `admission_id`, many `patient_portal_events` rows per `patient_id`) must be aggregated to
the anchor's grain before or during the final join — never joined directly, which would multiply
the anchor's row count. This aggregation is executed in
[materialization-and-validation.md](./materialization-and-validation.md) Phase 9, using the join
graph and CAST rules established here.

## Worked End-to-End Example — Patient Readmission Join Plan

1. Anchor: `Patient` (`patient_id`, entity grain).
2. Bridge: `Admissions` (`patient_id` → `admission_id`), aggregated to one row per `patient_id` (e.g. count of
   admissions, sum of length-of-stay) before joining to the anchor.
3. Event-grain: `Labs`, aggregated to `admission_id` grain first, then rolled up through
   `Admissions` to `patient_id` grain.
4. Event-grain: `Lab_History`, aggregated directly to `patient_id` grain (no bridge needed).
5. External enrichment (NOS): `nos_claims_feed`, already at `patient_id` grain — CAST applied per
   the compatibility check above — carries the label `readmit_flag`.
6. External enrichment (OTF): `patient_portal_events`, event grain, aggregated to `patient_id` grain (e.g.
   portal-visit count, total `portal_minutes`) before joining.

This join plan feeds the CTAS and the *Ready-to-Run Build Template* in
[materialization-and-validation.md](./materialization-and-validation.md).
