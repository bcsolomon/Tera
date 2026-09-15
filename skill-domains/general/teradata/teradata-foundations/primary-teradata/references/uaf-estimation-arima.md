# Teradata UAF — Estimation and Regression

## TD_ACF

Calculates autocorrelation (or autocovariance) coefficients for a time series at each lag up to MAXLAGS. Used to identify the moving-average (MA) order for ARIMA modeling and to detect non-stationarity.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(acf_results)
TD_ACF(
    { SERIES_SPEC(...) | ART_SPEC(TABLE_NAME(...)) },
    FUNC_PARAMS(
        [MAXLAGS(integer),]
        [FUNC_TYPE({ 0 | 1 }),]
        [QSTAT({ 0 | 1 }),]
        [ALPHA(float),]
        [DEMEAN({ 0 | 1 })]
    )
);
```

### FUNC_PARAMS reference

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `MAXLAGS` | No | `10*log10(N)` | Maximum number of lags to compute |
| `FUNC_TYPE(0\|1)` | No | 0 | 0 = autocorrelation, 1 = autocovariance |
| `QSTAT(0\|1)` | No | 0 | 1 = add Ljung-Box Q-statistic columns (`QSTATVAL`, `PVALUE`) |
| `ALPHA(float)` | No | — | Confidence interval level (e.g., 0.05 for 95%); adds `CONF_OFF`, `CONF_LOW`, `CONF_HI` |
| `DEMEAN(0\|1)` | No | 1 | 0 = do not subtract mean before computing; **warning:** when `QSTAT(1)` is also set, DEMEAN(0) causes all PVALUE columns to be 0 |

No INPUT_FMT. No OUTPUT_FMT. Single-layer ART (ARTPRIMARY only).

### Output schema

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | BIGINT | Lag index |
| `OUT_<field>` | FLOAT | ACF coefficient at each lag; one per payload field |
| `CONF_OFF_<field>` | FLOAT | Bartlett's formula critical value; present only if ALPHA set |
| `CONF_LOW_<field>` | FLOAT | Confidence lower bound; present only if ALPHA set |
| `CONF_HI_<field>` | FLOAT | Confidence upper bound; present only if ALPHA set |
| `QSTATVAL` | FLOAT | Ljung-Box Q-statistic; present only if QSTAT(1) |
| `PVALUE` | FLOAT | Q-statistic p-value; present only if QSTAT(1) |

Input: `REAL` or `MULTIVAR_REAL`. Output matches input dimensionality.

### Example

```sql
EXECUTE FUNCTION INTO VOLATILE ART(acf_results)
TD_ACF(
    SERIES_SPEC(TABLE_NAME(sales_ts), ROW_AXIS(SEQUENCE(seq_no)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales), CONTENT(REAL))),
    FUNC_PARAMS(MAXLAGS(20), FUNC_TYPE(0), QSTAT(1), ALPHA(0.05), DEMEAN(1))
);

SELECT * FROM acf_results;
-- Returns: store_id, ROW_I (lag), OUT_sales, CONF_OFF_sales, CONF_LOW_sales, CONF_HI_sales,
--          QSTATVAL, PVALUE

-- Rename output columns using COLUMNS() syntax
EXECUTE FUNCTION COLUMNS(OUT_sales AS ACF_Coeff) INTO VOLATILE ART(acf_renamed)
TD_ACF(SERIES_SPEC(...), FUNC_PARAMS(MAXLAGS(20), ALPHA(0.05)));
```

---


## TD_PACF

Calculates partial autocorrelation coefficients at each lag, removing the effects of all intervening lags. Where TD_ACF identifies MA order, TD_PACF identifies the AR order. Can accept raw series data or pre-computed TD_ACF output as input.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(pacf_results)
TD_PACF(
    { SERIES_SPEC(...) | ART_SPEC(TABLE_NAME(acf_art)) },
    FUNC_PARAMS(
        ALGORITHM({ LEVINSON_DURBIN | OLS }),
        [INPUT_TYPE({ DATA_SERIES | ACF }),]
        [MAXLAGS(integer),]
        [UNBIASED({ 0 | 1 }),]
        [ALPHA(float)]
    )
);
```

