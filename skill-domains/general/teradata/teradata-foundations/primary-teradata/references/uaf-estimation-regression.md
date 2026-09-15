# Teradata UAF — Estimation and Regression

## TD_LINEAR_REGR

Fits a simple linear regression model: one response variable against one explanatory variable, with optional weighting. The resulting coefficients can drive `TD_GENSERIES4FORMULA` for prediction on new data.

> **Typical workflow:** `TD_LINEAR_REGR` → extract COEFF_VALUE → build formula string → `TD_GENSERIES4FORMULA` to predict response values for new explanatory inputs.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(lr_result)
TD_LINEAR_REGR(
    SERIES_SPEC(
        TABLE_NAME(house_values),
        ROW_AXIS(SEQUENCE(s_no)),
        SERIES_ID(cid),
        PAYLOAD(FIELDS(HOUSE_VALUE, SALARY), CONTENT(MULTIVAR_REAL))
        --        ^response    ^explanatory  (^weights if WEIGHTS(1))
    ),
    FUNC_PARAMS(
        [VARIABLES_COUNT({ 2 | 3 }),]   -- 2 = no weights (default), 3 = with weights
        WEIGHTS({ 0 | 1 }),             -- 0 = no weight field (default), 1 = third field is weights
        FORMULA('Y = B0 + B1*X1'),      -- follows Formula Rules; see uaf-formula-rules
        ALGORITHM({ 'QR' | 'PSI' }),
        [COEFF_STATS({ 0 | 1 }),]
        [CONF_INT_LEVEL(float),]        -- 0–1; only with COEFF_STATS(1); default 0.90
        [MODEL_STATS({ 0 | 1 }),]
        [RESIDUALS({ 0 | 1 })]
    )
);
```

**Payload field order matters:** first field = response variable, second field = explanatory variable, third field = weights (when WEIGHTS(1)).

### FUNC_PARAMS reference

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `VARIABLES_COUNT` | No | 2 | Total payload fields: 2 = response + explanatory; 3 = + weights |
| `WEIGHTS(0\|1)` | Yes | 0 | 1 = third payload field is weights for weighted least-squares |
| `FORMULA` | Yes | — | Regression formula string; conforms to Formula Rules |
| `ALGORITHM` | Yes | — | `'QR'` (QR decomposition) or `'PSI'` (SVD pseudo-inverse) |
| `COEFF_STATS(0\|1)` | No | 0 | 1 = add STD_ERROR, TSTAT_VALUE, TSTAT_PROB, SIGNIF_RATING, CONF_INT_LOW/HIGH |
| `CONF_INT_LEVEL` | No | 0.90 | Confidence interval level; requires COEFF_STATS(1) |
| `MODEL_STATS(0\|1)` | No | 0 | 1 = generate ARTFITMETADATA layer |
| `RESIDUALS(0\|1)` | No | 0 | 1 = generate ARTFITRESIDUALS layer |

No INPUT_FMT. No OUTPUT_FMT.

### Output: three-layer ART

**Primary (ARTPRIMARY):**

| Column | Condition | Description |
|--------|-----------|-------------|
| `ROW_I` | Always | Coefficient index (position in formula) |
| `COEFF_NAME` | Always | Coefficient name |
| `COEFF_VALUE` | Always | Calculated coefficient value |
| `STD_ERROR` | COEFF_STATS(1) | Standard error of coefficient |
| `TSTAT_VALUE` | COEFF_STATS(1) | t-statistic |
| `TSTAT_PROB` | COEFF_STATS(1) | Probability if coefficient = 0 |
| `SIGNIF_RATING` | COEFF_STATS(1) | Confidence range label |
| `CONF_INT_LOW` / `CONF_INT_HIGH` | COEFF_STATS(1) | Confidence interval bounds |

**Secondary (ARTFITMETADATA):** MULTIPLE_R_SQUARED, ADJUSTED_R_SQUARED, FSTATISTIC, STD_ERROR2, STD_ERROR_DF, EXPLAINED_DF, UNEXPLAINED_DF, PROB_VALUE

**Tertiary (ARTFITRESIDUALS):** X1, ACTUAL_VALUE, CALC_VALUE, RESIDUAL

### Example

```sql
EXECUTE FUNCTION INTO VOLATILE ART(lr_result)
TD_LINEAR_REGR(
    SERIES_SPEC(TABLE_NAME(HOUSE_VALUES), ROW_AXIS(SEQUENCE(S_NO)),
                SERIES_ID(CID), PAYLOAD(FIELDS(HOUSE_VALUE, SALARY), CONTENT(MULTIVAR_REAL))),
    FUNC_PARAMS(
        VARIABLES_COUNT(2), WEIGHTS(0),
        FORMULA('Y = B0 + B1*X1'), ALGORITHM('QR'),
        COEFF_STATS(1), MODEL_STATS(1), RESIDUALS(1)
    )
);

