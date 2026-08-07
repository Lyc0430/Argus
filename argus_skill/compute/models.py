"""Typed, JSON-compatible request contracts for the compute broker."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, fields
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Mapping

COMPUTE_REQUEST_VERSION = 1
_JOB_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class Provider(str, Enum):
    TINKER = "tinker"
    KATANA = "katana"


class ProviderHint(str, Enum):
    AUTO = "auto"
    TINKER = "tinker"
    KATANA = "katana"


class EvidenceClass(str, Enum):
    EXPLORATORY = "exploratory"
    FROZEN = "frozen"


class TaskKind(str, Enum):
    PROMPT_SANITY = "prompt_sanity"
    SAMPLING = "sampling"
    LORA_PROTOTYPE = "lora_prototype"
    TRAINING = "training"
    EVALUATION = "evaluation"
    RENDERER = "renderer"
    EMBEDDING = "embedding"
    CUSTOM = "custom"


def _required_text(value: object, *, field: str, maximum: int = 240) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    if len(text) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    return text


def _non_negative_float(value: object, *, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if result < 0:
        raise ValueError(f"{field} must be non-negative")
    if result != result or result in {float("inf"), float("-inf")}:
        raise ValueError(f"{field} must be finite")
    return result


def _non_negative_int(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a non-negative integer") from exc
    if result < 0 or str(value).strip() not in {str(result), f"{result}.0"}:
        raise ValueError(f"{field} must be a non-negative integer")
    return result


def _safe_relative_paths(value: object, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field} must be a list of project-relative paths")
    result: list[str] = []
    for raw in value:
        candidate = str(raw or "").strip().replace("\\", "/")
        path = PurePosixPath(candidate)
        if (
            not candidate
            or candidate.startswith("/")
            or ".." in path.parts
            or "." == candidate
        ):
            raise ValueError(f"{field} contains an unsafe path: {candidate!r}")
        result.append(path.as_posix())
    return tuple(dict.fromkeys(result))


def _json_mapping(value: object, *, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a JSON object")
    result = {str(key): item for key, item in value.items()}
    try:
        json.dumps(result, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON serializable") from exc
    return result


@dataclass(frozen=True)
class ComputeRequest:
    version: int
    job_key: str
    mission_id: str
    project: str
    task_kind: TaskKind
    evidence_class: EvidenceClass
    provider_hint: ProviderHint
    model: str
    estimated_cost_usd: float = 0.0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    expected_outputs: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    workload: dict[str, Any] | None = None
    resources: dict[str, Any] | None = None
    requires_hidden_states: bool = False
    requires_full_vocab_logits: bool = False
    requires_model_revision_pin: bool = False
    requires_replay: bool = False
    requires_crn: bool = False
    requires_critic_training: bool = False
    requires_main_table: bool = False
    requires_custom_cuda: bool = False
    requires_private_no_egress: bool = False

    @property
    def frozen(self) -> bool:
        return self.evidence_class is EvidenceClass.FROZEN

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> "ComputeRequest":
        if not isinstance(raw, Mapping):
            raise ValueError("ComputeRequest must be a JSON object")
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(str(key) for key in raw if key not in allowed)
        if unknown:
            raise ValueError(f"unknown ComputeRequest fields: {', '.join(unknown)}")
        try:
            version = int(raw.get("version", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("version must be an integer") from exc
        if version != COMPUTE_REQUEST_VERSION:
            raise ValueError(
                f"version must be {COMPUTE_REQUEST_VERSION}, got {version!r}"
            )
        job_key = _required_text(raw.get("job_key"), field="job_key", maximum=128)
        if not _JOB_KEY.fullmatch(job_key):
            raise ValueError(
                "job_key must use only letters, numbers, dot, underscore, colon, or hyphen"
            )
        try:
            task_kind = TaskKind(str(raw.get("task_kind") or ""))
        except ValueError as exc:
            raise ValueError("task_kind is unsupported") from exc
        try:
            evidence_class = EvidenceClass(str(raw.get("evidence_class") or ""))
        except ValueError as exc:
            raise ValueError("evidence_class must be exploratory or frozen") from exc
        try:
            provider_hint = ProviderHint(str(raw.get("provider_hint") or "auto"))
        except ValueError as exc:
            raise ValueError("provider_hint must be auto, tinker, or katana") from exc
        return cls(
            version=version,
            job_key=job_key,
            mission_id=_required_text(raw.get("mission_id"), field="mission_id"),
            project=_required_text(raw.get("project"), field="project"),
            task_kind=task_kind,
            evidence_class=evidence_class,
            provider_hint=provider_hint,
            model=_required_text(raw.get("model"), field="model", maximum=500),
            estimated_cost_usd=_non_negative_float(
                raw.get("estimated_cost_usd", 0), field="estimated_cost_usd"
            ),
            estimated_input_tokens=_non_negative_int(
                raw.get("estimated_input_tokens", 0), field="estimated_input_tokens"
            ),
            estimated_output_tokens=_non_negative_int(
                raw.get("estimated_output_tokens", 0), field="estimated_output_tokens"
            ),
            expected_outputs=_safe_relative_paths(
                raw.get("expected_outputs"), field="expected_outputs"
            ),
            dependencies=_safe_relative_paths(
                raw.get("dependencies"), field="dependencies"
            ),
            workload=_json_mapping(raw.get("workload"), field="workload"),
            resources=_json_mapping(raw.get("resources"), field="resources"),
            requires_hidden_states=bool(raw.get("requires_hidden_states", False)),
            requires_full_vocab_logits=bool(
                raw.get("requires_full_vocab_logits", False)
            ),
            requires_model_revision_pin=bool(
                raw.get("requires_model_revision_pin", False)
            ),
            requires_replay=bool(raw.get("requires_replay", False)),
            requires_crn=bool(raw.get("requires_crn", False)),
            requires_critic_training=bool(
                raw.get("requires_critic_training", False)
            ),
            requires_main_table=bool(raw.get("requires_main_table", False)),
            requires_custom_cuda=bool(raw.get("requires_custom_cuda", False)),
            requires_private_no_egress=bool(
                raw.get("requires_private_no_egress", False)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["task_kind"] = self.task_kind.value
        result["evidence_class"] = self.evidence_class.value
        result["provider_hint"] = self.provider_hint.value
        result["expected_outputs"] = list(self.expected_outputs)
        result["dependencies"] = list(self.dependencies)
        result["workload"] = dict(self.workload or {})
        result["resources"] = dict(self.resources or {})
        return result


__all__ = [
    "COMPUTE_REQUEST_VERSION",
    "ComputeRequest",
    "EvidenceClass",
    "Provider",
    "ProviderHint",
    "TaskKind",
]
