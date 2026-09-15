# Interpretation rules and claim safety

This data is about infections in named US states and hospital types. Wrong framing produces statements that sound
authoritative and are wrong, or that impugn a state's hospitals on noise. These rules keep answers defensible.

## What a SIR is and is not

| It is | It is not |
|---|---|
| Observed infections divided by infections predicted by an NHSN risk model fitted to a **2015 national baseline** | An infection rate, a percentage, or infections per 1,000 patient days |
| A comparison of a reporting group against its own risk-adjusted expectation | A comparison between two states, or between a state and the nation |
| Risk-adjusted for the factors in `risk_model_factor` (bed size, location type, medical school affiliation, birthweight for NICU) | Adjusted for everything that differs between hospitals, such as case mix beyond those factors, staffing, or testing practice |
| Calculated only when predicted infections reach at least 1.0 | Available for every state and stratum |

Say "below the 2015 national baseline", not "below average". The baseline is a fixed historical reference, so a SIR of 0.66
means about a third fewer CLABSIs than 2015 practice predicted for the same mix of hospitals and locations.

## Significance: always from the interval

| Table | Interval around | Significant worse | Significant better |
|---|---|---|---|
| `sir_2024`, `sur_2024` | the ratio, versus 1.0 | `SIR_CI_LOWER > 1` | `SIR_CI_UPPER < 1` |
| `covid_state_qtr_2020` | the percent change, versus 0 | `CI_LOWER > 0` | `CI_UPPER < 0` |
| `covid_natl_location_qtr_2020` | the percent change | `SIGNIFICANT_FLG='Y'` (CDC's asterisk) | same flag, negative change |
| `sir_trend_2023_2024`, `sur_trend_2023_2024` | CDC's own test | `CHANGE_DIRECTION='INCREASE'` | `CHANGE_DIRECTION='DECREASE'` |

`CHANGE_DIRECTION='NO CHANGE'` can accompany a large-looking `PCT_CHANGE`. Hawaii's 2020 Q3 CLABSI rose 280 percent with a
very wide interval (18.6 to 1,640.1) because the 2019 baseline was 0.15 on few events. Report the interval or the CDC
verdict whenever the percent change is dramatic and the denominator is small.

## Two different questions: versus baseline and versus last year

`sir_2024` answers "how does this compare with the 2015 baseline?" while `sir_trend_2023_2024` answers "did it move since
last year?". A row can be significantly above the baseline and show no significant year-over-year change at the same time.
Alabama's 2024 acute care VAE is exactly that: SIR 1.165 (CI 1.055 to 1.283, so significantly above baseline) with
`CHANGE_DIRECTION='NO CHANGE'` against its 2023 SIR of 1.025. The correct statement is "persistently above the 2015
baseline, with no statistically significant change from 2023", not "getting worse" and not "no problem".

## Never rank states on the point estimate alone

Point-estimate league tables are the most common misuse of this data. Before comparing two states, consider:

1. **Do the intervals overlap?** If they do, the difference is not established.
2. **How many facilities reported?** `FACILITIES_REPORTING` of 10 is not comparable to 300.
3. **Is there a state reporting mandate?** `state_reporting_2024.STATE_MANDATE_FLG` (`Y`, `N`, or `M` for mid-year) changes
   who reports and how completely.
4. **Was there validation?** `VALIDATION_FLG` indicates the state did validation activity, which affects data quality.

Prefer counts ("24 states are significantly above the 2015 baseline for VAE") and named exceptions with their intervals
over ordered lists. When the user explicitly asks for the highest or lowest, give the value with its interval and add the
facility count, so the reader can see how solid it is.

Worked caution: Puerto Rico is the only state or territory whose 2024 ACH CLABSI SIR is significantly above 1
(2.578, CI 2.337 to 2.837, 410 infections across 42 facilities). That is a real signal, not noise, but the right framing is
"significantly above the 2015 baseline", with a note that territory healthcare context differs, not "the worst state for
infection control".

## NULL and suppressed values

| Appearance | Meaning | How to report |
|---|---|---|
| `SIR` NULL, `OBSERVED` present | Predicted infections below 1.0, so NHSN does not compute a SIR | "Not reportable: too few predicted infections" |
| Whole row NULL except `FACILITIES_REPORTING` | CDC suppressed the cell (fewer than the minimum facilities) | "Suppressed by CDC for small numbers" |
| `PCT_CHANGE` NULL with `PCT_CHANGE_NOTE='>>100'` | Change exceeded CDC's printable range | Quote the note, not a number |
| `CI_NOTE='inestimable'` or `'lower inestimable'` | Interval could not be estimated, typically a zero numerator | Report the change without claiming significance |

Do not impute, do not treat NULL as zero, and do not drop suppressed rows silently when counting states; say how many were
not reportable. Guam and the Virgin Islands are fully suppressed across all 28 COVID-era sheets but retain real hospital counts.

## Population strata do not add up

`ICU`, `WARD` and `NICU` rows are subsets of the `ALL` row for the same state and HAI. Summing them double-counts.
`CDC_LOCATION` rows are a finer cut of the same infections again. When asked for a total, use `POPULATION_CD='ALL'`
(or `ALL_SSI` for surgical site infections) and nothing else.

Likewise, oncology and pediatric rows appear twice in the model on purpose: as free-standing hospitals
(`FACILITY_TYPE_CD` `ONC` or `PED`) and as specialty locations inside acute care hospitals (`FACILITY_TYPE_CD='ACH'` with
`POPULATION_CD` `ONC_LOC` or `PED_LOC`). They are different denominators; never combine them.

## SIR and SUR together

A SIR above 1 with a SUR below 1 is the interesting case: fewer device days than predicted, yet more infections than
predicted for those days. National 2024 acute care shows exactly that for ventilators (VAE SIR 1.105, ventilator-day SUR
0.8645). The defensible reading is that ventilator-associated events remain elevated against the 2015 baseline while
ventilator use has fallen; the causal explanation belongs to the documents, not to this inference.

## Year and scope boundaries

- Structured coverage is **2024** results with a **2023** comparison, plus **2020 versus 2019 by quarter**. There is nothing
  for 2021 or 2022 in the tables; the COVID-impact document mentions 2021 narratively.
- The 2020 tables are **acute care hospitals only** and restricted to consistent reporters, so their facility counts do not
  match the 2024 tables.
- 2020 Q4 data are preliminary (frozen 1 April 2021) per CDC's own note.
- The 2024 report reflects data as published; it is not live surveillance.

If asked about a year or facility type outside that, say what is present rather than approximating from an adjacent year.

## Attribution

Numbers come from CDC/NHSN published workbooks; every fact row carries `SRC_WORKBOOK` and `SRC_SHEET` for traceability.
Quotes come from CDC PDFs; cite `DOC_TITLE` and `PAGE_NUMBER`. This database is a demo copy, so for any decision-grade use
point the reader to the CDC source rather than to this table.
