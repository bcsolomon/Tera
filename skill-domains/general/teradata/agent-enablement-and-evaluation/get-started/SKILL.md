---
name: get-started
description: 'Entry point for new Tera users. Runs a 3-question survey, delivers a personalized quick start, and routes every prompt to the correct Teradata skill by role, goal, and intent. Use when a user is new to Tera, needs orientation, or asks where to begin.'
metadata:
  author: teradata
  version: "1.0"
---

# Teradata Get Started

## When to Use

- User types `/get-started` — always runs the full experience
- User says "I'm new", "how do I get started", "where do I begin", "what can Tera do", "walk me through this"
- User needs orientation before diving into a specific workflow
- User's role or goal is unclear before routing to an SME

Several behaviours require platform support not yet in place (auto-invocation at session start, foundations check results, returning user detection, SME sub-agent handoff). Until those are ready the skill runs reliably when invoked explicitly via `/get-started`.

## Core Concepts

**Flow:** Foundations results (if provided by platform) → Session Type Detection → Survey → Quick Start → Routing

**Session types detected from the first message:**

| Session type | Signal | Action |
|---|---|---|
| New user | No first message, or first message is a greeting | Run Welcome and Survey |
| New user | First message mentions "I'm new" or "get started" | Run Welcome and Survey |
| Returning user | Harness passes a returning-user flag or prior session context | Skip survey — greet briefly ("Welcome back. What are you working on today?"), route by message content |
| Power user bypass | First message contains SQL, EXPLAIN output, error text, or a direct technical question | Skip survey — route based on message content |
| Explicit invocation | User typed `/get-started` | Run full experience regardless of context |

Returning user detection requires the harness to pass prior session context — not available today. Until then treat all sessions as new unless the user says otherwise.

**Post-survey routing** uses the role × goal table in [./references/skill-routing.md](./references/skill-routing.md). Per-prompt routing relies on the skill system's description-based discovery.

Telemetry events are instrumented at the harness and UI layers — not by this skill.

## Foundations Check Results

The agent cannot run foundations checks — that is executed by up-tera at page load. If the platform passes results in the session context, use them:

- All pass: proceed to session type detection silently
- Any fail: surface the issue using [./references/platform-setup.md](./references/platform-setup.md) for the failure message and [./references/tera-ui.md](./references/tera-ui.md) for the UI path. Do not block the user.
- No results provided: skip this step and proceed

Failure guidance by check:

| Check | Who can fix | Where to send the user |
|---|---|---|
| LLM Provider | Admin only | `/settings/ai-providers` — if empty, contact admin |
| Teradata MCP Server | User | `/customize/connectors` → Test Connection |
| Tera Agent | Admin only | `/settings` → Agents |
| Teradata Skills | User | `/customize/skills` |

## Welcome and Survey

Open with a warm greeting and present all three questions in the same message. Do not wait for a response between them.

Greeting template:
"Welcome to Tera — your AI-powered workspace for Teradata.
I'll ask you three quick questions so I can point you to the right starting point.
You can skip anytime and I'll give you a general overview instead."

Survey (present exactly):

**1. What's your role?**
A) Data Analyst  B) Data Engineer  C) Business Analyst
D) Data Scientist  E) DBA / Administrator  F) Developer  G) Other

**2. How would you rate your SQL experience?**
A) Beginner — new to SQL
B) Intermediate — can write basic queries
C) Advanced — comfortable with complex queries & optimization

**3. What's your primary goal right now?**
A) Explore data and create reports
B) Build data pipelines or ETL processes
C) Optimize query performance
D) Deploy models or analytics
E) Learn the platform
F) Solve a specific business problem

Or say **skip** for a general overview.

Accept any answer format. If ambiguous pick the closest match and note it briefly.

## Personalized Quick Start

Before selecting content from [./references/quick-start.md](./references/quick-start.md), apply the PII override: if PII, access control, or compliance was mentioned during the survey, route to `teradata-security` and recommend GuardBot regardless of role × goal.

If a specific role × goal section is missing, fall back to the closest matching role section (ignoring goal), then the General Quick Start if no role match exists. Never invent content — always use an existing section.

Output format:

**Your best first steps:**
1. [Concrete action scoped to role + goal]
2. [Concrete action scoped to role + goal]
3. [Concrete action scoped to role + goal]

**Your go-to expert(s):**
[Name · Bot] — [one sentence on what they help with]
[Second Name · Bot] — [include if dual-SME routing applies, e.g. DBA + performance]

**A starter query:**
[SQL snippet relevant to their goal]

**When you're ready to go deeper:**
[1–2 sentences on natural next topics]

Close with: "Not the right fit? Say **adjust** to refine — no need to start over."

Then name the recommended SME(s): if `/pt-sme-hub` is available, tell the user to type it and ask for [SME name]. If unavailable, name the SME and continue in conversation.

## Skill Routing

On every prompt after the survey, identify the primary skills from [./references/skill-routing.md](./references/skill-routing.md) Layer 1 using the user's role and goal. The skill system's description-based discovery handles per-prompt routing on follow-on questions.

One override applies at all times: if PII, access control, or compliance is mentioned, always route to `teradata-security` and recommend GuardBot.

## Agentic Tour

If the user asks for a guided introduction, run this three-step live sequence:

1. **Verify the connection** — run a DBC query and report what was found:

```sql
SELECT DatabaseName, SUM(CurrentPerm)/1e9 AS SizeGB
FROM DBC.DiskSpaceV GROUP BY 1 ORDER BY 2 DESC SAMPLE 5;
```

2. **Run a relevant query** — use the user's role and goal from the survey, or a general exploration query if skipped. Explain the results in plain language.

3. **Suggest three next steps** — concrete and specific to what was found and the user's goal.

The tour ends after step 3. Normal routing resumes.

## Exit / Completion

Get-started is complete when the user sends their first follow-on question after the quick start or tour. From that point:

- Route each follow-on question via Layer 1 skill routing
- Do not re-run the survey or foundations check in the same session
- If the user types `/get-started` again, re-run the full experience from the top

## Common Errors / Troubleshooting

| Situation | Response |
|-----------|----------|
| Foundations results show a failure | Use [platform setup](./references/platform-setup.md) and [Tera UI guide](./references/tera-ui.md) to guide the user; do not block |
| No foundations results provided | Skip the check, proceed to session type detection |
| User skips the survey | Deliver general quick start from [quick-start reference](./references/quick-start.md) |
| Role answer is ambiguous | Pick closest match: "I'll treat that as Data Analyst — let me know if that's off" |
| PII or sensitive data mentioned | Route to `teradata-security`; if `/pt-sme-hub` is available tell the user to invoke it and ask for GuardBot, otherwise name GuardBot and continue in conversation |
| User says "start over" | Re-run from session type detection |
| User says "adjust" | Ask one follow-up question to refine role or goal; re-run quick start with updated answers |
| Power user pastes SQL or error | Skip survey; route to matching skill based on message content |

## References


> **Access:** `skill_resource_read(action="read", skill="get-started", path="references/FILENAME")` — do NOT call `list`.

- [Platform setup](./references/platform-setup.md) — Foundations check definitions, ownership, per-check failure messages and fix paths
- [Tera UI navigation](./references/tera-ui.md) — Page-by-page UI guide, exact routes, where to send users when checks fail
- [Skill routing](./references/skill-routing.md) — Role × goal → primary skills table and SME routing map
- [Quick start content](./references/quick-start.md) — Role × goal quick start paths and general skip path
