from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from argus_skill.verticals.research_discovery.evidence import (
    completion_issue,
    validate_package,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _premise_sha(bet: dict, lane: str) -> str:
    anchor_field = "theory_anchor" if lane == "theory" else "application_test"
    material = {
        "bet_id": bet["id"],
        "bet_revision": bet["revision"],
        "candidate_premise": bet["candidate_premise"],
        "lane": lane,
        "lane_anchor": bet[anchor_field],
        "bridge": bet["bridge"],
    }
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def valid_pre_probe_gates(*, failed: str | None = None) -> dict:
    rationales = {
        "application_anchor": "The real decision and baseline are concrete.",
        "theory_anchor": "The binding theory premise is precise enough to probe.",
        "bridge": "The supported bridge changes the application decision.",
        "nearest_work": "The searched delta remains distinct on its stated axis.",
    }
    return {
        gate: {
            "status": "fail" if gate == failed else "pass",
            "rationale": rationales[gate],
        }
        for gate in (
            "application_anchor",
            "theory_anchor",
            "bridge",
            "nearest_work",
        )
    }


def valid_bet(*, candidate_state: str = "select") -> dict:
    return {
        "schema_version": 1,
        "id": "B1",
        "revision": 1,
        "title": "Mechanism-aware triage",
        "candidate_state": candidate_state,
        "candidate_premise": "A formal uncertainty bound improves triage decisions.",
        "problem_anchor": {
            "stakeholder": "Clinical triage lead",
            "setting_and_decision": "Urgent-care escalation decisions",
            "baseline": "Rule-based escalation",
            "observed_failure": "The rule over-escalates ambiguous cases.",
            "provenance": "Local audit, 2026-08-01",
        },
        "theory_anchor": {
            "binding_premise": "Interval width changes the threshold ordering.",
            "objects": "posterior interval and threshold",
            "assumptions_scope": "calibrated scores on the stated cohort",
            "mechanism": "The interval distinguishes uncertain from high-risk cases.",
            "prediction": "Bound-aware triage reduces avoidable escalation.",
            "falsifier": "A counterexample reverses the threshold ordering.",
            "status": "conjectured",
        },
        "bridge": {
            "direction": "theory_to_application",
            "variable_mappings": [
                {"theory": "posterior interval", "application": "triage confidence"}
            ],
            "dependency_claim": "The escalation threshold changes with the interval width.",
            "observable_prediction": "Interval-aware triage improves calibration at equal recall.",
            "no_garnish_counterfactual": "Without the interval, the threshold cannot adapt to uncertainty.",
            "status": "supported",
        },
        "novelty": {
            "status": "distinct_on_searched_axis",
            "search_date": "2026-08-01",
            "query_summary": "uncertainty intervals clinical triage calibration",
            "nearest_verified_work": "doi:10.1000/example",
            "delta_axis": "interval-derived triage threshold",
            "dangerous_overlap": "Confidence-score triage without the interval mechanism",
        },
        "pre_probe_gates": valid_pre_probe_gates(),
        "application_test": {
            "binding_premise": "Interval-aware triage improves the stated metric.",
            "intervention": "Replace the fixed threshold with the interval-aware threshold.",
            "baseline": "Rule-based fixed threshold",
            "decision_metric": "avoidable escalations at matched recall",
            "evaluator_identity": "held-out audit evaluator v1",
            "scope": "Retrospective urgent-care records",
            "falsifier": "No calibration improvement at matched recall.",
            "proxy_fidelity": "Retrospective records retain the decision inputs.",
            "external_validity_ceiling": "retrospective",
            "external_validity_level": "retrospective",
            "risks": ["clinical use remains out of scope"],
        },
        "kill_criteria": "No improvement on the preregistered metric.",
        "limitations": ["Retrospective evidence only"],
        "estimated_cost": "Two analyst days",
        "next_uncertainty": "Prospective calibration may differ.",
    }


def valid_theory_evidence(bet: dict | None = None) -> dict:
    current_bet = bet or valid_bet()
    return {
        "schema_version": 1,
        "bet_id": "B1",
        "bet_revision": 1,
        "premise_version": "B1-r1",
        "premise_sha256": _premise_sha(current_bet, "theory"),
        "preregistered_question": "Does the interval preserve threshold ordering?",
        "method": "finite counterexample search",
        "falsifier": "A reversed ordering in the finite check",
        "stop_rule": "Stop after the preregistered grid is exhausted.",
        "execution_status": "completed",
        "failure_class": "none",
        "idea_status": "supported",
        "summary": "The finite check preserved the ordering.",
        "evidence": "All 64 preregistered cases preserved the ordering.",
        "raw_artifact_refs": ["research/discovery/bets/B1/theory.txt"],
        "scope_limits": "Finite grid only.",
        "timestamp": "2026-08-02T00:00:00Z",
        "premise": "Interval width changes the threshold ordering.",
        "method_identity": "finite-grid-v1",
        "witness_or_derivation": "research/discovery/bets/B1/theory.txt",
    }


def valid_application_evidence(bet: dict | None = None) -> dict:
    current_bet = bet or valid_bet()
    return {
        "schema_version": 1,
        "bet_id": "B1",
        "bet_revision": 1,
        "premise_version": "B1-r1",
        "premise_sha256": _premise_sha(current_bet, "application"),
        "preregistered_question": "Does interval-aware triage reduce avoidable escalation?",
        "method": "held-out retrospective comparison",
        "falsifier": "No improvement at matched recall",
        "stop_rule": "Stop after the held-out comparison.",
        "execution_status": "completed",
        "failure_class": "none",
        "idea_status": "supported",
        "summary": "The held-out comparison met the decision metric.",
        "evidence": "Avoidable escalations decreased at matched recall.",
        "raw_artifact_refs": ["research/discovery/bets/B1/application.txt"],
        "scope_limits": "Retrospective setting only.",
        "timestamp": "2026-08-03T00:00:00Z",
        "premise": "Interval-aware triage improves the stated metric.",
        "evaluator_identity": "held-out audit evaluator v1",
        "comparison_identity": "rule-based fixed threshold",
        "claim_ceiling": "retrospective",
        "evidence_level": "retrospective",
    }


def valid_portfolio() -> dict:
    return {
        "schema_version": 1,
        "objective": "Find a bounded theory-application mechanism.",
        "focus_domain": "clinical triage",
        "budget": {
            "summary": "Two analyst days",
            "stop_condition": "Stop after the two preregistered probes.",
        },
        "bet_refs": ["research/discovery/bets/B1/BET.json"],
        "search_summary": {
            "as_of": "2026-08-01",
            "sources": ["local audit", "literature search"],
            "queries": ["uncertainty intervals clinical triage calibration"],
        },
    }


def valid_decision(decision: str, bindings: list[dict]) -> dict:
    recommended = decision == "recommended"
    return {
        "schema_version": 1,
        "decision": decision,
        "recommended_bet_id": "B1" if recommended else None,
        "eligibility": [
            {
                "bet_id": "B1",
                "eligible": recommended,
                "decision_basis": "eligible" if recommended else "pre_probe_gate",
                "failed_gates": [] if recommended else ["nearest_work"],
            }
        ],
        "ordering": ["B1"],
        "selection_rationale": "The two probes support the bounded recommendation." if recommended else "The candidate is parked with a grounded rationale.",
        "residual_risks": ["Retrospective evidence ceiling"],
        "limited_by_budget": False,
        "bindings": bindings,
    }


def valid_handoff(binding: dict) -> dict:
    return {
        "schema_version": 1,
        **binding,
        "next_vertical": "research",
        "binding_uncertainty": "Prospective calibration remains unknown.",
        "objective": "Test prospective calibration without clinical deployment.",
        "acceptance_check": "Preregistered prospective evaluation completes.",
        "non_goals": ["clinical deployment"],
        "evidence_references": ["research/discovery/bets/B1/application.txt"],
        "return_condition": "Return if the prospective comparison is inconclusive.",
        "claim_ceiling": "Discovery supports a retrospective candidate only, not clinical effectiveness.",
    }


def _valid_project(root: Path, *, decision: str = "recommended") -> Path:
    discovery = root / "research" / "discovery"
    discovery.mkdir(parents=True)
    (discovery / "BRIEF.md").write_text(
        "# Discovery brief\n\nFind a theory-application mechanism inside the stated budget.\n",
        encoding="utf-8",
    )
    bet_path = discovery / "bets" / "B1" / "BET.json"
    theory_path = bet_path.with_name("THEORY_EVIDENCE.json")
    application_path = bet_path.with_name("APPLICATION_EVIDENCE.json")
    bet = valid_bet(candidate_state="select" if decision == "recommended" else "park")
    if decision != "recommended":
        bet["novelty"]["status"] = "overlap"
        bet["pre_probe_gates"] = valid_pre_probe_gates(failed="nearest_work")
    _write_json(bet_path, bet)
    _write_json(theory_path, valid_theory_evidence(bet))
    _write_json(application_path, valid_application_evidence(bet))
    theory_path.with_name("theory.txt").write_text("finite check", encoding="utf-8")
    application_path.with_name("application.txt").write_text("comparison", encoding="utf-8")
    _write_json(discovery / "PORTFOLIO.json", valid_portfolio())
    bindings = [{
        "bet_id": "B1",
        "bet_revision": 1,
        "bet_sha256": _sha(bet_path),
        "theory_evidence_sha256": _sha(theory_path),
        "application_evidence_sha256": _sha(application_path),
    }]
    _write_json(discovery / "DECISION.json", valid_decision(decision, bindings))
    if decision == "recommended":
        _write_json(discovery / "HANDOFF.json", valid_handoff(bindings[0]))
    return root


def _refresh_bindings(root: Path) -> None:
    discovery = root / "research" / "discovery"
    portfolio = json.loads((discovery / "PORTFOLIO.json").read_text(encoding="utf-8"))
    bindings = []
    for ref in portfolio["bet_refs"]:
        bet_path = root / ref
        bet = json.loads(bet_path.read_text(encoding="utf-8"))
        bindings.append(
            {
                "bet_id": bet["id"],
                "bet_revision": bet["revision"],
                "bet_sha256": _sha(bet_path),
                "theory_evidence_sha256": _sha(
                    bet_path.with_name("THEORY_EVIDENCE.json")
                ),
                "application_evidence_sha256": _sha(
                    bet_path.with_name("APPLICATION_EVIDENCE.json")
                ),
            }
        )
    decision_path = discovery / "DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["bindings"] = bindings
    _write_json(decision_path, decision)
    handoff_path = discovery / "HANDOFF.json"
    if decision["decision"] == "recommended" and handoff_path.is_file():
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        handoff.update(bindings[0])
        _write_json(handoff_path, handoff)


def _refresh_premise_digests(root: Path) -> None:
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    for lane, filename in (
        ("theory", "THEORY_EVIDENCE.json"),
        ("application", "APPLICATION_EVIDENCE.json"),
    ):
        evidence_path = bet_path.with_name(filename)
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["premise_sha256"] = _premise_sha(bet, lane)
        _write_json(evidence_path, evidence)


def _add_ineligible_killed_bet(root: Path) -> None:
    discovery = root / "research" / "discovery"
    bet_path = discovery / "bets" / "B2" / "BET.json"
    theory_path = bet_path.with_name("THEORY_EVIDENCE.json")
    application_path = bet_path.with_name("APPLICATION_EVIDENCE.json")
    bet = valid_bet(candidate_state="kill")
    bet.update(id="B2", title="Rejected alternative")
    bet["novelty"]["status"] = "overlap"
    bet["pre_probe_gates"] = valid_pre_probe_gates(failed="nearest_work")
    theory = valid_theory_evidence(bet)
    theory.update(
        bet_id="B2",
        premise_version="B2-r1",
        premise_sha256=_premise_sha(bet, "theory"),
        raw_artifact_refs=["research/discovery/bets/B2/theory.txt"],
        witness_or_derivation="research/discovery/bets/B2/theory.txt",
    )
    application = valid_application_evidence(bet)
    application.update(
        bet_id="B2",
        premise_version="B2-r1",
        premise_sha256=_premise_sha(bet, "application"),
        raw_artifact_refs=["research/discovery/bets/B2/application.txt"],
    )
    _write_json(bet_path, bet)
    _write_json(theory_path, theory)
    _write_json(application_path, application)
    theory_path.with_name("theory.txt").write_text("finite check", encoding="utf-8")
    application_path.with_name("application.txt").write_text("comparison", encoding="utf-8")

    portfolio_path = discovery / "PORTFOLIO.json"
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
    portfolio["bet_refs"].append("research/discovery/bets/B2/BET.json")
    _write_json(portfolio_path, portfolio)

    decision_path = discovery / "DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"].append(
        {
            "bet_id": "B2",
            "eligible": False,
            "decision_basis": "pre_probe_gate",
            "failed_gates": ["nearest_work"],
        }
    )
    decision["ordering"].append("B2")
    decision["bindings"].append(
        {
            "bet_id": "B2",
            "bet_revision": 1,
            "bet_sha256": _sha(bet_path),
            "theory_evidence_sha256": _sha(theory_path),
            "application_evidence_sha256": _sha(application_path),
        }
    )
    _write_json(decision_path, decision)


