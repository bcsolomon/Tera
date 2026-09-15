# Teradata UAF — Estimation and Regression

## ARIMA Modeling Workflow

### Which approach to use

**Use TD_AUTOARIMA when:**
- All input series share the same type (all seasonal at the same period, or all non-seasonal)
- Automatic model selection is acceptable — no need to compare candidate models manually
- Exploration or prototyping phase

**Use TD_ARIMAESTIMATE when:**
- You need explicit control over model order (p, d, q, P, D, Q)
- Input mixes series types or seasonal periods (TD_AUTOARIMA errors on mixed input)
- You want TD_ARIMAVALIDATE diagnostics to rigorously compare candidate models
- Production workflows where model choice must be auditable

### Manual ARIMA pipeline (non-seasonal series)

```sql
-- 1. Check for unit roots — see uaf-diagnostics for TD_DICKEY_FULLER
EXECUTE FUNCTION INTO VOLATILE ART(df_result)
TD_DICKEY_FULLER(SERIES_SPEC(TABLE_NAME(sales_ts), ...), ...);

-- 2. Difference to eliminate unit roots
EXECUTE FUNCTION INTO VOLATILE ART(diff_series)
TD_DIFF(
    SERIES_SPEC(TABLE_NAME(sales_ts), ROW_AXIS(SEQUENCE(seq_no)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales), CONTENT(REAL))),
    FUNC_PARAMS(LAG(1), DIFFERENCES(1), SEASONAL_MULTIPLIER(0))
);

-- 3. Verify stationarity — re-run TD_DICKEY_FULLER on diff_series

-- 4. Identify AR/MA order using ACF and PACF
EXECUTE FUNCTION INTO VOLATILE ART(acf_art)
TD_ACF(SERIES_SPEC(TABLE_NAME(diff_series), ...), FUNC_PARAMS(MAXLAGS(20), ALPHA(0.05)));
EXECUTE FUNCTION INTO VOLATILE ART(pacf_art)
TD_PACF(SERIES_SPEC(TABLE_NAME(diff_series), ...), FUNC_PARAMS(ALGORITHM(LEVINSON_DURBIN), ALPHA(0.05)));

-- 5. Estimate model (FIT_PERCENTAGE < 100 reserves holdout for validation)
EXECUTE FUNCTION INTO VOLATILE ART(arima_est)
TD_ARIMAESTIMATE(
    SERIES_SPEC(TABLE_NAME(sales_ts), ROW_AXIS(SEQUENCE(seq_no)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales_amt), CONTENT(REAL))),
    FUNC_PARAMS(
        NONSEASONAL(MODEL_ORDER(1,1,1)),
        ALGORITHM(MLE), CONSTANT(1),
        FIT_PERCENTAGE(80), FIT_METRICS(1), RESIDUALS(1)
    )
);

-- 6. Validate on holdout portion
EXECUTE FUNCTION INTO VOLATILE ART(arima_val)
TD_ARIMAVALIDATE(
    ART_SPEC(TABLE_NAME(arima_est)),
    FUNC_PARAMS(FIT_METRICS(1), RESIDUALS(1))
);

-- 7. Inspect residuals with diagnostic tests — see uaf-diagnostics
-- (TD_DURBIN_WATSON, TD_PORTMAN, TD_DICKEY_FULLER on residuals)

-- 8. Forecast future periods — see uaf-forecasting
EXECUTE FUNCTION INTO VOLATILE ART(forecast)
TD_ARIMAFORECAST(ART_SPEC(TABLE_NAME(arima_val)), FUNC_PARAMS(FORECAST_PERIODS(12)));
SELECT * FROM forecast;
```

### Manual ARIMA pipeline (seasonal series with normalization)

When seasonal patterns create non-stationarity, normalize before modeling and restore scale after forecasting:

