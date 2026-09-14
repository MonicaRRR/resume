import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from resume_mvp.domain import JobAnalysis
from resume_mvp.providers.base import ProviderError
from resume_mvp.providers.codex import CodexProvider, ProcessResult


class FakeRunner:
    def __init__(self) -> None:
        self.last_command: list[str] = []
        self.last_stdin = ""

    async def run(
        self,
        command: list[str],
        *,
        stdin: str,
        cwd: Path,
        timeout: float,
    ) -> ProcessResult:
        self.last_command = command
        self.last_stdin = stdin
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(
            json.dumps(JobAnalysis(role_title="后端工程师").model_dump(mode="json")),
            encoding="utf-8",
        )
        return ProcessResult(returncode=0, stdout="", stderr="")


@pytest.mark.anyio
async def test_codex_uses_ephemeral_read_only_context(tmp_path: Path) -> None:
    """Catches Codex access expanding beyond the minimal temporary context."""
    runner = FakeRunner()
    provider = CodexProvider(runner=runner, temp_parent=tmp_path)

    result = await provider.complete_json("分析岗位", JobAnalysis)
    command = runner.last_command

    assert command[:2] == ["codex", "exec"]
    assert "--ephemeral" in command
    assert "--ask-for-approval" not in command
    sandbox = command.index("--sandbox")
    assert command[sandbox:sandbox + 2] == ["--sandbox", "read-only"]
    assert "--output-schema" in command
    assert runner.last_stdin == "分析岗位"
    assert result.role_title == "后端工程师"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.anyio
async def test_codex_writes_strict_output_schema(tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class CapturingRunner:
        async def run(self, command, *, stdin, cwd, timeout):
            schema_path = Path(command[command.index("--output-schema") + 1])
            captured["schema"] = json.loads(schema_path.read_text(encoding="utf-8"))
            assert "--ask-for-approval" not in command
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            return ProcessResult(returncode=0, stdout="", stderr="")

    class Probe(BaseModel):
        status: str

    provider = CodexProvider(runner=CapturingRunner(), temp_parent=tmp_path)
    await provider.complete_json("ping", Probe)
    schema = captured["schema"]
    assert isinstance(schema, dict)
    assert schema.get("additionalProperties") is False
    assert schema.get("required") == ["status"]


@pytest.mark.anyio
async def test_codex_job_analysis_schema_is_strict(tmp_path: Path) -> None:
    from resume_mvp.providers.codex import schema_for_codex

    schema = schema_for_codex(JobAnalysis)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    requirement = schema["$defs"]["JobRequirement"]
    assert requirement["additionalProperties"] is False
    assert set(requirement["required"]) == set(requirement["properties"])
    assert "exclusiveMinimum" not in requirement["properties"]["weight"]


@pytest.mark.anyio
async def test_codex_retries_without_schema_when_rejected(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    class FlakyRunner:
        async def run(self, command, *, stdin, cwd, timeout):
            calls.append(command)
            if "--output-schema" in command:
                return ProcessResult(
                    returncode=1,
                    stdout="",
                    stderr="invalid_json_schema: additionalProperties is required",
                )
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            return ProcessResult(returncode=0, stdout="", stderr="")

    class Probe(BaseModel):
        status: str

    provider = CodexProvider(runner=FlakyRunner(), temp_parent=tmp_path)
    result = await provider.complete_json("ping", Probe)
    assert result.status == "ok"
    assert any("--output-schema" in command for command in calls)
    assert any("--output-schema" not in command for command in calls)

@pytest.mark.anyio
async def test_codex_surfaces_cli_stderr(tmp_path: Path) -> None:
    class FailingRunner:
        async def run(self, command, *, stdin, cwd, timeout):
            return ProcessResult(
                returncode=2,
                stdout="",
                stderr="error: unexpected argument '--ask-for-approval' found\n",
            )

    provider = CodexProvider(runner=FailingRunner(), temp_parent=tmp_path)
    with pytest.raises(ProviderError, match="参数不兼容"):
        await provider.complete_json("ping", JobAnalysis)


def test_codex_process_env_merges_alias_proxy(monkeypatch) -> None:
    from resume_mvp.providers import codex as codex_module

    monkeypatch.setattr(codex_module, "_PROXY_ALIAS_CACHE", None)
    monkeypatch.setattr(
        codex_module,
        "discover_proxy_from_codex_alias",
        lambda: {"http_proxy": "http://172.16.166.11:3128", "https_proxy": "http://172.16.166.11:3128"},
    )
    monkeypatch.delenv("http_proxy", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    env = codex_module.codex_process_env()
    assert env["http_proxy"] == "http://172.16.166.11:3128"


def test_codex_process_env_overrides_localhost_ide_proxy(monkeypatch) -> None:
    from resume_mvp.providers import codex as codex_module

    monkeypatch.setattr(
        codex_module,
        "discover_proxy_from_codex_alias",
        lambda: {"http_proxy": "http://172.16.166.11:3128", "https_proxy": "http://172.16.166.11:3128"},
    )
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:35125")
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:35125")
    env = codex_module.codex_process_env()
    assert env["http_proxy"] == "http://172.16.166.11:3128"
    assert env["https_proxy"] == "http://172.16.166.11:3128"


def test_summarize_codex_failure_skips_version_banner() -> None:
    from resume_mvp.providers.codex import summarize_codex_failure

    message = summarize_codex_failure(
        "\n".join(
            [
                "WARNING: proceeding, even though we could not create PATH aliases",
                "OpenAI Codex v0.153.4",
                "--------",
                "ERROR: Reconnecting... waiting for network",
                "Proxy connection failed: HTTP CONNECT failed with status 403",
            ]
        )
    )
    assert "0.153.4" not in message
    assert "代理" in message or "Proxy" in message or "403" in message


def test_summarize_codex_failure_permission_denied() -> None:
    from resume_mvp.providers.codex import summarize_codex_failure

    message = summarize_codex_failure(
        "Error: failed to initialize in-process app-server client: Permission denied (os error 13)"
    )
    assert "~/.codex/tmp" in message


def test_summarize_codex_failure_revoked_oauth_token() -> None:
    from resume_mvp.providers.codex import summarize_codex_failure

    message = summarize_codex_failure(
        "\n".join(
            [
                "401 Unauthorized: Encountered invalidated oauth token for user",
                'auth error code: token_revoked',
                "Failed to refresh token: Your session has ended. Please log in again.",
                '"code": "refresh_token_invalidated"',
            ]
        )
    )
    assert "令牌已失效" in message
    assert "尚未登录，请在本机执行" not in message
    assert "codex login" in message


@pytest.mark.anyio
async def test_codex_probe_uses_short_timeout(tmp_path: Path) -> None:
    seen: dict[str, float] = {}

    class CapturingRunner:
        async def run(self, command, *, stdin, cwd, timeout):
            seen["timeout"] = timeout
            output = Path(command[command.index("--output-last-message") + 1])
            output.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            return ProcessResult(returncode=0, stdout="", stderr="")

    provider = CodexProvider(runner=CapturingRunner(), temp_parent=tmp_path, timeout=180)
    result = await provider.probe(timeout=45)
    assert result["status"] == "ok"
    assert seen["timeout"] == 45
    assert provider.timeout == 180