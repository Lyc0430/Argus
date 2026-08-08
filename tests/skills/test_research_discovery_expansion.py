from __future__ import annotations

import json
from pathlib import Path

from argus_skill.life.memory import Backlog, BacklogItem
from argus_skill.verticals.research_discovery import expansion


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _project(
    root: Path,
    *,
    decision: str = "no_bet",
    basis: str = "pre_probe_gate",
    gates: list[str] | None = None,
    active: int = 0,
) -> Path:
    discovery = root / "research" / "discovery"
    refs: list[str] = []
    for index in range(max(1, active)):
        bet_id = f"B{index + 1}"
        ref = f"research/discovery/bets/{bet_id}/BET.json"
        refs.append(ref)
        _write_json(
            root / ref,
            {
                "id": bet_id,
                "revision": 1,
                "candidate_state": "probe" if index < active else "park",
                "candidate_premise": "A bounded policy transport identifies value.",
                "theory_anchor": {"binding_premise": "Transport preserves ordering."},
                "application_test": {"binding_premise": "The policy reduces bad actions."},
                "next_uncertainty": "Value and influence may diverge.",
            },
        )
        _write_json(
            root / ref.replace("BET.json", "THEORY_EVIDENCE.json"),
            {
                "execution_status": "blocked" if basis == "blocked_probe" else "completed",
                "failure_class": "dependency" if basis == "blocked_probe" else "theoretical",
                "idea_status": "untested" if basis == "blocked_probe" else "inconclusive",
            },
        )
        _write_json(
            root / ref.replace("BET.json", "APPLICATION_EVIDENCE.json"),
            {
                "execution_status": "completed",
                "failure_class": "none",
                "idea_status": "inconclusive" if decision == "paused" else "supported",
            },
        )
    _write_json(
        discovery / "PORTFOLIO.json",
        {
            "schema_version": 1,
            "objective": "Discover a safe memory-to-action control method.",
            "bet_refs": refs,
        },
    )
    failed = gates
    if failed is None:
        failed = {
            "pre_probe_gate": ["nearest_work"],
            "completed_probe": ["theory_probe"],
            "blocked_probe": ["theory_probe"],
        }[basis]
    _write_json(
        discovery / "DECISION.json",
        {
            "schema_version": 1,
            "decision": decision,
            "recommended_bet_id": "B1" if decision == "recommended" else None,
            "selection_rationale": "Current bounded verdict.",
            "eligibility": [
                {
                    "bet_id": "B1",
                    "eligible": decision == "recommended",
                    "decision_basis": "eligible" if decision == "recommended" else basis,
                    "failed_gates": [] if decision == "recommended" else failed,
                }
            ],
            "bindings": [{"bet_id": "B1", "bet_revision": 1}],
        },
    )
    return root


def _valid(monkeypatch, *, paused: bool = False) -> None:
    findings = ["terminal_paused:paused discovery decisions are non-terminal"] if paused else []
    monkeypatch.setattr(expansion, "validate_package", lambda _root: list(findings))