```sql
-- 1. Detect unit roots, then normalize to remove seasonal fluctuations
EXECUTE FUNCTION INTO VOLATILE ART(norm_series)
TD_SEASONALNORMALIZE(
    SERIES_SPEC(TABLE_NAME(sales_ts), ROW_AXIS(TIMECODE(sale_date)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales), CONTENT(REAL)),
                INTERVAL(CAL_MONTHS(1))),              -- INTERVAL is required
    FUNC_PARAMS(SEASON_CYCLE(CYCLES("CAL_YEARS"), DURATION(1)))
);
-- ARTMETADATA layer stores per-interval mean and SD — needed by TD_UNNORMALIZE

-- 2. Verify stationarity on normalized series; estimate, validate, forecast as above

-- 3. After forecasting, restore original scale
EXECUTE FUNCTION INTO VOLATILE ART(final_forecast)
TD_UNNORMALIZE(
    SERIES_SPEC(TABLE_NAME(forecasted_norm), ROW_AXIS(TIMECODE(ROW_I)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales), CONTENT(REAL)),
                INTERVAL(CAL_MONTHS(1))),              -- must match TD_SEASONALNORMALIZE call
    ART_SPEC(TABLE_NAME(norm_series), LAYER(ARTMETADATA),
             PAYLOAD(FIELDS(MEAN_sales, SD_sales), CONTENT(MULTIVAR_REAL))),
    INPUT_FMT(INPUT_MODE(MATCH)),
    OUTPUT_FMT(INDEX_STYLE(FLOW_THROUGH))
);
```

### Auto ARIMA pipeline

```sql
-- 1. Auto-select best model and estimate
EXECUTE FUNCTION INTO ART(autoarima_art)
TD_AUTOARIMA(
    SERIES_SPEC(TABLE_NAME(sales_ts), ROW_AXIS(SEQUENCE(seq_no)),
                SERIES_ID(store_id), PAYLOAD(FIELDS(sales), CONTENT(REAL))),
    FUNC_PARAMS(MAX_PQ_NONSEASONAL(3,3), INFOR_CRITERIA(AIC), STEPWISE(0), RESIDUALS(1))
);

-- 2. Inspect selected model order (always generated in ARTICANDORDER layer)
EXECUTE FUNCTION INTO ART(model_order_art)
TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(autoarima_art), LAYER(ARTICANDORDER)));
SELECT * FROM model_order_art;   -- MODEL_ORDER: e.g. "ARIMA(1, 1, 3)"

-- 3. Forecast directly — TD_ARIMAVALIDATE is not valid on TD_AUTOARIMA output
EXECUTE FUNCTION INTO VOLATILE ART(forecast)
TD_ARIMAFORECAST(ART_SPEC(TABLE_NAME(autoarima_art)), FUNC_PARAMS(FORECAST_PERIODS(12)));
SELECT * FROM forecast;
```

---


## TD_DIFF

Performs non-seasonal differencing, seasonal differencing, or a combination. Used to transform a non-stationary series into a stationary series by removing trends and seasonality.

> **Workflow:** Detect unit roots with `TD_DICKEY_FULLER` (see `uaf-diagnostics`) → apply `TD_DIFF` → verify stationarity with a second `TD_DICKEY_FULLER` call.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(diff_results)
TD_DIFF(
    { SERIES_SPEC(...) | ART_SPEC(TABLE_NAME(...)) },
    FUNC_PARAMS(
        LAG(integer),
        DIFFERENCES(integer),
        SEASONAL_MULTIPLIER(integer)
    )
);
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `LAG` | Yes | Zero or positive integer |
| `DIFFERENCES` | Yes | Zero or positive integer |
| `SEASONAL_MULTIPLIER` | Yes | Zero or positive integer — combined with LAG and DIFFERENCES to determine the differencing formula |

No INPUT_FMT. No OUTPUT_FMT. Single-layer ART (ARTPRIMARY only).

### Output schema

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | INTEGER | NUMERICAL_SEQUENCE index |
| `OUT_<field>` | FLOAT | Differenced values; one column per payload field |

`REAL` input produces `REAL` output; `MULTIVAR_REAL` input produces `MULTIVAR_REAL` output.

### Example

```sql
EXECUTE FUNCTION INTO VOLATILE ART(diff_results)
TD_DIFF(
    SERIES_SPEC(
        TABLE_NAME(ocean_buoys),
        ROW_AXIS(TIMECODE(TD_TIMECODE)),
        SERIES_ID(Ocean_Name, BuoyID),
        PAYLOAD(FIELDS(SALINITY), CONTENT(REAL))
    ),
    FUNC_PARAMS(LAG(1), DIFFERENCES(2), SEASONAL_MULTIPLIER(0))
);

SELECT * FROM diff_results;
-- Returns: Ocean_Name, BuoyID, ROW_I, OUT_SALINITY
```

