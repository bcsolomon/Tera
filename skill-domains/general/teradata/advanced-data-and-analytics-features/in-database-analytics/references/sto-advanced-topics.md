# STO Advanced Topics — Resource Management, Patterns & Deployment

> Source: TDN0006543-4.3.2 — R and Python Analytics with SCRIPT Table Operator

## Multi-Model Fitting & Scoring Pattern

### Concept

Train separate models per partition (e.g., per product, per region), store models as CLOBs, then score with a second STO call.

### Model Serialization

| Language | Serialize | Deserialize |
|---|---|---|
| R | `caTools::base64encode(serialize(model, NULL))` | `unserialize(caTools::base64decode(clob_str))` |
| Python | `base64.b64encode(pickle.dumps(model)).decode()` | `pickle.loads(base64.b64decode(clob_str))` |

**Gotcha:** Never use `rawToChar()` in R — retains `\n` characters that break CLOB return.

### SQL Pattern — Partition-Based Training

```sql
CREATE MULTISET TABLE models_tbl AS (
    SELECT * FROM SCRIPT(
        ON (SELECT * FROM training_data) PARTITION BY product_id
        SCRIPT_COMMAND('Rscript --vanilla ./myDB/fit_model.r')
        RETURNS('product_id VARCHAR(20)', 'model CLOB')
    )
) WITH DATA;
```

**Always use `CREATE MULTISET TABLE`** — default SET tables silently drop duplicate scored rows.

### SQL Pattern — Scoring with Stored Models

```sql
SELECT * FROM SCRIPT(
    ON (
        SELECT d.*, m.model
        FROM scoring_data d
        JOIN models_tbl m ON d.product_id = m.product_id
    ) PARTITION BY product_id
    SCRIPT_COMMAND('Rscript --vanilla ./myDB/score_model.r')
    RETURNS('product_id VARCHAR(20)', 'prediction FLOAT')
);
```

## System-Wide Parallelization (Map-Reduce)

### Concept

Nested STO calls — inner STO maps computation across AMPs, outer STO reduces results.

### Critical Design Rule

The reduce step must use a **constant column** (e.g., `CompanyID`) to hash all intermediate results to a single AMP.

```sql
SELECT * FROM SCRIPT(
    ON (
        SELECT * FROM SCRIPT(
            ON (SELECT * FROM data) PARTITION BY dept_category
            SCRIPT_COMMAND('Rscript --vanilla ./myDB/map_local.r')
            RETURNS('key INT', 'category INT', 'avg_val FLOAT', 'n_items INT')
        )
    ) PARTITION BY key   -- constant value → all rows to one AMP
    SCRIPT_COMMAND('Rscript --vanilla ./myDB/reduce_global.r')
    RETURNS('global_result FLOAT')
);
```

**Gotcha:** Simple averaging of partial averages is mathematically **wrong** — must compute weighted sum where $w_d = N_d / N$.

### CALCMATRIX Interaction

```sql
SELECT * FROM SCRIPT(
    ON (
        SELECT * FROM CALCMATRIX(
            ON (SELECT cols FROM data_tbl) HASH BY SESSION
            CALCTYPE('ESSCP')    -- Corrected Extended Sum of Squares and Cross Products
        )
    )
    SCRIPT_COMMAND('Rscript --vanilla ./myDB/analyze.r')
    RETURNS('variable VARCHAR(20)', 'estimate FLOAT')
);
```

`HASH BY SESSION` routes all CALCMATRIX output to a single AMP using the built-in `SESSION` function.

## Memory Management

### Key Parameters

| Parameter | Scope | Location | Default | Max |
|---|---|---|---|---|
| `ScriptMemLimit` | STO per-AMP per-query | `cufconfig` GDO | 32 MB | 3.5 GB |
| `GPLUDFServerMemSize` | ExecR per-AMP per-query | `cufconfig` GDO | 3.5 GB | 3.5 GB |

### Setting ScriptMemLimit

```bash
# Set to 3.5 GB (recommended for ML workloads)
psh "printf 'ScriptMemLimit: 3758096384' > /tmp/ccChange.txt"
psh /usr/tdbms/bin/cufconfig -i -f /tmp/ccChange.txt

# Verify
/usr/tdbms/bin/cufconfig -o

# Cleanup
yes | psh rm /tmp/ccChange.txt
```

### Memory Formula

Available memory per AMP per query:

$$\text{TAFM} = \frac{\text{Total\_Memory} \times (1 - \text{FSG\%})}{\text{AMPs\_per\_node} \times \text{concurrency}}$$

### Memory Consumption by Language

| Language | Interpreter Only | + Selected Add-ons | + All Add-ons |
|---|---|---|---|
| R | ~4 MB/AMP | ~130 MB/AMP | ~400 MB/AMP |
| Python | ~5 MB/AMP | ~35 MB/AMP | ~180 MB/AMP |

### tdstoMemInspect Utility

