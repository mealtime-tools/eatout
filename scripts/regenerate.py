"""Rebuild data/meals.json from data/sources/*.json.

The artifact is the sources concatenated in filename order, each item stamped
with its restaurant's location so a caller never walks back up to the parent.
Rendering is hand-rolled because the committed file keeps short string arrays
on one line, and a reformatting diff would bury the review.
"""

import json
import pathlib
from typing import Any

import click

INHERITED = ("maps_url",)
TRAILING = ("tags", "applies_to_tags")


def located(item: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """One item carrying its restaurant's location, ahead of its tags."""
    kept = {k: v for k, v in item.items() if k not in TRAILING}
    for field in INHERITED:
        if field in source:
            kept[field] = source[field]

    return kept | {k: item[k] for k in TRAILING if k in item}


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


def render(value: Any, depth: int = 0) -> str:
    """JSON at indent 2, except an all-string array, which stays inline."""
    pad, inner = "  " * depth, "  " * (depth + 1)

    if isinstance(value, dict):
        if not value:
            return "{}"
        body = ",\n".join(
            f"{inner}{json.dumps(k, ensure_ascii=False)}: "
            f"{render(v, depth + 1)}"
            for k, v in value.items()
        )

        return "{\n" + body + "\n" + pad + "}"

    if isinstance(value, list):
        if not value:
            return "[]"
        if all(isinstance(v, str) for v in value):
            joined = ", ".join(
                json.dumps(v, ensure_ascii=False) for v in value
            )

            return f"[{joined}]"
        body = ",\n".join(inner + render(v, depth + 1) for v in value)

        return "[\n" + body + "\n" + pad + "]"

    return json.dumps(value, ensure_ascii=False)


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
