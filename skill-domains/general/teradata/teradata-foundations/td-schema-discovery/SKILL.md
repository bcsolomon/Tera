---
name: td-schema-discovery
description: Data discovery and metadata exploration skill for Teradata — ALWAYS invoke for queries related to semantic table and column discovery, schema exploration, DDL inspection, column-level searches, join-path identification, cross-database relationship mapping, and object inventory analysis through natural language search and metadata browsing.
---

# Teradata Data Discovery Skill

## Core Rules

**TOOLS**

Use only these 4 MCP tools:

| # | Tool | Purpose |
|---|------|---------|
| 1 | `base_userDatabaseList` | List accessible databases |
| 2 | `base_tableList` | List tables/views in a database |
| 3 | `base_tableDDL` | Columns, types, constraints |
| 4 | `base_readQuery` | Read-only SQL (Step 0 pre-scan and fallback) |

**No general-knowledge answers**: Always call at least one MCP tool. If database is unknown, start with Step 0 (`base_readQuery` on `DBC.TablesV`) when user terms can be pattern matched; otherwise start with `base_userDatabaseList` → `base_tableList`.

**Execution principle**: Match intent + likely sequence → call tools left-to-right → stop when you have enough evidence to answer the question with confidence. Then synthesize one final answer block. Do not narrate between tool calls. Make only the necessary tool calls for the chosen route.

**Pre-call tool compliance gate**: Before every tool call, enforce:
- If selected tool is not in the allowed set for the routed intent, do not call it.
- Re-route to the allowed tool sequence instead.
- Do not use a fallback tool before attempting the normal tool sequence for the routed intent.
- For Intents 2, 3, and 4, `base_readQuery` must not be used in place of the normal intent tool path.

**Global no-post-processing rule**: After a successful MCP result, do not perform extra `Read`, `Bash`, `grep`, or local filtering unless the tool output is incomplete, truncated, or unreadable. Apply this rule to all intents.

**Unknown-DB search order (relevance-first)**:
- Apply this flow whenever the database is unknown.
- **Step 0 (catalog pre-scan):** Run `base_readQuery` on `DBC.TablesV` to identify candidate databases before broader scanning.
- Use this Step 0 query template:
```sql
SELECT
    DatabaseName,
    TableName,
    CreateTimeStamp,
    LastAlterTimeStamp
FROM DBC.TablesV
WHERE TableKind = 'T'
  AND TableName LIKE '%<search_term_or_partial_name>%';
```
- **Step 1 (accessibility filter, required):** Run `base_userDatabaseList` and keep only candidate databases accessible to the current user.
- **Hard gate:** If Step 0 is used, do not finalize any result (found or not found) until Step 1 filtering is completed.
- Set logic:
  - accessible_candidates = step0_candidate_databases ∩ user_accessible_databases
  - inaccessible_candidates = step0_candidate_databases - user_accessible_databases
  - Continue tool calls only on `accessible_candidates`.
- **Phase 1 (relevance-first search):**
  - If Step 0 was used, check `accessible_candidates` first.
  - If Step 0 was not applicable (no usable object/search term), start with semantically relevant databases first (for example: retail, customer, telecom).
- **Phase 2 (completion search):** If object is not found in Phase 1, or the prompt requires exhaustive discovery, continue with remaining accessible databases.
- Never pick databases randomly.

---

## Intent Routing

### 1) Semantic Discovery
User provides a business concept with no table names.
- Database unknown by default: follow **Unknown-DB search order (relevance-first)** → `base_tableList` across candidate/relevant DBs → keyword/semantic match
- If the user asks for accessible-database discovery (for example: "What all databases can the current user access?") run `base_userDatabaseList` first.
- Output: all relevant objects found with a short match note.

### 2) Object and Database Browsing / Cross-Database Locate
User wants to locate, list, or validate objects.
- DB + table given → `base_tableList` (confirm exists and type)
- DB given only → `base_tableList` in that DB
- Known-DB stop rule: when database is explicitly given, answer from `base_tableList` results and stop.
- DB unknown → follow **Unknown-DB search order (relevance-first)** → `base_tableList` on candidate/relevant DBs and remaining DBs if needed
- **DO NOT** call `base_userDatabaseList` if a database name is given in the query.
- Never call `base_tableDDL` for browse/locate tasks.
- Never use `base_readQuery` for browse/locate prompts except Step 0 in Unknown-DB search order.

### 3) Schema / DDL Lookup
User asks for schema evidence: columns, data types, constraints, indexes, or any request to validate/flag type correctness.
- DB + table given → `base_tableDDL`
- Table only (no DB) → follow **Unknown-DB search order (relevance-first)** → `base_tableList` (candidate/relevant DBs) → `base_tableDDL`
- Never use `base_readQuery` for schema — use `base_tableDDL`.

### 4) Column Discovery (single or cross-database)
User wants to find tables/views containing a specific column.
- DB given → `base_tableList` → consider filtering by keyword → `base_tableDDL` on matching tables
- DB unknown → follow **Unknown-DB search order (relevance-first)** → `base_tableList` → filter by keyword → `base_tableDDL`
- `base_tableDDL` on selected candidates is the default and authoritative evidence step.
- Never use `base_readQuery` for column discovery.
- Do not query `DBC.ColumnsV` via `base_readQuery` for column discovery.
- Never jump to `base_tableDDL` when DB is unknown — must follow Unknown-DB search order, then `base_tableList` first.

