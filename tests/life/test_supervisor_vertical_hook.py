from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from argus_skill.life.supervisor._planner_orchestration import (
    PlannerOrchestrationMixin,
)
from argus_skill.skills.vertical_select import persist_vertical
from argus_skill.verticals._base import vertical_after_mission


def test_vertical_after_mission_normalizes_absent_success_and_error() -> None:
    calls: list[dict] = []

    class Missing:
        pass

    class Working:
        @staticmethod
        def after_mission(**context):
            calls.append(context)
            return {"status": "reconciled"}

    class Broken:
        @staticmethod
        def after_mission(**_context):
            raise RuntimeError("boom")

    assert vertical_after_mission(Missing(), value=1) == {}
    assert vertical_after_mission(Working(), value=2) == {
        "status": "reconciled"
    }
    assert calls == [{"value": 2}]
    assert vertical_after_mission(Broken(), value=3) == {
        "status": "hook_error",
        "error": "RuntimeError",
    }


class _Harness(PlannerOrchestrationMixin):
    def __init__(self, root: Path, *, host_stop: str = "") -> None:
        self._root = root
        self.config = SimpleNamespace(
            post_mission_hook=lambda _outcome: host_stop,
        )
        self.memory = SimpleNamespace(
            root=root,
            project_root=root,
            global_root=root.parent / "global",
            backlog=object(),
        )

    def _artifact_root(self) -> Path:
        return self._root


def test_supervisor_calls_vertical_hook_after_host_hook(
    tmp_path: Path, monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    persist_vertical(project_root, "research_discovery")
    calls: list[dict] = []

    from argus_skill.verticals.research_discovery import stages

    monkeypatch.setattr(
        stages,
        "after_mission",
        lambda **context: calls.append(context) or {"status": "queued"},
        raising=False,
    )
    harness = _Harness(project_root)
    outcome = {"item_id": "task-a", "status": "done"}

    assert harness._post_mission_hook(outcome) == ""
    assert len(calls) == 1
    assert calls[0]["project_root"] == project_root
    assert calls[0]["state_root"] == project_root
    assert calls[0]["global_root"] == tmp_path / "global"
    assert calls[0]["backlog"] is harness.memory.backlog
    assert calls[0]["outcome"] == outcome


def test_host_stop_reason_prevents_vertical_mutation(
    tmp_path: Path, monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    persist_vertical(project_root, "research_discovery")
    calls: list[dict] = []

    from argus_skill.verticals.research_discovery import stages

    monkeypatch.setattr(
        stages,
        "after_mission",
        lambda **context: calls.append(context),
        raising=False,
    )

    assert (
        _Harness(project_root, host_stop="daemon_handoff")._post_mission_hook(
            {"status": "done"}
        )
        == "daemon_handoff"
    )
    assert calls == []
