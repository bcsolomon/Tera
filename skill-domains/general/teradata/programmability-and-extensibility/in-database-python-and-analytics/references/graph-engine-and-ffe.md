# Graph Engine and Function Framework Engine (FFE) Reference

> **Source:** Teradata Vantage Analytics Database Analytic Functions  
> **Location:** https://docs.teradata.com/r/Enterprise_IntelliFlex_VMware/Analytics-Database-Analytic-Functions  
> **Extraction date:** 2025-07  
> **Topics:** Graph Engine and Function Framework Engine (FFE) Reference

## Graph Engine Architecture

The Graph Engine uses a **Bulk Synchronous Processing (BSP)** model designed for large-scale graph problems. It runs on the same Kubernetes-managed analytic nodes as the ML Engine, sharing the Queen/Worker pod infrastructure.

### Graph Data Model

- **Vertices (nodes)** — entities such as people, locations, accounts, servers, URLs
- **Edges** — relationships such as transactions, phone calls, emails, social connections
- Input requires two tables: a vertices table and an edges table

### BSP Execution Model

1. **Initialization** — graph edge and node data loaded into memory on worker JVMs
2. **Iteration** — each JVM independently processes graph nodes: compute, update state, set local aggregations, construct messages
3. **Synchronization barrier** — global aggregators computed and broadcast; messages sent to graph nodes via ICE
4. **Repeat** — iterations continue until convergence criteria met

> Source: TDN0009803 Section 2.1 — Machine Learning and Graph Engine Architecture

### Graph Function Syntax

```sql
SELECT *
FROM graph_function_name (
  ON vertices_table AS vertices PARTITION BY vertex_key
  ON edges_table AS edges PARTITION BY source_vertex_key
  argument_1 ('value_1')
  argument_2 ('value_2')
) AS DT;
```

Requirements:
- Vertices table must be partitioned by the vertex key
- Edges table must be partitioned by the source vertex key
- Both tables specified in the ON clause with aliases (`AS vertices`, `AS edges`)

> Source: TDN0009803 Section 2.3 — Syntax & Semantics

## Graph Engine Function Catalog

### Centrality and Importance Functions

| Function | Description |
|---|---|
| **Betweenness** | Measures vertex importance by the proportion of shortest paths passing through it. High betweenness = critical bridge in the network. |
| **Closeness** | Measures how quickly a vertex can reach all others. Inverse of total distance to all other vertices. Useful for information delivery speed analysis. |
| **EigenVectorCentrality** | "Important people know important people" — weights nodes by their connections to other high-centrality nodes. Basis for Google's PageRank. |
| **PageRank** | Link analysis algorithm assigning numerical weight (0–1) based on link structure. Sum of all PageRanks = 1. Most famously used by Google for URL relevance. |

> Source: TDN0009803 Table 11 — Graph Engine Functions

### Path and Traversal Functions

| Function | Description |
|---|---|
| **AllPairsShortestPath** | Measures shortest distance between two or more vertices. Includes Single Source Shortest Path (SSSP) variant. Analogous to shortest route on a road map. |
| **GTree** | Graph traversal following all paths from root vertices; computes aggregate functions along traversal paths. |
| **nTree** | Creates hierarchical map of all paths in a decision tree. Useful for discovering root-cause cascades (e.g., stock trade triggers). |

### Community Detection and Clustering

| Function | Description |
|---|---|
| **LocalClusteringCoefficient** | Measures degree to which nodes cluster together. Ratio of connected neighbor pairs to total neighbor pairs. Indicates embeddedness. |
| **Modularity** | Detects communities using clustering algorithm requiring no prior knowledge of cluster centers. Modularity score between -1 and 1; closer to 1 = better community structure. |
| **LoopyBeliefPropagation** | Infers properties of new nodes based on observed attributes of connected nodes. Iterative message-passing until convergence. Used in fraud detection and social network analysis. |

### Ranking and Influence Functions

| Function | Description |
|---|---|
| **PSALSA** | Personalized Stochastic Approach for Link Structure Analysis. Evaluates page/node reachability via random walks. Uses hubs (resource lists) and authorities (definitive content). |
| **RandomWalkSample** | Samples a graph preserving structural properties. Random walk with 0.85 probability of neighbor selection, 0.15 probability of returning to start. Useful when full graph analysis is computationally infeasible. |

