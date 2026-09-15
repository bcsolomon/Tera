---
name: new-data-access
description: 'Guides an enterprise user through the full lifecycle of onboarding a new Teradata dataset — from discovery and sensitivity assessment through role design, SQL generation, and live implementation. Use when a user wants to onboard new tables, identify what data they contain, assess sensitivity, define who can see or modify the data, create roles and views, generate and review access SQL, or implement and test database permissions. Trigger on phrases like "new dataset", "prepare tables for access", "data onboarding", "who can see this data", "set up permissions", "create a role", "grant access", "create a view", "row-level security", or "review our schema".'
metadata:
  author: teradata
  version: "3.0"
  license: Proprietary
  copyright: "© 2026 Teradata Corporation. All rights reserved."
  enforcement: script-controlled
emit_tasks: true
task_template:
  max_tasks: 14
  root_title: "Enterprise Data Access Onboarding"
  ephemeral_on_deactivate: false
  steps:
    - title: "Step 1 — Identify the Database"
      objective: "Search by name or partial name, confirm the target database exists"
      category: discovery
      priority: P1
      estimated_effort: "5 min"
      depends_on: []
      tags: [discovery, database]
    - title: "Step 2 — Enumerate Tables"
      objective: "List and filter tables in the confirmed database to define scope"
      category: discovery
      priority: P1
      estimated_effort: "5 min"
      depends_on: [0]
      tags: [discovery, tables]
    - title: "Step 3 — Assess Column Sensitivity"
      objective: "Classify every column for PII, PCI, location data, and other risk tiers"
      category: analysis
      priority: P1
      estimated_effort: "15 min"
      depends_on: [1]
      tags: [sensitivity, classification]
    - title: "Step 4 — Recommend Protection Strategy"
      objective: "For each sensitive column, recommend masking, exclusion, or view-based filtering"
      category: analysis
      priority: P1
      estimated_effort: "10 min"
      depends_on: [2]
      tags: [protection, strategy]
    - title: "Step 5 — Build Readiness Report"
      objective: "Compile row counts, refresh cadence, quality, sensitivity, and protection recommendations"
      category: reporting
      priority: P1
      estimated_effort: "10 min"
      depends_on: [3]
      tags: [report, readiness]
    - title: "Step 6 — Present & Confirm Report"
      objective: "Review readiness report with the user and apply corrections"
      category: review
      priority: P1
      estimated_effort: "5 min"
      depends_on: [4]
      tags: [review, confirmation]
    - title: "Step 7 — Identify Roles"
      objective: "Determine which roles (new or existing) will access the data"
      category: design
      priority: P1
      estimated_effort: "5 min"
      depends_on: [5]
      tags: [roles, design]
    - title: "Step 8 — Design Access Patterns"
      objective: "For each role define table privileges, view-based access, column exclusions, row filters"
      category: design
      priority: P1
      estimated_effort: "10 min"
      depends_on: [6]
      tags: [access-patterns, design]
    - title: "Step 9 — Assess ETL & Consumption Impact"
      objective: "Flag downstream pipelines or applications affected by column-level protections"
      category: analysis
      priority: P2
      estimated_effort: "10 min"
      depends_on: [7]
      tags: [etl, impact]
    - title: "Step 10 — GATE 1: Approve Data & Roles"
      objective: "Formal user approval of data profile, protection strategy, ETL impact, roles, and access design"
      category: gate
      priority: P0
      estimated_effort: "5 min"
      depends_on: [8]
      tags: [gate, approval]
    - title: "Step 11 — Generate SQL File"
      objective: "Produce four-section SQL file: Setup, Revoke/Rollback, Tests, Verification"
      category: generation
      priority: P1
      estimated_effort: "10 min"
      depends_on: [9]
      tags: [sql, generation]
    - title: "Step 12 — GATE 2: Review SQL"
      objective: "Line-by-line SQL review with the user before execution"
      category: gate
      priority: P0
      estimated_effort: "10 min"
      depends_on: [10]
      tags: [gate, sql-review]
    - title: "Step 13 — GATE 3: Apply SQL"
      objective: "Execute Setup SQL one statement at a time after explicit permission"
      category: gate
      priority: P0
      estimated_effort: "10 min"
      depends_on: [11]
      tags: [gate, execution]
    - title: "Step 14 — GATE 4: Review Test Results"
      objective: "Run all tests, present results, obtain final sign-off"
      category: gate
      priority: P0
      estimated_effort: "10 min"
      depends_on: [12]
      tags: [gate, testing, sign-off]
