# CDC_HAI data dictionary

Database `CDC_HAI`, Teradata demo box. 18 tables: 7 dimensions, 8 fact tables, 3 document tables (plus one empty fallback map).
Source: CDC/NHSN 2024 National and State HAI Progress Report workbooks (SIR and SUR), the 2020 COVID-impact supplements,
and seven CDC PDFs. Loaded 2026-09-14.

## Dimensions

| Table | Rows | Key columns |
|---|---:|---|
| `dim_state` | 57 | `STATE_CD CHAR(2)`, `STATE_NM`, `HHS_REGION`, `IS_TERRITORY_FLG`. Includes DC, GU, PR, VI, AS, MP and `US` (national) |
| `dim_facility_type` | 6 | `ACH` acute care, `CAH` critical access, `IRF` inpatient rehab, `LTACH` long-term acute care, `ONC` oncology, `PED` pediatric |
| `dim_hai_type` | 6 | `CLABSI`, `CAUTI`, `VAE`, `SSI`, `MRSA`, `CDI` with `HAI_CATEGORY` (DEVICE / PROCEDURE / LABID) and `DENOM_TYPE` |
| `dim_device_type` | 3 | `CLD` central line days, `UCD` urinary catheter days, `VD` ventilator days |
| `dim_population` | 9 | `ALL`, `ICU`, `WARD`, `NICU`, `ONC_LOC`, `PED_LOC`, `CDC_LOCATION`, `PROCEDURE`, `ALL_SSI` |
| `dim_procedure` | 39 | NHSN operative procedure codes: `AAA`, `AMP`, `APPY`, `CSEC`, `COLO`, `HYST`, `HPRO`, `KPRO`, `FUSN`, `PRST`, `KTP`, `XLAP` and more |
| `dim_cdc_location` | 78 | CDC location codes such as `IN:ACUTE:WARD:ORT_PED` with names |

`STATE_CD` is `CHAR(2)`, so it comes back space-padded (`'AL  '`). Compare with `=` to a 2-character literal, which works,
but use `TRIM()` when concatenating into text.

## `sir_2024` — 3,072 rows, the main fact table

Grain: `GEO_LEVEL` × `STATE_CD` × `FACILITY_TYPE_CD` × `HAI_CD` × `POPULATION_CD` × `PROCEDURE_CD` × `CDC_LOCATION_NM` × `SSI_MODEL`.

| Group | Columns |
|---|---|
| Keys | `REPORT_YEAR` (2024), `GEO_LEVEL` (NATIONAL/STATE), `STATE_CD`, `FACILITY_TYPE_CD`, `HAI_CD`, `POPULATION_CD`, `POPULATION_NM`, `PROCEDURE_CD`, `CDC_LOCATION_NM`, `SSI_MODEL` |
| Reporting context | `STATE_MANDATE_FLG` (Y/N/M), `VALIDATION_FLG` (Y/N), `FACILITIES_REPORTING`, `LOCATIONS_CNT` |
| Denominators | `PATIENT_DAYS`, `DEVICE_DAYS`, `ADMISSIONS`, `PROCEDURES_CNT`, `CO_EVENTS` (community-onset, LabID only) |
| Outcome | `OBSERVED`, `PREDICTED`, `SIR`, `SIR_CI_LOWER`, `SIR_CI_UPPER` |
| Facility spread | `FAC_GE1_PREDICTED`, `FAC_SIG_HIGHER_N`, `FAC_SIG_HIGHER_PCT`, `FAC_SIG_LOWER_N`, `FAC_SIG_LOWER_PCT` |
| Percentiles | `PCTL_05`, `PCTL_10`, `PCTL_25`, `PCTL_50`, `PCTL_75`, `PCTL_90`, `PCTL_95` (facility-level SIR at that percentile) |
| Lineage | `SRC_WORKBOOK`, `SRC_SHEET` |

Row counts by facility type: ACH 1,752; CAH 791; LTACH 281; IRF 220; oncology and pediatric 28.

Which `POPULATION_CD` values exist per HAI:

