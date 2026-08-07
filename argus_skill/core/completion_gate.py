"""Combined external and active-Vertical project completion gate."""

from __future__ import annotations

from pathlib import Path

from ..skills.vertical_select import resolve_vertical
from ..verticals._base import load_vertical, vertical_completion_issue
from .external_completion_gate import external_completion_gate_issue


def project_completion_issue(project_root: Path | str) -> str:
    """Return the first external or active-Vertical completion issue."""
    external = external_completion_gate_issue(project_root)
    if external:
        return external
    try:
        vertical = resolve_vertical(project_root)
        module = load_vertical(vertical, project_root=project_root)
    except Exception as exc:  # noqa: BLE001 — completion must fail closed
        return f"vertical completion check unavailable: {type(exc).__name__}"
    return vertical_completion_issue(module, project_root)


__all__ = ["project_completion_issue"]
