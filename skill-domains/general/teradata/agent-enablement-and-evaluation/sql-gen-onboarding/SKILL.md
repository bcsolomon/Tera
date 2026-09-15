---
name: sql-gen-onboarding
description: 'Onboard a database for SQL Generation (AgenticAI). Use when: setting up SQL Gen, creating a VectorStore, uploading table/column descriptions, running index scripts, uploading synonyms, taxonomy, acronyms, user profiles, or initializing the SQL Gen platform. Guides through mandatory and optional steps with plan approval before execution.'
argument-hint: "Describe which database and tables you want to onboard for SQL Gen"
metadata:
  author: teradata
  version: "1.0"
---

# SQL Generation Onboarding

Set up a Teradata database for the AgenticAI SQL Generation platform. This skill walks the user through the full onboarding lifecycle — from identifying the target database and tables, to creating a VectorStore, uploading metadata, running index scripts, and initializing the platform for operational use.

## When to Use

- Setting up a new database for SQL Gen / AgenticAI
- Creating or updating a VectorStore for SQL generation
- Uploading table descriptions, column descriptions, or acronyms
- Running index scripts (FeatureIndex, FeatureIndexDescription, IndexColumnUniqueness)
- Running AutoTaxonomy and curating the output
- Uploading synonyms or taxonomy for disambiguation
- Managing user profiles for SQL Gen
- Initializing or reinitializing the SQL Gen platform

## Prerequisites

- The target database exists in Teradata Vantage and is populated with business tables/views
- The calling user has admin privileges (member of `TD_AIADMIN` role)
- The SQL Gen API service is reachable at the configured base URL
- Python 3 with `requests` library available

## Environment Variables

All connection parameters are read from the environment. The agent must verify these are set before proceeding:

| Variable | Description | Example |
|----------|-------------|---------|
| `SQLGEN_BASE_URL` | SQL Gen API base URL | `http://host:8002/sql-gen/api/v1/` |
| `SQLGEN_HOSTNAME` | Database host IP | `100.80.31.103` |
| `SQLGEN_USERNAME` | Admin DB username (TD_AIADMIN member) | `dbc` |
| `SQLGEN_PASSWORD` | Admin DB password | *(set by user)* |

These are fixed for the environment and should already be configured. If any are missing, instruct the user to set them before proceeding.

## Overall Flow

Present this overview to the user at the start so they understand the full process:

```
MANDATORY STEPS (must complete in order):
  1. Identify the target database and tables to onboard
  2. Review and edit table descriptions (fetched from DB, user approves)
  3. Review and edit column descriptions (fetched from DB, user approves)
  4. Create a VectorStore (requires DB session)
  5. Run index scripts (FeatureIndex, FeatureIndexDescription, IndexColumnUniqueness)
  6. Initialize SQL Gen platform

OPTIONAL STEPS (can be added at any time):
  A. Upload synonyms file
  B. Upload taxonomy for disambiguation
  C. Run AutoTaxonomy → download → curate → re-upload
  D. Upload acronyms
  E. Upload user profiles
  F. Create naming patterns for table matching
```

---

## Procedure

### Step 1: Identify Target Database and Tables

First, verify that the required environment variables are set:
```bash
echo "BASE_URL=$SQLGEN_BASE_URL HOSTNAME=$SQLGEN_HOSTNAME USERNAME=$SQLGEN_USERNAME PASSWORD=$([ -n \"$SQLGEN_PASSWORD\" ] && echo SET || echo MISSING)"
```

If any are missing, instruct the user to set them and stop.

Next, run the health check to verify API connectivity:
```bash
python3 ./scripts/sqlgen_api.py health \
  --base-url "$SQLGEN_BASE_URL"
```

#### 1a. Ask the User for Their Target

**Do NOT list all databases upfront** — the system may have hundreds. Instead, ask the user directly:

> What database and/or table names are you interested in onboarding for SQL Gen?

Accept any of:
- A specific database name (e.g., `customer360`)
- A partial/fuzzy name to search for (e.g., "retail" or "bank")
- A database + table pattern (e.g., `DEMO_Retail_db` with tables matching `retail_%_VW`)

#### 1b. Validate the Database

