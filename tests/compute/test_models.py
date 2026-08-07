from __future__ import annotations

import pytest

from argus_skill.compute.models import ComputeRequest, EvidenceClass, TaskKind


def _request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": 1,
        "job_key": "mission-7.prompt-sanity.001",
        "mission_id": "mission-7",
        "project": "consequence",
        "task_kind": "prompt_sanity",
        "evidence_class": "exploratory",
        "provider_hint": "auto",
        "model": "Qwen/Qwen3.5-4B",
        "estimated_cost_usd": 4.0,
        "estimated_input_tokens": 2_000,
        "estimated_output_tokens": 500,
        "expected_outputs": ["runs/prompt-sanity/result.jsonl"],
        "workload": {"prompt_count": 8, "num_samples": 2},
    }
    payload.update(overrides)
    return payload


def test_request_round_trips_with_stable_idempotency_key() -> None:
    request = ComputeRequest.from_dict(_request())

    assert request.job_key == "mission-7.prompt-sanity.001"
    assert request.task_kind is TaskKind.PROMPT_SANITY
    assert request.evidence_class is EvidenceClass.EXPLORATORY
    assert request.frozen is False
    assert ComputeRequest.from_dict(request.to_dict()) == request


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("job_key", "../escape", "job_key"),
        ("job_key", "has space", "job_key"),
        ("model", "", "model"),
        ("estimated_cost_usd", -0.01, "estimated_cost_usd"),
        ("estimated_input_tokens", -1, "estimated_input_tokens"),
        ("expected_outputs", ["../secret"], "expected_outputs"),
        ("expected_outputs", ["/tmp/result"], "expected_outputs"),
    ],
)
def test_request_rejects_unsafe_or_negative_fields(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        ComputeRequest.from_dict(_request(**{field: value}))


def test_request_rejects_unknown_fields_instead_of_ignoring_policy_input() -> None:
    with pytest.raises(ValueError, match="unknown ComputeRequest fields"):
        ComputeRequest.from_dict(_request(frozon=True))


def test_frozen_is_derived_from_evidence_class_not_user_workload() -> None:
    request = ComputeRequest.from_dict(
        _request(evidence_class="frozen", workload={"frozen": False})
    )

    assert request.frozen is True
