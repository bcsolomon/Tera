# Query recipes

Every query below was executed against the live `CDC_HAI` database and its expected result recorded. If a recipe returns
something materially different, the data changed or a filter was dropped. Run one statement per `base_readQuery` call.

## Recipe 1: national 2024 SIR by HAI, acute care hospitals

```sql
SELECT h.HAI_NM, r.OBSERVED, r.PREDICTED, r.SIR, r.SIR_CI_LOWER, r.SIR_CI_UPPER, r.FACILITIES_REPORTING
FROM CDC_HAI.sir_2024 r JOIN CDC_HAI.dim_hai_type h ON h.HAI_CD = r.HAI_CD
WHERE r.GEO_LEVEL='NATIONAL' AND r.FACILITY_TYPE_CD='ACH'
  AND r.POPULATION_CD='ALL' AND r.PROCEDURE_CD IS NULL
ORDER BY r.SIR;
```

Expect 5 rows: CDI 0.375, CAUTI 0.559, CLABSI 0.660, MRSA 0.703, VAE 1.105. Only VAE is above 1 and its CI (1.092 to 1.118)
excludes 1.0. SSI is absent by design; add recipe 2.

## Recipe 2: national 2024 SSI, all procedures and by procedure

```sql
-- all-procedures roll-up (adult model)
SELECT POPULATION_NM, PROCEDURES_CNT, OBSERVED, PREDICTED, SIR, SIR_CI_LOWER, SIR_CI_UPPER
FROM CDC_HAI.sir_2024
WHERE GEO_LEVEL='NATIONAL' AND FACILITY_TYPE_CD='ACH' AND HAI_CD='SSI'
  AND POPULATION_CD='ALL_SSI' AND SSI_MODEL='COMPLEX_AR';
```

Expect 1 row: 2,937,677 procedures, 23,983 observed, SIR 0.973 (0.960 to 0.985), a significant improvement on the baseline.
Swap `SSI_MODEL='COMPLEX_AR_PED'` for the pediatric model (59,732 procedures, SIR 1.004, CI 0.927 to 1.086, not significant).

```sql
-- procedures significantly above the 2015 baseline
SELECT p.PROCEDURE_CD, p.PROCEDURE_NM, r.PROCEDURES_CNT, r.OBSERVED, r.SIR, r.SIR_CI_LOWER, r.SIR_CI_UPPER
FROM CDC_HAI.sir_2024 r JOIN CDC_HAI.dim_procedure p ON p.PROCEDURE_CD = r.PROCEDURE_CD
WHERE r.GEO_LEVEL='NATIONAL' AND r.FACILITY_TYPE_CD='ACH' AND r.HAI_CD='SSI'
  AND r.POPULATION_CD='PROCEDURE' AND r.SSI_MODEL='COMPLEX_AR'
  AND r.SIR_CI_LOWER > 1
ORDER BY r.SIR DESC;
```

Expect 12 rows, led by prostate surgery 2.904, limb amputation 2.584, kidney transplant 2.274, ventricular shunt 1.378,
spinal fusion 1.256, cesarean section 1.225. Note the small denominators on the top three (5,960 / 17,797 / 7,326 procedures).

## Recipe 3: how many states are significantly off baseline, by HAI

```sql
SELECT HAI_CD, COUNT(*) AS states,
       SUM(CASE WHEN SIR_CI_LOWER > 1 THEN 1 ELSE 0 END) AS sig_above_baseline,
       SUM(CASE WHEN SIR_CI_UPPER < 1 THEN 1 ELSE 0 END) AS sig_below_baseline,
       SUM(CASE WHEN SIR IS NULL THEN 1 ELSE 0 END) AS not_reportable
FROM CDC_HAI.sir_2024
WHERE GEO_LEVEL='STATE' AND FACILITY_TYPE_CD='ACH' AND POPULATION_CD='ALL' AND PROCEDURE_CD IS NULL
GROUP BY 1 ORDER BY 1;
```

Expect 54 states/territories per HAI: VAE 24 above and 11 below; CLABSI 1 above and 46 below; CAUTI 0 and 46; CDI 0 and 52;
MRSA 0 and 42. This is the cleanest one-query summary of where the country stands.

## Recipe 4: one state's full 2024 profile

