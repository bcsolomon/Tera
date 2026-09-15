# Data quirks, load decisions and performance

Things that will look like bugs but are either faithful to the CDC source or deliberate load-time choices. Know them before
telling a user a number is wrong.

## Quirks inherited from the CDC workbooks (loaded as printed)

| Quirk | Detail | How to handle |
|---|---|---|
| CAH national CLABSI percent change | `sir_trend_2023_2024` shows `PCT_CHANGE` 30.0 while the two SIRs (0.736 to 1.054) imply about 43 percent | The workbook prints 0.3; we did not override it. Quote the two SIRs instead of the change, or note the discrepancy |
| `STATE_MANDATE_FLG = 'M'` | Not Y or N: CDC's mid-year mandate marker, 36 ACH and 18 CAH rows | Treat as "mandate began mid-year", not as missing |
| `SSI_MODEL` has two values | `COMPLEX_AR` (adult complex admission/readmission model) and `COMPLEX_AR_PED` (pediatric) | Always filter to one, else procedure rows double |
| `PCT_CHANGE = 0` on zero-over-zero rows | Three 2020 SSI rows (Wyoming COLO Q3, Maine and Montana HYST Q1) have both SIRs 0 and an inestimable interval | Report as "no events in either period", not as "no change" |
| Fully suppressed territories | Guam and the Virgin Islands are `.` across all 28 COVID-era sheets; rows kept because `FACILITIES_REPORTING` is real | Count them as not reportable |
| Missing significance asterisk | 2020 Q1 national CLABSI wards shows change -13.9 with an interval excluding 0 but no CDC asterisk, so `SIGNIFICANT_FLG='N'` | Flag follows the workbook; the interval is the better test |
| Interval typo | LTACH national CAUTI wards prints a CI of 0.732 to 0.732 | Source typo; do not compute a width from it |
| Percentile inversion | Pediatric-location CLABSI has `PCTL_90` 1.973 above `PCTL_95` 1.474 | Source inconsistency; avoid quoting those two together |
| Small-denominator extremes | Critical access VAE SIR 2.221 on 104 facilities; prostate-surgery SSI 2.904 on 5,960 procedures | Always show the denominator with an extreme ratio |

## Deliberate load decisions

- **Percentages are stored 0 to 100.** The 2024 workbooks publish fractions (0.21 meaning 21 percent); they were multiplied
  by 100 on load. `FAC_SIG_HIGHER_PCT = 21.0` means 21 percent of facilities.
- **`PCT_CHANGE` is signed.** The 2024 workbooks publish an absolute value plus a direction word; the sign was derived from
  the direction, falling back to the sign of current minus base for "No change".
- **National rows carry `STATE_CD='US'`** rather than NULL, so the primary index stays usable and joins to `dim_state` work
  (there is a `US` row). Always filter `GEO_LEVEL` rather than relying on `STATE_CD IS NULL`.
- **`All US` rows inside state sheets were dropped** after verifying they equalled the national sheet, so state-level
  aggregates do not include a duplicate total. The exception is the reporting-characteristics table, where `US` is kept.
- **Only seven percentiles were captured** (05, 10, 25, 50, 75, 90, 95). The national sheets publish 19; the intermediate
  ones (0.15, 0.20, 0.30 and so on) are not in the database. State sheets publish only 10 through 90, so `PCTL_05` and
  `PCTL_95` are NULL on state rows.
- **`YesA` validation markers** became `VALIDATION_FLG='Y'` with the footnote letter in `VALIDATION_NOTE` on
  `state_reporting_2024`; `sir_2024` keeps only the `Y`.
- **Text charset.** `POPULATION_NM`, `CDC_LOCATION_NM`, `MODEL_NM`, `FACTORS_TEXT` and chunk text are UNICODE because CDC
  labels contain `≥`, `‡` and `†`. Other text columns are LATIN.

## Known gaps

- No 2021 or 2022 structured data. The COVID-impact document discusses 2021 narratively only.
- `state_reporting_2024` covers ACH and CAH only; IRF, LTACH, oncology and pediatric workbooks have no equivalent sheet.
- `sir_trend_2023_2024` lacks a `CDC_LOCATION_NM` column, so the four oncology-versus-pediatric location sub-rows collide on
  the natural key and are distinguishable only by `POPULATION_NM` and `SRC_SHEET`.
- `doc_record_map` exists but is empty; it is the fallback used only if Unstructured stops emitting filenames.
- `Document_Chunks.embeddings` is always NULL because the workflow has no embedder node; embeddings live in `doc_embeddings`.

## Performance

The fact tables are small (3,072 rows at most), but they arrived via `INSERT ... SELECT` from READ_NOS with no statistics.
Joins that filtered on `GEO_LEVEL` and `POPULATION_CD` while joining a trend table exceeded 120 seconds until statistics
were collected on 2026-09-15; the same queries then returned in seconds.

If a query is unexpectedly slow, re-collect:

```sql
COLLECT STATISTICS COLUMN (GEO_LEVEL), COLUMN (FACILITY_TYPE_CD), COLUMN (HAI_CD), COLUMN (POPULATION_CD),
                   COLUMN (STATE_CD), COLUMN (PROCEDURE_CD), COLUMN (SSI_MODEL), COLUMN (HAI_CD, STATE_CD)
ON CDC_HAI.sir_2024;
```

Equivalents exist for `sir_trend_2023_2024`, `sur_2024`, `sur_trend_2023_2024`, `covid_state_qtr_2020`, `dim_state` and
`doc_chunks`. Re-collect after any reload. `COLLECT STATISTICS ON CDC_HAI.<table>` alone refreshes what is already defined.

Vector search embeds the question at query time, so it carries a fixed cost of roughly a second per search regardless of
`TopK`. Batching several questions into one statement is not worth the complexity; issue them separately.

## Provenance

Every fact row carries `SRC_WORKBOOK` and `SRC_SHEET`. To defend a number, show them:

```sql
SELECT DISTINCT SRC_WORKBOOK, SRC_SHEET FROM CDC_HAI.sir_2024
WHERE GEO_LEVEL='NATIONAL' AND FACILITY_TYPE_CD='ACH' AND HAI_CD='VAE' AND POPULATION_CD='ALL';
```

Parse-time reports with per-sheet row counts and spot checks live in the build directory (`build/reports/*.md`), and the
raw workbooks are in `s3://cdc-hai/structured/raw/`.
