"""The meal record and everything derived from one.

The one rule this module exists to enforce: an unavailable macro stays
unavailable. `fat_g` and `carbs_g` are `None` when the operator never published
them, they are never defaulted to zero, and every consumer here has to opt into
handling `None`. A zero fat figure and an unknown one mean opposite things to
someone counting macros.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# Ordered worst-last: combining two figures keeps the weaker claim.
CONFIDENCE_RANKS = {
    "exact": 0,
    "high_confidence_estimate": 1,
    "low_confidence_estimate": 2,
}

CONFIDENCE_BY_RANK = {rank: name for name, rank in CONFIDENCE_RANKS.items()}


class MealDataError(ValueError):
    """A meal record could not be read as stated. Never repaired, refused."""


@dataclass(frozen=True)
class Meal:
    """One orderable item, or one item plus one add-on.

    Optional fields are `None`, not 0, and are omitted from output entirely.
    """

    restaurant: str
    item_name: str
    calories_kcal: float
    protein_g: float
    vegetarian: bool
    vegan: bool
    confidence: str
    source_url: str
    notes: str = ""
    fat_g: float | None = None
    carbs_g: float | None = None
    maps_url: str | None = None
    tags: tuple[str, ...] = ()
    applies_to_tags: tuple[str, ...] = ()


def normalize_meal(raw: Mapping[str, Any]) -> Meal:
    """Validate one raw record, refusing anything it cannot read."""
    calories = _positive_number(raw.get("calories_kcal"), "calories_kcal")
    protein = _positive_number(raw.get("protein_g"), "protein_g")

    # Protein alone cannot exceed the labelled energy: that is a units mix-up,
    # not a meal, and it would rank first under protein-per-calorie.
    if calories < protein * 4:
        raise MealDataError("calories_kcal is below protein calories")

    fat = _optional_number(raw.get("fat_g"), "fat_g")
    carbs = _optional_number(raw.get("carbs_g"), "carbs_g")
    _check_energy(calories, protein, fat, carbs)

    return Meal(
        restaurant=_text(raw.get("restaurant"), "restaurant"),
        item_name=_text(raw.get("item_name"), "item_name"),
        calories_kcal=calories,
        protein_g=protein,
        vegetarian=raw.get("vegetarian") is True,
        vegan=raw.get("vegan") is True,
        confidence=_confidence(raw.get("confidence")),
        source_url=_text(raw.get("source_url"), "source_url"),
        notes=raw["notes"] if isinstance(raw.get("notes"), str) else "",
        fat_g=fat,
        carbs_g=carbs,
        maps_url=_optional_text(raw.get("maps_url")),
        tags=_tags(raw.get("tags")),
        applies_to_tags=_tags(raw.get("applies_to_tags")),
    )


def protein_per_100_kcal(meal: Meal) -> float:
    """The reported protein density, rounded once so it reads like a label.

    Ranking uses the unrounded figure via `agentcli.rank`; this is the number a
    caller quotes.
    """
    return round1(meal.protein_g / meal.calories_kcal * 100)


def round1(value: float) -> float:
    """Round half up to one decimal, then drop a meaningless `.0`.

    Half up rather than Python's half-to-even, because the dataset and the
    reference implementation were built with it and re-rounding must not move
    a published figure.
    """
    return as_number(math.floor(value * 10 + 0.5) / 10)


def as_number(value: float) -> float:
    """Return an integral float as an int, so 540.0 is emitted as `540`."""
    number = float(value)

    return int(number) if number.is_integer() else number


def combine_confidence(left: str, right: str) -> str:
    """Two figures combined are only as trustworthy as the weaker one."""
    rank = max(CONFIDENCE_RANKS.get(left, 0), CONFIDENCE_RANKS.get(right, 0))

    return CONFIDENCE_BY_RANK[rank]


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MealDataError(f"{field} must be a non-empty string")

    return value.strip()


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _positive_number(value: Any, field: str) -> float:
    number = _finite(value, field)

    if number <= 0:
        raise MealDataError(f"{field} must be greater than 0")

    return number


def _optional_number(value: Any, field: str) -> float | None:
    """Absent means unknown. Present means published, including a real 0."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None

    number = _finite(value, field)

    if number < 0:
        raise MealDataError(f"{field} must not be negative")

    return number


def _finite(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MealDataError(f"{field} must be a finite number") from exc

    if not math.isfinite(number):
        raise MealDataError(f"{field} must be a finite number")

    return as_number(number)


def _confidence(value: Any) -> str:
    confidence = value.strip() if isinstance(value, str) else ""
    confidence = confidence or "exact"

    if confidence not in CONFIDENCE_RANKS:
        raise MealDataError(
            "confidence must be one of " + ", ".join(CONFIDENCE_RANKS)
        )

    return confidence


def _tags(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()

    return tuple(
        tag.strip() for tag in value if isinstance(tag, str) and tag.strip()
    )


def _check_energy(
    calories: float,
    protein: float,
    fat: float | None,
    carbs: float | None,
) -> None:
    """Reject a macro set that cannot produce the labelled energy.

    Only checkable when both optional macros are known, which is the point: a
    partial set is left alone rather than completed with a guess.
    """
    if fat is None or carbs is None:
        return

    difference = protein * 4 + fat * 9 + carbs * 4 - calories

    # AU labels exclude fibre from carbohydrate yet count some fibre energy, so
    # a deficit is expected and gets more room than an excess.
    allowed = max(20.0, calories * (0.15 if difference < 0 else 0.1))

    if abs(difference) > allowed:
        raise MealDataError(
            "protein, fat, and carbs are inconsistent with calories_kcal"
        )
