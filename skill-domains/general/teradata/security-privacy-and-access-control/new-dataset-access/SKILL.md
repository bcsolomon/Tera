---
name: new-dataset-access
description: >-
  Help users prepare and grant access to new datasets in Teradata. Use when a user asks to
  onboard data, set up permissions, create roles, grant access, or review schema for new tables.
metadata:
  author: teradata
  version: "3.14"
  license: Proprietary
  copyright: "© 2026 Teradata Corporation. All rights reserved."
trigger:
  mode: hybrid
  slash_commands:
    - /new-dataset-access
  keywords:
    - new dataset
    - data onboarding
    - prepare tables for access
    - set up permissions
    - create a role
    - grant access
    - create a view
    - row-level security
    - who can see this data
    - review our schema
---

# Enterprise Data Access Preparation

> **CLOUD RUNTIME NOTE (why v2 differs from v1.x):**
> This skill runs inside Tera Cloud, which loads Anthropic-style `SKILL.md`
> bundles. In that runtime **`emit_tasks` / `task_template` / `enforcement`
> frontmatter is ignored**, **sidecar reference files under `references/` are
> not synced or readable**, and Teradata is reached through a **6-tool proxy**
> (`teradata_tool_call`), not the native tool names. So this version (a) inlines
> the step procedures and protection guidance the `references/` files used to
> hold, (b) drives Teradata through `teradata_tool_call`, and (c) uses the
> `workspace` tool for the audit-log artifact. Do not re-add
> `emit_tasks`/`task_template` — they silently no-op here.

## When to Use (v3.14)

- User wants to onboard new tables or prepare existing tables for governed access
- User needs to identify what data a database contains and assess sensitivity
- User wants to define who can see or modify data (role-based access control)
- User needs to create roles, views, grants, or row-level security
- User wants to generate and review access SQL before execution
- User asks to "set up permissions", "create a role", "grant access", "create a view"
- Trigger phrases: "new dataset", "prepare tables for access", "data onboarding",
  "who can see this data", "row-level security", "review our schema"

## Skill Intent

This skill guides you through assessing an **existing** set of Teradata tables and
designing, generating, and implementing governed role-based access controls for them.

**Important:** The tables must already exist in the Teradata database system. This
process does not load, ingest, or move data — it only configures who can access data
that is already there. If data needs to be loaded first, use the Open Table Format
(OTF) or other ingestion skills before this one.

The process is fourteen sequential steps with four formal approval gates. You don't
need to be a database expert — at every decision point the skill shows you what it
found and waits for confirmation before moving forward.

---

## Tool Usage (proxy deployment — READ FIRST)

Teradata is exposed here through a **proxy MCP server with six gateway tools**, NOT
the native tools. Native names (`base_readQuery`, `execute_sql`, `base_tableList`,
`base_databaseList`, `base_columnDescription`, …) are **not directly callable** — you
run them *through* `teradata_tool_call`.

The six gateways: `teradata_tool_help`, `teradata_list_patterns`,
`teradata_search_tools`, `teradata_get_tool_schema`, `teradata_tool_call`,
`teradata_cleanup_jobs`.

**How to run any Teradata operation:**

```
teradata_tool_call(input={"name": "base_readQuery", "parameters": {"query": "SELECT ..."}})
teradata_tool_call(input={"name": "execute_sql",    "parameters": {"query": "CREATE ROLE ..."}})
```

