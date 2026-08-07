"""Append-only predictive budget ledger for Tinker admission."""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import portalocker

LEDGER_VERSION = 1
_CENT = Decimal("0.01")


class BudgetError(RuntimeError):
    pass


class BudgetExceeded(BudgetError):
    pass


class BudgetReconciliationRequired(BudgetExceeded):
    pass


class BudgetConflict(BudgetError):
    pass


class BudgetLedgerCorrupt(BudgetError):
    pass


def _money(value: object, *, field: str, allow_zero: bool = True) -> Decimal:
    try:
        result = Decimal(str(value)).quantize(_CENT)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a finite decimal amount") from exc
    if not result.is_finite() or result < 0 or (not allow_zero and result == 0):
        qualifier = "positive" if not allow_zero else "non-negative"
        raise ValueError(f"{field} must be a finite {qualifier} amount")
    return result


@dataclass(frozen=True)
class BudgetPolicy:
    total_budget_usd: Decimal = Decimal("4300")
    auto_limit_usd: Decimal = Decimal("2500")
    locked_usd: Decimal = Decimal("1800")
    reconciliation_threshold_usd: Decimal = Decimal("2250")
    lag_buffer_usd: Decimal = Decimal("250")
    safety_multiplier: Decimal = Decimal("1.25")

    def __post_init__(self) -> None:
        for field in (
            "total_budget_usd",
            "auto_limit_usd",
            "locked_usd",
            "reconciliation_threshold_usd",
            "lag_buffer_usd",
        ):
            object.__setattr__(self, field, _money(getattr(self, field), field=field))
        multiplier = Decimal(str(self.safety_multiplier))
        if not multiplier.is_finite() or multiplier < 1:
            raise ValueError("safety_multiplier must be finite and at least 1")
        object.__setattr__(self, "safety_multiplier", multiplier)
        if self.reconciliation_threshold_usd > self.auto_limit_usd:
            raise ValueError("reconciliation threshold cannot exceed auto limit")
        if self.lag_buffer_usd > self.auto_limit_usd:
            raise ValueError("lag buffer cannot exceed auto limit")
        if self.auto_limit_usd + self.locked_usd > self.total_budget_usd:
            raise ValueError(
                "automatic limit plus protected reserve cannot exceed total budget"
            )

    def to_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "BudgetPolicy":
        try:
            return cls(**{key: Decimal(str(item)) for key, item in value.items()})
        except (TypeError, InvalidOperation) as exc:
            raise BudgetLedgerCorrupt("ledger policy is invalid") from exc


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    job_key: str
    estimated_cost_usd: Decimal
    reserved_usd: Decimal
    state: str = "reserved"


@dataclass(frozen=True)
class Settlement:
    reservation_id: str
    job_key: str
    actual_cost_usd: Decimal


@dataclass(frozen=True)
class BudgetSnapshot:
    policy: BudgetPolicy
    settled_usd: Decimal
    active_reserved_usd: Decimal
    committed_usd: Decimal
    hard_exposure_usd: Decimal
    reservations: tuple[Reservation, ...]


@dataclass
class _State:
    policy: BudgetPolicy
    reservations: dict[str, Reservation]
    reservation_by_job: dict[str, str]
    settlements: dict[str, Settlement]
    releases: set[str]

    def snapshot(self) -> BudgetSnapshot:
        active = tuple(
            reservation
            for reservation_id, reservation in self.reservations.items()
            if reservation_id not in self.settlements and reservation_id not in self.releases
        )
        settled = sum(
            (item.actual_cost_usd for item in self.settlements.values()),
            Decimal("0.00"),
        ).quantize(_CENT)
        reserved = sum(
            (item.reserved_usd for item in active), Decimal("0.00")
        ).quantize(_CENT)
        committed = (settled + reserved).quantize(_CENT)
        return BudgetSnapshot(
            policy=self.policy,
            settled_usd=settled,
            active_reserved_usd=reserved,
            committed_usd=committed,
            hard_exposure_usd=(committed + self.policy.lag_buffer_usd).quantize(_CENT),
            reservations=active,
        )


