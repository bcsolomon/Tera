# Validation Checklist — Agent Skill Quality Audit

Use this checklist to audit a skill before publishing or sharing. Each item is pass/fail. Fix all failures before considering the skill complete.

## Frontmatter Validation

- [ ] `name` field present and 1-64 chars
- [ ] `name` uses only lowercase a-z, 0-9, hyphens
- [ ] `name` does not start or end with hyphen
- [ ] `name` has no consecutive hyphens
- [ ] `name` matches parent directory name exactly
- [ ] `description` field present and 1-1024 chars
- [ ] `description` includes action verbs (create, build, configure, debug, etc.)
- [ ] `description` includes "Use when" trigger phrases
- [ ] `description` includes domain-specific keywords
- [ ] `description` value is quoted (single or double quotes)
- [ ] YAML uses spaces, not tabs
- [ ] Frontmatter is between `---` delimiters

## SKILL.md Structure

- [ ] Starts with `# Title` heading after frontmatter
- [ ] Has "When to Use" section with bullet list
- [ ] Has at least one "Procedure" section with numbered steps
- [ ] Has "References" section linking to all reference files
- [ ] Total lines: 200-500 (target 200-300)
- [ ] Inline code examples for the top 3-5 most common operations
- [ ] No deeply nested content that belongs in references

## Reference Files

- [ ] Every file in `references/` is linked from SKILL.md
- [ ] Each reference file is 150-650 lines
- [ ] Each reference file covers one focused topic
- [ ] Reference files have clear `# Title` headings
- [ ] Source citations included where content was extracted from docs
- [ ] Code examples are complete (not snippets that won't run)
- [ ] Tables used for mappings, parameters, type conversions
- [ ] Edge cases and error conditions covered

## Templates (if present)

- [ ] Templates are in `assets/templates/`
- [ ] Templates are linked from SKILL.md
- [ ] Templates are self-contained and ready to use
- [ ] Templates have comments explaining customization points

## Progressive Disclosure

- [ ] Discovery works: description alone conveys what the skill does
- [ ] SKILL.md alone enables an agent to handle common tasks
- [ ] Reference files provide depth for complex/edge-case tasks
- [ ] Critical routing logic is in SKILL.md, not buried in references
- [ ] File references use relative paths with `./` prefix

## Content Quality

- [ ] No duplicate content between SKILL.md and reference files
- [ ] Consistent terminology throughout
- [ ] Error messages/codes include resolution steps
- [ ] Comparison tables used where multiple approaches exist
- [ ] Security implications noted where applicable

## Sizing Guidelines

| Component | Minimum | Target | Maximum | Action if exceeded |
|---|---|---|---|---|
| SKILL.md | 100 | 200-300 | 500 | Move content to references |
| Reference file | 100 | 300-500 | 650 | Split into focused files |
| Number of refs | 1 | 3-6 | 10 | Check for scope creep |
| Total skill lines | 500 | 1000-2500 | 3500 | Split into multiple skills + index |
| Description chars | 50 | 150-400 | 1024 | Trim verbose phrasing |

## Common Failures and Fixes

| Failure | Symptom | Fix |
|---|---|---|
| Agent doesn't find skill | User asks relevant question but skill doesn't activate | Add missing keywords to `description` |
| Agent loads skill for wrong tasks | Skill activates when irrelevant | Narrow description, add "Do NOT use for" in When to Use |
| Agent can't complete task | Loads SKILL.md but gets stuck | Add inline examples or improve procedure steps |
| Reference not loaded | Agent doesn't access detail it needs | Add explicit link in SKILL.md with descriptive text |
| YAML silently fails | Skill never appears or loads | Check for unescaped colons, tabs, name mismatch |
| Context overflow | Skill + references too large | Reduce SKILL.md to overview, move detail to smaller references |

## Quick Audit Script

Count lines for a skill to verify sizing:

```bash
# From the skill directory
echo "=== SKILL.md ==="
wc -l SKILL.md

echo "=== References ==="
wc -l references/*.md 2>/dev/null || echo "No references"

echo "=== Total ==="
find . -name "*.md" | xargs wc -l | tail -1
```
