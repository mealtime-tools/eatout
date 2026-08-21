"""Rebuild data/sources/grilld.json from Grill'd's public ordering API.

The eatout CLI is read-only by contract, so ingestion lives here rather than
behind a command. Run this, diff the result, then regenerate the artifact.

Grill'd publishes a per-serve panel for every bun variant of every product, so
the only judgement in here is which products to take and when to distrust a
macro set. Both are decided by rule: the operator's own menu categories, and
the same validator the reader applies.
"""

import json
import urllib.request
from datetime import UTC, datetime
from typing import Any

import click

from eatout.nutrition import MealDataError, normalize_meal, round1

API_BASE = "https://api.digital.grilld.com.au/v1"
ORDER_TYPE_PICKUP = 106
SYDNEY_CBD = (-33.8688, 151.2093)
TIMEOUT_S = 15

RESTAURANT = "Grill'd"
SOURCE_URL = "https://ordering.digital.grilld.com.au"
MAPS_URL = (
    "https://maps.google.com/?cid=15235200541032909243&g_mp=Cidnb29nbGUubWFw"
    "cy5wbGFjZXMudjEuUGxhY2VzLlNlYXJjaFRleHQQAhgBIAA"
)

# Grill'd shelves its meat-free burgers under these two titles, so following
# them picks up a new product instead of silently missing it.
MENU_CATEGORIES = ("Vegetarian", "Vegan")
ATTR_VEGETARIAN = "V"
ATTR_VEGAN = "VE"

NOTE = "Direct from Grill'd ordering API nutrition table."
NOTE_INCONSISTENT = (
    f"{NOTE} Fat and carbohydrate are omitted because the API's per-serve"
    " macro set is inconsistent with its labelled energy."
)

KJ_PER_KCAL = 4.184

# Grill'd publishes no nutrition for any add-on, so this one is the patty's
# own maker's figure for the 2.5 oz foodservice patty Grill'd serves. The
# 113 g retail patty is a different serve and overstates every macro.
EXTRA_BEYOND_PATTY = {
    "item_name": "Extra Beyond Patty",
    "calories_kcal": 143.8,
    "protein_g": 13,
    "vegetarian": True,
    "vegan": True,
    "confidence": "high_confidence_estimate",
    "notes": (
        "Grill'd publishes no add-on nutrition. Figures are Beyond Meat's"
        " 2.5 oz foodservice Beyond Burger IV, the patty Grill'd states it"
        " serves, whose published 13 g protein and 1 g saturated fat both"
        " match the 4 oz label scaled to 2.5 oz."
    ),
    "source_url": (
        "https://www.beyondmeat.com/en-US/press/beyond-meat-expands-"
        "foodservice-portfolio-with-the-fourth-generation-beyond-burger-"
        "and-new-beyond-crispy-nuggets"
    ),
    "fat_g": 8.8,
    "carbs_g": 5,
}


def parse_nutrition(table_rows: Any) -> dict[str, float] | None:
    """One bun variant's panel, carrying only the macros it actually states."""
    values = {row[0]: row[1] for row in table_rows or [] if len(row) > 1}
    kilojoules = _number(values.get("Energy"), "kJ")
    protein = _number(values.get("Protein"), "g")

    if kilojoules is None or protein is None:
        return None

    parsed = {
        "calories_kcal": round1(kilojoules / KJ_PER_KCAL),
        "protein_g": protein,
    }
    for key, label in (("fat_g", "Fat"), ("carbs_g", "Carbohydrate")):
        macro = _number(values.get(label), "g")
        if macro is not None:
            parsed[key] = macro

    return parsed


def is_vegetarian(product: dict[str, Any]) -> bool:
    attributes = product.get("attributes") or []

    return ATTR_VEGETARIAN in attributes or ATTR_VEGAN in attributes


def is_vegan(product: dict[str, Any]) -> bool:
    return ATTR_VEGAN in (product.get("attributes") or [])


def menu_products(menu: dict[str, Any]) -> list[dict[str, Any]]:
    """Every product Grill'd files under a meat-free category."""
    by_title = {
        category.get("title"): category
        for category in menu.get("categories") or []
    }
    missing = [name for name in MENU_CATEGORIES if name not in by_title]

    if missing:
        raise LookupError(f"Grill'd menu has no {', '.join(missing)} category")

    return [
        product
        for name in MENU_CATEGORIES
        for product in by_title[name].get("items")
        or by_title[name].get("products")
        or []
    ]


