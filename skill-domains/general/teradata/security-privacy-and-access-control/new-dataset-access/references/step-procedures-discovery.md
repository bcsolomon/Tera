# Step Procedures: Discovery & Reporting (Steps 1–6)

> Source: Enterprise Data Access Onboarding Skill v3.0
> This reference contains the detailed execution procedures for Steps 1 through 6.
> Each step must be executed sequentially per the Sequential Execution Contract in SKILL.md.

---

## Step 1 — Identify the Database

### Preconditions
- `current_step` must equal `1`.

### Actions

Ask the user:
> "What is the name (or partial name) of the database you want to onboard? For example, entering `sales` will match `sales_dw`, `retail_sales`, etc."

Once the user provides input, use `base_databaseList` to retrieve all databases, then filter the results client-side to those whose names contain the user-supplied string (case-insensitive). Present only the matching databases.

If there are no matches, tell the user and ask them to try a different search term.

If there are multiple matches, list them and ask the user to confirm which one (or ones) are the target database(s).

Wait for the user to confirm the exact database name(s) before proceeding.

### Required Output
```json
{"database_name": "<confirmed_database>"}
```

### Completion Criteria
Step 1 passes only when:
- At least one database name is confirmed by the user.
- The database was verified to exist via `base_databaseList`.

### On Failure
Remain on Step 1 and ask the user for a different search term.

### On Success
Record in the audit log and advance to the next step:
- Log: `<timestamp> | discovery | Database confirmed: <name>`
- Step output: `{"database_name": "<name>"}`

---

## Step 2 — Enumerate Tables

### Preconditions
- `current_step` equals `2`.
- Step 1 in `completed_steps`.
- `step_outputs.1.database_name` exists.

### Actions

Ask the user:
> "What is the name (or partial name) of the tables you want to include? You can enter a fragment like `customer` to match any table with that word, or enter `*` to include all tables in the database."

Once the user provides input, use `base_tableList` with the confirmed database name to retrieve all tables and views, then filter the results client-side to those whose names contain the user-supplied string (case-insensitive). If the user entered `*`, include all tables.

Present the matching tables and views, noting table kind (base table vs. view). Ask the user:
> "Do these look right? Confirm to proceed with all of them, or let me know which ones to add or remove."

If there are no matches, tell the user and ask them to try a different search term.

Wait for confirmation of the final in-scope table list before proceeding.

### Required Output
```json
{"tables_in_scope": ["Table1", "Table2", ...]}
```

### Completion Criteria
Step 2 passes only when:
- At least one table is confirmed in scope.
- The user explicitly approved the table list.

### On Failure
Remain on Step 2 and request a different search term.

### On Success
Record in the audit log and advance to the next step:
- Log: `<timestamp> | enumeration | Tables confirmed: <list>`
- Step output: `{"tables_in_scope": [...]}`

---

## Step 3 — Examine Columns and Assess Sensitivity

### Preconditions
- `current_step` equals `3`.
- Steps 1–2 in `completed_steps`.
- `step_outputs.2.tables_in_scope` exists.

### Actions

For each in-scope table, call `base_columnDescription` to retrieve its column definitions.

As you collect the column data, classify each column for sensitivity using these guidelines:

| Sensitivity | Criteria |
|---|---|
| **Critical — PCI/PHI** | Credit card numbers, CVV, Social Security Numbers, health record identifiers. These must NEVER be exposed in views without masking or exclusion. CVV must never be stored or exposed in any form per PCI DSS. |
| **High — PII candidate** | Full names, email addresses, phone numbers, street addresses, account numbers; free-text fields (VARCHAR > 500) that may contain unstructured PII |
| **Medium — contextual risk** | Dates of birth, financial amounts (balances, credit limits, salaries), demographic data (age, gender), location data (geometry/UDT types, precise lat/lon coordinates) |
| **Low — combination risk only** | Zip codes, card types, expiry dates — individually low risk but become sensitive when combined (see Combination Risk below) |
| **No** | IDs, codes, status flags, timestamps, public reference data (county names, business names, aggregated metrics) |

Foreign keys and primary keys are **No** unless the key itself is a sensitive identifier.

### Combination Risk Assessment

After classifying individual columns, scan for **combination risks** — groups of columns that are individually low-risk but become sensitive when combined in a single view or query result:

| Combination | Risk | Recommendation |
|---|---|---|
| ZipCode + DateOfBirth (+ Gender) | Re-identification — can uniquely identify ~87% of the US population | Exclude at least one quasi-identifier from views, or apply row-level restriction |
| CardType + ExpiryMonth + ExpiryYear | Card narrowing — combined with transaction amounts, can significantly narrow identification of a specific card | Exclude expiry fields unless genuinely needed by the consumer |
| FirstName + LastName + City | Identity resolution — enough to identify most individuals | Treat as High when all three appear together |
| Account/Card ID + Amount + Timestamp | Transaction fingerprinting — can re-identify anonymized transactions | Consider aggregation instead of row-level access |

Flag any detected combinations in the sensitivity assessment table with a note like: `⚠️ Combination risk with <other_column>`.

Present the combination risks as a separate callout to the user:
> "**⚠️ Combination Risk Detected:** The following column groups become sensitive when exposed together in a view: [list combinations]. Consider excluding one column from each group or applying additional row-level restrictions."

### Required Output
```json
{"sensitivity_assessment": {"<table>": [{"column": "...", "sensitivity": "...", "combination_risk": "..."}]}}
```

