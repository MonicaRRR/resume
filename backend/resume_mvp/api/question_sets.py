from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from resume_mvp.api.dependencies import AppServices, get_services
from resume_mvp.domain import QuestionSet, QuestionSetSource
from resume_mvp.question_sets import build_fallback_question_set
from resume_mvp.repositories import (
    ProjectNotFoundError,
    QuestionSetNotFoundError,
)

router = APIRouter(tags=["question-sets"])


class QuestionSetCreateInput(BaseModel):
    source_type: QuestionSetSource = "jd"
    title: str | None = Field(default=None, max_length=200)


@router.post("/api/projects/{project_id}/question-sets", response_model=QuestionSet, status_code=201)
def create_question_set(
    project_id: str,
    body: QuestionSetCreateInput,
    services: AppServices = Depends(get_services),
) -> QuestionSet:
    try:
        project = services.repository.get(project_id)
        version = services.repository.get_active_version(project_id)
    except ProjectNotFoundError as error:
        raise HTTPException(404, detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在"}) from error
    question_set = build_fallback_question_set(project, version, body.source_type)
    if body.title and body.title.strip():
        question_set = question_set.model_copy(update={"title": body.title.strip()})
    return services.repository.save_question_set(question_set)


@router.get("/api/projects/{project_id}/question-sets", response_model=list[QuestionSet])
def list_question_sets(project_id: str, services: AppServices = Depends(get_services)) -> list[QuestionSet]:
    try:
        return services.repository.list_question_sets(project_id)
    except ProjectNotFoundError as error:
        raise HTTPException(404, detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在"}) from error


@router.get("/api/question-sets/{question_set_id}", response_model=QuestionSet)
def get_question_set(question_set_id: str, services: AppServices = Depends(get_services)) -> QuestionSet:
    try:
        return services.repository.get_question_set(question_set_id)
    except QuestionSetNotFoundError as error:
        raise HTTPException(404, detail={"code": "QUESTION_SET_NOT_FOUND", "message": "题集不存在"}) from error


@router.post("/api/question-sets/{question_set_id}/reuse", response_model=QuestionSet)
def reuse_question_set(question_set_id: str, services: AppServices = Depends(get_services)) -> QuestionSet:
    try:
        return services.repository.reuse_question_set(question_set_id)
    except QuestionSetNotFoundError as error:
        raise HTTPException(404, detail={"code": "QUESTION_SET_NOT_FOUND", "message": "题集不存在"}) from error