### FUNC_PARAMS reference

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `ALGORITHM` | Yes | — | `LEVINSON_DURBIN` or `OLS` |
| `INPUT_TYPE` | No | `DATA_SERIES` | `DATA_SERIES` = raw series input; `ACF` = pre-computed ACF from a TD_ACF ART |
| `MAXLAGS` | No | `10*log10(N)` | Maximum number of lags |
| `UNBIASED(0\|1)` | No | 0 | 0 = Jenkins & Watts denominator; 1 = Box & Jenkins denominator; only valid with `INPUT_TYPE(DATA_SERIES)` |
| `ALPHA(float)` | No | — | Confidence interval level; adds `CONF_OFF`, `CONF_LOW`, `CONF_HI` columns |

No INPUT_FMT. No OUTPUT_FMT. Single-layer ART (ARTPRIMARY only).

### Output schema

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | BIGINT | Lag index |
| `OUT_<field>` | FLOAT | PACF coefficient at each lag |
| `CONF_OFF_<field>` | FLOAT | Bartlett's formula critical value; present only if ALPHA set |
| `CONF_LOW_<field>` | FLOAT | Confidence lower bound; present only if ALPHA set |
| `CONF_HI_<field>` | FLOAT | Confidence upper bound; present only if ALPHA set |

### Examples

```sql
-- From raw series
EXECUTE FUNCTION INTO VOLATILE ART(pacf_results)
TD_PACF(
    SERIES_SPEC(TABLE_NAME(sales_ts), ROW_AXIS(SEQUENCE(seq_no)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales), CONTENT(REAL))),
    FUNC_PARAMS(ALGORITHM(LEVINSON_DURBIN), MAXLAGS(10), ALPHA(0.05))
);

-- Chain from TD_ACF output — avoids reprocessing the raw series
EXECUTE FUNCTION INTO VOLATILE ART(pacf_from_acf)
TD_PACF(
    ART_SPEC(TABLE_NAME(acf_results)),
    FUNC_PARAMS(ALGORITHM(LEVINSON_DURBIN), INPUT_TYPE(ACF), MAXLAGS(10), ALPHA(0.05))
);
```

---


## TD_ARIMAESTIMATE

