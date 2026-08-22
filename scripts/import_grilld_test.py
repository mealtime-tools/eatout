import json
import pathlib

import pytest

from eatout.nutrition import MealDataError, normalize_meal, round1
from scripts.import_grilld import (
    EXTRA_BEYOND_PATTY,
    build_source,
    bun_items,
    is_vegan,
    is_vegetarian,
    menu_products,
    parse_nutrition,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]

# Beyond Meat's own published figures, from the two pages the add-on cites.
# Grill'd publishes no add-on panel, so these are the only check there is.
FOODSERVICE_PROTEIN_G = 13
RETAIL_4OZ = {"calories_kcal": 230, "fat_g": 14, "carbs_g": 8}
FOODSERVICE_SCALE = 2.5 / 4


def rows(energy, protein, fat=None, carbs=None):
    table = [["Energy", energy], ["Protein", protein]]
    if fat is not None:
        table.append(["Fat", fat])
    if carbs is not None:
        table.append(["Carbohydrate", carbs])

    return table


def product(title, attributes, items, additions=()):
    return {
        "title": title,
        "attributes": list(attributes),
        "multiChoices": [{"title": "Add Bun", "items": items}],
        "additions": [{"title": name} for name in additions],
    }


def bun(title, energy, protein, fat=None, carbs=None):
    return {
        "title": title,
        "nutrition": {"tableRows": rows(energy, protein, fat, carbs)},
    }


def test_parse_nutrition_converts_kilojoules_to_calories():
    parsed = parse_nutrition(rows("1750kJ", "24.5g", "17.8g", "36.4g"))

    assert parsed == {
        "calories_kcal": 418.3,
        "protein_g": 24.5,
        "fat_g": 17.8,
        "carbs_g": 36.4,
    }


def test_parse_nutrition_omits_macros_the_operator_left_out():
    parsed = parse_nutrition(rows("1010kJ", "18.8g"))

    assert parsed == {"calories_kcal": 241.4, "protein_g": 18.8}


def test_parse_nutrition_reads_a_label_that_states_its_unit_in_brackets():
    """A parenthetical qualifies the row rather than renaming it."""
    parsed = parse_nutrition(
        [["Energy (kJ)", "1750"], ["Protein (g)", "24.5"]]
    )

    assert parsed == {"calories_kcal": 418.3, "protein_g": 24.5}


def test_parse_nutrition_refuses_a_row_without_energy_or_protein():
    assert parse_nutrition(rows("", "24.5g")) is None
    assert parse_nutrition([["Protein", "24.5g"]]) is None


def test_is_vegan_reads_the_ve_attribute():
    assert is_vegan({"attributes": ["V", "DF", "GFR", "VE"]}) is True
    assert is_vegan({"attributes": ["GFR", "V"]}) is False


def test_is_vegetarian_counts_a_vegan_product_too():
    assert is_vegetarian({"attributes": ["GFR", "V"]}) is True
    assert is_vegetarian({"attributes": ["VE"]}) is True
    assert is_vegetarian({"attributes": ["LC", "GFR"]}) is False


def test_menu_products_follows_the_operators_own_categories():
    menu = {
        "categories": [
            {"title": "Beef", "items": [{"id": 1, "title": "Almighty"}]},
            {"title": "Vegetarian", "items": [{"id": 2, "title": "Garden"}]},
            {"title": "Vegan", "items": [{"id": 3, "title": "Vegan Garden"}]},
        ]
    }

    assert [p["id"] for p in menu_products(menu)] == [2, 3]


def test_menu_products_refuses_a_menu_missing_a_category():
    with pytest.raises(LookupError):
        menu_products({"categories": [{"title": "Beef", "items": []}]})


def test_bun_items_keeps_no_bun_as_a_selectable_option():
    raw = product(
        "Beyond Mustard & Pickled!",
        ["GFR", "V"],
        [
            bun("Panini", "1750kJ", "24.5g", "17.8g", "36.4g"),
            bun("No Bun", "1010kJ", "18.8g", "12.7g", "12.9g"),
        ],
    )

    names = [item["item_name"] for item in bun_items(raw)]

    assert names == [
        "Beyond Mustard & Pickled! (Panini)",
        "Beyond Mustard & Pickled! (No Bun)",
    ]


def test_bun_items_marks_a_vegan_product_vegan():
    raw = product(
        "Vegan Beyond Mustard & Pickled!",
        ["V", "DF", "GFR", "VE"],
        [bun("Panini", "1930kJ", "24.7g", "18.4g", "47.8g")],
    )

    assert bun_items(raw)[0]["vegan"] is True


