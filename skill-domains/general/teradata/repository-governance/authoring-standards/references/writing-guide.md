# Writing Guide — Style and Content Patterns for Effective Skills

Patterns extracted from 15 production skills (22,000+ lines) and the agentskills.io specification.

## Tone and Style

- **Direct and imperative** — Write procedures as commands: "Create the table" not "You should create the table"
- **Agent-first** — You're writing for an AI agent, not a human reader. Prioritize machine-parseable structure over prose
- **Concrete over abstract** — Always include a code example alongside a concept
- **Complete over concise** — When in doubt, include the full syntax rather than a partial example. Agents can't infer what you omitted

## SKILL.md Header Pattern

The most effective pattern from production skills:

```markdown
---
name: domain-topic
description: 'Verb-phrase capabilities. Use when [triggers]. Covers [topics].'
metadata:
  author: org
  version: "1.0"
---

# Domain Topic

## When to Use

- Scenario 1 the user might describe
- Scenario 2 with specific keywords
- DO NOT use for [related but out-of-scope topic] — use `other-skill` instead

## Quick Reference

| Type/Category | Key Feature | Notes |
|---|---|---|
| Type A | ... | ... |
| Type B | ... | ... |

## Procedure: Common Task

1. Step one
2. Step two with inline example:
   ```sql
   SELECT * FROM table;
   ```
3. Step three referencing detail: See [detailed reference](./references/topic.md)
```

## Description Writing Formula

The description follows this pattern:

```
[Action verbs] [domain objects]. Use when [user task triggers]. Covers [specific subtopics].
```

**Components:**

1. **Action verbs** (2-4 verbs): Create, configure, optimize, debug, monitor, test, deploy, migrate
2. **Domain objects**: What the skill acts on (tables, queries, functions, APIs, tests)
3. **Use when triggers**: Specific tasks or questions a user would have
4. **Covers subtopics**: Key areas to help the agent assess relevance

**Length sweet spot:** 150-400 characters. Under 50 hurts discovery. Over 500 wastes discovery-stage tokens.

## "When to Use" Section Patterns

### Positive triggers (always include)

```markdown
## When to Use

- Creating [specific thing] from scratch
- Modifying existing [thing] to add [feature]
- Debugging [specific error pattern]
- Optimizing [specific metric]
- Migrating from [source] to [target]
```

### Negative triggers (include when confusion is likely)

```markdown
- DO NOT use for [thing that sounds similar but belongs elsewhere]
  — use `other-skill-name` instead
- This skill covers [X version/platform]; for [Y], see `y-skill`
```

### Cross-references (include for multi-skill domains)

```markdown
- For tasks combining [this domain] with [other domain],
  also load `other-skill-name`
```

## Table Patterns

Tables are highly effective for agents. Use them for:

### Type/category overview tables (in SKILL.md)

```markdown
| Type | Use Case | Key Constraint |
|---|---|---|
| Scalar UDF | Row-level transforms | Single value return |
| Table UDF | Row generation | Returns table |
| Aggregate UDF | Group operations | Two-phase required |
```

### Parameter/field reference tables (in references/)

```markdown
| Parameter | Type | Default | Description |
|---|---|---|---|
| max_rows | INTEGER | 1000 | Maximum rows returned |
| timeout | INTERVAL | '00:05:00' | Query timeout |
```

### Comparison tables (when alternatives exist)

```markdown
| Feature | Approach A | Approach B |
|---|---|---|
| Performance | Fast | Moderate |
| Complexity | High | Low |
| Use when | Need speed | Need simplicity |
```

### Error/troubleshooting tables

```markdown
| Error Code | Message | Cause | Resolution |
|---|---|---|---|
| 3706 | Syntax error | Missing keyword | Check SQL syntax |
| 3807 | Object not found | Wrong database | Qualify with DB name |
```

## Reference File Patterns

### Structure template

```markdown
# Topic — Complete Reference

> Source: Document Name, Version X.Y (citation)

## Overview

One paragraph explaining what this reference covers and when to consult it.

## Section 1: Core Concepts

### Subsection A

[Content with code examples]

### Subsection B

[Content with tables]

## Section 2: Advanced Topics

...

## Section N: Error Handling

| Error | Cause | Fix |
|---|---|---|
```

### Content extraction from source docs

When extracting from PDFs or documentation:

1. **Preserve technical precision** — Copy exact syntax, parameter names, error codes
2. **Add structure** — Source docs are often linear; reorganize by topic
3. **Create tables** — Convert paragraph-style lists into scannable tables
4. **Include complete examples** — Never truncate code examples from sources
5. **Cite the source** — Add `> Source:` blockquote at the top
6. **Fill gaps** — If the source doc has implicit knowledge (assumed context), make it explicit
7. **Cross-reference** — Link to other reference files in the same skill when topics overlap

### Sizing a reference file

```
< 100 lines  →  Too thin. Either merge with another file or expand coverage
150-300 lines →  Good for focused topics (one function, one feature)
300-500 lines →  Ideal for moderate topics (feature category, workflow)
500-650 lines →  Maximum. Check if it should split
> 650 lines   →  Must split. Find natural topic boundaries
```

## Code Example Patterns

### Inline examples (in SKILL.md)

Keep inline examples short (5-15 lines). Show the most common usage:

```markdown
Create a basic stored procedure:
​```sql
CREATE PROCEDURE get_employee(IN emp_id INTEGER)
BEGIN
    SELECT * FROM employees WHERE id = emp_id;
END;
​```
```

### Reference examples (in references/)

Make examples complete and runnable:

```markdown
​```sql
-- Full example: Create aggregate UDF with all phases
CREATE FUNCTION avg_salary(phase INTEGER, salary DECIMAL(10,2))
RETURNS DECIMAL(10,2)
LANGUAGE C
NO SQL
PARAMETER STYLE SQL
EXTERNAL NAME 'CS!avg_salary!avg_salary.c';

-- Install the C source
CALL SYSUIF.INSTALL_FILE('avg_salary', 'avg_salary.c', 'cz!/path/to/avg_salary.c');

-- Test
SELECT department, avg_salary(salary) FROM employees GROUP BY department;
​```
```

## Skill Index Pattern

For domains with multiple skills, create a routing index:

```markdown
---
name: domain-skill-index
description: 'Route to the correct [domain] skill. Use FIRST when working with [domain] to identify which specialized skill to load.'
---

# Domain Skill Index

## Routing Table

| If the task involves... | Load this skill |
|---|---|
| Creating/modifying X | `domain-x` |
| Optimizing Y | `domain-y` |
| Debugging Z | `domain-z` |

## Multi-Skill Tasks

| Task | Skills to combine |
|---|---|
| Full deployment | `domain-x` + `domain-y` |
| Performance audit | `domain-y` + `domain-z` |
```

## Common Writing Mistakes

| Mistake | Why it's bad | Fix |
|---|---|---|
| Prose paragraphs for syntax | Agent can't parse reliably | Use code blocks |
| "See the docs for details" | There are no external docs in context | Include the details inline or in a reference |
| Incomplete examples | Agent generates broken code | Always test or verify examples are complete |
| Inconsistent terminology | Agent gets confused | Pick one term and use it everywhere |
| Duplicating between SKILL.md and refs | Wastes context tokens, risks divergence | Overview in SKILL.md, detail in refs only |
| Burying routing info in references | Agent doesn't see it at Stage 2 | Put all routing in SKILL.md |
