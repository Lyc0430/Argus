"""Fail-closed validation for research-discovery decision packages."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from argus_skill.core.evidence_status import (
    BASE_FAILURE_CLASSES,
    BASE_NON_IDEA_FAILURES,
    EvidenceContract,
    is_placeholder_text,
    validate_evidence,
)

SCHEMA_VERSION = 1
BET_ID = re.compile(r"^[A-Za-z0-9_-]+$")
DECISIONS = frozenset({"recommended", "no_bet", "paused"})
CANDIDATE_STATES = frozenset({"probe", "park", "select", "kill"})
NEXT_VERTICALS = frozenset({"math", "research", "software"})

THEORY_FAILURES = BASE_FAILURE_CLASSES | frozenset(
    {"theoretical", "prior_art", "scope_change"}
)
THEORY_EVIDENCE = EvidenceContract(
    domain="research_discovery_theory",
    failure_classes=THEORY_FAILURES,
    non_idea_failures=BASE_NON_IDEA_FAILURES,
    grounding_fields=("premise", "method_identity", "witness_or_derivation"),
    refuting_failures=frozenset({"theoretical"}),
    advisory_failures=frozenset({"prior_art", "scope_change"}),
)

APPLICATION_FAILURES = BASE_FAILURE_CLASSES | frozenset(
    {
        "data_access",
        "evaluator_infrastructure",
        "statistical_power",
        "empirical",
        "prior_art",
        "scope_change",
    }
)
APPLICATION_EVIDENCE = EvidenceContract(
    domain="research_discovery_application",
    failure_classes=APPLICATION_FAILURES,
    non_idea_failures=BASE_NON_IDEA_FAILURES
    | frozenset({"data_access", "evaluator_infrastructure", "statistical_power"}),
    grounding_fields=("premise", "evaluator_identity", "comparison_identity"),
    refuting_failures=frozenset({"empirical"}),
    advisory_failures=frozenset({"prior_art", "scope_change"}),
)

def content_digest(path: Path) -> str:
    """Return the SHA-256 digest of a canonical package artifact."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_ref(root: Path, value: object, *, suffix: str) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != suffix:
        return None
    candidate = (root / relative).resolve()
    if root != candidate and root not in candidate.parents:
        return None
    return candidate if candidate.is_file() and not candidate.is_symlink() else None


def _load_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file() or path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _text(value: object) -> bool:
    return not is_placeholder_text(value)


def _string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_text(item) for item in value)


