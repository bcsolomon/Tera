---
name: teradata-time-series-uaf
description: 'Use Teradata Unbounded Array Framework and path analysis functions for time series modeling, forecasting, digital signal processing, and event sequence analytics.'
metadata:
    author: teradata
    version: "1.0"
---

# Teradata Time Series & UAF (Unbounded Array Framework)

> **Skill:** teradata-time-series-uaf  
> **Domain:** 12-advanced-data-and-analytics-features / 04-time-series-and-event-analytics  
> **Applies to:** Teradata Vantage 17.10+, VantageCloud Lake  

---

## Purpose

Guide agents through time series analysis, forecasting, digital signal processing, and event sequence analysis using Teradata's Unbounded Array Framework (UAF) and path analysis functions. UAF functions operate on series (1D arrays), matrices (2D arrays), and Analytic Result Tables (ARTs).

> **When to use UAF:** Time series forecasting, ARIMA modeling, seasonal decomposition, regression on ordered sequences, Fourier transforms, digital filtering, spatial tracking. For cross-sectional ML, use the `teradata-ml-training-scoring` skill instead.

---

## Execution Pattern

UAF functions use `EXECUTE FUNCTION INTO ART` — results are stored in Analytic Result Tables.

```sql
-- Standard UAF call
EXECUTE FUNCTION INTO VOLATILE ART(my_result)
TD_ARIMAESTIMATE(
    SERIES_SPEC(TABLE_NAME(sales_ts), SERIES_ID(store_id),
        ROW_AXIS(SEQUENCE(seq_no)),
        PAYLOAD(FIELDS(sales_amt), CONTENT(REAL))),
    FUNC_PARAMS(NONSEASONAL(MODEL_ORDER(1,0,1)),
        FIT_PERCENTAGE(70), FIT_METRICS(1), RESIDUALS(1))
);

-- Retrieve results
SELECT * FROM my_result;
```

> **Multi-series parallelism:** A single UAF call processes ALL series instances simultaneously across all AMPs. Never loop per entity — pass all series at once.

See [references/uaf-concepts.md](references/uaf-concepts.md) for SERIES_SPEC, MATRIX_SPEC, ART_SPEC, and ART layer details.

---

## Input Specifications

| Spec Type | Data Shape | Use |
|-----------|-----------|-----|
| `SERIES_SPEC` | 1D array (one value per index) | Time series, signals |
| `MATRIX_SPEC` | 2D array (rows × columns) | Correlation matrices, images |
| `ART_SPEC` | Reference to existing ART | Chaining pipeline steps |
| `GENSERIES_SPEC` | Programmatically generated series | Synthetic test signals |

---

## ARIMA Pipeline (Canonical Workflow)

The standard pattern for time series forecasting:

```sql
-- Step 1: Estimate ARIMA coefficients
EXECUTE FUNCTION INTO VOLATILE ART(arima_est)
TD_ARIMAESTIMATE(
    SERIES_SPEC(...),
    FUNC_PARAMS(NONSEASONAL(MODEL_ORDER(1,0,1)),
        FIT_PERCENTAGE(70), FIT_METRICS(1), RESIDUALS(1))
);

-- Step 2: Validate in-sample fit
EXECUTE FUNCTION INTO VOLATILE ART(arima_val)
TD_ARIMAVALIDATE(
    ART_SPEC(TABLE_NAME(arima_est)),
    FUNC_PARAMS(FIT_METRICS(1), RESIDUALS(1))
);

-- Step 3: Forecast
EXECUTE FUNCTION INTO VOLATILE ART(arima_fcst)
TD_ARIMAFORECAST(
    ART_SPEC(TABLE_NAME(arima_val)),
    FUNC_PARAMS(FORECAST_PERIODS(7))
);

-- Step 4: Retrieve
SELECT * FROM arima_fcst;
```

---

## Function Quick Reference

### Estimation & Modeling

