"""Typed, append-only cross-project memory for rejected Research Bets."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

try:  # pragma: no cover - production daemons are POSIX
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

_ID = re.compile(r"^[A-Za-z0-9_-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"[\w-]{2,}", re.UNICODE)
_FAILURE_CLASSES = frozenset(
    {
        "scientific_rejection",
        "novelty_collision",
        "grounded_rejection",
        "stagnated_twice",
    }
)
_MAX_SCAN_BYTES = 2_000_000
_MAX_SCAN_RECORDS = 512
_THREAD_LOCKS: dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _text(value: object) -> str:
    return str(value or "").strip() if isinstance(value, str) else ""


def _string_list(value: object, *, allow_empty: bool = False) -> list[str] | None:
    if not isinstance(value, list) or any(not _text(item) for item in value):
        return None
    if not allow_empty and not value:
        return None
    return [str(item).strip() for item in value]


def validate_capsule(
    payload: object,
    *,
    expected_event_id: str = "",
) -> tuple[str, ...]:
    """Return stable structural findings for one Rejection Capsule."""
    if not isinstance(payload, Mapping):
        return ("capsule must be a JSON object",)
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    event_id = _text(payload.get("event_id"))
    if not _ID.fullmatch(event_id):
        errors.append("event_id must be a safe identifier")
    if expected_event_id and event_id != expected_event_id:
        errors.append("event_id does not match the expected event")
    bet_ids = _string_list(payload.get("source_bet_ids"))
    if bet_ids is None or any(not _ID.fullmatch(item) for item in bet_ids):
        errors.append("source_bet_ids must contain safe Bet identifiers")
    decision_sha = _text(payload.get("source_decision_sha256"))
    if not _SHA256.fullmatch(decision_sha):
        errors.append("source_decision_sha256 must be a lowercase SHA-256")
    if payload.get("failure_class") not in _FAILURE_CLASSES:
        errors.append("failure_class is invalid")
    for field in (
        "killed_premise",
        "open_tension",
        "mutation_demand",
    ):
        if not _text(payload.get(field)):
            errors.append(f"{field} must be non-empty text")
    for field in (
        "survivors",
        "forbidden_region",
        "structure_tags",
        "artifact_refs",
    ):
        if _string_list(payload.get(field)) is None:
            errors.append(f"{field} must be a non-empty list of strings")
    return tuple(errors)


def _tokens(*values: object) -> set[str]:
    return {
        token.casefold()
        for value in values
        for token in _TOKEN.findall(str(value or ""))
    }


@dataclass(frozen=True)
class ResearchExperienceHit:
    capsule: dict[str, Any]
    channel: str


class ResearchExperienceGraph:
    """Bounded advisory retrieval over append-only Rejection Capsules."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock_path = self.path.with_suffix(self.path.suffix + ".lock")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        key = str(self._lock_path.resolve())
        with _THREAD_LOCKS_GUARD:
            thread_lock = _THREAD_LOCKS.setdefault(key, threading.Lock())
        with thread_lock, self._lock_path.open("a+b") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _bounded_rows(
        self,
        *,
        max_bytes: int = _MAX_SCAN_BYTES,
        max_records: int = _MAX_SCAN_RECORDS,
    ) -> list[dict[str, Any]]:
        if max_bytes <= 0 or max_records <= 0 or not self.path.is_file():
            return []
        try:
            with self.path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                size = handle.tell()
                start = max(0, size - max_bytes)
                handle.seek(start)
                data = handle.read(max_bytes)
        except OSError:
            return []
        if start:
            newline = data.find(b"\n")
            data = data[newline + 1 :] if newline >= 0 else b""
        rows: list[dict[str, Any]] = []
        for raw in data.splitlines()[-max_records:]:
            try:
                row = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(row, dict) and row.get("record_type") == "capsule":
                rows.append(row)
        return rows

    @staticmethod
    def _capsule_id(payload: Mapping[str, Any], source_project_id: str) -> str:
        material = ":".join(
            (
                source_project_id,
                _text(payload.get("event_id")),
                _text(payload.get("source_decision_sha256")),
            )
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]

    def append(self, payload: object, *, source_project_id: str) -> str:
        errors = validate_capsule(payload)
        if errors:
            raise ValueError("; ".join(errors))
        if not _ID.fullmatch(str(source_project_id or "")):
            raise ValueError("source_project_id must be a safe identifier")
        capsule = dict(payload)  # type: ignore[arg-type]
        capsule_id = self._capsule_id(capsule, source_project_id)
        row = {
            "record_type": "capsule",
            "capsule_id": capsule_id,
            "source_project_id": source_project_id,
            "imported_at": time.time(),
            **capsule,
        }
        with self._locked():
            if any(
                existing.get("capsule_id") == capsule_id
                for existing in self._bounded_rows()
            ):
                return capsule_id
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                )
                handle.flush()
                os.fsync(handle.fileno())
        return capsule_id

    def import_capsule(
        self,
        path: Path,
        *,
        expected_event_id: str,
        source_project_id: str,
    ) -> str | None:
        candidate = Path(path)
        if candidate.is_symlink() or not candidate.is_file():
            return None
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if validate_capsule(payload, expected_event_id=expected_event_id):
            return None
        return self.append(payload, source_project_id=source_project_id)

    def recent(self, *, max_entries: int = 64) -> list[dict[str, Any]]:
        if max_entries <= 0:
            return []
        seen: set[str] = set()
        recent: list[dict[str, Any]] = []
        for row in reversed(self._bounded_rows()):
            capsule_id = _text(row.get("capsule_id"))
            if not capsule_id or capsule_id in seen:
                continue
            if validate_capsule(row):
                continue
            seen.add(capsule_id)
            recent.append(row)
            if len(recent) >= max_entries:
                break
        return recent

    def retrieve(
        self,
        objective: str,
        *,
        open_tension: str = "",
        structure_tags: list[str] | None = None,
        current_project_id: str = "",
        max_entries: int = 3,
    ) -> list[ResearchExperienceHit]:
        candidates = self.recent(max_entries=64)
        if not candidates or max_entries <= 0:
            return []
        domain_query = _tokens(objective)
        structure_query = _tokens(open_tension, *(structure_tags or []))

        def domain_score(row: Mapping[str, Any]) -> int:
            return len(
                domain_query
                & _tokens(
                    row.get("killed_premise"),
                    *(row.get("survivors") or []),
                    *(row.get("forbidden_region") or []),
                    row.get("open_tension"),
                    *(row.get("structure_tags") or []),
                )
            )

        def structure_score(row: Mapping[str, Any]) -> int:
            return len(
                structure_query
                & _tokens(
                    row.get("open_tension"),
                    row.get("mutation_demand"),
                    *(row.get("structure_tags") or []),
                )
            )

        hits: list[ResearchExperienceHit] = []
        selected: set[str] = set()

        def add(row: dict[str, Any], channel: str) -> None:
            capsule_id = _text(row.get("capsule_id"))
            if capsule_id and capsule_id not in selected and len(hits) < max_entries:
                selected.add(capsule_id)
                hits.append(ResearchExperienceHit(row, channel))

        near = max(
            candidates,
            key=lambda row: (
                _text(row.get("source_project_id")) == current_project_id,
                domain_score(row),
                structure_score(row),
                row.get("imported_at", 0),
            ),
        )
        add(near, "near")
        remaining = [
            row for row in candidates if _text(row.get("capsule_id")) not in selected
        ]
        if remaining and len(hits) < max_entries:
            structural = max(
                remaining,
                key=lambda row: (
                    structure_score(row),
                    domain_score(row),
                    row.get("imported_at", 0),
                ),
            )
            add(structural, "structural")
        remaining = [
            row for row in candidates if _text(row.get("capsule_id")) not in selected
        ]
        if remaining and len(hits) < max_entries:
            cross_project = [
                row
                for row in remaining
                if _text(row.get("source_project_id")) != current_project_id
                and structure_score(row) > 0
            ]
            pool = cross_project or [
                row for row in remaining if structure_score(row) > 0
            ] or remaining
            far = min(
                pool,
                key=lambda row: (
                    domain_score(row),
                    -structure_score(row),
                    -float(row.get("imported_at", 0) or 0),
                ),
            )
            add(far, "far")
        return hits


__all__ = [
    "ResearchExperienceGraph",
    "ResearchExperienceHit",
    "validate_capsule",
]
