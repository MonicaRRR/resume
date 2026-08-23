import json
from pathlib import Path

import pytest

from resume_mvp.domain import JobAnalysis
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
    sandbox = command.index("--sandbox")
    assert command[sandbox:sandbox + 2] == ["--sandbox", "read-only"]
    assert "--output-schema" in command
    assert runner.last_stdin == "分析岗位"
    assert result.role_title == "后端工程师"
    assert list(tmp_path.iterdir()) == []