def test_initialize_seed_project_is_idempotent_and_preserves_first_objective(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    first = expansion.initialize_seed_project(root, project_id="seed-a")
    portfolio = json.loads(
        (root / "research/discovery/PORTFOLIO.json").read_text(encoding="utf-8")
    )
    portfolio["objective"] = "A later relabel must not replace the seed."
    _write_json(root / "research/discovery/PORTFOLIO.json", portfolio)
    second = expansion.initialize_seed_project(root, project_id="seed-a")

    assert second == first
    assert first["initialization_point"].startswith("Discover a safe")
    assert first["policy"] == {
        "enabled": True,
        "automation": "full",
        "max_active_bets": 5,
        "stagnation_threshold": 2,
        "branch_modes": ["near", "far"],
        "max_expansion_events": 8,
        "max_repair_attempts": 2,
    }


def test_classify_routes_terminal_and_nonterminal_evidence(monkeypatch, tmp_path: Path) -> None:
    root = _project(tmp_path)
    state = expansion.initialize_seed_project(root, project_id="seed-a")
    _valid(monkeypatch)
    assert expansion.classify_current_outcome(root, state).kind == "novelty_collision"

    _project(root, basis="completed_probe", gates=["theory_probe"])
    assert expansion.classify_current_outcome(root, state).kind == "scientific_rejection"

    _project(root, decision="recommended")
    assert expansion.classify_current_outcome(root, state).kind == "eligible"

    _project(root, decision="paused", basis="blocked_probe")
    _valid(monkeypatch, paused=True)
    blocked = expansion.classify_current_outcome(root, state)
    assert blocked.kind == "execution_blocked"
    assert blocked.kind != "scientific_rejection"


def test_malformed_or_unsafe_package_is_invalid_and_enqueues_nothing(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    decision = root / "research/discovery/DECISION.json"
    decision.write_text("{", encoding="utf-8")
    state = expansion.initialize_seed_project(root, project_id="seed-a")
    backlog = Backlog(tmp_path / "backlog.jsonl")

    assert expansion.classify_current_outcome(root, state).kind == "invalid"
    assert expansion.reconcile_after_mission(
        project_root=root,
        state_root=tmp_path / "state",
        global_root=tmp_path / "global",
        backlog=backlog,
        outcome={},
    )["status"] == "invalid"
    assert backlog.all() == []


def test_no_bet_enqueues_one_immutable_near_far_request_and_keeps_siblings(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    _valid(monkeypatch)
    backlog = Backlog(tmp_path / "backlog.jsonl")
    sibling = backlog.add(BacklogItem.new(item_id="sibling", title="Sibling", objective="keep"))
    kwargs = {
        "project_root": root,
        "state_root": tmp_path / "state",
        "global_root": tmp_path / "global",
        "backlog": backlog,
        "outcome": {},
    }

    first = expansion.reconcile_after_mission(**kwargs)
    second = expansion.reconcile_after_mission(**kwargs)
    request = json.loads(Path(first["request_path"]).read_text(encoding="utf-8"))

    assert first["status"] == "enqueued"
    assert second["status"] == "already_processed"
    assert request["branch_modes"] == ["near", "far"]
    assert request["decision_sha256"]
    assert request["source_bet_ids"] == ["B1"]
    assert request["available_frontier_slots"] == 5
    assert [item.id for item in backlog.all()][0] == sibling.id
    assert len(backlog.all()) == 2


def test_stagnation_redesigns_once_then_expands_on_distinct_second_result(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _project(tmp_path, decision="paused", basis="completed_probe")
    _valid(monkeypatch, paused=True)
    backlog = Backlog(tmp_path / "backlog.jsonl")
    kwargs = {
        "project_root": root,
        "state_root": tmp_path / "state",
        "global_root": tmp_path / "global",
        "backlog": backlog,
        "outcome": {},
    }

    first = expansion.reconcile_after_mission(**kwargs)
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["selection_rationale"] = "A second independent no-information result."
    _write_json(decision_path, decision)
    second = expansion.reconcile_after_mission(**kwargs)

    assert first["action"] == "probe_redesign"
    assert second["action"] == "derive_near_far"
    assert len(backlog.all()) == 2


def test_blocked_probe_gets_bounded_repair_and_never_derivation(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _project(tmp_path, decision="paused", basis="blocked_probe")
    _valid(monkeypatch, paused=True)
    backlog = Backlog(tmp_path / "backlog.jsonl")
    result = expansion.reconcile_after_mission(
        project_root=root,
        state_root=tmp_path / "state",
        global_root=tmp_path / "global",
        backlog=backlog,
        outcome={},
    )

    assert result["action"] == "repair_probe"
    assert "derive" not in backlog.all()[0].node_key
    assert "Do not create a new Research Bet" in backlog.all()[0].objective


def test_frontier_and_expansion_ceiling_stop_runaway_branching(monkeypatch, tmp_path: Path) -> None:
    root = _project(tmp_path, active=6)
    _valid(monkeypatch)
    backlog = Backlog(tmp_path / "backlog.jsonl")
    kwargs = {
        "project_root": root,
        "state_root": tmp_path / "state",
        "global_root": tmp_path / "global",
        "backlog": backlog,
        "outcome": {},
    }
    assert expansion.reconcile_after_mission(**kwargs)["status"] == "frontier_invalid"
    assert backlog.all() == []

    root = _project(root, active=0)
    state = expansion.initialize_seed_project(root, project_id="seed-a")
    state["requests"] = {
        f"old-{index}": {"action": "derive_near_far", "status": "completed"}
        for index in range(8)
    }
    _write_json(root / "research/discovery/AUTO_EXPANSION.json", state)
    assert expansion.reconcile_after_mission(**kwargs)["status"] == "frontier_exhausted"
    assert len(backlog.all()) == 0


def test_changed_decision_imports_exact_capsule_into_global_graph(monkeypatch, tmp_path: Path) -> None:
    root = _project(tmp_path)
    _valid(monkeypatch)
    backlog = Backlog(tmp_path / "backlog.jsonl")
    kwargs = {
        "project_root": root,
        "state_root": tmp_path / "state",
        "global_root": tmp_path / "global",
        "backlog": backlog,
        "outcome": {},
    }
    first = expansion.reconcile_after_mission(**kwargs)
    request = json.loads(Path(first["request_path"]).read_text(encoding="utf-8"))
    capsule_path = root / "research/discovery/rejections" / f"{request['event_id']}.json"
    _write_json(
        capsule_path,
        {
            "schema_version": 1,
            "event_id": request["event_id"],
            "source_bet_ids": ["B1"],
            "source_decision_sha256": request["decision_sha256"],
            "failure_class": "novelty_collision",
            "killed_premise": "The nearest-work delta was not distinct.",
            "survivors": ["The application problem remains open."],
            "forbidden_region": ["cosmetic relabeling"],
            "open_tension": "Influence and value still diverge.",
            "mutation_demand": "Change mechanism, estimand, or prediction.",
            "structure_tags": ["identifiability", "memory-control"],
            "artifact_refs": ["research/discovery/DECISION.json"],
        },
    )
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["selection_rationale"] = "A changed canonical decision."
    _write_json(decision_path, decision)

    expansion.reconcile_after_mission(**kwargs)
    graph = tmp_path / "global" / "research" / "experience_graph.jsonl"
    assert request["event_id"] in graph.read_text(encoding="utf-8")


def test_restart_reuses_immutable_request_when_global_experience_changes(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _project(tmp_path / "project")
    _valid(monkeypatch)
    backlog = Backlog(tmp_path / "backlog.jsonl")
    kwargs = {
        "project_root": root,
        "state_root": tmp_path / "state",
        "global_root": tmp_path / "global",
        "backlog": backlog,
        "outcome": {},
    }
    first = expansion.reconcile_after_mission(**kwargs)
    request_path = Path(first["request_path"])
    frozen = request_path.read_bytes()
    state_path = root / "research/discovery/AUTO_EXPANSION.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["processed_decisions"] = []
    state["requests"] = {}
    _write_json(state_path, state)

    from argus_skill.verticals.research_discovery.experience_graph import (
        ResearchExperienceGraph,
    )

    ResearchExperienceGraph(
        tmp_path / "global/research/experience_graph.jsonl"
    ).append(
        {
            "schema_version": 1,
            "event_id": "evt-prior",
            "source_bet_ids": ["B0"],
            "source_decision_sha256": "a" * 64,
            "failure_class": "scientific_rejection",
            "killed_premise": "Local influence identified value.",
            "survivors": ["The control problem remains."],
            "forbidden_region": ["unidentified transport"],
            "open_tension": "Value and influence diverge.",
            "mutation_demand": "Change the estimand.",
            "structure_tags": ["identifiability"],
            "artifact_refs": ["research/discovery/DECISION.json"],
        },
        source_project_id="other-project",
    )

    restarted = expansion.reconcile_after_mission(**kwargs)
    assert restarted["status"] == "enqueued"
    assert request_path.read_bytes() == frozen
    assert len(backlog.all()) == 1


def test_symlinked_discovery_parent_is_rejected_before_controller_write(
    tmp_path: Path,
) -> None:
    external = _project(tmp_path / "external") / "research/discovery"
    root = tmp_path / "project"
    (root / "research").mkdir(parents=True)
    (root / "research/discovery").symlink_to(external, target_is_directory=True)

    result = expansion.reconcile_after_mission(
        project_root=root,
        state_root=tmp_path / "state",
        global_root=tmp_path / "global",
        backlog=Backlog(tmp_path / "backlog.jsonl"),
        outcome={},
    )

    assert result["status"] == "invalid"
    assert not (external / "AUTO_EXPANSION.json").exists()


def test_blocked_probe_repair_attempts_are_bounded_across_decisions(
    monkeypatch, tmp_path: Path,
) -> None:
    root = _project(tmp_path, decision="paused", basis="blocked_probe")
    _valid(monkeypatch, paused=True)
    backlog = Backlog(tmp_path / "backlog.jsonl")
    kwargs = {
        "project_root": root,
        "state_root": tmp_path / "state",
        "global_root": tmp_path / "global",
        "backlog": backlog,
        "outcome": {},
    }

    assert expansion.reconcile_after_mission(**kwargs)["action"] == "repair_probe"
    decision_path = root / "research/discovery/DECISION.json"
    for index in (2, 3):
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        decision["selection_rationale"] = f"Blocked observation {index}."
        _write_json(decision_path, decision)
        result = expansion.reconcile_after_mission(**kwargs)

    assert result["status"] == "repair_exhausted"
    assert len(backlog.all()) == 2


def test_frontier_exhaustion_does_not_hide_an_unresolved_request(tmp_path: Path) -> None:
    root = _project(tmp_path)
    state = expansion.initialize_seed_project(root, project_id="seed-a")
    state["status"] = "frontier_exhausted"
    state["requests"] = {"evt-a": {"status": "pending"}}
    _write_json(root / "research/discovery/AUTO_EXPANSION.json", state)

    assert expansion.automatic_expansion_issue(root).endswith(
        "automatic_expansion_pending"
    )
