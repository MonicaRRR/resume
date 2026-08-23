from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol, TypeVar

from pydantic import BaseModel

from resume_mvp.providers.base import (
    ProviderAuthError,
    ProviderError,
    ProviderTimeoutError,
    validate_json_response,
)


T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


class ProcessRunner(Protocol):
    async def run(
        self,
        command: list[str],
        *,
        stdin: str,
        cwd: Path,
        timeout: float,
    ) -> ProcessResult:
        ...


class AsyncProcessRunner:
    async def run(
        self,
        command: list[str],
        *,
        stdin: str,
        cwd: Path,
        timeout: float,
    ) -> ProcessResult:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(stdin.encode("utf-8")),
                timeout=timeout,
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            raise
        except asyncio.CancelledError:
            process.terminate()
            await process.wait()
            raise
        return ProcessResult(
            returncode=process.returncode or 0,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
        )


class CodexProvider:
    def __init__(
        self,
        *,
        runner: ProcessRunner | None = None,
        temp_parent: Path | None = None,
        timeout: float = 180,
        model: str = "",
    ) -> None:
        self.runner = runner or AsyncProcessRunner()
        self.temp_parent = temp_parent
        self.timeout = timeout
        self.model = model

    async def complete_json(self, prompt: str, schema: type[T]) -> T:
        with TemporaryDirectory(dir=self.temp_parent, prefix="resume-codex-") as directory:
            root = Path(directory)
            schema_path = root / "output-schema.json"
            output_path = root / "last-message.json"
            schema_path.write_text(
                json.dumps(schema.model_json_schema(), ensure_ascii=False),
                encoding="utf-8",
            )
            command = [
                "codex",
                "exec",
                "-",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--ask-for-approval",
                "never",
                "--skip-git-repo-check",
                "-C",
                str(root),
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "--color",
                "never",
            ]
            if self.model:
                command.extend(["--model", self.model])
            try:
                result = await self.runner.run(
                    command,
                    stdin=prompt,
                    cwd=root,
                    timeout=self.timeout,
                )
            except TimeoutError as error:
                raise ProviderTimeoutError("Codex 请求超时") from error
            except FileNotFoundError as error:
                raise ProviderError("未找到 Codex CLI") from error

            if result.returncode != 0:
                lowered = result.stderr.lower()
                if "login" in lowered or "authentication" in lowered:
                    raise ProviderAuthError("Codex 尚未登录")
                raise ProviderError("Codex 未能完成本次任务")
            raw = output_path.read_text(encoding="utf-8") if output_path.exists() else result.stdout
            return validate_json_response(raw, schema)
