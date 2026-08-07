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
        "application_test": {
            "intervention": "Replace the fixed threshold with the interval-aware threshold.",
            "baseline": "Rule-based fixed threshold",
            "decision_metric": "avoidable escalations at matched recall",
            "evaluator_identity": "held-out audit evaluator v1",
            "scope": "Retrospective urgent-care records",
            "falsifier": "No calibration improvement at matched recall.",
            "proxy_fidelity": "Retrospective records retain the decision inputs.",
            "external_validity_ceiling": "retrospective",
            "risks": ["clinical use remains out of scope"],
        },
        "kill_criteria": "No improvement on the preregistered metric.",
        "limitations": ["Retrospective evidence only"],
        "estimated_cost": "Two analyst days",
        "next_uncertainty": "Prospective calibration may differ.",
    }


def valid_theory_evidence() -> dict:
    return {
        "schema_version": 1,
        "bet_id": "B1",
        "bet_revision": 1,
        "premise_version": "B1-r1",
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


def valid_application_evidence() -> dict:
    return {
        "schema_version": 1,
        "bet_id": "B1",
        "bet_revision": 1,
        "premise_version": "B1-r1",
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
            {"bet_id": "B1", "eligible": recommended, "failed_gates": [] if recommended else ["bounded no-bet rationale"]}
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
    _write_json(bet_path, valid_bet(candidate_state="select" if decision == "recommended" else "park"))
    _write_json(theory_path, valid_theory_evidence())
    _write_json(application_path, valid_application_evidence())
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


def _add_ineligible_killed_bet(root: Path) -> None:
    discovery = root / "research" / "discovery"
    bet_path = discovery / "bets" / "B2" / "BET.json"
    theory_path = bet_path.with_name("THEORY_EVIDENCE.json")
    application_path = bet_path.with_name("APPLICATION_EVIDENCE.json")
    bet = valid_bet(candidate_state="kill")
    bet.update(id="B2", title="Rejected alternative")
    theory = valid_theory_evidence()
    theory.update(
        bet_id="B2",
        raw_artifact_refs=["research/discovery/bets/B2/theory.txt"],
        witness_or_derivation="research/discovery/bets/B2/theory.txt",
    )
    application = valid_application_evidence()
    application.update(
        bet_id="B2",
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
        {"bet_id": "B2", "eligible": False, "failed_gates": ["prior art"]}
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


def test_recommendation_rejects_decorative_bridge(tmp_path: Path) -> None:
    root = _valid_project(tmp_path)
    path = root / "research/discovery/bets/B1/BET.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["bridge"]["no_garnish_counterfactual"] = "Removing the theory changes nothing."
    payload["bridge"]["status"] = "weak"
    _write_json(path, payload)
    assert any("bridge" in error for error in validate_package(root))


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
    payload["claim_ceiling"] = "production"
    _write_json(path, payload)
    assert any("exceeds its declared" in error for error in validate_package(root))


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
