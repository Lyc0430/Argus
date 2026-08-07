from __future__ import annotations

import pytest

from argus_skill.compute.models import ComputeRequest, Provider
from argus_skill.compute.routing import RoutingError, route_request


def _request(**overrides: object) -> ComputeRequest:
    payload: dict[str, object] = {
        "version": 1,
        "job_key": "route-case-1",
        "mission_id": "m1",
        "project": "consequence",
        "task_kind": "sampling",
        "evidence_class": "exploratory",
        "provider_hint": "auto",
        "model": "Qwen/Qwen3.5-4B",
        "estimated_cost_usd": 1.0,
        "expected_outputs": ["runs/result.json"],
    }
    payload.update(overrides)
    return ComputeRequest.from_dict(payload)


@pytest.mark.parametrize("task_kind", ["prompt_sanity", "sampling", "lora_prototype"])
def test_exploratory_supported_work_routes_to_tinker(task_kind: str) -> None:
    decision = route_request(_request(task_kind=task_kind))

    assert decision.provider is Provider.TINKER
    assert decision.frozen is False
    assert decision.reason_codes == ("tinker_exploratory_fast_path",)


@pytest.mark.parametrize(
    "field",
    [
        "requires_hidden_states",
        "requires_full_vocab_logits",
        "requires_model_revision_pin",
        "requires_replay",
        "requires_crn",
        "requires_critic_training",
        "requires_main_table",
        "requires_custom_cuda",
        "requires_private_no_egress",
    ],
)
def test_hard_requirements_route_auto_requests_to_katana(field: str) -> None:
    decision = route_request(_request(**{field: True}))

    assert decision.provider is Provider.KATANA
    assert decision.frozen is False
    assert decision.reason_codes == (field,)


def test_frozen_evidence_routes_to_katana() -> None:
    decision = route_request(_request(evidence_class="frozen"))

    assert decision.provider is Provider.KATANA
    assert decision.frozen is True
    assert decision.reason_codes == ("frozen_evidence",)


def test_unsupported_tinker_task_routes_to_katana() -> None:
    decision = route_request(_request(task_kind="evaluation"))

    assert decision.provider is Provider.KATANA
    assert decision.reason_codes == ("task_requires_katana",)


def test_explicit_katana_hint_is_respected() -> None:
    decision = route_request(_request(provider_hint="katana"))

    assert decision.provider is Provider.KATANA
    assert decision.frozen is False
    assert decision.reason_codes == ("operator_requested_katana",)


def test_katana_routing_never_promotes_exploratory_evidence_to_frozen() -> None:
    decision = route_request(
        _request(provider_hint="katana", evidence_class="exploratory")
    )

    assert decision.frozen is False


def test_tinker_hint_cannot_weaken_frozen_or_internal_state_requirement() -> None:
    with pytest.raises(RoutingError, match="Tinker cannot satisfy"):
        route_request(
            _request(
                provider_hint="tinker",
                evidence_class="frozen",
                requires_hidden_states=True,
            )
        )


def test_tinker_hint_requires_a_positive_budget_estimate() -> None:
    with pytest.raises(RoutingError, match="positive estimated_cost_usd"):
        route_request(_request(provider_hint="tinker", estimated_cost_usd=0))