---

# Enterprise Data Access Preparation

## When to Use

- Version 2.3146
- User wants to onboard new tables or prepare existing tables for governed access
- User needs to identify what data a database contains and assess sensitivity
- User wants to define who can see or modify data (role-based access control)
- User needs to create roles, views, grants, or row-level security
- User wants to generate and review access SQL before execution
- User asks to "set up permissions", "create a role", "grant access", "create a view"
- Trigger phrases: "new dataset", "prepare tables for access", "data onboarding", "who can see this data", "row-level security", "review our schema"

## Tool Usage

- Use `base_readQuery` (teradata-base group) for all SELECT queries: catalog lookups, row counts, role searches, test queries, and verification
- Use `execute_sql` (teradata-sql-query-executor group) for DDL/DML — **ONLY in Step 13 after Gate 3 approval**: CREATE ROLE, GRANT, REVOKE, CREATE VIEW, DROP VIEW, DROP ROLE
- The `task_board` is auto-emitted by the skill's declarative `task_template` (see frontmatter). 14 tasks with sequential dependencies are created automatically when the skill activates — do NOT create them manually. Use `task_board` `update` to mark tasks in-progress/completed, `task_board` `list` to show board status, and `task_board` `show` to inspect a task.
- Other useful teradata-base tools: `base_databaseList`, `base_tableList`, `base_columnDescription`, `base_tableDDL`, `base_tablePreview`, `base_db_info`
- `teradata_tool_help` — Get general help and orientation on available tools
- `teradata_list_patterns` — List available tool groups/patterns
- `teradata_search_tools` — Search and discover tools by pattern
- `teradata_get_tool_schema` — Get the full parameter schema for a specific tool
- `teradata_tool_call` — Execute a native Teradata tool directly
- `teradata_cleanup_jobs` — Clean up long-running jobs

**CRITICAL — No Early SQL Execution:**
Steps 1 through 12 are **information-gathering and design only**. During these steps you may ONLY use read-only tools (`base_readQuery`, `base_databaseList`, `base_tableList`, `base_columnDescription`, etc.). Do NOT call `execute_sql` or `teradata_tool_call` to run CREATE, GRANT, REVOKE, DROP, ALTER, or any other DDL/DML statement until the user has passed through Gate 3 (Step 13). If the user asks you to create a role, grant access, or make any change during Steps 1–12, record it in the design and explain that it will be executed after SQL review and approval.

**CRITICAL — Tool Errors Do Not Bypass Gates:**
If any tool fails (task board, executor, or any other tool), do NOT improvise a "manual plan" and proceed to execute SQL. Stop, report the error to the user, and wait for instruction. A tool error is never a reason to skip SQL generation, SQL review, or any approval gate.

## Sequential Execution Contract

