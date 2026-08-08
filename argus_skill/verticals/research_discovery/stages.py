"""Four-stage contract for theory-application research discovery."""
from __future__ import annotations

from pathlib import Path

from ...skills.stage_machine import ChecklistItem

STAGE_ORDER = ("frame", "discover", "probe", "decide")
CHECKLIST_STAGE_ORDER = STAGE_ORDER
WORKFLOW_MODE = "proportional"
REQUIRE_INDEPENDENT_REVIEW = True
completion_gate = "none"
COMPLETION_CONTRACT_VERSION = 1
PROTECTED_ITEM_IDS = frozenset({
    "decide.package-valid",
    "decide.zero-or-one",
    "decide.dual-lane",
    "decide.handoff-valid",
    "decide.claim-ceiling",
})

_PIPELINE_CHECK = (
    "Pipeline state present",
    "test -f research/PIPELINE_STATE.json",
)

# Keep shell checks structural. The Reviewer and completion hook own scientific
# validity so textual scanners cannot certify the discovery package.
STAGE_CHECKS: dict[str, list[tuple[str, str]]] = {
    stage: [_PIPELINE_CHECK] for stage in STAGE_ORDER
}

REVIEWER_CHECKLISTS: dict[str, tuple[str, str, list[str]]] = {
    "frame": (
        "reviewer/research-discovery-review.md",
        "Confirm the real application problem, theoretical aperture, operating "
        "constraints, and decision-ready stopping boundary in BRIEF.md.",
        [],
    ),
    "discover": (
        "reviewer/research-discovery-review.md",
        "Check source-grounded, structurally distinct Research Bets, their nulls, "
        "load-bearing theory-application bridges, and unresolved novelty limits.",
        [],
    ),
    "probe": (
        "reviewer/research-discovery-review.md",
        "Check separately preregistered theory and application probes, raw evidence, "
        "and the separation of execution failure from scientific evidence.",
        [],
    ),
    "decide": (
        "reviewer/research-discovery-review.md",
        "Independently validate eligibility, evidence ceilings, freshness, zero-or-one "
        "selection, and the conditional downstream handoff.",
        [],
    ),
}

CHECKLIST_ITEMS: dict[str, tuple[ChecklistItem, ...]] = {
    "frame": (
        ChecklistItem(
            id="frame.problem-anchor",
            statement=(
                "The application context names the stakeholder, real workflow, baseline, "
                "observed failure or unmet need, and consequence of resolving it."
            ),
            evidence_hint="research/discovery/BRIEF.md problem anchor",
        ),
        ChecklistItem(
            id="frame.theory-aperture",
            statement=(
                "The theoretical aperture, operating constraints, and decision-ready stop "
                "condition are explicit without prematurely selecting a mechanism."
            ),
            evidence_hint="research/discovery/BRIEF.md theory aperture and constraints",
        ),
    ),
    "discover": (
        ChecklistItem(
            id="discover.portfolio-grounded",
            statement=(
                "The portfolio contains structurally distinct, source-grounded Research Bets "
                "and preserves nulls and failed searches."
            ),
            evidence_hint="research/discovery/PORTFOLIO.json and bets/<bet_id>/BET.json",
        ),
        ChecklistItem(
            id="discover.bridges-testable",
            statement=(
                "Each surviving Bet has a load-bearing theory-application bridge and an "
                "observable prediction that differs from its no-garnish counterfactual."
            ),
            evidence_hint="bridge and novelty fields in each referenced BET.json",
        ),
    ),
    "probe": (
        ChecklistItem(
            id="probe.preregistered-lanes",
            statement=(
                "Every finalist has separate minimum theory and application probes "
                "preregistered before their outcomes are interpreted."
            ),
            evidence_hint=(
                "bets/<bet_id>/THEORY_EVIDENCE.json and "
                "APPLICATION_EVIDENCE.json"
            ),
        ),
        ChecklistItem(
            id="probe.execution-evidence-separated",
            statement=(
                "Each lane records execution status, failure class, idea status, raw "
                "evidence, and scope limits without treating infrastructure failure as science."
            ),
            evidence_hint="THEORY_EVIDENCE.json and APPLICATION_EVIDENCE.json lane records",
        ),
    ),
    "decide": (
        ChecklistItem(
            id="decide.package-valid",
            statement="The canonical discovery package passes its machine validator.",
            evidence_hint="research/discovery/DECISION.json and current artifact digests",
        ),
        ChecklistItem(
            id="decide.zero-or-one",
            statement=(
                "The decision recommends exactly one eligible Bet or records a grounded "
                "no-bet result; a paused decision is not terminal."
            ),
            evidence_hint="research/discovery/DECISION.json selection and eligibility rows",
        ),
        ChecklistItem(
            id="decide.dual-lane",
            statement=(
                "Every selected or materially rejected Bet is supported by faithful, "
                "separately interpreted theory and application lane evidence."
            ),
            evidence_hint=(
                "BET.json plus THEORY_EVIDENCE.json and APPLICATION_EVIDENCE.json"
            ),
        ),
        ChecklistItem(
            id="decide.handoff-valid",
            statement=(
                "A recommended decision has a fresh, explicit downstream handoff, while "
                "no-bet and paused decisions do not create one."
            ),
            evidence_hint="conditional research/discovery/HANDOFF.json bound to DECISION.json",
        ),
        ChecklistItem(
            id="decide.claim-ceiling",
            statement=(
                "The final rationale and handoff stay within the evidence and proxy ceiling "
                "of both lanes and preserve unresolved external-validity limits."
            ),
            evidence_hint="DECISION.json claim ceilings, lane files, and conditional HANDOFF.json",
        ),
    ),
}


def completion_issue(project_root: object) -> str:
    from .evidence import completion_issue as validate_completion
    issue = validate_completion(project_root)
    if issue:
        return issue
    from .expansion import automatic_expansion_issue

    return automatic_expansion_issue(Path(project_root))


def after_mission(**context: object) -> dict[str, object]:
    """Reconcile the bounded Seed Project DAG after durable settlement."""
    from .expansion import reconcile_after_mission

    return reconcile_after_mission(**context)


def role_banner(role: str) -> str:
    """Load the discovery contract for a generic Argus role."""
    role_name = (role or "").strip().lower()
    skill_name = {
        "manager": "manager/research-discovery-manager.md",
        "planner": "planner/research-discovery-planning.md",
        "engineer": "engineer/idea-discovery.md",
        "reviewer": "reviewer/research-discovery-review.md",
        "scientist_create": "scientist/research-discovery-distillation.md",
        "scientist": "scientist/research-discovery-adaptation.md",
    }.get(role_name)
    if skill_name is None:
        return ""
    text = (Path(__file__).parent / "skills" / skill_name).read_text(encoding="utf-8")
    if text.startswith("---"):
        _frontmatter, _separator, body = text[3:].partition("---")
        return body.strip()
    return text.strip()


__all__ = [
    "CHECKLIST_ITEMS",
    "CHECKLIST_STAGE_ORDER",
    "COMPLETION_CONTRACT_VERSION",
    "PROTECTED_ITEM_IDS",
    "REQUIRE_INDEPENDENT_REVIEW",
    "REVIEWER_CHECKLISTS",
    "STAGE_CHECKS",
    "STAGE_ORDER",
    "WORKFLOW_MODE",
    "after_mission",
    "completion_gate",
    "completion_issue",
    "role_banner",
]
