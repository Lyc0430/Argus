from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest

from argus_skill.compute.budget import (
    BudgetConflict,
    BudgetExceeded,
    BudgetLedger,
    BudgetLedgerCorrupt,
    BudgetPolicy,
    BudgetReconciliationRequired,
)


def _ledger(path: Path, **policy: object) -> BudgetLedger:
    BudgetLedger.initialize(path, BudgetPolicy(**policy))
    return BudgetLedger(path)


def test_policy_reserves_1800_of_the_4300_total_outside_automatic_spend() -> None:
    policy = BudgetPolicy()

    assert policy.total_budget_usd == Decimal("4300.00")
    assert policy.auto_limit_usd == Decimal("2500.00")
    assert policy.locked_usd == Decimal("1800.00")

    with pytest.raises(ValueError, match="total budget"):
        BudgetPolicy(
            total_budget_usd=Decimal("4000"),
            auto_limit_usd=Decimal("2500"),
            locked_usd=Decimal("1800"),
        )


def test_reservation_applies_safety_multiplier_and_is_idempotent(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "budget.jsonl")

    first = ledger.reserve(job_key="job-1", estimated_cost_usd=Decimal("40"))
    replay = ledger.reserve(job_key="job-1", estimated_cost_usd=Decimal("40"))

    assert first == replay
    assert first.reserved_usd == Decimal("50.00")
    assert ledger.snapshot().active_reserved_usd == Decimal("50.00")
    events = [json.loads(line) for line in ledger.path.read_text().splitlines()]
    assert [event["event"] for event in events] == ["ledger_initialized", "reserved"]


def test_same_job_key_with_a_different_estimate_is_a_conflict(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "budget.jsonl")
    ledger.reserve(job_key="job-1", estimated_cost_usd=Decimal("10"))

    with pytest.raises(BudgetConflict, match="different estimate"):
        ledger.reserve(job_key="job-1", estimated_cost_usd=Decimal("11"))


def test_settle_replaces_reservation_with_actual_spend(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "budget.jsonl")
    reservation = ledger.reserve(job_key="job-1", estimated_cost_usd=Decimal("40"))

    ledger.settle(reservation.reservation_id, actual_cost_usd=Decimal("37.12"))
    replay = ledger.settle(
        reservation.reservation_id, actual_cost_usd=Decimal("37.12")
    )
    snapshot = ledger.snapshot()

    assert replay.actual_cost_usd == Decimal("37.12")
    assert snapshot.active_reserved_usd == Decimal("0.00")
    assert snapshot.settled_usd == Decimal("37.12")


def test_release_returns_unspent_reservation_capacity(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "budget.jsonl")
    reservation = ledger.reserve(job_key="job-1", estimated_cost_usd=Decimal("100"))

    ledger.release(reservation.reservation_id, reason="operator cancelled")

    assert ledger.snapshot().active_reserved_usd == Decimal("0.00")
    with pytest.raises(BudgetConflict, match="released"):
        ledger.settle(reservation.reservation_id, actual_cost_usd=Decimal("1"))


def test_missing_or_malformed_ledger_fails_closed(tmp_path: Path) -> None:
    missing = BudgetLedger(tmp_path / "missing.jsonl")
    with pytest.raises(BudgetLedgerCorrupt, match="not initialized"):
        missing.snapshot()

    malformed_path = tmp_path / "malformed.jsonl"
    malformed_path.write_text('{"event":"ledger_initialized"}\nnot-json\n')
    with pytest.raises(BudgetLedgerCorrupt, match="line 1|line 2"):
        BudgetLedger(malformed_path).snapshot()


def test_soft_threshold_requires_reconciliation_before_more_admission(
    tmp_path: Path,
) -> None:
    ledger = _ledger(
        tmp_path / "budget.jsonl",
        auto_limit_usd=Decimal("2500"),
        locked_usd=Decimal("1800"),
        reconciliation_threshold_usd=Decimal("2250"),
        lag_buffer_usd=Decimal("250"),
        safety_multiplier=Decimal("1"),
    )
    ledger.reserve(job_key="large", estimated_cost_usd=Decimal("2249"))

    with pytest.raises(BudgetReconciliationRequired, match="reconciliation"):
        ledger.reserve(job_key="one-more", estimated_cost_usd=Decimal("2"))


def test_hard_limit_includes_lag_buffer(tmp_path: Path) -> None:
    ledger = _ledger(
        tmp_path / "budget.jsonl",
        auto_limit_usd=Decimal("2500"),
        reconciliation_threshold_usd=Decimal("2499"),
        lag_buffer_usd=Decimal("250"),
        safety_multiplier=Decimal("1"),
    )

    with pytest.raises(BudgetExceeded, match="hard limit"):
        ledger.reserve(job_key="too-large", estimated_cost_usd=Decimal("2251"))


def test_job_cap_is_checked_before_mutating_ledger(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "budget.jsonl")

    with pytest.raises(BudgetExceeded, match="per-job cap"):
        ledger.reserve(
            job_key="oversized",
            estimated_cost_usd=Decimal("51"),
            job_cap_usd=Decimal("50"),
        )

    assert ledger.snapshot().active_reserved_usd == Decimal("0.00")


def test_competing_reservations_are_serialized_by_the_file_lock(tmp_path: Path) -> None:
    ledger = _ledger(
        tmp_path / "budget.jsonl",
        auto_limit_usd=Decimal("100"),
        reconciliation_threshold_usd=Decimal("100"),
        lag_buffer_usd=Decimal("0"),
        safety_multiplier=Decimal("1"),
    )

    def reserve(job_key: str) -> str:
        try:
            ledger.reserve(job_key=job_key, estimated_cost_usd=Decimal("60"))
            return "admitted"
        except BudgetExceeded:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(reserve, ["job-a", "job-b"]))

    assert outcomes == ["admitted", "rejected"]
    assert ledger.snapshot().active_reserved_usd == Decimal("60.00")