Once the user provides a database name, use `mcp_td-mcp_base_tableList` with that database name to confirm it exists and list its tables/views. Present the results showing object names and types (table vs view).

If the database name doesn't exist or returns no results, let the user know and ask them to try again or clarify. If they only gave a partial name, use `mcp_td-mcp_base_databaseList` with a small `sample` to search, but only as a fallback — not as the starting point.

#### 1c. Select Tables

Ask the user:
- **Do they want to include all tables/views?** Or only a subset?
- If a subset, help them identify a **naming pattern** (e.g., `customer360_%_VW`) that matches their target objects, or let them pick specific tables from the list.

Use `mcp_td-mcp_base_tableAffinity` on key tables if the user wants to understand which tables are commonly queried together — this helps decide what to include.

#### 1d. Confirm VectorStore Name

Suggest using the database name as the VectorStore name (this is the common convention). Confirm with the user conversationally.

By the end of Step 1, you should have:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `database` | Target database name | `customer360` |
| `vs_name` | VectorStore name (often same as database) | `customer360` |
| `table_pattern` | Naming pattern for tables to include (optional) | `customer360_%_VW` |
| Selected tables | Specific tables/views the user wants to onboard | *(from MCP list)* |

### Step 2: Review and Edit Table Descriptions

Table descriptions tell the SQL Gen platform what each table/view contains. The agent should generate initial descriptions from the database metadata and let the user review and refine them before uploading.

#### 2a. Fetch Existing Table Comments from the Database

Query the Teradata catalog to get any existing table comments using `mcp_td-mcp_base_readQuery`:

```sql
SELECT DatabaseName, TableName, CommentString
FROM DBC.TablesV
WHERE DatabaseName = '<DATABASE>'
  AND TableKind IN ('T', 'V', 'O')
ORDER BY TableName
```

This returns the actual `COMMENT ON TABLE` values stored in the database. Tables without comments will have `NULL` for `CommentString`.

#### 2b. Present Table Descriptions to the User

Present the results as a markdown table. If a table already has a comment, show it. If not, use `mcp_td-mcp_base_columnDescription` to inspect the columns and infer a reasonable starter description from the column names and types:

```
| database_name | table_name         | table_comment                          | source   |
|---------------|--------------------|----------------------------------------|----------|
| DEMO_Car_db   | Complaints         | Records of vehicle defect complaints   | existing |
| DEMO_Car_db   | Counties           | (inferred from columns)                | inferred |
| DEMO_Car_db   | Service_Centers    | (inferred from columns)                | inferred |
| DEMO_Car_db   | Complaint_Locations| Location data for complaints           | existing |
```

Mark each description as `existing` (from DB comment) or `inferred` (generated by the agent) so the user knows which ones need attention.

#### 2c. Let the User Edit

Ask the user:

> Review the table descriptions above. You can:
> 1. **Edit in chat** — tell me which descriptions to change and what they should say
> 2. **Download as CSV** — I'll save a CSV file you can edit in a spreadsheet, then give me the path back
> 3. **Accept as-is** — use the current descriptions

If the user edits in chat, update the descriptions based on their feedback and present the revised table for confirmation. Repeat until they approve.

If they choose CSV download, generate the file:
```bash
python3 ./scripts/sqlgen_api.py generate-desc \
  --database "$DATABASE" --mcp-json "/tmp/mcp_metadata.json" --output-dir "/tmp/sqlgen_onboarding"
```
Then tell the user where the file is saved and wait for them to provide the edited file path.

#### 2d. Generate the Upload File

Once descriptions are finalized (either from chat edits or a user-provided CSV), write the final CSV to a temp file for upload in the execution step. Store the path for later use.

### Step 3: Review and Edit Column Descriptions

Column descriptions tell the SQL Gen platform what each column means. The agent should fetch column metadata, generate initial descriptions, and let the user review and refine them.

#### 3a. Fetch Existing Column Comments from the Database

Query the Teradata catalog to get any existing column comments using `mcp_td-mcp_base_readQuery`:

```sql
SELECT DatabaseName, TableName, ColumnName, ColumnType, CommentString
FROM DBC.ColumnsV
WHERE DatabaseName = '<DATABASE>'
  AND TableName IN ('<TABLE1>', '<TABLE2>', ...)
ORDER BY TableName, ColumnId
```