| Function | Purpose | Reference |
|----------|---------|-----------|
| `TD_ARIMAESTIMATE` | Fit ARIMA model | [uaf-estimation.md](references/uaf-estimation.md) |
| `TD_ARIMAVALIDATE` | Validate ARIMA fit | [uaf-estimation.md](references/uaf-estimation.md) |
| `TD_AUTOARIMA` | Automatic ARIMA order selection | [uaf-estimation.md](references/uaf-estimation.md) |
| `TD_LINEAR_REGR` | Linear regression on series | [uaf-estimation.md](references/uaf-estimation.md) |
| `TD_MULTIVAR_REGR` | Multivariate regression on series | [uaf-estimation.md](references/uaf-estimation.md) |
| `TD_ACF` / `TD_PACF` | Auto/partial-autocorrelation | [uaf-estimation.md](references/uaf-estimation.md) |
| `TD_DIFF` / `TD_UNDIFF` | Differencing for stationarity | [uaf-estimation.md](references/uaf-estimation.md) |
| `TD_SEASONALNORMALIZE` | Seasonal decomposition | [uaf-estimation.md](references/uaf-estimation.md) |
| `TD_POWERTRANSFORM` | Box-Cox / power transforms | [uaf-estimation.md](references/uaf-estimation.md) |
| `TD_SMOOTHMA` | Moving average smoothing | [uaf-estimation.md](references/uaf-estimation.md) |

### Forecasting

| Function | Purpose | Reference |
|----------|---------|-----------|
| `TD_ARIMAFORECAST` | ARIMA forecast | [uaf-forecasting.md](references/uaf-forecasting.md) |
| `TD_HOLT_WINTERS_FORECASTER` | Exponential smoothing with trend & seasonality | [uaf-forecasting.md](references/uaf-forecasting.md) |
| `TD_MAMEAN` | Moving average forecast | [uaf-forecasting.md](references/uaf-forecasting.md) |
| `TD_SIMPLEEXP` | Simple exponential smoothing | [uaf-forecasting.md](references/uaf-forecasting.md) |
| `TD_DTW` | Dynamic time warping similarity | [uaf-forecasting.md](references/uaf-forecasting.md) |

### Diagnostics

| Function | Purpose | Reference |
|----------|---------|-----------|
| `TD_DICKEY_FULLER` | Unit root test (stationarity) | [uaf-diagnostics.md](references/uaf-diagnostics.md) |
| `TD_DURBIN_WATSON` | Autocorrelation in residuals | [uaf-diagnostics.md](references/uaf-diagnostics.md) |
| `TD_BREUSCH_GODFREY` | Higher-order serial correlation | [uaf-diagnostics.md](references/uaf-diagnostics.md) |
| `TD_BREUSCH_PAGAN_GODFREY` | Heteroskedasticity test | [uaf-diagnostics.md](references/uaf-diagnostics.md) |
| `TD_PORTMAN` | Portmanteau test | [uaf-diagnostics.md](references/uaf-diagnostics.md) |
| `TD_FITMETRICS` | Model fit metrics | [uaf-diagnostics.md](references/uaf-diagnostics.md) |

### DSP (Digital Signal Processing)

| Function | Purpose | Reference |
|----------|---------|-----------|
| `TD_DFFT` / `TD_IDFFT` | Forward/inverse FFT | [uaf-dsp.md](references/uaf-dsp.md) |
| `TD_POWERSPEC` / `TD_LINESPEC` | Power/line spectrum | [uaf-dsp.md](references/uaf-dsp.md) |
| `TD_DWT` / `TD_IDWT` | Wavelet transform | [uaf-dsp.md](references/uaf-dsp.md) |
| `TD_CONVOLVE` | Convolution/filtering | [uaf-dsp.md](references/uaf-dsp.md) |
| `TD_SAX` | Symbolic aggregate approximation | [uaf-dsp.md](references/uaf-dsp.md) |

### Data Prep & Utility

| Function | Purpose | Reference |
|----------|---------|-----------|
| `TD_RESAMPLE` | Resample series to regular intervals | [uaf-data-prep.md](references/uaf-data-prep.md) |
| `TD_IQR` | Interquartile range anomaly detection | [uaf-data-prep.md](references/uaf-data-prep.md) |
| `TD_BINARYSERIESOP` | Binary operations on two series | [uaf-data-prep.md](references/uaf-data-prep.md) |
| `TD_GENSERIES4FORMULA` | Generate series from formula | [uaf-data-prep.md](references/uaf-data-prep.md) |
| `TD_FILTERFACTORY1D` | Build filter coefficients | [uaf-utility.md](references/uaf-utility.md) |
| `TD_TRACKINGOP` | Geospatial tracking metrics | [uaf-utility.md](references/uaf-utility.md) |
| `TD_PLOT` | Visualize series/matrix | [uaf-utility.md](references/uaf-utility.md) |

