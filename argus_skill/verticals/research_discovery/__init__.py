"""Built-in research-discovery Vertical."""
from __future__ import annotations

from typing import Any

from .stages import (
    CHECKLIST_ITEMS,
    CHECKLIST_STAGE_ORDER,
    COMPLETION_CONTRACT_VERSION,
    PROTECTED_ITEM_IDS,
    REQUIRE_INDEPENDENT_REVIEW,
    REVIEWER_CHECKLISTS,
    STAGE_CHECKS,
    STAGE_ORDER,
    WORKFLOW_MODE,
    completion_gate,
    role_banner,
)

__all__ = [
    "APPLICATION_EVIDENCE",
    "CHECKLIST_ITEMS",
    "CHECKLIST_STAGE_ORDER",
    "COMPLETION_CONTRACT_VERSION",
    "PROTECTED_ITEM_IDS",
    "REQUIRE_INDEPENDENT_REVIEW",
    "REVIEWER_CHECKLISTS",
    "STAGE_CHECKS",
    "STAGE_ORDER",
    "THEORY_EVIDENCE",
    "WORKFLOW_MODE",
    "completion_gate",
    "completion_issue",
    "content_digest",
    "main",
    "role_banner",
    "validate_package",
]

_EVIDENCE_EXPORTS = {
    "APPLICATION_EVIDENCE",
    "THEORY_EVIDENCE",
    "completion_issue",
    "content_digest",
    "main",
    "validate_package",
}


def __getattr__(name: str) -> Any:
    """Lazily expose evidence APIs without preloading ``python -m`` targets."""
    if name not in _EVIDENCE_EXPORTS:
        raise AttributeError(name)
    from . import evidence

    return getattr(evidence, name)
