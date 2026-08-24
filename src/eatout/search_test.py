"""The candidate record's published shape, machine and human.

Both output paths are pinned here because the nutrient vocabulary is what a
caller reads: a key order change or a silently dropped nutrient is a contract
break, not an implementation detail.
"""

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from eatout.cli import main

# The add-on publishes fat but not carbs, exercising the all-or-nothing merge.
DOCUMENT = {
    "generated_at": "2026-01-01T00:00:00Z",
    "sources": [
        {
            "restaurant": "Test Cafe",
            "source_url": "https://example.test/menu",
            "allow_add_ons": True,
            "base_items": [
                {
                    "item_name": "Tofu Bowl",
                    "vegetarian": True,
                    "vegan": True,
                    "confidence": "exact",
                    "kcal": 500,
                    "protein": 25,
                    "fat": 20,
                    "carbs": 50,
                    "tags": ["bowl"],
                }
            ],
            "add_ons": [
                {
                    "item_name": "Extra Tofu",
                    "vegetarian": True,
                    "vegan": True,
                    "confidence": "high_confidence_estimate",
                    "kcal": 100,
                    "protein": 10,
                    "fat": 5,
                    "applies_to_tags": ["bowl"],
                }
            ],
        }
    ],
}

NUTRIENT_KEYS = ["kcal", "protein", "fat", "carbs", "fiber", "sodium", "sugar"]
RECORD_KEYS = ["kind", "id", "name", *NUTRIENT_KEYS, "complete", "detail"]


def _run(tmp_path: Path, *args: str) -> str:
    path = tmp_path / "meals.json"
    path.write_text(json.dumps(DOCUMENT), encoding="utf-8")
    result = CliRunner().invoke(main, ["--data", str(path), "search", *args])

    assert result.exit_code == 0, result.output

    return result.output


def _candidates(tmp_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(_run(tmp_path, "--json"))["data"]

    return payload["candidates"]


def test_json_records_keep_the_published_key_order(tmp_path: Path) -> None:
    for record in _candidates(tmp_path):
        assert list(record) == RECORD_KEYS


def test_json_reports_a_plain_item_as_published(tmp_path: Path) -> None:
    plain = next(
        record
        for record in _candidates(tmp_path)
        if record["name"] == "Test Cafe - Tofu Bowl"
    )

    assert plain["kcal"] == 500
    assert plain["protein"] == 25
    assert plain["fat"] == 20
    assert plain["carbs"] == 50
    assert plain["fiber"] is None
    assert plain["sodium"] is None
    assert plain["sugar"] is None
    assert plain["complete"] is True


def test_json_drops_a_macro_only_one_contributor_publishes(
    tmp_path: Path,
) -> None:
    combined = next(
        record
        for record in _candidates(tmp_path)
        if record["name"] == "Test Cafe - Tofu Bowl + Extra Tofu"
    )

    assert combined["kcal"] == 600
    assert combined["protein"] == 35
    assert combined["fat"] == 25
    assert combined["carbs"] is None
    assert combined["complete"] is False
    assert combined["detail"]["confidence"] == "high_confidence_estimate"


def test_human_output_shows_both_options(tmp_path: Path) -> None:
    assert _run(tmp_path).splitlines() == [
        "# generated_at: 2026-01-01T00:00:00Z",
        "# 2 candidates",
        "  5.8 p/100kcal  600 kcal  35 g protein  25 g fat  ? g carbs  "
        "Test Cafe - Tofu Bowl + Extra Tofu  [high_confidence_estimate]",
        "    5 p/100kcal  500 kcal  25 g protein  20 g fat  50 g carbs  "
        "Test Cafe - Tofu Bowl  [exact]",
    ]
