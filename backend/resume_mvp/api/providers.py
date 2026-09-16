from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from resume_mvp.api.dependencies import (
    AppServices,
    ProviderConfigurationError,
    ProviderPublicState,
    get_services,
)
from resume_mvp.providers.base import ProviderError, ProviderRateLimitError, ProviderTimeoutError


router = APIRouter(prefix="/api/settings/providers", tags=["providers"])


class ProviderSettingsInput(BaseModel):
    kind: str
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout: float = Field(default=90, ge=5, le=600)
    temperature: float = Field(default=0.2, ge=0, le=2)
    codex_confirmed: bool = False


class ProviderSettingsOutput(BaseModel):
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
    capabilities: list[str] = Field(default_factory=list)


class ProviderSelection(BaseModel):
    provider: str


class ProviderProbe(BaseModel):
    status: str


class CodexModelOptionOutput(BaseModel):
    slug: str
    display_name: str
    description: str = ""


class CodexDetectOutput(BaseModel):
    installed: bool
    authenticated: bool
    available: bool
    version: str = ""
    default_model: str = ""
    binary_path: str = ""
    models: list[CodexModelOptionOutput] = Field(default_factory=list)
    message: str = ""


@router.get("", response_model=ProviderSettingsOutput)
def get_provider_settings(services: AppServices = Depends(get_services)) -> ProviderPublicState:
    return services.providers.public_state()


@router.post("/codex/detect", response_model=CodexDetectOutput)
async def detect_codex_cli() -> CodexDetectOutput:
    from resume_mvp.providers.codex import detect_codex

    result = await detect_codex()
    return CodexDetectOutput(
        installed=result.installed,
        authenticated=result.authenticated,
        available=result.available,
        version=result.version,
        default_model=result.default_model,
        binary_path=result.binary_path,
        models=[
            CodexModelOptionOutput(
                slug=item.slug,
                display_name=item.display_name,
                description=item.description,
            )
            for item in result.models
        ],
        message=result.message,
    )


@router.patch("", response_model=ProviderSettingsOutput)
def update_provider_settings(
    body: ProviderSettingsInput,
    services: AppServices = Depends(get_services),
) -> ProviderPublicState:
    try:
        if body.kind == "openai-compatible":
            return services.providers.configure_openai(
                base_url=body.base_url,
                api_key=body.api_key,
                model=body.model,
                timeout=body.timeout,
                temperature=body.temperature,
            )
        if body.kind == "codex":
            return services.providers.configure_codex(
                confirmed=body.codex_confirmed,
                model=body.model,
            )
        raise ProviderConfigurationError("PROVIDER_KIND_INVALID", "不支持该模型类型")
    except ProviderConfigurationError as error:
        raise HTTPException(422, detail={"code": error.code, "message": str(error)}) from error


@router.delete("/key", response_model=ProviderSettingsOutput)
def delete_provider_key(services: AppServices = Depends(get_services)) -> ProviderPublicState:
    try:
        return services.providers.delete_openai_key()
    except ProviderConfigurationError as error:
        status = 503 if error.code == "KEYCHAIN_UNAVAILABLE" else 422
        raise HTTPException(status, detail={"code": error.code, "message": str(error)}) from error


@router.post("/test", response_model=ProviderProbe)
async def test_provider(
    body: ProviderSelection,
    services: AppServices = Depends(get_services),
) -> ProviderProbe:
    try:
        if body.provider == "codex":
            from resume_mvp.providers.codex import CodexProvider, detect_codex

            detection = await detect_codex(timeout=20)
            if not detection.available:
                raise ProviderError(detection.message or "Codex CLI 不可用")
            provider = services.providers.resolve("codex")
            if isinstance(provider, CodexProvider):
                payload = await provider.probe(timeout=45)
                return ProviderProbe(status=payload.get("status", "ok"))
            return await provider.complete_json('仅返回 {"status":"ok"}', ProviderProbe)

        provider = services.providers.resolve(body.provider)
        return await provider.complete_json(
            '仅返回 {"status":"ok"}',
            ProviderProbe,
        )
    except ProviderConfigurationError as error:
        raise HTTPException(422, detail={"code": error.code, "message": str(error)}) from error
    except ProviderTimeoutError as error:
        raise HTTPException(504, detail={"code": "PROVIDER_TIMEOUT", "message": str(error)}) from error
    except ProviderRateLimitError as error:
        raise HTTPException(
            429,
            detail={
                "code": "PROVIDER_RATE_LIMITED",
                "message": str(error),
                "retry_after_seconds": error.retry_after_seconds,
            },
        ) from error
    except ProviderError as error:
        raise HTTPException(502, detail={"code": "PROVIDER_UNAVAILABLE", "message": str(error)}) from error