This returns the actual `COMMENT ON COLUMN` values stored in the database. Columns without comments will have `NULL` for `CommentString`.

#### 3b. Present Column Descriptions to the User

Present the results as markdown tables, grouped by table. For columns that already have a comment, show it. For columns without comments, infer a reasonable description from the column name and type:

```
**Table: Complaints**
| column_name       | type          | column_comment                              | source   |
|-------------------|---------------|---------------------------------------------|----------|
| complaint_id      | INTEGER       | Unique identifier for each complaint        | existing |
| complaint_date    | DATE          | Date the complaint was filed                | existing |
| vehicle_make      | VARCHAR(50)   | Manufacturer of the vehicle                 | inferred |
| ...               | ...           | ...                                         | ...      |

**Table: Counties**
| column_name       | type          | column_comment                              | source   |
| ...               | ...           | ...                                         | ...      |
```

Mark each description as `existing` (from DB comment) or `inferred` (generated by the agent) so the user knows which ones need attention.

#### 3c. Let the User Edit

Ask the user the same options as table descriptions:

> Review the column descriptions above. You can:
> 1. **Edit in chat** — tell me which descriptions to change
> 2. **Download as CSV** — I'll save a CSV file you can edit in a spreadsheet, then give me the path back
> 3. **Accept as-is** — use the current descriptions

For large tables with many columns, the CSV download option is recommended. Mention this to the user.

If editing in chat, the user can say things like:
- "Change complaint_date to 'Date when the customer submitted the complaint'"
- "All the columns in Counties look good"
- "For Service_Centers, change center_name to 'Name of the authorized service center'"

Update and re-present until approved.

#### 3d. Generate the Upload File

Once descriptions are finalized, write the final CSV to a temp file for upload in the execution step. Store the path for later use.

### Step 4: Select Onboarding Steps

Present the full flow (mandatory + optional) and ask the user which optional steps they want to include. Use `vscode_askQuestions` with multiSelect for the optional steps.

### Step 5: Generate and Present the Plan

Based on the user's selections, generate an execution plan listing every API call that will be made, in order. Present it as a numbered plan for user approval.

Example plan:
```
ONBOARDING PLAN for database: customer360
═══════════════════════════════════════════
Environment: SQLGEN_BASE_URL, SQLGEN_HOSTNAME, SQLGEN_USERNAME — from env
Database: customer360 | VectorStore: customer360

  1. [MANDATORY] Health check
  2. [MANDATORY] Upload table descriptions (reviewed/edited by user)
  3. [MANDATORY] Upload column descriptions (reviewed/edited by user)
  4. [OPTIONAL]  Upload acronyms (file: acronyms.xlsx)
  5. [MANDATORY] Create DB session + VectorStore + disconnect
  6. [MANDATORY] Verify VectorStore READY status (explicit status check)
  7. [OPTIONAL]  Upload synonyms file
  8. [MANDATORY] Run index scripts (FeatureIndex + FeatureIndexDescription + IndexColumnUniqueness)
  9. [MANDATORY] Wait for index scripts SUCCEEDED status
 10. [OPTIONAL]  Run AutoTaxonomy script
 11. [OPTIONAL]  Wait for AutoTaxonomy SUCCEEDED status
 12. [OPTIONAL]  Download AutoTaxonomy file for curation
 13. [OPTIONAL]  ── USER CURATES FILE ──
 14. [OPTIONAL]  Upload curated AutoTaxonomy file
 15. [OPTIONAL]  Upload user profiles
 16. [MANDATORY] Run SQL Gen Initialization
 17. [MANDATORY] Wait for Initialization SUCCEEDED status
 18. [DONE]      Platform ready for operational use
```

**Ask the user to approve the plan before proceeding.**

### Step 6: Locate and Validate Input Files

For each file-upload step in the plan (excluding table and column descriptions, which were already prepared in Steps 2-3), ask the user to provide the file path. Validate that:
- The file exists on disk
- The file has a valid extension (.xlsx, .csv, or .json)
- For acronyms: file has columns `acronym`, `description`

If the user doesn't have the files yet, help them understand the format using [metadata file specs](./references/metadata-files.md).

### Step 7: Execute the Plan