def test_valid_recommended_package_passes(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    assert validate_package(root) == []
    assert completion_issue(root) == ""


def test_valid_no_bet_package_passes_without_handoff(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    assert not (root / "research/discovery/HANDOFF.json").exists()
    assert validate_package(root) == []


def test_valid_pre_probe_gate_can_ground_no_bet(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    decision = json.loads(
        (root / "research/discovery/DECISION.json").read_text(encoding="utf-8")
    )
    assert decision["eligibility"] == [
        {
            "bet_id": "B1",
            "eligible": False,
            "decision_basis": "pre_probe_gate",
            "failed_gates": ["nearest_work"],
        }
    ]
    assert validate_package(root) == []


def test_pre_probe_basis_cannot_mix_probe_gate_to_hide_blocked_lane(
    tmp_path: Path,
) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["novelty"]["status"] = "overlap"
    bet["pre_probe_gates"] = valid_pre_probe_gates(failed="nearest_work")
    _write_json(bet_path, bet)

    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][0].update(
        decision_basis="pre_probe_gate",
        failed_gates=["nearest_work", "theory_probe"],
    )
    _write_json(decision_path, decision)

    theory_path = bet_path.with_name("THEORY_EVIDENCE.json")
    theory = json.loads(theory_path.read_text(encoding="utf-8"))
    theory.update(
        execution_status="blocked",
        failure_class="dependency",
        idea_status="untested",
    )
    _write_json(theory_path, theory)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_decision:") and "cannot mix" in error
        for error in validate_package(root)
    )


def test_pre_probe_failed_gates_must_equal_current_bet_failures(
    tmp_path: Path,
) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["novelty"]["status"] = "overlap"
    bet["pre_probe_gates"] = valid_pre_probe_gates(failed="nearest_work")
    _write_json(bet_path, bet)
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][0]["failed_gates"] = ["bridge"]
    _write_json(decision_path, decision)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_decision:") and "current Bet" in error
        for error in validate_package(root)
    )


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_pre_probe_gates_require_exact_four_keys(
    tmp_path: Path,
    mutation: str,
) -> None:
    root = _valid_project(tmp_path)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    if mutation == "missing":
        bet["pre_probe_gates"].pop("nearest_work")
    else:
        bet["pre_probe_gates"]["theory_probe"] = {
            "status": "pass",
            "rationale": "The theory probe completed.",
        }
    _write_json(bet_path, bet)
    _refresh_bindings(root)

    errors = validate_package(root)
    assert any(
        error.startswith("invalid_bet:B1:") and "exactly" in error
        for error in errors
    )
    assert any(
        error.startswith("invalid_decision:") and "pre-probe gates" in error
        for error in errors
    )


