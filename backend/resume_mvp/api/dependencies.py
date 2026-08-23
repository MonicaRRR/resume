from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from fastapi import Request

from resume_mvp.providers import AIProvider, CodexProvider, OpenAICompatibleProvider
from resume_mvp.repositories import ProjectRepository


class ProviderConfigurationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProviderPublicState:
    kind: str
    base_url: str
    model: str
    timeout: float
    temperature: float
    configured: bool
    codex_confirmed: bool


class ProviderRegistry:
    def __init__(
        self,
        test_providers: Mapping[str, AIProvider] | None = None,
        *,
        default_test_kind: str = "",
    ) -> None:
        self._test_providers = dict(test_providers or {})
        self._kind = default_test_kind if default_test_kind in self._test_providers else ""
        self._base_url = ""
        self._api_key = ""
        self._model = ""
        self._timeout = 90.0
        self._temperature = 0.2
        self._codex_confirmed = False

    def public_state(self) -> ProviderPublicState:
        configured = self._kind in self._test_providers or (
            self._kind == "openai-compatible"
            and bool(self._base_url and self._api_key and self._model)
        ) or (self._kind == "codex" and self._codex_confirmed)
        return ProviderPublicState(
            kind=self._kind,
            base_url=self._base_url,
            model=self._model,
            timeout=self._timeout,
            temperature=self._temperature,
            configured=configured,
            codex_confirmed=self._codex_confirmed,
        )

    def configure_openai(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float,
        temperature: float,
    ) -> ProviderPublicState:
        if not base_url.strip() or not api_key or not model.strip():
            raise ProviderConfigurationError("PROVIDER_FIELDS_REQUIRED", "请填写 Base URL、API Key 和模型名称")
        self._kind = "openai-compatible"
        self._base_url = base_url.strip()
        self._api_key = api_key
        self._model = model.strip()
        self._timeout = timeout
        self._temperature = temperature
        return self.public_state()

    def configure_codex(self, *, confirmed: bool, model: str = "") -> ProviderPublicState:
        if not confirmed:
            raise ProviderConfigurationError(
                "CODEX_CONSENT_REQUIRED",
                "请先确认简历和 JD 的必要内容会发送给 Codex",
            )
        self._kind = "codex"
        self._codex_confirmed = True
        self._model = model.strip()
        return self.public_state()

    def resolve(self, kind: str) -> AIProvider:
        if kind in self._test_providers:
            return self._test_providers[kind]
        if kind == "openai-compatible":
            if not (self._base_url and self._api_key and self._model):
                raise ProviderConfigurationError("PROVIDER_NOT_CONFIGURED", "API 模型尚未配置")
            return OpenAICompatibleProvider(
                base_url=self._base_url,
                api_key=self._api_key,
                model=self._model,
                timeout=self._timeout,
                temperature=self._temperature,
            )
        if kind == "codex":
            if not self._codex_confirmed:
                raise ProviderConfigurationError("CODEX_CONSENT_REQUIRED", "尚未确认 Codex 隐私提示")
            return CodexProvider(timeout=self._timeout, model=self._model)
        raise ProviderConfigurationError("PROVIDER_NOT_CONFIGURED", "请选择并配置模型")


@dataclass(frozen=True)
class AppServices:
    repository: ProjectRepository
    providers: ProviderRegistry


def get_services(request: Request) -> AppServices:
    return request.app.state.services
