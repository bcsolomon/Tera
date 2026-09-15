---
name: prior-auth-review
description: Run a prior authorization care pathway review for a specific PA number. Trigger when the user says "run the prior auth review for", "PA review for", "care pathway review for", "review prior auth", or provides a PA number like PA-2026-003417. Queries the HCLS Teradata database, checks each CPT code against care_pathways prerequisites, verifies claims history, and produces a color-coded gap analysis visualization.
---

# Prior Authorization Care Pathway Review

This skill reviews a prior authorization request by checking its CPT codes against the `HCLS.care_pathways` table to identify missing prerequisite treatments, then verifies whether those prerequisites appear in the member's claims history.

## Trigger phrases

- "Run the prior auth review for PA-2026-003417"
- "Review PA-2026-003417 against care pathways"
- "Care pathway review for PA XXXX"
- "Check prior auth PA-XXXX"

## Extract the PA Number

Parse the PA number from the user's message — format is `PA-YYYY-NNNNNN`. If the user provides a number without the prefix, prepend `PA-`.

---

## Step-by-Step Execution

Execute each step sequentially using `base_readQuery`. Use **TOP** to limit rows (not LIMIT — this is Teradata).

---

### Step 1 — Load PA header

```sql
SELECT auth_request_id, auth_request_num, member_id, ordering_provider_id,
       requested_dos, auth_status_id, create_ts
FROM HCLS.prior_auth_request
WHERE auth_request_num = '{pa_number}'
```

Save: `auth_request_id`, `member_id`, `ordering_provider_id`, `requested_dos`.  
If no row returned → tell the user the PA was not found and stop.

---

### Step 2 — Load member demographics

```sql
SELECT member_id_num, first_name, last_name, dob, gender
FROM HCLS.member
WHERE member_id = {member_id}
```

Save: `member_id_num` (e.g. `MBR-884201`), full name.

---

### Step 3 — Load ordering provider

```sql
SELECT first_name, last_name, npi, primary_specialty, credential
FROM HCLS.provider
WHERE provider_id = {ordering_provider_id}
```

> **Note:** The column is `primary_specialty` — NOT `specialty`.

Save: provider name, `primary_specialty`.

---

### Step 4 — Load CPT procedure codes on the request

```sql
SELECT a.cpt_code, c.cpt_desc
FROM HCLS.auth_cpt_code a
JOIN HCLS.cpt_codes c ON a.cpt_code = c.cpt_code
WHERE a.auth_request_id = {auth_request_id}
```

Save the full list of CPT codes as `{cpt_list}`.

---

### Step 5 — Load ICD-10 diagnosis codes

```sql
SELECT icd_code, diagnosis_sequence, icd_description_override
FROM HCLS.auth_icd_code
WHERE auth_request_id = {auth_request_id}
ORDER BY diagnosis_sequence
```

---

### Step 6 — Load request detail (indications and treatments)

```sql
SELECT * FROM HCLS.auth_request_detail
WHERE auth_request_id = {auth_request_id}
```

---

### Step 7 — Check care pathways for prerequisites

```sql
SELECT cp.cpt_code, cp.cpt_code_prereq, c.cpt_desc AS prereq_desc
FROM HCLS.care_pathways cp
JOIN HCLS.cpt_codes c ON cp.cpt_code_prereq = c.cpt_code
WHERE cp.cpt_code IN ({comma_separated_cpt_codes})
```

- CPT codes that **appear in results** → have prerequisites that must be verified
- CPT codes that **do NOT appear** → no prerequisites, auto-approved (show as GREEN)

Group prerequisites by `cpt_code` for the visualization.

---

### Step 8 — Check claims history for each prerequisite

For **each unique prerequisite CPT code** from Step 7, run:

```sql
SELECT TOP 5
    h.Bill_ID,
    h.Service_Bill_From_Date,
    d.HCPCS_Line_Procedure_Billed_Code,
    d.HCPCS_Line_Procedure_Paid_Code,
    h.Rendering_Bill_Provider_Last_Name_or_Group,
    h.Rendering_Bill_Provider_First_Name
FROM HCLS.WORKERS_COMP_HDR h
JOIN HCLS.WORKERS_COMP_DTL d ON h.Bill_ID = d.Bill_ID
WHERE h.Patient_Account_Number = '{member_id_num}'
  AND d.HCPCS_Line_Procedure_Billed_Code = '{prereq_cpt_code}'
  AND h.Service_Bill_From_Date < '{requested_dos}'
ORDER BY h.Service_Bill_From_Date DESC
```

**Classification rules:**

| Result | Status | Color |
|--------|--------|-------|
| At least one claim row returned, service date before requested DOS | ✅ GREEN — Satisfied | `#27ae60` |
| No claim found, but treatment documented in `auth_request_detail` (treatment_type_id not null) | ⚠️ AMBER — Partial | `#f39c12` |
| No claim found, no treatment documentation | ⛔ RED — Missing | `#e74c3c` |

> **Known data note:** In this environment `Patient_Account_Number` in `WORKERS_COMP_HDR` does not map to `member_id_num` — the claims query will return zero rows for all members. This is expected. Prerequisites will show RED, which tells the correct demo story: *"provider needs to submit evidence of conservative treatment."*

---

### Step 9 — Check treatment documentation for AMBER classification

