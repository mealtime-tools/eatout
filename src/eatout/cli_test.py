"""The CLI contract: one JSON object, the right exit code, real data."""

import json

import pytest
from click.testing import CliRunner

from eatout.cli import main
from eatout.data import REFERENCE_PATH
from eatout.search_test import DOCUMENT


@pytest.fixture
def data_path(tmp_path):
    path = tmp_path / "meals.json"
    path.write_text(json.dumps(DOCUMENT), encoding="utf-8")

    return path


def _run(data_path, *args):
    return CliRunner().invoke(main, ["--data", str(data_path), *args])


def test_the_surface_is_a_data_source_only() -> None:
    # `nutrilog` shorthand was orchestration: eatout must not know that another
    # tool exists.
    assert sorted(main.commands) == [
        "guide",
        "metadata",
        "search",
        "skill",
    ]


def test_search_emits_one_candidate_object(data_path) -> None:
    result = _run(data_path, "search", "--json", "--min-protein", "30")
    payload = json.loads(result.output)
    data = payload["data"]

    assert result.exit_code == 0
    assert payload["ok"] is True
    assert list(data) == [
        "generated_at",
        "count",
        "candidates",
        "unverifiable",
    ]
    assert data["generated_at"] == DOCUMENT["generated_at"]
    assert data["count"] == len(data["candidates"])

    candidate = data["candidates"][0]
    assert list(candidate) == [
        "kind",
        "id",
        "name",
        "per_serving",
        "complete",
        "detail",
    ]
    assert candidate["kind"] == "meal"
    # The dataset never published this salad's fat, so no `fat` key exists.
    assert candidate["per_serving"] == {"kcal": 300, "protein": 30}


def test_a_search_matching_nothing_still_succeeds(data_path) -> None:
    result = _run(data_path, "search", "--json", "--min-protein", "900")

    assert result.exit_code == 0
    assert json.loads(result.output)["data"] == {
        "generated_at": DOCUMENT["generated_at"],
        "count": 0,
        "candidates": [],
        "unverifiable": [],
    }


def test_a_failure_is_an_error_object_on_stdout(data_path) -> None:
    result = _run(data_path, "search", "--json", "--max-kcal", "-1")

    assert result.exit_code == 1
    # Symmetric with success: one `ok` key a consumer can always branch on.
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert list(payload) == ["ok", "error"]
    assert list(payload["error"]) == ["message"]


@pytest.mark.skipif(
    not REFERENCE_PATH.is_file(), reason="reviewed dataset not checked out"
)
def test_the_reviewed_dataset_loads_and_ranks() -> None:
    metadata = json.loads(
        CliRunner().invoke(main, ["metadata", "--json"]).output
    )["data"]
    candidates = json.loads(
        CliRunner().invoke(main, ["search", "--json", "--limit", "500"]).output
    )["data"]["candidates"]
    densities = [
        record["per_serving"]["protein"] / record["per_serving"]["kcal"]
        for record in candidates
    ]

    assert metadata["restaurant_count"] > 0
    assert metadata["base_item_count"] > metadata["restaurant_count"]
    assert densities == sorted(densities, reverse=True)
    # Whatever the dataset says, it must never invent a macro to fill a set.
    assert any("fat" not in record["per_serving"] for record in candidates)
    assert all(record["id"] for record in candidates)
