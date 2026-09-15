# cdc-hai-analyst

Bundle-style skill following `HAI/SKILL_FORMAT_GUIDE.md`. Repo destination:

```
skill-domains/general/teradata/cdc-hai-analyst/
├── SKILL.md
├── references/
│   ├── data_dictionary.md
│   ├── query_recipes.md
│   ├── interpretation_rules.md
│   ├── semantic_search.md
│   └── data_quirks.md
└── assets/templates/
    ├── structured_query.sql
    └── semantic_search.sql
```

Copy the directory into the repo at that path, then:

```bash
git add skill-domains/general/teradata/cdc-hai-analyst
git commit -m "feat(skills): add cdc-hai-analyst"
git push origin main
```

Note on directory naming: the guide's structure diagram says `reference/` (singular) but its own real-repo example
(`td-vector-collections`) uses `references/`. This bundle uses `references/` to match the real repo. Rename if the
loader expects the singular form.

Companion skill: `unstructured-teradata-hybrid-rag` (in `HAI/build/skill/`) covers *building* this dataset;
this one covers *querying* it.

Every SQL snippet in SKILL.md, the recipes and the templates was executed against the live `CDC_HAI` database on
2026-09-15 and its expected result recorded in the text.
