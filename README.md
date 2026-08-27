# Eatout

Search the hand-curated, source-cited vegetarian restaurant nutrition dataset
around Sydney CBD.

```console
eatout search --query tofu
eatout search --max-kcal 700 --min-protein 25 --limit 5
eatout search --json --query "grilld"
```

The reviewed source files are in `data/sources/`; `data/research/` records the
restaurants that were investigated. Nutrition fields are flat; missing
values are JSON `null`, never zero. `scripts/regenerate.py` rebuilds `data/meals.json` from the
reviewed sources. The CLI itself is read-only and does not fetch or estimate.
Each candidate's nutrients describe that menu item. Restaurant weights are
left absent when the source did not publish them. A search returning one
candidate is a flat record in the shared
[item format](https://github.com/mealtime-tools/nutrients/blob/main/FORMAT.md),
so it can be piped with `--input -` into Recipes, or into whatever tool records
what you ate.
