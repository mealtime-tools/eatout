"""Rebuild data/meals.json from data/sources/*.json.

The artifact is the sources concatenated in filename order, each item stamped
with its restaurant's location so a caller never walks back up to the parent.
It is rendered exactly like the reviewed sources -- json.dumps at indent 2 --
so that regenerating after a source edit diffs only the edit.
"""

import json
import pathlib
from typing import Any

import click

INHERITED = ("maps_url",)
ANCHOR = "source_url"


def located(item: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """One item carrying its restaurant's location, beside its own source."""
    inherited = {f: source[f] for f in INHERITED if f in source}
    kept: dict[str, Any] = {}
    for key, value in item.items():
        kept[key] = value

        # The inherited location reads as a citation, so it follows the cite.
        if key == ANCHOR:
            kept.update(inherited)

    # An item with no cite to anchor to still keeps its restaurant's location.
    if ANCHOR not in item:
        return kept | inherited

    return kept


def build_source(raw: dict[str, Any]) -> dict[str, Any]:
    """One restaurant as the artifact holds it: no review stamp, located."""
    source = {k: v for k, v in raw.items() if k != "reviewed_at"}
    for field in ("base_items", "add_ons"):
        if field in source:
            source[field] = [located(i, raw) for i in source[field]]

    return source


def build_document(raws: list[dict[str, Any]]) -> dict[str, Any]:
    """The whole artifact, stamped with the newest review it contains."""
    return {
        "generated_at": max(raw["reviewed_at"] for raw in raws),
        "sources": [build_source(raw) for raw in raws],
    }


def render(value: Any) -> str:
    """The artifact's text, matching how the reviewed sources are written."""
    return json.dumps(value, indent=2, ensure_ascii=False)


def read_sources(root: pathlib.Path) -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((root / "data" / "sources").glob("*.json"))
    ]


@click.command()
@click.option(
    "--root",
    type=click.Path(file_okay=False, exists=True),
    default=".",
    show_default=True,
    help="Dataset checkout holding data/sources.",
)
def main(root: str) -> None:
    """Regenerate the meal document from the reviewed source files."""
    base = pathlib.Path(root)
    document = build_document(read_sources(base))
    out = base / "data" / "meals.json"
    out.write_text(render(document) + "\n", encoding="utf-8")

    click.echo(f"wrote {len(document['sources'])} sources to {out}")


if __name__ == "__main__":
    main()
