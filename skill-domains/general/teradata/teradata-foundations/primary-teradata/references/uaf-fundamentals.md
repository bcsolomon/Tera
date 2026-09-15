# Teradata UAF — Digital Signal Processing (DSP) and Spectral Analysis

## Quick Reference

| Function | Category | Dim | Purpose |
|----------|----------|-----|---------|
| `TD_DFFT` | Fourier | 1D | Forward FFT — time domain → frequency domain |
| `TD_DFFT2` | Fourier | 2D | Forward 2D FFT — matrices/images |
| `TD_IDFFT` | Fourier | 1D | Inverse FFT — frequency domain → time domain |
| `TD_IDFFT2` | Fourier | 2D | Inverse 2D FFT |
| `TD_DFFTCONV` | Fourier | 1D | Convert TD_DFFT result (raw↔human-readable, content type) |
| `TD_DFFT2CONV` | Fourier | 2D | Convert TD_DFFT2 result (raw↔human-readable, content type) |
| `TD_WINDOWDFFT` | Fourier | 1D | Apply window function then FFT in one call |
| `TD_DWT` | Wavelet | 1D | Forward Discrete Wavelet Transform |
| `TD_DWT2D` | Wavelet | 2D | Forward 2D DWT — matrices/images |
| `TD_IDWT` | Wavelet | 1D | Inverse DWT — reconstruct signal from wavelet coefficients |
| `TD_IDWT2D` | Wavelet | 2D | Inverse 2D DWT |
| `TD_CONVOLVE` | Convolution | 1D | Convolve time series with filter series |
| `TD_CONVOLVE2` | Convolution | 2D | Convolve matrix with filter matrix |
| `TD_POWERSPEC` | Spectral | 1D | Power spectrum estimate (Fourier-based); multiple algorithms + windowing |
| `TD_LINESPEC` | Spectral | 1D | Line spectrum — sinusoidal components; simpler than TD_POWERSPEC |
| `TD_GENSERIES4SINUSOIDS` | Spectral | 1D | Generate synthetic sinusoidal series at specified periodicities |
| `TD_SAX` | Symbolic | 1D | Symbolic Aggregate approXimation (PAA + SAX) |

---


## Key Pipelines

### Manual convolution (equivalent to TD_CONVOLVE)
```sql
EXECUTE FUNCTION INTO VOLATILE ART(dfftRes1) TD_DFFT(SERIES_SPEC(series1 ...), ...);
EXECUTE FUNCTION INTO VOLATILE ART(dfftRes2) TD_DFFT(SERIES_SPEC(series2 ...), ...);
EXECUTE FUNCTION INTO VOLATILE ART(freqRes)
  TD_BINARYSERIESOP(ART_SPEC(TABLE_NAME(dfftRes1)), ART_SPEC(TABLE_NAME(dfftRes2)),
    FUNC_PARAMS(MATHOP(MULTIPLY)), INPUT_FMT(INPUT_MODE(MATCH)));
EXECUTE FUNCTION INTO VOLATILE ART(convResult) TD_IDFFT(ART_SPEC(TABLE_NAME(freqRes)), ...);
-- Simpler: use TD_CONVOLVE instead
```

### Significant periodicities pipeline
```sql
-- 1. Spectral analysis with K_PERIODICITY
EXECUTE FUNCTION INTO VOLATILE ART(specRes)
  TD_POWERSPEC(SERIES_SPEC(...), FUNC_PARAMS(FREQ_STYLE('K_PERIODICITY')));
-- or TD_LINESPEC with FREQ_STYLE("K_PERIODICITY")

-- 2. Retrieve top periodicities
SELECT TOP 5 * FROM specRes ORDER BY SPECTRAL_DENSITY_field DESC;

-- 3. Test significance (use period values from step 2)
EXECUTE FUNCTION INTO VOLATILE ART(sigPeriodicities)
  TD_SIGNIF_PERIODICITIES(ART_SPEC(TABLE_NAME(residualsART), LAYER(ARTFITRESIDUALS)),
    FUNC_PARAMS(PERIODICITIES(p1, p2, p3, p4, p5)));
```

### Periodicity removal
```sql
-- 1. Identify dominant periods (K_PERIODICITY)
-- 2. Generate synthetic sinusoid series
EXECUTE FUNCTION INTO VOLATILE ART(sinusoids)
  TD_GENSERIES4SINUSOIDS(SERIES_SPEC(...), FUNC_PARAMS(PERIODICITIES(p1, p2)));
-- 3. Subtract from original
EXECUTE FUNCTION INTO VOLATILE ART(cleaned)
  TD_BINARYSERIESOP(SERIES_SPEC(original ...), ART_SPEC(TABLE_NAME(sinusoids)),
    FUNC_PARAMS(MATHOP(SUB)), INPUT_FMT(INPUT_MODE(MATCH)));
-- 4. Verify: TD_POWERSPEC on cleaned
```