SELECT * FROM lr_result;   -- B0 (intercept), B1 (slope) with confidence intervals

EXECUTE FUNCTION TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(lr_result), LAYER(ARTFITRESIDUALS)));
-- Returns: CID, ROW_I, X1 (SALARY), ACTUAL_VALUE (HOUSE_VALUE), CALC_VALUE, RESIDUAL
```

---


## TD_MULTIVAR_REGR

Fits a multivariate linear regression model: one response variable against multiple explanatory variables, with optional weighting. Same structure as `TD_LINEAR_REGR` extended to N explanatory variables.

```sql
EXECUTE FUNCTION INTO VOLATILE ART(mv_result)
TD_MULTIVAR_REGR(
    SERIES_SPEC(
        TABLE_NAME(house_values),
        ROW_AXIS(TIMECODE(TD_TIMECODE)),
        SERIES_ID(CITYID),
        PAYLOAD(FIELDS(HOUSE_VAL, SALARY, MORTGAGE), CONTENT(MULTIVAR_REAL))
        --        ^response  ^X1       ^X2      (last field = weights if WEIGHTS(1))
    ),
    FUNC_PARAMS(
        VARIABLES_COUNT(3),              -- required; 1 response + 2 explanatory here
        WEIGHTS(0),
        FORMULA('Y = B0 + B1*X1 + B2*X2'),
        ALGORITHM('QR'),
        [COEFF_STATS({ 0 | 1 }),]
        [CONF_INT_LEVEL(float),]
        [MODEL_STATS({ 0 | 1 }),]
        [RESIDUALS({ 0 | 1 })]
    )
);
```

**Payload field order:** first = response variable; second through (n−1) = explanatory variables; last = weights (when WEIGHTS(1)).

### Differences from TD_LINEAR_REGR

| Aspect | TD_LINEAR_REGR | TD_MULTIVAR_REGR |
|--------|---------------|-----------------|
| Explanatory variables | 1 (X1) | 2 or more (X1, X2, ...) |
| `VARIABLES_COUNT` | Optional; default 2 | Required; must reflect total payload field count |
| ARTFITRESIDUALS | `X1` only | `X1, X2, X3, ...` (one column per explanatory variable) |
| Formula | `Y = B0 + B1*X1` | `Y = B0 + B1*X1 + B2*X2 + ...` |

All other FUNC_PARAMS, output layers (ARTPRIMARY, ARTFITMETADATA, ARTFITRESIDUALS), schemas, and behavior are identical to `TD_LINEAR_REGR`.

### Example

```sql
EXECUTE FUNCTION INTO VOLATILE ART(mv_result)
TD_MULTIVAR_REGR(
    SERIES_SPEC(TABLE_NAME(HOUSE_VALUES), ROW_AXIS(TIMECODE(TD_TIMECODE)),
                SERIES_ID(CITYID),
                PAYLOAD(FIELDS(HOUSE_VAL, SALARY, MORTGAGE), CONTENT(MULTIVAR_REAL))),
    FUNC_PARAMS(
        VARIABLES_COUNT(3), WEIGHTS(0),
        FORMULA('Y = B0 + B1*X1 + B2*X2'),
        ALGORITHM('QR'), COEFF_STATS(1), MODEL_STATS(1), RESIDUALS(1)
    )
);

SELECT * FROM mv_result;    -- B0 (intercept), B1 (SALARY coeff), B2 (MORTGAGE coeff)

EXECUTE FUNCTION TD_EXTRACT_RESULTS(ART_SPEC(TABLE_NAME(mv_result), LAYER(ARTFITRESIDUALS)));
-- Returns: CITYID, ROW_I, X1 (SALARY), X2 (MORTGAGE), ACTUAL_VALUE, CALC_VALUE, RESIDUAL
```
