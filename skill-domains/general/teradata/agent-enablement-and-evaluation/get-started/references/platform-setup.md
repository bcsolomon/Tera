# Platform Setup — Foundations Check and UI Navigation

Use this file to interpret platform-provided foundations check results and guide users to the right place in the Tera UI when a check fails. The checks themselves are executed by up-tera — the agent only consumes the results.

---

## Foundations Check

If the platform passes check results to the agent, use this table to interpret each one and respond accordingly. Each check has a different owner and a different failure response.

| Check | What it confirms | Who owns it | If it fails |
|-------|-----------------|-------------|-------------|
| **LLM Provider** | At least one provider is configured and ready — no end-user setup required | Admin-provisioned | Tell user to go to `/settings/ai-providers` to see what's available. If none appear, direct them to contact their admin. |
| **Teradata MCP Server** | The Teradata MCP server is connected and reachable | Platform (always present) | Guide user to `/customize/connectors` to check connection status and test. |
| **Tera Agent** | The Tera Agent is available | Platform | Direct user to `/settings` → Agents. |
| **Teradata Skills** | At least one Teradata skill is enabled | User-configurable | Direct user to `/customize/skills` to enable skills. |

### Status display rules

- **All pass:** Show collapsed "Tera Agent ready ✓" panel. Proceed to survey or routing silently.
- **Any fail:** Auto-expand the panel, show amber warning per failing check, include the exact UI path and action from the sections below.
- **API failure / timeout:** Show all rows as "Unable to verify" — do not show red warnings. Offer a single retry button. Do not block the user.
- **Partial failure:** Show loaded checks with real status; show timed-out checks as "Unable to verify" with individual retry links.

### Reporting format

```
## Tera Foundations Check

✓ LLM Provider — ready
✓ Teradata MCP Server — connected
✓ Tera Agent — available
⚠ Teradata Skills — no skills enabled

→ Go to Customize → Skills to enable Teradata skills.
  You can continue without this, but domain-specific capabilities won't be available.
```

---

## Check 1: LLM Provider

**End-user experience:** Providers are configured by your admin — no setup required from you. This check just confirms one is ready.

**If the check fails — what to tell the user:**

> "No LLM provider is available for your account. Go to **Settings → AI Providers** (`/settings/ai-providers`) to see what's configured. If the list is empty, contact your admin to request access."

**UI path for the user:**
- Open the left nav → **Settings** → **AI Providers** (`/settings/ai-providers`)
- If providers are listed: one may need to be set as default — click the provider and select "Set as default"
- If no providers are listed: admin action required — the user cannot resolve this themselves

**Do not instruct end users to add or configure a provider** — that is an admin action at `/admin/providers`.

---

## Check 2: Teradata MCP Server

**End-user experience:** The Teradata MCP server is always present in the Tera environment. This check confirms it is currently connected and reachable.

**If the check fails — what to tell the user:**

> "The Teradata connection isn't responding. Go to **Customize → Connectors** (`/customize/connectors`) to check the status and test the connection."

**UI path for the user:**
1. Open the left nav → **Customize** → **Connectors**
2. Find the Teradata connector — check the status dot:
   - 🟢 Green = connected
   - 🟡 Amber = reachable but errors
   - 🔴 Red = unreachable or auth failed
3. Click the connector → click **Test Connection**
4. If the test fails, verify the host, username, and password are correct
5. Save and re-test

**Common issues to surface to the user:**
- Connection timeout: the Teradata host may be temporarily unavailable — try again in a few minutes
- Auth failure: credentials may have changed — re-enter and test
- If repeated failures: suggest contacting their admin

---

## Check 3: Tera Agent

**End-user experience:** The Tera Agent is platform-managed. End users cannot configure it.

**If the check fails — what to tell the user:**

> "The Tera Agent isn't showing as available. Go to **Settings → Agents** (`/settings`) to check its status. If it's missing, contact your admin."

---

## Check 4: Teradata Skills

**End-user experience:** Skills are user-configurable. End users can enable them directly.

**If the check fails — what to tell the user:**

> "No Teradata skills are enabled. Go to **Customize → Skills** (`/customize/skills`) to enable them — they add domain-specific capabilities to Tera."

**UI path for the user:**
1. Open the left nav → **Customize** → **Skills**
2. Browse the skills list — find Teradata skills
3. Toggle skills on — changes take effect immediately
4. Return to get-started and re-run the check

---

## UI Navigation Map

Key routes referenced when guiding users after a failed check:

| Destination | Route | When to use |
|---|---|---|
| Check LLM provider availability | `/settings/ai-providers` tab | Check 1 fails |
| Check / test Teradata connection | `/customize/connectors` | Check 2 fails |
| Check Tera Agent status | `/settings` → Agents tab | Check 3 fails |
| Enable Teradata skills | `/customize/skills` | Check 4 fails |
| View available tools | `/settings` → Tools tab | General reference |
| Start a new chat | `/` (home) | After onboarding completes |
| Create a new session | `/projects` → click + | After onboarding completes |
| Switch workspace | `/workspaces` | Top-left nav |
| View usage / quotas | `/usage` | Resource reference |

---

## Foundations Check Analytics Events

| Event | When | Properties |
|-------|------|-----------|
| `onboarding_foundations_expanded` | User manually expands the panel | — |
| `onboarding_foundations_fix_clicked` | User clicks a fix/navigate link | `check_name` |
| `onboarding_foundations_retry` | User clicks retry after API failure | — |
| `onboarding_foundations_all_pass` | All four checks pass | — |
