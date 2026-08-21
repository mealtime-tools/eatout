---
name: eatout
description: Search a reviewed, source-cited snapshot of vegetarian restaurant meals around Sydney CBD as ranked candidate records with per-serving macros and citations. Use for questions about what vegetarian meal to buy nearby, verified restaurant macros, or protein-per-calorie rankings.
---

# eatout

`eatout` is a data source: a read-only, reviewed snapshot of published
restaurant nutrition. Use the executable for all restaurant nutrition data. Do
not read the dataset files directly, scrape restaurant sites, or estimate a
value the tool did not give you. It never uses the network, never writes, and
never logs anything anywhere.

## Output contract

Every command takes `--json` and then emits exactly one JSON object on stdout:

```json
{"ok":true,"data":{...}}
```

A failure emits `{"ok":false,"error":{"message":"..."}}` on stdout (with
`--json`; stderr otherwise) and exits nonzero. Exit codes: `0` success, `1`
usage error or unreadable data, `3` assertion failure, `4` `--strict` warning. A
search that matches nothing is exit `0` with `count: 0` — not an error.

Without `--json` the output is human text. Never parse that.

## Commands

```sh
eatout metadata --json
eatout search --json --max-kcal 700 --min-protein 25 --limit 10
eatout search --json --query "tofu"
eatout guide
eatout skill install|uninstall|status
```

`eatout --data PATH <command>` (or `$EATOUT_DATA`) points at a different meal
document. `--data` belongs before the subcommand.

### metadata

`data`: `generated_at`, `restaurant_count`, `base_item_count`, `add_on_count`.

Report `generated_at` as the age of the snapshot. It is not the current date,
and it is the provenance stamp for every other command's results.

### search

`data`: `generated_at`, `count`, `candidates[]`, `unverifiable[]`. Each entry is
the shared candidate record, so it merges with any other candidate source:

```json
{"kind":"meal","id":"crust-pizza-peri-peri-not-chicken-high-protein-base-half",
 "name":"Crust Pizza - Peri Peri (not) Chicken - High Protein Base (Half)",
 "per_serving":{"kcal":625,"protein":45.8},"complete":false,
 "detail":{"restaurant":"Crust Pizza","item_name":"Peri Peri (not) Chicken - High Protein Base (Half)",
  "protein_per_100_kcal":7.3,"vegetarian":true,"vegan":false,
  "confidence":"exact","source_url":"https://www.crust.com.au/nutrition"}}
```

`kind` is always `meal`. `id` is a slug of restaurant and item: the same meal
has the same id on every machine and every run. `per_serving` is in kcal and
grams. Everything meal-specific is under `detail`.

Filters, all optional and all inclusive at the boundary:

| flag | meaning |
| --- | --- |
| `--max-kcal N` | keep `per_serving.kcal <= N` |
| `--min-protein N` | keep `per_serving.protein >= N` |
| `--query TEXT` | all words must occur in restaurant or item name; case and punctuation are ignored, so `grilld` matches `Grill'd` |
| `--limit N` | maximum candidates, default 25 |

Results are always vegetarian. Ranking is protein per 100 kcal descending, then
protein, then `name` — the shared ranking, so a merged list from several sources
is ordered consistently.

An item may be combined with one add-on the operator publishes figures for;
that option's `item_name` is `"Base + Add-on"` and its `confidence` is the
weaker of the two.

## Rules

- **A missing macro stays missing.** `per_serving` carries only what an operator
  published. The example above has no `fat` and no `carbs` because those figures
  do not exist — it is not a fat-free pizza. `complete` is `false` whenever a
  macro is absent. Never report an absent macro as 0, never derive one from the
  calories, and never fill a set in downstream.
- A candidate that lacks the macro you filtered on appears in `unverifiable`,
  not in `candidates`, and not nowhere. "No results" and "three I could not
  check" are different answers; say which you got.
- A combined meal reports a fat or carbohydrate total only when both parts
  published that macro; otherwise the key is absent.
- Quote `detail.source_url` and `detail.confidence` (`exact`,
  `high_confidence_estimate`, `low_confidence_estimate`) whenever you state a
  number.
- The dataset is a snapshot of published figures, not today's menu. Recommend
  confirming at the counter for anything that matters medically.
