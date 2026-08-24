"""The candidate record's published shape, machine and human.

Both output paths are pinned here because the nutrients are what a caller
reads: a key order change or a silently dropped nutrient is a contract break,
not an implementation detail.
"""

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner
from mealtime_nutrients import CORE_NUTRIENTS, NUTRIENTS as VOCABULARY

from eatout.cli import main
from eatout.search import _MEAL_READERS

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

RECORD_KEYS = ("kind", "id", "name", "complete", "detail")


def _run(tmp_path: Path, *args: str) -> str:
    path = tmp_path / "meals.json"
    path.write_text(json.dumps(DOCUMENT), encoding="utf-8")
    result = CliRunner().invoke(main, ["--data", str(path), "search", *args])

    assert result.exit_code == 0, result.output

    return result.output


def _candidates(tmp_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(_run(tmp_path, "--json"))["data"]

    return payload["candidates"]


def _nutrient_keys(record: dict[str, Any]) -> list[str]:
    return [key for key in record if key not in RECORD_KEYS]


def test_only_the_core_nutrients_have_a_meal_reader() -> None:
    assert set(_MEAL_READERS) == set(CORE_NUTRIENTS)


def test_the_record_states_the_core_nutrients_and_nothing_else(
    tmp_path: Path,
) -> None:
    for record in _candidates(tmp_path):
        assert tuple(_nutrient_keys(record)) == CORE_NUTRIENTS


def test_json_records_keep_the_published_key_order(tmp_path: Path) -> None:
    for record in _candidates(tmp_path):
        keys = list(record)

        assert keys[:3] == ["kind", "id", "name"]
        assert keys[-2:] == ["complete", "detail"]


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
    assert plain["complete"] is True


def test_json_omits_every_nutrient_no_source_states(tmp_path: Path) -> None:
    unsourced = [name for name in VOCABULARY if name not in CORE_NUTRIENTS]

    for record in _candidates(tmp_path):
        assert [name for name in unsourced if name in record] == []


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