def bun_items(product: dict[str, Any]) -> list[dict[str, Any]]:
    """One reviewed row per bun, including No Bun, which is orderable."""
    choices = (product.get("multiChoices") or [{}])[0]
    vegetarian, vegan = is_vegetarian(product), is_vegan(product)
    items = []

    for choice in choices.get("items") or []:
        parsed = parse_nutrition(
            (choice.get("nutrition") or {}).get("tableRows")
        )
        if parsed is None:
            continue

        items.append(
            _validated(
                {
                    "item_name": f"{product['title']} ({choice['title']})",
                    "calories_kcal": parsed["calories_kcal"],
                    "protein_g": parsed["protein_g"],
                    "vegetarian": vegetarian,
                    "vegan": vegan,
                    "confidence": "exact",
                    "notes": NOTE,
                    "source_url": SOURCE_URL,
                    **{
                        key: parsed[key]
                        for key in ("fat_g", "carbs_g")
                        if key in parsed
                    },
                }
            )
        )

    return items


def build_source(
    fetch_json: Any, reviewed_at: str | None = None
) -> dict[str, Any]:
    """The whole reviewed source file, as data/sources/grilld.json holds it."""
    restaurant = _nearest_restaurant(fetch_json)
    menu = fetch_json(
        f"{API_BASE}/restaurants/{restaurant['id']}/menu"
        f"?orderType={ORDER_TYPE_PICKUP}"
    )
    products = [
        fetch_json(
            f"{API_BASE}/restaurants/{restaurant['id']}/menu/{item['id']}"
            f"?orderType={ORDER_TYPE_PICKUP}"
        )
        for item in menu_products(menu)
    ]
    add_ons = [EXTRA_BEYOND_PATTY] if any(map(_sells_patty, products)) else []

    return {
        "reviewed_at": reviewed_at or _today(),
        "restaurant": RESTAURANT,
        "source_url": SOURCE_URL,
        "maps_url": MAPS_URL,
        "allow_add_ons": True,
        "base_items": [row for p in products for row in bun_items(p)],
        "add_ons": add_ons,
    }


def _validated(item: dict[str, Any]) -> dict[str, Any]:
    """Refuse a macro set the operator's own energy figure contradicts.

    Grill'd's SuperBun rows label ~130 kcal more than their macros support.
    Dropping the pair keeps the published energy and reports the macros as
    unknown, which is what they are; anything still broken is refused.
    """
    probe = {**item, "restaurant": RESTAURANT}

    try:
        normalize_meal(probe)

        return item
    except MealDataError:
        if "fat_g" not in item and "carbs_g" not in item:
            raise

    lean = {k: v for k, v in item.items() if k not in ("fat_g", "carbs_g")}
    lean["notes"] = NOTE_INCONSISTENT
    normalize_meal({**lean, "restaurant": RESTAURANT})

    return lean


def _sells_patty(product: dict[str, Any]) -> bool:
    return any(
        addition.get("title") == "Extra Beyond Patty"
        for addition in product.get("additions") or []
    )


def _nearest_restaurant(fetch_json: Any) -> dict[str, Any]:
    latitude, longitude = SYDNEY_CBD
    found = fetch_json(
        f"{API_BASE}/restaurants/nearby"
        f"?lat={latitude}&lng={longitude}&limit=10"
    )
    stores = found if isinstance(found, list) else found.get("data") or []

    for store in stores:
        if ORDER_TYPE_PICKUP in (store.get("orderTypes") or []):
            return store

    raise LookupError("no Grill'd pickup restaurant near Sydney CBD")


def _number(text: Any, unit: str) -> float | None:
    """A panel figure like "17.8g", or None where the operator stated none."""
    cleaned = str(text or "").replace(",", "").strip()

    if not cleaned.lower().endswith(unit.lower()):
        return None

    try:
        return float(cleaned[: -len(unit)].strip())
    except ValueError:
        return None


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT00:00:00.000Z")


def _http_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "eatout"})

    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        return json.loads(response.read())


@click.command()
@click.option(
    "--out",
    type=click.Path(dir_okay=False),
    default="data/sources/grilld.json",
    show_default=True,
    help="Where to write the reviewed source file.",
)
def main(out: str) -> None:
    """Pull Grill'd from its ordering API and write the reviewed source."""
    source = build_source(_http_json)

    with open(out, "w", encoding="utf-8") as handle:
        json.dump(source, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    click.echo(
        f"wrote {len(source['base_items'])} base items and "
        f"{len(source['add_ons'])} add-ons to {out}"
    )


if __name__ == "__main__":
    main()
