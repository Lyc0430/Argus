"""Bounded automatic continuation for Research Discovery Seed Projects."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from ...life.memory import Backlog, BacklogItem
from .evidence import validate_package
from .experience_graph import ResearchExperienceGraph

try:  # pragma: no cover - production daemons are POSIX
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_ACTIVE_STATES = frozenset({"probe", "select"})
_DEFAULT_POLICY: dict[str, Any] = {
    "enabled": True,
    "automation": "full",
    "max_active_bets": 5,
    "stagnation_threshold": 2,
    "branch_modes": ["near", "far"],
    "max_expansion_events": 8,
    "max_repair_attempts": 2,
}
_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True)
class ResearchOutcome:
    """Evidence-authoritative outcome used by the automatic controller."""

    kind: str
    decision_sha256: str = ""
    premise_family: str = ""
    source_bet_ids: tuple[str, ...] = ()
    failed_gates: tuple[str, ...] = ()
    active_bets: int = 0
    decision: Mapping[str, Any] | None = None
    diagnostic: str = ""


def _discovery(root: Path) -> Path:
    return root / "research" / "discovery"


def _state_path(root: Path) -> Path:
    return _discovery(root) / "AUTO_EXPANSION.json"


def _discovery_root_is_safe(root: Path) -> bool:
    research = root / "research"
    discovery = research / "discovery"
    try:
        return (
            research.is_dir()
            and not research.is_symlink()
            and discovery.is_dir()
            and not discovery.is_symlink()
        )
    except OSError:
        return False


def _load_object(path: Path) -> dict[str, Any] | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    candidate = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(candidate, path)
    finally:
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def _controller_lock(root: Path) -> Iterator[None]:
    lock_path = _discovery(root) / "expansion.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    key = str(lock_path.resolve())
    with _THREAD_LOCKS_GUARD:
        thread_lock = _THREAD_LOCKS.setdefault(key, threading.RLock())
    with thread_lock, lock_path.open("a+b") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _safe_project_id(value: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "")).strip("-")
    return candidate[:64] if candidate and _SAFE_ID.fullmatch(candidate[:64]) else "seed-project"


def initialize_seed_project(project_root: Path, *, project_id: str) -> dict[str, Any]:
    """Initialize a Seed Project exactly once from its first portfolio objective."""
    root = Path(project_root).resolve()
    if not _discovery_root_is_safe(root):
        raise ValueError("research/discovery must be a real project-local directory")
    state_path = _state_path(root)
    with _controller_lock(root):
        existing = _load_object(state_path)
        if existing is not None:
            return existing
        if state_path.exists() or state_path.is_symlink():
            raise ValueError("automatic expansion state is malformed or unsafe")
        portfolio = _load_object(_discovery(root) / "PORTFOLIO.json") or {}
        objective = str(portfolio.get("objective") or "").strip()
        if not objective:
            raise ValueError("portfolio objective is required to initialize a Seed Project")
        state: dict[str, Any] = {
            "schema_version": 1,
            "project_id": _safe_project_id(project_id),
            "initialization_point": objective,
            "policy": dict(_DEFAULT_POLICY),
            "processed_decisions": [],
            "stagnation": {},
            "requests": {},
            "graph_snapshot": [],
            "status": "active",
        }
        _atomic_json(state_path, state)
        return state


def _canonical_bets(root: Path) -> list[dict[str, Any]] | None:
    portfolio = _load_object(_discovery(root) / "PORTFOLIO.json")
    if portfolio is None or not isinstance(portfolio.get("bet_refs"), list):
        return None
    bets: list[dict[str, Any]] = []
    for raw_ref in portfolio["bet_refs"]:
        if not isinstance(raw_ref, str):
            return None
        match = re.fullmatch(r"research/discovery/bets/([A-Za-z0-9_-]+)/BET\.json", raw_ref)
        if match is None:
            return None
        path = root / raw_ref
        bet = _load_object(path)
        if bet is None or bet.get("id") != match.group(1):
            return None
        bet["_path"] = raw_ref
        bets.append(bet)
    return bets


def _decision_digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        return ""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _premise_family(bets: list[Mapping[str, Any]]) -> str:
    material = []
    for bet in bets:
        theory = bet.get("theory_anchor")
        application = bet.get("application_test")
        material.append(
            {
                "id": bet.get("id"),
                "candidate_premise": bet.get("candidate_premise"),
                "theory": theory.get("binding_premise") if isinstance(theory, Mapping) else None,
                "application": (
                    application.get("binding_premise")
                    if isinstance(application, Mapping)
                    else None
                ),
            }
        )
    raw = json.dumps(material, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def classify_current_outcome(
    project_root: Path,
    state: Mapping[str, Any],
) -> ResearchOutcome:
    """Classify only canonical, current discovery evidence; raw task status is ignored."""
    del state  # policy affects actions, never the evidence classification
    root = Path(project_root).resolve()
    findings = validate_package(root)
    paused_only = findings == [
        "terminal_paused:paused discovery decisions are non-terminal"
    ]
    if findings and not paused_only:
        return ResearchOutcome("invalid", diagnostic=findings[0])
    decision_path = _discovery(root) / "DECISION.json"
    decision = _load_object(decision_path)
    bets = _canonical_bets(root)
    digest = _decision_digest(decision_path)
    if decision is None or bets is None or not digest:
        return ResearchOutcome("invalid", diagnostic="unsafe or malformed canonical package")
    eligibility = decision.get("eligibility")
    if not isinstance(eligibility, list) or any(not isinstance(row, dict) for row in eligibility):
        return ResearchOutcome("invalid", diagnostic="invalid eligibility rows")
    source_ids = tuple(
        str(row.get("bet_id"))
        for row in eligibility
        if isinstance(row.get("bet_id"), str)
    )
    failed_gates = tuple(
        gate
        for row in eligibility
        for gate in (row.get("failed_gates") or [])
        if isinstance(gate, str)
    )
    bases = {
        str(row.get("decision_basis"))
        for row in eligibility
        if isinstance(row.get("decision_basis"), str)
    }
    common = {
        "decision_sha256": digest,
        "premise_family": _premise_family(bets),
        "source_bet_ids": source_ids,
        "failed_gates": failed_gates,
        "active_bets": sum(bet.get("candidate_state") in _ACTIVE_STATES for bet in bets),
        "decision": decision,
    }
    name = decision.get("decision")
    if name == "recommended" and not findings:
        return ResearchOutcome("eligible", **common)
    if name == "paused" and paused_only:
        if "blocked_probe" in bases:
            return ResearchOutcome("execution_blocked", **common)
        if "completed_probe" in bases:
            return ResearchOutcome("stagnating", **common)
        return ResearchOutcome("invalid", diagnostic="paused decision has no actionable basis")
    if name != "no_bet" or findings:
        return ResearchOutcome("invalid", diagnostic="decision state is not reconcilable")
    if "pre_probe_gate" in bases:
        kind = "novelty_collision" if "nearest_work" in failed_gates else "grounded_rejection"
        return ResearchOutcome(kind, **common)
    if "completed_probe" in bases:
        return ResearchOutcome("scientific_rejection", **common)
    return ResearchOutcome("grounded_rejection", **common)


def _graph_snapshot(root: Path, bets: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "bet_id": str(bet.get("id") or ""),
            "candidate_state": str(bet.get("candidate_state") or ""),
            "lineage": dict(bet.get("lineage")) if isinstance(bet.get("lineage"), Mapping) else None,
        }
        for bet in bets
    ]


def _request_objective(request: Mapping[str, Any]) -> str:
    path = str(request["request_ref"])
    action = request["action"]
    if action == "repair_probe":
        return (
            f"Execute the bounded repair in {path}. Repair only the blocked/failed probe "
            "and refresh canonical evidence. Do not create a new Research Bet and do not "
            "treat execution failure as scientific evidence."
        )
    if action == "probe_redesign":
        return (
            f"Execute the probe-redesign request in {path}. Preserve the current Bet and "
            "premise family, design one cheaper faithful discriminator, and refresh the "
            "paused canonical decision. Do not relabel an inconclusive probe as rejection."
        )
    return (
        f"Execute the automatic expansion request in {path}. Write the exact Rejection "
        "Capsule; preserve the application anchor and live siblings; derive exactly one "
        "near and one far Bet by changing mechanism, estimand, or prediction; give the far "
        "Bet a source-domain mechanism, target-role mapping, negative-transfer boundary, "
        "new prediction, and discriminating target-domain probe; keep at most five active "
        "Bets; then refresh the canonical portfolio, evidence, and decision."
    )


def _event_id(project_id: str, result: ResearchOutcome, action: str) -> str:
    material = ":".join(
        (project_id, result.decision_sha256, result.kind, result.premise_family, action, "v1")
    )
    return "evt-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def _request_task(request: Mapping[str, Any]) -> BacklogItem:
    action = str(request["action"])
    event_id = str(request["event_id"])
    label = {
        "derive_near_far": "Derive near and far Research Bets",
        "probe_redesign": "Redesign an information-free probe",
        "repair_probe": "Repair a blocked research probe",
    }[action]
    return BacklogItem.new(
        item_id=f"rd-{action.replace('_', '-')}-{event_id.removeprefix('evt-')}",
        title=label,
        objective=_request_objective(request),
        priority=30,
        tags=["research-discovery", "automatic-expansion", action],
        node_key=f"research-discovery:{action}:{event_id}",
        context_refs=[
            {"kind": "expansion_request", "path": str(request["request_ref"])},
            {"kind": "decision", "path": "research/discovery/DECISION.json"},
        ],
        iterate=False,
        iteration_max_cycles=1,
        deps=[],
        acceptance_check=(
            "The exact request is resolved in current canonical artifacts without "
            "converting an execution failure into scientific evidence."
        ),
        non_goals=["cross-Vertical handoff", "paper completion", "production deployment"],
    )


def _write_immutable(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    existing = _load_object(path)
    if existing is not None:
        binding_fields = (
            "schema_version",
            "event_id",
            "project_id",
            "trigger",
            "action",
            "decision_sha256",
            "premise_family",
            "source_bet_ids",
            "failed_gates",
            "branch_modes",
            "request_ref",
        )
        if any(existing.get(field) != payload.get(field) for field in binding_fields):
            raise ValueError(f"immutable expansion request changed: {path.name}")
        return existing
    if path.exists() or path.is_symlink():
        raise ValueError(f"unsafe expansion request path: {path.name}")
    _atomic_json(path, payload)
    return dict(payload)


def _reconcile_prior_requests(
    *,
    root: Path,
    global_root: Path,
    backlog: Backlog,
    state: dict[str, Any],
    current_digest: str,
) -> bool:
    changed = False
    by_id = {item.id: item for item in backlog.all()}
    graph = ResearchExperienceGraph(global_root / "research" / "experience_graph.jsonl")
    policy = state.get("policy") if isinstance(state.get("policy"), dict) else {}
    repair_limit = max(0, int(policy.get("max_repair_attempts", 2) or 0))
    requests = state.get("requests")
    if not isinstance(requests, dict):
        state["requests"] = {}
        return True
    for event_id, record in list(requests.items()):
        if not isinstance(record, dict):
            continue
        task_id = str(record.get("task_id") or "")
        task = by_id.get(task_id)
        if current_digest and current_digest != record.get("decision_sha256"):
            if record.get("status") != "completed":
                record["status"] = "completed"
                changed = True
        elif task is not None and record.get("status") != task.status:
            record["status"] = task.status
            changed = True
        capsule_path = _discovery(root) / "rejections" / f"{event_id}.json"
        capsule_id = graph.import_capsule(
            capsule_path,
            expected_event_id=event_id,
            source_project_id=str(state.get("project_id") or "seed-project"),
        )
        if capsule_id and record.get("capsule_id") != capsule_id:
            record["capsule_id"] = capsule_id
            changed = True
        if task is None or task.status not in {"failed", "skipped"}:
            continue
        attempts = max(0, int(record.get("repair_attempts", 0) or 0))
        if attempts >= repair_limit:
            if record.get("status") != "blocked":
                record["status"] = "blocked"
                changed = True
            continue
        attempt = attempts + 1
        repair_id = f"{task_id}-repair-{attempt}"
        repair = BacklogItem.new(
            item_id=repair_id,
            title="Repair automatic research continuation",
            objective=(
                f"Repair execution of research/discovery/expansion/requests/{event_id}.json "
                "without creating additional Ideas or treating the failed execution as evidence."
            ),
            priority=25,
            tags=["research-discovery", "automatic-expansion", "execution-repair"],
            node_key=f"research-discovery:repair:{event_id}:{attempt}",
            iterate=False,
            iteration_max_cycles=1,
            deps=[],
        )
        backlog.ensure_many([repair])
        record.update(
            status="repair_pending",
            task_id=repair_id,
            repair_attempts=attempt,
        )
        changed = True
    return changed


def reconcile_after_mission(
    *,
    project_root: object,
    state_root: object,
    global_root: object,
    backlog: object,
    outcome: object,
) -> dict[str, Any]:
    """Persist and enqueue the next bounded research action, if evidence warrants it."""
    del outcome  # mission/runtime outcome is diagnostic, never scientific evidence
    root = Path(project_root).resolve()
    if not isinstance(backlog, Backlog):
        return {"status": "invalid", "reason": "backlog unavailable"}
    try:
        initialize_seed_project(root, project_id=Path(state_root).name)
    except (OSError, TypeError, ValueError):
        return {"status": "invalid", "reason": "seed initialization failed"}

    with _controller_lock(root):
        state = _load_object(_state_path(root))
        if state is None or state.get("schema_version") != 1:
            return {"status": "invalid", "reason": "automatic expansion state invalid"}
        result = classify_current_outcome(root, state)
        prior_changed = _reconcile_prior_requests(
            root=root,
            global_root=Path(global_root).resolve(),
            backlog=backlog,
            state=state,
            current_digest=result.decision_sha256,
        )
        if prior_changed:
            _atomic_json(_state_path(root), state)
        if result.kind == "invalid":
            return {"status": "invalid", "reason": result.diagnostic}
        processed = state.get("processed_decisions")
        if not isinstance(processed, list):
            processed = []
            state["processed_decisions"] = processed
        if result.decision_sha256 in processed:
            return {"status": "already_processed", "outcome": result.kind}
        policy = state.get("policy")
        if not isinstance(policy, dict) or policy.get("enabled") is not True:
            return {"status": "disabled"}
        max_active = max(1, int(policy.get("max_active_bets", 5) or 5))
        if result.active_bets > max_active:
            state["status"] = "frontier_invalid"
            _atomic_json(_state_path(root), state)
            return {"status": "frontier_invalid", "active_bets": result.active_bets}
        if result.kind == "eligible":
            processed.append(result.decision_sha256)
            state["status"] = "eligible"
            _atomic_json(_state_path(root), state)
            return {"status": "eligible", "action": "none"}

        action = "derive_near_far"
        if result.kind == "execution_blocked":
            action = "repair_probe"
        elif result.kind == "stagnating":
            stagnation = state.get("stagnation")
            if not isinstance(stagnation, dict):
                stagnation = {}
                state["stagnation"] = stagnation
            observations = stagnation.setdefault(result.premise_family, [])
            if not isinstance(observations, list):
                observations = []
                stagnation[result.premise_family] = observations
            if result.decision_sha256 not in observations:
                observations.append(result.decision_sha256)
            threshold = max(2, int(policy.get("stagnation_threshold", 2) or 2))
            action = "derive_near_far" if len(observations) >= threshold else "probe_redesign"

        requests = state.get("requests")
        if not isinstance(requests, dict):
            requests = {}
            state["requests"] = requests
        if action == "repair_probe":
            repair_limit = max(
                0,
                int(policy.get("max_repair_attempts", 2) or 0),
            )
            repair_count = sum(
                isinstance(record, dict)
                and record.get("action") == "repair_probe"
                and record.get("premise_family") == result.premise_family
                for record in requests.values()
            )
            if repair_count >= repair_limit:
                processed.append(result.decision_sha256)
                state["status"] = "repair_exhausted"
                _atomic_json(_state_path(root), state)
                return {"status": "repair_exhausted", "action": "none"}
        expansion_count = sum(
            isinstance(record, dict) and record.get("action") == "derive_near_far"
            for record in requests.values()
        )
        expansion_limit = max(0, int(policy.get("max_expansion_events", 8) or 0))
        if action == "derive_near_far" and expansion_count >= expansion_limit:
            processed.append(result.decision_sha256)
            state["status"] = "frontier_exhausted"
            _atomic_json(_state_path(root), state)
            return {"status": "frontier_exhausted", "action": "none"}

        event_id = _event_id(str(state.get("project_id") or "seed-project"), result, action)
        relative_request = f"research/discovery/expansion/requests/{event_id}.json"
        graph = ResearchExperienceGraph(
            Path(global_root).resolve() / "research" / "experience_graph.jsonl"
        )
        hits = graph.retrieve(
            str(state.get("initialization_point") or ""),
            open_tension=result.premise_family,
            current_project_id=str(state.get("project_id") or ""),
            max_entries=3,
        )
        request: dict[str, Any] = {
            "schema_version": 1,
            "event_id": event_id,
            "project_id": state.get("project_id"),
            "trigger": result.kind,
            "action": action,
            "decision_sha256": result.decision_sha256,
            "premise_family": result.premise_family,
            "source_bet_ids": list(result.source_bet_ids),
            "failed_gates": list(result.failed_gates),
            "branch_modes": list(policy.get("branch_modes") or ["near", "far"]),
            "available_frontier_slots": max(0, max_active - result.active_bets),
            "experience_hits": [
                {
                    "channel": hit.channel,
                    "capsule_id": hit.capsule.get("capsule_id"),
                    "source_project_id": hit.capsule.get("source_project_id"),
                    "event_id": hit.capsule.get("event_id"),
                }
                for hit in hits
            ],
            "required_outputs": (
                ["rejection_capsule", "near_bet", "far_bet", "minimum_probes", "decision"]
                if action == "derive_near_far"
                else ["repaired_probe", "evidence", "decision"]
                if action == "repair_probe"
                else ["redesigned_probe", "evidence", "decision"]
            ),
            "request_ref": relative_request,
        }
        request_path = root / relative_request
        request = _write_immutable(request_path, request)
        task = _request_task(request)
        backlog.ensure_many([task])
        requests[event_id] = {
            "action": action,
            "decision_sha256": result.decision_sha256,
            "premise_family": result.premise_family,
            "task_id": task.id,
            "status": task.status,
            "repair_attempts": 1 if action == "repair_probe" else 0,
            "request_ref": relative_request,
        }
        processed.append(result.decision_sha256)
        bets = _canonical_bets(root) or []
        state["graph_snapshot"] = _graph_snapshot(root, bets)
        state["status"] = "active"
        _atomic_json(_state_path(root), state)
        return {
            "status": "enqueued",
            "action": action,
            "event_id": event_id,
            "task_id": task.id,
            "request_path": str(request_path),
        }


def automatic_expansion_issue(project_root: Path) -> str:
    """Return an automatic-portfolio completion blocker, if initialized."""
    root = Path(project_root).resolve()
    path = _state_path(root)
    if not path.exists() and not path.is_symlink():
        return ""
    state = _load_object(path)
    if state is None or state.get("schema_version") != 1:
        return "research_discovery:invalid_auto_expansion"
    requests = state.get("requests")
    if isinstance(requests, dict) and any(
        isinstance(record, dict)
        and record.get("status") in {"pending", "running", "repair_pending", "blocked"}
        for record in requests.values()
    ):
        return "research_discovery:automatic_expansion_pending"
    if state.get("status") == "frontier_exhausted":
        return ""
    bets = _canonical_bets(root)
    policy = state.get("policy") if isinstance(state.get("policy"), dict) else {}
    if bets is None:
        return "research_discovery:invalid_auto_expansion"
    active = sum(bet.get("candidate_state") in _ACTIVE_STATES for bet in bets)
    if active > max(1, int(policy.get("max_active_bets", 5) or 5)):
        return "research_discovery:automatic_frontier_exceeds_limit"
    if state.get("status") == "frontier_invalid":
        return "research_discovery:automatic_frontier_invalid"
    if state.get("status") == "repair_exhausted":
        return "research_discovery:automatic_repair_exhausted"
    return ""


__all__ = [
    "ResearchOutcome",
    "automatic_expansion_issue",
    "classify_current_outcome",
    "initialize_seed_project",
    "reconcile_after_mission",
]
