"""Small contracts for the curated restaurant source."""

import hashlib
import json
from pathlib import Path

from click.testing import CliRunner

from eatout.cli import main
from eatout.data import load_meals
from eatout.search import meal_candidate

DATA_DIGEST = (
    "6ff14c155552107a1c9d324a2c336daf7e917c890047924c2d865758d2885089"
)


def test_curated_data_is_unchanged() -> None:
    digest = hashlib.sha256()
    root = Path(__file__).resolve().parents[2] / "data"
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root.parent).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")

    assert digest.hexdigest() == DATA_DIGEST


def test_restaurant_nutrients_use_the_canonical_shape() -> None:
    _, meals = load_meals()
    candidate = next(
        meal_candidate(meal) for meal in meals if meal.fat_g is None
    )

    assert candidate["fat"] is None
    assert candidate["carbs"] is None
    # An unstated nutrient is absent, which reads as the null above: unknown.
    assert "fiber" not in candidate
    assert "nutrients" not in candidate
    assert "per_serving" not in candidate
    assert candidate["complete"] is False


def test_cli_searches_the_reviewed_restaurants() -> None:
    result = CliRunner().invoke(
        main, ["search", "--json", "--query", "grilld", "--limit", "1"]
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["data"]
    assert payload["count"] == 1
    assert "Grill'd" in payload["candidates"][0]["name"]
