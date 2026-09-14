from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Mapping

from fastapi import Request

from resume_mvp.provider_store import load_provider_settings, save_provider_settings
from resume_mvp.providers import AIProvider, CodexProvider, OpenAICompatibleProvider
from resume_mvp.repositories import ProjectRepository
from resume_mvp.secret_store import SecretStore, provider_key_account

if TYPE_CHECKING:
    from resume_mvp.optimization_orchestrator import OptimizationOrchestrator


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
    key_storage: str
    key_saved: bool
    storage_warning: str


class ProviderRegistry:
    def __init__(
        self,
        test_providers: Mapping[str, AIProvider] | None = None,
        *,
        default_test_kind: str = "",
        persist_path: Path | None = None,
        secret_store: SecretStore | None = None,
    ) -> None:
        self._test_providers = dict(test_providers or {})
        self._persist_path = persist_path
        self._secret_store = secret_store
        self._kind = default_test_kind if default_test_kind in self._test_providers else ""
        self._preferred_kind = self._kind
        self._base_url = ""
        self._api_key = ""
        self._model = ""
        self._timeout = 90.0
        self._temperature = 0.2
        self._codex_confirmed = False
        self._key_storage = "none"
        self._key_account = ""
        self._storage_warning = ""
        self._restore()

    def _restore(self) -> None:
        if self._persist_path is None or self._kind in self._test_providers:
            return
        saved = load_provider_settings(self._persist_path)
        if not saved:
            return
        kind = str(saved.get("kind") or "")
        self._base_url = str(saved.get("base_url") or "")
        self._model = str(saved.get("model") or "")
        self._timeout = float(saved.get("timeout") or 90)
        self._temperature = float(saved.get("temperature") or 0.2)
        self._codex_confirmed = bool(saved.get("codex_confirmed"))
        self._preferred_kind = kind
        if kind == "codex" and self._codex_confirmed:
            # Codex has no secret key — restore as fully configured.
            self._kind = "codex"
        elif kind == "openai-compatible" and self._base_url and self._model:
            try:
                account = provider_key_account(self._base_url)
                api_key = self._secret_store.get(account) if self._secret_store else None
            except Exception:
                api_key = None
                self._storage_warning = "无法从 macOS 钥匙串恢复密钥，请解锁钥匙串后重试。"
            if api_key:
                self._api_key = api_key
                self._key_account = account
                self._key_storage = "keychain"
                self._kind = "openai-compatible"
        else:
            self._kind = ""

    def _persist(self) -> None:
        if self._persist_path is None or self._kind in self._test_providers:
            return
        save_provider_settings(
            self._persist_path,
            {
                "kind": self._kind or self._preferred_kind,
                "base_url": self._base_url,
                "model": self._model,
                "timeout": self._timeout,
                "temperature": self._temperature,
                "codex_confirmed": self._codex_confirmed,
            },
        )

    def public_state(self) -> ProviderPublicState:
        configured = self._kind in self._test_providers or (
            self._kind == "openai-compatible"
            and bool(self._base_url and self._api_key and self._model)
        ) or (self._kind == "codex" and self._codex_confirmed)
        return ProviderPublicState(
            kind=self._kind or self._preferred_kind or "",
            base_url=self._base_url,
            model=self._model,
            timeout=self._timeout,
            temperature=self._temperature,
            configured=configured,
            codex_confirmed=self._codex_confirmed,
            key_storage=self._key_storage,
            key_saved=self._key_storage == "keychain",
            storage_warning=self._storage_warning,
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
        if not base_url.strip() or not model.strip():
            raise ProviderConfigurationError("PROVIDER_FIELDS_REQUIRED", "请填写 Base URL 和模型名称")
        normalized_url = base_url.strip().rstrip("/")
        normalized_model = model.strip().lower()
        if (
            normalized_url == "https://open.bigmodel.cn/api/coding/paas/v4"
            and normalized_model.endswith("-flash")
        ):
            raise ProviderConfigurationError(
                "ZHIPU_ENDPOINT_MODEL_MISMATCH",
                "glm-4.7-flash 需要使用智谱标准 API 地址 "
                "https://open.bigmodel.cn/api/paas/v4；Coding Plan 地址请改用套餐支持的模型。",
            )
        try:
            account = provider_key_account(normalized_url)
        except ValueError as error:
            raise ProviderConfigurationError(
                "PROVIDER_BASE_URL_INVALID",
                "Base URL 必须是 http 或 https 地址，不能包含登录信息、查询参数或片段",
            ) from error
        resolved_key = api_key
        key_storage = "none"
        if resolved_key:
            if self._secret_store is not None:
                try:
                    self._secret_store.set(account, resolved_key)
                    key_storage = "keychain"
                except Exception:
                    key_storage = "memory"
            else:
                key_storage = "memory"
        elif self._key_account == account and self._api_key:
            resolved_key = self._api_key
            key_storage = self._key_storage
        elif self._secret_store is not None:
            try:
                resolved_key = self._secret_store.get(account) or ""
            except Exception:
                resolved_key = ""
            if resolved_key:
                key_storage = "keychain"
        if not resolved_key:
            raise ProviderConfigurationError(
                "PROVIDER_API_KEY_REQUIRED",
                "这个 API 地址尚未保存密钥，请填写 API Key",
            )
        self._kind = "openai-compatible"
        self._preferred_kind = "openai-compatible"
        self._base_url = normalized_url
        self._api_key = resolved_key
        self._key_account = account
        self._key_storage = key_storage
        self._storage_warning = (
            "无法写入 macOS 钥匙串；本次密钥仅保存在内存，重启后需重新输入。若此前保存过密钥，旧值可能仍在钥匙串中。"
            if key_storage == "memory" else ""
        )
        self._model = model.strip()
        self._timeout = timeout
        self._temperature = temperature
        self._codex_confirmed = False
        self._persist()
        return self.public_state()

    def delete_openai_key(self) -> ProviderPublicState:
        try:
            account = self._key_account or (provider_key_account(self._base_url) if self._base_url else "")
        except ValueError:
            account = ""
        if account and self._secret_store is None:
            raise ProviderConfigurationError(
                "KEYCHAIN_UNAVAILABLE",
                "macOS 钥匙串当前不可用，无法确认已保存密钥是否删除，请稍后重试",
            )
        if account and self._secret_store is not None:
            try:
                self._secret_store.delete(account)
            except Exception as error:
                raise ProviderConfigurationError(
                    "KEYCHAIN_UNAVAILABLE",
                    "无法从 macOS 钥匙串删除密钥，请稍后重试",
                ) from error
        self._api_key = ""
        self._key_account = ""
        self._key_storage = "none"
        self._storage_warning = ""
        if self._kind == "openai-compatible":
            self._kind = ""
        self._persist()
        return self.public_state()

    def configure_codex(self, *, confirmed: bool, model: str = "") -> ProviderPublicState:
        if not confirmed:
            raise ProviderConfigurationError(
                "CODEX_CONSENT_REQUIRED",
                "请先确认简历和 JD 的必要内容会发送给 Codex",
            )
        self._kind = "codex"
        self._preferred_kind = "codex"
        self._codex_confirmed = True
        self._model = model.strip()
        self._api_key = ""
        self._key_account = ""
        self._key_storage = "none"
        self._storage_warning = ""
        self._persist()
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
            if not (self._kind == "codex" and self._codex_confirmed):
                raise ProviderConfigurationError("CODEX_CONSENT_REQUIRED", "尚未确认 Codex 隐私提示")
            return CodexProvider(timeout=self._timeout, model=self._model)
        raise ProviderConfigurationError("PROVIDER_NOT_CONFIGURED", "请选择并配置模型")


@dataclass(frozen=True)
class AppServices:
    repository: ProjectRepository
    providers: ProviderRegistry
    optimization: OptimizationOrchestrator


def get_services(request: Request) -> AppServices:
    return request.app.state.services