| HAI | Populations present |
|---|---|
| CLABSI | `ALL`, `ICU`, `WARD`, `NICU`, `CDC_LOCATION`, plus `ONC_LOC` / `PED_LOC` under `FACILITY_TYPE_CD='ACH'` |
| CAUTI | `ALL`, `ICU`, `WARD`, `CDC_LOCATION`, `ONC_LOC`, `PED_LOC` |
| VAE | `ALL`, `ICU`, `WARD`, `CDC_LOCATION` |
| MRSA, CDI | `ALL` only (facility-wide LabID surveillance) |
| SSI | `ALL_SSI` (all procedures) and `PROCEDURE` (one per procedure); **never `ALL`** |

`ICU`, `WARD` and `NICU` rows are subsets of `ALL`. Never add them together.

## `sur_2024` — 1,381 rows, device utilization

Same shape as `sir_2024` but keyed by `DEVICE_CD` instead of `HAI_CD`, with `OBSERVED_DEVICE_DAYS`,
`PREDICTED_DEVICE_DAYS`, `SUR`, `SUR_CI_LOWER`, `SUR_CI_UPPER`, the same facility-spread and percentile columns.
National ACH 2024: CLD 0.8134, UCD 0.7343, VD 0.8645, each a significant decrease from 2023.

## `sir_trend_2023_2024` (1,324) and `sur_trend_2023_2024` (679)

One row per comparison: `BASE_YEAR` 2023 and `REPORT_YEAR` 2024 with `BASE_FACILITIES`, `BASE_OBSERVED`, `BASE_PREDICTED`,
`BASE_SIR` (or `BASE_SUR`), the matching `CURR_*` columns, then `PCT_CHANGE` (**signed percent**, 0 to 100 scale),
`PCT_CHANGE_NOTE`, `CHANGE_DIRECTION` (`INCREASE` / `DECREASE` / `NO CHANGE`) and `P_VALUE`.

`CHANGE_DIRECTION` is CDC's own significance verdict; prefer it over comparing `P_VALUE` yourself. The SIR trend table has no
`CDC_LOCATION_NM`, so oncology and pediatric location sub-rows are distinguished only by `POPULATION_NM`.

## `state_reporting_2024` — 770 rows

Per state, facility type and HAI: `STATE_MANDATE_FLG`, `VALIDATION_FLG`, `VALIDATION_NOTE`, `FACILITIES_REPORTING`,
`LOCATIONS_TOTAL`, `LOCATIONS_ICU`, `LOCATIONS_WARD`, `LOCATIONS_NICU`, `PROCEDURES_CNT`. Use it to explain reporting
differences behind a state comparison. Only ACH and CAH have these sheets.

## `covid_state_qtr_2020` — 1,512 rows

Acute care hospitals, consistent reporters only, one row per `REPORT_QTR` (1 to 4) × `STATE_CD` × `HAI_CD` × `PROCEDURE_CD`:
`OBSERVED_2020`, `PREDICTED_2020`, `DENOM_2020` and the 2019 equivalents, `SIR_2020`, `SIR_2019`, signed `PCT_CHANGE`,
`PCT_CHANGE_NOTE`, `CI_LOWER`, `CI_UPPER`, `CI_NOTE`, `DENOM_TYPE`.

The confidence interval here is **around the percent change**, so significance means excluding 0, not 1.
SSI rows carry `HAI_CD='SSI'` plus `PROCEDURE_CD` of `COLO` or `HYST`.

## `covid_natl_location_qtr_2020` — 40 rows

National by location type for CLABSI, CAUTI and VAE: `SIR_2020`, `SIR_2019`, `PCT_CHANGE`, `SIGNIFICANT_FLG` (CDC's own
asterisk), `CI_LOWER`, `CI_UPPER` and percentiles `PCTL_00` through `PCTL_100`.

## `risk_model_factor` — 193 rows

