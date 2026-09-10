from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from typing import Any, Protocol, TypeVar

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


@dataclass(frozen=True)
class CodexModelOption:
    slug: str
    display_name: str
    description: str = ""


@dataclass(frozen=True)
class CodexDetectResult:
    installed: bool
    authenticated: bool
    available: bool
    version: str = ""
    default_model: str = ""
    binary_path: str = ""
    models: list[CodexModelOption] = field(default_factory=list)
    message: str = ""


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
        env = codex_process_env() if command and command[0] == "codex" else None
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
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


_PROXY_ALIAS_CACHE: dict[str, str] | None = None


def discover_proxy_from_codex_alias() -> dict[str, str]:
    """Mirror interactive shell aliases like: alias codex='http_proxy=... codex'."""
    global _PROXY_ALIAS_CACHE
    if _PROXY_ALIAS_CACHE is not None:
        return dict(_PROXY_ALIAS_CACHE)

    import re
    import subprocess

    found: dict[str, str] = {}
    try:
        completed = subprocess.run(
            ["bash", "-ic", "alias codex"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        _PROXY_ALIAS_CACHE = {}
        return {}

    text = f"{completed.stdout}\n{completed.stderr}"
    for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
        match = re.search(rf"{key}=([^\s'\"]+)", text)
        if match:
            found[key] = match.group(1)
    _PROXY_ALIAS_CACHE = found
    return dict(found)


def _proxy_looks_local(value: str) -> bool:
    lowered = value.strip().lower()
    return any(
        token in lowered
        for token in (
            "://127.",
            "://localhost",
            "://[::1]",
            "://0.0.0.0",
        )
    )


def codex_process_env() -> dict[str, str]:
    """Build env for Codex CLI.

    Prefer the interactive `alias codex='http_proxy=... codex'` proxies when present.
    IDE/agent shells often inject a localhost proxy that cannot reach api.openai.com.
    """
    env = os.environ.copy()
    alias_proxy = discover_proxy_from_codex_alias()
    if not alias_proxy:
        return env

    current = {
        key: env[key]
        for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy")
        if env.get(key)
    }
    should_override = (not current) or any(_proxy_looks_local(value) for value in current.values())
    if should_override:
        env.update(alias_proxy)
        # Keep common casings aligned so libraries that read either form work.
        if "http_proxy" in alias_proxy and "HTTP_PROXY" not in alias_proxy:
            env["HTTP_PROXY"] = alias_proxy["http_proxy"]
        if "https_proxy" in alias_proxy and "HTTPS_PROXY" not in alias_proxy:
            env["HTTPS_PROXY"] = alias_proxy["https_proxy"]
    return env


def resolve_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".codex"


UNSUPPORTED_SCHEMA_KEYS = {
    "default",
    "examples",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minimum",
    "maximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minContains",
    "maxContains",
    "minProperties",
    "maxProperties",
    "patternProperties",
    "unevaluatedProperties",
    "unevaluatedItems",
    "propertyNames",
    "contains",
}


JSON_VALUE_SCHEMA: dict[str, Any] = {
    "anyOf": [
        {"type": "string"},
        {"type": "number"},
        {"type": "boolean"},
        {"type": "null"},
        {"type": "array", "items": {"type": "string"}},
        {
            "type": "object",
            "properties": {
                "value": {"type": "string"},
                "source_fact_ids": {"type": "array", "items": {"type": "string"}},
                "origin": {"type": "string"},
                "confidence": {"type": "number"},
            },
            "required": ["value", "source_fact_ids", "origin", "confidence"],
            "additionalProperties": False,
        },
        {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "value": {"type": "string"},
                    "source_fact_ids": {"type": "array", "items": {"type": "string"}},
                    "origin": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["value", "source_fact_ids", "origin", "confidence"],
                "additionalProperties": False,
            },
        },
    ]
}


def schema_for_codex(schema: type[BaseModel]) -> dict[str, Any]:
    """Rewrite Pydantic JSON Schema into OpenAI/Codex strict structured-output form."""

    def strip_unsupported(node: dict[str, Any]) -> None:
        for key in list(node):
            if key in UNSUPPORTED_SCHEMA_KEYS:
                node.pop(key, None)

    def ensure_typed(node: dict[str, Any]) -> None:
        if any(key in node for key in ("$ref", "anyOf", "oneOf", "allOf", "enum", "const", "type")):
            return
        # Pydantic `Any` / unconstrained fields become bare objects — replace with expressible unions.
        replacement = json.loads(json.dumps(JSON_VALUE_SCHEMA))
        node.clear()
        node.update(replacement)

    def enforce(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                enforce(item)
            return
        if not isinstance(node, dict):
            return

        strip_unsupported(node)

        # Free-form maps (additionalProperties as a schema) are not expressible in strict mode.
        additional = node.get("additionalProperties")
        if isinstance(additional, dict) and node.get("type") == "object" and not node.get("properties"):
            value_schema = additional
            enforce(value_schema)
            node.clear()
            node.update(
                {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": value_schema,
                        },
                        "required": ["key", "value"],
                        "additionalProperties": False,
                    },
                }
            )
            return

        ensure_typed(node)

        if node.get("type") == "object" or "properties" in node:
            properties = node.setdefault("properties", {})
            if not isinstance(properties, dict):
                properties = {}
                node["properties"] = properties
            node["type"] = "object"
            node["additionalProperties"] = False
            node["required"] = list(properties.keys())
            for value in properties.values():
                enforce(value)

        if "items" in node:
            enforce(node["items"])

        for key in ("anyOf", "oneOf", "allOf"):
            if key in node and isinstance(node[key], list):
                for option in node[key]:
                    enforce(option)

        if "$defs" in node and isinstance(node["$defs"], dict):
            for value in node["$defs"].values():
                enforce(value)
        if "definitions" in node and isinstance(node["definitions"], dict):
            for value in node["definitions"].values():
                enforce(value)

    payload = schema.model_json_schema()
    enforce(payload)
    return payload


