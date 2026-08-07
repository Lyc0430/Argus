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
DECISION_BASES = frozenset(
    {"eligible", "pre_probe_gate", "completed_probe", "blocked_probe"}
)
ELIGIBILITY_GATES = frozenset(
    {
        "application_anchor",
        "theory_anchor",
        "bridge",
        "nearest_work",
        "theory_probe",
        "application_probe",
        "evidence_separation",
        "safety_authority",
        "fresh_review",
    }
)
PRE_PROBE_GATE_ORDER = (
    "application_anchor",
    "theory_anchor",
    "bridge",
    "nearest_work",
)
PRE_PROBE_GATES = frozenset(PRE_PROBE_GATE_ORDER)
PROBE_GATES = frozenset({"theory_probe", "application_probe"})
EVIDENCE_LEVELS = ("proxy", "retrospective", "real_setting", "production")
_EVIDENCE_LEVEL_ORDER = {value: index for index, value in enumerate(EVIDENCE_LEVELS)}

THEORY_FAILURES = BASE_FAILURE_CLASSES | frozenset(
    {"theoretical", "prior_art", "scope_change"}
)
THEORY_EVIDENCE = EvidenceContract(
    domain="research_discovery_theory",
    failure_classes=THEORY_FAILURES,
    non_idea_failures=BASE_NON_IDEA_FAILURES | frozenset({"implementation"}),
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
    | frozenset(
        {
            "data_access",
            "evaluator_infrastructure",
            "implementation",
            "statistical_power",
        }
    ),
    grounding_fields=("premise", "evaluator_identity", "comparison_identity"),
    refuting_failures=frozenset({"empirical"}),
    advisory_failures=frozenset({"prior_art", "scope_change"}),
)

