import json
import pathlib

from scripts.regenerate import build_document, located, read_sources, render

ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "data" / "meals.json"


def test_located_puts_the_restaurants_location_after_the_items_source():
    item = {"item_name": "X", "source_url": "s", "tags": ["a"], "kcal": 1}
    source = {"maps_url": "u"}

    assert list(located(item, source)) == [
        "item_name",
        "source_url",
        "maps_url",
        "tags",
        "kcal",
    ]


def test_located_leaves_an_item_alone_when_the_source_has_no_location():
    item = {"item_name": "X", "source_url": "s"}

    assert located(item, {}) == item


def test_build_source_drops_the_review_stamp():
    document = build_document(
        [{"reviewed_at": "2026-01-01T00:00:00.000Z", "restaurant": "X"}]
    )

    assert document["generated_at"] == "2026-01-01T00:00:00.000Z"
    assert "reviewed_at" not in document["sources"][0]


def test_render_expands_a_string_array_like_the_reviewed_sources():
    assert render({"tags": ["a", "b"]}) == (
        '{\n  "tags": [\n    "a",\n    "b"\n  ]\n}'
    )


def test_regenerating_reproduces_the_committed_artifact():
    """The artifact is a build output, so a stale one is a review problem."""
    expected = ARTIFACT.read_text(encoding="utf-8")

    assert render(build_document(read_sources(ROOT))) + "\n" == expected


def test_the_artifact_is_stamped_with_the_newest_review_it_contains():
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    newest = max(raw["reviewed_at"] for raw in read_sources(ROOT))

    assert committed["generated_at"] == newest


def test_regenerating_changes_no_nutrition_content():
    """Ordering and whitespace are free to move; the data is not."""
    rebuilt = json.loads(render(build_document(read_sources(ROOT))))
    committed = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    assert rebuilt == committed


def test_located_keeps_the_location_when_an_item_has_no_source():
    """A malformed item must not silently lose its restaurant's location."""
    located_item = located({"item_name": "X"}, {"maps_url": "u"})

    assert located_item == {"item_name": "X", "maps_url": "u"}