The risk-adjustment factors behind each model, from the workbook appendices: `RATIO_TYPE` (SIR/SUR), `FACILITY_TYPE_CD`,
`MODEL_NM` (for example `CLABSI (non-NICU)`, `CLDs (NICU)`), `FACTORS_TEXT`. Use it when asked what a SIR adjusts for:
the CLABSI non-NICU model adjusts for medical school affiliation, location type, facility type and bed size; the NICU
model adjusts for birthweight.

## Document tables

| Table | Rows | Purpose |
|---|---:|---|
| `document` | 7 | Registry: `DOC_ID`, `FILENAME`, `DOC_TITLE`, `DOC_TYPE` (GUIDE/REPORT/FAQ/WEB_PAGE/FIGURE), `PUBLISHER`, `PUB_YEAR`, `PAGE_CNT`, `S3_URI`, `DOC_SUMMARY` |
| `doc_chunks` | 1,274 | `CHUNK_KEY` (integer), `DOC_ID`, `RECORD_ID`, `FILENAME`, `PAGE_NUMBER`, `ELEMENT_ID`, `ELEMENT_TYPE` (`CompositeElement` or `TableChunk`), `CHUNK_TEXT` |
| `doc_embeddings` | 1,274 | `id` (= `CHUNK_KEY`), `txt`, `doc_id`, `filename`, `emb_0` to `emb_383` |
| `Document_Chunks` | 1,274 | Raw Unstructured landing table; prefer `doc_chunks` for queries |

Documents: `DOC_ID` 1 NHSN SIR Guide (50 pages, 551 chunks), 2 NHSN SUR Guide (28 pages, 242), 3 2024 Progress Report
(10 pages, 210), 4 FAQ (5 pages, 99), 5 Reports and Data (8 pages, 118), 6 COVID-19 Impact (3 pages, 47),
7 Figure 1 summary table (1 page, 7).

Chunk text is prefixed by the contextual chunker as `Prefix: <what this passage is>; Original: <the passage>`. Quote the
part after `Original:` when citing, and use the prefix to judge relevance.

## Join paths

```sql
-- names and region for a state-level result
FROM CDC_HAI.sir_2024 r JOIN CDC_HAI.dim_state s ON s.STATE_CD = r.STATE_CD   -- r.GEO_LEVEL='STATE'

-- SSI rows to procedure names
FROM CDC_HAI.sir_2024 r JOIN CDC_HAI.dim_procedure p ON p.PROCEDURE_CD = r.PROCEDURE_CD  -- r.HAI_CD='SSI'

-- 2024 result with its 2023-to-2024 trend
FROM CDC_HAI.sir_2024 r
JOIN CDC_HAI.sir_trend_2023_2024 t
  ON t.GEO_LEVEL=r.GEO_LEVEL AND t.STATE_CD=r.STATE_CD AND t.FACILITY_TYPE_CD=r.FACILITY_TYPE_CD
 AND t.HAI_CD=r.HAI_CD AND t.POPULATION_CD=r.POPULATION_CD

-- pandemic quarter to today
FROM CDC_HAI.covid_state_qtr_2020 c
JOIN CDC_HAI.sir_2024 r ON r.STATE_CD=c.STATE_CD AND r.HAI_CD=c.HAI_CD
 AND r.FACILITY_TYPE_CD='ACH' AND r.POPULATION_CD='ALL' AND r.GEO_LEVEL='STATE'

-- infection alongside device use
FROM CDC_HAI.sir_2024 r JOIN CDC_HAI.sur_2024 u
  ON u.STATE_CD=r.STATE_CD AND u.FACILITY_TYPE_CD=r.FACILITY_TYPE_CD AND u.POPULATION_CD=r.POPULATION_CD
 AND u.DEVICE_CD = CASE r.HAI_CD WHEN 'CLABSI' THEN 'CLD' WHEN 'CAUTI' THEN 'UCD' WHEN 'VAE' THEN 'VD' END

-- search hit to a citable title and page
FROM CDC_HAI.doc_chunks ch JOIN CDC_HAI.document d ON d.DOC_ID = ch.DOC_ID
```

Every fact row carries `SRC_WORKBOOK` and `SRC_SHEET`, so any number can be traced back to a CDC workbook sheet.