```sql
SELECT h.HAI_NM, r.FACILITIES_REPORTING, r.OBSERVED, r.PREDICTED, r.SIR, r.SIR_CI_LOWER, r.SIR_CI_UPPER,
       CASE WHEN r.SIR_CI_LOWER > 1 THEN 'above baseline'
            WHEN r.SIR_CI_UPPER < 1 THEN 'below baseline'
            WHEN r.SIR IS NULL THEN 'not reportable'
            ELSE 'no significant difference' END AS verdict,
       sr.STATE_MANDATE_FLG, sr.VALIDATION_FLG
FROM CDC_HAI.sir_2024 r
JOIN CDC_HAI.dim_hai_type h ON h.HAI_CD = r.HAI_CD
LEFT JOIN CDC_HAI.state_reporting_2024 sr
       ON sr.STATE_CD=r.STATE_CD AND sr.FACILITY_TYPE_CD='ACH' AND sr.HAI_CD=r.HAI_CD
WHERE r.GEO_LEVEL='STATE' AND r.FACILITY_TYPE_CD='ACH' AND r.POPULATION_CD='ALL'
  AND r.PROCEDURE_CD IS NULL AND r.STATE_CD='AL'
ORDER BY r.SIR;
```

Expect 5 rows for Alabama: CDI 0.465, CAUTI 0.530, CLABSI 0.730 (0.655 to 0.811, 83 hospitals, mandate Y, validated Y),
MRSA 0.867 (CI upper exactly 1.000, so "no significant difference"), VAE 1.165 (1.055 to 1.283, significantly above baseline
on only 36 reporting facilities). Note that VAE row: significantly above the 2015 baseline yet `CHANGE_DIRECTION='NO CHANGE'`
against 2023. The two tests answer different questions; see
[interpretation rules](./interpretation_rules.md#two-different-questions-versus-baseline-and-versus-last-year).

The `verdict` expression is the reusable significance test; reuse it rather than eyeballing the point estimate.

## Recipe 5: facility types compared

```sql
SELECT f.FACILITY_TYPE_NM, r.HAI_CD, r.FACILITIES_REPORTING, r.SIR, r.SIR_CI_LOWER, r.SIR_CI_UPPER
FROM CDC_HAI.sir_2024 r JOIN CDC_HAI.dim_facility_type f ON f.FACILITY_TYPE_CD = r.FACILITY_TYPE_CD
WHERE r.GEO_LEVEL='NATIONAL' AND r.POPULATION_CD='ALL' AND r.PROCEDURE_CD IS NULL
ORDER BY r.HAI_CD, r.SIR;
```

Useful contrasts in the result: CDI is lowest in long-term acute care (0.266) and inpatient rehab (0.323) but 0.375 in
acute care; critical access hospitals show CLABSI 1.054 with a wide interval (0.822 to 1.333, 989 facilities) so it is
**not** significantly above baseline; critical access VAE is 2.221 but on only 104 facilities (CI 1.083 to 4.075).

## Recipe 6: device utilization next to infections

```sql
SELECT d.DEVICE_NM, u.OBSERVED_DEVICE_DAYS, u.PREDICTED_DEVICE_DAYS, u.SUR, u.SUR_CI_LOWER, u.SUR_CI_UPPER,
       t.BASE_SUR AS sur_2023, t.PCT_CHANGE, t.CHANGE_DIRECTION
FROM CDC_HAI.sur_2024 u
JOIN CDC_HAI.dim_device_type d ON d.DEVICE_CD = u.DEVICE_CD
LEFT JOIN CDC_HAI.sur_trend_2023_2024 t
       ON t.GEO_LEVEL='NATIONAL' AND t.FACILITY_TYPE_CD='ACH'
      AND t.DEVICE_CD=u.DEVICE_CD AND t.POPULATION_CD=u.POPULATION_CD
WHERE u.GEO_LEVEL='NATIONAL' AND u.FACILITY_TYPE_CD='ACH' AND u.POPULATION_CD='ALL'
ORDER BY 1;
```

Expect central line days SUR 0.8134 (2023: 0.8345, -2.54 percent, DECREASE), urinary catheter days 0.7343 (-3.00, DECREASE),
ventilator days 0.8645 (-2.00, DECREASE). Device use is falling, which matters when interpreting the VAE SIR being above 1.

## Recipe 7: pandemic quarter joined to the 2024 result

```sql
SELECT s.STATE_NM, s.HHS_REGION,
       c.SIR_2019 AS q3_2019, c.SIR_2020 AS q3_2020, c.PCT_CHANGE AS covid_pct_change,
       c.CI_LOWER, c.CI_UPPER,
       r.SIR AS sir_2024, t.BASE_SIR AS sir_2023, t.PCT_CHANGE AS pct_change_2023_2024, t.CHANGE_DIRECTION
FROM CDC_HAI.covid_state_qtr_2020 c
JOIN CDC_HAI.dim_state s ON s.STATE_CD = c.STATE_CD
JOIN CDC_HAI.sir_2024 r ON r.STATE_CD=c.STATE_CD AND r.FACILITY_TYPE_CD='ACH'
                       AND r.HAI_CD='CLABSI' AND r.POPULATION_CD='ALL' AND r.GEO_LEVEL='STATE'
JOIN CDC_HAI.sir_trend_2023_2024 t ON t.STATE_CD=c.STATE_CD AND t.FACILITY_TYPE_CD='ACH'
                                  AND t.HAI_CD='CLABSI' AND t.GEO_LEVEL='STATE'
WHERE c.HAI_CD='CLABSI' AND c.REPORT_QTR=3 AND c.CI_LOWER > 0
ORDER BY c.PCT_CHANGE DESC;
```

Expect 17 states. Hawaii +280 percent (0.15 to 0.57), Arizona +148, Iowa +115, Georgia +103, Alabama +100, Florida +97,
California +76. Most are now below baseline: Hawaii's 2024 SIR is 0.597, Arizona 0.540, Alabama 0.730.

## Recipe 8: the pandemic arc by quarter

```sql
SELECT REPORT_QTR, HAI_CD, COUNT(*) AS states,
       SUM(CASE WHEN CI_LOWER > 0 THEN 1 ELSE 0 END) AS sig_increase,
       SUM(CASE WHEN CI_UPPER < 0 THEN 1 ELSE 0 END) AS sig_decrease
FROM CDC_HAI.covid_state_qtr_2020
WHERE HAI_CD IN ('CLABSI','CAUTI','MRSA')
GROUP BY 1,2 ORDER BY 2,1;
```

Expect a clean escalation across 2020 for CLABSI: 0 states with a significant increase in Q1, then 12, 17, and 25 by Q4;
CAUTI 0, 2, 5, 11; MRSA 1, 6, 7, 15. Q1 was pre-pandemic and shows the opposite pattern (5 significant CLABSI decreases).

## Recipe 9: what does a SIR adjust for

```sql
SELECT FACILITY_TYPE_CD, MODEL_NM, FACTORS_TEXT
FROM CDC_HAI.risk_model_factor
WHERE RATIO_TYPE='SIR' AND MODEL_NM LIKE 'CLABSI%'
ORDER BY 1,2;
```

Expect the non-NICU model (intercept, medical school affiliation, location type, facility type, bed size) and the NICU model
(intercept, birthweight) for ACH and CAH.

## Recipe 10: location strata inside a state

```sql
SELECT r.POPULATION_CD, r.POPULATION_NM, r.FACILITIES_REPORTING, r.DEVICE_DAYS, r.OBSERVED, r.SIR,
       r.SIR_CI_LOWER, r.SIR_CI_UPPER
FROM CDC_HAI.sir_2024 r
WHERE r.GEO_LEVEL='STATE' AND r.FACILITY_TYPE_CD='ACH' AND r.HAI_CD='CLABSI'
  AND r.STATE_CD='CA' AND r.POPULATION_CD IN ('ALL','ICU','WARD','NICU')
ORDER BY CASE r.POPULATION_CD WHEN 'ALL' THEN 1 WHEN 'ICU' THEN 2 WHEN 'WARD' THEN 3 ELSE 4 END;
```

`ALL` is the total; the other three are subsets of it and must not be summed. Use this shape when asked whether a problem
sits in intensive care or on the wards.

## Patterns worth reusing

**The significance verdict** (recipe 4) as a `CASE` expression, on any ratio column pair.

**Counting rather than ranking.** Prefer "24 states are significantly above the baseline" over "state X is worst", because
point-estimate ranking ignores overlapping intervals and reporting differences.

**Always project the interval.** `SELECT ... SIR, SIR_CI_LOWER, SIR_CI_UPPER` should be reflexive.

**Filter on the CDC verdict for trends.** `CHANGE_DIRECTION IN ('INCREASE','DECREASE')` uses CDC's own test rather than
re-deriving significance from `P_VALUE`.
