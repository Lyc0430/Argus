"""Dry-run compute broker joining routing, budget, plans, and liveness."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any, Mapping

import portalocker

from .budget import BudgetError, BudgetLedger, Reservation
from .external import atomic_write_json, safe_record_stem, write_planned_external_work
from .katana import KatanaPlanError, build_katana_plan
from .models import ComputeRequest, Provider, TaskKind
from .routing import RoutingError, route_request
from .tinker import (
    PriceSnapshot,
    TinkerCapabilities,
    TinkerPlanError,
    build_tinker_plan,
)

_SECRET_MARKERS = (
    "token",
    "secret",
    "password",
    "credential",
    "api_key",
    "access_key",
    "private_key",
    "cookie",
)


class BrokerPlanError(RuntimeError):
    """A broker request was rejected without launching external work."""


def redact_secrets(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if any(marker in name.casefold() for marker in _SECRET_MARKERS):
                result[name] = "[REDACTED]"
            else:
                result[name] = redact_secrets(item)
        return result
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return value


def _canonical_digest(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BrokerPlanError(f"{label} does not exist: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise BrokerPlanError(f"cannot read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise BrokerPlanError(f"{label} must contain a JSON object")
    return value


def _price_snapshot(path: Path | None) -> PriceSnapshot:
    if path is None:
        raise BrokerPlanError("a Tinker price snapshot is required before reservation")
    raw = _read_json_object(path, label="Tinker price snapshot")
    try:
        return PriceSnapshot(
            source=str(raw.get("source") or ""),
            sha256=str(raw.get("sha256") or ""),
            captured_at=str(raw.get("captured_at") or ""),
        )
    except ValueError as exc:
        raise BrokerPlanError(str(exc)) from exc


def _capabilities(path: Path | None) -> TinkerCapabilities | None:
    if path is None:
        return None
    raw = _read_json_object(path, label="Tinker capabilities")
    models = raw.get("supported_models")
    if not isinstance(models, list):
        raise BrokerPlanError("Tinker capabilities must contain supported_models")
    try:
        return TinkerCapabilities(
            supported_models=tuple(str(model) for model in models),
            max_concurrent_requests=(
                int(raw["max_concurrent_requests"])
                if raw.get("max_concurrent_requests") is not None
                else None
            ),
        )
    except (TypeError, ValueError) as exc:
        raise BrokerPlanError(str(exc)) from exc


@dataclass(frozen=True)
class ComputeTicket:
    version: int
    ticket_id: str
    job_key: str
    request_sha256: str
    provider: str
    plan_path: str
    external_work_path: str
    reservation_id: str
    dry_run: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ComputeTicket":
        try:
            return cls(
                version=int(value["version"]),
                ticket_id=str(value["ticket_id"]),
                job_key=str(value["job_key"]),
                request_sha256=str(value["request_sha256"]),
                provider=str(value["provider"]),
                plan_path=str(value["plan_path"]),
                external_work_path=str(value["external_work_path"]),
                reservation_id=str(value.get("reservation_id") or ""),
                dry_run=bool(value.get("dry_run", True)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BrokerPlanError("stored compute ticket is invalid") from exc


class ComputeBroker:
    def __init__(
        self,
        *,
        project_root: Path | str,
        ledger_path: Path | str | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.state_root = self.project_root / ".argus_compute"
        self.ledger = BudgetLedger(ledger_path) if ledger_path is not None else None
        self.lock_path = self.state_root / "broker.lock"

    def plan(
        self,
        raw_request: Mapping[str, object],
        *,
        price_snapshot_path: Path | str | None = None,
        capabilities_path: Path | str | None = None,
    ) -> ComputeTicket:
        try:
            request = ComputeRequest.from_dict(raw_request)
        except ValueError as exc:
            raise BrokerPlanError(str(exc)) from exc
        request_sha = _canonical_digest(request.to_dict())
        self.state_root.mkdir(parents=True, exist_ok=True)
        with portalocker.Lock(str(self.lock_path), mode="a", timeout=10):
            existing = self._stored_ticket(request.job_key)
            if existing is not None:
                if existing.request_sha256 != request_sha:
                    raise BrokerPlanError(
                        f"job_key {request.job_key!r} already belongs to a different request"
                    )
                return existing
            try:
                route = route_request(request)
                if route.provider is Provider.TINKER:
                    ticket = self._plan_tinker(
                        request,
                        request_sha=request_sha,
                        price_path=(
                            Path(price_snapshot_path)
                            if price_snapshot_path is not None
                            else None
                        ),
                        capabilities_path=(
                            Path(capabilities_path)
                            if capabilities_path is not None
                            else None
                        ),
                    )
                else:
                    plan = build_katana_plan(request)
                    ticket = self._persist(
                        request,
                        request_sha=request_sha,
                        provider=Provider.KATANA,
                        plan=plan.to_dict(),
                        reservation_id="",
                    )
                return ticket
            except (BudgetError, KatanaPlanError, RoutingError, TinkerPlanError) as exc:
                raise BrokerPlanError(str(exc)) from exc

    def status(self, job_key: str) -> ComputeTicket:
        ticket = self._stored_ticket(str(job_key or "").strip())
        if ticket is None:
            raise BrokerPlanError(f"no compute ticket exists for job_key {job_key!r}")
        return ticket

    def _plan_tinker(
        self,
        request: ComputeRequest,
        *,
        request_sha: str,
        price_path: Path | None,
        capabilities_path: Path | None,
    ) -> ComputeTicket:
        price = _price_snapshot(price_path)
        capabilities = _capabilities(capabilities_path)
        if self.ledger is None:
            raise BrokerPlanError("Tinker planning requires an initialized budget ledger")
        snapshot = self.ledger.snapshot()
        estimate = Decimal(str(request.estimated_cost_usd)).quantize(Decimal("0.01"))
        provisional = Reservation(
            reservation_id="preflight",
            job_key=request.job_key,
            estimated_cost_usd=estimate,
            reserved_usd=(estimate * snapshot.policy.safety_multiplier).quantize(
                Decimal("0.01"), rounding=ROUND_CEILING
            ),
        )
        # Validate the complete provider plan before the ledger is mutated.
        build_tinker_plan(
            request,
            reservation=provisional,
            price_snapshot=price,
            capabilities=capabilities,
        )
        reservation = self.ledger.reserve(
            job_key=request.job_key,
            estimated_cost_usd=estimate,
            job_cap_usd=(
                Decimal("200")
                if request.task_kind is TaskKind.LORA_PROTOTYPE
                else Decimal("50")
            ),
        )
        try:
            plan = build_tinker_plan(
                request,
                reservation=reservation,
                price_snapshot=price,
                capabilities=capabilities,
            )
            return self._persist(
                request,
                request_sha=request_sha,
                provider=Provider.TINKER,
                plan=plan.to_dict(),
                reservation_id=reservation.reservation_id,
            )
        except Exception:
            self.ledger.release(
                reservation.reservation_id,
                reason="broker plan persistence failed before external execution",
            )
            raise

    def _persist(
        self,
        request: ComputeRequest,
        *,
        request_sha: str,
        provider: Provider,
        plan: dict[str, Any],
        reservation_id: str,
    ) -> ComputeTicket:
        stem = safe_record_stem(request.job_key)
        plan_rel = (Path(".argus_compute") / "plans" / f"{stem}.json").as_posix()
        ticket_rel = (Path(".argus_compute") / "tickets" / f"{stem}.json").as_posix()
        external_rel = (
            Path(".argus_external_work") / f"{stem}.json"
        ).as_posix()
        atomic_write_json(self.project_root / plan_rel, plan)
        ticket = ComputeTicket(
            version=1,
            ticket_id=hashlib.sha256(
                f"{request.job_key}:{request_sha}".encode("utf-8")
            ).hexdigest()[:24],
            job_key=request.job_key,
            request_sha256=request_sha,
            provider=provider.value,
            plan_path=plan_rel,
            external_work_path=external_rel,
            reservation_id=reservation_id,
            dry_run=True,
        )
        atomic_write_json(self.project_root / ticket_rel, ticket.to_dict())
        write_planned_external_work(
            self.project_root,
            job_key=request.job_key,
            provider=provider.value,
            plan_path=plan_rel,
        )
        return ticket

    def _stored_ticket(self, job_key: str) -> ComputeTicket | None:
        if not job_key:
            return None
        path = self.state_root / "tickets" / f"{safe_record_stem(job_key)}.json"
        if not path.is_file():
            return None
        return ComputeTicket.from_dict(_read_json_object(path, label="compute ticket"))


__all__ = [
    "BrokerPlanError",
    "ComputeBroker",
    "ComputeTicket",
    "redact_secrets",
]