@pytest.mark.parametrize(
    ("mutation", "error_fragment"),
    [
        ({"nearest_work": {"status": "fail", "rationale": "Distinct work."}}, "nearest_work"),
        ({"bridge": {"status": "fail", "rationale": "Bridge failed."}}, "bridge"),
        ({"application_anchor": {"status": "maybe", "rationale": "Unknown."}}, "status"),
        ({"theory_anchor": {"status": "pass", "rationale": "REPLACE"}}, "rationale"),
    ],
)
def test_pre_probe_gate_rows_are_current_and_well_formed(
    tmp_path: Path,
    mutation: dict,
    error_fragment: str,
) -> None:
    root = _valid_project(tmp_path)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["pre_probe_gates"] = valid_pre_probe_gates()
    bet["pre_probe_gates"].update(mutation)
    _write_json(bet_path, bet)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_bet:B1:") and error_fragment in error
        for error in validate_package(root)
    )


@pytest.mark.parametrize("bad_status", [["pass"], {"value": "pass"}, None])
def test_malformed_pre_probe_status_returns_stable_invalid_bet(
    tmp_path: Path,
    bad_status: object,
) -> None:
    root = _valid_project(tmp_path)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["pre_probe_gates"]["application_anchor"]["status"] = bad_status
    _write_json(bet_path, bet)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_bet:B1:pre_probe_gates.application_anchor.status")
        for error in validate_package(root)
    )


