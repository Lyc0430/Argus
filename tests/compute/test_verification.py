from __future__ import annotations

import hashlib
from pathlib import Path

from argus_skill.compute.verification import verify_compute_run


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plan(provider: str = "katana", *, frozen: bool = True) -> dict[str, object]:
    return {
        "version": 1,
        "provider": provider,
        "job_key": "verify.job.001",
        "frozen": frozen,
        "output_paths": ["runs/result.json"],
        "actor_fingerprint_inputs": {
            "container_sha256": "a" * 64,
            "model_snapshot_sha256": "b" * 64,
            "sampling_config_sha256": "c" * 64,
            "actual_gpu_capture_required": True,
        },
    }


def _manifest(result: Path, **overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "version": 1,
        "job_key": "verify.job.001",
        "provider": "katana",
        "evidence_class": "frozen",
        "frozen": True,
        "status": "completed",
        "exit_code": 0,
        "outputs": [{"path": "runs/result.json", "sha256": _sha(result)}],
        "coverage": {
            "expected_episodes": 12,
            "completed_episodes": 12,
            "unique_episode_keys": 12,
            "duplicate_episode_keys": 0,
            "idempotency_fields": ["query", "branch", "seed"],
        },
        "actor": {
            "container_sha256": "a" * 64,
            "model_snapshot_sha256": "b" * 64,
            "sampling_config_sha256": "c" * 64,
            "actual_gpu_name": "NVIDIA H200",
            "actual_gpu_uuid": "GPU-123",
        },
    }
    value.update(overrides)
    return value


def test_complete_katana_manifest_with_matching_hashes_is_accepted(tmp_path: Path) -> None:
    result = tmp_path / "runs" / "result.json"
    result.parent.mkdir()
    result.write_text('{"ok":true}\n')

    report = verify_compute_run(
        project_root=tmp_path,
        plan=_plan(),
        manifest=_manifest(result),
    )

    assert report.accepted is True
    assert report.findings == ()


def test_zero_exit_code_without_outputs_or_coverage_is_not_evidence(tmp_path: Path) -> None:
    report = verify_compute_run(
        project_root=tmp_path,
        plan=_plan(),
        manifest={
            "version": 1,
            "job_key": "verify.job.001",
            "provider": "katana",
            "status": "completed",
            "exit_code": 0,
        },
    )

    assert report.accepted is False
    assert "missing output manifest" in report.findings
    assert "missing episode coverage" in report.findings


def test_hash_mismatch_and_partial_or_duplicate_coverage_are_rejected(tmp_path: Path) -> None:
    result = tmp_path / "runs" / "result.json"
    result.parent.mkdir()
    result.write_text("changed")
    manifest = _manifest(result)
    manifest["outputs"] = [{"path": "runs/result.json", "sha256": "d" * 64}]
    manifest["coverage"] = {
        "expected_episodes": 12,
        "completed_episodes": 11,
        "unique_episode_keys": 10,
        "duplicate_episode_keys": 1,
        "idempotency_fields": ["query", "branch", "seed"],
    }

    report = verify_compute_run(project_root=tmp_path, plan=_plan(), manifest=manifest)

    assert report.accepted is False
    assert any("sha256 mismatch" in finding for finding in report.findings)
    assert any("coverage incomplete" in finding for finding in report.findings)
    assert any("duplicate episode" in finding for finding in report.findings)


def test_tinker_manifest_cannot_claim_frozen_evidence(tmp_path: Path) -> None:
    result = tmp_path / "runs" / "result.json"
    result.parent.mkdir()
    result.write_text("ok")
    manifest = _manifest(
        result,
        provider="tinker",
        evidence_class="frozen",
        frozen=True,
        actor={},
    )

    report = verify_compute_run(
        project_root=tmp_path,
        plan=_plan(provider="tinker", frozen=False),
        manifest=manifest,
    )

    assert report.accepted is False
    assert "Tinker evidence must remain exploratory and frozen:false" in report.findings


def test_frozen_katana_manifest_requires_actual_gpu_and_matching_actor(tmp_path: Path) -> None:
    result = tmp_path / "runs" / "result.json"
    result.parent.mkdir()
    result.write_text("ok")
    manifest = _manifest(result)
    manifest["actor"] = {
        "container_sha256": "f" * 64,
        "model_snapshot_sha256": "b" * 64,
        "sampling_config_sha256": "c" * 64,
    }

    report = verify_compute_run(project_root=tmp_path, plan=_plan(), manifest=manifest)

    assert report.accepted is False
    assert any("container_sha256" in finding for finding in report.findings)
    assert "frozen Katana actor is missing actual GPU identity" in report.findings


def test_unsafe_output_path_is_rejected_without_reading_outside_project(
    tmp_path: Path,
) -> None:
    outside = tmp_path.parent / "outside-secret"
    outside.write_text("secret")
    manifest = _manifest(outside)
    manifest["outputs"] = [{"path": "../outside-secret", "sha256": _sha(outside)}]

    report = verify_compute_run(project_root=tmp_path, plan=_plan(), manifest=manifest)

    assert report.accepted is False
    assert any("unsafe output path" in finding for finding in report.findings)
