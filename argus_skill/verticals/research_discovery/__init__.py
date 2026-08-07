"""Evidence validation for the built-in research-discovery Vertical."""
from __future__ import annotations

from typing import Any

__all__ = [
    "APPLICATION_EVIDENCE",
    "THEORY_EVIDENCE",
    "completion_issue",
    "content_digest",
    "main",
    "validate_package",
]


def __getattr__(name: str) -> Any:
    """Lazily expose evidence APIs without preloading ``python -m`` targets."""
    if name not in __all__:
        raise AttributeError(name)
    from . import evidence

    return getattr(evidence, name)
