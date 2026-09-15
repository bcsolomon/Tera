# Quick Start — Role × Goal Matrix

Content for personalized quick start output. Match on role × goal and use the relevant section.

---

## General Quick Start (Skip Path)

**Best first steps:**
1. Describe what you want to know in plain English — Tera will write the SQL for you.
2. Share your database name and key table names so Tera can tailor its help to your environment.
3. Paste something you're stuck on — a query, an EXPLAIN output, a DDL — and Tera will dig in.

**Lead expert:** QueryBot (Marcus Chen) for SQL questions; PipelineBot (Alex Rivera) for data loading; GuardBot (James Whitfield) if you're handling sensitive data.

**Starter query:**
```sql
-- See your top 10 databases by size
SELECT DatabaseName, SUM(CurrentPerm) / 1e9 AS SizeGB
FROM DBC.DiskSpaceV
GROUP BY 1
ORDER BY 2 DESC
SAMPLE 10;
```

**When you're ready to go deeper:** Tell Tera what you're working on and ask to speak with the relevant expert. Each expert has a specific domain — QueryBot for SQL, PipelineBot for pipelines, AnalyticsBot for ML, ModelBot for schema design, OpsBot for system health, GuardBot for security.

Not what you were looking for? Say **start over** and pick your role for a more tailored path.

---

## Data Analyst × Explore Data / Create Reports

**Best first steps:**
1. Describe your business question in plain English — Tera will identify the right tables and write the SQL.
2. Ask for a metric definition: "How should I measure monthly active customers?" — Tera will define it and write the query.
3. Ask Tera to explain any result set in plain terms so you can share findings with stakeholders.

**Lead expert:** QueryBot (Marcus Chen) — SQL generation, query iteration, performance.

**Starter query:**
```sql
SELECT EXTRACT(YEAR FROM order_date) AS yr,
       EXTRACT(MONTH FROM order_date) AS mo,
       SUM(order_total) AS revenue,
       COUNT(*) AS order_count
FROM sales.orders
WHERE order_date >= ADD_MONTHS(CURRENT_DATE, -12)
GROUP BY 1, 2
ORDER BY 1, 2;
```

**When you're ready to go deeper:** Ask Tera to define KPIs, build reusable query templates, or structure an analysis for a stakeholder presentation. Ask for QueryBot if a query is running slow.

---

## Data Analyst × Solve a Specific Business Problem

**Best first steps:**
1. Describe the business problem — Tera will suggest which tables, joins, and metrics to use.
2. Ask Tera to identify relevant tables: "What tables in [your_database] relate to customer orders?"
3. Paste a query you've already written and ask Tera to review it for correctness and performance.

**Lead expert:** QueryBot (Marcus Chen) for SQL; ModelBot (Priya Sharma) if the schema doesn't look right.

**Starter query:**
```sql
SELECT customer_id,
       COUNT(*) AS total_orders,
       SUM(order_total) AS lifetime_value
FROM sales.orders
GROUP BY 1
ORDER BY 3 DESC
SAMPLE 20;
```

---

## Business Analyst × Explore Data / Create Reports

Same as Data Analyst × Explore Data above.

**Emphasis:** Ask Tera to explain results in plain business terms. You don't need to write SQL — describe what you want and Tera handles it. Format outputs for sharing with non-technical stakeholders.

---

## Business Analyst × Solve a Specific Business Problem

Same as Data Analyst × Solve a Specific Business Problem above.

**Emphasis:** Describe the business question in plain language — Tera will identify the tables, write the SQL, and explain the results. Ask for QueryBot if you want deeper analysis or the numbers don't look right.

---

## Data Engineer × Build Pipelines / ETL

**Best first steps:**
1. Ask Tera to generate DDL for your staging and target tables — describe the data and it will recommend a PRIMARY INDEX.
2. Ask for an incremental load pattern: "Write a MERGE statement to upsert from my staging table."
3. Ask PipelineBot to review your load approach for failure modes and SLA risks.

**Lead expert:** PipelineBot (Alex Rivera) — TPT, CDC, MERGE patterns, load strategies, Airflow integration.