---


## TD_UNDIFF

Reverses a previous `TD_DIFF` operation, reconstructing the original series. Used during the forecasting phase to restore the original scale after modeling on a differenced series.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(undiff_results)
TD_UNDIFF(
    { SERIES_SPEC(differenced_series) | ART_SPEC(TABLE_NAME(...)) },
    [ SERIES_SPEC(original_series), ]             -- required if INITIAL_VALUES not provided
    FUNC_PARAMS(
        LAG(integer),
        DIFFERENCES(integer),
        SEASONAL_MULTIPLIER(integer)
        [, INITIAL_VALUES(float [, float ...]) ]   -- required if secondary SERIES_SPEC not provided
    ),
    INPUT_FMT(INPUT_MODE({ ONE2ONE | MANY2ONE | MATCH })),  -- required with two inputs
    [OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH }))]
);
```

### Two reconstruction modes

| Mode | Primary input | Initial values source |
|------|--------------|----------------------|
| Two-input | Differenced SERIES_SPEC or ART_SPEC | Secondary SERIES_SPEC referencing original series — function derives initial values |
| One-input | Differenced SERIES_SPEC or ART_SPEC | `INITIAL_VALUES` list: LAG=1 requires 1 value, LAG=2 requires 2 values, etc. |

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `LAG` | Yes | Must match the value used in the originating `TD_DIFF` call |
| `DIFFERENCES` | Yes | Must match the value used in the originating `TD_DIFF` call |
| `SEASONAL_MULTIPLIER` | Yes | Must match the value used in the originating `TD_DIFF` call |
| `INITIAL_VALUES` | Conditional | Required when no secondary SERIES_SPEC is provided |

INPUT_FMT is mandatory when using two inputs. OUTPUT_FMT: NUMERICAL_SEQUENCE (default) or FLOW_THROUGH.

### Output schema

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | INTEGER | Index of result series |
| `OUT_<field>` | REAL | Restored values; one per payload field |

### Example: two-input mode

```sql
EXECUTE FUNCTION INTO VOLATILE ART(undiff_results)
TD_UNDIFF(
    SERIES_SPEC(TABLE_NAME(diff_results), SERIES_ID(BuoyId),
                ROW_AXIS(SEQUENCE(ROW_I)), PAYLOAD(FIELDS(MAG), CONTENT(REAL))),
    SERIES_SPEC(TABLE_NAME(buoy_data), SERIES_ID(BuoyId),
                ROW_AXIS(SEQUENCE(SeqNo)), PAYLOAD(FIELDS(Mag), CONTENT(REAL))),
    FUNC_PARAMS(LAG(1), DIFFERENCES(1), SEASONAL_MULTIPLIER(0)),
    INPUT_FMT(INPUT_MODE(MATCH))
);
```

---


## TD_SEASONALNORMALIZE

Normalizes a time series by dividing it into seasonal cycles and intervals, then averaging and normalizing each interval across all cycles. Produces a stationary series suitable for ARIMA modeling. Normalization formula: `(value − mean) / SD` per interval.

> **`INTERVAL` is required in SERIES_SPEC** — unlike most UAF functions where it is optional. The `ARTMETADATA` layer stores per-interval mean and SD that `TD_UNNORMALIZE` uses to reverse the transform.

> **Workflow:** `TD_DICKEY_FULLER` → `TD_SEASONALNORMALIZE` → `TD_DICKEY_FULLER` (verify) → estimate → validate → forecast → `TD_UNNORMALIZE`

```sql
EXECUTE FUNCTION INTO VOLATILE ART(norm_series)
TD_SEASONALNORMALIZE(
    SERIES_SPEC(
        TABLE_NAME(table_name),
        ROW_AXIS(TIMECODE(timecode_col)),
        SERIES_ID(id_col),
        PAYLOAD(FIELDS(value_col), CONTENT(REAL)),
        INTERVAL(CAL_MONTHS(1))                    -- required; defines the interval size
    ),
    FUNC_PARAMS(
        SEASON_CYCLE(
            CYCLES("CAL_YEARS"),                   -- time-unit of one seasonal cycle
            DURATION(1)                            -- number of CYCLES units per season
        )
        [, SEASON_INFO({ 0 | 1 | 2 | 3 }) ]
    )
    [, OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH })) ]
);
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `SEASON_CYCLE` | Yes | Groups CYCLES and DURATION to define the seasonal period |
| `CYCLES` | Yes | Time-unit of one seasonal cycle: `CAL_MONTHS`, `CAL_DAYS`, `WEEKS`, `DAYS`, `HOURS`, `MINUTES`, `SECONDS`, `MILLISECONDS`, `MICROSECONDS` |
| `DURATION` | Yes | Number of CYCLES units per seasonal cycle |
| `SEASON_INFO(0\|1\|2\|3)` | No | Extra columns: 0 = none (default), 1 = SEASON_NO, 2 = CYCLE_NO, 3 = both |

