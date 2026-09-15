---
name: teradata-query-banding
description: 'Teradata Query Banding for workload classification, session tracking, and application identification. Use when setting query bands (SET QUERY_BAND), using query bands for workload management classification, tracking application sessions, implementing proxy user authentication, or analyzing query band data in DBQL.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Query Banding

## When to Use

- Tagging sessions/transactions with application metadata
- Classifying workloads based on application identity
- Tracking queries by application, module, or user context
- Implementing proxy user patterns
- Analyzing application-level query patterns in DBQL

## SET QUERY_BAND Syntax

```sql
-- Session-level (persists until changed or session ends)
SET QUERY_BAND = 'key1=value1;key2=value2;' FOR SESSION;

-- Transaction-level (cleared at transaction end)
SET QUERY_BAND = 'key1=value1;key2=value2;' FOR TRANSACTION;

-- Clear session query band
SET QUERY_BAND = NONE FOR SESSION;

-- Clear transaction query band
SET QUERY_BAND = NONE FOR TRANSACTION;
```

### Rules

- Format: semicolon-separated key=value pairs, trailing semicolon required
- Keys and values are case-sensitive
- Max total length: 2048 bytes
- Transaction band overrides session band during a transaction
- Both session and transaction bands logged in DBQL

### Common Patterns

```sql
-- Application identification
SET QUERY_BAND = 'ApplicationName=BI_Reports;Module=Dashboard;User=jsmith;' FOR SESSION;

-- ETL job tracking
SET QUERY_BAND = 'JobName=daily_load;JobID=20250615_001;Source=SAP;' FOR SESSION;

-- Analytics workload tagging
SET QUERY_BAND = 'Workload=Analytics;Model=churn_prediction;Team=DataScience;' FOR SESSION;

-- Utility data size hint (reserved name)
SET QUERY_BAND = 'UtilityDataSize=LARGE;' FOR SESSION;
```

## Reserved Query Band Names

| Name | Values | Purpose |
|---|---|---|
| `UtilityDataSize` | `SMALL`, `MEDIUM`, `LARGE` | Hint for utility session allocation |
| `ProxyUser` | Username string | Proxy user identification |

## Proxy User Authentication

```sql
-- Trusted session: connect as service account, identify actual user
SET QUERY_BAND = 'ProxyUser=actual_user;ApplicationName=WebApp;' FOR SESSION;
```

### Trusted Session Setup

```sql
-- Grant permanent proxy user access
GRANT CONNECT THROUGH service_acct TO PERMANENT actual_user;

-- Grant proxy for any user (application proxy)
GRANT CONNECT THROUGH service_acct TO PERMANENT actual_user WITHOUT ROLE;

-- With trust only (prevents query band injection)
GRANT CONNECT THROUGH service_acct WITH TRUST_ONLY;
```

### Proxy User Security Model

- Service account authenticates to the database
- `ProxyUser` query band identifies the actual end user
- `CURRENT_USER` returns the proxy user name for row-level security
- `SESSION_USER` returns the service account name
- With `TRUST_ONLY`, the query band cannot be altered after the initial SET

## Workload Management Classification

Query bands serve as classification criteria in TDWM/TASM:

```
Classification rule:
  Query Band Contains: ApplicationName=BI_Reports
  → Assign to workload: BI_Reporting_WD (SLG Tier 2, 30% allocation)

Classification rule:
  Query Band Contains: Workload=Analytics
  → Assign to workload: Analytics_WD (Timeshare Low)
```

## Reading Query Bands

```sql
-- Current session query band
SELECT GetQueryBandValue(GetQueryBand(), 'ApplicationName');

-- From DBQL
SELECT QueryBand, UserName, AmpCPUTime, TotalIOCount
FROM DBC.DBQLogTbl
WHERE LogDate = CURRENT_DATE
  AND QueryBand LIKE '%ApplicationName=BI_Reports%'
ORDER BY AmpCPUTime DESC;

-- Parse specific key from DBQL
SELECT REGEXP_SUBSTR(QueryBand, 'ApplicationName=([^;]+)', 1, 1, 'c', 1) AS app_name,
       COUNT(*) AS query_count,
       SUM(AmpCPUTime) AS total_cpu
FROM DBC.DBQLogTbl
WHERE LogDate = CURRENT_DATE
  AND QueryBand IS NOT NULL
GROUP BY app_name
ORDER BY total_cpu DESC;
```

