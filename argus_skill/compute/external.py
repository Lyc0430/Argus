"""Canonical external-work records emitted by the compute broker."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path

from ..engineer.external_work import (
    EXTERNAL_WORK_PROTOCOL_VERSION,
    EXTERNAL_WORK_REGISTRY,
)


def safe_record_stem(job_key: str) -> str:
    label = re.sub(r"[^A-Za-z0-9-]+", "-", job_key).strip("-").lower()[:40]
    digest = hashlib.sha256(job_key.encode("utf-8")).hexdigest()[:16]
    return f"{label or 'job'}-{digest}"


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.writing-{os.getpid()}-{uuid.uuid4().hex}")
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False
    )
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_planned_external_work(
    project_root: Path,
    *,
    job_key: str,
    provider: str,
    plan_path: str,
) -> Path:
    record_path = (
        project_root / EXTERNAL_WORK_REGISTRY / f"{safe_record_stem(job_key)}.json"
    )
    atomic_write_json(
        record_path,
        {
            "version": EXTERNAL_WORK_PROTOCOL_VERSION,
            "work_id": job_key,
            "state": "terminal",
            "description": f"dry-run {provider} compute plan",
            "source": "compute_broker",
            "heartbeat_at": time.time(),
            "stale_after_seconds": 1800,
            "poll_after_seconds": 120,
            "outcome": "planned_dry_run",
            "reason": "live execution is disabled in the standard broker phase",
            "evidence_paths": [plan_path],
            "activity_paths": [],
        },
    )
    return record_path


__all__ = ["atomic_write_json", "safe_record_stem", "write_planned_external_work"]
