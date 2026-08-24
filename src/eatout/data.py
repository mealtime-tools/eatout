"""Locating and reading the meal document. The only file access in the tool.

The document is a build artifact: `data/sources/*.json` is the reviewed source
of truth, one restaurant per file with item-local citations, and the artifact is
regenerated from it and diffed by a human. Nothing here writes, so a stale
artifact is a review problem rather than something a command silently fixes.
"""

import json
import os
from pathlib import Path
from typing import Any

from agentcli import UsageError

from eatout.nutrition import Meal, MealDataError
from eatout.search import expand_meals

ENV_PATH = "EATOUT_DATA"


def _owned_data() -> Path:
    """Find the same owned data in a wheel or source checkout."""
    packaged = Path(__file__).resolve().parent / "data"
    if packaged.is_dir():
        return packaged

    return Path(__file__).resolve().parents[2] / "data"


# Read-only at runtime: editing it would edit a review outcome, not a source.
REFERENCE_PATH = _owned_data() / "meals.json"


def resolve_path(explicit: str | Path | None = None) -> Path:
    """Where the meal document is: flag, then environment, then the checkout."""
    if explicit:
        return Path(explicit).expanduser()

    from_env = os.environ.get(ENV_PATH)

    return Path(from_env).expanduser() if from_env else REFERENCE_PATH


def load_document(explicit: str | Path | None = None) -> dict[str, Any]:
    """Read the meal document, refusing one that cannot be interpreted."""
    path = resolve_path(explicit)

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UsageError(
            f"could not read meal data at {path}: {exc.strerror or exc}. "
            f"Set ${ENV_PATH} or pass --data."
        ) from None
    except json.JSONDecodeError as exc:
        raise UsageError(f"{path} is not valid JSON: {exc}") from None

    if not isinstance(document, dict):
        raise UsageError(f"{path} must contain a JSON object")

    # Every answer is stamped with this, so a snapshot cannot pass as current.
    if not isinstance(document.get("generated_at"), str):
        raise UsageError(f"{path} is missing generated_at")

    if not isinstance(document.get("sources"), list):
        raise UsageError(f"{path} must contain a sources array")

    return document


def load_meals(
    explicit: str | Path | None = None,
) -> tuple[dict[str, Any], list[Meal]]:
    """The document and its expanded options, with data errors reported."""
    document = load_document(explicit)

    try:
        return document, expand_meals(document)
    except MealDataError as exc:
        raise UsageError(f"{resolve_path(explicit)}: {exc}") from None
