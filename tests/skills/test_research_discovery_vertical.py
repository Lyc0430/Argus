from pathlib import Path

from argus_skill.skills.builtins import iter_vertical_skill_texts
from argus_skill.skills.vertical_select import (
    VERTICAL_PURPOSES,
    VERTICALS,
    persist_vertical,
)
from argus_skill.verticals._base import (
    load_vertical,
    vertical_checklist_items,
    vertical_checklist_stage_order,
    vertical_completion_contract_version,
    vertical_completion_gate,
    vertical_requires_independent_review,
    vertical_role_banner,
    vertical_workflow_mode,
)

EXPECTED_SKILLS = {
    "manager/research-discovery-manager.md",
    "planner/research-discovery-planning.md",
    "engineer/idea-discovery.md",
    "engineer/idea-creator.md",
    "engineer/novelty-check.md",
    "engineer/theory-application-bridge.md",
    "engineer/dual-lane-probing.md",
    "reviewer/research-discovery-review.md",
    "scientist/research-discovery-distillation.md",
    "scientist/research-discovery-adaptation.md",
}


def test_research_discovery_vertical_contract() -> None:
    assert "research_discovery" in VERTICALS
    assert set(VERTICAL_PURPOSES) == set(VERTICALS)
    module = load_vertical("research_discovery")
    assert vertical_checklist_stage_order(module) == ("frame", "discover", "probe", "decide")
    assert vertical_workflow_mode(module) == "proportional"
    assert vertical_completion_gate(module) == "none"
    assert vertical_requires_independent_review(module) is True
    assert vertical_completion_contract_version(module) == 1


def test_research_discovery_final_protected_floor_is_exact() -> None:
    module = load_vertical("research_discovery")
    assert module.PROTECTED_ITEM_IDS == frozenset({
        "decide.package-valid",
        "decide.zero-or-one",
        "decide.dual-lane",
        "decide.handoff-valid",
        "decide.claim-ceiling",
    })
    declared = {item.id for items in vertical_checklist_items(module).values() for item in items}
    assert module.PROTECTED_ITEM_IDS <= declared


def test_research_discovery_checklists_route_reviewers_to_canonical_lane_files() -> None:
    module = load_vertical("research_discovery")
    lane_hints = " ".join(
        item.evidence_hint
        for stage in ("probe", "decide")
        for item in vertical_checklist_items(module)[stage]
        if item.id in {
            "probe.preregistered-lanes",
            "probe.execution-evidence-separated",
            "decide.dual-lane",
        }
    )
    assert "THEORY_EVIDENCE.json" in lane_hints
    assert "APPLICATION_EVIDENCE.json" in lane_hints
    assert "PROBE.json" not in lane_hints


def test_research_discovery_roles_and_skills_are_complete() -> None:
    module = load_vertical("research_discovery")
    for role in ("manager", "planner", "engineer", "reviewer", "scientist_create", "scientist"):
        assert "discovery" in vertical_role_banner(module, role).lower()
    assert set(dict(iter_vertical_skill_texts("research_discovery"))) == EXPECTED_SKILLS


def test_research_discovery_persistence_seeds_frame(tmp_path: Path) -> None:
    persist_vertical(tmp_path, "research_discovery")
    assert (tmp_path / "research/PIPELINE_STATE.json").read_text(encoding="utf-8").find('"current_stage": "frame"') >= 0


def test_research_discovery_roles_shape_dynamic_portfolio_continuation() -> None:
    module = load_vertical("research_discovery")
    manager = vertical_role_banner(module, "manager")
    planner = vertical_role_banner(module, "planner")
    engineer = vertical_role_banner(module, "engineer")
    reviewer = vertical_role_banner(module, "reviewer")

    assert "Seed Project" in manager and "AUTO_EXPANSION.json" in manager
    assert "local branch" in manager and "project completion" in manager
    assert "near" in planner and "far" in planner and "siblings" in planner
    assert "Rejection Capsule" in engineer and "theory_transfer" in engineer
    assert "five active" in reviewer and "relabel" in reviewer
