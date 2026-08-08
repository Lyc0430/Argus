from __future__ import annotations

from pathlib import Path

import pytest

from argus_skill.life.memory import Backlog, BacklogItem


def test_ensure_many_is_idempotent_and_keeps_existing_siblings(
    tmp_path: Path,
) -> None:
    backlog = Backlog(tmp_path / "backlog.jsonl")
    sibling = backlog.add(
        BacklogItem.new(item_id="sibling", title="Sibling", objective="keep")
    )
    derived = BacklogItem.new(
        item_id="derived",
        title="Derived",
        objective="expand",
        tags=["research-discovery"],
        node_key="derive:evt-a",
    )

    first = backlog.ensure_many([derived])
    second = backlog.ensure_many([derived])

    assert [item.id for item in first] == ["derived"]
    assert [item.id for item in second] == ["derived"]
    assert [item.id for item in backlog.all()] == [sibling.id, "derived"]


def test_ensure_many_rejects_existing_id_with_different_authored_contract(
    tmp_path: Path,
) -> None:
    backlog = Backlog(tmp_path / "backlog.jsonl")
    backlog.add(
        BacklogItem.new(item_id="derived", title="Derived", objective="expand")
    )

    with pytest.raises(ValueError, match="different authored contract"):
        backlog.ensure_many(
            [
                BacklogItem.new(
                    item_id="derived",
                    title="Renamed",
                    objective="expand differently",
                )
            ]
        )


def test_ensure_many_rejects_duplicate_batch_ids(tmp_path: Path) -> None:
    backlog = Backlog(tmp_path / "backlog.jsonl")

    with pytest.raises(ValueError, match="duplicate item ids"):
        backlog.ensure_many(
            [
                BacklogItem.new(item_id="same", title="First", objective="one"),
                BacklogItem.new(item_id="same", title="Second", objective="two"),
            ]
        )


def test_ensure_many_preserves_dependency_cycle_validation(tmp_path: Path) -> None:
    backlog = Backlog(tmp_path / "backlog.jsonl")

    with pytest.raises(ValueError, match="dependency cycle"):
        backlog.ensure_many(
            [
                BacklogItem.new(
                    item_id="left",
                    title="Left",
                    objective="left",
                    deps=["right"],
                ),
                BacklogItem.new(
                    item_id="right",
                    title="Right",
                    objective="right",
                    deps=["left"],
                ),
            ]
        )