No INPUT_FMT. OUTPUT_FMT: NUMERICAL_SEQUENCE (default) or FLOW_THROUGH.

### Output: two-layer ART

**Primary (ARTPRIMARY):**

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | Varies | Index; type depends on OUTPUT_FMT |
| `SEASON_NO` | BIGINT | Season number within cycle; present when SEASON_INFO is 1 or 3 |
| `CYCLE_NO` | BIGINT | Cycle sequence number; present when SEASON_INFO is 2 or 3 |
| payload field | FLOAT | Normalized values |

**Secondary (ARTMETADATA):**

| Column | Type | Description |
|--------|------|-------------|
| `MEAN_<field>` | FLOAT | Mean for each interval (season) |
| `SD_<field>` | FLOAT | Standard deviation for each interval (season) |

### Example

```sql
-- Normalize store sales: monthly intervals, yearly seasonal cycle
EXECUTE FUNCTION INTO VOLATILE ART(norm_store_sales)
TD_SEASONALNORMALIZE(
    SERIES_SPEC(TABLE_NAME(StoreSales), ROW_AXIS(TIMECODE(TD_TIMECODE)),
                SERIES_ID(StoreID), PAYLOAD(FIELDS(Sales), CONTENT(REAL)),
                INTERVAL(CAL_MONTHS(1))),
    FUNC_PARAMS(SEASON_CYCLE(CYCLES("CAL_YEARS"), DURATION(1)), SEASON_INFO(3)),
    OUTPUT_FMT(INDEX_STYLE(FLOW_THROUGH))
);

-- Retrieve normalization metadata (consumed by TD_UNNORMALIZE)
EXECUTE FUNCTION INTO VOLATILE ART(norm_metadata)
TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(norm_store_sales), LAYER(ARTMETADATA)));
SELECT * FROM norm_metadata;
-- Returns: StoreID, ROW_I, MEAN_Sales, SD_Sales (one row per interval per series)
```

---


## TD_UNNORMALIZE

Reverses a previous `TD_SEASONALNORMALIZE` operation, restoring the original scale. Used at the end of the forecast pipeline to convert forecasted normalized values back to original units.

> **`INTERVAL` in the primary SERIES_SPEC must match the `INTERVAL` used in the originating `TD_SEASONALNORMALIZE` call.**

> The secondary ART_SPEC requires `LAYER(ARTMETADATA)` and `PAYLOAD` explicitly — unlike typical ART_SPEC usage where these are optional.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(unnorm_results)
TD_UNNORMALIZE(
    SERIES_SPEC(normalized_series, ..., INTERVAL(CAL_MONTHS(1))),  -- INTERVAL must match
    { SERIES_SPEC(metadata_table, ...)
    | ART_SPEC(TABLE_NAME(norm_art),
               LAYER(ARTMETADATA),
               PAYLOAD(FIELDS(MEAN_field, SD_field [, ...]), CONTENT(MULTIVAR_REAL))) },
    [FUNC_PARAMS(FIELDS(integer_list)),]       -- optional; 1-based positions to unnormalize
    INPUT_FMT(INPUT_MODE({ ONE2ONE | MANY2ONE | MATCH })),
    [OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH }))]
);
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `FIELDS(integer_list)` | No | 1-based field positions to unnormalize; default = all payload fields |

### Output schema

Single-layer ART (ARTPRIMARY only). Output column names are the **original payload field names** — no `OUT_` prefix.

### Example: feeding ARTMETADATA directly from TD_SEASONALNORMALIZE ART

