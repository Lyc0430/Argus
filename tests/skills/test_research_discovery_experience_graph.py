from __future__ import annotations

import json
from pathlib import Path

from argus_skill.verticals.research_discovery.experience_graph import (
    ResearchExperienceGraph,
    validate_capsule,
)


def _capsule(
    event_id: str,
    *,
    tension: str = "Normative value and realized influence can diverge.",
    tags: list[str] | None = None,
    refs: list[str] | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "event_id": event_id,
        "source_bet_ids": ["B1"],
        "source_decision_sha256": "a" * 64,
        "failure_class": "scientific_rejection",
        "killed_premise": "The local policy shift identifies utility.",
        "survivors": ["The application still needs safe memory control."],
        "forbidden_region": ["unidentified action-shift heuristic"],
        "open_tension": tension,
        "mutation_demand": "Change the estimand or identification design.",
        "structure_tags": tags or ["identifiability", "policy-transport"],
        "artifact_refs": refs or ["research/discovery/DECISION.json"],
    }


def test_capsule_validation_is_total_and_requires_the_exact_semantic_fields() -> None:
    assert validate_capsule(_capsule("evt-a")) == ()

    missing = _capsule("evt-a")
    missing.pop("open_tension")
    assert any("open_tension" in error for error in validate_capsule(missing))

    malformed = _capsule("evt-a")
    malformed["structure_tags"] = {"not": "a list"}
    assert any("structure_tags" in error for error in validate_capsule(malformed))

    assert any(
        "expected event" in error
        for error in validate_capsule(
            _capsule("evt-a"), expected_event_id="evt-b"
        )
    )


def test_graph_append_is_idempotent_and_corrupt_rows_fail_soft(
    tmp_path: Path,
) -> None:
    path = tmp_path / "research_experience_graph.jsonl"
    graph = ResearchExperienceGraph(path)
    capsule = _capsule("evt-a")

    first_id = graph.append(capsule, source_project_id="project-a")
    second_id = graph.append(capsule, source_project_id="project-a")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")
        handle.write(json.dumps({"record_type": "unknown"}) + "\n")

    assert first_id == second_id
    rows = graph.recent()
    assert len(rows) == 1
    assert rows[0]["capsule_id"] == first_id
    assert rows[0]["source_project_id"] == "project-a"


def test_import_rejects_symlink_and_accepts_exact_regular_capsule(
    tmp_path: Path,
) -> None:
    graph = ResearchExperienceGraph(tmp_path / "graph.jsonl")
    source = tmp_path / "capsule.json"
    source.write_text(json.dumps(_capsule("evt-a")), encoding="utf-8")
    symlink = tmp_path / "linked.json"
    symlink.symlink_to(source)

    assert graph.import_capsule(
        symlink,
        expected_event_id="evt-a",
        source_project_id="project-a",
    ) is None
    capsule_id = graph.import_capsule(
        source,
        expected_event_id="evt-a",
        source_project_id="project-a",
    )

    assert capsule_id
    assert len(graph.recent()) == 1


def test_retrieval_mixes_near_structural_and_cross_project_far_channels(
    tmp_path: Path,
) -> None:
    graph = ResearchExperienceGraph(tmp_path / "graph.jsonl")
    graph.append(
        _capsule(
            "evt-near",
            tension="Memory control policy confuses action influence with value.",
            tags=["memory", "control", "identifiability"],
        ),
        source_project_id="current-project",
    )
    graph.append(
        _capsule(
            "evt-structural",
            tension="A measured transport can diverge from normative value.",
            tags=["identifiability", "transport", "intervention"],
        ),
        source_project_id="causal-project",
    )
    graph.append(
        _capsule(
            "evt-far",
            tension="A population adapts to stale environmental signals.",
            tags=["adaptation", "stale-state", "selection"],
        ),
        source_project_id="ecology-project",
    )
    graph.append(
        _capsule(
            "evt-noise",
            tension="Typography spacing is inconsistent.",
            tags=["font", "layout"],
        ),
        source_project_id="design-project",
    )

    hits = graph.retrieve(
        "post-retrieval memory control policy",
        open_tension="normative value and realized transport diverge",
        structure_tags=["identifiability", "adaptation"],
        current_project_id="current-project",
        max_entries=3,
    )

    assert [hit.channel for hit in hits] == ["near", "structural", "far"]
    assert hits[0].capsule["event_id"] == "evt-near"
    assert hits[1].capsule["event_id"] == "evt-structural"
    assert hits[2].capsule["source_project_id"] != "current-project"
    assert hits[2].capsule["event_id"] != "evt-noise"


def test_retrieval_never_opens_lazy_artifact_refs(
    tmp_path: Path, monkeypatch,
) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    graph = ResearchExperienceGraph(tmp_path / "graph.jsonl")
    graph.append(
        _capsule("evt-a", refs=[str(raw_dir)]),
        source_project_id="project-a",
    )
    original_iterdir = Path.iterdir

    def guarded_iterdir(path: Path):
        if path == raw_dir:
            raise AssertionError("artifact reference was traversed")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", guarded_iterdir)

    assert graph.retrieve("memory control", max_entries=1)
