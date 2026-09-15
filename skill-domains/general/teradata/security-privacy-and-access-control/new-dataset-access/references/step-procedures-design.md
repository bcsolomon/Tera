# Step Procedures: Design & Gate 1 (Steps 7–10)

> Source: Enterprise Data Access Onboarding Skill v3.0
> This reference contains the detailed execution procedures for Steps 7 through 10.
> Step 10 is Gate 1 — the first formal approval gate. Do not proceed past it without explicit user approval.

---

## Step 7 — Identify Roles

### Preconditions
- `current_step` equals `7`.
- Steps 1–6 in `completed_steps`.
- Readiness report confirmed.

### Actions

Ask the user:
> "How many roles will need access to this dataset? For each role, is it an existing role or a new one you want to create?"

Collect the role count and for each role:

**If new:** Ask the user to provide the role name. Record it as a new role to be created.

**If existing:** Ask for the name or partial name of the role, then run:
```sql
SELECT RoleName FROM DBC.RoleInfo WHERE RoleName LIKE '%<user_input>%' (NOT CASESPECIFIC)
```
via `base_readQuery`. Present matching role names and ask the user to confirm which one(s) to use. If no matches, ask the user to try a different search term.

After all roles are identified, display a summary list:

| Role | Status | Name |
|---|---|---|
| Role 1 | New / Existing | `role_name` |

Ask the user to confirm before proceeding.

### Required Output
```json
{"roles": [{"name": "role_name", "status": "new|existing"}]}
```

### Completion Criteria
Step 7 passes only when:
- All roles are identified (new or existing) and confirmed by the user.

### On Failure
Remain on Step 7. Clarify missing roles.

### On Success
Record in the audit log and advance to the next step:
- Log: `<timestamp> | roles | Roles confirmed: <list>`
- Step output: `{"roles": [...]}`

---

## Step 8 — Define Access Patterns

### Preconditions
- `current_step` equals `8`.
- Steps 1–7 in `completed_steps`.
- `step_outputs.7.roles` exists.

### Actions

For each confirmed role, work through the following questions one role at a time.

**7a — Direct Table Access**

Ask:
> "Should `<role_name>` have direct access to the base tables? If yes, which operations — SELECT, INSERT, UPDATE, DELETE?"

Record the privileges per table for this role (may be all tables or a subset).

**7b — View-Based Access**

Ask:
> "Should `<role_name>` access the data through views rather than (or in addition to) the base tables?"

If yes, continue with 7c and 7d. If no, move to the next role.

**7c — Column Exclusions**

Display the full column list for each relevant table. Ask:
> "Are there any columns that should be **excluded** from the view for `<role_name>`? List any columns to hide, or say 'none' to include everything."

Record the approved column list (all columns minus exclusions) for each table.

**7d — Row-Level Filtering**

Ask:
> "Should `<role_name>` be restricted to certain rows? For example, filtering by region, department, or some other column value?"

If yes, ask the user to describe the filter logic (e.g., `WHERE region = 'WEST'` or a dynamic expression). Record the WHERE clause for inclusion in the view definition.

**7e — View Scope**

Ask:
> "Should `<role_name>` have its own dedicated view, or share a view with another role?"

Record whether a new view is needed or an existing view definition covers this role.

Repeat Steps 7a–7e for every role. Keep a running design table:

| Role | Table Access | Privileges | View Name | Excluded Columns | Row Filter |
|---|---|---|---|---|---|
| `role_name` | Yes/No | SELECT/INSERT/… | `view_name` or shared | col list or none | WHERE clause or none |

### Required Output
```json
{"access_patterns": [{"role": "...", "table_access": true, "privileges": [...], "view_name": "...", "excluded_columns": [...], "row_filter": "..."}]}
```

### Completion Criteria
Step 8 passes only when:
- Access patterns are defined for every role from Step 7.
- The user has confirmed the design table.

### On Failure
Remain on Step 8. Complete missing role definitions.

### On Success
Record in the audit log and advance to the next step:
- Log: `<timestamp> | access-design | Access patterns defined for <N> roles`
- Step output: `{"access_patterns": [...]}`

---