### 5) Relationship, Join-Path, and Cross-Database Overlap
User asks about joins, overlaps, anti-joins, or cross-table relationships.

**Route based on what is known:**
- All table locations known → `base_tableDDL` (on candidate tables) → use DDL evidence to synthesize join path
- DBs known, tables unknown → `base_tableList` → `base_tableDDL` (on primary entity candidates) → synthesize join
- DBs unknown → follow **Unknown-DB search order (relevance-first)** → `base_tableList` → `base_tableDDL` (on primary entity candidates) → synthesize join

**Data Query Rule:**
- Use DDL evidence to identify join keys and produce join SQL.
- Call `base_readQuery` only if DDL evidence is contradictory, ambiguous, or insufficient.
- For NOT EXISTS/MINUS queries: verify key columns in DDL first; synthesize the SQL from DDL. Skip `base_readQuery` unless the join strategy is unclear from DDL alone.

**Candidate Selection:**
- Focus on primary entity tables (tables holding main business records, not reference-only or generic lookup tables).
- Limit candidate checks to a reasonable number (typically 5–10 primary entities across all accessible databases); prioritize by semantic relevance.
- **Stop when**: You have DDL evidence of a valid join path. You may stop before exhaustively checking all potential tables.

#### Type Mismatch Rule (Intent 5)
If DDL reveals a type mismatch between join candidate columns (e.g. VARCHAR vs INTEGER):
- **This is a valid join path** using CAST — do NOT conclude "no direct join path exists".
- Frame CAST as the recommended solution: "Join is possible using CAST. Suggested SQL: …"
- When one side is numeric and the other side is string/alphanumeric, **prefer casting the numeric side to string**.
- Prefer normalized string-side joins such as: `string_col = TRIM(CAST(numeric_col AS VARCHAR(n)))`
- Avoid casting free-form VARCHAR identifiers to INTEGER or FLOAT unless DDL or query evidence proves the values are purely numeric.
- Only say no join is possible when column names AND semantics are entirely unrelated.

#### Table Selection for Anti-Join / MINUS Tasks (Intent 5)
When the query asks "which rows in DB_A have no match in DB_B":
- Identify the **primary entity table** in DB_A (holds entity records, not reference/lookup).
- Use `base_tableList` + `base_tableDDL` to confirm table structure and key columns.
- For anti-joins across databases, prefer source tables with primary business entities and stable ID keys; avoid generic identity tables or known-empty tables.
- For MINUS tasks, prefer tables with rich ID column coverage as the source side.

### 6) Object Counts by Kind
User wants counts of tables, views, or other object types.
- DB given → `base_readQuery`
- DB unknown → follow **Unknown-DB search order (relevance-first)** (use Step 0 when a table/object term can be pattern matched) → `base_readQuery`
- Must use `DBC.TablesV` with `TableKind IN ('T','V','O')` and `GROUP BY TableKind`.
- Report only returned values; do not infer, estimate, or merge with counts from other tools.
- Compute total only as the sum of returned category counts.
- Use this exact query:
```sql
SELECT TableKind, COUNT(*) AS ObjectCount
FROM DBC.TablesV WHERE DatabaseName = '<db>'
GROUP BY TableKind ORDER BY ObjectCount DESC
```

### Fallback (No Clear Intent Match)
Apply this routing order when user intent is ambiguous:
1. If request asks for accessible database inventory (for example current-user database access) → Intent 1.
2. If request centers on columns, keys, types, schema words → Intent 3.
3. If request centers on object existence, location, listing, browsing → Intent 2.
4. If request centers on business meaning/domain terms with no object names → Intent 1.
5. If request asks join/overlap/relationship language → Intent 5.
6. If request asks counts by kind → Intent 6.
7. If still ambiguous, start with Intent 2 using conservative scope; stop when sufficient evidence is gathered.

---

## Correctness Guardrails

- For "find/list/which objects", check accessible databases and stop after sufficient coverage for the prompt.
- For discovery/listing, include both tables and views unless user explicitly excludes one type.
- For relationship checks, attempt type alignment (e.g. CAST) before concluding no join is possible — CAST-based joins are valid.
- For cross-database key discovery, prioritize primary-entity tables with stable identifiers.
- **When to stop**: stop when the answer is correct and sufficiently supported.

---

## Output Rules

**Output format**:
- Direct answer only — no tool traces, intermediate steps, or process narration.
- All results as fully qualified `DatabaseName.TableName`.
- Return DDL/columns only if explicitly requested.
- No duplicated sections.
- Emit exactly one final answer block; never emit a second answer block.
- **Keep the final response concise and within approximately 1.5K tokens.**
- Avoid chain-of-thought lead-ins and filler openers (for example: "I'll help you...", "Let me first...", "Perfect!", "Excellent!", "Would you like me to...", "Do you want me to...", "Shall I continue...?").
- Do not use these phrases in final responses: "I'll", "I will", "let me", "loading", "searching", "executing tool".
- No follow-up prompts: end immediately after the final answer; do not append questions, invitations, or offers for additional help.
- Answer only what was asked. Do not add optional sections like Interpretation, Source, or Assumptions unless explicitly requested.

**"Not found" cases**: Explicitly state what was not found, suggest closest alternatives, and give a definitive YES/NO/MAYBE conclusion on viability.