Estimates the coefficients of an ARIMA model for seasonal and non-seasonal series. Supports the full Box-Jenkins seasonal ARIMA formula. The most complex estimation function in the UAF — outputs up to five ART layers. The resulting ART is consumed by `TD_ARIMAVALIDATE` and `TD_ARIMAFORECAST`.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(arima_est)
TD_ARIMAESTIMATE(
    SERIES_SPEC(                                       -- primary: series to model
        TABLE_NAME(table_name),
        ROW_AXIS(SEQUENCE(seq_col)),
        SERIES_ID(id_col),
        PAYLOAD(FIELDS(value_col), CONTENT(REAL))
    ),
    [{ SERIES_SPEC(...) | ART_SPEC(...) },]            -- secondary: apply existing model
    FUNC_PARAMS(
        ALGORITHM({ OLE | MLE | MLE_CSS | CSS }),
        CONSTANT({ 0 | 1 }),
        NONSEASONAL(MODEL_ORDER(p, d, q)),
        [SEASONAL(MODEL_ORDER(P, D, Q), PERIOD(n)),]
        [FIT_PERCENTAGE(integer),]
        [COEFF_STATS({ 0 | 1 }),]
        [FIT_METRICS({ 0 | 1 }),]
        [RESIDUALS({ 0 | 1 })]
    ),
    [INPUT_FMT(INPUT_MODE({ ONE2ONE | MANY2ONE | MATCH })),]   -- required only with two inputs
    [OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH }))]  -- ARTFITRESIDUALS and ARTVALDATA only
);
```

### FUNC_PARAMS reference

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `ALGORITHM` | Yes | — | `OLE` (ordinary least estimates), `MLE` (maximum likelihood), `MLE_CSS` (CSS start → MLE), `CSS` (conditional sum-of-squares) |
| `CONSTANT(0\|1)` | Yes | — | 1 = include intercept/constant term |
| `NONSEASONAL(MODEL_ORDER(p,d,q))` | Yes | — | AR order (p), differencing order (d), MA order (q) |
| `SEASONAL(MODEL_ORDER(P,D,Q), PERIOD(n))` | No | — | Seasonal AR (P), differencing (D), MA (Q); periods per season (n) |
| `FIT_PERCENTAGE(integer)` | No | 100 | % of series used for estimation; remainder is holdout for `TD_ARIMAVALIDATE`; must be < 100 to enable validation |
| `COEFF_STATS(0\|1)` | No | 0 | 1 = add STD_ERROR, ZSTAT_VALUE, ZSTAT_PROB to primary layer |
| `FIT_METRICS(0\|1)` | No | 0 | 1 = generate ARTFITMETADATA layer |
| `RESIDUALS(0\|1)` | No | 0 | 1 = generate ARTFITRESIDUALS layer |

> OUTPUT_FMT applies only to ARTFITRESIDUALS and ARTVALDATA — not to the primary coefficients layer.

### Output: five-layer ART

| Layer | Retrieved by | Contents |
|-------|-------------|----------|
| `ARTPRIMARY` | `SELECT *` | Coefficients: INDEX, COEFF_NAME, COEFF_VALUE; +STD_ERROR, ZSTAT_VALUE, ZSTAT_PROB if COEFF_STATS(1) |
| `ARTFITMETADATA` | `TD_EXTRACT_RESULTS` | Goodness-of-fit: R², adjusted R², F-statistic, AIC, MAE, MSE, MAPE |
| `ARTFITRESIDUALS` | `TD_EXTRACT_RESULTS` | ACTUAL_VALUE, CALC_VALUE, RESIDUAL per in-sample observation |
| `ARTMODEL` | `TD_EXTRACT_RESULTS` | Binary model context (VARBYTE 32000) — consumed by TD_ARIMAVALIDATE |
| `ARTVALDATA` | `TD_EXTRACT_RESULTS` | Holdout validation data (the FIT_PERCENTAGE remainder) |

### Example

```sql
EXECUTE FUNCTION INTO VOLATILE ART(arima_est)
TD_ARIMAESTIMATE(
    SERIES_SPEC(
        TABLE_NAME(sales_ts),
        ROW_AXIS(SEQUENCE(seq_no)),
        SERIES_ID(store_id),
        PAYLOAD(FIELDS(sales_amt), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        NONSEASONAL(MODEL_ORDER(1,0,1)),
        ALGORITHM(MLE), CONSTANT(1),
        FIT_PERCENTAGE(70), FIT_METRICS(1), RESIDUALS(1)
    )
);

SELECT * FROM arima_est;   -- primary: coefficient table (COEFF_NAME, COEFF_VALUE, ...)

EXECUTE FUNCTION TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(arima_est), LAYER(ARTFITMETADATA)));
```

---


## TD_ARIMAVALIDATE

Performs in-sample forecasting (validation) on the holdout portion reserved by `TD_ARIMAESTIMATE`'s `FIT_PERCENTAGE` parameter. Provides goodness-of-fit metrics and residuals for model comparison. The output ART is consumed by `TD_ARIMAFORECAST`.

> **`FIT_PERCENTAGE` must have been less than 100 in the preceding `TD_ARIMAESTIMATE` call.** If FIT_PERCENTAGE was 100, there is no holdout to validate against.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(arima_val)
TD_ARIMAVALIDATE(
    ART_SPEC(TABLE_NAME(arima_est)),    -- TABLE_NAME only; no other ART_SPEC params
    FUNC_PARAMS(
        [FIT_METRICS({ 0 | 1 }),]
        [RESIDUALS({ 0 | 1 })]
    )
    [, OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH })) ]  -- ARTFITRESIDUALS only
);
```

### FUNC_PARAMS reference

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `FIT_METRICS(0\|1)` | No | 0 | 1 = generate ARTFITMETADATA |
| `RESIDUALS(0\|1)` | No | 0 | 1 = generate ARTFITRESIDUALS |

No INPUT_FMT options. OUTPUT_FMT applies only to ARTFITRESIDUALS.

### Output: four-layer ART

| Layer | Retrieved by | Contents |
|-------|-------------|----------|
| `ARTPRIMARY` | `SELECT *` | Model selection metrics: NUM_SAMPLES, VAR_COUNT, AIC, SBIC, HQIC, MLR, MSE |
| `ARTFITMETADATA` | `TD_EXTRACT_RESULTS` | Goodness-of-fit: R², adjusted R², ME, MAE, MSE, MAPE, F_STAT, NULL_HYPOTH |
| `ARTFITRESIDUALS` | `TD_EXTRACT_RESULTS` | ACTUAL_VALUE, CALC_VALUE, RESIDUAL per validation observation |
| `ARTMODEL` | `TD_EXTRACT_RESULTS` | Binary model context consumed by `TD_ARIMAFORECAST` |

