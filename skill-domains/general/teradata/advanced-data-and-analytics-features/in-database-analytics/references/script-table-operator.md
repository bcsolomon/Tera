# SCRIPT Table Operator — Complete Reference

## Architecture

The SCRIPT Table Operator (STO) executes external language scripts (R, Python, shell) directly on each AMP of the Advanced SQL Engine. Each AMP runs an independent instance of the script in a sandboxed `udfscriptsrv` child process.

Data flow:
1. Input rows from ON clause sent to script via stdin (tab-delimited)
2. Script reads stdin, processes data, writes to stdout
3. STO parses stdout per RETURNS clause column definitions
4. Rows returned to SQL engine for further processing

## Full Syntax

```sql
SELECT [DISTINCT] result_columns
FROM SCRIPT (
    ON { table_name | (subquery) }
    [ PARTITION BY col1[, col2...]
      | HASH BY col1[, col2...]
      | PARTITION BY 1 ]              -- all rows to single AMP
    [ ORDER BY col1 [ASC|DESC][, col2 [ASC|DESC]...] ]
    SCRIPT_COMMAND('<shell_command>')
    RETURNS('<col1 type1>[, <col2 type2>, ...]')
    [ DELIMITER('<char>') ]           -- default: tab '\t'
    [ QUOTECHAR('<char>') ]           -- quote character
    [ CHARSET('UTF-8' | 'LATIN') ]   -- character set
)
AS alias;
```

## SCRIPT_COMMAND Patterns

| Language | Command Pattern |
|---|---|
| R | `'Rscript --vanilla ./dbname/script.r'` |
| Python | `'python3 ./dbname/script.py'` |
| Shell | `'bash ./dbname/script.sh'` |
| Inline shell | `'whoami; echo $PATH'` |
| Python inline | `'python3 -c "from math import pi; print(pi)"'` |
| R inline | `'Rscript --vanilla -e "write(pi, stdout())"'` |

### Important: R Options

- `--vanilla` — Prevents R from loading profiles/environment variables that could corrupt output
- `-s` — Silent mode (implied by `Rscript`, needed with `R` command)
- For `R` command use: `R --vanilla -s -f ./dbname/script.r`

### Important: Python Options

- Always use `python3` (not `python`) for Teradata in-nodes Python 3 packages
- If `$PYTHONHOME` errors occur, prefix with: `'export PATH; python3 ./dbname/script.py'`

## Data Distribution (ON clause)

| Pattern | Effect | Use Case |
|---|---|---|
| `ON table` | Each AMP gets its local rows | Independent per-row transforms |
| `PARTITION BY col` | Group by column values | Per-group analytics (e.g., per customer) |
| `PARTITION BY 1` | All rows to one AMP | Global aggregation (use cautiously!) |
| `HASH BY col` | Hash-distribute | Balanced distribution |
| `PARTITION BY col ORDER BY sort_col` | Grouped + sorted | Time series per group |

## RETURNS Clause

Define output columns with name and type:

```sql
RETURNS('col1 INTEGER, col2 FLOAT, col3 VARCHAR(100), col4 DATE')
```

### Supported Types

| SQL Type | Notes |
|---|---|
| `INTEGER` | Standard 32-bit integer |
| `BIGINT` | 64-bit integer |
| `FLOAT` | Double-precision float |
| `DECIMAL(p,s)` | Fixed-point decimal |
| `VARCHAR(n)` | Variable-length string |
| `DATE` | Date value |
| `TIMESTAMP` | Timestamp value |

### Type Handling Tips

- If FLOAT returns cause errors, use `VARCHAR(20)` and CAST in SELECT
- Always ensure VARCHAR is large enough for actual output
- Script must output exactly the number of columns specified in RETURNS

## Script Installation and Management

### Prerequisites

```sql
-- Grant installation permissions
GRANT EXECUTE PROCEDURE ON SYSUIF.INSTALL_FILE TO username;
GRANT EXECUTE PROCEDURE ON SYSUIF.REPLACE_FILE TO username;
GRANT EXECUTE PROCEDURE ON SYSUIF.REMOVE_FILE TO username;

-- Set the search path (REQUIRED every session)
SET SESSION SEARCHUIFDBPATH = myDB;
```

### INSTALL_FILE

```sql
-- Install from Linux path
CALL SYSUIF.INSTALL_FILE('alias', 'filename.py', 'cz!/path/to/file.py');

-- Install from Windows path (when using client tools)
CALL SYSUIF.INSTALL_FILE('alias', 'filename.py', 'cz!C:\\Users\\me\\file.py');

-- Install compiled binary (cb prefix)
CALL SYSUIF.INSTALL_FILE('mybin', 'mybin.out', 'cb!/path/to/binary.out');
```

Arguments:
1. **Alias** — Logical name for the file in the database
2. **Filename** — Physical filename as stored on AMPs
3. **Source** — `cz!` (compressed text) or `cb!` (compressed binary) followed by path

### REPLACE_FILE

```sql
CALL SYSUIF.REPLACE_FILE('alias', 'filename.py', 'cz!/path/to/new_file.py', 1);
```

The 4th argument is the file type: `1` for all types.

### REMOVE_FILE

