from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from resume_mvp.api.dependencies import (
    AppServices,
    ProviderConfigurationError,
    get_services,
)
from resume_mvp.domain import PracticeSession
from resume_mvp.practice import answer_practice, start_practice
from resume_mvp.providers.base import ProviderError
from resume_mvp.repositories import PracticeSessionNotFoundError, ProjectNotFoundError


router = APIRouter(tags=["practice"])


class PracticeStartInput(BaseModel):
    kind: Literal["interview", "written"]
    provider: str


class PracticeAnswerInput(BaseModel):
    answer: str = Field(min_length=1)
    provider: str


@router.post(
    "/api/projects/{project_id}/practice/sessions",
    response_model=PracticeSession,
    status_code=201,
)
async def create_practice_session(
    project_id: str,
    body: PracticeStartInput,
    services: AppServices = Depends(get_services),
) -> PracticeSession:
    try:
        project = services.repository.get(project_id)
    except ProjectNotFoundError as error:
        raise HTTPException(404, detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在"}) from error
    version = services.repository.get_active_version(project_id)
    if version is None:
        raise HTTPException(409, detail={"code": "RESUME_REQUIRED", "message": "请先上传或创建简历"})
    if project.job_analysis is None:
        raise HTTPException(409, detail={"code": "ANALYSIS_REQUIRED", "message": "请先分析职位描述"})
    provider = _provider(services, body.provider)
    try:
        practice = await start_practice(body.kind, provider, project, version.resume)
    except ProviderError as error:
        raise HTTPException(502, detail={"code": "PROVIDER_FAILED", "message": str(error)}) from error
    return services.repository.save_practice(practice)


@router.get("/api/practice/sessions/{session_id}", response_model=PracticeSession)
def get_practice_session(
    session_id: str,
    services: AppServices = Depends(get_services),
) -> PracticeSession:
    try:
        return services.repository.get_practice(session_id)
    except PracticeSessionNotFoundError as error:
        raise HTTPException(404, detail={"code": "PRACTICE_NOT_FOUND", "message": "训练记录不存在"}) from error


@router.post("/api/practice/sessions/{session_id}/answer", response_model=PracticeSession)
async def answer_practice_session(
    session_id: str,
    body: PracticeAnswerInput,
    services: AppServices = Depends(get_services),
) -> PracticeSession:
    try:
        session = services.repository.get_practice(session_id)
    except PracticeSessionNotFoundError as error:
        raise HTTPException(404, detail={"code": "PRACTICE_NOT_FOUND", "message": "训练记录不存在"}) from error
    provider = _provider(services, body.provider)
    try:
        await answer_practice(session, body.answer, provider)
    except ProviderError as error:
        raise HTTPException(502, detail={"code": "PROVIDER_FAILED", "message": str(error)}) from error
    return services.repository.save_practice(session)


def _provider(services: AppServices, kind: str):
    try:
        return services.providers.resolve(kind)
    except ProviderConfigurationError as error:
        raise HTTPException(422, detail={"code": error.code, "message": str(error)}) from error
