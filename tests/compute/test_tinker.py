from __future__ import annotations

from decimal import Decimal

import pytest

from argus_skill.compute.budget import Reservation
from argus_skill.compute.models import ComputeRequest
from argus_skill.compute.tinker import (
    PriceSnapshot,
    TinkerCapabilities,
    TinkerPlanError,
    build_tinker_plan,
)


def _request(**overrides: object) -> ComputeRequest:
    payload: dict[str, object] = {
        "version": 1,
        "job_key": "tinker.sample.001",
        "mission_id": "mission-1",
        "project": "consequence",
        "task_kind": "sampling",
        "evidence_class": "exploratory",
        "provider_hint": "tinker",
        "model": "Qwen/Qwen3.5-4B",
        "estimated_cost_usd": 10,
        "expected_outputs": ["runs/tinker/result.jsonl"],
        "workload": {
            "prompt_file": "inputs/prompts.jsonl",
            "prompt_count": 8,
            "num_samples": 4,
            "max_tokens": 512,
            "temperature": 0.7,
        },
    }
    payload.update(overrides)
    return ComputeRequest.from_dict(payload)


def _reservation(amount: str = "12.50") -> Reservation:
    return Reservation(
        reservation_id="reservation-1",
        job_key="tinker.sample.001",
        estimated_cost_usd=Decimal("10.00"),
        reserved_usd=Decimal(amount),
    )


def _price() -> PriceSnapshot:
    return PriceSnapshot(
        source="https://tinker-docs.thinkingmachines.ai/tinker/models.json",
        sha256="a" * 64,
        captured_at="2026-08-07T12:00:00Z",
    )


def test_plan_keeps_prompt_concurrency_and_num_samples_as_separate_axes() -> None:
    plan = build_tinker_plan(
        _request(),
        reservation=_reservation(),
        price_snapshot=_price(),
        capabilities=TinkerCapabilities(
            supported_models=("Qwen/Qwen3.5-4B",),
            max_concurrent_requests=64,
        ),
    )

    assert plan.prompt_count == 8
    assert plan.request_count == 8
    assert plan.num_samples == 4
    assert plan.completion_count == 32
    assert plan.concurrency_limit == 8
    assert plan.concurrency_source == "server_capabilities"
    assert plan.execution_pattern == "asyncio.gather(sample_async(...))"
    assert plan.sdk_retry_owned is True
    assert plan.client_timeout_seconds is None
    assert plan.frozen is False


def test_plan_without_live_capabilities_requires_pre_submit_check() -> None:
    plan = build_tinker_plan(
        _request(), reservation=_reservation(), price_snapshot=_price()
    )

    assert plan.requires_live_capability_check is True
    assert plan.concurrency_limit == 8
    assert plan.concurrency_source == "sdk_managed"


def test_capabilities_reject_unsupported_model() -> None:
    with pytest.raises(TinkerPlanError, match="not present in Tinker capabilities"):
        build_tinker_plan(
            _request(),
            reservation=_reservation(),
            price_snapshot=_price(),
            capabilities=TinkerCapabilities(supported_models=("another/model",)),
        )


def test_frozen_request_is_rejected_even_with_tinker_hint() -> None:
    with pytest.raises(TinkerPlanError, match="frozen:false"):
        build_tinker_plan(
            _request(evidence_class="frozen"),
            reservation=_reservation(),
            price_snapshot=_price(),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("sequential", True, "concurrent"),
        ("client_timeout_seconds", 30, "timeout"),
        ("retry_count", 2, "SDK"),
        ("prompt_count", 0, "prompt_count"),
        ("num_samples", 0, "num_samples"),
        ("max_tokens", 0, "max_tokens"),
        ("prompt_file", "../secret.jsonl", "prompt_file"),
    ],
)
def test_plan_rejects_sequential_custom_retry_timeout_and_bad_workload(
    field: str, value: object, message: str
) -> None:
    workload = dict(_request().workload or {})
    workload[field] = value
    with pytest.raises(TinkerPlanError, match=message):
        build_tinker_plan(
            _request(workload=workload),
            reservation=_reservation(),
            price_snapshot=_price(),
        )


def test_sampling_and_lora_per_job_caps_are_enforced() -> None:
    with pytest.raises(TinkerPlanError, match=r"\$50"):
        build_tinker_plan(
            _request(estimated_cost_usd=50.01),
            reservation=_reservation("62.52"),
            price_snapshot=_price(),
        )

    lora_workload = dict(_request().workload or {})
    lora_workload["training_recipe"] = "recipes/lora.toml"
    with pytest.raises(TinkerPlanError, match=r"\$200"):
        build_tinker_plan(
            _request(
                task_kind="lora_prototype",
                estimated_cost_usd=200.01,
                workload=lora_workload,
            ),
            reservation=_reservation("250.02"),
            price_snapshot=_price(),
        )


def test_price_snapshot_requires_stable_sha256_and_https_source() -> None:
    with pytest.raises(ValueError, match="sha256"):
        PriceSnapshot(source="https://example.test/models.json", sha256="bad")
    with pytest.raises(ValueError, match="HTTPS"):
        PriceSnapshot(source="file:///tmp/models.json", sha256="b" * 64)


def test_plan_rejects_reservation_for_another_job() -> None:
    reservation = Reservation(
        reservation_id="reservation-2",
        job_key="another-job",
        estimated_cost_usd=Decimal("10"),
        reserved_usd=Decimal("12.50"),
    )

    with pytest.raises(TinkerPlanError, match="reservation job_key"):
        build_tinker_plan(
            _request(), reservation=reservation, price_snapshot=_price()
        )