## DBQL Query Band Analysis

```sql
-- Top applications by resource consumption
SELECT REGEXP_SUBSTR(QueryBand, 'ApplicationName=([^;]+)', 1, 1, 'c', 1) AS app,
       COUNT(*) AS queries,
       SUM(AmpCPUTime) AS cpu_sec,
       SUM(TotalIOCount) AS io_count,
       AVG(TotalFirstRespTime) AS avg_response
FROM DBC.DBQLogTbl
WHERE LogDate >= CURRENT_DATE - 7
  AND QueryBand IS NOT NULL
GROUP BY app
ORDER BY cpu_sec DESC;

-- Track specific ETL job
SELECT QueryID, StartTime, TotalFirstRespTime, AmpCPUTime, SpoolUsage
FROM DBC.DBQLogTbl
WHERE LogDate = CURRENT_DATE
  AND QueryBand LIKE '%JobName=daily_load%'
ORDER BY StartTime;
```

## Best Practices

- Always set query bands in application connection initialization
- Use consistent key names across applications
- Include at minimum: `ApplicationName`, `Module`, `User`
- Use `UtilityDataSize` for ETL utilities to get proper session allocation
- Trailing semicolon is mandatory: `'key=value;'` not `'key=value'`
- Avoid storing sensitive data (passwords, tokens) in query band values — they are logged in DBQL
- Keep total query band length well under the 2048-byte limit to avoid truncation
- Use transaction-level bands for short-lived context that should not persist

## DBS Control Configuration

| Parameter | Description | Default |
|---|---|---|
| `MaxSetQueryBandSize` | Maximum query band string length in bytes | 2048 |
| `Ignore Query Band Values` | Profile-level override — ignore application-set query bands and use profile defaults instead | OFF |

## Profile-Based Query Bands

```sql
-- Set default query band at profile level
CREATE PROFILE bi_profile AS
  DEFAULT QUERY_BAND = 'ApplicationName=BI;Tier=2;' FOR SESSION;

-- Override NOT allowed — profile takes precedence
MODIFY PROFILE bi_profile AS
  QUERY_BAND = 'ApplicationName=BI;Tier=2;' NOT DEFAULT FOR SESSION;
```

Profile query bands (=P>) have lowest precedence. Session bands (=S>) override profile bands. Transaction bands (=T>) override both.

## Query Band Precedence

```
Transaction band (=T>)  ← highest priority
    ↓ overrides
Session band (=S>)
    ↓ overrides
Profile band (=P>)      ← lowest priority
```

When WLM classification evaluates query bands, it checks transaction-level first. If no match, it falls back to session-level, then profile-level.

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-query-banding", path="references/FILENAME")` — do NOT call `list`.

Load these files for detailed technical reference on specific topics:

- **references/query-band-syntax-and-reserved-names.md** — Advanced SET QUERY_BAND syntax (UPDATE mode, VOLATILE, parameter markers), profile query bands (CREATE/MODIFY PROFILE), query band precedence (=T>/=S>/=P>), complete reserved name catalog (base, optional, system, QueryGrid, utility names), max length history and DBS Control config, system functions (GetQueryBandValue, GetQueryBandPairs, MonitorQueryBand), feature history by release
- **references/trusted-sessions-and-wlm-integration.md** — Trusted sessions (GRANT CONNECT THROUGH, application/permanent proxy users, proxy user groups), proxy user lifecycle, row-level security with CURRENT_USER, TRUST_ONLY for injection prevention, WLM integration (filter rules, workload classification with query bands), DBQL analysis patterns (GetQueryBandValueSF queries), client API integration (JDBC, BTEQ, .NET), error handling, performance considerations
- **references/client-api-and-bi-integration.md** — Client API query band code (JDBC basic/parameterized/connection pool, .NET TdQueryBand class, ODBC/CLIv2, BTEQ scripts), JDBC TRUST_ONLY with teradata_untrusted escape, ThreadLocalContext pattern (console/servlet filter/query prepend), profile-based enforcement (DEFAULT/NOT DEFAULT, Ignore Query Band Values), MicroStrategy VLDB variable mapping and Pre/Post-SQL config, IBM Cognos XML command blocks (open/close connection, LDAP parameterization, priority-based data sources), DBS Control MaxSetQueryBandSize, VOLATILE option