### TD_IDFFT raw format constraint
If TD_IDFFT input is not via ART_SPEC, it **must** be in RAW format:
```sql
-- Convert human-readable TD_DFFT output to raw before TD_IDFFT
EXECUTE FUNCTION INTO VOLATILE ART(rawResult)
  TD_DFFTCONV(ART_SPEC(TABLE_NAME(hrDfftResult)),
    FUNC_PARAMS(CONV(HR_TO_RAW), FREQ_STYLE(K_INTEGRAL)));
-- Same constraint for TD_IDFFT2 — use TD_DFFT2CONV
```

---


## Shared Reference: Wavelet Families

Used by TD_DWT, TD_DWT2D, TD_IDWT, TD_IDWT2D. **WAVELET names are case-sensitive.**

| Family | Names |
|--------|-------|
| Daubechies | `db1` (= `haar`), `db2` – `db38` |
| Coiflets | `coif1` – `coif17` |
| Symlets | `sym2` – `sym20` |
| Discrete Meyer | `dmey` |
| Biorthogonal | `bior1.1`, `bior1.3`, `bior1.5`, `bior2.2`, `bior2.4`, `bior2.6`, `bior2.8`, `bior3.1`, `bior3.3`, `bior3.5`, `bior3.7`, `bior3.9`, `bior4.4`, `bior5.5`, `bior6.8` |
| Reverse Biorthogonal | `rbio1.1`, `rbio1.3`, `rbio1.5`, `rbio2.2`, `rbio2.4`, `rbio2.6`, `rbio2.8`, `rbio3.1`, `rbio3.3`, `rbio3.5`, `rbio3.7`, `rbio3.9`, `rbio4.4`, `rbio5.5`, `rbio6.8` |

**Signal extension modes** (MODE — case-insensitive):
`symmetric`/`sym`/`symh` · `reflect`/`symw` · `smooth`/`spd`/`sp1` · `constant`/`sp0` · `zero`/`zpd` · `periodic`/`ppd` · `periodization`/`per` · `antisymmetric`/`asym`/`asymh` · `antireflect`/`asymw`

---


## Shared Reference: FFT Parameters

Used by TD_DFFT, TD_DFFT2, TD_DFFTCONV, TD_DFFT2CONV, TD_WINDOWDFFT.

| Parameter | Options | Default | Notes |
|-----------|---------|---------|-------|
| `ZERO_PADDING_OK` | 1 \| 0 | 1 | Add zeros for efficient FFT size; use default |
| `FREQ_STYLE` | K_INTEGRAL, K_SAMPLE_RATE, K_RADIANS, K_HERTZ | K_INTEGRAL | K_HERTZ requires HERTZ_SAMPLE_RATE |
| `HERTZ_SAMPLE_RATE` | FLOAT | — | Required with K_HERTZ only |
| `ALGORITHM` | COOLEY_TUKEY \| SINGLETON | internal planner | Omit for best performance |
| `HUMAN_READABLE` | 1 \| 0 | 1 | 1 = symmetric around 0 (−3,−2,−1,0,1,2,3); 0 = sequential from 0 (0,1,2,3) |

**OUTPUT_FMT CONTENT options** (TD_DFFT, TD_DFFT2, TD_IDFFT, TD_IDFFT2, TD_DFFTCONV, TD_DFFT2CONV, TD_WINDOWDFFT):

| Series type | CONTENT options | Default |
|-------------|-----------------|---------|
| Univariate | COMPLEX, AMPL_PHASE_RADIANS, AMPL_PHASE_DEGREES | COMPLEX |
| Multivariate | MULTIVAR_COMPLEX, MULTIVAR_AMPL_PHASE, MULTIVAR_AMPL_PHASE_RADIANS, MULTIVAR_AMPL_PHASE_DEGREES | MULTIVAR_COMPLEX |

Output columns per content type:
- `COMPLEX` / `MULTIVAR_COMPLEX` → `REAL_PayloadName` + `IMAGINARY_PayloadName`
- `AMPL_PHASE*` / `MULTIVAR_AMPL_PHASE*` → `AMPLITUDE_PayloadName` + `PHASE_PayloadName`

---

---

# Teradata UAF — Formula Syntax Rules

User-defined formula syntax used by UAF functions that accept a `FORMULA(...)` parameter.

**Functions that use formulas:**
- `TD_GENSERIES4FORMULA` (uaf-data-prep) — generate a series by applying a formula to input payload fields
- `TD_LINEAR_REGR` (uaf-estimation) — simple linear regression formula
- `TD_MULTIVAR_REGR` (uaf-estimation) — multivariate regression formula
- `TD_BREUSCH_PAGAN_GODFREY` (uaf-diagnostics) — optional formula for auxiliary regression