Execute each step in the approved plan sequentially using the Python API script. For each step:

1. Announce which step is starting
2. Run the corresponding command via the script
3. Report the result (success/failure with details)
4. For async operations (VectorStore creation, index scripts, initialization), poll for status

Use the script at `./scripts/sqlgen_api.py` for all API calls:

All commands use `$SQLGEN_BASE_URL`, `$SQLGEN_HOSTNAME`, `$SQLGEN_USERNAME`, `$SQLGEN_PASSWORD` from the environment. Only `--database`, `--vs-name`, file paths, and step-specific params vary.

**Health check:**
```bash
python3 ./scripts/sqlgen_api.py health \
  --base-url "$SQLGEN_BASE_URL"
```

**Fetch existing table comments from DB (used in Step 2a) — via `mcp_td-mcp_base_readQuery`:**
```sql
SELECT DatabaseName, TableName, CommentString
FROM DBC.TablesV
WHERE DatabaseName = '<DATABASE>'
  AND TableKind IN ('T', 'V', 'O')
ORDER BY TableName
```

**Fetch existing column comments from DB (used in Step 3a) — via `mcp_td-mcp_base_readQuery`:**
```sql
SELECT DatabaseName, TableName, ColumnName, ColumnType, CommentString
FROM DBC.ColumnsV
WHERE DatabaseName = '<DATABASE>'
  AND TableName IN ('<TABLE1>', '<TABLE2>', ...)
ORDER BY TableName, ColumnId
```

**Generate starter description CSVs from MCP metadata (used in Steps 2-3):**
```bash
python3 ./scripts/sqlgen_api.py generate-desc \
  --database "$DATABASE" --mcp-json "/tmp/mcp_metadata.json" \
  --output-dir "/tmp/sqlgen_onboarding"
```

**Upload table descriptions (uses CSV generated/edited in Step 2):**
```bash
python3 ./scripts/sqlgen_api.py upload-table-desc \
  --base-url "$SQLGEN_BASE_URL" --hostname "$SQLGEN_HOSTNAME" --database "$DATABASE" \
  --username "$SQLGEN_USERNAME" --password "$SQLGEN_PASSWORD" \
  --file "/tmp/sqlgen_onboarding/table_descriptions.csv"
```

**Upload column descriptions (uses CSV generated/edited in Step 3):**
```bash
python3 ./scripts/sqlgen_api.py upload-column-desc \
  --base-url "$SQLGEN_BASE_URL" --hostname "$SQLGEN_HOSTNAME" --database "$DATABASE" \
  --username "$SQLGEN_USERNAME" --password "$SQLGEN_PASSWORD" \
  --file "/tmp/sqlgen_onboarding/column_descriptions.csv"
```

**Upload acronyms:**
```bash
python3 ./scripts/sqlgen_api.py upload-acronyms \
  --base-url "$SQLGEN_BASE_URL" --hostname "$SQLGEN_HOSTNAME" --database "$DATABASE" \
  --username "$SQLGEN_USERNAME" --password "$SQLGEN_PASSWORD" \
  --file "path/to/acronyms.xlsx"
```

**Create session + VectorStore + disconnect (combined; command returns non-zero if READY is not reached):**
```bash
python3 ./scripts/sqlgen_api.py create-vectorstore \
  --base-url "$SQLGEN_BASE_URL" --hostname "$SQLGEN_HOSTNAME" --database "$DATABASE" \
  --vs-name "$VS_NAME" --username "$SQLGEN_USERNAME" --password "$SQLGEN_PASSWORD" \
  --embeddings-model "amazon.titan-embed-text-v2:0" \
  --include-patterns "pattern1,pattern2"
```

**Verify VectorStore status explicitly (required after create-vectorstore):**
```bash
python3 ./scripts/sqlgen_api.py get-vs-status \
  --base-url "$SQLGEN_BASE_URL" --hostname "$SQLGEN_HOSTNAME" --database "$DATABASE" \
  --vs-name "$VS_NAME" --username "$SQLGEN_USERNAME" --password "$SQLGEN_PASSWORD"
```