@pytest.mark.parametrize(
    ("bridge_status", "gate_status"),
    [
        ("supported", "fail"),
        ("weak", "pass"),
        ("broken", "pass"),
        ("untested", "pass"),
        ("untested", "fail"),
    ],
)
def test_bridge_gate_result_matches_current_structured_bridge(
    tmp_path: Path,
    bridge_status: str,
    gate_status: str,
) -> None:
    root = _valid_project(tmp_path)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["bridge"]["status"] = bridge_status
    bet["pre_probe_gates"]["bridge"]["status"] = gate_status
    _write_json(bet_path, bet)
    _refresh_premise_digests(root)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_bet:B1:") and "pre_probe_gates.bridge" in error
        for error in validate_package(root)
    )


def test_distinct_nearest_work_requires_passing_pre_probe_gate(
    tmp_path: Path,
) -> None:
    root = _valid_project(tmp_path)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["pre_probe_gates"] = valid_pre_probe_gates(failed="nearest_work")
    _write_json(bet_path, bet)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_bet:B1:") and "nearest_work" in error
        for error in validate_package(root)
    )


def test_unresolved_nearest_work_requires_failing_pre_probe_gate(
    tmp_path: Path,
) -> None:
    root = _valid_project(tmp_path)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["novelty"]["status"] = "unresolved"
    bet["pre_probe_gates"] = valid_pre_probe_gates()
    _write_json(bet_path, bet)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_bet:B1:") and "nearest_work" in error
        for error in validate_package(root)
    )


@pytest.mark.parametrize("decision", ["recommended", "no_bet"])
def test_eligible_or_completed_probe_requires_all_pre_probe_gates_to_pass(
    tmp_path: Path,
    decision: str,
) -> None:
    root = _valid_project(tmp_path, decision=decision)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["bridge"]["status"] = "broken"
    bet["pre_probe_gates"] = valid_pre_probe_gates(failed="bridge")
    _write_json(bet_path, bet)
    decision_path = root / "research/discovery/DECISION.json"
    payload = json.loads(decision_path.read_text(encoding="utf-8"))
    if decision == "no_bet":
        payload["eligibility"][0].update(
            decision_basis="completed_probe",
            failed_gates=["theory_probe"],
        )
    _write_json(decision_path, payload)
    _refresh_premise_digests(root)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_decision:") and "pre-probe gates" in error
        for error in validate_package(root)
    )


def test_grounded_empty_portfolio_can_record_no_bet(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    portfolio = root / "research/discovery/PORTFOLIO.json"
    portfolio_payload = json.loads(portfolio.read_text(encoding="utf-8"))
    portfolio_payload["bet_refs"] = []
    _write_json(portfolio, portfolio_payload)
    decision = root / "research/discovery/DECISION.json"
    decision_payload = json.loads(decision.read_text(encoding="utf-8"))
    decision_payload.update(eligibility=[], ordering=[], bindings=[])
    _write_json(decision, decision_payload)
    assert validate_package(root) == []


def test_no_bet_rejects_an_eligible_candidate(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][0]["eligible"] = True
    _write_json(decision_path, decision)

    assert any(
        error.startswith("invalid_decision:") and "no_bet" in error
        for error in validate_package(root)
    )


def test_no_bet_rejects_arbitrary_free_text_failed_gate(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][0]["failed_gates"] = ["reviewer did not like it"]
    _write_json(decision_path, decision)

    assert any(
        error.startswith("invalid_decision:") and "failed_gates" in error
        for error in validate_package(root)
    )


@pytest.mark.parametrize(
    ("lane", "execution_status", "failure_class"),
    [
        ("theory", "blocked", "dependency"),
        ("application", "failed", "implementation"),
    ],
)
def test_no_bet_rejects_a_blocked_or_failed_finalist_probe(
    tmp_path: Path,
    lane: str,
    execution_status: str,
    failure_class: str,
) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][0].update(
        decision_basis="completed_probe",
        failed_gates=[f"{lane}_probe"],
    )
    _write_json(decision_path, decision)
    filename = "THEORY_EVIDENCE.json" if lane == "theory" else "APPLICATION_EVIDENCE.json"
    evidence_path = root / "research/discovery/bets/B1" / filename
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence.update(
        execution_status=execution_status,
        failure_class=failure_class,
        idea_status="inconclusive",
    )
    _write_json(evidence_path, evidence)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_decision:") and "paused" in error
        for error in validate_package(root)
    )


def test_no_bet_rejects_blocked_probe_decision_basis(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][0].update(
        decision_basis="blocked_probe",
        failed_gates=["theory_probe"],
    )
    _write_json(decision_path, decision)

    assert any(
        error.startswith("invalid_decision:") and "blocked_probe" in error
        for error in validate_package(root)
    )