def summarize_codex_failure(stderr: str, stdout: str = "") -> str:
    combined = "\n".join(part for part in (stderr, stdout) if part).strip()
    if not combined:
        return "Codex 未能完成本次任务"

    lowered = combined.lower()
    # Local auth.json can still exist while ChatGPT OAuth tokens are revoked.
    if any(
        marker in lowered
        for marker in (
            "token_revoked",
            "refresh_token_invalidated",
            "invalidated oauth token",
            "session has ended",
            "your session has ended",
        )
    ):
        return (
            "Codex 本地显示已登录，但 ChatGPT 会话令牌已失效。"
            "请在本机重新执行 `codex login`（必要时先 `codex logout`）后再试。"
        )
    if "login" in lowered or "authentication" in lowered or "unauthorized" in lowered:
        return "Codex 尚未登录或会话已失效，请在本机执行 `codex login`"
    if "unexpected argument" in lowered or "unrecognized" in lowered:
        first_line = next((line.strip() for line in combined.splitlines() if line.strip()), "")
        return f"Codex CLI 参数不兼容：{first_line}"
    if "invalid_json_schema" in lowered or "additionalproperties" in lowered:
        return "Codex 拒绝了输出 JSON Schema，请升级应用后重试"
    if "permission denied" in lowered and (".codex" in lowered or "app-server" in lowered or "path aliases" in lowered):
        return (
            "Codex 无法写入 ~/.codex/tmp（权限不足）。"
            "请在终端执行：rm -rf ~/.codex/tmp/arg0 && mkdir -p ~/.codex/tmp/arg0 && chmod -R u+rwx ~/.codex/tmp"
        )
    if "proxy connection failed" in lowered or "http connect failed" in lowered or "status 403" in lowered:
        return (
            "无法经当前代理连接 OpenAI（Proxy CONNECT 失败）。"
            "请确认 alias codex 使用的 http_proxy 可用，并用该代理重启后端"
        )
    if "proxy" in lowered or "connect" in lowered or "timed out" in lowered or "websocket" in lowered:
        return "无法连接 Codex / OpenAI 服务，请检查网络或代理设置"

    noise_prefixes = (
        "warning:",
        "--------",
        "workdir:",
        "model:",
        "provider:",
        "approval:",
        "sandbox:",
        "reasoning",
        "session id:",
        "user",
        "openai codex v",
        "codex-cli",
    )

    def useful(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        low = stripped.lower()
        if any(low.startswith(prefix) for prefix in noise_prefixes):
            return False
        if low.startswith("error:") or low.startswith("error ") or " failed" in low or low.startswith("failed"):
            return True
        if "permission denied" in low or "proxy" in low or "timeout" in low:
            return True
        return len(stripped) > 12 and not stripped.startswith("202")

    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    preferred = [line for line in lines if useful(line)]
    # Prefer explicit ERROR lines when present.
    error_lines = [line for line in preferred if line.lower().startswith("error")]
    snippet = (error_lines[-1] if error_lines else (preferred[-1] if preferred else lines[-1]))[:240]
    return f"Codex 未能完成本次任务：{snippet}"


def load_codex_model_options(codex_home: Path | None = None) -> tuple[str, list[CodexModelOption]]:
    home = codex_home or resolve_codex_home()
    default_model = ""
    config_path = home / "config.toml"
    if config_path.exists():
        for line in config_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("model") and "=" in stripped and not stripped.startswith("["):
                _, raw = stripped.split("=", 1)
                default_model = raw.strip().strip("\"'")
                break

    models: list[CodexModelOption] = []
    cache_path = home / "models_cache.json"
    if cache_path.exists():
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
        for item in payload.get("models", []):
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug") or "").strip()
            if not slug:
                continue
            visibility = str(item.get("visibility") or "list").strip().lower()
            if visibility and visibility not in {"list", "visible", "available"}:
                continue
            models.append(
                CodexModelOption(
                    slug=slug,
                    display_name=str(item.get("display_name") or slug).strip() or slug,
                    description=str(item.get("description") or "").strip(),
                )
            )

    if default_model and all(option.slug != default_model for option in models):
        models.insert(0, CodexModelOption(slug=default_model, display_name=default_model))
    return default_model, models


async def detect_codex(
    *,
    runner: ProcessRunner | None = None,
    codex_home: Path | None = None,
    timeout: float = 20,
) -> CodexDetectResult:
    binary = shutil.which("codex")
    if not binary:
        return CodexDetectResult(
            installed=False,
            authenticated=False,
            available=False,
            message="未找到 Codex CLI。请先安装并确保 `codex` 在 PATH 中。",
        )

    process_runner = runner or AsyncProcessRunner()
    try:
        result = await process_runner.run(
            ["codex", "doctor", "--json", "--summary"],
            stdin="",
            cwd=Path.cwd(),
            timeout=timeout,
        )
    except TimeoutError:
        return CodexDetectResult(
            installed=True,
            authenticated=False,
            available=False,
            binary_path=binary,
            message="检测 Codex 超时，请稍后重试。",
        )
    except FileNotFoundError:
        return CodexDetectResult(
            installed=False,
            authenticated=False,
            available=False,
            message="未找到 Codex CLI。请先安装并确保 `codex` 在 PATH 中。",
        )

    doctor: dict[str, Any] = {}
    try:
        doctor = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        doctor = {}

    checks = doctor.get("checks") if isinstance(doctor.get("checks"), dict) else {}
    auth_check = checks.get("auth.credentials") if isinstance(checks.get("auth.credentials"), dict) else {}
    authenticated = str(auth_check.get("status") or "").lower() == "ok"
    if not authenticated:
        auth_file = (codex_home or resolve_codex_home()) / "auth.json"
        authenticated = auth_file.exists()

    version = str(doctor.get("codexVersion") or "").strip()
    default_model, models = load_codex_model_options(codex_home)
    config_model = ""
    config_check = checks.get("config.load") if isinstance(checks.get("config.load"), dict) else {}
    details = config_check.get("details") if isinstance(config_check.get("details"), dict) else {}
    config_model = str(details.get("model") or "").strip()
    if config_model:
        default_model = config_model
        if all(option.slug != config_model for option in models):
            models.insert(0, CodexModelOption(slug=config_model, display_name=config_model))

    if not authenticated:
        return CodexDetectResult(
            installed=True,
            authenticated=False,
            available=False,
            version=version,
            default_model=default_model,
            binary_path=binary,
            models=models,
            message="已找到 Codex CLI，但尚未登录。请先在本机执行 `codex login`。",
        )

    if not models:
        return CodexDetectResult(
            installed=True,
            authenticated=True,
            available=True,
            version=version,
            default_model=default_model,
            binary_path=binary,
            models=[],
            message="Codex 已就绪，但暂未读取到模型列表，可先使用 CLI 默认模型。",
        )

    return CodexDetectResult(
        installed=True,
        authenticated=True,
        available=True,
        version=version,
        default_model=default_model,
        binary_path=binary,
        models=models,
        message=f"已检测到 Codex {version or 'CLI'}，请选择模型后继续。",
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
        self.actual_call_count = 0

    async def complete_json(self, prompt: str, schema: type[T]) -> T:
        try:
            return await self._complete_json_once(prompt, schema, use_schema=True)
        except ProviderError as error:
            message = str(error)
            if "JSON Schema" not in message and "invalid_json_schema" not in message.lower():
                raise
            # Schema still rejected by an older/stricter Codex build: degrade to local validation.
            return await self._complete_json_once(prompt, schema, use_schema=False)

    async def _complete_json_once(self, prompt: str, schema: type[T], *, use_schema: bool) -> T:
        with TemporaryDirectory(dir=self.temp_parent, prefix="resume-codex-") as directory:
            root = Path(directory)
            schema_path = root / "output-schema.json"
            output_path = root / "last-message.json"
            schema_path.write_text(
                json.dumps(schema_for_codex(schema), ensure_ascii=False),
                encoding="utf-8",
            )
            command = [
                "codex",
                "exec",
                "-",
                "--ephemeral",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "-C",
                str(root),
                "--output-last-message",
                str(output_path),
                "--color",
                "never",
            ]
            if use_schema:
                command.extend(["--output-schema", str(schema_path)])
            if self.model:
                command.extend(["--model", self.model])
            try:
                self.actual_call_count += 1
                result = await self.runner.run(
                    command,
                    stdin=prompt if use_schema else f"{prompt}\n\n请只输出符合目标结构的 JSON，不要 Markdown。",
                    cwd=root,
                    timeout=self.timeout,
                )
            except TimeoutError as error:
                raise ProviderTimeoutError(
                    "Codex 请求超时。若本机 `codex` 依赖代理，请先 export http_proxy/https_proxy 后重启后端。"
                ) from error
            except FileNotFoundError as error:
                raise ProviderError("未找到 Codex CLI") from error

            if result.returncode != 0:
                detail = summarize_codex_failure(result.stderr, result.stdout)
                if "尚未登录" in detail:
                    raise ProviderAuthError(detail)
                raise ProviderError(detail)
            raw = output_path.read_text(encoding="utf-8") if output_path.exists() else result.stdout
            return validate_json_response(raw, schema)

    async def probe(self, *, timeout: float = 45) -> dict[str, str]:
        """Short connection check used by settings; avoids the default long workflow timeout."""
        previous = self.timeout
        self.timeout = timeout
        try:
            class _Probe(BaseModel):
                model_config = {"extra": "forbid"}
                status: str

            result = await self.complete_json('仅返回 {"status":"ok"}', _Probe)
            return {"status": result.status}
        finally:
            self.timeout = previous
