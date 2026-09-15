# Step Procedures: SQL Generation, Execution & Gates 2–4 (Steps 11–14)

> Source: Enterprise Data Access Onboarding Skill v3.0
> This reference contains the detailed execution procedures for Steps 11 through 14.
> Steps 12, 13, and 14 are approval gates. Do not proceed past any gate without explicit user approval.

---

## Step 11 — Generate SQL Files

### Preconditions
- `current_step` equals `11`.
- Steps 1–10 in `completed_steps`.
- Gate 1 approved.

### Actions

Generate **two separate SQL files** and write both to the workspace:

- **`<database_name>_access_setup.sql`** — the forward script (Setup, Tests, Verification)
- **`<database_name>_access_revert.sql`** — the standalone rollback script

The revert file must be a complete, self-contained script that a DBA can run independently at any time to undo every change made by the setup script. It must be kept in sync with the setup file — any change to the setup script requires a corresponding update to the revert script.

The setup file must contain three clearly labelled sections:

### Section 1: Setup SQL

```sql
-- ============================================================
-- SECTION 1: SETUP
-- Database: <database_name>  Generated: <timestamp>
-- ============================================================

-- Create new roles (skip if role already exists)
CREATE ROLE <new_role_name>;

-- Grant direct table privileges
GRANT SELECT [, INSERT, UPDATE, DELETE]
  ON <database>.<table>
  TO <role_name>;

-- Create views
CREATE VIEW <view_db>.<view_name> AS
  SELECT <approved_column_list>
  FROM <database>.<table>
  [WHERE <row_filter>];

-- Grant view privileges
GRANT SELECT ON <view_db>.<view_name> TO <role_name>;
```

The revert file (`<database_name>_access_revert.sql`) must contain:

```sql
-- ============================================================
-- REVERT SCRIPT
-- Database: <database_name>  Generated: <timestamp>
-- Run this file to fully undo all changes in
-- <database_name>_access_setup.sql.
-- Execute statements in order — views before grants, grants before roles.
-- ============================================================

REVOKE SELECT ON <view_db>.<view_name> FROM <role_name>;

DROP VIEW <view_db>.<view_name>;

REVOKE SELECT [, INSERT, UPDATE, DELETE]
  ON <database>.<table>
  FROM <role_name>;

DROP ROLE <new_role_name>;  -- only for newly created roles
```

### Section 2: Test SQL

```sql
-- ============================================================
-- SECTION 2: TESTS
-- Run each block while connected as a user who holds the role,
-- or use SET ROLE before each block.
-- ============================================================

-- Test: <role_name> direct table access
SET ROLE <role_name>;
SELECT TOP 5 * FROM <database>.<table>;

-- Test: <role_name> view access
SELECT TOP 5 * FROM <view_db>.<view_name>;

-- Negative test: confirm excluded columns are not accessible
SELECT <excluded_column> FROM <view_db>.<view_name>;  -- should fail

-- Negative test: confirm row filter is enforced
SELECT COUNT(*) FROM <view_db>.<view_name>;  -- should match filtered count only
```

### Section 3: Verification Queries

```sql
-- ============================================================
-- SECTION 3: VERIFICATION
-- Confirm grants and objects exist after setup.
-- ============================================================

SELECT * FROM DBC.RoleInfo WHERE RoleName = '<role_name>';
SELECT * FROM DBC.AllRights WHERE DatabaseName = '<database_name>';
SHOW VIEW <view_db>.<view_name>;
```

Present both files to the user — **all sections of both files must be shown**. Ask:
> "This is **Approval Gate 2 — SQL Review**. Please review the setup file (Setup, Tests, Verification) and the revert file below. The revert file is a standalone script a DBA can run at any time to undo all changes. Reply 'approved' to proceed with execution, or describe any changes needed."

Log:
`- <timestamp> | sql-generated | SQL files generated: <database_name>_access_setup.sql and <database_name>_access_revert.sql with <N> setup statements, <M> test statements`

### Required Output
```json
{"setup_sql": "<filename>", "revert_sql": "<filename>"}
```

### Completion Criteria
Step 11 passes only when:
- Both SQL files are generated (setup + revert).
- All four sections are present in the setup file.
- Both files have been presented to the user.

### On Failure
Remain on Step 11. Complete missing SQL sections.

### On Success
Record in the audit log and advance to the next step:
- Log: `<timestamp> | sql-generated | SQL files generated`
- Step output: `{"setup_sql": "...", "revert_sql": "..."}`

---

## Step 12 — ⛔ GATE 2: SQL Review and Approval

### Preconditions
- `current_step` equals `12`.
- Steps 1–11 in `completed_steps`.
- `step_outputs.11.setup_sql` and `step_outputs.11.revert_sql` exist.

### Actions

Apply any edits the user requests to either file. Re-present the changed sections after each revision. If a change to the setup file affects the rollback logic, update the revert file in the same edit and present both changes together.

