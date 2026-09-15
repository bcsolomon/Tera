---
name: REPLACE-domain-skill-index
description: 'Route to the correct [DOMAIN] skill. Use FIRST when working with [DOMAIN] to identify which specialized skill to load. Covers [list all sub-domains].'
metadata:
  author: REPLACE
  version: "1.0"
---

# REPLACE: Domain Skill Index

Use this skill FIRST to determine which specialized skill to load.

## Routing Table

| If the task involves... | Load this skill | Key topics |
|---|---|---|
| Creating/modifying X | `domain-x` | topic1, topic2 |
| Optimizing Y | `domain-y` | topic3, topic4 |
| Debugging Z | `domain-z` | topic5, topic6 |

## Multi-Skill Tasks

| Task | Skills to combine |
|---|---|
| Full deployment | `domain-x` + `domain-y` |
| Performance audit | `domain-y` + `domain-z` |

## All Skills

| Skill | Lines | References | Depth |
|---|---|---|---|
| `domain-x` | ~1200 | 4 files | Deep |
| `domain-y` | ~800 | 3 files | Moderate |
| `domain-z` | ~600 | 2 files | Focused |
