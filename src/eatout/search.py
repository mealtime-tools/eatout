"""Expanding the dataset into candidates, then filtering and ranking them.

Pure functions over records: no I/O and no click, so the same code answers a
CLI, a test literal, and anything later that wants the domain without a shell.

Everything only a restaurant meal has lives under `detail`.
"""

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from eatout.nutrition import (
    Meal,
    MealDataError,
    combine_confidence,
    normalize_meal,
    protein_per_100_kcal,
    round1,
)

# Provenance an item may leave to its restaurant. An item that states one of
# these overrides it; one that states nothing inherits, so a per-item citation
# is never silently replaced by the restaurant-wide one.
INHERITED = ("restaurant", "source_url", "maps_url")


@dataclass(frozen=True)
class Filters:
    """A search request. `None` means the caller stated no ceiling at all."""

    max_kcal: float | None = None
    min_protein: float | None = None
    query: str = ""


@dataclass(frozen=True)
class Results:
    """Candidates that provably pass, and those a filter could not check."""

    matched: list[dict[str, Any]]
    unverifiable: list[dict[str, Any]]


def expand_meals(document: Mapping[str, Any]) -> list[Meal]:
    """Every vegetarian option in the document, base items and add-on pairs.

    Add-ons multiply the option count, so this is done once per process and the
    result reused rather than recomputed per filter.
    """
    sources = document.get("sources")

    if not isinstance(sources, list):
        raise MealDataError("meal data must contain a sources array")

    return [meal for source in sources for meal in _expand_source(source)]


def meal_candidate(meal: Meal) -> dict[str, Any]:
    """One meal as the shared candidate record.

    Nutrients are top-level. Missing values are null, because a 0 there would
    read as a nutrient-free dish. The
    citation and the confidence travel with it, since a caller quoting a number
    has to be able to say where it came from.
    """
    nutrients = {
        "kcal": meal.calories_kcal,
        "protein": meal.protein_g,
        "fat": meal.fat_g,
        "carbs": meal.carbs_g,
        "fiber": None,
        "sodium": None,
        "sugar": None,
    }
    return {
        "kind": "meal",
        "id": candidate_id(meal),
        "name": f"{meal.restaurant} - {meal.item_name}",
        **nutrients,
        "complete": all(
            nutrients[key] is not None
            for key in ("kcal", "protein", "fat", "carbs")
        ),
        "detail": _detail(meal),
    }


def candidate_id(meal: Meal) -> str:
    """A slug of restaurant and item: the same meal, the same id, everywhere.

    Derived rather than assigned because the dataset carries no ids, and folded
    to ASCII so a machine's Unicode handling cannot move the boundary between
    two ids.
    """
    label = f"{meal.restaurant} {meal.item_name}"
    folded = unicodedata.normalize("NFKD", label)
    ascii_only = folded.encode("ascii", "ignore").decode()

    return "-".join(_normalize_text(ascii_only).split())


def find_candidates(meals: Sequence[Meal], filters: Filters) -> Results:
    """Filter to what is orderable and asked for, then rank.

    Non-vegetarian items are out of scope for this dataset, so they are dropped
    unconditionally rather than being offered behind a flag.
    """
    tokens = _search_tokens(filters.query)
    scoped = [
        meal for meal in meals if meal.vegetarian and _matches(meal, tokens)
    ]

    return partition([meal_candidate(meal) for meal in scoped], filters)


def partition(
    candidates: Sequence[dict[str, Any]], filters: Filters
) -> Results:
    """Split candidates into those that pass and those that cannot be checked.

    Both lists are ranked by the shared metric, so a merged answer from several
    tools is ordered the same way whoever produced it.
    """
    matched: list[dict[str, Any]] = []
    unchecked: list[dict[str, Any]] = []

    # A filter asked about a macro this candidate lacks: still excluded, but
    # reported, because "could not check" is a different answer from "no".
    for record in candidates:
        if (filters.max_kcal is not None and record["kcal"] is None) or (
            filters.min_protein is not None and record["protein"] is None
        ):
            unchecked.append(record)
        elif (
            filters.max_kcal is None or record["kcal"] <= filters.max_kcal
        ) and (
            filters.min_protein is None
            or record["protein"] >= filters.min_protein
        ):
            matched.append(record)

    return Results(matched=_rank(matched), unverifiable=_rank(unchecked))


