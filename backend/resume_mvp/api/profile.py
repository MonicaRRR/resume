from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from resume_mvp.api.dependencies import AppServices, get_services
from resume_mvp.domain import Fact, ResumeDocument
from resume_mvp.profile import profile_is_ready


router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfilePayload(BaseModel):
    resume: ResumeDocument
    facts: list[Fact] = Field(default_factory=list)
    ready: bool = False


class ProfileSaveInput(BaseModel):
    resume: ResumeDocument


@router.get("", response_model=ProfilePayload)
def get_profile(services: AppServices = Depends(get_services)) -> ProfilePayload:
    resume, facts = services.repository.get_profile()
    return ProfilePayload(resume=resume, facts=facts, ready=profile_is_ready(resume))


@router.put("", response_model=ProfilePayload)
def save_profile(body: ProfileSaveInput, services: AppServices = Depends(get_services)) -> ProfilePayload:
    resume, facts = services.repository.save_profile(body.resume)
    return ProfilePayload(resume=resume, facts=facts, ready=profile_is_ready(resume))
