"""Evidence verification for completed compute plans."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class VerificationReport:
    accepted: bool
    provider: str
    job_key: str
    evidence_class: str
    findings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["findings"] = list(self.findings)
        return result


def _safe_output_path(root: Path, value: object) -> Path | None:
    candidate = str(value or "").strip().replace("\\", "/")
    posix = PurePosixPath(candidate)
    if not candidate or candidate.startswith("/") or ".." in posix.parts:
        return None
    path = (root / candidate).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if str(value).strip() in {str(result), f"{result}.0"} else None


def verify_compute_run(
    *,
    project_root: Path | str,
    plan: Mapping[str, object],
    manifest: Mapping[str, object],
) -> VerificationReport:
    root = Path(project_root).resolve()
    findings: list[str] = []
    provider = str(manifest.get("provider") or "")
    job_key = str(manifest.get("job_key") or "")
    plan_provider = str(plan.get("provider") or "")
    plan_job_key = str(plan.get("job_key") or "")
    if provider != plan_provider:
        findings.append("manifest provider does not match plan")
    if job_key != plan_job_key:
        findings.append("manifest job_key does not match plan")
    if manifest.get("status") != "completed":
        findings.append("run status is not completed")
    if _integer(manifest.get("exit_code")) != 0:
        findings.append("run exit_code is not zero")
    frozen = manifest.get("frozen") is True
    evidence_class = str(manifest.get("evidence_class") or "")
    plan_frozen = plan.get("frozen") is True
    if frozen != plan_frozen:
        findings.append("manifest frozen flag does not match plan")
    if frozen != (evidence_class == "frozen"):
        findings.append("evidence_class and frozen flag disagree")
    if provider == "tinker" and (frozen or evidence_class != "exploratory"):
        findings.append("Tinker evidence must remain exploratory and frozen:false")

    outputs = manifest.get("outputs")
    expected_raw = plan.get("output_paths")
    expected = {
        str(item) for item in expected_raw
    } if isinstance(expected_raw, list) else set()
    observed: set[str] = set()
    if not isinstance(outputs, list) or not outputs:
        findings.append("missing output manifest")
    else:
        for index, item in enumerate(outputs):
            if not isinstance(item, Mapping):
                findings.append(f"output {index} is not an object")
                continue
            relative = str(item.get("path") or "")
            output_path = _safe_output_path(root, relative)
            if output_path is None:
                findings.append(f"unsafe output path at index {index}")
                continue
            observed.add(relative)
            digest = str(item.get("sha256") or "").lower()
            if not _SHA256.fullmatch(digest):
                findings.append(f"output {relative} has no valid sha256")
                continue
            if not output_path.is_file():
                findings.append(f"output {relative} is missing")
                continue
            actual = hashlib.sha256(output_path.read_bytes()).hexdigest()
            if actual != digest:
                findings.append(f"output {relative} sha256 mismatch")
        for missing in sorted(expected - observed):
            findings.append(f"planned output {missing} is absent from manifest")

    coverage = manifest.get("coverage")
    if not isinstance(coverage, Mapping):
        findings.append("missing episode coverage")
    else:
        expected_episodes = _integer(coverage.get("expected_episodes"))
        completed = _integer(coverage.get("completed_episodes"))
        unique = _integer(coverage.get("unique_episode_keys"))
        duplicates = _integer(coverage.get("duplicate_episode_keys"))
        fields = coverage.get("idempotency_fields")
        if (
            expected_episodes is None
            or completed is None
            or unique is None
            or expected_episodes < 0
            or completed != expected_episodes
            or unique != expected_episodes
        ):
            findings.append("episode coverage incomplete")
        if duplicates is None or duplicates != 0:
            findings.append("duplicate episode keys are present")
        if fields != ["query", "branch", "seed"] and fields != (
            "query",
            "branch",
            "seed",
        ):
            findings.append("episode idempotency fields are not query, branch, seed")

    if provider == "katana" and frozen:
        actor = manifest.get("actor")
        plan_actor = plan.get("actor_fingerprint_inputs")
        if not isinstance(actor, Mapping):
            findings.append("frozen Katana run is missing actor fingerprint")
        else:
            if isinstance(plan_actor, Mapping):
                for field in (
                    "container_sha256",
                    "model_snapshot_sha256",
                    "sampling_config_sha256",
                ):
                    expected_value = plan_actor.get(field)
                    if expected_value is not None and actor.get(field) != expected_value:
                        findings.append(f"actor {field} does not match plan")
            if not str(actor.get("actual_gpu_name") or "").strip() or not str(
                actor.get("actual_gpu_uuid") or ""
            ).strip():
                findings.append("frozen Katana actor is missing actual GPU identity")

    return VerificationReport(
        accepted=not findings,
        provider=provider,
        job_key=job_key,
        evidence_class=evidence_class,
        findings=tuple(findings),
    )


__all__ = ["VerificationReport", "verify_compute_run"]