### Completion Criteria
Step 3 passes only when:
- Every column in every in-scope table has a sensitivity classification.
- Combination risks have been flagged.
- The assessment has been presented to the user.

### On Failure
Remain on Step 3. Re-run `base_columnDescription` for any missing tables.

### On Success
Record in the audit log and advance to the next step:
- Log: `<timestamp> | sensitivity | Sensitivity assessed: <N> columns, <M> high/critical`
- Step output: `{"sensitivity_assessment": {...}}`

---

## Step 4 — Recommend Protection Strategy

### Preconditions
- `current_step` equals `4`.
- Steps 1–3 in `completed_steps`.
- `step_outputs.3.sensitivity_assessment` exists.

### Actions

For each column classified as Critical, High, or Medium sensitivity, recommend a protection approach:

| Protection | When to Use | Implementation |
|---|---|---|
| **Exclude from view** | Column is not needed by the consuming role | Omit from the SELECT list in the view definition |
| **Mask in view** | Consumer needs a reduced form (e.g., last 4 digits) | Use `SUBSTR`, string concatenation, or `HASHBUCKET` in the view SELECT |
| **Row-level filter** | Consumer should only see a subset of rows | Add a WHERE clause to the view definition |
| **Full access (auditor/compliance)** | Consumer has a legitimate need for unmasked PII | Direct table GRANT — document the justification |

Present the recommendations as a table:

| Table | Column | Sensitivity | Recommendation | Rationale |
|---|---|---|---|---|
| `Customer` | `SSN` | Critical | Exclude | No consumer needs full SSN in this workflow |
| `Credit_Card` | `CardNumber` | Critical | Mask (last 4) | Fraud investigators need partial card reference |
| `Customer` | `DateOfBirth` | Medium | Keep (flag combo risk) | Needed for analytics; flag ZipCode combination |

Ask the user:
> "Here is the recommended protection strategy for sensitive columns. Do you agree with these recommendations, or would you like to adjust any?"

Apply corrections and log:
`- <timestamp> | protection-strategy | Protection strategy presented: <N> columns protected (<X> excluded, <Y> masked, <Z> flagged)`

### Required Output
```json
{"protection_recommendations": [{"table": "...", "column": "...", "action": "exclude|mask|filter|full_access", "rationale": "..."}]}
```

### Completion Criteria
Step 4 passes only when:
- Every Critical/High/Medium column has a protection recommendation.
- The user has confirmed or corrected the recommendations.

### On Failure
Remain on Step 4. Apply user corrections and re-present.

### On Success
Record in the audit log and advance to the next step:
- Log: `<timestamp> | protection-strategy | Protection strategy confirmed`
- Step output: `{"protection_recommendations": [...]}`

---

## Step 5 — Build and Present the Readiness Report

### Preconditions
- `current_step` equals `5`.
- Steps 1–4 in `completed_steps`.
- `step_outputs.4.protection_recommendations` exists.

### Actions

Produce a structured report in the following format. Use the example below as the template — adjust content to match the actual dataset.

---

### Dataset Readiness Report

**Database:** `<database_name>` (base tables) + `<governed_view_db>` (governed views, TableKind V)

#### Table Inventory

| Table | Kind | Row Count | Description |
|---|---|---|---|
| `TableName` | Base table | *examine or note unknown* | Short functional description |
| `TableName` | View | — | Pre-existing governed views |

#### Column Inventory

For each table, produce a block like this:

**`TableName`**

| Column | Type | Sensitive? | Notes |
|---|---|---|---|
| `column_name` | TYPE | High / Medium / Low / No | Brief rationale |

#### Readiness Profile

- **Volume:** State row counts and whether the size is suitable for dev, staging, or production validation.
- **Refresh cadence:** Note whether timestamp/date columns suggest an append pattern, or if the dataset appears static.
- **Structural quality:** Note NULL constraints, missing keys, or anything that may affect data quality downstream.

#### Sensitive Field Candidates

List only the fields rated Medium or above, one bullet per field:

- `table.column` (TYPE) — **SEVERITY** — reason why it's sensitive and what risk it poses.

### Required Output
```json
{"readiness_report": "compiled"}
```

### Completion Criteria
Step 5 passes only when:
- Table Inventory, Column Inventory, Readiness Profile, and Sensitive Field Candidates sections are all present.

### On Failure
Remain on Step 5. Complete the missing report sections.

### On Success
Record in the audit log and advance to the next step:
- Log: `<timestamp> | readiness-report | Report compiled: <N> tables, <M> sensitive fields`
- Step output: `{"readiness_report": "compiled"}`

---

## Step 6 — Present Readiness Report

### Preconditions
- `current_step` equals `6`.
- Steps 1–5 in `completed_steps`.
- `step_outputs.5.readiness_report` exists.

### Actions

Present the full report to the user and ask:
> "Does this assessment look correct? Are there any tables, columns, sensitivity ratings, or protection recommendations you'd like to adjust before we proceed to role design?"

Apply any corrections the user requests. Log the readiness report:
`- <timestamp> | readiness-report | Readiness report presented for <database_name>: <N> tables, <M> sensitive fields identified`

### Required Output
```json
{"report_confirmed": true}
```

### Completion Criteria
Step 6 passes only when:
- The user has explicitly confirmed the readiness report (or corrections have been applied and re-confirmed).

### On Failure
Remain on Step 6. Apply corrections and re-present the report.

### On Success
Record in the audit log and advance to the next step:
- Log: `<timestamp> | readiness-confirmed | User confirmed readiness report`
- Step output: `{"report_confirmed": true}`