### Example

```sql
EXECUTE FUNCTION INTO VOLATILE ART(arima_val)
TD_ARIMAVALIDATE(
    ART_SPEC(TABLE_NAME(arima_est)),
    FUNC_PARAMS(FIT_METRICS(1), RESIDUALS(1)),
    OUTPUT_FMT(INDEX_STYLE(FLOW_THROUGH))
);

SELECT * FROM arima_val;    -- primary: model selection metrics (AIC, SBIC, MSE...)

EXECUTE FUNCTION INTO VOLATILE ART(residuals_art)
TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(arima_val), LAYER(ARTFITRESIDUALS)));
SELECT * FROM residuals_art;   -- ACTUAL_VALUE, CALC_VALUE, RESIDUAL
```

---


## TD_AUTOARIMA

Automatically searches for and fits the best ARIMA model based on an information criterion. Eliminates the manual TD_ARIMAESTIMATE → TD_ARIMAVALIDATE comparison cycle. `TD_ARIMAFORECAST` accepts TD_AUTOARIMA output directly.

> **Restrictions — read before using:**
> - Do not mix seasonal and non-seasonal series in one input
> - Do not mix seasonal series with different period attributes in one input
> - `PERIOD` must be explicitly specified for seasonal data — the function cannot infer it from the data; incorrect PERIOD produces inaccurate model selection
> - **Do not run TD_ARIMAVALIDATE on a TD_AUTOARIMA ART** — this returns an error; the returned model is already the best per the chosen criterion
> - Max p+q+P+Q = 5 when `STEPWISE(0)` (grid search)

```sql
EXECUTE FUNCTION INTO ART(autoarima_art)
TD_AUTOARIMA(
    SERIES_SPEC(
        TABLE_NAME(table_name),
        ROW_AXIS(SEQUENCE(seq_col)),
        SERIES_ID(id_col),
        PAYLOAD(FIELDS(value_col), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        [MAX_PQ_NONSEASONAL(p, q),]            -- default (5,5)
        [MAX_PQ_SEASONAL(P, Q),]               -- default (2,2)
        [START_PQ_NONSEASONAL(p, q),]          -- default (0,0); STEPWISE(1) only
        [START_PQ_SEASONAL(P, Q),]             -- default (0,0); STEPWISE(1) only
        [d(integer),]                          -- default -1 (auto search)
        [Ds(integer),]                         -- default -1 (auto search)
        [MAX_d(integer),]                      -- default 2
        [MAX_Ds(integer),]                     -- default 1
        [PERIOD(integer),]                     -- default 1 (non-seasonal)
        [STATIONARY({ 0 | 1 }),]               -- default 0
        [SEASONAL({ 0 | 1 }),]                 -- default 1 (search all models including seasonal)
        [CONSTANT({ 0 | 1 }),]                 -- default 1 (include intercept)
        [ALGORITHM({ CSS_MLE | MLE | CSS }),]  -- default MLE
        [FIT_PERCENTAGE(integer),]             -- default 100
        [INFOR_CRITERIA({ AIC | AICC | BIC }),] -- default AIC
        [STEPWISE({ 0 | 1 }),]                 -- default 0 (grid search)
        [NMODELS(integer),]                    -- default 94; stepwise only
        [MAX_ITERATIONS(integer),]             -- default 100
        [COEFF_STATS({ 0 | 1 }),]              -- adds STD_ERROR, ZSTAT_VALUE, ZSTAT_PROB
        [FIT_METRICS({ 0 | 1 }),]
        [RESIDUALS({ 0 | 1 }),]
        [ARMA_ROOTS({ 0 | 1 }),]               -- generates ARTARMAROOTS layer
        [TEST_NONSEASONAL(ADF),]               -- only ADF supported
        [TEST_SEASONAL(OCSB)]                  -- only OCSB supported
    )
);
```

### Output: up to six-layer ART