## Step 9 — Assess ETL & Consumption Impact

### Preconditions
- `current_step` equals `9`.
- Steps 1–8 in `completed_steps`.
- `step_outputs.8.access_patterns` exists.

### Actions

Before finalizing the design, assess whether the proposed column exclusions, masking, or row-level filters will break downstream consumers.

Ask the user:
> "Are there any downstream ETL pipelines, reports, dashboards, or applications that currently read from these tables? If so, which columns and tables do they depend on?"

Based on the user's response, check for these common impact scenarios:

| Scenario | Risk | Mitigation |
|---|---|---|
| ETL pipeline JOINs on a column being excluded | Broken pipeline — JOIN key missing from view | Keep the column in the view or create a separate ETL-specific view without exclusions |
| Aggregation pipeline uses a masked column | Incorrect results — masked values won't aggregate properly | Provide an unmasked view for the ETL role with appropriate access controls |
| Row-level filter excludes rows needed by a downstream report | Missing data in reports | Verify the filter scope with the report owner; consider a broader filter or separate view |
| Application hardcodes column names from the base table | Application breaks when pointed to the view | Document the column mapping; views should use the same column names as the base table where possible |

If the user identifies impacted consumers, record each one and flag it in the design:

`- <timestamp> | etl-impact | ETL impact assessment: <N> downstream consumers identified, <M> require mitigation`

If no downstream consumers are identified, log:
`- <timestamp> | etl-impact | No downstream ETL/consumption dependencies identified`

### Required Output
```json
{"etl_assessment": {"consumers_identified": 0, "mitigations_needed": 0}}
```

### Completion Criteria
Step 9 passes only when:
- The user has been asked about downstream consumers.
- Any identified impacts are documented with mitigations.

### On Failure
Remain on Step 9. Gather more details about impacted consumers.

### On Success
Record in the audit log and advance to the next step:
- Log: `<timestamp> | etl-impact | ETL impact assessed: <N> consumers, <M> mitigations`
- Step output: `{"etl_assessment": {...}}`

---

## Step 10 — ⛔ GATE 1: Approve Data & Roles

### Preconditions
- `current_step` equals `10`.
- Steps 1–9 in `completed_steps`.
- All step outputs from 1–9 are available.

### Actions

Produce a structured summary of everything decided so far:

---

### Access Design Summary

**Database:** `<database_name>`

#### Data Profile
- Tables in scope, row counts, sensitive fields identified
- Protection strategy recommendations from Step 4
- Refer back to the readiness report from Step 5
- ETL & consumption impact assessment from Step 9

#### Roles

| Role | Status | Direct Table Privileges | View Name | Excluded Columns | Row Filter |
|---|---|---|---|---|---|
| `role_name` | New/Existing | SELECT, … | `view_name` | `col1`, `col2` / none | `WHERE …` / none |

#### View Definitions (preview)

For each view to be created, show the draft SQL:

```sql
CREATE VIEW <view_db>.<view_name> AS
  SELECT <approved_column_list>
  FROM <database>.<table>
  [WHERE <row_filter>];
```

---

Present the summary and ask:
> \"This is **Approval Gate 1 — Data & Roles**. Please review the data profile, sensitivity assessment, protection strategy, ETL impact, roles, and access patterns above. Do you approve this design? Reply 'approved' to proceed to SQL generation, or describe any changes needed.\"

**Do NOT proceed until the user explicitly says 'approved' or equivalent.** Apply corrections and re-present if needed.

Log the approval:
`- <timestamp> | GATE-1-APPROVED | User approved data profile and access design for <database_name>: <N> tables, <M> sensitive fields, <P> roles, <Q> views`

### Required Output
```json
{"gate_1_approved": true}
```

### Completion Criteria
Step 10 passes only when:
- The user has explicitly said "approved" or equivalent.
- Gate 1 approval has been recorded in the audit log.

### On Failure
Remain on Step 10. Apply corrections and re-present for approval.

### On Success
Record gate approval in the audit log and advance to the next step:
- Log: `<timestamp> | GATE-1-APPROVED | User approved data profile and access design`
- Step output: `{"gate_1_approved": true}`

---