@pytest.mark.parametrize(
    "failed_gates",
    [[], ["theory_probe", "nearest_work"]],
)
def test_blocked_probe_gate_shape_is_nonempty_and_probe_only(
    tmp_path: Path,
    failed_gates: list[str],
) -> None:
    root = _valid_project(tmp_path, decision="paused")
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][0].update(
        decision_basis="blocked_probe",
        failed_gates=failed_gates,
    )
    _write_json(decision_path, decision)
    theory_path = root / "research/discovery/bets/B1/THEORY_EVIDENCE.json"
    theory = json.loads(theory_path.read_text(encoding="utf-8"))
    theory.update(
        execution_status="blocked",
        failure_class="dependency",
        idea_status="untested",
    )
    _write_json(theory_path, theory)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_decision:")
        and "blocked_probe accepts only probe gates" in error
        for error in validate_package(root)
    )


def test_blocked_probe_requires_overall_paused_decision(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    _add_ineligible_killed_bet(root)
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][1].update(
        decision_basis="blocked_probe",
        failed_gates=["theory_probe"],
    )
    _write_json(decision_path, decision)
    theory_path = root / "research/discovery/bets/B2/THEORY_EVIDENCE.json"
    theory = json.loads(theory_path.read_text(encoding="utf-8"))
    theory.update(
        execution_status="blocked",
        failure_class="dependency",
        idea_status="untested",
    )
    _write_json(theory_path, theory)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_decision:")
        and "blocked_probe requires decision=paused" in error
        for error in validate_package(root)
    )


def test_blocked_probe_requires_every_named_probe_to_be_grounded(
    tmp_path: Path,
) -> None:
    root = _valid_project(tmp_path, decision="paused")
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][0].update(
        decision_basis="blocked_probe",
        failed_gates=["theory_probe", "application_probe"],
    )
    _write_json(decision_path, decision)
    theory_path = root / "research/discovery/bets/B1/THEORY_EVIDENCE.json"
    theory = json.loads(theory_path.read_text(encoding="utf-8"))
    theory.update(
        execution_status="blocked",
        failure_class="dependency",
        idea_status="untested",
    )
    _write_json(theory_path, theory)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_decision:")
        and "blocked_probe lacks a blocked or failed lane" in error
        for error in validate_package(root)
    )


def _make_completed_theory_refutation(root: Path) -> None:
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["candidate_state"] = "kill"
    bet["novelty"]["status"] = "distinct_on_searched_axis"
    bet["pre_probe_gates"] = valid_pre_probe_gates()
    _write_json(bet_path, bet)
    theory_path = bet_path.with_name("THEORY_EVIDENCE.json")
    theory = json.loads(theory_path.read_text(encoding="utf-8"))
    theory.update(
        execution_status="completed",
        failure_class="theoretical",
        idea_status="refuted",
        summary="A valid finite counterexample refuted the binding theory premise.",
        evidence="The recorded witness reverses the preregistered ordering.",
    )
    _write_json(theory_path, theory)
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][0].update(
        eligible=False,
        decision_basis="completed_probe",
        failed_gates=["theory_probe"],
    )
    _write_json(decision_path, decision)
    _refresh_bindings(root)


