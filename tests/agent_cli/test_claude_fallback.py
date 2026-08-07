from __future__ import annotations

from argus_skill.agent_cli.agent_cli_runner import AgentCliRunner, RunnerOptions
from argus_skill.agent_cli.runner_backend import BACKEND_CLAUDE


def _command(options: RunnerOptions) -> list[str]:
    runner = AgentCliRunner(agent_bin="claude", backend=BACKEND_CLAUDE)
    return runner._build_claude_command(resume_thread_id=None, options=options)


def test_claude_explicit_fable_to_opus_fallback_uses_max_effort() -> None:
    command = _command(
        RunnerOptions(
            model="fable",
            fallback_models=["opus"],
            reasoning_effort="max",
        )
    )

    assert command[command.index("--model") + 1] == "fable"
    assert command[command.index("--fallback-model") + 1] == "opus"
    assert command[command.index("--effort") + 1] == "max"


def test_claude_fable_defaults_to_opus_fallback() -> None:
    command = _command(RunnerOptions(model="fable", reasoning_effort="max"))

    assert command[command.index("--fallback-model") + 1] == "opus"


def test_claude_supports_an_ordered_fallback_chain() -> None:
    command = _command(
        RunnerOptions(model="fable", fallback_models=["opus", "sonnet"])
    )

    assert command[command.index("--fallback-model") + 1] == "opus,sonnet"


def test_claude_xhigh_effort_is_not_silently_downgraded() -> None:
    command = _command(RunnerOptions(model="fable", reasoning_effort="xhigh"))

    assert command[command.index("--effort") + 1] == "xhigh"


def test_claude_fallback_models_reject_empty_or_unsafe_values() -> None:
    for fallback in ([""], ["opus,haiku"], ["--dangerously-skip-permissions"]):
        try:
            _command(RunnerOptions(model="fable", fallback_models=fallback))
        except ValueError as exc:
            assert "fallback model" in str(exc).lower()
        else:  # pragma: no cover - failure message is clearer than parametrization here
            raise AssertionError(f"unsafe fallback was accepted: {fallback!r}")
