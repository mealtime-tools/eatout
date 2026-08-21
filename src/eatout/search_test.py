"""Expansion, the shared candidate shape, filtering, and the ranking."""

import random

from eatout.search import (
    Filters,
    expand_meals,
    find_candidates,
    meal_candidate,
    partition,
)

CAFE = {
    "restaurant": "Test Cafe",
    "source_url": "https://example.test/nutrition",
    "allow_add_ons": True,
    "base_items": [
        {
            "item_name": "Tofu Bowl",
            "calories_kcal": 500,
            "protein_g": 30,
            "vegetarian": True,
            "fat_g": 20,
            "carbs_g": 40,
            "tags": ["bowl"],
        },
        {
            "item_name": "Wrap",
            "calories_kcal": 450,
            "protein_g": 15,
            "vegetarian": True,
        },
        {
            "item_name": "Chicken Bowl",
            "calories_kcal": 500,
            "protein_g": 40,
            "vegetarian": False,
            "tags": ["bowl"],
        },
    ],
    "add_ons": [
        {
            "item_name": "Extra Tofu",
            "calories_kcal": 136,
            "protein_g": 9.8,
            "vegetarian": True,
            "applies_to_tags": ["bowl"],
            "confidence": "high_confidence_estimate",
        }
    ],
}

# A restaurant that published no fat or carbs, so a macro filter asking
# about either has nothing to check its item against.
PARTIAL = {
    "restaurant": "Partial Kitchen",
    "source_url": "https://example.test/partial",
    "base_items": [
        {
            "item_name": "Salad",
            "calories_kcal": 300,
            "protein_g": 30,
            "vegetarian": True,
        }
    ],
}

DOCUMENT = {
    "generated_at": "2026-08-20T00:00:00.000Z",
    "sources": [CAFE, PARTIAL],
}


def _names(meals) -> list[str]:
    return [meal.item_name for meal in meals]


def _candidate_ids(document) -> list[str]:
    return [meal_candidate(meal)["id"] for meal in expand_meals(document)]


def _found(filters: Filters) -> list[str]:
    results = find_candidates(expand_meals(DOCUMENT), filters)

    return [record["detail"]["item_name"] for record in results.matched]


def test_expansion_offers_only_the_orderable_vegetarian_options() -> None:
    names = _names(expand_meals(DOCUMENT))

    assert "Chicken Bowl" not in names
    assert "Chicken Bowl + Extra Tofu" not in names
    # A tagged add-on attaches only to base items carrying one of its tags.
    assert "Tofu Bowl + Extra Tofu" in names
    assert "Wrap + Extra Tofu" not in names


def test_candidate_publishes_only_the_macros_the_operator_did() -> None:
    meals = {meal.item_name: meal for meal in expand_meals(DOCUMENT)}
    complete = meal_candidate(meals["Tofu Bowl"])
    partial = meal_candidate(meals["Salad"])

    assert complete["kind"] == "meal"
    assert complete["id"] == "test-cafe-tofu-bowl"
    assert complete["name"] == "Test Cafe - Tofu Bowl"
    assert complete["per_serving"] == {
        "kcal": 500,
        "protein": 30,
        "fat": 20,
        "carbs": 40,
    }
    assert complete["complete"] is True

    # The salad's fat was never published: no key, no zero, `complete` false.
    assert partial["per_serving"] == {"kcal": 300, "protein": 30}
    assert partial["complete"] is False
    assert "fat" not in partial["per_serving"]

    # Provenance has to survive into the candidate or a number cannot be cited.
    assert partial["detail"]["source_url"] == PARTIAL["source_url"]
    assert partial["detail"]["confidence"] == "exact"
    assert partial["detail"]["protein_per_100_kcal"] == 10


def test_the_id_is_a_stable_ascii_slug() -> None:
    accented = {
        **DOCUMENT,
        "sources": [
            {
                **PARTIAL,
                "restaurant": "Guzman y Gomez",
                "base_items": [
                    {
                        **PARTIAL["base_items"][0],
                        "item_name": "Saut\u00e9ed Bowl",
                    }
                ],
            }
        ],
    }
    combined = next(
        meal
        for meal in expand_meals(DOCUMENT)
        if meal.item_name == "Tofu Bowl + Extra Tofu"
    )

    # Derived from restaurant and item alone -- no counters, no file order --
    # and folded to ASCII so no machine's Unicode handling can move it.
    assert meal_candidate(combined)["id"] == "test-cafe-tofu-bowl-extra-tofu"
    assert _candidate_ids(accented) == ["guzman-y-gomez-sauteed-bowl"]


def test_macro_filters_are_inclusive_at_the_boundary() -> None:
    assert _found(Filters(max_kcal=500, min_protein=30)) == [
        "Salad",
        "Tofu Bowl",
    ]
    assert _found(Filters(max_kcal=499.9, min_protein=30)) == ["Salad"]
    assert _found(Filters(max_kcal=500, min_protein=30.1)) == []


def test_the_text_filter() -> None:
    punctuated = {**DOCUMENT, "sources": [{**CAFE, "restaurant": "Grill'd"}]}
    queried = find_candidates(
        expand_meals(punctuated), Filters(query="GRILLD wrap")
    )

    # Case and punctuation are folded away; every word must match.
    assert [record["name"] for record in queried.matched] == ["Grill'd - Wrap"]


def test_add_on_total_needs_both_parts_to_publish_the_macro() -> None:
    combined = next(
        meal
        for meal in expand_meals(DOCUMENT)
        if meal.item_name == "Tofu Bowl + Extra Tofu"
    )

    assert combined.protein_g == 39.8
    assert combined.calories_kcal == 636
    # The add-on publishes no fat, so the total is unknown, not the base's 20.
    assert combined.fat_g is None
    assert combined.carbs_g is None
    assert combined.confidence == "high_confidence_estimate"


def test_a_candidate_a_filter_cannot_check_is_reported_not_dropped() -> None:
    unchecked = {
        "kind": "meal",
        "id": "unlabelled",
        "name": "Unlabelled Kitchen - Mystery Bowl",
        "per_serving": {"kcal": 400},
        "complete": False,
        "detail": {},
    }
    results = partition([unchecked], Filters(min_protein=20))

    # Excluded from the answer, but "could not check" is not "does not pass".
    assert results.matched == []
    assert results.unverifiable == [unchecked]
    assert partition([unchecked], Filters(max_kcal=500)).matched == [unchecked]


def test_ties_rank_the_same_whatever_order_they_arrive_in() -> None:
    tied = [
        {
            "item_name": name,
            "calories_kcal": 400,
            "protein_g": protein,
            "vegetarian": True,
        }
        for name, protein in (("Zeta", 20), ("Alpha", 20), ("Beta", 24))
    ]
    document = {
        **DOCUMENT,
        "sources": [{**CAFE, "base_items": tied, "add_ons": []}],
    }
    meals = expand_meals(document)
    shuffled = random.Random(7).sample(meals, len(meals))

    def ordered(records) -> list[str]:
        return [
            record["detail"]["item_name"]
            for record in find_candidates(records, Filters()).matched
        ]

    # Density first, then protein, then name -- never arrival order.
    assert ordered(meals) == ["Beta", "Alpha", "Zeta"]
    assert ordered(shuffled) == ordered(meals)
