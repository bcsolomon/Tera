-- Template: structured question against CDC_HAI.
-- Fill the four pins, keep the significance verdict, keep the confidence bounds.
--
--   geography        GEO_LEVEL 'NATIONAL' (STATE_CD='US') or 'STATE'
--   facility type    ACH | CAH | IRF | LTACH | ONC | PED
--   population       ALL  (or ALL_SSI for surgical site infection; ICU/WARD/NICU are subsets of ALL)
--   procedure        PROCEDURE_CD IS NULL for non-SSI; a code plus SSI_MODEL for SSI

SELECT s.STATE_NM,
       h.HAI_NM,
       r.FACILITIES_REPORTING,
       r.OBSERVED,
       r.PREDICTED,
       r.SIR,
       r.SIR_CI_LOWER,
       r.SIR_CI_UPPER,
       CASE WHEN r.SIR_CI_LOWER > 1 THEN 'significantly above 2015 baseline'
            WHEN r.SIR_CI_UPPER < 1 THEN 'significantly below 2015 baseline'
            WHEN r.SIR IS NULL      THEN 'not reportable (predicted < 1.0 or suppressed)'
            ELSE 'no significant difference' END          AS verdict,
       t.BASE_SIR                                          AS sir_2023,
       t.PCT_CHANGE                                        AS pct_change_2023_2024,
       t.CHANGE_DIRECTION,
       sr.STATE_MANDATE_FLG,
       sr.VALIDATION_FLG,
       r.SRC_WORKBOOK,
       r.SRC_SHEET
FROM CDC_HAI.sir_2024 r
JOIN CDC_HAI.dim_state      s ON s.STATE_CD = r.STATE_CD
JOIN CDC_HAI.dim_hai_type   h ON h.HAI_CD   = r.HAI_CD
LEFT JOIN CDC_HAI.sir_trend_2023_2024 t
       ON t.GEO_LEVEL        = r.GEO_LEVEL
      AND t.STATE_CD         = r.STATE_CD
      AND t.FACILITY_TYPE_CD = r.FACILITY_TYPE_CD
      AND t.HAI_CD           = r.HAI_CD
      AND t.POPULATION_CD    = r.POPULATION_CD
LEFT JOIN CDC_HAI.state_reporting_2024 sr
       ON sr.STATE_CD         = r.STATE_CD
      AND sr.FACILITY_TYPE_CD = r.FACILITY_TYPE_CD
      AND sr.HAI_CD           = r.HAI_CD
WHERE r.GEO_LEVEL        = 'STATE'      -- pin 1
  AND r.FACILITY_TYPE_CD = 'ACH'        -- pin 2
  AND r.POPULATION_CD    = 'ALL'        -- pin 3
  AND r.PROCEDURE_CD IS NULL            -- pin 4
  -- AND r.HAI_CD = 'CLABSI'
  -- AND r.STATE_CD = 'AL'
ORDER BY r.HAI_CD, r.SIR;