def _mapping(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _require_texts(
    payload: Mapping[str, Any], fields: tuple[str, ...], errors: list[str], prefix: str
) -> None:
    for field in fields:
        if not _text(payload.get(field)):
            errors.append(f"{prefix}{field} is empty")


def _require_map(
    payload: Mapping[str, Any], field: str, errors: list[str], prefix: str
) -> dict[str, Any] | None:
    value = _mapping(payload.get(field))
    if value is None:
        errors.append(f"{prefix}{field} must be an object")
    return value


def _validate_portfolio(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    _require_texts(payload, ("objective", "focus_domain"), errors, "")
    budget = _require_map(payload, "budget", errors, "")
    if budget is not None:
        _require_texts(budget, ("summary", "stop_condition"), errors, "budget.")
    refs = payload.get("bet_refs")
    if not isinstance(refs, list) or any(not _text(ref) for ref in refs):
        errors.append("bet_refs must be a list of non-empty paths")
    search = _require_map(payload, "search_summary", errors, "")
    if search is not None:
        _require_texts(search, ("as_of",), errors, "search_summary.")
        for field in ("sources", "queries"):
            if not _string_list(search.get(field)):
                errors.append(f"search_summary.{field} must be a non-empty list of strings")
    return errors


def _validate_bet(payload: Mapping[str, Any], bet_id: str) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    if payload.get("id") != bet_id or not BET_ID.fullmatch(str(payload.get("id") or "")):
        errors.append("id must match the referenced bet ID")
    revision = payload.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision <= 0:
        errors.append("revision must be a positive integer")
    _require_texts(payload, ("title", "candidate_premise", "kill_criteria", "estimated_cost", "next_uncertainty"), errors, "")
    if payload.get("candidate_state") not in CANDIDATE_STATES:
        errors.append("candidate_state is invalid")
    if not _string_list(payload.get("limitations")):
        errors.append("limitations must be a non-empty list of strings")

    problem = _require_map(payload, "problem_anchor", errors, "")
    if problem is not None:
        _require_texts(problem, ("stakeholder", "setting_and_decision", "baseline", "observed_failure", "provenance"), errors, "problem_anchor.")
    theory = _require_map(payload, "theory_anchor", errors, "")
    if theory is not None:
        _require_texts(theory, ("objects", "assumptions_scope", "mechanism", "prediction", "falsifier"), errors, "theory_anchor.")
        if theory.get("status") not in {"conjectured", "sketched", "proved", "verified"}:
            errors.append("theory_anchor.status is invalid")
    bridge = _require_map(payload, "bridge", errors, "")
    if bridge is not None:
        if bridge.get("direction") not in {"theory_to_application", "application_to_theory", "bidirectional"}:
            errors.append("bridge.direction is invalid")
        mappings = bridge.get("variable_mappings")
        if not isinstance(mappings, list) or not mappings or any(not isinstance(item, dict) or not item for item in mappings):
            errors.append("bridge.variable_mappings must be a non-empty list of mappings")
        _require_texts(bridge, ("dependency_claim", "observable_prediction", "no_garnish_counterfactual"), errors, "bridge.")
        if bridge.get("status") not in {"untested", "weak", "supported", "broken"}:
            errors.append("bridge.status is invalid")
    novelty = _require_map(payload, "novelty", errors, "")
    if novelty is not None:
        if novelty.get("status") not in {"distinct_on_searched_axis", "overlap", "unresolved"}:
            errors.append("novelty.status is invalid")
        _require_texts(novelty, ("search_date", "query_summary", "nearest_verified_work", "delta_axis", "dangerous_overlap"), errors, "novelty.")
    application = _require_map(payload, "application_test", errors, "")
    if application is not None:
        _require_texts(application, ("intervention", "baseline", "decision_metric", "evaluator_identity", "scope", "falsifier", "proxy_fidelity", "external_validity_ceiling"), errors, "application_test.")
        if not _string_list(application.get("risks")):
            errors.append("application_test.risks must be a non-empty list of strings")
    return errors


def _validate_lane(
    payload: Mapping[str, Any], *, bet_id: str, revision: object, contract: EvidenceContract, kind: str, root: Path
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    if payload.get("bet_id") != bet_id:
        errors.append("bet_id does not match BET.json")
    if payload.get("bet_revision") != revision:
        errors.append("bet_revision does not match BET.json revision")
    _require_texts(payload, ("premise_version", "preregistered_question", "method", "falsifier", "stop_rule", "scope_limits", "timestamp"), errors, "")
    refs = payload.get("raw_artifact_refs")
    if not _string_list(refs):
        errors.append("raw_artifact_refs must be a non-empty list of paths")
    else:
        for ref in refs:
            if _safe_ref(root, ref, suffix=Path(str(ref)).suffix) is None:
                errors.append(f"raw_artifact_refs contains an unsafe or missing path: {ref!r}")
    evidence_errors = validate_evidence(dict(payload), contract)
    errors.extend(
        finding.replace("record it as a replan reason", "record it as a replanning reason")
        for finding in evidence_errors
    )
    if kind == "application" and not _text(payload.get("claim_ceiling")):
        errors.append("claim_ceiling is empty")
    return list(dict.fromkeys(errors))


def _ceiling_level(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "proxy": 0,
        "simulation": 0,
        "simulated": 0,
        "benchmark": 0,
        "retrospective": 1,
        "real_setting": 2,
        "real_world": 2,
        "prospective": 2,
        "production": 3,
    }
    return aliases.get(normalized)


def _validate_decision(
    payload: Mapping[str, Any], bet_ids: list[str], bets: Mapping[str, Mapping[str, Any]], records: Mapping[str, Mapping[str, Any]], errors: list[str]
) -> str | None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    decision = payload.get("decision")
    if decision not in DECISIONS:
        errors.append("decision is invalid")
        return None
    _require_texts(payload, ("selection_rationale",), errors, "")
    if not _string_list(payload.get("residual_risks")):
        errors.append("residual_risks must be a non-empty list of strings")
    if not isinstance(payload.get("limited_by_budget"), bool):
        errors.append("limited_by_budget must be boolean")

    eligibility = payload.get("eligibility")
    if not isinstance(eligibility, list) or len(eligibility) != len(bet_ids):
        errors.append("eligibility must contain one row per referenced bet")
    else:
        seen: set[str] = set()
        for expected_id, row in zip(bet_ids, eligibility, strict=True):
            if not isinstance(row, dict) or row.get("bet_id") != expected_id or not isinstance(row.get("eligible"), bool) or not isinstance(row.get("failed_gates"), list) or any(not _text(gate) for gate in row.get("failed_gates", [])):
                errors.append("eligibility rows must be ordered bet_id, eligible, and failed_gates records")
                break
            if row["bet_id"] in seen:
                errors.append("eligibility contains duplicate bet IDs")
                break
            seen.add(row["bet_id"])

    ordering = payload.get("ordering")
    if not isinstance(ordering, list) or len(ordering) != len(set(ordering)) or set(ordering) != set(bet_ids) or any(not isinstance(item, str) for item in ordering):
        errors.append("ordering must be an ordinal list of each unique bet ID without scores")

    bindings = payload.get("bindings")
    if not isinstance(bindings, list) or len(bindings) != len(bet_ids):
        errors.append("bindings must contain one row per referenced bet")

    selected_ids = [bet_id for bet_id, bet in bets.items() if bet.get("candidate_state") == "select"]
    recommended_id = payload.get("recommended_bet_id")
    if decision == "recommended":
        if recommended_id not in bets:
            errors.append("recommended bet is not in portfolio")
        if len(selected_ids) != 1 or selected_ids != [recommended_id]:
            errors.append("recommended requires exactly one selected bet")
        if not isinstance(eligibility, list) or any(
            not isinstance(row, dict)
            or row.get("eligible") is not True
            or row.get("failed_gates") != []
            for row in eligibility
        ):
            errors.append("recommended requires every eligibility gate to pass")
        if isinstance(recommended_id, str) and recommended_id in records and recommended_id in bets:
            theory = records[recommended_id]["theory"]
            application = records[recommended_id]["application"]
            bet = bets[recommended_id]
            if theory.get("execution_status") != "completed" or theory.get("idea_status") != "supported":
                errors.append("recommended premise is not supported")
            if application.get("execution_status") != "completed" or application.get("idea_status") != "supported":
                errors.append("recommended premise is not supported")
            bridge = _mapping(bet.get("bridge")) or {}
            if bridge.get("status") != "supported" or "changes nothing" in str(bridge.get("no_garnish_counterfactual") or "").lower():
                errors.append("recommended bridge is not supported")
            novelty = _mapping(bet.get("novelty")) or {}
            if novelty.get("status") == "unresolved":
                errors.append("recommended novelty delta is unresolved")
            app_test = _mapping(bet.get("application_test")) or {}
            claimed = _ceiling_level(application.get("claim_ceiling"))
            ceiling = _ceiling_level(app_test.get("external_validity_ceiling"))
            if claimed is None or ceiling is None or claimed > ceiling:
                errors.append("application proxy evidence exceeds its declared external-validity ceiling")
    elif decision == "no_bet":
        if recommended_id is not None:
            errors.append("no_bet requires recommended_bet_id to be null")
        if selected_ids:
            errors.append("no_bet cannot select a bet")
        if bet_ids and (
            not isinstance(eligibility, list)
            or any(not isinstance(row, dict) or not row.get("failed_gates") for row in eligibility)
            or any(bets[bet_id].get("candidate_state") not in {"park", "kill"} for bet_id in bet_ids if bet_id in bets)
        ):
            errors.append("no_bet requires a grounded disposition for every referenced bet")
    elif decision == "paused" and recommended_id is not None:
        errors.append("paused requires recommended_bet_id to be null")
    return str(decision)


def _validate_bindings(
    bindings: object, bet_ids: list[str], records: Mapping[str, Mapping[str, Any]], errors: list[str]
) -> None:
    if not isinstance(bindings, list):
        return
    by_id: dict[str, Mapping[str, Any]] = {}
    for binding in bindings:
        if not isinstance(binding, Mapping) or not isinstance(binding.get("bet_id"), str):
            errors.append("binding must include bet_id and current digests")
            continue
        bet_id = binding["bet_id"]
        if bet_id in by_id:
            errors.append("bindings contain duplicate bet IDs")
            continue
        by_id[bet_id] = binding
    for bet_id in bet_ids:
        binding = by_id.get(bet_id)
        record = records.get(bet_id)
        if binding is None or record is None:
            errors.append(f"missing current binding for {bet_id}")
            continue
        expected = {
            "bet_revision": record["bet"].get("revision"),
            "bet_sha256": content_digest(record["bet_path"]),
            "theory_evidence_sha256": content_digest(record["theory_path"]),
            "application_evidence_sha256": content_digest(record["application_path"]),
        }
        if any(binding.get(field) != value for field, value in expected.items()):
            errors.append(f"binding for {bet_id} is stale")


def _validate_handoff(
    payload: Mapping[str, Any], decision: Mapping[str, Any], records: Mapping[str, Mapping[str, Any]], root: Path
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    bet_id = decision.get("recommended_bet_id")
    record = records.get(bet_id) if isinstance(bet_id, str) else None
    if record is None:
        errors.append("handoff bet is not a valid recommendation")
    else:
        expected = {
            "bet_id": bet_id,
            "bet_revision": record["bet"].get("revision"),
            "bet_sha256": content_digest(record["bet_path"]),
            "theory_evidence_sha256": content_digest(record["theory_path"]),
            "application_evidence_sha256": content_digest(record["application_path"]),
        }
        if any(payload.get(field) != value for field, value in expected.items()):
            errors.append("handoff bindings are stale or inconsistent")
    if payload.get("next_vertical") not in NEXT_VERTICALS:
        errors.append("next_vertical is invalid")
    _require_texts(payload, ("binding_uncertainty", "objective", "acceptance_check", "return_condition", "claim_ceiling"), errors, "")
    if not _string_list(payload.get("non_goals")):
        errors.append("non_goals must be a non-empty list of strings")
    refs = payload.get("evidence_references")
    if not _string_list(refs):
        errors.append("evidence_references must be a non-empty list of paths")
    else:
        for ref in refs:
            if _safe_ref(root, ref, suffix=Path(str(ref)).suffix) is None:
                errors.append(f"evidence_references contains an unsafe or missing path: {ref!r}")
    return errors


def validate_package(project_root: Path | str) -> list[str]:
    """Return stable-code validation findings for a discovery package."""
    root = Path(project_root).resolve()
    discovery = root / "research" / "discovery"
    errors: list[str] = []

    brief = discovery / "BRIEF.md"
    if not brief.is_file() or brief.is_symlink() or not brief.read_text(encoding="utf-8").strip():
        errors.append("missing_brief:research/discovery/BRIEF.md is missing or empty")

    portfolio_path = discovery / "PORTFOLIO.json"
    portfolio = _load_object(portfolio_path)
    if portfolio is None:
        errors.append("invalid_portfolio:PORTFOLIO.json is missing or invalid JSON")
        portfolio = {}
    for finding in _validate_portfolio(portfolio):
        errors.append(f"invalid_portfolio:{finding}")

    refs = portfolio.get("bet_refs")
    bet_ids: list[str] = []
    records: dict[str, dict[str, Any]] = {}
    if isinstance(refs, list):
        seen_refs: set[str] = set()
        for ref in refs:
            path = _safe_ref(root, ref, suffix=".json")
            if path is None:
                errors.append(f"invalid_portfolio:unsafe or missing bet reference: {ref!r}")
                continue
            relative = path.relative_to(root)
            parts = relative.parts
            if len(parts) != 5 or parts[:3] != ("research", "discovery", "bets") or parts[-1] != "BET.json" or not BET_ID.fullmatch(parts[3]):
                errors.append(f"invalid_portfolio:bet reference is not an exact BET.json path: {ref!r}")
                continue
            bet_id = parts[3]
            if bet_id in seen_refs:
                errors.append(f"invalid_portfolio:duplicate bet ID: {bet_id}")
                continue
            seen_refs.add(bet_id)
            bet_ids.append(bet_id)
            bet = _load_object(path)
            if bet is None:
                errors.append(f"invalid_bet:{bet_id}:BET.json is invalid")
                continue
            for finding in _validate_bet(bet, bet_id):
                errors.append(f"invalid_bet:{bet_id}:{finding}")
            theory_path = path.with_name("THEORY_EVIDENCE.json")
            application_path = path.with_name("APPLICATION_EVIDENCE.json")
            theory = _load_object(theory_path)
            application = _load_object(application_path)
            if theory is None:
                errors.append(f"invalid_theory_evidence:{bet_id}:THEORY_EVIDENCE.json is missing or invalid")
                theory = {}
            for finding in _validate_lane(theory, bet_id=bet_id, revision=bet.get("revision"), contract=THEORY_EVIDENCE, kind="theory", root=root):
                errors.append(f"invalid_theory_evidence:{bet_id}:{finding}")
            if application is None:
                errors.append(f"invalid_application_evidence:{bet_id}:APPLICATION_EVIDENCE.json is missing or invalid")
                application = {}
            for finding in _validate_lane(application, bet_id=bet_id, revision=bet.get("revision"), contract=APPLICATION_EVIDENCE, kind="application", root=root):
                errors.append(f"invalid_application_evidence:{bet_id}:{finding}")
            records[bet_id] = {
                "bet": bet,
                "theory": theory,
                "application": application,
                "bet_path": path,
                "theory_path": theory_path,
                "application_path": application_path,
            }

    decision_path = discovery / "DECISION.json"
    decision = _load_object(decision_path)
    decision_name: str | None = None
    if decision is None:
        errors.append("invalid_decision:DECISION.json is missing or invalid JSON")
        decision = {}
    decision_findings: list[str] = []
    decision_name = _validate_decision(decision, bet_ids, {key: value["bet"] for key, value in records.items()}, records, decision_findings)
    errors.extend(f"invalid_decision:{finding}" for finding in decision_findings)

    freshness_findings: list[str] = []
    _validate_bindings(decision.get("bindings"), bet_ids, records, freshness_findings)
    errors.extend(f"stale_decision:{finding}" for finding in freshness_findings)

    handoff_path = discovery / "HANDOFF.json"
    if decision_name == "recommended":
        handoff = _load_object(handoff_path)
        if handoff is None:
            errors.append("invalid_handoff:recommended decision requires HANDOFF.json")
        else:
            errors.extend(f"invalid_handoff:{finding}" for finding in _validate_handoff(handoff, decision, records, root))
    elif handoff_path.exists():
        errors.append("invalid_handoff:HANDOFF.json is allowed only for a recommended decision")

    if decision_name == "paused":
        errors.append("terminal_paused:paused discovery decisions are non-terminal")
    return errors


def completion_issue(project_root: Path | str) -> str:
    """Return the first stable completion blocker, or an empty string."""
    errors = validate_package(project_root)
    if not errors:
        return ""
    # Freshness is the terminal review boundary: a changed bet invalidates the
    # decision even when the edit also made a lane's revision stale.
    for error in errors:
        if error.startswith("stale_decision:"):
            return "research_discovery:stale_decision"
    return f"research_discovery:{errors[0].split(':', 1)[0]}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    errors = validate_package(args.project_root)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 2
    print("research discovery package: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
