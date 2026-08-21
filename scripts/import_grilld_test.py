import pytest

from eatout.nutrition import MealDataError
from scripts.import_grilld import (
    EXTRA_BEYOND_PATTY,
    build_source,
    bun_items,
    is_vegan,
    is_vegetarian,
    menu_products,
    parse_nutrition,
)


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