def test_bun_items_drops_macros_the_labelled_energy_contradicts():
    raw = product(
        "Beyond Mustard & Pickled!",
        ["GFR", "V"],
        [bun("SuperBun", "2450kJ", "34.5g", "25.9g", "19.9g")],
    )

    item = bun_items(raw)[0]

    assert "fat_g" not in item and "carbs_g" not in item
    assert "inconsistent" in item["notes"]


def test_bun_items_refuses_a_row_that_cannot_be_repaired_by_dropping():
    raw = product(
        "Broken",
        ["V"],
        [bun("Panini", "100kJ", "50g", "1g", "1g")],
    )

    with pytest.raises(MealDataError):
        bun_items(raw)


def test_build_source_assembles_the_reviewed_shape():
    menu = {
        "categories": [
            {"title": "Vegetarian", "items": [{"id": 7, "title": "Garden"}]},
            {"title": "Vegan", "items": []},
        ]
    }
    detail = product(
        "Garden",
        ["V"],
        [bun("Panini", "1750kJ", "24.5g", "17.8g", "36.4g")],
        additions=["Extra Beyond Patty"],
    )
    responses = {
        "nearby": [{"id": 146, "orderTypes": [106]}],
        "menu": menu,
        "product": detail,
    }

    def fake(url):
        if "nearby" in url:
            return responses["nearby"]
        return responses["product"] if "/menu/" in url else responses["menu"]

    source = build_source(fake, reviewed_at="2026-08-21T00:00:00.000Z")

    assert source["restaurant"] == "Grill'd"
    assert source["allow_add_ons"] is True
    assert source["add_ons"] == [EXTRA_BEYOND_PATTY]
    assert [i["item_name"] for i in source["base_items"]] == [
        "Garden (Panini)"
    ]


def test_build_source_refuses_a_menu_whose_panels_no_longer_parse():
    """A renamed panel label must fail loudly, not empty the source file.

    Row names are matched whole, so a label that merely contains "Energy" is
    as unreadable as one that drops the word altogether.
    """
    menu = {
        "categories": [
            {"title": "Vegetarian", "items": [{"id": 7, "title": "Garden"}]},
            {"title": "Vegan", "items": []},
        ]
    }
    renamed = {
        "title": "Garden",
        "attributes": ["V"],
        "multiChoices": [
            {
                "items": [
                    {
                        "title": "Panini",
                        "nutrition": {
                            "tableRows": [
                                ["Energy Content Per Serve", "1750kJ"],
                                ["Protein", "24.5g"],
                            ]
                        },
                    }
                ]
            }
        ],
        "additions": [],
    }

    def fake(url):
        if "nearby" in url:
            return [{"id": 146, "orderTypes": [106]}]
        return renamed if "/menu/" in url else menu

    with pytest.raises(LookupError, match="panel labels"):
        build_source(fake, reviewed_at="x")


def test_build_source_omits_the_add_on_when_the_menu_lacks_it():
    menu = {
        "categories": [
            {"title": "Vegetarian", "items": [{"id": 7, "title": "Garden"}]},
            {"title": "Vegan", "items": []},
        ]
    }
    detail = product("Garden", ["V"], [bun("Panini", "1750kJ", "24.5g")])

    def fake(url):
        if "nearby" in url:
            return [{"id": 146, "orderTypes": [106]}]
        return detail if "/menu/" in url else menu

    assert build_source(fake, reviewed_at="x")["add_ons"] == []


def test_the_beyond_patty_carries_its_makers_published_figures():
    """Protein is published for the foodservice patty; the rest is scaled.

    Beyond states protein and saturated fat for the 2.5 oz patty and nothing
    else, so energy, fat and carbohydrate come from the 4 oz retail label
    scaled by weight.
    """
    assert EXTRA_BEYOND_PATTY["protein_g"] == FOODSERVICE_PROTEIN_G

    for key, retail in RETAIL_4OZ.items():
        assert EXTRA_BEYOND_PATTY[key] == round1(retail * FOODSERVICE_SCALE)


def test_the_beyond_patty_survives_the_readers_own_validator():
    """A hand-authored row combines with every base item, so it must hold up."""
    meal = normalize_meal({**EXTRA_BEYOND_PATTY, "restaurant": "Grill'd"})

    assert meal.confidence == "high_confidence_estimate"


def test_the_committed_source_carries_the_same_beyond_patty():
    """The constant and the reviewed file must not drift apart unnoticed."""
    committed = json.loads(
        (ROOT / "data" / "sources" / "grilld.json").read_text(encoding="utf-8")
    )

    assert committed["add_ons"] == [EXTRA_BEYOND_PATTY]
