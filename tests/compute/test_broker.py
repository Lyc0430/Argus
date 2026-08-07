from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from argus_skill.compute.broker import BrokerPlanError, ComputeBroker, redact_secrets
from argus_skill.compute.budget import BudgetLedger, BudgetPolicy
from argus_skill.engineer.external_work import ExternalWorkState, inspect_external_work


def _price(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "source": "https://tinker-docs.thinkingmachines.ai/tinker/models.json",
                "sha256": "a" * 64,
                "captured_at": "2026-08-07T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    return path


def _tinker_request(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": 1,
        "job_key": "broker.tinker.001",
        "mission_id": "mission-1",
        "project": "consequence",
        "task_kind": "sampling",
        "evidence_class": "exploratory",
        "provider_hint": "auto",
        "model": "Qwen/Qwen3.5-4B",
        "estimated_cost_usd": 10,
        "expected_outputs": ["runs/tinker/result.jsonl"],
        "workload": {
            "prompt_file": "inputs/prompts.jsonl",
            "prompt_count": 8,
            "num_samples": 2,
            "max_tokens": 256,
            "temperature": 0.7,
        },
    }
    payload.update(overrides)
    return payload


def _katana_request() -> dict[str, object]:
    return {
        "version": 1,
        "job_key": "broker.katana.001",
        "mission_id": "mission-1",
        "project": "consequence",
        "task_kind": "evaluation",
        "evidence_class": "frozen",
        "provider_hint": "auto",
        "model": "Qwen/Qwen3.5-4B",
        "estimated_cost_usd": 0,
        "requires_main_table": True,
        "expected_outputs": ["runs/katana/manifest.json"],
        "resources": {"ncpus": 18, "ngpus": 1, "memory_gb": 120},
        "workload": {
            "smoke": True,
            "scratch_dir": "/srv/scratch/nemesis/consequence",
            "log_dir": "/srv/scratch/nemesis/logs",
            "shards": ["s0"],
            "runtime": {
                "kind": "container",
                "container_path": "/srv/scratch/nemesis/containers/verl_vllm015.sif",
                "container_sha256": "b" * 64,
                "command": ["python", "-m", "consequence.runner"],
            },
            "checkpoint": {
                "mode": "episode_append_only",
                "path": "/srv/scratch/nemesis/consequence/checkpoints/broker-001",
                "idempotency_fields": ["query", "branch", "seed"],
            },
            "actor": {
                "model_snapshot_path": "/srv/scratch/nemesis/models/qwen3.5-4b",
                "model_snapshot_sha256": "c" * 64,
                "sampling_config_path": "configs/models.yaml",
                "sampling_config_sha256": "d" * 64,
            },
        },
    }


def test_tinker_plan_reserves_budget_then_writes_plan_and_external_record(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "budget.jsonl"
    BudgetLedger.initialize(ledger_path, BudgetPolicy())
    broker = ComputeBroker(project_root=tmp_path, ledger_path=ledger_path)

    ticket = broker.plan(_tinker_request(), price_snapshot_path=_price(tmp_path / "price.json"))

    assert ticket.provider == "tinker"
    assert ticket.dry_run is True
    assert ticket.reservation_id
    assert (tmp_path / ticket.plan_path).is_file()
    plan = json.loads((tmp_path / ticket.plan_path).read_text())
    assert plan["provider"] == "tinker"
    assert plan["frozen"] is False
    status = inspect_external_work(tmp_path, "broker.tinker.001")
    assert status is not None
    assert status.state is ExternalWorkState.TERMINAL
    assert status.outcome == "planned_dry_run"
    assert status.evidence_paths == (ticket.plan_path,)
    assert BudgetLedger(ledger_path).snapshot().active_reserved_usd == Decimal("12.50")


def test_duplicate_job_key_reuses_ticket_without_second_reservation(tmp_path: Path) -> None:
    ledger_path = tmp_path / "budget.jsonl"
    BudgetLedger.initialize(ledger_path)
    broker = ComputeBroker(project_root=tmp_path, ledger_path=ledger_path)
    price = _price(tmp_path / "price.json")

    first = broker.plan(_tinker_request(), price_snapshot_path=price)
    replay = broker.plan(_tinker_request(), price_snapshot_path=price)

    assert replay == first
    events = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    assert [event["event"] for event in events] == ["ledger_initialized", "reserved"]


def test_same_job_key_with_changed_request_is_rejected(tmp_path: Path) -> None:
    ledger_path = tmp_path / "budget.jsonl"
    BudgetLedger.initialize(ledger_path)
    broker = ComputeBroker(project_root=tmp_path, ledger_path=ledger_path)
    price = _price(tmp_path / "price.json")
    broker.plan(_tinker_request(), price_snapshot_path=price)

    with pytest.raises(BrokerPlanError, match="different request"):
        broker.plan(
            _tinker_request(workload={**_tinker_request()["workload"], "prompt_count": 9}),
            price_snapshot_path=price,
        )


def test_invalid_tinker_plan_does_not_mutate_budget(tmp_path: Path) -> None:
    ledger_path = tmp_path / "budget.jsonl"
    BudgetLedger.initialize(ledger_path)
    broker = ComputeBroker(project_root=tmp_path, ledger_path=ledger_path)
    capabilities = tmp_path / "caps.json"
    capabilities.write_text(json.dumps({"supported_models": ["another/model"]}))

    with pytest.raises(BrokerPlanError, match="not present"):
        broker.plan(
            _tinker_request(),
            price_snapshot_path=_price(tmp_path / "price.json"),
            capabilities_path=capabilities,
        )

    assert BudgetLedger(ledger_path).snapshot().active_reserved_usd == Decimal("0.00")


def test_katana_plan_never_touches_tinker_ledger(tmp_path: Path) -> None:
    ledger_path = tmp_path / "budget.jsonl"
    BudgetLedger.initialize(ledger_path)
    broker = ComputeBroker(project_root=tmp_path, ledger_path=ledger_path)

    ticket = broker.plan(_katana_request())

    assert ticket.provider == "katana"
    assert ticket.reservation_id == ""
    assert BudgetLedger(ledger_path).snapshot().active_reserved_usd == Decimal("0.00")


def test_tinker_requires_initialized_ledger_and_price_snapshot(tmp_path: Path) -> None:
    broker = ComputeBroker(project_root=tmp_path, ledger_path=tmp_path / "missing.jsonl")

    with pytest.raises(BrokerPlanError, match="price snapshot"):
        broker.plan(_tinker_request())
    with pytest.raises(BrokerPlanError, match="not initialized"):
        broker.plan(
            _tinker_request(), price_snapshot_path=_price(tmp_path / "price.json")
        )


def test_secret_redaction_is_recursive_and_case_insensitive() -> None:
    redacted = redact_secrets(
        {
            "TINKER_API_KEY": "secret-value",
            "nested": {"password": "p", "safe": "visible"},
            "items": [{"Access_Token": "t"}],
        }
    )

    assert redacted == {
        "TINKER_API_KEY": "[REDACTED]",
        "nested": {"password": "[REDACTED]", "safe": "visible"},
        "items": [{"Access_Token": "[REDACTED]"}],
    }