> Source: TDN0009803 Table 11 — Graph Engine Functions

## Graph Analytics Examples

### PageRank Calculation

```sql
SELECT *
FROM PageRank (
  ON web_pages AS vertices PARTITION BY page_id
  ON web_links AS edges PARTITION BY source_page_id
  TargetKey ('target_page_id')
  MaxIterNum (50)
  DampFactor (0.85)
) AS DT
ORDER BY page_rank DESC;
```

### Community Detection with Modularity

```sql
SELECT *
FROM Modularity (
  ON social_users AS vertices PARTITION BY user_id
  ON social_connections AS edges PARTITION BY from_user_id
  TargetKey ('to_user_id')
  Resolution (1.0)
) AS DT;
```

### Shortest Path Analysis

```sql
SELECT *
FROM AllPairsShortestPath (
  ON locations AS vertices PARTITION BY location_id
  ON routes AS edges PARTITION BY origin_id
  TargetKey ('destination_id')
  EdgeWeight ('distance_km')
  MaxDistance (1000)
) AS DT;
```

## Function Framework Engine (FFE) — Function Aliasing

### Overview

Function aliasing (also called function mapping) provides a simplified name for executing functions on a foreign server. Instead of the fully qualified `function_name@foreign_server` syntax, users invoke functions by simple name.

### Purpose

- **Abstraction** — hides the execution location from end users
- **Version management** — DBAs can swap underlying function implementations (e.g., `sentiment_production_1` → `sentiment_production_2`) while applications continue using the alias `sentiment`
- **Access control** — GRANT/REVOKE privileges on the alias object rather than the remote function directly
- **Search path resolution** — user default database → SYSLIB → TD_SYSFNLIB

> Source: TDN0009803 Section 4.4 — Foreign Function Aliasing

### DDL Statements

```sql
-- Create a function alias
CREATE FUNCTION MAPPING my_sessionize
FOR sessionize
SERVER coprocessor;

-- Replace an existing alias
REPLACE FUNCTION MAPPING my_sessionize
FOR sessionize_v2
SERVER coprocessor;

-- Show alias definition
SHOW FUNCTION MAPPING my_sessionize;

-- Drop an alias
DROP FUNCTION MAPPING my_sessionize;
```

### Prebuilt Aliases

Vantage ships with prebuilt function aliases for all ML and Graph Engine functions **except** those already ported to the SQL Engine:

**Functions with NO alias (execute on SQL Engine by default):**
- Attribution
- nPath
- Sessionize
- DecisionTreePredict (GLMPredict, Forest_Predict, SVMSparsePredict, NaiveBayesPredict, NaiveBayesTextClassifierPredict)

To force these functions to execute on the ML Engine, use explicit syntax:

```sql
-- Force execution on ML Engine
SELECT * FROM sessionize@COPROCESSOR (
  ON web_clicks PARTITION BY user_id ORDER BY click_time
  TIMECOLUMN('click_time')
  TIMEOUT(60)
) AS DT;
```

**Special cases:**
- `nPath` does not support function aliases due to earlier foreign function syntax differences — must always use `nPath@COPROCESSOR`
- `nTree` also requires explicit `@COPROCESSOR` syntax

> Source: TDN0009803 Section 4.4 — Foreign Function Aliasing

### Grammar Structure

```
SELECT ...
FROM FUNCTION_NAME (
  ON (subquery | table) [AS alias] [USING] PARTITION BY ... ORDER BY ...
  [ON (subquery | table) [AS alias] [USING] PARTITION BY ...]
  [OUT TABLE output_arg_name ('output_table_name')]
  argument_name ('value')
  ...
) AS alias;
```

Key differences between SQL-MR and SQL Engine grammar:

| Feature | SQL-MR (ML Engine) | SQL Engine |
|---|---|---|
| USING clause | Not required | Required between ON and arguments |
| Argument values | Literals only | Scalar sub-queries allowed |
| BOOLEAN data type | Supported | Not supported |
| UNBOUNDED DECIMAL/VARCHAR | Supported | Not supported |
| VARCHAR > 64KB | Supported | Use CLOB (up to 2GB) |
| TRUNCATE TABLE | Supported | Not allowed |
| IF EXISTS clause | Supported | Not allowed |

