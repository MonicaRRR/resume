from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from resume_mvp.api.dependencies import (
    AppServices,
    ProviderConfigurationError,
    ProviderPublicState,
    get_services,
)
from resume_mvp.providers.base import ProviderError


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


class ProviderSelection(BaseModel):
    provider: str


class ProviderProbe(BaseModel):
    status: str


@router.get("", response_model=ProviderSettingsOutput)
def get_provider_settings(services: AppServices = Depends(get_services)) -> ProviderPublicState:
    return services.providers.public_state()


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


@router.post("/test", response_model=ProviderProbe)
async def test_provider(
    body: ProviderSelection,
    services: AppServices = Depends(get_services),
) -> ProviderProbe:
    try:
        provider = services.providers.resolve(body.provider)
        return await provider.complete_json(
            "仅返回 {\"status\":\"ok\"}",
            ProviderProbe,
        )
    except ProviderConfigurationError as error:
        raise HTTPException(422, detail={"code": error.code, "message": str(error)}) from error
    except ProviderError as error:
        raise HTTPException(502, detail={"code": "PROVIDER_UNAVAILABLE", "message": str(error)}) from error