```sql
EXECUTE FUNCTION INTO VOLATILE ART(final_forecast)
TD_UNNORMALIZE(
    SERIES_SPEC(TABLE_NAME(forecasted_norm), SERIES_ID(StoreID),
                ROW_AXIS(TIMECODE(ROW_I)), PAYLOAD(FIELDS(Sales), CONTENT(REAL)),
                INTERVAL(CAL_MONTHS(1))),
    ART_SPEC(TABLE_NAME(norm_store_sales),
             LAYER(ARTMETADATA),
             PAYLOAD(FIELDS(MEAN_Sales, SD_Sales), CONTENT(MULTIVAR_REAL))),
    INPUT_FMT(INPUT_MODE(MATCH)),
    OUTPUT_FMT(INDEX_STYLE(FLOW_THROUGH))
);

SELECT TOP 18 * FROM final_forecast;
-- Returns: StoreID, ROW_I (original timestamps), Sales (restored original values)
```

---


## TD_POWERTRANSFORM

Applies a power transform equation (log, Box-Cox, square root, etc.) to a series. Used to stabilize variance (heteroscedasticity), linearize exponential trends, or reduce distribution skewness before ARIMA modeling. The same function with `BACK_TRANSFORM(1)` restores the original scale after forecasting.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(trans_series)
TD_POWERTRANSFORM(
    SERIES_SPEC(
        TABLE_NAME(production_data),
        ROW_AXIS(TIMECODE(MYTIMECODE)),
        SERIES_ID(ProductID),
        PAYLOAD(FIELDS(BEER_SALES), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        BACK_TRANSFORM({ 0 | 1 }),    -- 0 = forward transform, 1 = back transform
        P(float),
        B(float),
        LAMBDA(float)
    )
    [, OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH })) ]
);
```

### FUNC_PARAMS reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `BACK_TRANSFORM(0\|1)` | Yes | 0 = forward (default); 1 = back transform |
| `P(float)` | Yes | Power value |
| `B(float)` | Yes | Logarithm base |
| `LAMBDA(float)` | Yes | Box-Cox parameter |

No INPUT_FMT. OUTPUT_FMT: NUMERICAL_SEQUENCE (default) or FLOW_THROUGH.

### Transform equation reference

Forward transforms (`BACK_TRANSFORM(0)`):

| Transform | P | B | LAMBDA |
|-----------|---|---|--------|
| Natural log | 0 | 0 | 0 |
| Log base b | 0 | positive | 0 |
| Box-Cox: `(Y^λ − 1) / λ` | 0 | 0 | nonzero |
| Power: `Y^p` | positive | 0 | 0 |
| Negative power: `−Y^p` | negative | 0 | 0 |

Well-known transforms and their P/B/LAMBDA values:

| Transform | P | B | LAMBDA |
|-----------|---|---|--------|
| Square root | 0.5 | 0 | 0 |
| Cube root | 0.333 | 0 | 0 |
| Natural log | 0 | 0 | 0 |
| Negative reciprocal | −1 | 0 | 0 |

Use the same P/B/LAMBDA values for `BACK_TRANSFORM(1)` to reverse the corresponding forward transform.

### Output schema

Single-layer ART (ARTPRIMARY only).

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | Varies | Index; type depends on OUTPUT_FMT |
| `MAGNITUDE_<field>` | FLOAT | Transformed values; one per payload field |

### Workflow pattern

```sql
-- 1. Forward transform to stabilize variance
EXECUTE FUNCTION INTO VOLATILE ART(trans_series)
TD_POWERTRANSFORM(SERIES_SPEC(...), FUNC_PARAMS(BACK_TRANSFORM(0), P(0), B(0), LAMBDA(0)));

-- 2. Model and forecast the transformed series