> Source: TDN0009803 Section 4.5 — Grammar

### Access Rights

```sql
-- Grant execute on a function alias
GRANT EXECUTE FUNCTION ON my_function_alias TO user_name;

-- Revoke execute on a function alias
REVOKE EXECUTE FUNCTION ON my_function_alias FROM user_name;
```

Function alias privileges are logged via extended DBQL and BEGIN/END LOGGING statements.

### Data Dictionary Views

| View | Description |
|---|---|
| `FunctionAliasV` | Function alias definitions |
| `FunctionAliasVX` | Extended function alias definitions |
| `FunctionAliasInfoV` | Function alias metadata |
| `FunctionAliasInfoVX` | Extended function alias metadata |

> Source: TDN0009803 Table 12 — Links to documentation for Aliasing Features

## Administration and Monitoring

### Workload Management for Graph/ML Functions

**Service Class Table** (`nc_system.nc_qos_service_class`):

| Service Class | Priority | Weight | Soft Memory Limit | Hard Memory Limit |
|---|---|---|---|---|
| HighClass | 3 | 90 | 90% | 100% |
| DefaultClass | 2 | 30 | 80% | 90% |
| LowClass | 1 | 5 | 70% | 80% |
| DenyClass | 0 | 1 | 60% | 70% |

**Priority coordination with SQL Engine:**
1. SQL Engine passes workload name to ML/Graph Engine via QueryGrid
2. Queen matches workload name against policy table predicates
3. Matched service class priority applied to the request
4. Unmatched requests default to DefaultClass (medium priority)

**Concurrency limits:**
- QGLimit system throttle on SQL Engine: 10 concurrent ML/Graph requests (tunable)
- ML Engine internal limit: 32 total active functions (master + child tasks)
- Workload-level throttles can further restrict concurrency per priority class

> Source: TDN0009803 Section 6 — Workload Management in Teradata Vantage

### DenyClass Activation

- Triggered when analytic node disk usage exceeds 80%
- Blocks all requests except DROP and TRUNCATE statements
- Background cleanup daemon frees space; RUM deactivates policy when threshold drops
- Returns "Admission Denied" error to blocked requests

### Memory Management

- **Soft limit** — function can exceed allocation when no memory pressure; aborted if contention occurs at exceeded level
- **Hard limit** — absolute ceiling; function aborted immediately upon exceeding regardless of memory availability
- Memory limits defined per service class as percentage of total node memory

> Source: TDN0009803 Section 6.3 — Managing Memory Usage

### Monitoring Cross-Engine Queries

```sql
-- Join SQL Engine DBQL with ML Engine QueryLog on shared Query-ID
SELECT d.QueryID, d.QueryText, d.StartTime,
       c.CpuSecs, c.MemoryKb, c.ReadBytes, c.WriteBytes
FROM DBC.DBQLogTbl d
JOIN TD_Coprocessor_DB.QueryLog c
  ON d.QueryID = c.UUID
WHERE d.StartTime > CURRENT_TIMESTAMP - INTERVAL '1' HOUR;
```

### Security

- Authentication: SQL Engine credentials used; proxy user for JDBC sessions to Queen
- Authorization: GRANT/REVOKE on function aliases controls analytic function access
- Supported methods: TD2, LDAP, Kerberos
- Data encrypted in transit over QueryGrid fabric
- Analytic node OS hardened per CIS/DISA STIG standards

> Source: TDN0009803 Section 10 — Security in Teradata Vantage

## Performance Considerations

- Data redistribution between SQL Engine and analytic nodes adds latency (InfiniBand minimizes this)
- JVM startup cost on Kubernetes adds per-invocation overhead
- In-database SQL Engine functions avoid redistribution overhead but consume AMP resources
- ML Engine functions release all AWTs except one during remote execution
- Use `ORDER BY` with `PARTITION BY` to ensure deterministic results
- Use `SequenceInputBy` argument when partition key is absent and determinism is required
- Spoolspace requirements vary by function — consult per-function guidelines

> Source: TDN0009803 Section 11 — Performance Considerations
