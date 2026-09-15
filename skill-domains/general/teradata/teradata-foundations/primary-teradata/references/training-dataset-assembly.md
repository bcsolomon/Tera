# Training Dataset Assembly from Hybrid Sources — Workflow Reference

> Governs the end-to-end protocol for building raw training datasets from EDW tables, NOS foreign tables, and OTF datalake sources. This reference defines discovery, validation, materialization, and boundary rules.

---

## Scope and Boundaries

**In scope:** Discover candidate tables, validate join keys, assemble and materialize a raw training dataset with structural validation.

**Out of scope — defer to downstream data preparation:**
- Statistical profiling (column distributions, null analysis beyond row counts)
- Data cleaning (imputation, outlier removal)
- Feature encoding (one-hot, ordinal, target encoding)
- Pivoting, sessionization, or any reshaping transformation
- Resampling, oversampling (SMOTE), or class rebalancing
- Model training, scoring, or evaluation

When the user requests any out-of-scope operation, complete the in-scope assembly first, then explicitly state that the requested operation belongs to downstream data preparation and name it as the next step.

---

## Confirm-Before-Building Gates

**CRITICAL:** The following conditions require the agent to STOP and ask the user for confirmation BEFORE materializing any table. Do not proceed silently.

### Trigger 1 — Missing or Ambiguous Label
The target/label column is not present in the schema and no derivation rule was provided. Ask the user for a label rule or an external label source. Do NOT invent a threshold, proxy, or synthetic label.

### Trigger 2 — Grain Ambiguity
The user's request is ambiguous about entity grain (e.g., "one row each" could mean one row per policy or one row per claim). Characterize both options from the schema, explain the modeling impact, and ask for confirmation.

### Trigger 3 — Vague or Open-Ended Request
No specific tables are named and the goal is broad (e.g., "find useful data for demand forecasting"). Discover candidates, present them ranked with rationale, and ask the user to confirm the source set before building.

### Trigger 4 — Wrong Join Key
The user-specified join key cannot connect the tables (e.g., order_id exists only on orders but not on customer_master). Halt, explain the problem, recommend the correct key or ask for confirmation. Do NOT fabricate a key.

### Trigger 5 — Missing Bridge Table
Tables have no direct shared key (e.g., Customer has cust_id but Transactions has acct_nbr). Surface the missing bridge (e.g., an Accounts table mapping acct_nbr to cust_id), offer to discover it, or ask the user to supply it. Do NOT synthesize a join via MOD, hash, ROW_NUMBER, or modulo arithmetic.

### Trigger 6 — Named Source Does Not Exist
The user-named database or table does not exist. Report the miss, surface ranked real alternatives, and ask the user to confirm before proceeding. Do NOT fabricate tables, columns, or data.

---

## Destructive SQL Guardrails

**NEVER execute destructive SQL statements:**
- No `DROP TABLE`, `DROP DATABASE`
- No `DELETE FROM`, `TRUNCATE TABLE`
- No `REPLACE TABLE` that overwrites existing data
- No `base_dropTable` or equivalent

**When asked to "rebuild", "drop and rebuild", or "overwrite":**
1. Refuse the destructive operation
2. Explain the guardrail (this skill only runs CREATE TABLE AS plus read-only SELECTs)
3. Offer alternatives:
   - Materialize under a fresh `TDH_`-prefixed name (e.g., `TDH_churn_training_v2`)
   - Let the user perform the DROP themselves first
4. Pause for the user's choice

**When an existing target table is detected:**
- Do NOT silently overwrite or DELETE ALL + INSERT
- Propose a non-destructive path and explain the risk

---

## Security and Access Gates

### Phase 4.5 — Privilege Check (before accessing any table)

```sql
-- Check SELECT rights on a candidate table
SELECT AccessRight, TableName, DatabaseName
FROM DBC.AllRightsV
WHERE DatabaseName = '<db>' AND TableName = '<table>'
  AND UserName = USER AND AccessRight = 'R ';

-- Alternative: check via UserRightsV
SELECT * FROM DBC.UserRightsV
WHERE DatabaseName = '<db>' AND TableName = '<table>';
```

**When access is denied (Error 3523):**
- If the restricted source is **optional enrichment**: drop it from consideration, explain the exclusion, assemble from accessible sources
- If the restricted source is the **required core feature group**: STOP, report that access must be provisioned, name the exact object and the `GRANT SELECT` needed, refuse to substitute or fabricate, materialize nothing

**NEVER self-grant access:**
- No `GRANT SELECT` statements
- No `CREATE AUTHORIZATION` for restricted objects
- Direct the user to request the grant from a DBA or security admin

---

## Discovery Protocol

### Phase 3 — Database Discovery
```sql
-- List available databases
SELECT DatabaseName FROM DBC.DatabasesV ORDER BY DatabaseName;
```

### Phase 4 — Table Discovery (EDW)
```sql
-- List tables in a database
-- Use base_tableList(database_name='<db>')
-- Then base_tableDDL(database_name='<db>', table_name='<table>') for each candidate
```