-- 3. Back-transform forecast to original scale
EXECUTE FUNCTION INTO VOLATILE ART(final_forecast)
TD_POWERTRANSFORM(
    SERIES_SPEC(TABLE_NAME(forecast_art), ...),
    FUNC_PARAMS(BACK_TRANSFORM(1), P(0), B(0), LAMBDA(0))
);
```

---


## TD_SMOOTHMA

Applies a moving average smoothing function to a series, exposing the underlying trend. The smoothed trend series can be modeled directly, or subtracted from the original via `TD_BINARYSERIESOP` to isolate irregular fluctuations for separate modeling.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(ma_results)
TD_SMOOTHMA(
    SERIES_SPEC(
        TABLE_NAME(orders),
        SERIES_ID(OrderID),
        ROW_AXIS(SEQUENCE(SEQ)),
        PAYLOAD(FIELDS(Qty), CONTENT(REAL))
    ),
    FUNC_PARAMS(
        MA({ CUMULATIVE | MEAN | MEDIAN | EXPONENTIAL }),
        [WINDOW(integer),]
        [ONE_SIDED({ 0 | 1 }),]
        [LAMBDA(float),]
        [PAD(float),]
        [WEIGHTS(float [, ...]),]
        [WELL_KNOWN("3MA" | "5MA" | "2x12MA" | "3x3MA" | "3x5MA" |
                    "S15MA" | "S21MA" | "H5MA" | "H9MA" | "H13MA" | "H23MA")]
    )
    [, OUTPUT_FMT(INDEX_STYLE({ NUMERICAL_SEQUENCE | FLOW_THROUGH })) ]
);
```

### FUNC_PARAMS reference

| Parameter | Used with | Required | Description |
|-----------|-----------|----------|-------------|
| `MA` | All | Yes | Smoothing algorithm |
| `WINDOW` | MEAN, MEDIAN | Yes | Window size; odd = simple MA, even = centered MA |
| `ONE_SIDED(0\|1)` | MEAN | No | 0 = centered (default), 1 = trailing (no centering) |
| `LAMBDA` | EXPONENTIAL | Yes | Weighting decay factor; 0–1; higher = discount older values faster |
| `PAD` | MEAN, MEDIAN | Yes | Fill value for positions before window is filled |
| `WEIGHTS` | MEAN | No | Custom weight list; must sum to 1 and be symmetric; element count sets implied WINDOW; mutually exclusive with WELL_KNOWN |
| `WELL_KNOWN` | MEAN | No | Named weighted MA preset; mutually exclusive with WEIGHTS |

**WELL_KNOWN implied WINDOW values (if WINDOW not specified):**
`3MA` / `3x3MA` / `H5MA` → 5 | `3x5MA` → 7 | `H9MA` → 9 | `2x12MA` / `H13MA` → 13 | `S15MA` → 15 | `S21MA` → 21 | `H23MA` → 23

No INPUT_FMT. OUTPUT_FMT: NUMERICAL_SEQUENCE (default) or FLOW_THROUGH.

### Output schema

Single-layer ART (ARTPRIMARY only).

| Column | Type | Description |
|--------|------|-------------|
| `derived-series-identifier` | Varies | Inherited from SERIES_ID |
| `ROW_I` | Varies | Index; type depends on OUTPUT_FMT |
| `MAGNITUDE_<field>` | REAL | Smoothed values; one per payload field |

### Examples

```sql
-- Simple MA with WELL_KNOWN preset
EXECUTE FUNCTION INTO VOLATILE ART(ma_results)
TD_SMOOTHMA(
    SERIES_SPEC(TABLE_NAME(Orders1_12), SERIES_ID(OrderID),
                ROW_AXIS(SEQUENCE(SEQ)), PAYLOAD(FIELDS(Qty1), CONTENT(REAL))),
    FUNC_PARAMS(WINDOW(5), PAD(4.5555), MA(MEAN), WELL_KNOWN("5MA"))
);

-- Exponential smoothing
EXECUTE FUNCTION INTO VOLATILE ART(exp_ma)
TD_SMOOTHMA(
    SERIES_SPEC(TABLE_NAME(sales_ts), SERIES_ID(store_id),
                ROW_AXIS(SEQUENCE(seq_no)), PAYLOAD(FIELDS(sales), CONTENT(REAL))),
    FUNC_PARAMS(MA(EXPONENTIAL), LAMBDA(0.3))
);

-- Two-payload multivariate with trailing (one-sided) window
EXECUTE FUNCTION INTO VOLATILE ART(ma_multi)
TD_SMOOTHMA(
    SERIES_SPEC(TABLE_NAME(Orders1_12mf), SERIES_ID(OrderID),
                ROW_AXIS(SEQUENCE(SEQ)), PAYLOAD(FIELDS(Qty1, Qty2), CONTENT(MULTIVAR_REAL))),
    FUNC_PARAMS(WINDOW(5), MA(MEAN), ONE_SIDED(1)),
    OUTPUT_FMT(INDEX_STYLE(FLOW_THROUGH))
);
```

---
