"""What a meal record may and may not say about itself."""

import pytest

from eatout.nutrition import MealDataError, normalize_meal

# Crust publishes protein and energy for this pizza but no fat or carbohydrate.
PIZZA = {
    "restaurant": "Crust Pizza",
    "item_name": "Peri Peri (not) Chicken - High Protein Base (Half)",
    "calories_kcal": 625,
    "protein_g": 45.8,
    "vegetarian": True,
    "confidence": "exact",
    "source_url": "https://www.crust.com.au/nutrition",
}

# A complete, self-consistent macro set, one of whose figures is a whole number.
MARGHERITA = {
    **PIZZA,
    "item_name": "Classic Margherita - High Protein Base (Half)",
    "calories_kcal": 540,
    "protein_g": 41.5,
    "fat_g": 23.0,
    "carbs_g": 34.7,
}


def test_unpublished_macro_is_none_and_a_published_zero_survives() -> None:
    unpublished = normalize_meal(PIZZA)
    zero_fat = normalize_meal(
        {
            **PIZZA,
            "calories_kcal": 200,
            "protein_g": 20,
            "fat_g": 0,
            "carbs_g": 30,
        }
    )

    assert unpublished.fat_g is None
    assert unpublished.carbs_g is None

    # A published zero is a measurement and must not be confused with absence.
    assert zero_fat.fat_g == 0


def test_the_energy_tolerance_stays_wider_below_the_label_than_above() -> None:
    """AU labels under-count carbohydrate, so a deficit gets more room.

    Both sets miss the stated 540 kcal by 70. The one that accounts for less
    is ordinary; the one that accounts for more is a panel read wrong.
    """
    under = normalize_meal({**MARGHERITA, "fat_g": 20, "carbs_g": 31})

    assert under.carbs_g == 31

    with pytest.raises(MealDataError):
        normalize_meal({**MARGHERITA, "fat_g": 24, "carbs_g": 57})


@pytest.mark.parametrize(
    "broken",
    [
        {"protein_g": None},
        {"protein_g": 0},
        {"fat_g": 200, "carbs_g": 200},
        {"source_url": ""},
    ],
)
def test_refuses_a_record_it_cannot_read(broken: dict) -> None:
    with pytest.raises(MealDataError):
        normalize_meal({**MARGHERITA, **broken})
