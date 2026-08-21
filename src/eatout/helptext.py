"""Shared help strings and the in-binary manual.

One place, so a flag reads the same on every command and an agent that only
sees one `--help` still learns the rules it would otherwise pay a failed call
to discover. The macro filters are not here: they come from `agentcli` so every
candidate source spells them identically.
"""

DATA = (
    "Path to the reviewed meal document. Defaults to $EATOUT_DATA, then the "
    "artifact in the checkout. Read-only, always."
)

QUERY = (
    "Match restaurant or item name. Punctuation and case are ignored, so "
    '"grilld" matches "Grill\'d". All words must match.'
)

GUIDE = """
eatout -- cited vegetarian restaurant nutrition for Sydney CBD.

WHAT THIS IS
  A read-only snapshot of published restaurant figures, reviewed one
  restaurant at a time, with a citation on every item. A data source, nothing
  more: it does not estimate, log, or reach the network. Report
  `generated_at` as the age of the data; it is not the current date.

OUTPUT
  Human text by default; `--json` emits exactly one JSON object on stdout:

    {"ok":true,"data":{...}}

  A failure emits {"ok":false,"error":{"message":"..."}} on stdout under
  --json, on stderr otherwise, with a nonzero exit. A search matching nothing
  is a success: exit 0, count 0.

EXIT CODES
  0 success, 1 usage error or unreadable data, 3 assertion failure, 4 --strict
  warning. Code 2 (remote) is unused: this tool never uses the network.

COMMANDS
  eatout metadata
      Snapshot provenance: generated_at, restaurant count, item counts.

  eatout search --max-kcal 700 --min-protein 25 --limit 10
      Ranked candidates. Add --query TEXT.

  eatout skill install|uninstall|status
  eatout guide

THE CANDIDATE RECORD
  `search` emits the shared candidate shape, so its results merge with any
  other candidate source and rank as one list:

    {"kind":"meal","id":"crust-pizza-...","name":"Crust Pizza - ...",
     "per_serving":{"kcal":625,"protein":45.8},"complete":false,
     "detail":{"restaurant":"Crust Pizza","item_name":"...",
               "protein_per_100_kcal":7.3,"vegetarian":true,"vegan":false,
               "confidence":"exact","source_url":"..."}}

  `id` is a slug of restaurant and item: stable across runs and machines.
  Ranking is protein per 100 kcal descending, then protein, then name.

MISSING VALUES -- THE RULE THAT MATTERS
  `per_serving` carries only the macros the operator published. The example
  above has no `fat` and no `carbs` because those figures do not exist -- it is
  not a fat-free pizza. `complete` is false whenever a macro is absent. Never
  report an absent macro as 0, never derive one from the calories, and never
  fill a set in downstream.

  A candidate a filter could not check -- it lacks the macro you filtered on --
  is listed under `unverifiable` instead of being dropped. "No results" and
  "three I could not check" are different answers.

PROVENANCE
  Every candidate carries `source_url` and `confidence` (exact,
  high_confidence_estimate, low_confidence_estimate). Quote both when
  explaining a number.

DATA
  `data/sources/*.json` is the reviewed source of truth and the meal document
  is generated from it. No command here writes to either; correcting a number
  means editing a source file in the dataset checkout and regenerating.
"""