**Starter pattern:**
```sql
MERGE INTO target_table AS tgt
USING staging_table AS src
ON tgt.id = src.id
WHEN MATCHED THEN UPDATE SET col1 = src.col1, updated_at = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN INSERT VALUES (src.id, src.col1, CURRENT_TIMESTAMP);
```

**When you're ready to go deeper:** Ask PipelineBot about TPT configuration, CDC watermark strategies, Airflow DAG patterns for Teradata, or pipeline failure handling.

---

## DBA / Administrator × Optimize Query Performance

**Best first steps:**
1. Paste a slow query and ask Tera: "What's wrong with this query's performance?"
2. Run EXPLAIN and paste the output — ask Tera or QueryBot to interpret it.
3. Ask Tera to generate COLLECT STATISTICS statements for your hot tables.
4. Ask OpsBot whether TASM workload rules are throttling or deprioritising the query.

**Lead experts:** QueryBot (Marcus Chen) for query plan analysis; OpsBot (Keiko Tanaka) for workload and TASM context.

**Starter queries:**
```sql
-- Interpret the query plan
EXPLAIN SELECT * FROM your_schema.your_table WHERE filter_col = 'value';

-- Find stale statistics
SELECT DatabaseName, TableName, FieldName, LastCollectTimeStamp
FROM DBC.StatsTbl
WHERE DatabaseName = 'your_db'
ORDER BY LastCollectTimeStamp ASC
SAMPLE 20;

-- Check active TASM workload rules
SELECT RuleName, Priority, WorkloadName, IsActive
FROM DBC.TDWMRuleV
WHERE IsActive = 'Y'
ORDER BY Priority;
```

**When you're ready to go deeper:** Ask QueryBot to walk through the full EXPLAIN output. Ask OpsBot about workload classification and whether a TASM rule change would help.

---

## DBA / Administrator × General System Health

**Best first steps:**
1. Ask OpsBot for the most important health checks for your system.
2. Ask Tera to write DBC view queries for disk usage, active sessions, and CPU trends.
3. Ask OpsBot about TASM workload classification if you're seeing concurrency issues.

**Lead expert:** OpsBot (Keiko Tanaka) — Viewpoint, TASM, DBC views, capacity planning, cost.

**Starter queries:**
```sql
SELECT UserName, SessionNo, State, AMPCPUTime
FROM DBC.SessionInfoV
WHERE State <> 'Idle'
ORDER BY AMPCPUTime DESC;

SELECT DatabaseName, SUM(CurrentPerm)/1e9 AS UsedGB, SUM(MaxPerm)/1e9 AS AllocGB
FROM DBC.DiskSpaceV
GROUP BY 1
ORDER BY 2 DESC
SAMPLE 15;
```

---

## Data Scientist × Deploy Models / Analytics

**Best first steps:**
1. Ask AnalyticsBot which ClearScape Analytics functions fit your use case.
2. Ask Tera to write the SQL for analytic functions against your tables.
3. Ask AnalyticsBot how to import an external model via BYOM.

**Lead expert:** AnalyticsBot (Dana Okafor) — ClearScape Analytics, VAL, BYOM, ModelOps, teradataml.

**Starter query:**
```sql
SELECT * FROM TD_UnivariateStatistics(
  ON your_schema.your_table
  USING TargetColumns('feature1', 'feature2', 'feature3')
) AS dt;
```

---

## Developer × Learn the Platform / Solve a Specific Problem

**Best first steps:**
1. Describe what you're building and ask Tera to suggest the right SQL patterns, APIs, or tools.
2. Ask Tera to explain the Teradata developer ecosystem — TPT, JDBC/ODBC, REST APIs, QueryGrid.
3. Ask ModelBot to review your schema if you're designing a new data model.

**Lead expert:** QueryBot (Marcus Chen) for SQL patterns; ModelBot (Priya Sharma) for schema; PipelineBot (Alex Rivera) for data movement.

**Starter question:** "I'm building [describe your project]. What Teradata SQL patterns and tools should I know?"

---

## Other / Unknown Role — Fallback

Use the General Quick Start and offer to re-run:
"No worries — here's a general overview to get you started. If you'd like something more tailored, just say 'start over' and pick your role."
