from __future__ import annotations

import pytest

from argus_skill.compute.katana import KatanaPlanError, build_katana_plan
from argus_skill.compute.models import ComputeRequest


def _workload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "smoke": False,
        "scratch_dir": "/srv/scratch/nemesis/consequence",
        "log_dir": "/srv/scratch/nemesis/logs",
        "shards": ["s0", "s1"],
        "runtime": {
            "kind": "container",
            "container_path": "/srv/scratch/nemesis/containers/verl_vllm015.sif",
            "container_sha256": "a" * 64,
            "command": [
                "python",
                "-m",
                "consequence.runner",
                "--config",
                "configs/models.yaml",
            ],
        },
        "checkpoint": {
            "mode": "episode_append_only",
            "path": "/srv/scratch/nemesis/consequence/checkpoints/main-001",
            "idempotency_fields": ["query", "branch", "seed"],
        },
        "actor": {
            "model_snapshot_path": "/srv/scratch/nemesis/models/qwen3.5-4b",
            "model_snapshot_sha256": "b" * 64,
            "sampling_config_path": "configs/models.yaml",
            "sampling_config_sha256": "c" * 64,
        },
    }
    value.update(overrides)
    return value


def _request(**overrides: object) -> ComputeRequest:
    payload: dict[str, object] = {
        "version": 1,
        "job_key": "katana.main.001",
        "mission_id": "mission-1",
        "project": "consequence",
        "task_kind": "evaluation",
        "evidence_class": "frozen",
        "provider_hint": "katana",
        "model": "Qwen/Qwen3.5-4B",
        "estimated_cost_usd": 0,
        "expected_outputs": ["runs/katana/main-001/manifest.json"],
        "workload": _workload(),
        "resources": {"ncpus": 18, "ngpus": 1, "memory_gb": 120},
    }
    payload.update(overrides)
    return ComputeRequest.from_dict(payload)


def test_standard_plan_renders_one_unpinned_pbs_script_per_shard() -> None:
    plan = build_katana_plan(_request())

    assert plan.walltime == "12:00:00"
    assert plan.queue is None
    assert plan.gpu_model is None
    assert plan.status_argv == ("/opt/pbs/bin/qstat", "-u", "z5614191")
    assert [shard.shard_id for shard in plan.shards] == ["s0", "s1"]
    assert all(shard.submit_argv[0] == "/opt/pbs/bin/qsub" for shard in plan.shards)
    assert len({shard.remote_script_path for shard in plan.shards}) == 2
    assert plan.frozen is True

    script = plan.shards[0].script_text
    assert "#PBS -q" not in script
    assert "gpu_model" not in script
    assert "#PBS -l walltime=12:00:00" in script
    assert "#PBS -l select=1:ncpus=18:ngpus=1:mem=120gb" in script
    assert "#PBS -j oe" in script
    assert "#PBS -o /srv/scratch/nemesis/logs/katana-main-001.s0.log" in script
    assert "cd /srv/scratch/nemesis/consequence" in script
    assert "ARGUS_COMPUTE_RESUME=1" in script
    assert "ARGUS_COMPUTE_SHARD_ID=s0" in script
    assert "nvidia-smi --query-gpu=name,uuid" in script
    assert (
        "apptainer exec --nv /srv/scratch/nemesis/containers/verl_vllm015.sif "
        "python -m consequence.runner --config configs/models.yaml"
    ) in script


def test_smoke_plan_uses_two_hours() -> None:
    plan = build_katana_plan(_request(workload=_workload(smoke=True, shards=["debug"])))

    assert plan.walltime == "02:00:00"
    assert "#PBS -l walltime=02:00:00" in plan.shards[0].script_text


def test_afterok_dependency_is_an_explicit_qsub_argument() -> None:
    plan = build_katana_plan(
        _request(workload=_workload(shards=["s0"], afterok_job_id="12345.kat"))
    )

    assert plan.shards[0].submit_argv == (
        "/opt/pbs/bin/qsub",
        "-W",
        "depend=afterok:12345.kat",
        "/srv/scratch/nemesis/consequence/.argus_compute/jobs/katana-main-001/s0.pbs",
    )


def test_explicit_memory_floor_uses_boolean_resource_not_gpu_model() -> None:
    resources = {
        "ncpus": 18,
        "ngpus": 1,
        "memory_gb": 120,
        "min_gpu_memory_gb": 93,
        "memory_requirement_reason": "72B tensor parallel shard requires at least 93 GB",
    }
    plan = build_katana_plan(_request(resources=resources))

    assert "mem_per_gpu_gte_93=True" in plan.shards[0].script_text
    assert plan.requested_gpu_memory_floor_gb == 93
    assert plan.gpu_model is None


@pytest.mark.parametrize("forbidden", ["queue", "gpu_model", "gpu_type"])
def test_queue_and_gpu_model_pins_are_rejected(forbidden: str) -> None:
    resources = {"ncpus": 18, "ngpus": 1, "memory_gb": 120, forbidden: "H200"}

    with pytest.raises(KatanaPlanError, match=forbidden):
        build_katana_plan(_request(resources=resources))


def test_memory_floor_requires_supported_threshold_and_scientific_reason() -> None:
    with pytest.raises(KatanaPlanError, match="supported threshold"):
        build_katana_plan(
            _request(
                resources={
                    "ncpus": 18,
                    "ngpus": 1,
                    "memory_gb": 120,
                    "min_gpu_memory_gb": 100,
                    "memory_requirement_reason": "need memory",
                }
            )
        )
    with pytest.raises(KatanaPlanError, match="memory_requirement_reason"):
        build_katana_plan(
            _request(
                resources={
                    "ncpus": 18,
                    "ngpus": 1,
                    "memory_gb": 120,
                    "min_gpu_memory_gb": 93,
                }
            )
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("scratch_dir", "/home/z5614191/run", "/srv/scratch/nemesis"),
        ("log_dir", "/tmp/logs", "/srv/scratch/nemesis"),
        ("shards", ["bad\n#PBS -q hacked"], "shard"),
        ("afterok_job_id", "123; touch /tmp/pwn", "afterok"),
    ],
)
def test_paths_and_scheduler_identifiers_reject_login_home_or_injection(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(KatanaPlanError, match=message):
        build_katana_plan(_request(workload=_workload(**{field: value})))


def test_command_arguments_reject_control_characters() -> None:
    runtime = dict(_workload()["runtime"])
    runtime["command"] = ["python", "-c", "print(1)\n#PBS -q hacked"]

    with pytest.raises(KatanaPlanError, match="control character"):
        build_katana_plan(_request(workload=_workload(runtime=runtime)))


def test_frozen_plan_requires_complete_actor_fingerprint_inputs() -> None:
    actor = dict(_workload()["actor"])
    actor.pop("model_snapshot_sha256")

    with pytest.raises(KatanaPlanError, match="model_snapshot_sha256"):
        build_katana_plan(_request(workload=_workload(actor=actor)))


def test_episode_resume_contract_is_exact_and_fail_closed() -> None:
    checkpoint = dict(_workload()["checkpoint"])
    checkpoint["idempotency_fields"] = ["query", "seed"]

    with pytest.raises(KatanaPlanError, match="query, branch, seed"):
        build_katana_plan(_request(workload=_workload(checkpoint=checkpoint)))


def test_exploratory_katana_plan_stays_exploratory() -> None:
    plan = build_katana_plan(_request(evidence_class="exploratory"))

    assert plan.frozen is False
