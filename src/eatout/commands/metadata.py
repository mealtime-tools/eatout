"""`eatout metadata` -- how old the snapshot is and how much is in it."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

import click
from agentcli import emit, json_option

from eatout.data import load_document


@click.command("metadata")
@json_option
@click.pass_obj
def metadata(data: Path | None, json_output: bool) -> None:
    """Report the snapshot's provenance and item counts."""
    document = load_document(data)
    sources = document["sources"]
    payload = {
        "generated_at": document["generated_at"],
        "restaurant_count": len(sources),
        "base_item_count": _count(sources, "base_items"),
        "add_on_count": _count(sources, "add_ons"),
    }

    emit(payload, json_output=json_output, human=_human)


def _count(sources: list[dict[str, Any]], field: str) -> int:
    return sum(len(source.get(field) or []) for source in sources)


def _human(payload: dict[str, Any]) -> Iterable[str]:
    yield f"generated_at: {payload['generated_at']}"
    yield f"restaurants:  {payload['restaurant_count']}"
    yield f"base items:   {payload['base_item_count']}"
    yield f"add-ons:      {payload['add_on_count']}"
