from __future__ import annotations

import json
from pathlib import Path

from argus_skill.compute.cli import main

ROOT = Path(__file__).resolve().parents[2]


def _request(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "job_key": "cli.katana.001",
                "mission_id": "mission-1",
                "project": "consequence",
                "task_kind": "evaluation",
                "evidence_class": "frozen",
                "provider_hint": "katana",
                "model": "Qwen/Qwen3.5-4B",
                "estimated_cost_usd": 0,
                "requires_main_table": True,
                "expected_outputs": ["runs/manifest.json"],
                "resources": {"ncpus": 18, "ngpus": 1, "memory_gb": 120},
                "workload": {
                    "smoke": True,
                    "scratch_dir": "/srv/scratch/nemesis/consequence",
                    "log_dir": "/srv/scratch/nemesis/logs",
                    "shards": ["s0"],
                    "runtime": {
                        "kind": "container",
                        "container_path": "/srv/scratch/nemesis/containers/verl_dev.sif",
                        "container_sha256": "a" * 64,
                        "command": ["python", "-m", "consequence.runner"],
                    },
                    "checkpoint": {
                        "mode": "episode_append_only",
                        "path": "/srv/scratch/nemesis/consequence/checkpoints/cli",
                        "idempotency_fields": ["query", "branch", "seed"],
                    },
                    "actor": {
                        "model_snapshot_path": "/srv/scratch/nemesis/models/qwen",
                        "model_snapshot_sha256": "b" * 64,
                        "sampling_config_path": "configs/models.yaml",
                        "sampling_config_sha256": "c" * 64,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_cli_plan_and_status_emit_one_json_object_each(
    tmp_path: Path, capsys
) -> None:
    request_path = _request(tmp_path / "request.json")
    ledger_path = tmp_path / "budget.jsonl"

    assert main(["init-budget", "--ledger", str(ledger_path)]) == 0
    initialized = json.loads(capsys.readouterr().out)
    assert initialized["status"] == "initialized"

    assert (
        main(
            [
                "plan",
                "--project-root",
                str(tmp_path),
                "--ledger",
                str(ledger_path),
                "--request",
                str(request_path),
            ]
        )
        == 0
    )
    ticket = json.loads(capsys.readouterr().out)
    assert ticket["provider"] == "katana"
    assert ticket["dry_run"] is True

    assert (
        main(
            [
                "status",
                "--project-root",
                str(tmp_path),
                "--job-key",
                "cli.katana.001",
            ]
        )
        == 0
    )
    status = json.loads(capsys.readouterr().out)
    assert status["job_key"] == "cli.katana.001"


def test_cli_errors_are_json_and_redact_secret_values(tmp_path: Path, capsys) -> None:
    request = tmp_path / "bad.json"
    request.write_text(
        json.dumps({"TINKER_API_KEY": "do-not-print", "job_key": "x"}),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "plan",
            "--project-root",
            str(tmp_path),
            "--ledger",
            str(tmp_path / "missing.jsonl"),
            "--request",
            str(request),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    error = json.loads(captured.err)
    assert error["status"] == "error"
    assert "do-not-print" not in captured.err


def test_cli_verify_emits_evidence_report(capsys) -> None:
    examples = ROOT / ".agents" / "skills" / "verify-compute-run" / "examples"

    exit_code = main(
        [
            "verify",
            "--project-root",
            str(examples),
            "--plan",
            str(examples / "katana-plan.json"),
            "--manifest",
            str(examples / "katana-manifest.json"),
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert report["accepted"] is True
    assert report["provider"] == "katana"


def test_cli_verify_rejects_invalid_evidence_with_distinct_exit_code(capsys) -> None:
    examples = ROOT / ".agents" / "skills" / "verify-compute-run" / "examples"

    exit_code = main(
        [
            "verify",
            "--project-root",
            str(examples),
            "--plan",
            str(examples / "tinker-plan.json"),
            "--manifest",
            str(examples / "tinker-frozen-manifest.json"),
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 3
    assert report["accepted"] is False


def test_cli_katana_plan_does_not_require_tinker_ledger(
    tmp_path: Path, capsys
) -> None:
    exit_code = main(
        [
            "plan",
            "--project-root",
            str(tmp_path),
            "--request",
            str(_request(tmp_path / "katana.json")),
        ]
    )

    ticket = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert ticket["provider"] == "katana"