> **This skill is a strictly ordered workflow.**
>
> ### State
>
> The workflow tracks these state variables:
> - `current_step`: The **only** step that may be executed.
> - `completed_steps`: Steps that passed their completion criteria.
> - `step_outputs`: The validated output from each completed step.
> - `approval_results`: Gate approvals recorded with timestamps.
> - `audit_log`: The complete chain of custody for the session.
>
> The task board is auto-emitted by the skill's `task_template` (see frontmatter). All 14 tasks with sequential dependencies are created automatically when the skill activates — do NOT create them manually.
> Use `task_board update` to mark each task in-progress when starting a step and completed when the step's completion criteria are met. Use `task_board list` to present board status at gate steps and on request.
>
> ### Mandatory Execution Rules
>
> 1. Execute **only** the step identified by `current_step`.
> 2. **Never** execute, draft, preview, or partially complete a later step.
> 3. Before executing Step N, verify that every step from 1 through N-1 is listed in `completed_steps` and has a saved output in `step_outputs`.
> 4. Do not infer that a step is complete merely because related information appears in the conversation.
> 5. A step is complete **only** when all its completion criteria are met and the user has confirmed the output.
> 6. When a step transition is invalid: remain on the current step, identify what is missing or invalid, do not continue.
> 7. If the user requests a later step, respond: *"Step N cannot begin until Step {current_step} has been completed and approved."*
> 8. Never change `current_step` based only on a user request — only meeting the completion criteria and user approval advances state.
> 9. Do not silently combine multiple steps into one response.
> 10. Before any DDL execution, verify that Gate 3 has been approved — proceed ONLY after explicit user approval at the gate step.
>
> ### Human Approval Rule
>
> After completing each step, present its output and ask the user to confirm.
> Do not begin the next step until the user explicitly approves by saying "approved", "continue", "yes", or equivalent.
> For gate steps (10, 12, 13, 14), record the approval in the audit log with a timestamp.
>
> ### Anti-Wandering Rule
>
> **Do NOT offer menus, numbered option lists, or open-ended suggestions between steps.** When a step completes:
> 1. Present the step's output and findings.
> 2. State what the next step is (by name and number).
> 3. Ask for confirmation to proceed — nothing else.
>
> The agent must NEVER suggest alternative analyses, visualization ideas, side explorations, or "what would you like to do?" prompts. There is exactly one valid next action at any point: the next step in the sequence. If the user asks for something outside the workflow, acknowledge it and redirect: *"That's outside the scope of this workflow. The next required step is Step {N} — {title}. Shall I continue?"*
>
> ### Anti-Skip Enforcement
>
> If the user or context attempts to skip ahead:
> ```
> The requested action belongs to Step {requested_step}.
> The current required step is Step {current_step}.
> Step {requested_step} cannot begin until all earlier steps have passed
> their completion criteria. Continue with Step {current_step}.
> ```
>

## Step Procedures

> The detailed procedure for each step lives in a reference file. Load the relevant reference when executing each step.

| Steps | Phase | Reference |
|-------|-------|-----------|
| 1–6 | Discovery, Analysis & Reporting | [step-procedures-discovery.md](./references/step-procedures-discovery.md) |
| 7–10 | Design & Gate 1 Approval | [step-procedures-design.md](./references/step-procedures-design.md) |
| 11–14 | SQL Generation, Execution & Gates 2–4 | [step-procedures-execution.md](./references/step-procedures-execution.md) |

## References


> **Access:** `skill_resource_read(action="read", skill="new-data-access", path="references/FILENAME")` — do NOT call `list`.

- [step-procedures-discovery.md](./references/step-procedures-discovery.md) — Steps 1–6: database identification, table enumeration, sensitivity assessment, protection strategy, readiness report compilation and confirmation.
- [step-procedures-design.md](./references/step-procedures-design.md) — Steps 7–10: role identification, access pattern design, ETL impact assessment, Gate 1 approval.
- [step-procedures-execution.md](./references/step-procedures-execution.md) — Steps 11–14: SQL file generation (setup + revert), SQL review (Gate 2), SQL execution (Gate 3), test review (Gate 4), final summary.
- [protection-strategy-guide.md](./references/protection-strategy-guide.md) — Masking patterns, PCI combination risk tables, Teradata SQL examples for column exclusion, masking, row filtering, and encryption.
- [protegrity-compatible-udfs.md](./references/protegrity-compatible-udfs.md) — Protegrity-compatible UDF definitions for tokenization, detokenization, and masking operations.
- [ujm-process-mapping.md](./references/ujm-process-mapping.md) — UJM "Ingest New Data" (DE-3) process mapping; persona responsibilities; deferred items.
