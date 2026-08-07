"""Validated dry-run plans for Tinker sampling and LoRA prototypes.

This module intentionally does not import the optional Tinker SDK. A future live
adapter must perform the capability check described by the plan and remain
behind a separately reviewed execution boundary.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

from .budget import Reservation
from .models import ComputeRequest, TaskKind

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TINKER_JOB_CAPS = {
    TaskKind.PROMPT_SANITY: 50.0,
    TaskKind.SAMPLING: 50.0,
    TaskKind.LORA_PROTOTYPE: 200.0,
}


class TinkerPlanError(ValueError):
    """A request cannot be represented as a safe Tinker dry-run plan."""


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise TinkerPlanError(f"{field} must be a positive integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise TinkerPlanError(f"{field} must be a positive integer") from exc
    if result <= 0 or str(value).strip() not in {str(result), f"{result}.0"}:
        raise TinkerPlanError(f"{field} must be a positive integer")
    return result


def _safe_relative_path(value: object, *, field: str) -> str:
    candidate = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(candidate)
    if not candidate or candidate.startswith("/") or ".." in path.parts:
        raise TinkerPlanError(f"{field} must be a safe project-relative path")
    return path.as_posix()


@dataclass(frozen=True)
class PriceSnapshot:
    source: str
    sha256: str
    captured_at: str = ""

    def __post_init__(self) -> None:
        parsed = urlparse(str(self.source or ""))
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Tinker price snapshot source must be an HTTPS URL")
        digest = str(self.sha256 or "").strip().lower()
        if not _SHA256.fullmatch(digest):
            raise ValueError("Tinker price snapshot sha256 must be 64 hex characters")
        object.__setattr__(self, "sha256", digest)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class TinkerCapabilities:
    supported_models: tuple[str, ...]
    max_concurrent_requests: int | None = None

    def __post_init__(self) -> None:
        normalized = tuple(
            dict.fromkeys(str(model or "").strip() for model in self.supported_models)
        )
        if any(not model for model in normalized):
            raise ValueError("supported_models cannot contain an empty model id")
        object.__setattr__(self, "supported_models", normalized)
        if self.max_concurrent_requests is not None:
            maximum = _positive_int(
                self.max_concurrent_requests, field="max_concurrent_requests"
            )
            object.__setattr__(self, "max_concurrent_requests", maximum)


@dataclass(frozen=True)
class TinkerPlan:
    version: int
    provider: str
    job_key: str
    mission_id: str
    project_id: str
    model: str
    task_kind: str
    prompt_file: str
    prompt_count: int
    request_count: int
    num_samples: int
    completion_count: int
    max_tokens: int
    temperature: float
    concurrency_limit: int
    concurrency_source: str
    execution_pattern: str
    sdk_retry_owned: bool
    client_timeout_seconds: None
    requires_live_capability_check: bool
    create_new_sampler_after_weights: bool
    reservation_id: str
    reserved_usd: str
    price_snapshot: dict[str, str]
    output_paths: tuple[str, ...]
    frozen: bool = False

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["output_paths"] = list(self.output_paths)
        return result


def build_tinker_plan(
    request: ComputeRequest,
    *,
    reservation: Reservation,
    price_snapshot: PriceSnapshot,
    capabilities: TinkerCapabilities | None = None,
) -> TinkerPlan:
    """Build a non-executing Tinker plan from one admitted request."""
    if request.frozen:
        raise TinkerPlanError("Tinker plans require evidence_class exploratory and frozen:false")
    cap = _TINKER_JOB_CAPS.get(request.task_kind)
    if cap is None:
        raise TinkerPlanError(
            f"task_kind={request.task_kind.value} is not a legal Tinker workload"
        )
    if request.estimated_cost_usd > cap:
        raise TinkerPlanError(
            f"{request.task_kind.value} exceeds the Tinker per-job cap ${cap:.0f}"
        )
    if reservation.job_key != request.job_key:
        raise TinkerPlanError("reservation job_key does not match ComputeRequest")
    if float(reservation.estimated_cost_usd) != request.estimated_cost_usd:
        raise TinkerPlanError("reservation estimate does not match ComputeRequest")
    if capabilities is not None and request.model not in capabilities.supported_models:
        raise TinkerPlanError(
            f"model {request.model!r} is not present in Tinker capabilities"
        )
    workload = dict(request.workload or {})
    if workload.get("sequential") is True:
        raise TinkerPlanError("Tinker prompt requests must be submitted concurrently")
    if "client_timeout_seconds" in workload:
        raise TinkerPlanError(
            "do not wrap Tinker sample_async calls in a client timeout"
        )
    if "retry_count" in workload:
        raise TinkerPlanError("Tinker transient retry is owned by the SDK")
    prompt_file = _safe_relative_path(workload.get("prompt_file"), field="prompt_file")
    prompt_count = _positive_int(workload.get("prompt_count"), field="prompt_count")
    num_samples = _positive_int(workload.get("num_samples", 1), field="num_samples")
    max_tokens = _positive_int(workload.get("max_tokens"), field="max_tokens")
    try:
        temperature = float(workload.get("temperature", 1.0))
    except (TypeError, ValueError) as exc:
        raise TinkerPlanError("temperature must be numeric") from exc
    if temperature < 0 or temperature != temperature:
        raise TinkerPlanError("temperature must be finite and non-negative")
    if request.task_kind is TaskKind.LORA_PROTOTYPE:
        _safe_relative_path(workload.get("training_recipe"), field="training_recipe")
    if capabilities is not None and capabilities.max_concurrent_requests is not None:
        concurrency_limit = min(
            prompt_count, capabilities.max_concurrent_requests
        )
        concurrency_source = "server_capabilities"
    else:
        # This is not a client-side throttle: it means all prompt requests are
        # submitted together and the SDK/service controls actual scheduling.
        concurrency_limit = prompt_count
        concurrency_source = "sdk_managed"
    return TinkerPlan(
        version=1,
        provider="tinker",
        job_key=request.job_key,
        mission_id=request.mission_id,
        project_id=request.project,
        model=request.model,
        task_kind=request.task_kind.value,
        prompt_file=prompt_file,
        prompt_count=prompt_count,
        request_count=prompt_count,
        num_samples=num_samples,
        completion_count=prompt_count * num_samples,
        max_tokens=max_tokens,
        temperature=temperature,
        concurrency_limit=concurrency_limit,
        concurrency_source=concurrency_source,
        execution_pattern="asyncio.gather(sample_async(...))",
        sdk_retry_owned=True,
        client_timeout_seconds=None,
        requires_live_capability_check=capabilities is None,
        create_new_sampler_after_weights=request.task_kind is TaskKind.LORA_PROTOTYPE,
        reservation_id=reservation.reservation_id,
        reserved_usd=str(reservation.reserved_usd),
        price_snapshot=price_snapshot.to_dict(),
        output_paths=request.expected_outputs,
        frozen=False,
    )


__all__ = [
    "PriceSnapshot",
    "TinkerCapabilities",
    "TinkerPlan",
    "TinkerPlanError",
    "build_tinker_plan",
]
