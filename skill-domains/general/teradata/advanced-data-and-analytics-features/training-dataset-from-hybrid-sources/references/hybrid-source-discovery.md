# Hybrid Source Discovery — Complete Reference (NOS + OTF)

> Covers **Phase 7** (locating and reading sources outside native EDW tables) and the **Phase 9**
> staging of those sources into the CTAS, for the `training-dataset-from-hybrid-sources` pipeline.
> It is the single reference for both hybrid tiers: **NOS** (Native/Network Object Store) foreign
> tables and raw object-store paths, and **OTF** (Open Table Format — Apache Iceberg and Delta Lake)
> tables registered in an external catalog. Scope is strictly **discover, interpret, read, and stage**.
>
> **Out of scope for this skill (intentionally omitted):**
> - `WRITE_NOS` and any export-to-object-store flow — this skill never writes to an object store.
> - `CREATE`/`REPLACE`/`DROP AUTHORIZATION`, `CREATE FOREIGN TABLE` authoring, and
>   `REPLACE`/`ALTER`/`DROP DATALAKE` — the skill never provisions credentials, datalakes, or
>   self-grants (see the SKILL's Phase 4.5 and Anti-Fabrication rules); it only *reads* what exists.
> - Catalog integration/provisioning (AWS Glue, Hive Metastore, Polaris, Unity Catalog, BigLake,
>   Lake Formation, OAuth) — infrastructure setup, not raw assembly.
> - DML on hybrid sources (`INSERT`/`UPDATE`/`DELETE`/`MERGE`), managed-OTF tables, and
>   `RETENTIONDAYS` lifecycle — mutating work barred by the No-Destructive-SQL rule.
> - Deep semi-structured parsing (`JSON_TABLE`, `XMLTABLE`, `JSON_SHRED_BATCH`, DATASET shredding)
>   and `COLLECT STATS` on *external* sources — payload flattening and source-side stats are
>   downstream data-preparation work, not raw assembly.

## Overview of the Three Storage Tiers

| Tier | What it is | MCP tool support |
|---|---|---|
| EDW native table | A standard Teradata table | Full — a scoped `base_readQuery` against `DBC.TablesV`, `base_tableDDL`, `base_columnDescription`, and `base_readQuery` all work |
| NOS foreign table | A `CREATE FOREIGN TABLE` object pointing at CSV/JSON/Parquet/ORC/Avro files in an object store, registered in `DBC.TablesV` | Full — behaves like a normal table for every metadata tool because it *is* registered as a database object |
| OTF (Iceberg/Delta) via external catalog | A table registered in an external catalog (e.g. AWS Glue) and read through a Teradata OTF read function | Partial — `DBC.TablesV`/`base_tableDDL`/`base_columnDescription` typically **fail** because the three-level external-catalog namespace is not exposed through `DBC` views; discovery instead uses `HELP DATALAKE`/`HELP DATABASE`/`HELP TABLE`, which are **not** `SELECT` statements and must run through `base_executeSQL` (`base_readQuery` rejects them with `TD_TOOL_EXECUTION_ERROR: Only SELECT queries are allowed`); only the final read of the confirmed table is a `SELECT` and goes through `base_readQuery` |

Because of this split, Phase 7 runs two different discovery strategies depending on which tier a
candidate source belongs to. Enrichment is **best-effort**: if no relevant or accessible hybrid
source exists, an EDW-only dataset is a valid outcome — note that no enrichment was applied.

---

# Part 1 — NOS (Object-Store) Sources

NOS foreign tables appear directly in the scoped `DBC.TablesV` query from Phase 4 alongside ordinary
tables (and in a `database_name`-scoped `base_tableList`) — see
[database-and-table-discovery.md](./database-and-table-discovery.md) Phase 4 for why the
keyword-filtered `DBC.TablesV` query is preferred over the unfilterable `base_tableList`. Once found,
`base_tableDDL` returns the full `CREATE FOREIGN TABLE` definition — the authoritative signal for
provenance and format.

## Reading an Existing `CREATE FOREIGN TABLE` Definition

### Canonical Shape

```sql
CREATE FOREIGN TABLE nos_claims_feed,
  EXTERNAL SECURITY DEFINER TRUSTED ext_stg.s3_auth        -- auth sits OUTSIDE USING(...)
USING (
    LOCATION('/s3/s3.us-west-2.amazonaws.com/<bucket>/nos_claims_feed/')
    STOREDAS('PARQUET')
);
```

Two placement rules to remember when reading (or reasoning about) the DDL:

- **`EXTERNAL SECURITY [DEFINER|INVOKER] TRUSTED <auth>` sits outside `USING(...)`,** immediately after
  the table name. This is the correct place for authorization on foreign-table DDL.
- **Inline `AUTHORIZATION(...)` inside a `USING(...)` clause is valid only for ad hoc `READ_NOS` calls,**
  not for foreign-table DDL. Seeing it inline in a `CREATE FOREIGN TABLE` would be a malformed definition.

### `USING` Parameters You Will See

| Parameter | Meaning when reading the DDL |
|---|---|
| `LOCATION` | The S3/Azure/GCS path — confirms the source is genuinely object-store-backed (see path formats below). |
| `AUTHORIZATION` | Named auth object (when not using `EXTERNAL SECURITY`). |
| `STOREDAS` | File format: `'PARQUET'`, `'CSV'`, `'JSON'`, `'ORC'`, `'AVRO'` — the format-identification signal. |
| `HEADER` | `'TRUE'`/`'FALSE'` — CSV has a header row. |
| `ROWFORMAT` | JSON spec of CSV field/record delimiters. |
| `PATHPATTERN` | Maps path segments to virtual `$PATH.$var` columns (partition pruning). |
| `SCHEMA` | Explicit column definitions (used for JSON/CSV where schema is not embedded). |

### Format Identification from the DDL

| Signal in the DDL | Format |
|---|---|
| `STOREDAS('PARQUET')` | Parquet |
| `STOREDAS('CSV')` | CSV |
| `STOREDAS('JSON')` | JSON |
| `STOREDAS('ORC')` | ORC |
| `STOREDAS('AVRO')` | Avro |

> **`TableKind` is not a reliable NOS filter.** A verified S3-backed `CREATE FOREIGN TABLE` can report
> `TableKind = 'T'` (the ordinary-table code) on a real instance, so a `WHERE TableKind = 'O'` scan can
> silently exclude a genuine NOS source. Scan by `TableName LIKE` on concept synonyms only, then confirm
> each hit with `base_tableDDL` and check the text for `CREATE FOREIGN TABLE` / an external `LOCATION`.
> (Cross-referenced in the SKILL as *Provenance, not `TableKind`*.)

Once confirmed, a foreign table is queried exactly like a native table via `base_readQuery` — no special
read function is required — and can be referenced by name directly in the Phase 9 CTAS `FROM`/`JOIN`.

## `READ_NOS` — Reading a Raw Object-Store Path

When a request names a specific bucket/path but **no matching foreign table** turns up in `DBC.TablesV`,
do not conclude the data is missing. The files may exist without a `CREATE FOREIGN TABLE` wrapper. Probe
the location with `READ_NOS` first. Its read-only forms (`NOSREAD_KEYS`, `NOSREAD_SCHEMA`) and a
`NOSREAD_RECORD` `SELECT` all run through `base_readQuery`.

```sql
SELECT <columns>
FROM (
    LOCATION = '<path>'
    AUTHORIZATION = <auth_object>
    RETURNTYPE = '<return_type>'
    [ STOREDAS = '<format>' ]
    [ additional parameters ]
) AS alias;
```

### `LOCATION` Path Formats

| Cloud | Format |
|---|---|
| Amazon S3 | `/s3/bucket-name.s3.amazonaws.com/path/` |
| Amazon S3 (region) | `/s3/bucket-name.s3.us-west-2.amazonaws.com/path/` |
| Azure Blob | `/az/account.blob.core.windows.net/container/path/` |
| Google Cloud | `/gs/bucket-name.storage.googleapis.com/path/` |

Path wildcards: a trailing `/` reads all files in a directory; `/…/file.parquet` targets one file;
`/…/*.parquet` targets all Parquet files.

### `RETURNTYPE` Values

| Value | Returns | Use in this skill |
|---|---|---|
| `NOSREAD_KEYS` | File listing (`Location`, `ObjectLength`, `ObjectTimestamp`) | **Discovery** — confirm files exist at a path before declaring a named source absent (Phase 7 rung 3). |
| `NOSREAD_SCHEMA` | Column names and types from file metadata | **Discovery** — inspect Parquet/ORC schema to learn columns/keys before joining. |
| `NOSREAD_RECORD` | Actual data rows | **Read/stage** — project columns for an overlap probe or to stage into the Phase 9 CTAS. |

```sql
-- List files at a location (NOSREAD_KEYS)
SELECT location, object_length, object_timestamp
FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/data/'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_KEYS'
) AS keys
ORDER BY object_timestamp DESC;

-- Inspect schema before joining (NOSREAD_SCHEMA) — embedded in Parquet/ORC; from payload for JSON/CSV
SELECT * FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/data/sample.parquet'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_SCHEMA'
) AS schema_info;

-- Read/project Parquet data (NOSREAD_RECORD)
SELECT cust_id, event_date, amount
FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/parquet_data/'
    AUTHORIZATION = mydb.s3_auth
    STOREDAS = 'PARQUET'
    RETURNTYPE = 'NOSREAD_RECORD'
) AS data;

-- Read JSON payload fields with dot notation + an inline type
SELECT payload..cust_id (INTEGER),
       payload..amount (DECIMAL(10,2))
FROM (
    LOCATION = '/s3/my-bucket.s3.amazonaws.com/orders/'
    AUTHORIZATION = mydb.s3_auth
    RETURNTYPE = 'NOSREAD_RECORD'
) AS data;
```

> Payload dot-notation is only to **project raw key/feature columns** for discovery, overlap probes, or
> CTAS staging. Flattening nested arrays/objects into a cleaned wide table is downstream data-preparation
> work — out of scope here.

### Useful Read Parameters

| Parameter | Values | Why it helps discovery/assembly |
|---|---|---|
| `STOREDAS` | `'PARQUET'` / `'JSON'` / `'CSV'` / `'ORC'` / `'AVRO'` | Explicit format skips detection overhead and enables Parquet columnar pushdown. |
| `SAMPLE_PERC` | `'1'`–`'100'` | Sample a fraction while exploring, before a full read. |
| `HEADER` | `'TRUE'`/`'FALSE'` | CSV header row present. |
| `ROWFORMAT` | JSON string | CSV field/record delimiters and character set. |
| `PATHPATTERN` | `'$dir1/$dir2/$file'` | Extract partition values from the path; filter on `$PATH.$var` to prune files. |

**Path filtering beats payload filtering.** When the same value lives in both the path and the payload,
filter on the path variable (`WHERE $PATH.$year = '2025'`) — it prunes whole files instead of reading
them all and filtering rows afterward.

## Interpreting NOS Authorization (Read-Only)

This skill **reads** authorization signals; it never creates, replaces, or drops them.

- **What the auth object does:** it maps the Teradata session to object-store credentials. Under
  `EXTERNAL SECURITY DEFINER TRUSTED`, the auth owner's credentials are used; under `INVOKER`, each user
  supplies their own. Foreign tables are read-only, and NOS enforces both a Teradata privilege check and
  an object-store credential check.
- **When an auth is missing or wrong,** discovery fails at query time — surface the exact object and the
  privilege/auth that must be provisioned separately, and stop. Never `CREATE`/`REPLACE AUTHORIZATION`
  to self-repair (see Phase 4.5 and Anti-Fabrication).

## Common Discovery Errors (NOS)

| Symptom | Likely cause | Read-only response for this skill |
|---|---|---|
| `Access denied` / `Error 3523` on a NOS read | Session lacks the object-store credential or the `SELECT` right | Surface the exact object + `GRANT`/auth to request; drop the candidate and re-rank. Never self-grant. |
| `Bucket not found` / no files at `LOCATION` | Wrong path/region, or empty prefix | Re-check the `LOCATION` in the DDL; run `NOSREAD_KEYS` to confirm keys exist before declaring the source absent. |
| Schema looks wrong / columns missing | Format misdetected, or inconsistent files | Set `STOREDAS` explicitly; use `NOSREAD_SCHEMA` to inspect before joining. |
| A `*_parquet` / `*_from_s3` look-alike assumed external | Name inferred instead of DDL-confirmed | Confirm with `base_tableDDL` — only an external `LOCATION` / `CREATE FOREIGN TABLE` counts as NOS (Provenance, not `TableKind`). |

---

# Part 2 — OTF (Iceberg / Delta) Sources

## Why OTF Discovery Differs From EDW/NOS

OTF tables registered through an external catalog frequently **will not** surface through a
`DBC.TablesV` query, `base_tableDDL`, or `base_columnDescription` — those calls typically fail or
return nothing for objects whose metadata lives in the external catalog rather than `DBC`. An empty
`DBC.TablesV` result is **not** proof the source is absent. When metadata-tool calls come up empty,
switch to enumerating registered datalakes first, then browsing their namespaces/tables with `HELP`,
rather than jumping to a read that requires already knowing the exact three-part name.

## Three-Part Naming

Every OTF table is addressed as `datalake_name.database_name.table_name`:

```sql
SELECT * FROM prod_iceberg.sales_db.orders;      -- a SELECT: base_readQuery
```

## Discovery: Enumerate → Browse → Identify

### Step 1 — Enumerate registered datalakes (a `SELECT`)

```sql
SELECT DatalakeName, CatalogType, StorageLocation FROM DBC.DatalakeInfoV;   -- base_readQuery
```

Browse **every** datalake returned — never just the first alphabetical one. A same-topic table in one
datalake is not grounds to stop enumerating the others.

### Step 2 — Browse namespaces/tables with `HELP` (NOT `SELECT`)

`HELP` is **not** a `SELECT` statement. Route these three through `base_executeSQL`; `base_readQuery`
rejects them with `TD_TOOL_EXECUTION_ERROR: Only SELECT queries are allowed` (see the SKILL's Tool
Routing rule):

```sql
HELP DATALAKE <datalake>;                       -- lists databases/namespaces in the catalog
HELP DATABASE <datalake>.<namespace>;           -- lists tables in a namespace (+ OTF Table Format column)
HELP TABLE <datalake>.<namespace>.<table>;      -- column metadata for a specific table
```

Score the returned names against the same concept-expansion list used in Phase 3/4 (e.g. a table named
`stream_support_tickets` matches the "support ticket" concept). `HELP TABLE`/`HELP DATABASE` succeed on
3-level OTF namespaces where `base_tableDDL` fails, and expose an explicit `OTF Type`/`OTF Table Format`
column — a cleaner format signal than inferring it.

> **Per-datalake failures are not proof of absence.** *Error 6938 (`Authorization '<auth>' does not
> exist`)* on one datalake is a per-datalake break — skip it, note it unreachable, and keep enumerating
> the rest. Never `CREATE AUTHORIZATION`/`REPLACE DATALAKE` to self-repair.

### Step 3 — Identify the format

| Signal | Format |
|---|---|
| `HELP DATABASE`/`HELP TABLE` shows `OTF Table Format = iceberg` | Iceberg |
| `HELP DATABASE`/`HELP TABLE` shows `OTF Table Format = delta` | Delta Lake |
| Read via `TD_ICEBERG_READ` (fallback) | Iceberg |
| Read via `TD_DELTA_READ` (fallback) | Delta Lake |

## Reading an OTF Table

### Preferred — query the confirmed table by three-part name (a `SELECT`)

Once a candidate is confirmed via `HELP`, query it directly — this final read *is* a `SELECT` and runs
through `base_readQuery`. OTF tables can be joined with native Teradata tables, NOS foreign tables, and
other OTF tables:

```sql
-- Iceberg joined with a native Teradata table
SELECT c.customer_name, o.order_date, o.total
FROM prod_iceberg.sales_db.orders o
JOIN my_local_db.customers c ON o.customer_id = c.id;
```

### Fallback — direct read function (only when no DATALAKE object is registered)

When no `DATALAKE` object has been registered for the source, read it with the format-appropriate
function. This carries no metadata-tool support, so validate schema/grain by inspecting a sample result
set rather than relying on `base_tableDDL`.

```sql
-- Iceberg
SELECT * FROM TD_OTFDB.TD_ICEBERG_READ(
    AUTHORIZATION(ext_stg.s3_auth)
    DATALAKE('iceberg_catalog')
    ICEBERG_NAMESPACE('portal_events_ns')
    ICEBERG_TABLE('patient_portal_events')
) AS t;

-- Delta Lake — analogous arguments in the same function family
SELECT * FROM TD_OTFDB.TD_DELTA_READ(
    AUTHORIZATION(<auth_object>)
    DATALAKE('<catalog_name>')
    DELTA_NAMESPACE('<namespace>')
    DELTA_TABLE('<table_name>')
) AS t;
```

> Iceberg supports time-travel reads (`FOR TIMESTAMP AS OF` / `FOR VERSION AS OF`) and `$snapshots`/
> `$history` metadata tables. These are **not** needed for raw training-set assembly — assemble from the
> current table state unless the user explicitly asks for a historical snapshot.

## Type Mapping for Join-Key Reconciliation

When an OTF key joins onto a native/NOS key, reconcile the declared types explicitly. The catalog reports
OTF-native types; map them to the Teradata type on the other side before comparing.

### Iceberg ↔ Teradata

| Iceberg Type | Teradata Type | Reconcile a join key with |
|---|---|---|
| `int` | INTEGER / SMALLINT | usually compatible; `CAST(... AS BIGINT)` if the other side is BIGINT |
| `long` | BIGINT | `CAST(<other_side> AS BIGINT)` when the other side is INTEGER/DECIMAL |
| `string` | VARCHAR / CHAR | `TRIM()` both sides when one is padded `CHAR`; cast a numeric side to VARCHAR only if the id is genuinely character |
| `decimal(p,s)` | DECIMAL(p,s) | align precision/scale; `CAST(... AS BIGINT)` if joined to an integer id |
| `date` / `timestamp` | DATE / TIMESTAMP | avoid string casts on partition/date keys — compare as `DATE`/`TIMESTAMP` |

### Delta ↔ Teradata

| Delta Type | Teradata Type | Note for key reconciliation |
|---|---|---|
| `integer` | INTEGER | compatible |
| `long` | BIGINT | cast an INTEGER counterpart to BIGINT |
| `string` | VARCHAR | Delta does **not** enforce declared length — `TRIM()`/length is not guaranteed; normalize both sides |
| `decimal(p,s)` | DECIMAL(p,s) | trailing-zero normalization can differ (`10.50` vs `10.5`) |
| `date` / `timestamp` | DATE / TIMESTAMP | compare as date/timestamp, not string |

Full casting guidance and the join-graph rules: [join-key-reconciliation.md](./join-key-reconciliation.md).

## Row-Count Reads for Structural Validation (Phase 10)

Validation of the **materialized native output** uses ordinary `SELECT`s. When you need the source-side
cardinality of an OTF table to confirm no fan-out, a plain `COUNT(*)` works:

```sql
SELECT COUNT(*) FROM prod_iceberg.sales_db.orders;                          -- base_readQuery
SELECT APPROXCOUNT(DISTINCT customer_id) FROM prod_iceberg.sales_db.orders; -- fast distinct-key estimate
```

## Common Discovery Errors (OTF)

| Symptom | Likely cause | Read-only response for this skill |
|---|---|---|
| `DBC.TablesV`/`base_tableDDL` returns nothing for a named OTF table | Metadata lives in the external catalog, not `DBC` | Switch to `DBC.DatalakeInfoV` + `HELP DATALAKE`/`HELP DATABASE`/`HELP TABLE`; don't conclude absence. |
| *Error 6938* (`Authorization '<auth>' does not exist`) on one datalake | That datalake's auth is unreachable | Skip it, note it unreachable, keep enumerating the rest. Never `CREATE`/`REPLACE` to self-repair. |
| `base_readQuery` rejects `HELP …` | `HELP` is not a `SELECT` | Re-run via `base_executeSQL` (see Tool Routing). |
| `Table not found in catalog` | Wrong namespace/table name | Navigate `HELP DATALAKE` → `HELP DATABASE` to get the exact three-part name. |
| Zero overlap after a type-compatible OTF join | Wrong datalake/decoy, or a missing key transform | Browse **every** datalake/namespace and re-rank in the same turn; never synthesize a key (see Anti-Fabrication). |

---

# Part 3 — Staging a Hybrid Source Into the Phase 9 CTAS

Once a NOS or OTF source is read, fold it into the join graph exactly like any other table node — the
same key-type `CAST`/`TRIM` rules and the same entity-vs-event-grain aggregation rules from
[join-key-reconciliation.md](./join-key-reconciliation.md) apply. The only difference is *how* it is
referenced:

- A **NOS foreign table** is referenced by name directly in `FROM`/`JOIN`.
- A **raw `READ_NOS` read** or an **OTF read** (three-part name or `TD_ICEBERG_READ`/`TD_DELTA_READ`) has
  no persisted name to join against — stage it as a CTE (or an aggregated sub-select) inside the same
  `base_executeSQL` CTAS call that builds the training table.

```sql
-- Illustrative: an event-grain hybrid source aggregated to entity grain, then joined.
-- (Swap the NOS READ_NOS block for `FROM prod_iceberg.portal_events_ns.patient_portal_events` for an OTF source.)
CREATE TABLE TDH_TRAINSET_<runtag>__<slug> AS (
    WITH events_agg AS (
        SELECT cust_id,
               COUNT(*)        AS event_count,
               MAX(event_date) AS last_event_date
        FROM (
            LOCATION = '/s3/my-bucket.s3.amazonaws.com/web_events/'
            AUTHORIZATION = mydb.s3_auth
            STOREDAS = 'PARQUET'
            RETURNTYPE = 'NOSREAD_RECORD'
        ) AS r
        GROUP BY cust_id                                   -- event grain -> entity grain BEFORE the join
    )
    SELECT a.customer_id,
           a.tenure_months,
           e.event_count,
           e.last_event_date
    FROM <anchor> a
    LEFT JOIN events_agg e
      ON CAST(a.customer_id AS BIGINT) = CAST(e.cust_id AS BIGINT)   -- reconcile key types
) WITH DATA
PRIMARY INDEX (customer_id);
```

> `CREATE TABLE AS` is the **only** write this skill issues, and it runs through `base_executeSQL`
> (`base_readQuery` is `SELECT`-only). Never `INSERT`/`UPDATE`/`DELETE`/`MERGE` into a hybrid source.
> See the SKILL's Tool Routing and No-Destructive-SQL rules.

## MCP Tool Compatibility Priority

When multiple ways exist to bring an external source into the training table, prefer in this order:

1. **NOS foreign table** — full metadata tool support, simplest to discover and validate.
2. **In-database CTAS/CTE copy** of a confirmed external source (`base_executeSQL`) — materialize once,
   then treat the copy as a native node for the remainder of the pipeline.
3. **Registered OTF table found via datalake enumeration** (`DBC.DatalakeInfoV` + `HELP DATABASE`/
   `HELP TABLE`, queried by three-part name) — no `base_tableDDL`, but discoverable and schema-confirmed.
4. **Direct OTF read function** (`TD_ICEBERG_READ`/`TD_DELTA_READ`) — fallback only when no `DATALAKE`
   object is registered; validate schema/grain manually from a sample result set.

## Worked End-to-End Example — Subscription Churn

1. **EDW:** `StreamCo_db.Subscriber_Churn` (`SubscriberID`, entity grain) — anchor, label column `Churn`.
2. **NOS:** `nos_stream_usage` (`SubscriberID`, entity grain) — full metadata tool support, discovered via
   the scoped `DBC.TablesV` query/`base_tableDDL`, joined directly by name.
3. **OTF:** `stream_support_tickets` (`SubscriberID`, `ticket_date`, `category`, `resolved_flag` — event
   grain) — the scoped `DBC.TablesV` query does **not** return this table because it is registered in an
   external Iceberg catalog, not `DBC`. Find it by enumerating `DBC.DatalakeInfoV`, then running
   `HELP DATABASE <datalake>.<namespace>` and matching `stream_support_tickets` against the "support
   ticket" concept-expansion list — not by assuming the empty `DBC.TablesV` result means no such source
   exists. Once located, query it by three-part name, aggregate to `SubscriberID` grain (ticket count,
   unresolved count, days since last ticket) before joining to the anchor.

## See Also

- [database-and-table-discovery.md](./database-and-table-discovery.md) — the Phase 3–5 EDW discovery and
  the keyword-filtered `DBC.TablesV` scan that surfaces NOS foreign tables.
- [join-key-reconciliation.md](./join-key-reconciliation.md) — key-type casting and entity-vs-event-grain
  aggregation that apply once a hybrid source is read into the join graph.
- [materialization-and-validation.md](./materialization-and-validation.md) — the Phase 9 CTAS and Phase 10
  structural validation this hybrid staging feeds into.
- [teradata-sql-basics.md](./teradata-sql-basics.md) — the Teradata SQL dialect gotchas that apply to
  every discovery `SELECT` and the staging CTAS here.
