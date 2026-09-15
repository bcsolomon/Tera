# Tera UI — User Flows & Navigation Reference

A user-centric guide to the Tera application. Use this when a foundations check fails, a user is lost, or setup guidance is needed — so responses include the exact location in the UI to go to.

---

## The Big Picture

Tera is an AI workspace where users have conversations with agents to get work done — analyzing data, building workflows, monitoring systems, and more. Everything revolves around a three-level hierarchy:

```
Workspace  →  Project  →  Session
(team)        (context)   (conversation)
```

- **Workspace** — A team or personal container. Users can belong to multiple workspaces. The active workspace is always shown in the top toolbar.
- **Project** — A scoped work area inside a workspace. Holds sessions, files, and resources.
- **Session** — A single AI conversation. This is where work happens.

The active workspace and project are remembered between visits. Switching workspaces resets the active project.

---

## Navigation Layout

### Top Toolbar
| Element | What it does |
|---|---|
| Teradata logo | Links to Home (`/`) |
| Workspace picker (dropdown) | Switch the active workspace |
| Theme toggle | Switch dark / light mode |
| Help button | Documentation / support |
| User avatar | Account dropdown (settings, logout) |

### Left Nav Rail
| Element | Route | Notes |
|---|---|---|
| New Session button | Starts a session | Top of rail |
| Project picker | — | Switch active project |
| Customize | `/customize` | Skills and connectors |
| Recent sessions | `/sessions/:id` | Pinned recent sessions |
| Usage | `/usage` | Token and cost tracking |
| Settings | `/settings` | User account and preferences |
| Admin *(admin only)* | `/admin` | System management |

The rail collapses to icons only or expands to icons + labels.

---

## Key Pages

### Home — `/`

The main starting point after login.

- Chat input bar to start a new session
- **JTBD suggestion chips**: Analyze · Monitor · Build · Optimize · Secure — clicking one pre-fills the input
- Grid of recent sessions (last 4)
- Database browser panel (slides in from right) — browse Teradata tables and attach to a message

> **For get-started:** This is where a new user lands. The Get Started project shows the foundations check and JTBD chips here when no sessions exist yet.

---

### Session — `/sessions/:sessionId`

The core experience. Full chat with the agent.

- Message thread with streaming AI responses
- **Tool timeline** (left) — each step the agent took
- **Activity panel** (right) — Artifacts, Tasks, Files, UI Apps tabs
- Attach files and database tables via the `+` button
- Use `/` to trigger a skill or slash command (e.g. `/get-started`)

---

### Customize — `/customize`

Manage the tools and extensions available in sessions. Redirects to `/customize/connectors` by default.

#### Connectors — `/customize/connectors`

- List of MCP servers (global and user-level)
- Per-connector: status badge (connected / error / unconfigured)
- Click a connector to configure: API keys, endpoint, auth
- **Test Connection** button — use this to diagnose a failing Teradata MCP Server check

> **For get-started:** If the Teradata MCP Server check fails, send the user here. Walk them through finding the Teradata connector and clicking Test Connection.

#### Skills — `/customize/skills`

- List of available skills (slash commands + prompt templates)
- Toggle skills on/off — changes take effect immediately
- Upload a skill YAML file
- Browse marketplace

> **For get-started:** If the Teradata Skills check fails, send the user here to enable skills.

---

### Settings — `/settings`

User account and personal preferences. Redirects to `/settings/for-you`.

| Sub-route | What it does | Relevant for get-started |
|---|---|---|
| `/settings/for-you` | Theme, language, notification defaults | — |
| `/settings/profile` | Name, email, avatar | — |
| `/settings/ai-providers` | View available LLM providers | **Check 1 — LLM Provider** |
| `/settings/api-keys` | Generate / revoke API keys | — |
| `/settings/active-logins` | See active sessions, log out others | — |
| `/settings/mcp-server` | User-level MCP server config | — |
| `/settings/tools` | Web search, browse, HTTP tool settings | — |
| `/settings/external-integrations` | Third-party service connections | — |
| `/settings/workspaces` | Workspace memberships, pending invites | — |

> **For get-started — LLM Provider check failure:** Send the user to `/settings/ai-providers` to see what providers are available. If the list is empty, they need to contact their admin — end users cannot add providers themselves.

---

### Usage — `/usage`

Token and cost tracking.

- Current month vs. previous month comparison
- Daily usage chart (input / output / cache tokens)
- Total cost and remaining quota

---

### Admin — `/admin` *(admin users only)*

Visible only to users with `isAdmin = true`.

| Sub-route | What it does |
|---|---|
| `/admin/users` | User list, quota override, suspension |
| `/admin/mcp-servers` | Global MCP server CRUD |
| `/admin/model-catalog` | LLM model inventory |
| `/admin/providers` | LLM provider configuration |
| `/admin/skills` | System-wide skill management |
| `/admin/developer` | Dev tools and diagnostics |

> **For get-started:** Do not direct end users to admin routes. If a check failure requires admin action (LLM Provider, Tera Agent), tell the user to contact their admin.

---

## Foundations Check — Where to Send Users

| Check | Fails because | Send user to | Message |
|---|---|---|---|
| LLM Provider | No provider configured or accessible | `/settings/ai-providers` | "Go to Settings → AI Providers to see what's available. If the list is empty, contact your admin." |
| Teradata MCP Server | Server unreachable or auth failed | `/customize/connectors` | "Go to Customize → Connectors, find the Teradata connector, and click Test Connection." |
| Tera Agent | Agent not available | `/settings` | "Go to Settings and check the Agents section. If it's missing, contact your admin." |
| Teradata Skills | No skills enabled | `/customize/skills` | "Go to Customize → Skills and enable Teradata skills." |

---

## Key User Journeys

### New user — first session
1. Log in at `/login`
2. If no workspace: workspace creation modal appears
3. If no project: project creation modal appears
4. Land on Home (`/`) → Get Started project shown
5. Foundations check runs — green or amber
6. JTBD chips shown — click one to start

### Setting up a connector (e.g. Teradata)
1. Left nav → **Customize** → **Connectors** (`/customize/connectors`)
2. Find the connector in the list
3. Click to open detail panel
4. Enter required config (credentials, endpoint)
5. Click **Test Connection**
6. Save → connector active in sessions

### Enabling a skill
1. Left nav → **Customize** → **Skills** (`/customize/skills`)
2. Find the skill (or upload a YAML file)
3. Toggle on → available immediately via `/` in any session

### Checking LLM provider access
1. Left nav → **Settings** (`/settings`)
2. Select **AI Providers** tab (`/settings/ai-providers`)
3. If providers listed: set one as default if needed
4. If empty: contact admin — end users cannot add providers

---

## Modals the User May Encounter During Get-Started

| Modal | Triggered from | What it does |
|---|---|---|
| Create Project | Projects page | Name + workspace picker |
| Create Workspace | Workspaces page | Name + description |
| Skill Upload | Customize / Skills | Multi-step YAML skill upload |

---

## Persistence — What's Remembered

| What | Stored in | Notes |
|---|---|---|
| Active workspace | `localStorage` | Persists across sessions |
| Active project | `localStorage` | Cleared when workspace changes |
| Theme preference | `localStorage` | Default is dark |
| Auth token | `localStorage` | Cleared on logout or expiry |
