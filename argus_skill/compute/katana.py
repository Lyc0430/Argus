"""Typed, non-submitting PBS plans for UNSW Katana."""
from __future__ import annotations

import os
import re
import shlex
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any, Mapping

from .models import ComputeRequest

KATANA_USER = os.environ.get("ARGUS_KATANA_USER", "z5614191").strip()
KATANA_HOST = os.environ.get(
    "ARGUS_KATANA_HOST", "katana.restech.unsw.edu.au"
).strip()
KATANA_SSH_TARGET = f"{KATANA_USER}@{KATANA_HOST}"
KATANA_SCRATCH_ROOT = PurePosixPath("/srv/scratch/nemesis")
QSUB = "/opt/pbs/bin/qsub"
QSTAT = "/opt/pbs/bin/qstat"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_GPU_MEMORY_THRESHOLDS = frozenset({45, 62, 93, 120, 124, 180, 240, 250, 500})


class KatanaPlanError(ValueError):
    """A request cannot be rendered as a safe Katana PBS plan."""


def _mapping(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise KatanaPlanError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise KatanaPlanError(f"{field} must be a positive integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise KatanaPlanError(f"{field} must be a positive integer") from exc
    if result <= 0 or str(value).strip() not in {str(result), f"{result}.0"}:
        raise KatanaPlanError(f"{field} must be a positive integer")
    return result


def _scratch_path(value: object, *, field: str, allow_root: bool = False) -> PurePosixPath:
    candidate = PurePosixPath(str(value or "").strip())
    try:
        candidate.relative_to(KATANA_SCRATCH_ROOT)
    except ValueError as exc:
        raise KatanaPlanError(
            f"{field} must stay under /srv/scratch/nemesis"
        ) from exc
    if not candidate.is_absolute() or (candidate == KATANA_SCRATCH_ROOT and not allow_root):
        raise KatanaPlanError(f"{field} must name a project path under /srv/scratch/nemesis")
    if ".." in candidate.parts:
        raise KatanaPlanError(f"{field} contains an unsafe path")
    return candidate


def _relative_path(value: object, *, field: str) -> str:
    candidate = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(candidate)
    if not candidate or candidate.startswith("/") or ".." in path.parts:
        raise KatanaPlanError(f"{field} must be a safe project-relative path")
    return path.as_posix()


def _sha(value: object, *, field: str) -> str:
    digest = str(value or "").strip().lower()
    if not _SHA256.fullmatch(digest):
        raise KatanaPlanError(f"{field} must be a 64-character sha256")
    return digest


def _safe_argv(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise KatanaPlanError("runtime.command must be a non-empty argument list")
    result: list[str] = []
    for raw in value:
        item = str(raw)
        if not item or any(ord(char) < 32 or ord(char) == 127 for char in item):
            raise KatanaPlanError("runtime.command contains an empty or control character")
        if len(item) > 4096:
            raise KatanaPlanError("runtime.command argument exceeds 4096 characters")
        result.append(item)
    return tuple(result)


def _slug(value: str, *, maximum: int = 40) -> str:
    slug = re.sub(r"[^A-Za-z0-9-]+", "-", value).strip("-").lower()
    return (slug or "job")[:maximum].rstrip("-")


@dataclass(frozen=True)
class KatanaShardPlan:
    shard_id: str
    remote_script_path: str
    run_dir: str
    log_path: str
    script_text: str
    submit_argv: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["submit_argv"] = list(self.submit_argv)
        return result


@dataclass(frozen=True)
class KatanaPlan:
    version: int
    provider: str
    job_key: str
    mission_id: str
    ssh_target: str
    walltime: str
    queue: None
    gpu_model: None
    requested_gpu_memory_floor_gb: int | None
    memory_requirement_reason: str
    status_argv: tuple[str, ...]
    actor_fingerprint_inputs: dict[str, Any]
    shards: tuple[KatanaShardPlan, ...]
    output_paths: tuple[str, ...]
    frozen: bool

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status_argv"] = list(self.status_argv)
        result["shards"] = [shard.to_dict() for shard in self.shards]
        result["output_paths"] = list(self.output_paths)
        return result


def _runtime_command(runtime: dict[str, Any]) -> tuple[str, tuple[str, ...], dict[str, str]]:
    kind = str(runtime.get("kind") or "").strip()
    command = _safe_argv(runtime.get("command"))
    if kind == "container":
        container_path = _scratch_path(
            runtime.get("container_path"), field="container_path"
        )
        containers_root = KATANA_SCRATCH_ROOT / "containers"
        try:
            container_path.relative_to(containers_root)
        except ValueError as exc:
            raise KatanaPlanError(
                "container_path must stay under /srv/scratch/nemesis/containers"
            ) from exc
        if container_path.suffix != ".sif":
            raise KatanaPlanError("container_path must name an Apptainer .sif image")
        fingerprint = {
            "runtime_kind": kind,
            "container_path": str(container_path),
            "container_sha256": _sha(
                runtime.get("container_sha256"), field="container_sha256"
            ),
        }
        argv = ("apptainer", "exec", "--nv", str(container_path), *command)
        return shlex.join(argv), command, fingerprint
    if kind == "conda":
        conda_env = str(runtime.get("conda_env") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", conda_env):
            raise KatanaPlanError("conda_env is invalid")
        prefix = (
            "source /srv/scratch/nemesis/conda/etc/profile.d/conda.sh\n"
            f"conda activate {shlex.quote(conda_env)}\n"
        )
        return prefix + shlex.join(command), command, {
            "runtime_kind": kind,
            "conda_env": conda_env,
        }
    raise KatanaPlanError("runtime.kind must be container or conda")


def build_katana_plan(request: ComputeRequest) -> KatanaPlan:
    workload = _mapping(request.workload, field="workload")
    resources = _mapping(request.resources, field="resources")
    for forbidden in ("queue", "gpu_model", "gpu_type"):
        if forbidden in resources or forbidden in workload:
            raise KatanaPlanError(
                f"{forbidden} is forbidden by the default Katana routing policy"
            )
    scratch_dir = _scratch_path(workload.get("scratch_dir"), field="scratch_dir")
    log_dir = _scratch_path(workload.get("log_dir"), field="log_dir")
    shards_raw = workload.get("shards")
    if not isinstance(shards_raw, (list, tuple)) or not shards_raw:
        raise KatanaPlanError("shards must contain at least one shard id")
    shards = tuple(str(shard or "").strip() for shard in shards_raw)
    if len(shards) > 256 or len(set(shards)) != len(shards):
        raise KatanaPlanError("shards must be unique and contain at most 256 items")
    if any(not _SAFE_ID.fullmatch(shard) for shard in shards):
        raise KatanaPlanError("each shard id must be a safe scheduler identifier")
    afterok = str(workload.get("afterok_job_id") or "").strip()
    if afterok and not _SAFE_ID.fullmatch(afterok):
        raise KatanaPlanError("afterok_job_id is not a safe PBS job identifier")
    ncpus = _positive_int(resources.get("ncpus", 18), field="ncpus")
    ngpus = _positive_int(resources.get("ngpus", 1), field="ngpus")
    memory_gb = _positive_int(resources.get("memory_gb", 120), field="memory_gb")
    floor_raw = resources.get("min_gpu_memory_gb")
    floor = None if floor_raw is None else _positive_int(
        floor_raw, field="min_gpu_memory_gb"
    )
    memory_reason = " ".join(
        str(resources.get("memory_requirement_reason") or "").split()
    )[:500]
    if floor is not None:
        if floor not in _GPU_MEMORY_THRESHOLDS:
            raise KatanaPlanError(
                "min_gpu_memory_gb must be a supported threshold: "
                + ", ".join(str(value) for value in sorted(_GPU_MEMORY_THRESHOLDS))
            )
        if not memory_reason:
            raise KatanaPlanError(
                "memory_requirement_reason is required for a GPU memory floor"
            )
    elif memory_reason:
        raise KatanaPlanError(
            "memory_requirement_reason requires min_gpu_memory_gb"
        )
    checkpoint = _mapping(workload.get("checkpoint"), field="checkpoint")
    if checkpoint.get("mode") != "episode_append_only":
        raise KatanaPlanError("checkpoint.mode must be episode_append_only")
    checkpoint_path = _scratch_path(checkpoint.get("path"), field="checkpoint.path")
    fields = checkpoint.get("idempotency_fields")
    if fields != ["query", "branch", "seed"] and fields != (
        "query",
        "branch",
        "seed",
    ):
        raise KatanaPlanError(
            "checkpoint idempotency_fields must be exactly query, branch, seed"
        )
    runtime = _mapping(workload.get("runtime"), field="runtime")
    command_text, _command, runtime_fingerprint = _runtime_command(runtime)
    actor = _mapping(workload.get("actor"), field="actor")
    actor_inputs: dict[str, Any] = {
        **runtime_fingerprint,
        "requested_model": request.model,
        "requested_gpu_memory_floor_gb": floor,
        "actual_gpu_capture_required": True,
    }
    if request.frozen:
        model_path = _scratch_path(
            actor.get("model_snapshot_path"), field="model_snapshot_path"
        )
        actor_inputs.update(
            {
                "model_snapshot_path": str(model_path),
                "model_snapshot_sha256": _sha(
                    actor.get("model_snapshot_sha256"),
                    field="model_snapshot_sha256",
                ),
                "sampling_config_path": _relative_path(
                    actor.get("sampling_config_path"), field="sampling_config_path"
                ),
                "sampling_config_sha256": _sha(
                    actor.get("sampling_config_sha256"),
                    field="sampling_config_sha256",
                ),
            }
        )
    walltime = "02:00:00" if workload.get("smoke") is True else "12:00:00"
    resource_select = f"select=1:ncpus={ncpus}:ngpus={ngpus}:mem={memory_gb}gb"
    if floor is not None:
        resource_select += f":mem_per_gpu_gte_{floor}=True"
    job_slug = _slug(request.job_key)
    jobs_root = scratch_dir / ".argus_compute" / "jobs" / job_slug
    shard_plans: list[KatanaShardPlan] = []
    for shard in shards:
        run_dir = jobs_root / "runs" / shard
        remote_script = jobs_root / f"{shard}.pbs"
        log_path = log_dir / f"{job_slug}.{shard}.log"
        actor_manifest = run_dir / "actor-manifest.json"
        gpu_capture = run_dir / "gpu.csv"
        job_name = f"argus-{job_slug}-{_slug(shard, maximum=12)}"[:63].rstrip("-")
        script_lines = [
            "#!/usr/bin/env bash",
            f"#PBS -N {job_name}",
            f"#PBS -l walltime={walltime}",
            f"#PBS -l {resource_select}",
            "#PBS -j oe",
            f"#PBS -o {log_path}",
            "",
            "set -euo pipefail",
            f"cd {shlex.quote(str(scratch_dir))}",
            f"export ARGUS_COMPUTE_JOB_KEY={shlex.quote(request.job_key)}",
            f"export ARGUS_COMPUTE_SHARD_ID={shlex.quote(shard)}",
            "export ARGUS_COMPUTE_RESUME=1",
            f"export ARGUS_COMPUTE_CHECKPOINT_PATH={shlex.quote(str(checkpoint_path))}",
            f"export ARGUS_COMPUTE_ACTOR_MANIFEST={shlex.quote(str(actor_manifest))}",
            f"mkdir -p {shlex.quote(str(run_dir))}",
            (
                "nvidia-smi --query-gpu=name,uuid --format=csv,noheader > "
                f"{shlex.quote(str(gpu_capture))}"
            ),
            command_text,
            "",
        ]
        submit = [QSUB]
        if afterok:
            submit.extend(["-W", f"depend=afterok:{afterok}"])
        submit.append(str(remote_script))
        shard_plans.append(
            KatanaShardPlan(
                shard_id=shard,
                remote_script_path=str(remote_script),
                run_dir=str(run_dir),
                log_path=str(log_path),
                script_text="\n".join(script_lines),
                submit_argv=tuple(submit),
            )
        )
    return KatanaPlan(
        version=1,
        provider="katana",
        job_key=request.job_key,
        mission_id=request.mission_id,
        ssh_target=KATANA_SSH_TARGET,
        walltime=walltime,
        queue=None,
        gpu_model=None,
        requested_gpu_memory_floor_gb=floor,
        memory_requirement_reason=memory_reason,
        status_argv=(QSTAT, "-u", KATANA_USER),
        actor_fingerprint_inputs=actor_inputs,
        shards=tuple(shard_plans),
        output_paths=request.expected_outputs,
        frozen=request.frozen,
    )


__all__ = [
    "KATANA_SCRATCH_ROOT",
    "KatanaPlan",
    "KatanaPlanError",
    "KatanaShardPlan",
    "build_katana_plan",
]
