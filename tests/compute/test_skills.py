from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from argus_skill.compute.broker import ComputeBroker
from argus_skill.compute.budget import BudgetLedger
from argus_skill.compute.models import ComputeRequest, Provider
from argus_skill.compute.routing import route_request
from argus_skill.compute.verification import verify_compute_run
from argus_skill.skills.builtins import iter_builtin_skill_texts

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".agents" / "skills"


def _load_skill(name: str) -> tuple[dict[str, object], str, Path]:
    path = SKILLS / name / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    match = re.fullmatch(r"---\n(.*?)\n---\n\n(.+)", text, flags=re.DOTALL)
    assert match is not None, f"{path} must use standard YAML frontmatter"
    metadata = yaml.safe_load(match.group(1))
    assert isinstance(metadata, dict)
    return metadata, match.group(2), path


def _assert_standard_skill(name: str) -> tuple[str, Path]:
    metadata, body, path = _load_skill(name)
    assert set(metadata) == {"name", "description"}
    assert metadata["name"] == name
    description = str(metadata["description"])
    assert description.startswith("Use when ")
    assert len(description) <= 500
    assert len(body.split()) <= 500
    assert "TINKER_API_KEY=" not in body
    assert "OPENAI_API_KEY=" not in body
    evals = json.loads((path.parent / "evals" / "evals.json").read_text())
    assert evals["skill_name"] == name
    assert len(evals["evals"]) >= 3
    assert all(item["prompt"] and item["expected_output"] for item in evals["evals"])
    return body, path


def test_route_compute_skill_is_standard_and_examples_obey_hard_routing() -> None:
    body, path = _assert_standard_skill("route-compute")
    assert "references/contract.md" in body
    assert "argus-compute plan" in body

    tinker = ComputeRequest.from_dict(
        json.loads((path.parent / "examples" / "tinker-request.json").read_text())
    )
    katana = ComputeRequest.from_dict(
        json.loads((path.parent / "examples" / "katana-request.json").read_text())
    )

    assert route_request(tinker).provider is Provider.TINKER
    assert route_request(katana).provider is Provider.KATANA
    assert katana.requires_hidden_states is True


def test_run_tinker_skill_is_standard_and_example_passes_budgeted_dry_run(
    tmp_path: Path,
) -> None:
    body, path = _assert_standard_skill("run-tinker")
    assert "references/contract.md" in body
    assert "num_samples" in body
    assert "asyncio.gather" in body
    assert "SDK" in body

    ledger_path = tmp_path / "budget.jsonl"
    BudgetLedger.initialize(ledger_path)
    request = json.loads((path.parent / "examples" / "sampling-request.json").read_text())
    ticket = ComputeBroker(project_root=tmp_path, ledger_path=ledger_path).plan(
        request,
        price_snapshot_path=path.parent / "examples" / "price-snapshot.json",
    )
    plan = json.loads((tmp_path / ticket.plan_path).read_text())

    assert plan["provider"] == "tinker"
    assert plan["frozen"] is False
    assert plan["request_count"] == request["workload"]["prompt_count"]
    assert plan["num_samples"] == request["workload"]["num_samples"]
    assert plan["sdk_retry_owned"] is True
    assert plan["client_timeout_seconds"] is None


def test_run_katana_skill_is_standard_and_example_renders_safe_pbs(
    tmp_path: Path,
) -> None:
    body, path = _assert_standard_skill("run-katana")
    assert "references/contract.md" in body
    assert "/opt/pbs/bin/qsub" in body
    assert "/opt/pbs/bin/qstat" in body
    assert "episode_append_only" in body

    request = json.loads((path.parent / "examples" / "pbs-request.json").read_text())
    ticket = ComputeBroker(project_root=tmp_path).plan(request)
    plan = json.loads((tmp_path / ticket.plan_path).read_text())
    script = plan["shards"][0]["script_text"]

    assert plan["provider"] == "katana"
    assert len(plan["shards"]) == len(request["workload"]["shards"])
    assert "#PBS -q" not in script
    assert "gpu_model" not in script
    assert "#PBS -l walltime=02:00:00" in script
    assert plan["shards"][0]["submit_argv"][0] == "/opt/pbs/bin/qsub"


def test_verify_compute_run_skill_is_standard_and_examples_enforce_evidence() -> None:
    body, path = _assert_standard_skill("verify-compute-run")
    assert "references/contract.md" in body
    assert "exit code" in body.lower()
    examples = path.parent / "examples"

    valid = verify_compute_run(
        project_root=examples,
        plan=json.loads((examples / "katana-plan.json").read_text()),
        manifest=json.loads((examples / "katana-manifest.json").read_text()),
    )
    invalid = verify_compute_run(
        project_root=examples,
        plan=json.loads((examples / "tinker-plan.json").read_text()),
        manifest=json.loads((examples / "tinker-frozen-manifest.json").read_text()),
    )

    assert valid.accepted is True
    assert invalid.accepted is False
    assert "Tinker evidence must remain exploratory and frozen:false" in invalid.findings


def test_argus_native_role_mirrors_are_packaged_and_secret_free() -> None:
    bundled = dict(iter_builtin_skill_texts())
    expected = {
        "planner/route-compute.md": "argus-compute plan",
        "engineer/run-tinker.md": "frozen:false",
        "engineer/run-katana.md": "/opt/pbs/bin/qsub",
        "reviewer/verify-compute-run.md": "argus-compute verify",
    }

    for relative_path, required_text in expected.items():
        text = bundled[relative_path]
        assert required_text in text
        assert "TINKER_API_KEY=" not in text
        assert "OPENAI_API_KEY=" not in text