def content_digest(path: Path) -> str:
    """Return the SHA-256 digest of a canonical package artifact."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def premise_digest(bet: Mapping[str, Any], *, lane: str) -> str:
    """Bind one lane to the current canonical Bet premise material."""
    if lane not in {"theory", "application"}:
        raise ValueError("lane must be 'theory' or 'application'")
    anchor_field = "theory_anchor" if lane == "theory" else "application_test"
    material = {
        "bet_id": bet.get("id"),
        "bet_revision": bet.get("revision"),
        "candidate_premise": bet.get("candidate_premise"),
        "lane": lane,
        "lane_anchor": bet.get(anchor_field),
        "bridge": bet.get("bridge"),
    }
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _safe_ref(root: Path, value: object, *, suffix: str) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        relative = Path(value)
    except (TypeError, ValueError):
        return None
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.suffix != suffix
    ):
        return None
    try:
        unresolved = root
        for part in relative.parts:
            unresolved /= part
            if unresolved.is_symlink():
                return None
        candidate = unresolved.resolve()
        if root != candidate and root not in candidate.parents:
            return None
        if not candidate.is_file() or candidate.is_symlink():
            return None
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate


def _load_object(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        if not path.is_file() or path.is_symlink():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _path_present(path: Path) -> bool:
    try:
        return path.exists() or path.is_symlink()
    except OSError:
        return True


def _text(value: object) -> bool:
    return not is_placeholder_text(value)


def _string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(_text(item) for item in value)


def _mapping(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _pre_probe_gate_statuses(
    bet: Mapping[str, Any], errors: list[str] | None = None
) -> dict[str, str] | None:
    findings = errors if errors is not None else []
    gates = _mapping(bet.get("pre_probe_gates"))
    if gates is None or set(gates) != PRE_PROBE_GATES:
        findings.append("pre_probe_gates must contain exactly the four required gates")
        return None
    statuses: dict[str, str] = {}
    for gate in PRE_PROBE_GATE_ORDER:
        row = _mapping(gates.get(gate))
        if row is None or row.get("status") not in {"pass", "fail"}:
            findings.append(f"pre_probe_gates.{gate}.status must be pass or fail")
            continue
        if not _text(row.get("rationale")):
            findings.append(f"pre_probe_gates.{gate}.rationale is empty")
            continue
        statuses[gate] = str(row["status"])
    return statuses if len(statuses) == len(PRE_PROBE_GATE_ORDER) else None


def _failed_pre_probe_gates(bet: Mapping[str, Any]) -> frozenset[str] | None:
    statuses = _pre_probe_gate_statuses(bet)
    if statuses is None:
        return None
    return frozenset(
        gate for gate, status in statuses.items() if status == "fail"
    )


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
        _require_texts(
            theory,
            (
                "binding_premise",
                "objects",
                "assumptions_scope",
                "mechanism",
                "prediction",
                "falsifier",
            ),
            errors,
            "theory_anchor.",
        )
        if theory.get("status") not in {"conjectured", "sketched", "proved", "verified"}:
            errors.append("theory_anchor.status is invalid")
    bridge = _require_map(payload, "bridge", errors, "")
    if bridge is not None:
        if bridge.get("direction") not in {"theory_to_application", "application_to_theory", "bidirectional"}:
            errors.append("bridge.direction is invalid")
        mappings = bridge.get("variable_mappings")
        if not isinstance(mappings, list) or not mappings:
            errors.append(
                "bridge.variable_mappings must be a non-empty list of mappings"
            )
        elif any(
            not isinstance(item, Mapping)
            or not _text(item.get("theory"))
            or not _text(item.get("application"))
            for item in mappings
        ):
            errors.append(
                "bridge.variable_mappings rows require non-empty theory and application"
            )
        _require_texts(bridge, ("dependency_claim", "observable_prediction", "no_garnish_counterfactual"), errors, "bridge.")
        if bridge.get("status") not in {"untested", "weak", "supported", "broken"}:
            errors.append("bridge.status is invalid")
    novelty = _require_map(payload, "novelty", errors, "")
    if novelty is not None:
        if novelty.get("status") not in {"distinct_on_searched_axis", "overlap", "unresolved"}:
            errors.append("novelty.status is invalid")
        _require_texts(novelty, ("search_date", "query_summary", "nearest_verified_work", "delta_axis", "dangerous_overlap"), errors, "novelty.")
    gate_statuses = _pre_probe_gate_statuses(payload, errors)
    if gate_statuses is not None:
        bridge_gate = gate_statuses["bridge"]
        bridge_status = bridge.get("status") if bridge is not None else None
        if bridge_status == "supported" and bridge_gate != "pass":
            errors.append(
                "pre_probe_gates.bridge.status must pass when bridge.status is supported"
            )
        elif bridge_status in {"weak", "broken"} and bridge_gate != "fail":
            errors.append(
                "pre_probe_gates.bridge.status must fail when bridge.status is weak or broken"
            )
        elif bridge_status == "untested":
            errors.append(
                "pre_probe_gates.bridge cannot certify a terminal package when bridge.status is untested"
            )

        nearest_gate = gate_statuses["nearest_work"]
        novelty_status = novelty.get("status") if novelty is not None else None
        if (
            novelty_status == "distinct_on_searched_axis"
            and nearest_gate != "pass"
        ):
            errors.append(
                "pre_probe_gates.nearest_work.status must pass when novelty.status is distinct_on_searched_axis"
            )
        elif novelty_status == "unresolved" and nearest_gate != "fail":
            errors.append(
                "pre_probe_gates.nearest_work.status must fail when novelty.status is unresolved"
            )
    application = _require_map(payload, "application_test", errors, "")
    if application is not None:
        _require_texts(
            application,
            (
                "binding_premise",
                "intervention",
                "baseline",
                "decision_metric",
                "evaluator_identity",
                "scope",
                "falsifier",
                "proxy_fidelity",
                "external_validity_ceiling",
            ),
            errors,
            "application_test.",
        )
        if application.get("external_validity_level") not in EVIDENCE_LEVELS:
            errors.append(
                "application_test.external_validity_level must be one of "
                + " | ".join(EVIDENCE_LEVELS)
            )
        if not _string_list(application.get("risks")):
            errors.append("application_test.risks must be a non-empty list of strings")
    return errors


def _validate_lane(
    payload: Mapping[str, Any], *, bet: Mapping[str, Any], bet_id: str,
    revision: object, contract: EvidenceContract, kind: str, root: Path
) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version must be 1")
    if payload.get("bet_id") != bet_id:
        errors.append("bet_id does not match BET.json")
    if payload.get("bet_revision") != revision:
        errors.append("bet_revision does not match BET.json revision")
    _require_texts(
        payload,
        (
            "premise_version",
            "premise_sha256",
            "preregistered_question",
            "method",
            "falsifier",
            "stop_rule",
            "scope_limits",
            "timestamp",
        ),
        errors,
        "",
    )
    expected_version = (
        f"{bet_id}-r{revision}"
        if isinstance(revision, int) and not isinstance(revision, bool) and revision > 0
        else None
    )
    if expected_version is not None and payload.get("premise_version") != expected_version:
        errors.append(f"premise_version must equal {expected_version}")
    anchor_field = "theory_anchor" if kind == "theory" else "application_test"
    anchor = _mapping(bet.get(anchor_field)) or {}
    if payload.get("premise") != anchor.get("binding_premise"):
        errors.append(f"premise must equal {anchor_field}.binding_premise")
    try:
        expected_digest = premise_digest(bet, lane=kind)
    except (TypeError, ValueError):
        expected_digest = None
    if expected_digest is not None and payload.get("premise_sha256") != expected_digest:
        errors.append("premise_sha256 does not bind the current canonical Bet premise")
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
    if kind == "application":
        if not _text(payload.get("claim_ceiling")):
            errors.append("claim_ceiling is empty")
        evidence_level = payload.get("evidence_level")
        if evidence_level not in EVIDENCE_LEVELS:
            errors.append(
                "evidence_level must be one of " + " | ".join(EVIDENCE_LEVELS)
            )
        ceiling_level = anchor.get("external_validity_level")
        if (
            evidence_level in _EVIDENCE_LEVEL_ORDER
            and ceiling_level in _EVIDENCE_LEVEL_ORDER
            and _EVIDENCE_LEVEL_ORDER[evidence_level]
            > _EVIDENCE_LEVEL_ORDER[ceiling_level]
        ):
            errors.append(
                "application evidence_level exceeds its declared external-validity level"
            )
    return list(dict.fromkeys(errors))


def _completed_probe_basis_issue(
    row: Mapping[str, Any],
    record: Mapping[str, Any] | None,
) -> str:
    if record is None:
        return "completed_probe has no current lane records"
    lanes = {
        "theory_probe": (
            record.get("theory"),
            THEORY_EVIDENCE,
            record.get("theory_valid") is True,
        ),
        "application_probe": (
            record.get("application"),
            APPLICATION_EVIDENCE,
            record.get("application_valid") is True,
        ),
    }
    for lane_record, contract, valid in lanes.values():
        if not isinstance(lane_record, Mapping):
            return "completed_probe has no current lane records"
        failure = lane_record.get("failure_class")
        if (
            lane_record.get("execution_status") != "completed"
            or failure in contract.non_idea_failures
            or failure in contract.advisory_failures
            or not valid
        ):
            return (
                "completed_probe requires both faithful lanes to complete; "
                "record paused when a lane is blocked, failed, or invalid"
            )
    failed_probe_gates = set(row.get("failed_gates", ())) & PROBE_GATES
    if not failed_probe_gates:
        return "completed_probe requires a failed theory_probe or application_probe gate"
    for gate in failed_probe_gates:
        lane_record = lanes[gate][0]
        if not isinstance(lane_record, Mapping) or lane_record.get(
            "idea_status"
        ) not in {"refuted", "inconclusive"}:
            return f"completed_probe {gate} is not grounded by a negative or inconclusive result"
    return ""


def _blocked_probe_basis_is_grounded(
    row: Mapping[str, Any],
    record: Mapping[str, Any] | None,
) -> bool:
    if record is None:
        return False
    lane_by_gate = {
        "theory_probe": (record.get("theory"), THEORY_EVIDENCE),
        "application_probe": (record.get("application"), APPLICATION_EVIDENCE),
    }
    failed_probe_gates = set(row.get("failed_gates", ())) & PROBE_GATES
    if not failed_probe_gates:
        return False
    for gate in failed_probe_gates:
        lane_record, contract = lane_by_gate[gate]
        if not isinstance(lane_record, Mapping):
            return True
        failure = lane_record.get("failure_class")
        if (
            lane_record.get("execution_status") != "completed"
            or failure in contract.non_idea_failures
            or failure in contract.advisory_failures
        ):
            return True
    return False


def _validate_decision(
    payload: Mapping[str, Any],
    bet_ids: list[str],
    bets: Mapping[str, Mapping[str, Any]],
    records: Mapping[str, Mapping[str, Any]],
    errors: list[str],
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
    eligibility_by_id: dict[str, Mapping[str, Any]] = {}
    if not isinstance(eligibility, list) or len(eligibility) != len(bet_ids):
        errors.append("eligibility must contain one row per referenced bet")
    else:
        seen: set[str] = set()
        for expected_id, row in zip(bet_ids, eligibility, strict=True):
            if (
                not isinstance(row, Mapping)
                or row.get("bet_id") != expected_id
                or not isinstance(row.get("eligible"), bool)
                or row.get("decision_basis") not in DECISION_BASES
                or not isinstance(row.get("failed_gates"), list)
            ):
                errors.append(
                    "eligibility rows must be ordered bet_id, eligible, "
                    "decision_basis, and failed_gates records"
                )
                continue
            bet_id = row["bet_id"]
            if bet_id in seen:
                errors.append("eligibility contains duplicate bet IDs")
                continue
            seen.add(bet_id)
            eligibility_by_id[bet_id] = row
            gates = row["failed_gates"]
            if any(
                not isinstance(gate, str) or gate not in ELIGIBILITY_GATES
                for gate in gates
            ):
                errors.append(
                    f"eligibility {bet_id} failed_gates must use documented gate identifiers"
                )
                continue
            eligible = row["eligible"]
            basis = row["decision_basis"]
            if eligible and (basis != "eligible" or gates):
                errors.append(
                    f"eligibility {bet_id} eligible=true requires decision_basis=eligible "
                    "and no failed_gates"
                )
            if not eligible and (basis == "eligible" or not gates):
                errors.append(
                    f"eligibility {bet_id} ineligible rows require a noneligible "
                    "decision_basis and failed_gates"
                )
            current_bet = bets.get(bet_id)
            current_failed = (
                _failed_pre_probe_gates(current_bet)
                if isinstance(current_bet, Mapping)
                else None
            )
            gate_set = set(gates)
            if basis == "eligible":
                if current_failed is None:
                    errors.append(
                        f"eligibility {bet_id} eligible requires valid current Bet "
                        "pre-probe gates"
                    )
                elif current_failed:
                    errors.append(
                        f"eligibility {bet_id} eligible requires all pre-probe gates to pass"
                    )
            elif basis == "pre_probe_gate":
                if not gate_set or not gate_set <= PRE_PROBE_GATES:
                    errors.append(
                        f"eligibility {bet_id} pre_probe_gate cannot mix probe gates"
                    )
                elif current_failed is None or gate_set != set(current_failed):
                    errors.append(
                        f"eligibility {bet_id} failed_gates do not match the current Bet"
                    )
            elif basis == "completed_probe":
                if not gate_set or not gate_set <= PROBE_GATES:
                    errors.append(
                        f"eligibility {bet_id} completed_probe accepts only probe gates"
                    )
                if current_failed is None:
                    errors.append(
                        f"eligibility {bet_id} completed_probe requires valid current Bet "
                        "pre-probe gates"
                    )
                elif current_failed:
                    errors.append(
                        f"eligibility {bet_id} completed_probe requires all pre-probe gates to pass"
                    )
                issue = _completed_probe_basis_issue(row, records.get(bet_id))
                if issue:
                    errors.append(f"eligibility {bet_id} {issue}")
            elif basis == "blocked_probe" and not _blocked_probe_basis_is_grounded(
                row, records.get(bet_id)
            ):
                errors.append(
                    f"eligibility {bet_id} blocked_probe lacks a blocked or failed lane"
                )

    ordering = payload.get("ordering")
    if not isinstance(ordering, list) or any(
        not isinstance(item, str) for item in ordering
    ):
        errors.append("ordering must be an ordinal list of each unique bet ID without scores")
    elif len(ordering) != len(set(ordering)) or set(ordering) != set(bet_ids):
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
        recommended_eligibility = eligibility_by_id.get(str(recommended_id))
        if (
            not isinstance(recommended_eligibility, dict)
            or recommended_eligibility.get("eligible") is not True
            or recommended_eligibility.get("decision_basis") != "eligible"
            or recommended_eligibility.get("failed_gates") != []
        ):
            errors.append("recommended bet must pass every eligibility gate")
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
    elif decision == "no_bet":
        if recommended_id is not None:
            errors.append("no_bet requires recommended_bet_id to be null")
        if selected_ids:
            errors.append("no_bet cannot select a bet")
        if any(row.get("eligible") is not False for row in eligibility_by_id.values()):
            errors.append("no_bet requires every referenced candidate to be ineligible")
        if any(
            row.get("decision_basis") == "blocked_probe"
            for row in eligibility_by_id.values()
        ):
            errors.append("no_bet cannot terminate with decision_basis=blocked_probe")
        if bet_ids and (
            len(eligibility_by_id) != len(bet_ids)
            or any(
                not row.get("failed_gates") for row in eligibility_by_id.values()
            )
            or any(
                bets[bet_id].get("candidate_state") not in {"park", "kill"}
                for bet_id in bet_ids
                if bet_id in bets
            )
        ):
            errors.append("no_bet requires a grounded disposition for every referenced bet")
    elif decision == "paused" and recommended_id is not None:
        errors.append("paused requires recommended_bet_id to be null")
    return str(decision)


def _current_binding(record: Mapping[str, Any]) -> dict[str, object] | None:
    try:
        bet_path = record["bet_path"]
        theory_path = record["theory_path"]
        application_path = record["application_path"]
        if not all(
            isinstance(path, Path)
            for path in (bet_path, theory_path, application_path)
        ):
            return None
        return {
            "bet_revision": record["bet"].get("revision"),
            "bet_sha256": content_digest(bet_path),
            "theory_evidence_sha256": content_digest(theory_path),
            "application_evidence_sha256": content_digest(application_path),
        }
    except (KeyError, OSError):
        return None


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
        expected = _current_binding(record)
        if expected is None:
            errors.append(f"current artifacts for {bet_id} are unavailable")
            continue
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
        expected = _current_binding(record)
        if expected is None:
            errors.append("handoff bindings are unavailable")
        elif payload.get("bet_id") != bet_id or any(
            payload.get(field) != value for field, value in expected.items()
        ):
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
    try:
        root = Path(project_root).resolve()
    except (OSError, RuntimeError, TypeError, ValueError):
        return ["missing_brief:project root is unavailable"]
    discovery = root / "research" / "discovery"
    errors: list[str] = []

    brief = _safe_ref(
        root,
        "research/discovery/BRIEF.md",
        suffix=".md",
    )
    brief_text = ""
    if brief is not None:
        try:
            brief_text = brief.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError):
            brief_text = ""
    if not brief_text.strip():
        errors.append("missing_brief:research/discovery/BRIEF.md is missing or empty")

    portfolio_path = _safe_ref(
        root,
        "research/discovery/PORTFOLIO.json",
        suffix=".json",
    )
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
            bet_relative = path.relative_to(root)
            theory_path = _safe_ref(
                root,
                str(bet_relative.with_name("THEORY_EVIDENCE.json")),
                suffix=".json",
            )
            application_path = _safe_ref(
                root,
                str(bet_relative.with_name("APPLICATION_EVIDENCE.json")),
                suffix=".json",
            )
            theory = _load_object(theory_path)
            application = _load_object(application_path)
            if theory is None:
                errors.append(f"invalid_theory_evidence:{bet_id}:THEORY_EVIDENCE.json is missing or invalid")
                theory = {}
            theory_findings = _validate_lane(
                theory,
                bet=bet,
                bet_id=bet_id,
                revision=bet.get("revision"),
                contract=THEORY_EVIDENCE,
                kind="theory",
                root=root,
            )
            for finding in theory_findings:
                errors.append(f"invalid_theory_evidence:{bet_id}:{finding}")
            if application is None:
                errors.append(f"invalid_application_evidence:{bet_id}:APPLICATION_EVIDENCE.json is missing or invalid")
                application = {}
            application_findings = _validate_lane(
                application,
                bet=bet,
                bet_id=bet_id,
                revision=bet.get("revision"),
                contract=APPLICATION_EVIDENCE,
                kind="application",
                root=root,
            )
            for finding in application_findings:
                errors.append(f"invalid_application_evidence:{bet_id}:{finding}")
            records[bet_id] = {
                "bet": bet,
                "theory": theory,
                "application": application,
                "bet_path": path,
                "theory_path": theory_path,
                "application_path": application_path,
                "theory_valid": not theory_findings,
                "application_valid": not application_findings,
            }

    decision_path = _safe_ref(
        root,
        "research/discovery/DECISION.json",
        suffix=".json",
    )
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

    handoff_lexical = discovery / "HANDOFF.json"
    if decision_name == "recommended":
        handoff_path = _safe_ref(
            root,
            "research/discovery/HANDOFF.json",
            suffix=".json",
        )
        handoff = _load_object(handoff_path)
        if handoff is None:
            errors.append("invalid_handoff:recommended decision requires HANDOFF.json")
        else:
            errors.extend(f"invalid_handoff:{finding}" for finding in _validate_handoff(handoff, decision, records, root))
    elif _path_present(handoff_lexical):
        errors.append("invalid_handoff:HANDOFF.json is allowed only for a recommended decision")

    if decision_name == "paused":
        errors.append("terminal_paused:paused discovery decisions are non-terminal")
    return errors


def completion_issue(project_root: Path | str) -> str:
    """Return the first stable completion blocker, or an empty string."""
    errors = validate_package(project_root)
    if not errors:
        return ""
    first_error = errors[0]
    if "missing or invalid" in first_error:
        return f"research_discovery:{first_error.split(':', 1)[0]}"
    # A changed BET revision makes all older lane and decision bindings stale.
    # Otherwise preserve the validator's structural-order finding.
    if any("bet_revision does not match BET.json revision" in error for error in errors):
        for error in errors:
            if error.startswith("stale_decision:"):
                return "research_discovery:stale_decision"
    return f"research_discovery:{first_error.split(':', 1)[0]}"


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
