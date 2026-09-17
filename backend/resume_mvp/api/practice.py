from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from resume_mvp.api.dependencies import (
    AppServices,
    ProviderConfigurationError,
    get_services,
)
from resume_mvp.domain import (
    PracticeQuestion,
    PracticeSession,
    QuestionSet,
    QuestionSetSource,
)
from resume_mvp.practice import answer_practice, start_practice, start_practice_from_set
from resume_mvp.providers.base import ProviderError
from resume_mvp.repositories import (
    PracticeSessionNotFoundError,
    ProjectNotFoundError,
    QuestionSetNotFoundError,
)


router = APIRouter(tags=["practice"])


class PracticeStartInput(BaseModel):
    kind: Literal["interview", "written"]
    provider: str = ""
    question_set_id: str | None = None


class PracticeAnswerInput(BaseModel):
    answer: str = Field(min_length=1)
    provider: str


class QuestionSetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    kind: Literal["interview", "written"] = "interview"
    source: QuestionSetSource = "fixed"
    questions: list[PracticeQuestion] = Field(default_factory=list)
    rules: dict = Field(default_factory=dict)
    question_count: int = Field(default=5, ge=1, le=50)


class QuestionSetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    kind: Literal["interview", "written"] | None = None
    source: QuestionSetSource | None = None
    questions: list[PracticeQuestion] | None = None
    rules: dict | None = None
    question_count: int | None = Field(default=None, ge=1, le=50)


class PracticeSetStartInput(BaseModel):
    question_set_id: str
    provider: str = ""


class PracticeProviderInput(BaseModel):
    provider: str = ""


@router.post("/api/question-sets", response_model=QuestionSet, status_code=201)
def create_question_set(
    body: QuestionSetCreate,
    services: AppServices = Depends(get_services),
) -> QuestionSet:
    return services.repository.create_question_set(QuestionSet(**body.model_dump()))


@router.get("/api/question-sets", response_model=list[QuestionSet])
def list_question_sets(
    services: AppServices = Depends(get_services),
) -> list[QuestionSet]:
    return services.repository.list_question_sets()


@router.get("/api/question-sets/{question_set_id}", response_model=QuestionSet)
def get_question_set(
    question_set_id: str,
    services: AppServices = Depends(get_services),
) -> QuestionSet:
    try:
        return services.repository.get_question_set(question_set_id)
    except QuestionSetNotFoundError as error:
        raise HTTPException(
            404, detail={"code": "QUESTION_SET_NOT_FOUND", "message": "题集不存在"}
        ) from error


@router.put("/api/question-sets/{question_set_id}", response_model=QuestionSet)
@router.patch("/api/question-sets/{question_set_id}", response_model=QuestionSet)
def update_question_set(
    question_set_id: str,
    body: QuestionSetUpdate,
    services: AppServices = Depends(get_services),
) -> QuestionSet:
    try:
        return services.repository.update_question_set(
            question_set_id, **body.model_dump(exclude_unset=True)
        )
    except QuestionSetNotFoundError as error:
        raise HTTPException(
            404, detail={"code": "QUESTION_SET_NOT_FOUND", "message": "题集不存在"}
        ) from error


@router.delete("/api/question-sets/{question_set_id}", status_code=204)
def delete_question_set(
    question_set_id: str,
    services: AppServices = Depends(get_services),
) -> None:
    try:
        services.repository.delete_question_set(question_set_id)
    except QuestionSetNotFoundError as error:
        raise HTTPException(
            404, detail={"code": "QUESTION_SET_NOT_FOUND", "message": "题集不存在"}
        ) from error


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
    if body.question_set_id:
        return await _start_from_set(project_id, body.question_set_id, body.provider, services)
    if project.job_analysis is None:
        raise HTTPException(409, detail={"code": "ANALYSIS_REQUIRED", "message": "请先分析职位描述"})
    provider = _provider(services, body.provider)
    try:
        practice = await start_practice(body.kind, provider, project, version.resume)
    except ProviderError as error:
        raise HTTPException(502, detail={"code": "PROVIDER_FAILED", "message": str(error)}) from error
    return services.repository.save_practice(practice)


@router.post(
    "/api/projects/{project_id}/practice/sessions/from-set",
    response_model=PracticeSession,
    status_code=201,
)
async def create_practice_session_from_set(
    project_id: str,
    body: PracticeSetStartInput,
    services: AppServices = Depends(get_services),
) -> PracticeSession:
    return await _start_from_set(project_id, body.question_set_id, body.provider, services)


@router.post(
    "/api/projects/{project_id}/question-sets/{question_set_id}/sessions",
    response_model=PracticeSession,
    status_code=201,
    include_in_schema=False,
)
async def create_practice_session_from_set_path(
    project_id: str,
    question_set_id: str,
    body: PracticeProviderInput | None = None,
    services: AppServices = Depends(get_services),
) -> PracticeSession:
    return await _start_from_set(
        project_id, question_set_id, body.provider if body else "", services
    )


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


async def _start_from_set(
    project_id: str,
    question_set_id: str,
    provider_kind: str,
    services: AppServices,
) -> PracticeSession:
    try:
        project = services.repository.get(project_id)
        question_set = services.repository.get_question_set(question_set_id)
    except ProjectNotFoundError as error:
        raise HTTPException(
            404, detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在"}
        ) from error
    except QuestionSetNotFoundError as error:
        raise HTTPException(
            404, detail={"code": "QUESTION_SET_NOT_FOUND", "message": "题集不存在"}
        ) from error
    version = services.repository.get_active_version(project_id)
    if version is None:
        raise HTTPException(
            409, detail={"code": "RESUME_REQUIRED", "message": "请先上传或创建简历"}
        )
    provider = (
        _provider(services, provider_kind)
        if question_set.source in ("ai", "mixed")
        else None
    )
    try:
        practice = await start_practice_from_set(
            question_set, project, version.resume, provider
        )
    except ProviderError as error:
        raise HTTPException(
            502, detail={"code": "PROVIDER_FAILED", "message": str(error)}
        ) from error
    except ValueError as error:
        raise HTTPException(
            422, detail={"code": "QUESTION_SET_INVALID", "message": str(error)}
        ) from error
    return services.repository.save_practice(practice)