```bash
# Normal mode (reads system values)
./tdstoMemInspect.sh

# Simulation mode (manual inputs)
./tdstoMemInspect.sh -s
# Prompts for: AMP count, memory limits, total memory, FSG%, concurrency
```

Reports TAFM per AMP per query and recommends `ScriptMemLimit` value.

## CPU & Concurrency (TASM/WLM Setup)

### TASM Configuration Steps

1. **Create workload** — Workload Designer → new ruleset → new workload "STO_Workload" (Timeshare)
2. **Classification** — Add Target → Function type → Include `TD_SYSFNLIB.SCRIPT` and `TD_SYSGPL.EXECR`
3. **Virtual partition** — Create "TO_Partition", assign workload, set allocation % (low single digits)
4. **Concurrency throttle** — Set limit, use "Delay" mode (not "Reject")
5. **Activate ruleset**

### Concurrency Guidelines

| Concurrency | Memory/Query | Use Case |
|---|---|---|
| 1 | Maximum | Large ML models, development |
| 2 | Half | Moderate workloads |
| 3 (max recommended) | Third | Production, small scripts |

- **Delay** mode queues excess queries until a slot opens
- **Reject** mode discards with "TDWM Throttle violation" error
- Soft limits preferred over hard/fixed limits

## Package Installation

### DBS Control Flags

| Flag | Number | Required Value | Purpose |
|---|---|---|---|
| `LanguagesSupportPurchased` | 382 | TRUE | Enable SCRIPT TO |
| `PurchasedRTableoperator` | 316 | TRUE | Enable ExecR TO |
| `DisableClientRoutineCreation` | 618 | FALSE | Allow script uploads |

### RPM Packages

| Package | Contents |
|---|---|
| `teradata-R` | Base R interpreter |
| `teradata-R-addons` | R add-on packages (caTools, forecast, etc.) |
| `teradata-python` | Python 3 interpreter (`tdpython3`) |
| `teradata-python-addons` | Python packages (numpy, pandas, scikit-learn, etc.) |

### Installation via PUT

1. Place RPMs in `/var/opt/teradata/customermodepkgs/` on PDN node
2. Access PUT tool via browser (port 8443)
3. Install packages through PUT interface

### Manual CLI Installation

```bash
pcl -send /root/myPackage.rpm /tmp
psh "rpm -Uvh /tmp/myPackage.rpm"
```

### Removal Order (Dependencies)

- R: `teradata-udfgpl` → `teradata-R-addons` → `teradata-R`
- Python: `teradata-python-addons` → `teradata-python`

### List Installed Packages via STO

```sql
-- R packages
SELECT DISTINCT RAddOns FROM SCRIPT(
    SCRIPT_COMMAND('Rscript -e "x <- installed.packages(); x[, c(1,3)]"')
    RETURNS('RAddOns VARCHAR(80)')
);

-- Python packages
SELECT DISTINCT PythonAddOns FROM SCRIPT(
    SCRIPT_COMMAND('tdpip3 freeze')
    RETURNS('PythonAddOns VARCHAR(80)')
);
```

### Add-on Package Installation

```bash
# R — install from CRAN mirror or local
psh "Rscript -e \"install.packages('mypackage', repos='file:///tmp/R_packages')\""

# Python — install from local wheel
psh "tdpip3 install /tmp/mypackage.whl --no-deps"
```

## Client Packages — tdplyr & teradataml

### Script() Function

| Operation | R (tdplyr) | Python (teradataml) |
|---|---|---|
| Create Script | `Script(data=..., script.command=..., returns=list(...))` | `Script(data=..., script_command=..., returns=OrderedDict(...))` |
| Install file | `td_install_file()` | `install_file()` |
| Remove file | `td_remove_file()` | `remove_file()` |
| Test (sandbox) | `td_test_script(inputfile=...)` | `test_script(inputfile=...)` |
| Execute | `td_execute_script()` | `execute_script()` |

### Extra Permissions (Cross-Database)

```sql
GRANT EXECUTE FUNCTION ON td_sysfnlib.script TO myDB WITH GRANT OPTION;
GRANT EXECUTE ON SYSUIF.DEFAULT_AUTH TO myDB WITH GRANT OPTION;
```

## STO Sandbox

- Docker image emulating single-AMP environment
- Language-specific images (R and Python separately)
- **For correctness testing only** — not for scaling tests
- Download from `downloads.teradata.com`

## Best Practices

1. **Never invoke ML Engine analytic functions from in-nodes scripts** — N AMPs = N simultaneous calls, causing resource exhaustion
2. **Test scripts in STO Sandbox first** — catches data type mismatches before deployment
3. **Use `SET SESSION SEARCHUIFDBPATH`** — required for script file resolution
4. **Monitor with `tdstoMemInspect.sh`** — validate memory headroom before production deployment
5. **Start concurrency at 1** — increase only after validating memory consumption
6. **Use MULTISET tables** for model/prediction output — SET tables silently deduplicate
7. **Default delimiter is tab** — match script I/O parsing to tab-delimited format
8. **Use Sparse Maps** to reduce memory when input data has many columns but script uses few