| Layer | Generated when | Retrieved by | Contents |
|-------|---------------|-------------|----------|
| `ARTPRIMARY` | Always | `SELECT *` | Best-model coefficients: INDEX, COEFF_NAME, COEFF_VALUE; +stats if COEFF_STATS(1) |
| `ARTFITMETADATA` | FIT_METRICS(1) | `TD_EXTRACT_RESULTS` | Same goodness-of-fit schema as TD_ARIMAESTIMATE |
| `ARTFITRESIDUALS` | RESIDUALS(1) | `TD_EXTRACT_RESULTS` | ACTUAL_VALUE, CALC_VALUE, RESIDUAL |
| `ARTMODEL` | Always | `TD_EXTRACT_RESULTS` | Binary model context (VARBYTE 64000) — consumed by TD_ARIMAFORECAST |
| `ARTICANDORDER` | Always | `TD_EXTRACT_RESULTS` | AIC, SBIC, HQIC, MLR, MSE, MODEL_ORDER (e.g. `"ARIMA(1, 1, 3)"`) |
| `ARTARMAROOTS` | ARMA_ROOTS(1) | `TD_EXTRACT_RESULTS` | ROOTS_NAME, REAL, IMAG, UNIT_CIRCLE — no roots should appear outside the unit circle |

### Two post-AUTOARIMA forecast paths

```sql
-- Path 1: Forecast directly (simplest — no validation step needed or allowed)
EXECUTE FUNCTION INTO VOLATILE ART(forecast)
TD_ARIMAFORECAST(ART_SPEC(TABLE_NAME(autoarima_art)), FUNC_PARAMS(FORECAST_PERIODS(12)));

-- Path 2: Extract order → re-estimate with TD_ARIMAESTIMATE → full manual pipeline
EXECUTE FUNCTION INTO ART(model_order_art)
TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(autoarima_art), LAYER(ARTICANDORDER)));
SELECT MODEL_ORDER FROM model_order_art;  -- e.g. "ARIMA(1, 1, 3)"
-- Use p=1, d=1, q=3 in TD_ARIMAESTIMATE for full validation and auditable results
```

### Example

```sql
EXECUTE FUNCTION INTO ART(myart)
TD_AUTOARIMA(
    SERIES_SPEC(TABLE_NAME(covid_confirm), ROW_AXIS(SEQUENCE(row_axis)),
                SERIES_ID(city), PAYLOAD(FIELDS(cnumber), CONTENT(REAL))),
    FUNC_PARAMS(
        MAX_PQ_NONSEASONAL(3,3),
        STATIONARY(0), STEPWISE(0),
        RESIDUALS(1), ARMA_ROOTS(1)
    )
);

SELECT * FROM myart;   -- coefficients for selected best model
```

---

## TD_DIFF — Series Differencing (Preprocessing for ARIMA)

Computes the differenced series (first or higher-order) to achieve stationarity before ARIMA modeling. Use TD_DIFF when ACF/PACF analysis or the ADF test indicates a non-stationary series (e.g., a trend or unit root). The "d" parameter in ARIMA(p,d,q) corresponds to the differencing order applied here.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(diff_results)
TD_DIFF(
    SERIES_SPEC(
        TABLE_NAME(table_name),
        ROW_AXIS(SEQUENCE(seq_col)),
        SERIES_ID(id_col),
        PAYLOAD(FIELDS(value_col), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        [DIFFERENCES(1),]              -- default 1; order of differencing (1 = first differences, 2 = second differences)
        [LAG(1)]                       -- default 1; seasonal differencing uses LAG equal to the seasonal period (e.g., LAG(12) for monthly)
    )
);
```

### FUNC_PARAMS reference

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `DIFFERENCES(integer)` | No | 1 | Order of differencing; 1 for trend removal, 2 for quadratic trend |
| `LAG(integer)` | No | 1 | Lag between observations; set to seasonal period for seasonal differencing (e.g., 12 for monthly, 4 for quarterly) |

### Typical Workflow
1. Run `TD_ACF` on raw series — if coefficients decay slowly, the series is non-stationary
2. Apply `TD_DIFF(DIFFERENCES(1))` to remove the trend
3. Run `TD_ACF`/`TD_PACF` again on the differenced series to determine p and q
4. Feed the differenced series to `TD_ARIMAESTIMATE` with d=0 (already differenced), or feed the original series with the appropriate d value

> **Note:** `TD_ARIMAESTIMATE` can handle differencing internally via its `NONSEASONAL_MODEL_ORDER(p, d, q)` parameter (d > 0). Using TD_DIFF explicitly is useful when you need to inspect or validate the differenced series before estimation, or when applying seasonal differencing with a non-standard lag.
