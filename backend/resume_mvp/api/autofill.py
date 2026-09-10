from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from resume_mvp.api.dependencies import (
    AppServices,
    ProviderConfigurationError,
    get_services,
)
from resume_mvp.autofill import (
    AutofillPlan,
    PageField,
    build_autofill_plan,
    flatten_profile,
)


router = APIRouter(prefix="/api/autofill", tags=["autofill"])


class AutofillPlanRequest(BaseModel):
    fields: list[PageField] = Field(default_factory=list)
    page_url: str = ""
    page_title: str = ""
    provider: str | None = None


@router.post("/plan", response_model=AutofillPlan)
async def create_autofill_plan(
    body: AutofillPlanRequest,
    services: AppServices = Depends(get_services),
) -> AutofillPlan:
    resume, _facts = services.repository.get_profile()
    profile = flatten_profile(resume)
    provider = None
    provider_kind = body.provider
    if not provider_kind:
        state = services.providers.public_state()
        if state.configured and state.kind:
            provider_kind = state.kind
    if provider_kind:
        try:
            provider = services.providers.resolve(provider_kind)
        except ProviderConfigurationError as error:
            # Rules still run; surface config issue as warning via hybrid path skip.
            plan = await build_autofill_plan(
                body.fields,
                profile,
                provider=None,
                page_url=body.page_url,
                page_title=body.page_title,
            )
            plan.warnings.append(str(error))
            return plan
    return await build_autofill_plan(
        body.fields,
        profile,
        provider=provider,
        page_url=body.page_url,
        page_title=body.page_title,
    )


@router.get("/profile-flat")
def get_flat_profile(services: AppServices = Depends(get_services)) -> dict[str, str]:
    """Debug helper: flattened profile keys used by autofill."""
    resume, _facts = services.repository.get_profile()
    return flatten_profile(resume)