```sql
CALL SYSUIF.REMOVE_FILE('alias', 1);
```

### Verify Installed Scripts

```sql
-- List installed files
SELECT DISTINCT * FROM SCRIPT (
    SCRIPT_COMMAND('ls ./myDB')
    RETURNS('filename VARCHAR(100)')
);
```

## R Script I/O Pattern

```r
#!/usr/bin/env Rscript

# Read stdin (tab-delimited from STO)
input <- file("stdin", "r")
data <- read.table(input, sep="\t", header=FALSE)
close(input)

# Process
result <- data.frame(
  col1 = data$V1,
  col2 = data$V2 * 2,
  col3 = as.character(Sys.time())
)

# Write to stdout (tab-delimited)
write.table(result, stdout(), sep="\t", row.names=FALSE,
            col.names=FALSE, quote=FALSE)
```

### R Best Practices

- Use `suppressMessages()`, `suppressWarnings()` around `library()` calls
- Use `suppressPackageStartupMessages(library(pkg))` to prevent startup noise
- Wrap `glm()`, `predict()` in `suppressWarnings()` for clean output
- Test scripts locally with sample data before installing

## Python Script I/O Pattern

```python
#!/usr/bin/env python3
import sys

# Read stdin (tab-delimited from STO)
for line in sys.stdin:
    fields = line.strip().split('\t')
    col1 = int(fields[0])
    col2 = float(fields[1])

    # Process
    result = col2 * 2.0

    # Write to stdout (tab-delimited)
    print(f"{col1}\t{result}\t{'processed'}")
```

### Python Best Practices

- Use `warnings.filterwarnings("ignore")` to suppress warnings
- Read all input before processing if needed for global computation
- Always use `sys.stdin` for input and `print()` for output
- Use `sys.stderr` for debug messages (goes to scriptlog, not RETURNS)

## Delimiter Configuration

```sql
-- CSV-style delimiter
SELECT * FROM SCRIPT (
    ON input_data
    SCRIPT_COMMAND('python3 ./myDB/csv_script.py')
    RETURNS('col1 VARCHAR(50), col2 INTEGER')
    DELIMITER(',')
    QUOTECHAR('"')
);
```

Default delimiter is tab (`\t`). Script I/O must match.

## Memory Management

| Parameter | Scope | Description |
|---|---|---|
| `ScriptMemLimit` | Per-AMP | Max memory per STO execution per AMP |
| `GPLUDFServerMemSize` | System | Memory allocated to udfscriptsrv processes |

- R standalone: ~4 MB/AMP; with add-ons: ~130–400 MB/AMP
- Python standalone: ~5 MB/AMP; with add-ons: ~35–180 MB/AMP
- Minimum: 1 GB non-FSG cache free memory per AMP per STO query

## Debugging

### Check Script Logs

```sql
-- View scriptlog (errors/warnings go to stderr → scriptlog)
SELECT DISTINCT * FROM SCRIPT (
    SCRIPT_COMMAND('tail /var/opt/teradata/tdtemp/uiflib/scriptlog')
    RETURNS('logline VARCHAR(256)')
);
```

### Common Error Resolution

| Error | Cause | Fix |
|---|---|---|
| `Failure 9134: output could not be converted` | Script stdout doesn't match RETURNS | Check column count and types |
| `Script not found` | SEARCHUIFDBPATH not set or wrong | `SET SESSION SEARCHUIFDBPATH = myDB;` |
| `not all input could be read` | Memory shortage | Increase ScriptMemLimit |
| `OpenBLAS pthread_create failed` | Too many threads vs resources | Reduce concurrency or increase memory |
| Import errors | Missing package | Install via teradata-R-addons or teradata-python-addons |

## STO Sandbox (Client-Side Testing)

Test scripts locally before deploying to the database:

```python
# Available in Teradata Client Packages
from teradataml import Script

# Test R script
s = Script(script_command='Rscript --vanilla score.r',
           input_data=test_df,
           returns=['col1 INTEGER', 'col2 FLOAT'],
           delimiter=',')
result = s.execute()
```

## Complete Working Examples

### Example: R Model Scoring

```sql
-- Assume model.r reads features and outputs predictions
SET SESSION SEARCHUIFDBPATH = analytics_db;

SELECT customer_id, prediction, probability
FROM SCRIPT (
    ON (SELECT customer_id, age, income, tenure
        FROM mydb.customer_features
        WHERE score_date = CURRENT_DATE)
    PARTITION BY customer_id
    SCRIPT_COMMAND('Rscript --vanilla ./analytics_db/churn_model.r')
    RETURNS('customer_id INTEGER, prediction VARCHAR(10), probability FLOAT')
) AS scores
WHERE probability > 0.7;
```

### Example: Python Data Transformation

```sql
SET SESSION SEARCHUIFDBPATH = etl_db;

INSERT INTO mydb.transformed_data
SELECT *
FROM SCRIPT (
    ON mydb.raw_events
    PARTITION BY event_type
    ORDER BY event_timestamp
    SCRIPT_COMMAND('python3 ./etl_db/transform.py')
    RETURNS('event_id BIGINT, category VARCHAR(50), metric FLOAT, ts TIMESTAMP')
);
```
