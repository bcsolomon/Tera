---
name: CDC HAI Analyst (Teradata CDC_HAI)
description: Answer questions about US healthcare-associated infections by querying the CDC_HAI database in Teradata, which holds CDC/NHSN 2024 Progress Report SIR and SUR results, 2020 COVID-impact quarterly tables, and semantically searchable CDC guidance documents.
tags:
  - teradata
  - healthcare
  - hai
  - nhsn
  - cdc
  - sir
  - rag
  - vector-search
  - hybrid-retrieval
created_by: Brian Solomon
last_updated: 2026-09-15
---

# CDC HAI Analyst (Teradata `CDC_HAI`)

## Overview and purpose

`CDC_HAI` on the Teradata demo box holds both halves of the CDC healthcare-associated infection (HAI) story in one place:

- **Structured** (9,127 rows): CDC/NHSN **2024 National and State HAI Progress Report** standardized infection ratios (SIR)
  and standardized utilization ratios (SUR) for five facility types, 2023-to-2024 trends, state reporting characteristics,
  and the **2020 COVID-impact** quarterly comparisons.
- **Unstructured** (1,274 chunks with 384-dimension embeddings): seven CDC PDFs, including the NHSN SIR and SUR methodology
  guides, the Progress Report narrative, the FAQ, and the COVID-impact page.

Use this skill to answer questions such as "which HAI got worse in 2024?", "how did CLABSI change during the pandemic in
my state?", "which surgical procedures have infection rates above the national baseline?", and "how does NHSN define a
significant SIR change?" — the last of which is answered from the documents, not the tables.

Run all SQL through the `teradata` MCP server (`base_readQuery`). Every query in this skill has been executed against the
live database and its expected result is recorded, so you can verify you are reading the data correctly.

## Key concepts

**SIR (standardized infection ratio)** = observed infections / predicted infections, where predicted comes from an NHSN
risk-adjustment model fitted to a **2015 national baseline**. SIR below 1 means fewer infections than the 2015 baseline
predicts; above 1 means more. It is a ratio against a model, **not** an infection rate and **not** a comparison between states.

**SUR (standardized utilization ratio)** = observed device days / predicted device days, same baseline idea, for central
lines, urinary catheters and ventilators. It measures how much devices are used, which is the exposure behind device-associated infections.

**Significance comes from the confidence interval, never from the point estimate.** A SIR is significantly different from the
2015 baseline only when its 95 percent interval excludes 1.0: `SIR_CI_LOWER > 1` (worse) or `SIR_CI_UPPER < 1` (better).
For the 2020 COVID tables the interval is around the percent change, so it excludes **0**: `CI_LOWER > 0` is a significant increase.

**A NULL SIR is meaningful.** NHSN does not publish a SIR when predicted infections are below 1.0, and suppresses cells for
states with too few facilities. NULL means "not reportable", not zero. Two states have no ACH SIR for most HAI types; six lack VAE.

**Grain of the fact tables.** Every row of `sir_2024` is one `GEO_LEVEL` (NATIONAL or STATE) × `STATE_CD` (`'US'` for national)
× `FACILITY_TYPE_CD` × `HAI_CD` × `POPULATION_CD` × `PROCEDURE_CD` × `CDC_LOCATION_NM` × `SSI_MODEL`. Miss a filter and you
will sum national totals into state numbers, or add ICU rows on top of the all-locations row that already includes them.

**The canonical filter set.** Almost every structured query starts here:

```sql
WHERE GEO_LEVEL = 'STATE'          -- or 'NATIONAL' (which carries STATE_CD='US')
  AND FACILITY_TYPE_CD = 'ACH'     -- ACH, CAH, IRF, LTACH, ONC, PED
  AND POPULATION_CD = 'ALL'        -- 'ALL' excludes ICU/WARD/NICU/location strata
  AND PROCEDURE_CD IS NULL         -- excludes the per-procedure SSI rows
```

**Surgical site infection is the exception to that pattern.** SSI has no `POPULATION_CD='ALL'` row. Use
`POPULATION_CD='ALL_SSI'` for the all-procedures roll-up, or `POPULATION_CD='PROCEDURE'` with a `PROCEDURE_CD` for one
operation, and always pin `SSI_MODEL='COMPLEX_AR'` (adult) versus `'COMPLEX_AR_PED'` (pediatric), or you will double-count.

Full column lists, code lists and join paths: [data dictionary](./references/data_dictionary.md).
Interpretation and claim-safety rules: [interpretation rules](./references/interpretation_rules.md).

