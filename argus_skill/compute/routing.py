"""Fail-closed routing between Tinker exploration and Katana evidence work."""
from __future__ import annotations

from dataclasses import dataclass

from .models import ComputeRequest, Provider, ProviderHint, TaskKind

_TINKER_TASKS = frozenset(
    {TaskKind.PROMPT_SANITY, TaskKind.SAMPLING, TaskKind.LORA_PROTOTYPE}
)
_HARD_REQUIREMENTS = (
    "requires_hidden_states",
    "requires_full_vocab_logits",
    "requires_model_revision_pin",
    "requires_replay",
    "requires_crn",
    "requires_critic_training",
    "requires_main_table",
    "requires_custom_cuda",
    "requires_private_no_egress",
)


class RoutingError(ValueError):
    """The requested provider would weaken a required evidence boundary."""


@dataclass(frozen=True)
class RouteDecision:
    provider: Provider
    reason_codes: tuple[str, ...]
    frozen: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "provider": self.provider.value,
            "reason_codes": list(self.reason_codes),
            "frozen": self.frozen,
        }


def route_request(request: ComputeRequest) -> RouteDecision:
    hard_reasons = tuple(
        field for field in _HARD_REQUIREMENTS if getattr(request, field)
    )
    if request.frozen:
        hard_reasons = (*hard_reasons, "frozen_evidence")
    if hard_reasons:
        if request.provider_hint is ProviderHint.TINKER:
            raise RoutingError(
                "Tinker cannot satisfy frozen or internal-state requirements: "
                + ", ".join(hard_reasons)
            )
        return RouteDecision(
            provider=Provider.KATANA,
            reason_codes=hard_reasons,
            frozen=request.frozen,
        )
    if request.provider_hint is ProviderHint.KATANA:
        return RouteDecision(
            provider=Provider.KATANA,
            reason_codes=("operator_requested_katana",),
            frozen=request.frozen,
        )
    if request.task_kind not in _TINKER_TASKS:
        if request.provider_hint is ProviderHint.TINKER:
            raise RoutingError(
                f"Tinker cannot satisfy task_kind={request.task_kind.value}"
            )
        return RouteDecision(
            provider=Provider.KATANA,
            reason_codes=("task_requires_katana",),
            frozen=request.frozen,
        )
    if request.estimated_cost_usd <= 0:
        if request.provider_hint is ProviderHint.TINKER:
            raise RoutingError(
                "Tinker admission requires a positive estimated_cost_usd"
            )
        return RouteDecision(
            provider=Provider.KATANA,
            reason_codes=("tinker_cost_unestimated",),
            frozen=request.frozen,
        )
    return RouteDecision(
        provider=Provider.TINKER,
        reason_codes=("tinker_exploratory_fast_path",),
        frozen=False,
    )


__all__ = ["RouteDecision", "RoutingError", "route_request"]
