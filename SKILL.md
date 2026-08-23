---
name: eatout
description: Search the reviewed, source-cited vegetarian restaurant nutrition dataset around Sydney CBD.
---

# Eatout

```console
eatout search --json [--query TEXT] [--max-kcal N] [--min-protein N]
```

This is a reviewed, read-only snapshot; do not scrape or estimate missing data.
Each candidate is a flat whole-item record with its source. Missing nutrients
are `null`; explicit zero remains zero. One-candidate output can be piped to
Recipes or Nutrilog.