**Upload metadata files (synonyms, taxonomy, autotaxonomy):**
```bash
python3 ./scripts/sqlgen_api.py upload-files \
  --base-url "$SQLGEN_BASE_URL" --hostname "$SQLGEN_HOSTNAME" --database "$DATABASE" \
  --vs-name "$VS_NAME" --username "$SQLGEN_USERNAME" --password "$SQLGEN_PASSWORD" \
  --synonyms "path/to/synonyms.csv" \
  --taxonomy-disambiguation "path/to/taxonomy.json" \
  --autotaxonomy "path/to/curated_taxonomy.json"
```

**Run index scripts + poll until complete:**
```bash
python3 ./scripts/sqlgen_api.py run-index-scripts \
  --base-url "$SQLGEN_BASE_URL" --hostname "$SQLGEN_HOSTNAME" --database "$DATABASE" \
  --vs-name "$VS_NAME" --username "$SQLGEN_USERNAME" --password "$SQLGEN_PASSWORD" \
  --wait
```

**Get current script status snapshot (optional point-in-time tracking):**
```bash
python3 ./scripts/sqlgen_api.py get-status \
  --base-url "$SQLGEN_BASE_URL" --hostname "$SQLGEN_HOSTNAME" --database "$DATABASE" \
  --vs-name "$VS_NAME" --username "$SQLGEN_USERNAME" --password "$SQLGEN_PASSWORD"
```

**Run AutoTaxonomy + poll + download:**
```bash
python3 ./scripts/sqlgen_api.py run-autotaxonomy \
  --base-url "$SQLGEN_BASE_URL" --hostname "$SQLGEN_HOSTNAME" --database "$DATABASE" \
  --vs-name "$VS_NAME" --username "$SQLGEN_USERNAME" --password "$SQLGEN_PASSWORD" \
  --table-pattern "customer360_%_VW" \
  --wait --download "downloaded_taxonomy.json"
```

**Upload user profiles:**
```bash
python3 ./scripts/sqlgen_api.py upload-user-profiles \
  --base-url "$SQLGEN_BASE_URL" --hostname "$SQLGEN_HOSTNAME" --database "$DATABASE" \
  --vs-name "$VS_NAME" --username "$SQLGEN_USERNAME" --password "$SQLGEN_PASSWORD" \
  --file "path/to/profiles.xlsx"
```

**Initialize SQL Gen + poll until complete:**
```bash
python3 ./scripts/sqlgen_api.py initialize \
  --base-url "$SQLGEN_BASE_URL" --hostname "$SQLGEN_HOSTNAME" --database "$DATABASE" \
  --vs-name "$VS_NAME" --username "$SQLGEN_USERNAME" --password "$SQLGEN_PASSWORD" \
  --wait
```

### Step 8: AutoTaxonomy Curation (if selected)

If AutoTaxonomy was selected, after the script completes and the file is downloaded:
1. Inform the user the file has been downloaded
2. Explain what the file contains and how to curate it (see [metadata file specs](./references/metadata-files.md))
3. **Pause and wait for the user to confirm curation is complete**
4. Ask for the path to the curated file
5. Upload the curated file using the upload-files command with `--autotaxonomy`

### Step 9: Final Status Report

After all steps complete, present a summary:

```
ONBOARDING COMPLETE
═══════════════════
Database:     customer360
VectorStore:  customer360
Status:       READY

Completed steps:
  ✓ Table descriptions uploaded (3 tables)
  ✓ Column descriptions uploaded (20 columns)
  ✓ Acronyms uploaded (5 entries)
  ✓ VectorStore created (status: READY)
  ✓ Index scripts completed (FeatureIndex, FeatureIndexDescription, IndexColumnUniqueness)
  ✓ AutoTaxonomy generated and curated
  ✓ User profiles uploaded (3 users)
  ✓ SQL Gen initialized (status: SUCCEEDED)

The platform is now ready for operational use via the Ask API.
```

## Error Handling

- If any step fails, report the error and ask the user if they want to retry or skip
- For async operations that fail, report the script name and failure status
- If the health check fails, do not proceed — the service is unreachable
- If admin check fails (403), inform the user they need TD_AIADMIN role membership

## Reference Documents

- [API Endpoint Reference](./references/api-reference.md) — All endpoints, parameters, response codes
- [Metadata File Specifications](./references/metadata-files.md) — File formats for synonyms, taxonomy, descriptions, acronyms, user profiles