```sql
SELECT ard.treatment_type_id, tt.treatment_code, tt.treatment_name,
       pd.duration_code, pd.duration_label
FROM HCLS.auth_request_detail ard
JOIN HCLS.treatment_type tt ON ard.treatment_type_id = tt.treatment_type_id
LEFT JOIN HCLS.prior_treatment_duration pd ON ard.duration_id = pd.duration_id
WHERE ard.auth_request_id = {auth_request_id}
  AND ard.treatment_type_id IS NOT NULL
```

If `treatment_code = 'PHYSICAL_THERAPY'` is documented and the corresponding CPT codes (97001, 97110) are absent from claims → upgrade those prerequisites from RED to AMBER.

---

### Step 10 — Load clinical notes

```sql
SELECT TOP 5 note_type, note_text, prior_test_name, prior_test_result,
       create_ts AS note_date
FROM HCLS.auth_clinical_notes
WHERE auth_request_id = {auth_request_id}
ORDER BY create_ts DESC
```

> **Note:** The date column is `create_ts` aliased as `note_date` — there is no `note_date` column.

---

### Step 11 — Produce the visualization

Generate a complete standalone HTML visualization using this template structure. Use inline CSS only — no external dependencies.

**Design requirements (from project standards):**
- Background: `#1a1a2e` (dark)
- Card background: `#16213e`
- Card border: `#454446`
- Title: **"Teradata Prior Auth Care Pathway Review"** in `#FF5F02` (Teradata Orange), bold
- Subtitles and section headers: `#fd7d69`
- Light text: `#fafafa`
- Max width: `800px`, responsive
- All chart containers fixed size

**Visualization content:**

1. **Header card** — PA number, member name + ID, provider name + specialty, requested DOS, ICD codes

2. **Overall status banner** — colored border:
   - RED border if any RED prerequisites
   - AMBER border if any AMBER prerequisites (no RED)
   - GREEN border if all prerequisites satisfied

3. **Care Pathway Gap Analysis section** — for each CPT code that has prerequisites:
   - Show the requested CPT code and description in a card
   - Under it, show each prerequisite as a badge:
     - Border and label color matching RED / AMBER / GREEN status
     - Prerequisite CPT code + description
     - Evidence text (claim date + provider if GREEN, note if AMBER, "Not found in claims history" if RED)

4. **Auto-Approved section** — CPT codes with no prerequisites, each shown with a GREEN border

5. **Summary section** — overall status, denial codes, recommended action

6. **Legend** — GREEN / AMBER / RED with descriptions

---

### Step 12 — Text summary

After the visualization, provide a concise text summary:

- **Overall status**: PENDING / PEND / APPROVED
- **Member**: name, ID
- **Provider**: name, specialty
- **Gaps**: for each RED/AMBER prerequisite — what the provider must submit
- **Applicable denial codes:**
  - `44` — Documentation of conservative treatment failure is required
  - `0F` — Not medically necessary
  - `0U` — Additional patient information required
- **Recommended next action**

---

## Reference: HCLS Table Schema (verified column names)

| Table | Key columns |
|-------|-------------|
| `HCLS.prior_auth_request` | `auth_request_id`, `auth_request_num`, `member_id`, `ordering_provider_id`, `requested_dos`, `auth_status_id` |
| `HCLS.member` | `member_id`, `member_id_num`, `first_name`, `last_name`, `dob`, `gender` |
| `HCLS.provider` | `provider_id`, `npi`, `first_name`, `last_name`, `primary_specialty`, `credential` |
| `HCLS.auth_cpt_code` | `auth_request_id`, `cpt_code` |
| `HCLS.cpt_codes` | `cpt_code`, `cpt_desc` |
| `HCLS.auth_icd_code` | `auth_request_id`, `icd_code`, `diagnosis_sequence`, `icd_description_override` |
| `HCLS.auth_request_detail` | `auth_request_id`, `treatment_type_id`, `duration_id`, `indication_id` |
| `HCLS.treatment_type` | `treatment_type_id`, `treatment_code`, `treatment_name` |
| `HCLS.prior_treatment_duration` | `duration_id`, `duration_code`, `duration_label` |
| `HCLS.care_pathways` | `cpt_code`, `cpt_code_prereq` |
| `HCLS.auth_clinical_notes` | `note_id`, `auth_request_id`, `note_type`, `note_text`, `prior_test_name`, `prior_test_dt`, `prior_test_result`, `create_ts` |
| `HCLS.WORKERS_COMP_HDR` | `Bill_ID`, `Patient_Account_Number`, `Service_Bill_From_Date`, `Rendering_Bill_Provider_Last_Name_or_Group` |
| `HCLS.WORKERS_COMP_DTL` | `Bill_ID`, `HCPCS_Line_Procedure_Billed_Code`, `HCPCS_Line_Procedure_Paid_Code` |
| `HCLS.preauth_codes` | denial/pend reason codes |

## Demo test case

- **PA number:** `PA-2026-003417` (`auth_request_id = 1`)
- **Member:** Robert Martinez, `MBR-884201`
- **Provider:** Dr. Sarah Chen, Orthopedic Surgery
- **Requested DOS:** 2026-03-25
- **CPT codes:** `73223` (shoulder MRI), `77002`, `23350`, `20610`
- **Expected result:**
  - `73223` → requires `97001` (PT Evaluation) and `97110` (Therapeutic Exercises) → both RED
  - `77002`, `23350`, `20610` → no prerequisites → auto-approved GREEN

## Teradata SQL rules

- Use `TOP N` to limit rows, never `LIMIT N`
- Qualify all tables with the schema: `HCLS.table_name`
- Use `EXPLAIN {sql}` to debug slow queries before re-running
- String comparisons are case-sensitive
