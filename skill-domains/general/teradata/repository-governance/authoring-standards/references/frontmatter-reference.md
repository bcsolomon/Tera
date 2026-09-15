# Frontmatter Reference — Complete Specification

> Source: agentskills.io specification v1.0 + VS Code Copilot customization docs

## Required Fields

### `name`

The unique identifier for the skill.

**Rules:**
- 1-64 characters
- Lowercase letters (a-z), numbers (0-9), and hyphens (-) only
- No uppercase, underscores, spaces, or special characters
- Cannot start or end with a hyphen
- No consecutive hyphens (`--`)
- MUST match the parent directory name exactly
- Regex: `^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$`

**Examples:**
```yaml
name: webapp-testing          # Valid
name: my-skill-v2             # Valid
name: a                       # Valid (single char)
name: My-Skill                # INVALID: uppercase
name: my_skill                # INVALID: underscore
name: -my-skill               # INVALID: leading hyphen
name: my--skill               # INVALID: consecutive hyphens
```

**Common failure:** The name field must match the folder. If the folder is `webapp-testing/`, the name must be `webapp-testing`. A mismatch causes silent failures — no error message, the skill simply won't load.

### `description`

How the agent discovers and decides to activate the skill.

**Rules:**
- 1-1024 characters
- Must describe WHAT the skill does AND WHEN to use it
- Use the "Use when..." pattern for activation triggers
- Include domain-specific keywords that users would mention
- Always single-quote or double-quote in YAML to avoid parsing issues with special characters

**Pattern:**
```
[Verb phrase describing capabilities]. Use when [trigger scenarios]. Covers [key topics].
```

**Good examples:**
```yaml
description: 'Create and optimize Teradata SQL queries. Use when writing SELECT, INSERT, UPDATE, DELETE statements, or optimizing query performance. Covers joins, subqueries, set operations, and explain plans.'

description: 'Build, review, and improve Agent Skills (SKILL.md format). Use when creating new skills, auditing existing ones, or extracting knowledge into reference files.'
```

**Bad examples:**
```yaml
description: A helpful database skill     # Too vague, no triggers
description: Teradata stuff               # No action verbs, no "Use when"
description: Use this skill for things     # No domain keywords
```

**Anti-pattern:** Treating the description as a human-readable summary. It's a **machine-readable activation surface**. Every keyword that might appear in a user's question should be in the description.

## Optional Fields (Standard)

### `license`

```yaml
license: MIT
```

SPDX license identifier. Informational only; does not affect behavior.

### `compatibility`

```yaml
compatibility:
  - github-copilot
  - claude
```

List of compatible platforms. Informational only.

### `metadata`

```yaml
metadata:
  author: team-name
  version: "1.0"
  domain: database-administration
```

Arbitrary key-value pairs. Useful for organization and filtering. Values must be strings (quote numbers).

## VS Code Extension Fields

These fields are VS Code-specific and may not be supported by other platforms.

### `argument-hint`

```yaml
argument-hint: 'Describe the skill you want to create'
```

Hint text shown when the skill is invoked via slash command (`/skill-name`). Helps users understand what input to provide.

### `user-invocable`

```yaml
user-invocable: true    # Default
user-invocable: false   # Hide from slash commands
```

Controls whether the skill appears as a `/` slash command in chat. When `false`, the skill can still be auto-loaded by the model based on the description, but users can't invoke it directly.

### `disable-model-invocation`

```yaml
disable-model-invocation: false   # Default
disable-model-invocation: true    # Only manual invocation
```

Prevents the model from auto-loading this skill. When `true`, the skill only activates via explicit `/skill-name` invocation. Useful for skills that should only run when deliberately requested.

### Visibility Matrix

| `user-invocable` | `disable-model-invocation` | Slash command | Auto-loaded |
|---|---|---|---|
| true (default) | false (default) | Yes | Yes |
| false | false | No | Yes |
| true | true | Yes | No |
| false | true | No | No |

### `context` (Experimental)

```yaml
context: inline   # Default: skill runs in current conversation
context: fork     # Experimental: skill runs in isolated subcontext
```

When set to `fork`, the skill executes in a forked context, similar to a subagent. The skill's output is returned as a single message to the main conversation. Useful for complex skills that generate lots of intermediate context.

**Warning:** This is an experimental feature and behavior may change.

## YAML Syntax Pitfalls

### Unescaped colons

```yaml
# WRONG — YAML interprets "Use when" as a key
description: Use when: creating skills

# CORRECT — quote the entire value
description: 'Use when: creating skills'
description: "Use when: creating skills"
```

### Tabs vs spaces

YAML requires spaces for indentation, never tabs. Tabs cause silent parsing failures.

### Multi-line strings

```yaml
# Block scalar — preserves newlines
description: |
  First line of description.
  Second line continues.

# Flow scalar — folds newlines to spaces  
description: >
  This is all one line
  when parsed by YAML.
```

For the description field, prefer single-line quoted strings. Multi-line descriptions may not parse correctly on all platforms.

### Boolean gotchas

```yaml
# These are all parsed as boolean true:
user-invocable: yes
user-invocable: Yes  
user-invocable: true
user-invocable: True

# Use lowercase true/false for clarity
user-invocable: true
user-invocable: false
```

## Complete Frontmatter Example

```yaml
---
name: webapp-testing
description: 'Test web applications with Playwright. Use when verifying frontend behavior, debugging UI issues, or capturing screenshots. Covers page navigation, element interaction, assertions, and visual regression.'
argument-hint: 'Describe the test scenario or UI behavior to verify'
metadata:
  author: frontend-team
  version: "2.1"
  domain: testing
---
```
