---
name: eatout
description: Search the reviewed, source-cited vegetarian restaurant nutrition dataset around Sydney CBD.
---

# Eatout

Use the CLI for restaurant product acquisition. Do not scrape or estimate data
that is absent from this reviewed snapshot.

```console
eatout search --json --query TEXT --limit 10
eatout search --json --max-kcal 700 --min-protein 25 --limit 10
```

Each candidate is a flat whole-item record with restaurant details, confidence,
and its source URL. Missing nutrients are `null`; explicit zero remains zero.
One-candidate output can be piped to Recipes or Nutrilog with `--input -`.