### Phase 5 — NOS/Foreign Table Discovery
Scan by table name patterns (never filter on `TableKind` — real foreign tables may report `TableKind='T'`):
```sql
SELECT DatabaseName, TableName, TableKind
FROM DBC.TablesV
WHERE TableName LIKE '%bureau%' OR TableName LIKE '%credit%'
   OR TableName LIKE '%nos_%' OR TableName LIKE '%external%';
```

Confirm NOS provenance by reading the DDL:
```sql
SHOW TABLE <db>.<foreign_table>;
-- Look for: CREATE FOREIGN TABLE ... LOCATION ... STOREDAS PARQUET
```

### Phase 6 — OTF/Datalake Discovery
```sql
-- List registered datalakes
SELECT DatalakeName, CatalogType, StorageLocation, TableFormat
FROM DBC.DatalakeInfoV;

-- Browse a specific datalake (non-SELECT — use base_executeSQL)
HELP DATALAKE <datalake_name>;
HELP DATABASE <datalake_name>.<database_name>;
HELP TABLE <datalake_name>.<database_name>.<table_name>;

-- Read OTF table data using three-part name
SELECT * FROM <datalake_name>.<database_name>.<table_name> SAMPLE 100;
```

**Error 6938 (missing authorization):** Record the datalake as unreachable, continue browsing others. Do NOT self-grant an authorization.

### Shortcut: When user names specific tables
If the user provides exact table names, skip Phases 3-5 and enter at the appropriate phase (Phase 6 for DDL inspection, Phase 7 for key reconciliation).

---

## Join Key Reconciliation

### Phase 7 — Key Inspection
1. Read DDL of both tables to identify the join column(s)
2. Validate data types match — if mismatched:
   - Apply explicit `CAST()` (e.g., `CAST(c.cust_id AS INTEGER)`)
   - Document the cast transparently
3. For composite keys, join on ALL key columns (ship_id + order_id) — never partial-key joins

### Phase 8.5 — Join Overlap Check (MANDATORY before materialization)
```sql
-- Validate join overlap BEFORE creating the table
SELECT
  COUNT(DISTINCT a.join_key) AS left_keys,
  COUNT(DISTINCT b.join_key) AS right_keys,
  COUNT(DISTINCT CASE WHEN b.join_key IS NOT NULL THEN a.join_key END) AS matched_keys
FROM left_table a
LEFT JOIN right_table b ON a.join_key = b.join_key;
```

Report the match rate. If zero overlap, STOP and surface the issue.

---

## Grain Management

### Event-to-Entity Aggregation
When joining event-grain tables (orders, transactions, shipments, clickstream) to entity-grain tables (customers), ALWAYS aggregate the event table to entity grain first:

```sql
-- Aggregate orders to customer grain
CREATE TABLE agentic_demo.orders_agg AS (
    SELECT cust_id,
           COUNT(*) AS order_count,
           SUM(amount) AS total_spend,
           MAX(order_date) AS last_order_date
    FROM orders
    GROUP BY cust_id
) WITH DATA PRIMARY INDEX (cust_id);
```

**Never join event-grain directly** — this causes row fan-out (e.g., 542 rows per customer instead of 1).

### Large Fact Table Bounding
For tables exceeding ~1M rows, use `SAMPLE` or `TOP` to bound the fact before joining:
```sql
SELECT * FROM large_fact_table SAMPLE 500000;
```

---

## Materialization Rules

### Required Elements
```sql
CREATE MULTISET TABLE <db>.<table_name> AS (
    SELECT ...
    FROM ...
    JOIN ...
) WITH DATA
PRIMARY INDEX (<grain_key>);

-- Immediately after CTAS:
COLLECT STATISTICS ON <db>.<table_name> COLUMN (<grain_key>);
COLLECT STATISTICS ON <db>.<table_name> COLUMN (<label_column>);
```

**PRIMARY INDEX:** Must be grain-aligned (the entity key, e.g., `cust_id`). For composite keys, use all components.

**COLLECT STATISTICS:** Required on the primary index columns and the label/target column.

### Structural Validation (post-materialization)
Run ONLY basic structural checks:
```sql
-- Row count
SELECT COUNT(*) FROM <table>;

-- Column count and types
HELP TABLE <table>;

-- Sample rows
SELECT TOP 5 * FROM <table>;
```

Do NOT run statistical profiling, distribution analysis, or data quality scoring.

### Tool Routing
- **Read-only SELECTs** → `base_readQuery`
- **DDL (CTAS, COLLECT STATS), HELP commands** → `base_executeSQL`
- If `base_readQuery` rejects a non-SELECT with `TD_TOOL_EXECUTION_ERROR`, recover by re-issuing through `base_executeSQL`

---

## Handoff Protocol

After materialization and structural validation, provide:

1. **Table location**: database.table_name
2. **Grain**: entity and key column(s)
3. **Label/target**: column name and type (if identified)
4. **Row count and column count**
5. **Next step**: "Invoke downstream data preparation for profiling, cleaning, and feature engineering"
6. **Do NOT** train a model, run a train/test split, or perform any ML operation
