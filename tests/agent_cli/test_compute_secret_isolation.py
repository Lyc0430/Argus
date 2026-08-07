from __future__ import annotations

from argus_skill.agent_cli.agent_cli_runner import AgentCliRunner, RunnerOptions
from argus_skill.agent_cli.runner_backend import BACKEND_CLAUDE, BACKEND_CODEX


def test_codex_child_cannot_inherit_tinker_or_compute_broker_secrets(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TINKER_API_KEY", "tinker-secret")
    monkeypatch.setenv("ARGUS_COMPUTE_TINKER_API_KEY", "broker-secret")
    monkeypatch.setenv("ARGUS_COMPUTE_POLICY", "safe-nonsecret-setting")
    monkeypatch.setenv("OPENAI_API_KEY", "codex-auth")
    runner = AgentCliRunner(agent_bin="codex", backend=BACKEND_CODEX)

    env = runner._child_env(RunnerOptions())

    assert env is not None
    assert "TINKER_API_KEY" not in env
    assert "ARGUS_COMPUTE_TINKER_API_KEY" not in env
    assert env["ARGUS_COMPUTE_POLICY"] == "safe-nonsecret-setting"
    assert env["OPENAI_API_KEY"] == "codex-auth"


def test_claude_child_keeps_its_auth_but_not_compute_provider_auth(monkeypatch) -> None:
    monkeypatch.setenv("TINKER_API_KEY", "tinker-secret")
    monkeypatch.setenv("ARGUS_COMPUTE_ACCESS_TOKEN", "broker-secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "claude-auth")
    runner = AgentCliRunner(agent_bin="claude", backend=BACKEND_CLAUDE)

    env = runner._child_env(RunnerOptions())

    assert env is not None
    assert "TINKER_API_KEY" not in env
    assert "ARGUS_COMPUTE_ACCESS_TOKEN" not in env
    assert env["ANTHROPIC_API_KEY"] == "claude-auth"


def test_sandboxed_child_also_scrubs_compute_provider_auth(monkeypatch) -> None:
    monkeypatch.setenv("TINKER_API_KEY", "tinker-secret")
    runner = AgentCliRunner(agent_bin="codex", backend=BACKEND_CODEX)

    env = runner._child_env(RunnerOptions(sandbox_mode="workspace-write"))

    assert env is not None
    assert "TINKER_API_KEY" not in env
