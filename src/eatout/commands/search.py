"""`eatout search` -- ranked meal candidates matching the stated filters."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import click
from agentcli import emit, json_option, limit_option, macro_options

from eatout.data import load_meals
from eatout.search import MEAL_NUTRIENTS, Filters, find_candidates

# The reference CLI's default. Wide enough to compare options, small enough
# that an agent is not handed the whole dataset.
DEFAULT_LIMIT = 25

# Labels only: an unlabelled nutrient falls back to its key, never disappears.
UNITS = {
    "kcal": "kcal",
    "protein": "g protein",
    "fat": "g fat",
    "carbs": "g carbs",
}


@click.command("search")
@macro_options
@click.option("--query", default="", help="Words in restaurant or item name.")
@limit_option(DEFAULT_LIMIT)
@json_option
@click.pass_obj
def search(
    data: Path | None,
    max_kcal: float | None,
    min_protein: float | None,
    query: str,
    limit: int,
    json_output: bool,
) -> None:
    """Search reviewed vegetarian meals as ranked candidate records.

    Matching nothing is a success with an empty list, not an error. A candidate
    omits a macro the operator never published; that absence means unknown and
    must not be read as zero. Candidates a filter could not check are listed
    under `unverifiable` rather than dropped.
    """
    document, meals = load_meals(data)
    filters = Filters(
        max_kcal=max_kcal,
        min_protein=min_protein,
        query=query,
    )
    results = find_candidates(meals, filters)

    # Only the matches are truncated: an "I could not check these" list is an
    # answer about the whole dataset, so a partial one would understate it.
    candidates = results.matched[:limit]
    payload = {
        "generated_at": document["generated_at"],
        "count": len(candidates),
        "candidates": candidates,
        "unverifiable": results.unverifiable,
    }

    emit(payload, json_output=json_output, human=_human)


def _human(payload: dict[str, Any]) -> Iterable[str]:
    yield f"# generated_at: {payload['generated_at']}"
    yield f"# {payload['count']} candidates"

    for record in payload["candidates"]:
        detail = record["detail"]
        yield (
            f"{detail['protein_per_100_kcal']:>5} p/100kcal  "
            f"{_macros(record)}  {record['name']}  [{detail['confidence']}]"
        )

    for record in payload["unverifiable"]:
        yield f"# unverifiable: {record['name']}"


def _macros(record: dict[str, Any]) -> str:
    """Show unknown values as question marks, never zero."""
    return "  ".join(
        f"{record[key] if record[key] is not None else '?'} "
        f"{UNITS.get(key, key)}"
        for key in MEAL_NUTRIENTS
    )
