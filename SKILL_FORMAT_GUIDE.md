# Skill Format & Structure Guide

This document describes how to bundle existing work into a skill for the `bcsolomon/Tera` repository.

## Directory Structure

All skills are organized under `skill-domains/` in the repo root:

```
skill-domains/
└── <domain>/                    ← one of the allowed domains
    ├── my-skill.yaml            ← Shape 1: framework YAML file
    └── my-bundle/               ← Shape 2: bundle directory
        ├── SKILL.md             ← required entry point (frontmatter + body)
        ├── reference/           ← optional reference documents
        │   ├── notes.md
        │   ├── params.md
        │   └── edge_cases.md
        ├── assets/              ← optional assets directory
        │   └── templates/
        └── scripts/             ← optional scripts directory
            └── run.py
```

## Two Skill Shapes

### Shape 1: YAML File
A single YAML file defining the skill:
```
skill-domains/general/my-skill.yaml
```

### Shape 2: Bundle Directory
A directory with `SKILL.md` as the entry point:
```
skill-domains/general/my-skill-bundle/
├── SKILL.md          (required)
├── reference/        (optional)
├── assets/           (optional)
└── scripts/          (optional)
```

## SKILL.md Format

The `SKILL.md` file is required for bundle-style skills. It should have:

### Frontmatter (YAML)
```yaml
---
name: Skill Display Name
description: One-line description of what the skill does
tags:
  - tag1
  - tag2
created_by: Author Name
last_updated: 2026-09-15
---
```

### Body (Markdown)
The body contains the skill documentation including:
- Overview and purpose
- Key concepts
- Usage instructions
- Examples
- Links to reference docs

## Reference Directory

The `reference/` subdirectory contains supporting documentation files. Common examples:

- `permissions.md` - Required permissions or access
- `parameters.md` - Parameter definitions
- `edge_cases.md` - Known limitations and edge cases
- `search_params.md` - Search-specific parameters
- `create_collection.md` - Creation instructions
- `ingest_params.md` - Data ingestion parameters
- `model_selection.md` - Model or configuration selection
- `update_params.md` - Update operations

Each reference file is a standalone markdown document.

## Assets & Scripts Directories

### assets/
Optional directory for templates, examples, or other static assets:
```
assets/
└── templates/
    └── example-template.sql
```

### scripts/
Optional directory for executable scripts or code examples:
```
scripts/
├── run.py
└── helper.py
```

## Real Examples in the Repo

### Simple Single Skill
```
skill-domains/general/my-name-is-brian/
└── SKILL.md
```

### Complex Multi-Category Skill
```
skill-domains/general/teradata/teradata-foundations/
├── td-data-profile/
│   └── SKILL.md
├── database-space-management/
│   └── SKILL.md
├── td-schema-discovery/
│   └── SKILL.md
└── ... (more skills)
```

### Skill with Rich References
```
skill-domains/general/teradata/td-vector-collections/
├── SKILL.md
├── references/
│   ├── update_params.md
│   ├── permissions.md
│   ├── search_params.md
│   ├── edge_cases.md
│   ├── create_collection.md
│   ├── ingest_params.md
│   └── model_selection.md
```

## Bundling Previous Work into a Skill

To convert existing documentation/code into a skill:

1. **Create the directory structure:**
   ```
   skill-domains/general/<domain>/<skill-name>/
   ```

2. **Create SKILL.md:**
   - Add frontmatter with name, description, tags, created_by, last_updated
   - Convert main documentation to the body

3. **Organize supporting docs:**
   - Move reference/supplementary docs to `reference/` subdirectory
   - Move code examples to `scripts/` subdirectory
   - Move assets (templates, etc.) to `assets/` subdirectory

4. **Commit and push:**
   ```bash
   git add skill-domains/
   git commit -m "feat(skills): add <skill-name>"
   git push origin main
   ```

## Domain Categories

The repo currently uses these domain categories under `general/`:
- `my-name-is-brian` - Example skills
- `prior-auth-review` - Prior auth review skills
- `teradata/` - Teradata-specific skills with subcategories:
  - `td-vector-collections` - Vector/embedding operations
  - `teradata-foundations` - Core Teradata concepts
  - `advanced-data-and-analytics-features` - Advanced analytics
  - `agent-enablement-and-evaluation` - Agent-related skills

## Best Practices

1. **Use clear, descriptive names** for skill directories (kebab-case)
2. **Keep SKILL.md focused** - it's the entry point, reference docs go in `reference/`
3. **Include practical examples** in the skill body or reference docs
4. **Tag appropriately** - helps with discovery and organization
5. **Update the `last_updated` field** in frontmatter when making changes
6. **Reference external docs** - link to Teradata docs where relevant