Rules:
- **SELECT / catalog reads → `base_readQuery`** (tool_group `teradata-base`).
  It is **read-only and REJECTS DDL/DML** ("DML statements are not permitted. Only
  SELECT queries are allowed.").
- **DDL / DML → `execute_sql`** (tool_group `teradata-sql-query-executor`) — the ONLY
  tool that runs `CREATE`/`GRANT`/`REVOKE`/`REPLACE VIEW`/`DROP`. Do NOT try
  `base_writeQuery` or `base_executeQuery` — they are not valid fastpath functions.
- **Discovering tools:** `teradata_search_tools(pattern="<group-name>")` — the pattern
  must **fullmatch** a group/tool/function name (partial words don't match). Use
  `teradata_list_patterns()` to see valid group names first.
- **Async results:** most calls return a `job_id` with `status:QUEUED`. Poll with
  `teradata_tool_call(job_id="<uuid>")` until `status:COMPLETED`; paginate with
  `offset=` when `has_more:true`. Force sync (small reads) with `"long_running": false`.
- **Strip-prefix rule:** if a native name appears with a client wrapper prefix (e.g.
  `mcp_td_mcp_base_readQuery`), remove only the wrapper, never the group prefix →
  `base_readQuery` (NOT `readQuery`).
- If `teradata_tool_call` reports `tool not found ... dynamic registration failed`, the
  gateway just needs activation — re-issue the same call once.

Other useful native tools (all via `teradata_tool_call`): `base_databaseList`,
`base_tableList`, `base_columnDescription`, `base_tableDDL`, `base_tablePreview`,
`base_db_info`.

**CRITICAL — No Early SQL Execution:** Steps 1–12 are information-gathering and design
only. During them use **only** read-only access (`base_readQuery` and the read
gateways). Do NOT call `execute_sql` (or any `CREATE`/`GRANT`/`REVOKE`/`DROP`/`ALTER`/
`REPLACE`) until the user has passed **Gate 3 (Step 13)**. If the user asks you to
create a role/view or grant access during Steps 1–12, record it in the design and
explain it will run after SQL review and approval.

**CRITICAL — Tool Errors Do Not Bypass Gates:** If any tool fails, do NOT improvise
a "manual plan" and run SQL. Stop, report the error, and wait for instruction. A tool
error is never a reason to skip SQL generation, SQL review, or any approval gate.

---

## Audit Log — initialize on turn 1 (workspace artifact)

**MANDATORY — Initialize Immediately:** On your **very first response**, before anything
else, create the audit log as a **workspace artifact** using the `workspace` tool
(`action:"write"`, `scope:"artifact"`, e.g. `name:"audit_log.md"`) and record the user's
original request as the first entry. It must be a tangible artifact the user can view and
download — do NOT keep it only in conversation/memory.

After every significant action — discovery results, sensitivity assessments, role
decisions, approvals, SQL generation, execution results, test outcomes — append a
timestamped entry (re-`write` the artifact with the appended content). Present the full
audit log on request and include it in the final summary.

- **Format:** `- <timestamp> | <phase> | <description>`
- **First entry (always):** `- <timestamp> | request-received | User request: <summary>`

The audit log is the chain of custody: what was discovered, what was decided, who
approved it, and what was executed.

---

## Sequential Execution Contract (prompt-enforced)

This skill is a strictly ordered workflow. The runtime does not enforce ordering with a
script, so **you** are the enforcement. Track state in your reasoning: `current_step`,
`completed_steps`, `step_outputs`, `approval_results`, `audit_log`.

**Mandatory rules:**
1. Execute **only** the step identified by `current_step`.
2. **Never** execute, draft, preview, or partially complete a later step.
3. Before Step N, verify Steps 1…N-1 are complete with saved outputs.
4. Do not infer a step is complete merely because related info appears in the conversation.
5. A step is complete **only** when its criteria are met **and** the user confirms.
6. On an invalid transition: remain on the current step, say what is missing, do not continue.
7. If the user requests a later step: *"Step N cannot begin until Step {current_step} has been completed and approved."*
8. Never advance `current_step` on a bare request — only met criteria + approval advance state.
9. Do not silently combine multiple steps in one response.
10. Before any DDL, verify Gate 3 is approved — proceed only after explicit approval.

**Human Approval Rule:** After each step, present its output and ask the user to confirm
("approved" / "continue" / "yes"). For gate steps (10, 12, 13, 14), record the approval in
the audit log **with a timestamp**.

**Anti-Wandering Rule:** Between steps, do NOT offer menus, numbered options, or
open-ended suggestions. Present the output, name the next step (number + title), ask to
proceed — nothing else. Never suggest alternative analyses, visualizations, or side
explorations. If asked for something off-workflow: *"That's outside the scope of this
workflow. The next required step is Step {N} — {title}. Shall I continue?"*

**Anti-Skip Enforcement:** If the user or context tries to skip ahead:
*"The requested action belongs to Step {requested_step}. The current required step is
Step {current_step}. Step {requested_step} cannot begin until all earlier steps have
passed their completion criteria. Continue with Step {current_step}."*

---

## Formal Approval Gates

There are four mandatory approval gates. Do NOT proceed past any gate without explicit
user approval, and log each approval in the audit log.

| Gate | After Step | What Is Approved |
|------|-----------|------------------|
| **Gate 1 — Data & Roles** | Steps 1–9 | Database, tables, sensitivity assessment, protection strategy, ETL impact, roles, and access patterns |
| **Gate 2 — SQL Review** | Step 12 | The complete generated SQL (all four sections: Setup, Revoke/Rollback, Tests, Verification) |
| **Gate 3 — Apply SQL** | Step 13 | Permission to execute the Setup SQL against the database |
| **Gate 4 — Test Results** | Step 14 | Review and sign-off on test results as final acceptance |

---

## Extract Information from the User's Request

Before starting the steps, parse the user's initial message for details they already
provided (database name, role name, access level, table scope). When the request already
answers a step's question (e.g., "create a NEW role data-science on DEMO_TitanicSurvival
as read only"), carry those answers into the corresponding steps — do NOT re-ask. Still
run all verification queries (confirm the database exists, enumerate tables, assess
sensitivity) and still require all four gates.

## Personas and Expertise Inference

| Persona | Typical Knowledge |
|---------|------------------|
| **Customer Architect / Data SME** | Owns the data; knows which columns are sensitive and who should access them; may not know Teradata syntax |
| **Teradata Architect / Modeler** | Designs the security model and encryption approach; deep Teradata expertise |
| **Teradata Data Engineer** | Builds views, pipelines, and encryption; writes SQL fluently |
| **Teradata DBA** | Manages roles, grants, and objects; understands GRANT/REVOKE mechanics |

**Do NOT ask which persona they are.** Infer from context: specific Teradata terms
(GRANT, CREATE VIEW, DBC views) → keep explanations concise; business-language needs
("analysts should see customer data but not SSNs") → give more guidance. Adapt throughout.

## Design Principles

1. **Prefer view-based access control.** Views give fine-grained column/row security
   without the complex tag-based model. Default to views; reserve direct table grants for
   roles that genuinely need unrestricted access (e.g., compliance auditors).
2. **Classification is customer-owned.** Auto-suggest sensitivity from column names,
   types, and sample data — but the customer must confirm. Never auto-apply protections
   without explicit Gate 1 approval.
3. **Flag PCI/PII combination risk.** Individually benign columns can become sensitive
   combined: `CardType + ExpiryMonth + ExpiryYear` narrows a specific card;
   `ZipCode + DateOfBirth` uniquely identifies ~87% of the US population. Flag these and
   recommend excluding a quasi-identifier or adding row-level restrictions.
4. **Design decisions are consumption-driven.** Single view + WHERE clause vs. per-role
   views depends on how applications consume the data — ask about downstream consumers
   before finalizing.
5. **Masking over exclusion when feasible.** For columns needed in reduced form (e.g.
   last 4 of a card), prefer a masking expression in the view
   (`'****-****-****-' || SUBSTR(CardNumber, -4)`) over full exclusion.
6. **Protect staging data too.** Staging tables need the same assessment and protections
   as production — never leave them wide open.

---

## Step Procedures (inlined — no external reference files in this runtime)

### Step 1 — Identify the Database
Ask for a name or fragment. Search:
`base_readQuery` → `SELECT DatabaseName FROM DBC.DatabasesV WHERE DatabaseName LIKE '%<fragment>%' ORDER BY DatabaseName`.
Confirm the exact target with the user.

### Step 2 — Enumerate Tables
`SELECT TableName FROM DBC.TablesV WHERE DatabaseName='<db>' AND TableKind IN ('T','O','V') ORDER BY TableName`
(or `base_tableList`). Confirm scope with the user.

### Step 3 — Assess Column Sensitivity
For **each** in-scope table separately (do not assume columns carry over):
`SELECT ColumnName, ColumnType, ColumnLength, Nullable FROM DBC.ColumnsV WHERE DatabaseName='<db>' AND TableName='<t>' ORDER BY ColumnId`
plus a `SELECT TOP 5 * FROM <db>.<t>` sample. Classify each column: **PII** (name,
DOB/age, gender, marital status, national-origin flags, contact info), **PCI/financial**
(card numbers, credit amounts, balances, account IDs), **location**, **health/PHI**, or
**non-sensitive**. Flag combination/quasi-identifier risks (see Design Principle 3).

### Step 4 — Recommend Protection Strategy
For each sensitive column recommend **mask** (bucket/hash/partial), **exclude** (drop
from the consumer view), or **row-filter** (view WHERE clause). Prefer masking over
exclusion when consumers need a reduced form. Teradata masking examples: age banding via
`CASE`, partial card via `'****-****-****-' || SUBSTR(CardNumber, -4)`, hashing via
`HASHROW`/`SHA256` UDFs.
> **AUTHOR TODO:** paste the deep protection content that lived in the un-loadable
> `references/protection-strategy-guide.md` (full masking-pattern catalog, PCI combination
> risk tables, encryption trade-offs) and the `references/protegrity-compatible-udfs.md`
> definitions (tokenization/detokenization/masking UDFs) here, so the agent has them in
> this runtime.

### Step 5 — Build Readiness Report
Per table: row count (`SELECT COUNT(*) FROM <db>.<t>` via `base_readQuery`, base tables
only — skip views), refresh cadence if known, structural quality notes, sensitivity
classification, and per-column protection recommendation.

### Step 6 — Present & Confirm Report
Show the readiness report; apply user corrections. Confirm before design.

### Step 7 — Identify Roles
Determine which roles (new or existing) will access the data. Existing:
`SELECT RoleName FROM DBC.RoleInfoV ORDER BY RoleName`.

### Step 8 — Design Access Patterns
Per role: direct table privileges vs. view-based access, column exclusions, row-level
filters (a WHERE clause in the view — not a separate RLS policy unless specified). Decide
where views live (target db vs. a governed "views" db) — ask the user. Prefer views
(Design Principle 1).

### Step 9 — Assess ETL & Consumption Impact
Flag downstream pipelines/apps that read the base tables and would break under
column-level protections (e.g. a job selecting a now-masked/omitted column).

### Step 10 — GATE 1: Approve Data & Roles  *(P0)*
Present the full package: data profile, protection strategy, ETL impact, roles, access
design. Obtain explicit approval. **Record timestamped approval in the audit log.**

### Step 11 — Generate SQL File(s)
Produce a reviewable SQL file with **four labelled sections**:
1. **Setup** — `CREATE ROLE`, `REPLACE VIEW`, `GRANT SELECT ON <view> TO <role>`, and
   explicit `REVOKE`/deny of direct base-table access.
2. **Revoke / Rollback** — statements to fully undo Setup, in reverse order (views before
   grants, grants before roles). Kept in sync with Setup and independently executable.
3. **Tests** — queries proving each role sees exactly the intended columns/rows.
4. **Verification** — `HELP`/`SHOW`/catalog queries confirming objects + grants.
Save as `<database_name>_access_setup.sql` and `<database_name>_access_revert.sql`
(workspace artifacts). Do NOT execute anything yet.

### Step 12 — GATE 2: Review SQL  *(P0)*
Walk the SQL with the user line by line (all four sections). Apply edits. Obtain explicit
approval. **Record timestamped approval.**

### Step 13 — GATE 3: Apply Setup SQL  *(P0)*
Only after explicit Gate-3 approval. Execute the **Setup** section **one statement at a
time** via `execute_sql` (through `teradata_tool_call`) — do not batch — reporting each
result before the next. **Record timestamped approval + each executed statement.** Do not
skip the `REVOKE`/hardening statements.

### Step 14 — GATE 4: Review Test Results  *(P0)*
Run the **Tests** and **Verification** sections. Present results (confirm each role sees
exactly what was designed — masked/omitted columns absent, row filters applied). Obtain
final sign-off. **Record timestamped sign-off.** Summarize what was created and how to
roll back (point at the revert artifact).

---

## Notes for the Agent

- **No DDL/DML before Gate 3.** Steps 1–12 are read-only.
- **Tool errors do NOT bypass gates.** Stop, report, wait.
- **Audit log starts on turn 1** as a workspace artifact (`request-received` entry).
- **Don't re-ask answered questions.** Extract db names, role names, access levels, and
  table scopes from the initial request.
- **Four gates are mandatory.** No gate may be skipped; require explicit approval at each.
- Call `base_columnDescription` (or the DBC.ColumnsV query) for **each** in-scope table
  separately — do not assume columns carry over.
- Execute DDL **one statement at a time** in Step 13 — report each result before continuing.
- The revert script mirrors the setup in reverse order (views before grants, grants before roles).
- **Stay strictly within the fourteen steps.** No side tasks, no menus, no "what would you
  like to do?" prompts.