## Usage instructions

Route the question before writing any SQL:

| Question shape | Route | Where |
|---|---|---|
| A number, rate, ranking, trend, or "which states/procedures..." | Structured SQL over the fact tables | [query recipes](./references/query_recipes.md) |
| A definition, method, caveat, or "what does CDC say about..." | Semantic search over document chunks | [semantic search](./references/semantic_search.md) |
| A number that needs its method or caveat explained, or a finding that needs a citation | Both: query, then search, then answer with the figure and the source | [semantic search](./references/semantic_search.md#hybrid-patterns) |

Then:

1. **Pin the grain.** Choose geography, facility type, population and procedure explicitly. If the user did not say, assume
   acute care hospitals (`ACH`) and all locations, and say so in your answer.
2. **Select the confidence bounds alongside every ratio.** Never return a SIR or SUR without `*_CI_LOWER` and `*_CI_UPPER`;
   you need them for any claim about better or worse.
3. **Run it through MCP** with `base_readQuery`, one statement per call.
4. **Read NULLs as "not reportable"** and say so rather than dropping the row silently, because a suppressed state is
   information (too few facilities reported).
5. **Cite documents by title and page.** Search results carry `DOC_TITLE` and `PAGE_NUMBER`; use them, not the S3 filename.
6. **State the baseline.** Any SIR statement should mention that it is against the 2015 national baseline, otherwise the
   reader will hear it as a raw infection rate.

Statistics are collected on the fact tables. If a join suddenly takes minutes, re-collect them
([data quirks](./references/data_quirks.md#performance)).

## Examples

**National 2024 picture for acute care hospitals** (verified output):

```sql
SELECT h.HAI_NM, r.OBSERVED, r.PREDICTED, r.SIR, r.SIR_CI_LOWER, r.SIR_CI_UPPER
FROM CDC_HAI.sir_2024 r JOIN CDC_HAI.dim_hai_type h ON h.HAI_CD = r.HAI_CD
WHERE r.GEO_LEVEL='NATIONAL' AND r.FACILITY_TYPE_CD='ACH'
  AND r.POPULATION_CD='ALL' AND r.PROCEDURE_CD IS NULL
ORDER BY r.SIR;
```

| HAI | Observed | SIR | 95% CI |
|---|---:|---:|---|
| C. difficile | 31,595 | 0.375 | 0.371 to 0.379 |
| CAUTI | 15,347 | 0.559 | 0.550 to 0.568 |
| CLABSI | 18,165 | 0.660 | 0.650 to 0.669 |
| MRSA bacteremia | 7,605 | 0.703 | 0.688 to 0.719 |
| **VAE** | 26,509 | **1.105** | 1.092 to 1.118 |

The headline: four of five device and LabID infection types sit well below the 2015 baseline, while **ventilator-associated
events are about 10 percent above it** and the interval excludes 1.0, so that gap is statistically significant. SSI is not in
this list because it needs `POPULATION_CD='ALL_SSI'` (2024 all-procedures SIR 0.973, CI 0.960 to 0.985).

**A pandemic-to-present story in one query** (the demo's opening): states whose CLABSI SIR rose significantly in 2020 Q3,
joined to their 2024 result and 2023-to-2024 trend. Seventeen states qualify, led by Hawaii (+280 percent), Arizona
(+148 percent) and Iowa (+115 percent); most have since fallen back below the baseline. Full SQL in
[query recipes](./references/query_recipes.md#recipe-7-pandemic-quarter-joined-to-the-2024-result).

**Documents answer the method question** the numbers raise. Searching "when is an SIR not reported?" returns the SIR Guide
page 12 passage stating the SIR is only calculated when predicted infections reach at least 1.0 — which is exactly why
some states show NULL. See [semantic search](./references/semantic_search.md).

## Reference documents

- [data_dictionary.md](./references/data_dictionary.md) — every table, column, code list and join path.
- [query_recipes.md](./references/query_recipes.md) — ten tested queries with expected results.
- [interpretation_rules.md](./references/interpretation_rules.md) — SIR and SUR semantics, significance tests, suppression, and what not to claim.
- [semantic_search.md](./references/semantic_search.md) — the vector-search statement, scoping, and hybrid patterns.
- [data_quirks.md](./references/data_quirks.md) — source anomalies, load-time decisions, and performance notes.
- `assets/templates/` — copy-paste SQL skeletons for a structured query and a semantic search.
