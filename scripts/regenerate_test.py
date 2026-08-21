import json
import pathlib

from scripts.regenerate import build_document, located, read_sources, render

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_located_puts_the_restaurants_location_ahead_of_tags():
    item = {"item_name": "X", "tags": ["a"]}
    source = {"maps_url": "u"}

    assert list(located(item, source)) == ["item_name", "maps_url", "tags"]


def test_no_source_carries_a_distance():
    """Distances were derived from a private address, so none may come back."""
    for raw in read_sources(ROOT):
        assert "distance_km" not in raw


def test_build_source_drops_the_review_stamp():
    document = build_document(
        [{"reviewed_at": "2026-01-01T00:00:00.000Z", "restaurant": "X"}]
    )

    assert document["generated_at"] == "2026-01-01T00:00:00.000Z"
    assert "reviewed_at" not in document["sources"][0]


def test_render_keeps_a_string_array_on_one_line():
    assert render({"tags": ["a", "b"]}) == '{\n  "tags": ["a", "b"]\n}'


def test_render_expands_an_array_of_objects():
    assert render([{"a": 1}]) == '[\n  {\n    "a": 1\n  }\n]'


def test_regenerating_reproduces_the_committed_artifact():
    """The artifact is a build output, so a stale one is a review problem."""
    expected = (ROOT / "data" / "meals.json").read_text(encoding="utf-8")

    assert render(build_document(read_sources(ROOT))) + "\n" == expected


def test_every_source_item_survives_into_the_artifact():
    document = build_document(read_sources(ROOT))
    counted = sum(
        len(source.get(field) or [])
        for source in document["sources"]
        for field in ("base_items", "add_ons")
    )
    committed = json.loads(
        (ROOT / "data" / "meals.json").read_text(encoding="utf-8")
    )

    assert counted == sum(
        len(source.get(field) or [])
        for source in committed["sources"]
        for field in ("base_items", "add_ons")
    )
