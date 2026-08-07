from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from argus_skill.core.completion_gate import project_completion_issue
from argus_skill.skills.stage_machine import complete_final_stage
from argus_skill.skills.vertical_select import persist_vertical
from argus_skill.verticals._base import vertical_completion_issue


def test_missing_vertical_completion_hook_is_satisfied(tmp_path) -> None:
    assert vertical_completion_issue(SimpleNamespace(), tmp_path) == ""


def test_vertical_completion_hook_result_is_returned(tmp_path) -> None:
    module = SimpleNamespace(
        completion_issue=lambda root: "research_discovery:invalid_decision"
    )
    assert (
        vertical_completion_issue(module, tmp_path)
        == "research_discovery:invalid_decision"
    )


def test_vertical_completion_hook_exception_fails_closed(tmp_path) -> None:
    def broken(_root):
        raise RuntimeError("boom")

    issue = vertical_completion_issue(
        SimpleNamespace(completion_issue=broken),
        tmp_path,
    )
    assert issue == "vertical completion check unavailable: RuntimeError"


def test_external_gate_has_precedence(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(
        "ARGUS_SKILL_EXTERNAL_COMPLETION_GATE",
        "controller.json:satisfied",
    )
    assert "external completion gate is missing" in project_completion_issue(tmp_path)


def test_invalid_discovery_package_cannot_complete_final_stage(tmp_path) -> None:
    persist_vertical(tmp_path, "research_discovery")
    discovery = tmp_path / "research" / "discovery"
    discovery.mkdir(parents=True)
    (discovery / "BRIEF.md").write_text("A bounded discovery brief.\n", encoding="utf-8")
    (discovery / "PORTFOLIO.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "objective": "Choose a research direction.",
                "focus_domain": "testing",
                "budget": {
                    "summary": "One validation cycle.",
                    "stop_condition": "Stop after the first decisive result.",
                },
                "bet_refs": [],
                "search_summary": {
                    "as_of": "2026-08-08",
                    "sources": ["operator-provided evidence"],
                    "queries": ["completion gate behavior"],
                },
            }
        ),
        encoding="utf-8",
    )
    (discovery / "DECISION.json").write_text("{}\n", encoding="utf-8")

    state_path = tmp_path / "research" / "PIPELINE_STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current_stage"] = "decide"
    state["stages"] = {"decide": {"status": "in_progress"}}
    state_path.write_text(json.dumps(state), encoding="utf-8")

    with pytest.raises(ValueError, match=r"research_discovery:invalid_"):
        complete_final_stage(tmp_path, reason="reviewer certified completion")

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["stages"]["decide"]["status"] != "done"