def _rank(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Protein density first, then protein and name."""
    return sorted(
        records,
        key=lambda record: (
            -record["detail"]["protein_per_100_kcal"],
            -record["protein"],
            record["name"].casefold(),
        ),
    )


def _detail(meal: Meal) -> dict[str, Any]:
    """The meal-specific half, which nothing shared ever reads."""
    return {
        "restaurant": meal.restaurant,
        "item_name": meal.item_name,
        "protein_per_100_kcal": protein_per_100_kcal(meal),
        "vegetarian": meal.vegetarian,
        "vegan": meal.vegan,
        "confidence": meal.confidence,
        "source_url": meal.source_url,
    }


def _matches(meal: Meal, tokens: Sequence[str]) -> bool:
    if not tokens:
        return True

    haystack = _normalize_text(f"{meal.restaurant} {meal.item_name}")

    return all(token in haystack for token in tokens)


def _search_tokens(query: str | None) -> list[str]:
    return _normalize_text(query or "").split()


def _normalize_text(value: str) -> str:
    """Fold punctuation away so "Grill'd" matches "grilld"."""
    return re.sub(r"[^a-z0-9]+", " ", value.lower().replace("'", "")).strip()


def _expand_source(source: Mapping[str, Any]) -> list[Meal]:
    add_ons = (
        [meal for meal in _source_items(source, "add_ons") if meal.vegetarian]
        # A source must opt in: combinations are only offered where the
        # operator publishes add-on figures for those items.
        if source.get("allow_add_ons") is True
        else []
    )

    return [
        option
        for base in _source_items(source, "base_items")
        if base.vegetarian
        for option in _options(base, add_ons)
    ]


def _source_items(source: Mapping[str, Any], field: str) -> list[Meal]:
    """Normalize a source's items, inheriting the source-level provenance."""
    return [
        normalize_meal(
            {
                **item,
                **{
                    key: source[key]
                    for key in INHERITED
                    if item.get(key) is None and source.get(key) is not None
                },
            }
        )
        for item in source.get(field) or []
    ]


def _options(base: Meal, add_ons: Sequence[Meal]) -> list[Meal]:
    return [base] + [
        _combine(base, add_on) for add_on in add_ons if _applies(base, add_on)
    ]


def _applies(base: Meal, add_on: Meal) -> bool:
    """An untagged add-on goes with anything; a tagged one only with its tags."""
    if not add_on.applies_to_tags:
        return True

    return any(tag in base.tags for tag in add_on.applies_to_tags)


def _combine(base: Meal, add_on: Meal) -> Meal:
    """Base plus add-on, re-validated as if it were a published row.

    A total is only reported for a macro both contributors publish: adding a
    known figure to an unknown one yields an unknown, never the known part.
    """
    combined = {
        "restaurant": base.restaurant,
        "item_name": f"{base.item_name} + {add_on.item_name}",
        "kcal": round1(base.calories_kcal + add_on.calories_kcal),
        "protein": round1(base.protein_g + add_on.protein_g),
        "fat": _combined_macro(base.fat_g, add_on.fat_g),
        "carbs": _combined_macro(base.carbs_g, add_on.carbs_g),
        "vegetarian": base.vegetarian and add_on.vegetarian,
        "vegan": base.vegan and add_on.vegan,
        "confidence": combine_confidence(base.confidence, add_on.confidence),
        "notes": "; ".join(
            note for note in (base.notes, add_on.notes) if note
        ),
        "source_url": base.source_url,
        "maps_url": base.maps_url,
        "tags": list(base.tags),
    }

    return normalize_meal(combined)


def _combined_macro(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None

    return round1(left + right)