def test_completed_scientific_refutation_can_ground_no_bet(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    _make_completed_theory_refutation(root)
    assert validate_package(root) == []


def test_completed_probe_basis_cannot_mix_pre_probe_gate(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    _make_completed_theory_refutation(root)
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][0]["failed_gates"] = [
        "theory_probe",
        "nearest_work",
    ]
    _write_json(decision_path, decision)

    assert any(
        error.startswith("invalid_decision:")
        and "accepts only probe gates" in error
        for error in validate_package(root)
    )


def test_budget_limited_completed_refutation_can_ground_no_bet(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    _make_completed_theory_refutation(root)
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["limited_by_budget"] = True
    _write_json(decision_path, decision)
    assert validate_package(root) == []


def test_budget_limit_does_not_waive_a_blocked_finalist_probe(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision.update(limited_by_budget=True)
    decision["eligibility"][0].update(
        decision_basis="completed_probe",
        failed_gates=["application_probe"],
    )
    _write_json(decision_path, decision)
    application_path = root / "research/discovery/bets/B1/APPLICATION_EVIDENCE.json"
    application = json.loads(application_path.read_text(encoding="utf-8"))
    application.update(
        execution_status="blocked",
        failure_class="data_access",
        idea_status="untested",
    )
    _write_json(application_path, application)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_decision:") and "paused" in error
        for error in validate_package(root)
    )


def test_blocked_probe_is_a_coherent_nonterminal_paused_decision(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="paused")
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["eligibility"][0].update(
        decision_basis="blocked_probe",
        failed_gates=["theory_probe"],
    )
    _write_json(decision_path, decision)
    theory_path = root / "research/discovery/bets/B1/THEORY_EVIDENCE.json"
    theory = json.loads(theory_path.read_text(encoding="utf-8"))
    theory.update(
        execution_status="blocked",
        failure_class="dependency",
        idea_status="untested",
    )
    _write_json(theory_path, theory)
    _refresh_bindings(root)

    errors = validate_package(root)
    assert errors == ["terminal_paused:paused discovery decisions are non-terminal"]
    assert completion_issue(root) == "research_discovery:terminal_paused"


def test_stale_bet_digest_blocks_recommendation(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    bet = root / "research/discovery/bets/B1/BET.json"
    payload = json.loads(bet.read_text(encoding="utf-8"))
    payload["revision"] = 2
    _write_json(bet, payload)
    assert "stale_decision" in completion_issue(root)


def test_infrastructure_failure_cannot_refute_theory(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    path = root / "research/discovery/bets/B1/THEORY_EVIDENCE.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(execution_status="blocked", failure_class="dependency", idea_status="refuted")
    _write_json(path, payload)
    errors = validate_package(root)
    assert any("dependency" in error and "untested or inconclusive" in error for error in errors)


def test_prior_art_cannot_refute_application_premise(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    path = root / "research/discovery/bets/B1/APPLICATION_EVIDENCE.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(execution_status="completed", failure_class="prior_art", idea_status="refuted")
    _write_json(path, payload)
    assert any("prior_art" in error and "replanning" in error for error in validate_package(root))


@pytest.mark.parametrize("lane", ["theory", "application"])
@pytest.mark.parametrize("idea_status", ["supported", "refuted"])
def test_implementation_failure_cannot_be_conclusive_in_discovery_lanes(
    tmp_path: Path,
    lane: str,
    idea_status: str,
) -> None:
    root = _valid_project(tmp_path)
    filename = "THEORY_EVIDENCE.json" if lane == "theory" else "APPLICATION_EVIDENCE.json"
    path = root / "research/discovery/bets/B1" / filename
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(
        execution_status="completed",
        failure_class="implementation",
        idea_status=idea_status,
    )
    _write_json(path, payload)
    _refresh_bindings(root)

    code = "invalid_theory_evidence" if lane == "theory" else "invalid_application_evidence"
    assert any(
        error.startswith(f"{code}:")
        and "implementation" in error
        and "untested or inconclusive" in error
        for error in validate_package(root)
    )


@pytest.mark.parametrize(
    ("lane", "anchor_field", "filename", "error_code"),
    [
        (
            "theory",
            "theory_anchor",
            "THEORY_EVIDENCE.json",
            "invalid_theory_evidence",
        ),
        (
            "application",
            "application_test",
            "APPLICATION_EVIDENCE.json",
            "invalid_application_evidence",
        ),
    ],
)
def test_old_probe_cannot_be_relabelled_as_current_after_binding_premise_changes(
    tmp_path: Path,
    lane: str,
    anchor_field: str,
    filename: str,
    error_code: str,
) -> None:
    root = _valid_project(tmp_path)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["revision"] = 2
    bet[anchor_field]["binding_premise"] = f"Revision 2 {lane} binding premise."
    _write_json(bet_path, bet)
    lane_path = bet_path.with_name(filename)
    lane_record = json.loads(lane_path.read_text(encoding="utf-8"))
    lane_record.update(bet_revision=2, premise_version="B1-r2")
    _write_json(lane_path, lane_record)
    other_filename = (
        "APPLICATION_EVIDENCE.json"
        if filename == "THEORY_EVIDENCE.json"
        else "THEORY_EVIDENCE.json"
    )
    other_path = bet_path.with_name(other_filename)
    other_record = json.loads(other_path.read_text(encoding="utf-8"))
    other_record.update(bet_revision=2, premise_version="B1-r2")
    other_lane = "application" if lane == "theory" else "theory"
    other_record["premise_sha256"] = _premise_sha(bet, other_lane)
    _write_json(other_path, other_record)
    _refresh_bindings(root)

    assert any(
        error.startswith(f"{error_code}:B1:") and "premise" in error
        for error in validate_package(root)
    )


def test_candidate_premise_change_invalidates_both_lane_premise_digests(
    tmp_path: Path,
) -> None:
    root = _valid_project(tmp_path)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet.update(
        revision=2,
        candidate_premise="Revision 2 changes the load-bearing candidate premise.",
    )
    _write_json(bet_path, bet)
    for filename in ("THEORY_EVIDENCE.json", "APPLICATION_EVIDENCE.json"):
        lane_path = bet_path.with_name(filename)
        lane = json.loads(lane_path.read_text(encoding="utf-8"))
        lane.update(bet_revision=2, premise_version="B1-r2")
        _write_json(lane_path, lane)
    _refresh_bindings(root)

    errors = validate_package(root)
    assert any(
        error.startswith("invalid_theory_evidence:B1:") and "premise_sha256" in error
        for error in errors
    )
    assert any(
        error.startswith("invalid_application_evidence:B1:")
        and "premise_sha256" in error
        for error in errors
    )


def test_public_premise_digest_uses_canonical_bet_material() -> None:
    from argus_skill.verticals.research_discovery.evidence import premise_digest

    assert premise_digest(valid_bet(), lane="theory") == (
        "3edbf71ff7530c0b1928f4fb696464266d8c082bb687f3d031799bb2dfa32b5f"
    )
    assert premise_digest(valid_bet(), lane="application") == (
        "be66e58b9f81fe115dff2061a1223422bec138b7151ddb19a68e9b45115d54ab"
    )


def test_recommendation_rejects_decorative_bridge(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    path = root / "research/discovery/bets/B1/BET.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["bridge"]["no_garnish_counterfactual"] = "Removing the theory changes nothing."
    payload["bridge"]["status"] = "weak"
    _write_json(path, payload)
    assert any("bridge" in error for error in validate_package(root))


@pytest.mark.parametrize(
    "mapping",
    [
        {},
        {"application": "triage confidence"},
        {"theory": "posterior interval"},
        {"theory": "", "application": "triage confidence"},
        {"theory": "posterior interval", "application": ""},
        {"note": "shared vocabulary only"},
    ],
)
def test_bridge_mapping_requires_non_placeholder_theory_and_application(
    tmp_path: Path,
    mapping: dict,
) -> None:
    root = _valid_project(tmp_path)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["bridge"]["variable_mappings"] = [mapping]
    _write_json(bet_path, bet)
    _refresh_bindings(root)

    assert any(
        error.startswith("invalid_bet:B1:bridge.variable_mappings")
        for error in validate_package(root)
    )


def test_paused_decision_is_non_terminal(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="paused")
    assert completion_issue(root) == "research_discovery:terminal_paused"


def test_no_bet_rejects_stray_handoff(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    _write_json(root / "research/discovery/HANDOFF.json", valid_handoff({}))
    assert any("invalid_handoff" in error for error in validate_package(root))


def test_invalid_bet_id_is_rejected(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    portfolio = root / "research/discovery/PORTFOLIO.json"
    payload = json.loads(portfolio.read_text(encoding="utf-8"))
    payload["bet_refs"] = ["research/discovery/bets/BAD ID/BET.json"]
    _write_json(portfolio, payload)
    assert "invalid_portfolio" in completion_issue(root)


def test_path_escaping_bet_ref_is_rejected(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    portfolio = root / "research/discovery/PORTFOLIO.json"
    payload = json.loads(portfolio.read_text(encoding="utf-8"))
    payload["bet_refs"] = ["../outside/BET.json"]
    _write_json(portfolio, payload)
    assert any("unsafe" in error for error in validate_package(root))


def test_duplicate_bet_id_is_rejected(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    portfolio = root / "research/discovery/PORTFOLIO.json"
    payload = json.loads(portfolio.read_text(encoding="utf-8"))
    payload["bet_refs"].append(payload["bet_refs"][0])
    _write_json(portfolio, payload)
    assert any("duplicate bet ID" in error for error in validate_package(root))


def test_mismatched_evidence_revision_is_rejected(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    path = root / "research/discovery/bets/B1/THEORY_EVIDENCE.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["bet_revision"] = 2
    _write_json(path, payload)
    assert any("bet_revision" in error for error in validate_package(root))


def test_unresolved_novelty_blocks_recommendation(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    path = root / "research/discovery/bets/B1/BET.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["novelty"]["status"] = "unresolved"
    _write_json(path, payload)
    assert any("novelty delta is unresolved" in error for error in validate_package(root))


def test_unsupported_lane_blocks_recommendation(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    path = root / "research/discovery/bets/B1/APPLICATION_EVIDENCE.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["idea_status"] = "inconclusive"
    _write_json(path, payload)
    assert any("recommended premise is not supported" in error for error in validate_package(root))


def test_multiple_selected_candidates_block_recommendation(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    bet = root / "research/discovery/bets/B1/BET.json"
    payload = json.loads(bet.read_text(encoding="utf-8"))
    payload["candidate_state"] = "probe"
    _write_json(bet, payload)
    assert any("exactly one selected" in error for error in validate_package(root))


def test_recommendation_requires_handoff(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    (root / "research/discovery/HANDOFF.json").unlink()
    assert any("requires HANDOFF" in error for error in validate_package(root))


def test_invalid_next_vertical_is_rejected(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    handoff = root / "research/discovery/HANDOFF.json"
    payload = json.loads(handoff.read_text(encoding="utf-8"))
    payload["next_vertical"] = "publication"
    _write_json(handoff, payload)
    assert any("next_vertical is invalid" in error for error in validate_package(root))


def test_proxy_evidence_cannot_exceed_declared_ceiling(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    path = root / "research/discovery/bets/B1/APPLICATION_EVIDENCE.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["evidence_level"] = "production"
    _write_json(path, payload)
    _refresh_bindings(root)
    assert any("exceeds its declared" in error for error in validate_package(root))


def test_narrative_claim_ceiling_is_not_used_as_machine_enum(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    bet = json.loads(bet_path.read_text(encoding="utf-8"))
    bet["application_test"]["external_validity_ceiling"] = (
        "Retrospective urgent-care records only; no prospective clinical claim."
    )
    _write_json(bet_path, bet)
    application_path = bet_path.with_name("APPLICATION_EVIDENCE.json")
    application = json.loads(application_path.read_text(encoding="utf-8"))
    application["claim_ceiling"] = (
        "Observed retrospective comparison only, with no production effectiveness claim."
    )
    application["premise_sha256"] = _premise_sha(bet, "application")
    _write_json(application_path, application)
    theory_path = bet_path.with_name("THEORY_EVIDENCE.json")
    theory = json.loads(theory_path.read_text(encoding="utf-8"))
    theory["premise_sha256"] = _premise_sha(bet, "theory")
    _write_json(theory_path, theory)
    _refresh_bindings(root)

    assert validate_package(root) == []


@pytest.mark.parametrize(
    ("field", "value", "error_code"),
    [
        ("external_validity_level", "field_study", "invalid_bet"),
        ("evidence_level", "field_study", "invalid_application_evidence"),
    ],
)
def test_machine_evidence_levels_use_exact_documented_enum(
    tmp_path: Path,
    field: str,
    value: str,
    error_code: str,
) -> None:
    root = _valid_project(tmp_path)
    bet_path = root / "research/discovery/bets/B1/BET.json"
    if field == "external_validity_level":
        path = bet_path
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["application_test"][field] = value
    else:
        path = bet_path.with_name("APPLICATION_EVIDENCE.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload[field] = value
    _write_json(path, payload)
    _refresh_bindings(root)

    assert any(
        error.startswith(f"{error_code}:") and field in error
        for error in validate_package(root)
    )


def test_recommendation_allows_an_ineligible_killed_alternative(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    _add_ineligible_killed_bet(root)
    assert validate_package(root) == []


def test_no_bet_requires_park_or_kill_disposition(tmp_path: Path) -> None:
    root = _valid_project(tmp_path, decision="no_bet")
    path = root / "research/discovery/bets/B1/BET.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["candidate_state"] = "probe"
    _write_json(path, payload)
    assert any("grounded disposition" in error for error in validate_package(root))


def test_module_help_does_not_emit_import_warning() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "argus_skill.verticals.research_discovery.evidence", "--help"],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0
    assert result.stderr == ""
    assert "{check}" in result.stdout


@pytest.mark.parametrize(
    ("filename", "error_code"),
    [
        ("THEORY_EVIDENCE.json", "invalid_theory_evidence"),
        ("APPLICATION_EVIDENCE.json", "invalid_application_evidence"),
    ],
)
def test_missing_lane_file_returns_stable_validation_error(
    tmp_path: Path, filename: str, error_code: str
) -> None:
    root = _valid_project(tmp_path)
    (root / "research/discovery/bets/B1" / filename).unlink()
    errors = validate_package(root)
    assert any(error.startswith(f"{error_code}:B1:") for error in errors)
    assert completion_issue(root) == f"research_discovery:{error_code}"


@pytest.mark.parametrize(
    ("relative_path", "error_code"),
    [
        ("research/discovery/bets/B1/THEORY_EVIDENCE.json", "invalid_theory_evidence"),
        ("research/discovery/bets/B1/APPLICATION_EVIDENCE.json", "invalid_application_evidence"),
        ("research/discovery/DECISION.json", "invalid_decision"),
    ],
)
def test_invalid_utf8_canonical_json_returns_stable_validation_error(
    tmp_path: Path, relative_path: str, error_code: str
) -> None:
    root = _valid_project(tmp_path)
    (root / relative_path).write_bytes(b"{\xff}")
    assert any(error.startswith(f"{error_code}:") for error in validate_package(root))


def test_symlinked_bet_reference_is_rejected_before_resolution(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    _add_ineligible_killed_bet(root)
    portfolio_path = root / "research/discovery/PORTFOLIO.json"
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
    portfolio["bet_refs"] = ["research/discovery/bets/B1/BET.json"]
    _write_json(portfolio_path, portfolio)
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision.update(
        eligibility=decision["eligibility"][:1],
        ordering=decision["ordering"][:1],
        bindings=decision["bindings"][:1],
    )
    _write_json(decision_path, decision)
    first_bet = root / "research/discovery/bets/B1/BET.json"
    first_bet.unlink()
    first_bet.symlink_to(Path("../B2/BET.json"))
    assert any(
        error.startswith("invalid_portfolio:") and "unsafe" in error
        for error in validate_package(root)
    )


@pytest.mark.parametrize("bad_item", [{}, [], None])
def test_malformed_ordering_elements_return_stable_errors(
    tmp_path: Path,
    bad_item: object,
) -> None:
    root = _valid_project(tmp_path)
    decision_path = root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["ordering"] = [bad_item]
    _write_json(decision_path, decision)

    errors = validate_package(root)
    assert any(
        error.startswith("invalid_decision:") and "ordering" in error
        for error in errors
    )


def test_invalid_utf8_brief_returns_missing_brief_error(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    (root / "research/discovery/BRIEF.md").write_bytes(b"\xff\xfe")

    errors = validate_package(root)
    assert errors[0].startswith("missing_brief:")
    assert completion_issue(root) == "research_discovery:missing_brief"


def test_unreadable_brief_returns_missing_brief_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _valid_project(tmp_path)
    brief = root / "research/discovery/BRIEF.md"
    real_read_text = Path.read_text

    def unreadable(path: Path, *args, **kwargs):
        if path == brief:
            raise PermissionError("brief is unreadable")
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", unreadable)
    errors = validate_package(root)
    assert errors[0].startswith("missing_brief:")


@pytest.mark.parametrize(
    ("relative_path", "error_code"),
    [
        ("research/discovery/BRIEF.md", "missing_brief"),
        ("research/discovery/PORTFOLIO.json", "invalid_portfolio"),
        ("research/discovery/DECISION.json", "invalid_decision"),
        ("research/discovery/HANDOFF.json", "invalid_handoff"),
    ],
)
def test_canonical_package_file_symlinks_are_rejected(
    tmp_path: Path,
    relative_path: str,
    error_code: str,
) -> None:
    root = _valid_project(tmp_path / "project")
    path = root / relative_path
    external = tmp_path / "external" / path.name
    external.parent.mkdir(parents=True)
    external.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(external)

    assert any(
        error.startswith(f"{error_code}:") for error in validate_package(root)
    )


def test_symlinked_discovery_parent_is_rejected_without_external_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    external_root = _valid_project(tmp_path / "external", decision="no_bet")
    portfolio_path = external_root / "research/discovery/PORTFOLIO.json"
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
    portfolio["bet_refs"] = []
    _write_json(portfolio_path, portfolio)
    decision_path = external_root / "research/discovery/DECISION.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision.update(eligibility=[], ordering=[], bindings=[])
    _write_json(decision_path, decision)

    root = tmp_path / "project"
    (root / "research").mkdir(parents=True)
    (root / "research/discovery").symlink_to(
        external_root / "research/discovery",
        target_is_directory=True,
    )
    real_read_text = Path.read_text
    external_reads: list[Path] = []

    def record_external_reads(path: Path, *args, **kwargs):
        resolved = path.resolve()
        if external_root == resolved or external_root in resolved.parents:
            external_reads.append(resolved)
        return real_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", record_external_reads)
    errors = validate_package(root)

    assert errors
    assert external_reads == []


@pytest.mark.parametrize(
    ("relative_path", "error_code"),
    [
        ("research/discovery/BRIEF.md", "missing_brief"),
        ("research/discovery/PORTFOLIO.json", "invalid_portfolio"),
        ("research/discovery/DECISION.json", "invalid_decision"),
        ("research/discovery/HANDOFF.json", "invalid_handoff"),
    ],
)
def test_non_regular_canonical_package_paths_return_stable_errors(
    tmp_path: Path,
    relative_path: str,
    error_code: str,
) -> None:
    root = _valid_project(tmp_path)
    path = root / relative_path
    path.unlink()
    path.mkdir()

    assert any(
        error.startswith(f"{error_code}:") for error in validate_package(root)
    )
