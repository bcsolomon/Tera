---
name: agent-skill-builder
description: 'Build, review, and improve Agent Skills (SKILL.md format). Use when creating new skills from scratch, enriching thin skills with source material, auditing existing skills for completeness, or refactoring oversized skills. Covers the full lifecycle: planning skill scope, writing YAML frontmatter, structuring SKILL.md body, creating reference files, adding templates, building skill indexes, and validating against the agentskills.io specification. Also use when extracting knowledge from PDFs or documentation into skill reference files.'
metadata:
  author: skill-builder
  version: "1.0"
---

# Agent Skill Builder

## When to Use

- Creating a new skill from scratch for any domain
- Enriching a thin/stub skill with content from source documents (PDFs, docs, web pages)
- Auditing an existing skill for completeness and well-formedness
- Refactoring an oversized SKILL.md into proper progressive-disclosure structure
- Building a skill index that routes to multiple related skills
- Reviewing skills before sharing or publishing
- Extracting structured reference material from unstructured sources

## Procedure: Creating a New Skill

### Step 1: Define Scope

Before writing anything, determine:

1. **Domain boundary** — What specific tasks does this skill cover? What does it NOT cover?
2. **Target audience** — Who will invoke this skill (developer, DBA, analyst)?
3. **Activation triggers** — What keywords, questions, or task descriptions should cause an agent to load this skill?
4. **Depth level** — Is this a shallow routing skill or a deep technical reference?

Ask these questions if scope is unclear. A well-scoped skill covers one coherent domain. If you find yourself covering two unrelated areas, split into two skills.

### Step 2: Create Directory Structure

```
skill-name/
├── SKILL.md              # Required: metadata + instructions (target 200-300 lines)
├── references/            # Detailed reference material (150-650 lines each)
│   ├── topic-a.md
│   ├── topic-b.md
│   └── topic-c.md
├── assets/
│   └── templates/         # Reusable code/SQL/config templates
│       ├── template-a.md
│       └── template-b.py
└── scripts/               # Executable scripts (if needed)
```

**Critical rule:** The directory name MUST match the `name` field in the YAML frontmatter exactly.

### Step 3: Write YAML Frontmatter

```yaml
---
name: skill-name
description: 'Verb-driven description of capabilities. Use when [specific triggers]. Covers [key topics].'
metadata:
  author: org-or-person
  version: "1.0"
---
```

**Frontmatter rules:**
- `name`: 1-64 chars, lowercase alphanumeric + hyphens only, no consecutive hyphens, no leading/trailing hyphens
- `description`: 1-1024 chars, must describe WHAT the skill does AND WHEN to use it
- Always single-quote the description value to avoid YAML parsing issues with colons
- **The description is the discovery surface** — if trigger keywords aren't in the description, the agent won't find the skill

See [frontmatter reference](./references/frontmatter-reference.md) for all fields and validation rules.

### Step 4: Write SKILL.md Body

Structure the body with these sections (in order):

```markdown
# Skill Title

## When to Use
- Bullet list of activation scenarios
- Include specific task descriptions an agent would match

## Core Concepts (or Quick Reference)
- Tables, key terminology, decision trees
- Just enough to orient the agent without loading references

## Procedure: [Task Name]
1. Step-by-step instructions
2. Include code examples inline for common operations
3. Reference deeper content: See [topic reference](./references/topic.md)

## Procedure: [Another Task]
...

## Common Errors / Troubleshooting
| Error | Cause | Fix |
|---|---|---|

## References

> **Access:** `skill_resource_read(action="read", skill="agent-skill-builder", path="references/FILENAME")` — do NOT call `list`.

- [Topic A](./references/topic-a.md) — Brief description of what's in there
- [Topic B](./references/topic-b.md) — Brief description

## Templates
- [Template A](./assets/templates/template-a.md)
```

**Key principles:**
- Keep SKILL.md under **500 lines** (target 200-300 for most skills)
- Put detailed reference material in `references/` files
- Every reference file MUST be linked from SKILL.md or it won't be discovered
- Use relative paths with `./` prefix: `[link text](./references/file.md)`
- Include inline code examples for the most common operations
- Save exhaustive syntax, type tables, and edge cases for reference files

### Step 5: Write Reference Files

Each reference file should be **150-650 lines** and cover one focused topic:

```markdown
# Topic Title — Complete Reference

> Source: [citation if extracted from documentation]

## Section 1
### Subsection
[Detailed content, tables, examples]

## Section 2
...
```

**Reference file best practices:**
- Start with a clear title indicating scope
- Include source citations when extracted from documentation
- Use tables for mappings, type conversions, parameter lists
- Include complete code examples (not snippets)
- Cover edge cases and error conditions
- Keep each file focused — split rather than combine unrelated topics

### Step 6: Add Templates (Optional)

