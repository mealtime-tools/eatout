# eatout

Cited vegetarian restaurant nutrition around Sydney CBD, emitted as the shared
candidate record: filter by per-serving macros, ranked by protein per 100 kcal.
A data source, nothing more — it does not log, estimate, or reach the network.

```sh
uv run eatout metadata
uv run eatout search --max-kcal 700 --min-protein 25 --limit 5
uv run eatout search --json --query tofu
uv run eatout guide            # the full agent-facing manual
```

`SKILL.md` is the agent-facing contract; `eatout guide` is the same manual from
inside the binary. `eatout skill install` puts the skill where agents look.

## Data

The meal document is a build artifact. `data/sources/*.json` in the dataset
checkout is the reviewed source of truth — one restaurant per file, with a
citation on every item — and the artifact is regenerated from it and diffed by
a human. This tool only ever reads it:

1. `eatout --data PATH <command>`
2. `$EATOUT_DATA`
3. the artifact bundled in this repository or installed package

`per_serving` carries only the macros an operator published; an absent key means
the figure does not exist. Nothing here fills one in, at any layer.

`data/research/*.json` and `data/place-candidates.json` are the review record
behind those sources: which chains were considered, and why the ones that were
rejected publish nothing usable. No code reads them, so neither is published;
only `data/meals.json` ships in the wheel.

## Refreshing a source

Ingestion lives in `scripts/`, outside the package, because the CLI is
read-only by contract. Pull a restaurant, diff it, then rebuild the artifact:

```sh
uv run --project . python -m scripts.import_grilld
git diff data/sources/grilld.json
uv run --project . python -m scripts.regenerate
```

Only Grill'd has an importer; every other source is still maintained by hand.
`scripts/regenerate.py` is the only writer of `data/meals.json`, and a test
asserts the committed artifact matches what it produces.

## Development

```sh
uv run --project . pytest -q
uvx ruff check src scripts --line-length 79
```