---

## Formula Structure

A formula is a `VARCHAR(64000)` string passed to `FUNC_PARAMS(FORMULA(...))`. Rules:

- Enclosed in single or double quotation marks.
- Must start with `Y =` (or `y =`).
- `Y` is the **response variable** (dependent variable) and corresponds to the **first field** in `SERIES_SPEC(PAYLOAD(FIELDS(...)))`.
- The expression after `Y =` is a SQL arithmetic expression composed of coefficients, explanatory variables, numeric constants, operators, math functions, and parentheses.

### Variable naming

**Explanatory variables** (the Xn inputs):
- The **nth explanatory variable** corresponds to the **nth field** in `PAYLOAD(FIELDS(...))`.
- Can appear in the formula any number of times.
- Must have a valid Teradata name label.

**Coefficients** — appear immediately before `*` and an explanatory variable:
- **Numeric constant coefficients:** literal values (e.g., `6`, `2.99`, `89`) — value is fixed.
- **Numeric variable coefficients:** named variables (e.g., `a`, `B0`, `B1`) — value is **estimated by the function**.
  - Must appear exactly once in the formula.
  - Names are case-insensitive.
  - Must be valid Teradata UNICODE object names with no escape characters or quotation marks.

### Examples

```sql
-- Numeric variable coefficients (a, b, c, d are estimated by the function)
FORMULA('Y = d + a*X1 + b*X2 + c*(exp(X3) * cos(X2))')

-- Numeric constant coefficients (all values fixed)
FORMULA('Y = 89 + 6*X1 + 2.99*X1**2 + exp(X2)')

-- Linear regression formulas (B0, B1, B2 are estimated)
FORMULA('Y = B0 + B1*X1')
FORMULA('Y = B0 + B1*X1 + B2*X2')
```

---

## Operator Precedence

Evaluation order (highest to lowest precedence):

| Precedence | Operators |
|------------|-----------|
| 1 (highest) | Unary `+` and unary `-` |
| 2 | Exponentiation `**` |
| 3 | Multiplication `*` and division `/` |
| 4 (lowest) | Addition `+` and subtraction `-` |

- Expressions in parentheses are evaluated first.
- Operators of equal precedence are evaluated left to right.

---

## Arithmetic Operators

| Operator | Operation |
|----------|-----------|
| `**` | Exponentiate |
| `*` | Multiply |
| `/` | Divide |
| `+` | Add |
| `-` | Subtract |
| `+` | Unary plus |
| `-` | Unary minus |

---

## Math Functions

| Function | Description |
|----------|-------------|
| `ABS(x)` | Absolute value |
| `CEILING(x)` | Smallest integer ≥ x |
| `EXP(x)` | e raised to the power x (e ≈ 2.71828) |
| `FLOOR(x)` | Largest integer ≤ x |
| `LN(x)` | Natural logarithm (base e) |
| `LOG(x)` | Base-10 logarithm |
| `NANIFZERO(x)` | Converts 0 to NaN — avoids division-by-zero errors; **FORMULA parameter only** |
| `POWER(base, exp)` | base raised to the power of exp |
| `RANDOM` | Random integer per result row |
| `ROUND(x, n)` | x rounded to n decimal places |
| `SIGN(x)` | Sign of x: −1, 0, or 1 |
| `SQRT(x)` | Square root |
| `TRUNC(x, n)` | x truncated to n decimal places |
| `ZEROIFNAN(x)` | Converts NaN to 0 — avoids NaN propagation errors; **FORMULA parameter only** |

---

## Trigonometric Functions

All angles are in radians unless converted with DEGREES/RADIANS.

| Function | Description |
|----------|-------------|
| `SIN(x)` | Sine; result in [−1, 1] |
| `COS(x)` | Cosine; result in [−1, 1] |
| `TAN(x)` | Tangent |
| `ASIN(x)` | Arcsine; result in [−π/2, π/2] |
| `ACOS(x)` | Arccosine; result in [0, π] |
| `ATAN(x)` | Arctangent; result in [−π/2, π/2] |
| `ATAN2(x, y)` | Four-quadrant arctangent; result in (−π, π]; positive = counterclockwise from x-axis |
| `SINH(x)` | Hyperbolic sine |
| `COSH(x)` | Hyperbolic cosine |
| `TANH(x)` | Hyperbolic tangent |
| `ASINH(x)` | Inverse hyperbolic sine |
| `ACOSH(x)` | Inverse hyperbolic cosine |
| `ATANH(x)` | Inverse hyperbolic tangent |
| `DEGREES(x)` | Convert radians to degrees |
| `RADIANS(x)` | Convert degrees to radians |