class BudgetLedger:
    """A ledger whose absence or corruption blocks new admissions."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(f"{self.path.suffix}.lock")

    @classmethod
    def initialize(
        cls, path: Path | str, policy: BudgetPolicy | None = None
    ) -> "BudgetLedger":
        ledger = cls(path)
        ledger.path.parent.mkdir(parents=True, exist_ok=True)
        with portalocker.Lock(str(ledger.lock_path), mode="a", timeout=10):
            if ledger.path.exists() and ledger.path.stat().st_size:
                state = ledger._read_state()
                if policy is not None and state.policy != policy:
                    raise BudgetConflict("ledger is already initialized with another policy")
                return ledger
            event = {
                "version": LEDGER_VERSION,
                "event": "ledger_initialized",
                "event_id": uuid.uuid4().hex,
                "timestamp": time.time(),
                "ledger_id": uuid.uuid4().hex,
                "policy": (policy or BudgetPolicy()).to_dict(),
            }
            ledger._append_event(event)
        return ledger

    def snapshot(self) -> BudgetSnapshot:
        with portalocker.Lock(str(self.lock_path), mode="a", timeout=10):
            return self._read_state().snapshot()

    def reserve(
        self,
        *,
        job_key: str,
        estimated_cost_usd: Decimal,
        job_cap_usd: Decimal | None = None,
    ) -> Reservation:
        estimate = _money(
            estimated_cost_usd, field="estimated_cost_usd", allow_zero=False
        )
        cap = _money(job_cap_usd, field="job_cap_usd") if job_cap_usd is not None else None
        if cap is not None and estimate > cap:
            raise BudgetExceeded(
                f"estimated cost ${estimate} exceeds the per-job cap ${cap}"
            )
        with portalocker.Lock(str(self.lock_path), mode="a", timeout=10):
            state = self._read_state()
            existing_id = state.reservation_by_job.get(job_key)
            if existing_id:
                existing = state.reservations[existing_id]
                if existing.estimated_cost_usd != estimate:
                    raise BudgetConflict(
                        f"job_key {job_key!r} already has a different estimate"
                    )
                if existing_id in state.releases:
                    raise BudgetConflict(f"job_key {job_key!r} reservation was released")
                return existing
            reserved = (estimate * state.policy.safety_multiplier).quantize(
                _CENT, rounding=ROUND_CEILING
            )
            snapshot = state.snapshot()
            committed_after = snapshot.committed_usd + reserved
            hard_after = committed_after + state.policy.lag_buffer_usd
            if committed_after > state.policy.reconciliation_threshold_usd:
                raise BudgetReconciliationRequired(
                    "Tinker reconciliation threshold would be exceeded: "
                    f"${committed_after} > ${state.policy.reconciliation_threshold_usd}"
                )
            if hard_after > state.policy.auto_limit_usd:
                raise BudgetExceeded(
                    "Tinker hard limit would be exceeded: "
                    f"${hard_after} > ${state.policy.auto_limit_usd}"
                )
            reservation = Reservation(
                reservation_id=uuid.uuid4().hex,
                job_key=job_key,
                estimated_cost_usd=estimate,
                reserved_usd=reserved,
            )
            self._append_event(
                {
                    "version": LEDGER_VERSION,
                    "event": "reserved",
                    "event_id": uuid.uuid4().hex,
                    "timestamp": time.time(),
                    "reservation_id": reservation.reservation_id,
                    "job_key": job_key,
                    "estimated_cost_usd": str(estimate),
                    "reserved_usd": str(reserved),
                }
            )
            return reservation

    def settle(
        self, reservation_id: str, *, actual_cost_usd: Decimal
    ) -> Settlement:
        actual = _money(actual_cost_usd, field="actual_cost_usd")
        with portalocker.Lock(str(self.lock_path), mode="a", timeout=10):
            state = self._read_state()
            reservation = state.reservations.get(reservation_id)
            if reservation is None:
                raise BudgetConflict(f"unknown reservation_id {reservation_id!r}")
            if reservation_id in state.releases:
                raise BudgetConflict(f"reservation {reservation_id!r} was released")
            existing = state.settlements.get(reservation_id)
            if existing:
                if existing.actual_cost_usd != actual:
                    raise BudgetConflict("reservation already settled with another amount")
                return existing
            settlement = Settlement(
                reservation_id=reservation_id,
                job_key=reservation.job_key,
                actual_cost_usd=actual,
            )
            self._append_event(
                {
                    "version": LEDGER_VERSION,
                    "event": "settled",
                    "event_id": uuid.uuid4().hex,
                    "timestamp": time.time(),
                    "reservation_id": reservation_id,
                    "job_key": reservation.job_key,
                    "actual_cost_usd": str(actual),
                }
            )
            return settlement

    def release(self, reservation_id: str, *, reason: str) -> None:
        clean_reason = " ".join(str(reason or "").split())[:500]
        if not clean_reason:
            raise ValueError("release reason is required")
        with portalocker.Lock(str(self.lock_path), mode="a", timeout=10):
            state = self._read_state()
            reservation = state.reservations.get(reservation_id)
            if reservation is None:
                raise BudgetConflict(f"unknown reservation_id {reservation_id!r}")
            if reservation_id in state.settlements:
                raise BudgetConflict(f"reservation {reservation_id!r} is settled")
            if reservation_id in state.releases:
                return
            self._append_event(
                {
                    "version": LEDGER_VERSION,
                    "event": "released",
                    "event_id": uuid.uuid4().hex,
                    "timestamp": time.time(),
                    "reservation_id": reservation_id,
                    "job_key": reservation.job_key,
                    "reason": clean_reason,
                }
            )

    def _read_state(self) -> _State:
        if not self.path.is_file() or self.path.stat().st_size == 0:
            raise BudgetLedgerCorrupt(f"budget ledger is not initialized: {self.path}")
        events: list[dict[str, Any]] = []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise BudgetLedgerCorrupt(f"cannot read budget ledger: {exc}") from exc
        for index, line in enumerate(lines, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BudgetLedgerCorrupt(f"invalid JSON on ledger line {index}") from exc
            if not isinstance(value, dict):
                raise BudgetLedgerCorrupt(f"ledger line {index} is not an object")
            if value.get("version") != LEDGER_VERSION:
                raise BudgetLedgerCorrupt(f"invalid ledger version on line {index}")
            events.append(value)
        if not events or events[0].get("event") != "ledger_initialized":
            raise BudgetLedgerCorrupt("ledger line 1 must initialize the ledger")
        policy_raw = events[0].get("policy")
        if not isinstance(policy_raw, dict):
            raise BudgetLedgerCorrupt("ledger line 1 has no valid policy")
        policy = BudgetPolicy.from_dict(policy_raw)
        state = _State(policy, {}, {}, {}, set())
        for index, event in enumerate(events[1:], 2):
            kind = event.get("event")
            reservation_id = str(event.get("reservation_id") or "")
            job_key = str(event.get("job_key") or "")
            try:
                if kind == "reserved":
                    if not reservation_id or not job_key:
                        raise ValueError
                    reservation = Reservation(
                        reservation_id=reservation_id,
                        job_key=job_key,
                        estimated_cost_usd=_money(
                            event.get("estimated_cost_usd"),
                            field="estimated_cost_usd",
                            allow_zero=False,
                        ),
                        reserved_usd=_money(
                            event.get("reserved_usd"),
                            field="reserved_usd",
                            allow_zero=False,
                        ),
                    )
                    if reservation_id in state.reservations or job_key in state.reservation_by_job:
                        raise ValueError
                    state.reservations[reservation_id] = reservation
                    state.reservation_by_job[job_key] = reservation_id
                elif kind == "settled":
                    reservation = state.reservations.get(reservation_id)
                    if reservation is None or reservation.job_key != job_key:
                        raise ValueError
                    settlement = Settlement(
                        reservation_id=reservation_id,
                        job_key=job_key,
                        actual_cost_usd=_money(
                            event.get("actual_cost_usd"), field="actual_cost_usd"
                        ),
                    )
                    if reservation_id in state.settlements or reservation_id in state.releases:
                        raise ValueError
                    state.settlements[reservation_id] = settlement
                elif kind == "released":
                    reservation = state.reservations.get(reservation_id)
                    if reservation is None or reservation.job_key != job_key:
                        raise ValueError
                    if reservation_id in state.settlements or reservation_id in state.releases:
                        raise ValueError
                    state.releases.add(reservation_id)
                else:
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise BudgetLedgerCorrupt(
                    f"invalid {kind!r} event on ledger line {index}"
                ) from exc
        return state

    def _append_event(self, event: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(
            event, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise BudgetLedgerCorrupt(f"cannot append budget ledger: {exc}") from exc


__all__ = [
    "BudgetConflict",
    "BudgetError",
    "BudgetExceeded",
    "BudgetLedger",
    "BudgetLedgerCorrupt",
    "BudgetPolicy",
    "BudgetReconciliationRequired",
    "BudgetSnapshot",
    "Reservation",
    "Settlement",
]