**Do NOT proceed to execution until the user explicitly approves both files.** The user must see and approve:
1. **Setup SQL** — the changes that will be applied
2. **Revert file** — the standalone script to undo everything
3. **Test SQL** — how the access will be validated
4. **Verification SQL** — how to confirm objects exist

Once the user gives explicit approval of both files, log it:
`- <timestamp> | GATE-2-APPROVED | User approved <database_name>_access_setup.sql and <database_name>_access_revert.sql for execution`

### Required Output
```json
{"gate_2_approved": true}
```

### Completion Criteria
Step 12 passes only when:
- The user has explicitly approved both the setup and revert SQL files.
- Gate 2 approval has been recorded in the audit log.

### On Failure
Remain on Step 12. Apply edits and re-present changed sections.

### On Success
Record gate approval in the audit log and advance to the next step:
- Log: `<timestamp> | GATE-2-APPROVED | User approved setup and revert SQL`
- Step output: `{"gate_2_approved": true}`

---

## Step 13 — ⛔ GATE 3: Apply SQL

### Preconditions
- `current_step` equals `13`.
- Steps 1–12 in `completed_steps`.
- Gates 1 and 2 approved.
- DDL execution is permitted ONLY after Gate 3 approval below.

### Actions

Before executing, confirm one final time:
> "This is **Approval Gate 3 — Apply SQL**. I am about to execute the Setup SQL against the database. The Revoke/Rollback SQL is available if we need to undo any changes. Do you approve execution? Reply 'approved' to proceed."

**Do NOT execute until the user explicitly approves.**

Once the user approves, record Gate 3 approval in the audit log, then proceed with execution.

Log:
`- <timestamp> | GATE-3-APPROVED | User approved execution of setup SQL for <database_name>`

Execute the **Setup** section statements in order using `execute_sql` for DDL/DML (CREATE, GRANT, REVOKE, DROP) and `base_readQuery` for SELECT queries. Run each statement individually and report success or failure after each one. If any statement fails, stop and report the error to the user before continuing.

Log each executed statement:
`- <timestamp> | execute | <statement_summary> — <SUCCESS/FAILED>`

### Required Output
```json
{"gate_3_approved": true, "execution_results": [{"statement": "...", "result": "SUCCESS|FAILED"}]}
```

### Completion Criteria
Step 13 passes only when:
- Gate 3 approval has been recorded in the audit log.
- The user explicitly approved execution.
- All setup SQL statements have been executed and results logged.

### On Failure
If any statement fails: stop execution, report the error, and wait for user instruction. Do NOT continue to the next statement or advance the workflow.

### On Success
Record in the audit log and advance to the next step:
- Log: `<timestamp> | execution-complete | All <N> statements executed successfully`
- Step output: `{"gate_3_approved": true, "execution_results": [...]}`

---

## Step 14 — ⛔ GATE 4: Review Test Results

### Preconditions
- `current_step` equals `14`.
- Steps 1–13 in `completed_steps`.
- Gates 1, 2, and 3 approved.
- `step_outputs.13.execution_results` shows all statements succeeded.

### Actions

After all setup statements succeed, run the **Test SQL** section. For each test:
- Report whether it succeeded or failed
- For positive tests (expected to return rows), show the result
- For negative tests (expected to fail), confirm the error occurred as intended

Produce a final test report:

| Test | Expected | Result | Pass/Fail |
|---|---|---|---|
| `<role>` reads `<table>` | Rows returned | 5 rows | Pass |
| `<role>` excluded column blocked | Error | Teradata error 3523 | Pass |
| Row filter enforced | Filtered count | N rows | Pass |

Present the test report and ask:
> "This is **Approval Gate 4 — Test Results**. Please review the test results above. All tests must pass for the onboarding to be considered complete. Do you approve these results as final acceptance? Reply 'approved' to complete, or identify any issues."

**Do NOT mark the onboarding as complete until the user explicitly approves the test results.**

Log the outcome:
`- <timestamp> | GATE-4-APPROVED | User approved test results for <database_name>: <N> statements executed, <M>/<M> tests passed`

If any test fails, present the failure to the user and ask how to proceed before making any further changes.

### Required Output
```json
{"gate_4_approved": true, "test_results": [{"test": "...", "expected": "...", "result": "...", "pass": true}]}
```

### Completion Criteria
Step 14 passes only when:
- All tests have been run and results presented.
- The user has explicitly approved the test results.
- Gate 4 approval has been recorded in the audit log.

### On Failure
Remain on Step 14. Identify failed tests, report them, and wait for user direction.

### On Success
Record gate approval in the audit log:
- Log: `<timestamp> | GATE-4-APPROVED | User approved test results — workflow complete`
- Step output: `{"gate_4_approved": true, "test_results": [...]}`

---

## Final Summary

After Gate 4 approval, present the complete audit log to the user as a final record of the onboarding process. Include:
- All four gate approvals with timestamps
- Summary of objects created (roles, views, grants)
- Test results
- The location of the SQL file (including the Revoke/Rollback section for future use)