---

## Path & Sequence Analysis

Native functions for event sequence analysis — sessionization, attribution, and path mining.

| Function | Purpose | Reference |
|----------|---------|-----------|
| `Sessionize` | Divide event streams into sessions by timeout | [path-analysis.md](references/path-analysis.md) |
| `nPath` | Pattern matching on event sequences (regex-like) | [path-analysis.md](references/path-analysis.md) |
| `Attribution` | Multi-touch attribution modeling | [path-analysis.md](references/path-analysis.md) |

```sql
-- Sessionize: divide clickstream into sessions (30-min timeout)
SELECT * FROM Sessionize(
    ON db.clickstream PARTITION BY user_id ORDER BY event_ts
    USING TimeColumn('event_ts') TimeOut(1800)
) AS t;
```

---

## Recommended Workflows

| Use Case | Topic Sequence |
|----------|---------------|
| **ARIMA forecasting** | uaf-concepts → uaf-data-prep → uaf-estimation → uaf-forecasting → uaf-diagnostics |
| **Regression on ordered series** | uaf-concepts → uaf-data-prep → uaf-estimation (TD_LINEAR_REGR) → uaf-diagnostics |
| **Frequency / spectral analysis** | uaf-concepts → uaf-dsp (TD_DFFT, TD_POWERSPEC) |
| **Digital signal filtering** | uaf-concepts → uaf-utility (TD_FILTERFACTORY1D) → uaf-dsp (TD_CONVOLVE) |
| **Event path analysis** | path-analysis (Sessionize → nPath → Attribution) |

---

## ART Layers

Multi-layer ARTs store several result sets. Use `TD_EXTRACT_RESULTS` for non-primary layers:

| Layer | Contents |
|-------|----------|
| `ARTPRIMARY` | Primary function results (queryable via SELECT) |
| `ARTFITRESIDUALS` | Residual series |
| `ARTFITMETADATA` | Goodness-of-fit metrics |
| `ARTMODEL` | Validation model context |
| `ARTSTATSDATA` | Aggregate statistics |

```sql
-- Extract fit metrics from an ARIMA ART
EXECUTE FUNCTION TD_EXTRACT_RESULTS(
    ART_SPEC(TABLE_NAME(arima_est), LAYER(ARTFITMETADATA))
);
```

---

## References


> **Access:** `skill_resource_read(action="read", skill="teradata-time-series-uaf", path="references/FILENAME")` — do NOT call `list`.

| File | Content |
|------|---------|
| [uaf-concepts.md](references/uaf-concepts.md) | SERIES_SPEC, MATRIX_SPEC, ART_SPEC, execution pattern, ART layers |
| [uaf-estimation.md](references/uaf-estimation.md) | ARIMA, ACF/PACF, regression, seasonal decomposition (1055 lines) |
| [uaf-forecasting.md](references/uaf-forecasting.md) | ARIMA forecast, Holt-Winters, moving average, DTW |
| [uaf-diagnostics.md](references/uaf-diagnostics.md) | Dickey-Fuller, Durbin-Watson, Breusch-Godfrey, residual tests |
| [uaf-dsp.md](references/uaf-dsp.md) | FFT, wavelet, convolution, power spectrum |
| [uaf-data-prep.md](references/uaf-data-prep.md) | Resample, IQR, binary series operations |
| [uaf-utility.md](references/uaf-utility.md) | Filter factory, tracking, plot, SINFO/MINFO |
| [uaf-formula-rules.md](references/uaf-formula-rules.md) | Formula syntax for FORMULA() parameters |
| [path-analysis.md](references/path-analysis.md) | Sessionize, nPath, Attribution |

*Source: Teradata tdsql-mcp syntax library (ksturgeon-td/tdsql-mcp)*
