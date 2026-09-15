# UJM Process Mapping — New Data Access Skill

This document maps the User Journey Model (UJM) for the "Ingest New Data" workflow
(DE-3) to the steps implemented in this skill. The UJM defines a 12-step process
across 4 personas; this skill implements the post-ingestion subset as a single
orchestrated workflow.

## UJM-to-Skill Step Mapping

| UJM Step | UJM Description | Skill Step | Implementation Notes |
|----------|----------------|-----------|---------------------|
| 1 | Classify Sensitive Data | Step 3 | Auto-suggest classification + PCI combination risk |
| 2 | Define Protection Strategy | Step 4 | Masking / exclusion / view-based filtering recommendations |
| 3 | Provision Roles & Identity | Steps 7, 10, 13 | Role identification at Step 7, approval at Gate 1, execution at Gate 3 |
| 4 | Ingest & Encrypt at Rest | — | Out of scope — handled by OTF / ingestion skills |
| 5 | Deploy Column-Level Encryption | — | Out of scope — requires Protegrity partner UDFs |
| 6 | Build Access Views | Steps 8, 11 | View design at Step 8, SQL generation at Step 11 |
| 7 | Implement Row-Level Security | Step 8 | WHERE clause in view definitions |
| 8 | Assess ETL / Consumption Impact | Step 9 | Downstream consumer impact check |
| 9 | Set Up Test Env & Test IDs | — | Partial — test SQL generated but test environments are manual |
| 10 | Execute Security Validation | Step 14 | Test SQL execution and result review |
| 11 | Customer Validation & Sign-Off | Step 14 | Gate 4 final acceptance |
| 12 | Document Access Model & Audit | Final Summary | Audit log + SQL file archive |

## UJM Personas vs. Skill Assumptions

| UJM Persona | UJM Responsibility | Skill Approach |
|-------------|-------------------|----------------|
| Customer Architect / Data SME | Owns classification decisions | User confirms sensitivity assessment at Gate 1 |
| Teradata Architect / Modeler | Designs security model | Agent recommends; user approves at Gate 1 |
| Teradata Data Engineer | Builds views/pipelines | Agent generates SQL; user reviews at Gate 2 |
| Teradata DBA | Manages roles/grants | Agent executes after Gate 3; user verifies at Gate 4 |

**MVP Simplification:** For MVP, the skill assumes a single operator who may wear
multiple hats. The agent infers the user's expertise level from their language and
database metadata rather than asking which persona they represent.

## UJM Steps Deferred to Future Versions

| UJM Step | Reason Deferred |
|----------|----------------|
| 4 — Encrypt at Rest | Requires infrastructure-level configuration beyond SQL |
| 5 — Column-Level Encryption | Requires Protegrity UDFs and centralized key management |
| 9 — Test Environment Setup | Requires DBA provisioning of test users/profiles |
| Multi-persona handoff workflow | Not in MVP scope — same-person assumption |
| Decomposition into 12 sub-skills | Keep as single orchestrated skill for now |

## Key Design Decisions from UJM Review

1. **Post-ingestion focus:** Tables must already exist. The OTF skill handles ingestion.
2. **Infer context from metadata:** Don't ask user about expertise level — query
   DBC system views to understand what roles, grants, and objects already exist.
3. **Audit log continuity:** The log persists so a paused workflow can resume
   from where it left off.
4. **Staging data needs protection too:** 9/10 times new data lands in a staging
   schema. Even staging tables need access controls.
5. **Simple views for new data:** New data onboarding typically uses SELECT * with
   column/row filters, not complex joins or transformations.
6. **Skills are composable:** An overarching orchestrator skill can chain OTF →
   new-data-access → other governance skills in the future.
