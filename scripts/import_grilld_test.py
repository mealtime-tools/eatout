"""The Grill'd panel reader, pinned to figures already in reviewed data.

The kilojoule figures below are Grill'd's own panel values, recovered from
data/sources/grilld.json: each committed kcal has exactly one integer kJ that
produces it. Changing how energy is converted must leave these alone, because
a moved figure silently rewrites a row a reviewer already signed off.
"""

from scripts.import_grilld import parse_nutrition

# (panel kJ, committed kcal), across the range and both bun extremes.
ENERGY_ROWS = (
    (1010, 241.4),
    (1450, 346.6),
    (1710, 408.7),
    (2450, 585.6),
    (2830, 676.4),
    (3000, 717),
)


def test_energy_matches_the_reviewed_figures() -> None:
    for kilojoules, kcal in ENERGY_ROWS:
        rows = [["Energy", f"{kilojoules}kJ"], ["Protein", "20g"]]

        assert parse_nutrition(rows)["kcal"] == kcal


def test_grams_pass_through_unconverted() -> None:
    rows = [
        ["Energy", "1710kJ"],
        ["Protein", "17.8g"],
        ["Fat", "20.1g"],
        ["Carbohydrate", "45g"],
    ]

    assert parse_nutrition(rows) == {
        "kcal": 408.7,
        "protein": 17.8,
        "fat": 20.1,
        "carbs": 45,
    }


def test_a_panel_without_energy_states_nothing() -> None:
    assert parse_nutrition([["Protein", "17.8g"]]) is None