Templates go in `assets/templates/` and should be:
- Self-contained and ready to use with minimal modification
- Commented to explain what to customize
- Referenced from SKILL.md

### Step 7: Validate

Run through the [validation checklist](./references/validation-checklist.md) before considering the skill complete.

## Procedure: Enriching a Thin Skill from Sources

When a skill exists but lacks depth (< 100 lines in references), enrich it:

1. **Inventory current coverage** — Read all existing files, note line counts
2. **Identify source material** — PDFs, documentation, web pages containing authoritative content
3. **Extract text from PDFs** — Use pymupdf or similar to extract to .txt files
4. **Scan for gaps** — Compare source content against existing skill coverage
5. **Fill gaps systematically** — Update reference files section by section
6. **Preserve existing structure** — Augment, don't rewrite what's already correct
7. **Update SKILL.md references section** — Ensure new/expanded refs are described
8. **Verify line counts** — Confirm reference files are 150-650 lines each

**Extraction pattern for PDFs:**
```python
import pymupdf
doc = pymupdf.open("source.pdf")
with open("source-extracted.txt", "w") as fh:
    for i in range(doc.page_count):
        page = doc[i]
        fh.write(f"\n{'='*80}\n=== PAGE {i+1} ===\n{'='*80}\n")
        fh.write(page.get_text())
doc.close()
```

## Procedure: Auditing an Existing Skill

Use the [validation checklist](./references/validation-checklist.md) to audit. Key checks:

1. **Frontmatter valid?** — name matches folder, description is keyword-rich
2. **SKILL.md under 500 lines?** — Refactor to references if over
3. **References linked?** — Every file in `references/` must be linked from SKILL.md
4. **References sized correctly?** — Each 150-650 lines
5. **Progressive disclosure working?** — SKILL.md gives overview, refs give depth
6. **Inline examples present?** — Most common operations should have code in SKILL.md
7. **When to Use section present?** — Clear activation triggers listed
8. **Error/troubleshooting section?** — Common problems and solutions

## Procedure: Building a Skill Index

When you have multiple related skills, create a routing/index skill:

1. Set description to emphasize "Use FIRST to determine which skill to load"
2. Create a **routing table**: "If the task involves X → load `skill-y`"
3. List **all skills** with key topics and depth indicators
4. Include **multi-skill tasks** showing which skills to combine
5. Keep the index under 100 lines — it's a router, not content

See [skill-index-template](./assets/templates/skill-index-template.md) for the pattern.

## Progressive Disclosure Model

Skills load in three stages. Design for this:

```
Stage 1: Discovery (~100 tokens)
  → Agent reads `name` + `description` from frontmatter
  → Must contain enough keywords to match user intent

Stage 2: Instructions (< 5000 tokens recommended)
  → Full SKILL.md body loaded into context
  → Should orient the agent and provide common operations inline
  → Must reference deeper content via links

Stage 3: Resources (as needed)
  → Reference files, scripts, templates loaded only when referenced
  → Each file should be independently useful
```

**Design implication:** Never bury critical routing information in reference files. The agent won't see it until Stage 3. Put task identification and procedure selection in SKILL.md.

## Quality Targets

| Metric | Target | Warning |
|---|---|---|
| SKILL.md lines | 200-300 | > 500 needs refactoring |
| Reference file lines | 150-650 | > 650 should split |
| Reference files per skill | 2-8 | > 10 may indicate scope creep |
| Description length | 100-500 chars | < 50 hurts discovery |
| Total skill lines | 700-3000 | < 500 likely too thin |

## Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| Vague description | "Helps with databases" | Use verb-driven: "Create, modify, and optimize X. Use when Y." |
| Monolithic SKILL.md | 800+ lines in one file | Split detailed content into references/ |
| Orphaned references | Files in references/ not linked from SKILL.md | Add links in References section |
| Name mismatch | Folder `my-skill/` but `name: my_skill` | Must match exactly (lowercase, hyphens) |
| Missing "When to Use" | Agent can't determine activation | Add bullet list of specific scenarios |
| No inline examples | Agent must load references for basic tasks | Put top 3-5 operations inline |
| Kitchen-sink scope | One skill covers everything | Split into focused skills + index |
| Deeply nested refs | References that reference other references | Keep one level deep from SKILL.md |

## References

- [Frontmatter Reference](./references/frontmatter-reference.md) — Complete YAML field spec, validation rules, VS Code extensions
- [Validation Checklist](./references/validation-checklist.md) — Step-by-step audit checklist for skill quality
- [Writing Guide](./references/writing-guide.md) — Style, tone, and content patterns for effective skills

## Templates

- [SKILL.md Template](./assets/templates/skill-template.md)
- [Reference File Template](./assets/templates/reference-template.md)
- [Skill Index Template](./assets/templates/skill-index-template.md)
