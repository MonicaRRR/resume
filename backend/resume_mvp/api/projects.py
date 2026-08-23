from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator

from resume_mvp.ai_workflows import (
    JobEvidenceError,
    UnsupportedFactError,
    analyze_job,
    generate_followup_questions,
    suggest_resume_patch,
)
from resume_mvp.api.dependencies import (
    AppServices,
    ProviderConfigurationError,
    get_services,
)
from resume_mvp.domain import (
    ApplicationType,
    Fact,
    JobProject,
    MatchReport,
    ResumeDocument,
    ResumePatch,
    ResumeVersion,
)
from resume_mvp.ingestion import ImportResult, ResumeImportError, import_resume
from resume_mvp.matching import calculate_match
from resume_mvp.patches import PatchConflictError, apply_resume_patch
from resume_mvp.providers.base import ProviderError
from resume_mvp.repositories import ProjectNotFoundError, VersionNotFoundError


router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    company_name: str = Field(default="", max_length=200)
    application_type: ApplicationType
    job_description: str = Field(min_length=1)

    @field_validator("title", "job_description")
    @classmethod
    def reject_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("不能为空")
        return value.strip()


class ProjectUpdate(BaseModel):
    title: str | None = None
    company_name: str | None = None
    application_type: ApplicationType | None = None
    job_description: str | None = None
    selected_template_id: str | None = None


class ProviderSelection(BaseModel):
    provider: str


class ImportResponse(ImportResult):
    version_id: str


class ResumeSaveInput(BaseModel):
    resume: ResumeDocument
    facts: list[Fact] = Field(default_factory=list)
    reason: str = "手动保存"


class FactCreate(BaseModel):
    category: str
    statement: str = Field(min_length=1)
    source_type: Literal["questionnaire", "manual"] = "manual"
    source_location: str = ""
    user_confirmed: bool = True


class PatchApplyInput(BaseModel):
    patch: ResumePatch
    accepted_operation_ids: list[str]


@router.get("", response_model=list[JobProject])
def list_projects(services: AppServices = Depends(get_services)) -> list[JobProject]:
    return services.repository.list()


@router.post("", response_model=JobProject, status_code=201)
def create_project(body: ProjectCreate, services: AppServices = Depends(get_services)) -> JobProject:
    return services.repository.create(
        title=body.title,
        company_name=body.company_name,
        application_type=body.application_type,
        job_description=body.job_description,
    )


@router.get("/{project_id}", response_model=JobProject)
def get_project(project_id: str, services: AppServices = Depends(get_services)) -> JobProject:
    return _project_or_404(services, project_id)


@router.patch("/{project_id}", response_model=JobProject)
def update_project(
    project_id: str,
    body: ProjectUpdate,
    services: AppServices = Depends(get_services),
) -> JobProject:
    _project_or_404(services, project_id)
    return services.repository.update(project_id, **body.model_dump(exclude_unset=True))


@router.post("/{project_id}/resume/import", response_model=ImportResponse)
async def upload_resume(
    project_id: str,
    file: UploadFile = File(...),
    services: AppServices = Depends(get_services),
) -> ImportResponse:
    _project_or_404(services, project_id)
    try:
        result = import_resume(
            file.filename or "resume.txt",
            file.content_type or "application/octet-stream",
            await file.read(),
        )
    except ResumeImportError as error:
        raise HTTPException(422, detail={"code": "IMPORT_FAILED", "message": str(error)}) from error
    version = services.repository.save_version(
        project_id,
        result.resume,
        reason="初始导入",
        facts=result.facts,
    )
    return ImportResponse(**result.model_dump(), version_id=version.id)


@router.put("/{project_id}/resume", response_model=ResumeVersion)
def save_resume(
    project_id: str,
    body: ResumeSaveInput,
    services: AppServices = Depends(get_services),
) -> ResumeVersion:
    _project_or_404(services, project_id)
    return services.repository.save_version(
        project_id,
        body.resume,
        reason=body.reason,
        facts=body.facts,
    )


@router.get("/{project_id}/versions", response_model=list[ResumeVersion])
def list_versions(project_id: str, services: AppServices = Depends(get_services)) -> list[ResumeVersion]:
    try:
        return services.repository.list_versions(project_id)
    except ProjectNotFoundError as error:
        raise HTTPException(404, detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在"}) from error


@router.post("/{project_id}/versions/{version_id}/activate", response_model=JobProject)
def activate_version(
    project_id: str,
    version_id: str,
    services: AppServices = Depends(get_services),
) -> JobProject:
    try:
        return services.repository.activate_version(project_id, version_id)
    except (ProjectNotFoundError, VersionNotFoundError) as error:
        raise HTTPException(404, detail={"code": "VERSION_NOT_FOUND", "message": "简历版本不存在"}) from error


@router.post("/{project_id}/analyze-jd")
async def analyze_project_job(
    project_id: str,
    body: ProviderSelection,
    services: AppServices = Depends(get_services),
):
    project = _project_or_404(services, project_id)
    provider = _provider_or_422(services, body.provider)
    try:
        analysis = await analyze_job(provider, project.company_name, project.job_description)
    except JobEvidenceError as error:
        raise HTTPException(422, detail={"code": "JD_EVIDENCE_INVALID", "message": str(error)}) from error
    except ProviderError as error:
        raise HTTPException(502, detail={"code": "PROVIDER_FAILED", "message": str(error)}) from error
    services.repository.update(project_id, job_analysis=analysis)
    return analysis


@router.post("/{project_id}/questions")
async def create_questions(
    project_id: str,
    body: ProviderSelection,
    services: AppServices = Depends(get_services),
):
    project, version = _project_and_version(services, project_id)
    if project.job_analysis is None:
        raise HTTPException(409, detail={"code": "ANALYSIS_REQUIRED", "message": "请先分析职位描述"})
    provider = _provider_or_422(services, body.provider)
    return await generate_followup_questions(provider, project.job_analysis, version.resume, version.facts)


@router.post("/{project_id}/facts", response_model=ResumeVersion)
def create_fact(
    project_id: str,
    body: FactCreate,
    services: AppServices = Depends(get_services),
) -> ResumeVersion:
    _, version = _project_and_version(services, project_id)
    fact = Fact(**body.model_dump())
    return services.repository.save_version(
        project_id,
        version.resume,
        reason="补充事实",
        facts=[*version.facts, fact],
    )


@router.get("/{project_id}/match", response_model=MatchReport)
def get_match(project_id: str, services: AppServices = Depends(get_services)) -> MatchReport:
    project, version = _project_and_version(services, project_id)
    if project.job_analysis is None:
        raise HTTPException(409, detail={"code": "ANALYSIS_REQUIRED", "message": "请先分析职位描述"})
    return calculate_match(project.job_analysis, version.resume, version.facts)


@router.post("/{project_id}/resume/suggest", response_model=ResumePatch)
async def suggest_patch(
    project_id: str,
    body: ProviderSelection,
    services: AppServices = Depends(get_services),
) -> ResumePatch:
    project, version = _project_and_version(services, project_id)
    if project.job_analysis is None:
        raise HTTPException(409, detail={"code": "ANALYSIS_REQUIRED", "message": "请先分析职位描述"})
    provider = _provider_or_422(services, body.provider)
    try:
        return await suggest_resume_patch(
            provider,
            project.job_analysis,
            version.resume,
            version.facts,
            application_type=project.application_type,
        )
    except UnsupportedFactError as error:
        raise HTTPException(422, detail={"code": "FACT_EVIDENCE_INVALID", "message": str(error)}) from error
    except ProviderError as error:
        raise HTTPException(502, detail={"code": "PROVIDER_FAILED", "message": str(error)}) from error


@router.post("/{project_id}/resume/apply-patch", response_model=ResumeVersion)
def apply_patch(
    project_id: str,
    body: PatchApplyInput,
    services: AppServices = Depends(get_services),
) -> ResumeVersion:
    _, version = _project_and_version(services, project_id)
    try:
        updated = apply_resume_patch(
            version.resume,
            body.patch,
            set(body.accepted_operation_ids),
            facts=version.facts,
        )
    except PatchConflictError as error:
        raise HTTPException(409, detail={"code": "PATCH_CONFLICT", "message": str(error)}) from error
    except ValueError as error:
        raise HTTPException(422, detail={"code": "PATCH_INVALID", "message": str(error)}) from error
    return services.repository.save_version(
        project_id,
        updated,
        reason="应用 AI 建议",
        facts=version.facts,
    )


def _project_or_404(services: AppServices, project_id: str) -> JobProject:
    try:
        return services.repository.get(project_id)
    except ProjectNotFoundError as error:
        raise HTTPException(404, detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在"}) from error


def _project_and_version(services: AppServices, project_id: str) -> tuple[JobProject, ResumeVersion]:
    project = _project_or_404(services, project_id)
    version = services.repository.get_active_version(project_id)
    if version is None:
        raise HTTPException(409, detail={"code": "RESUME_REQUIRED", "message": "请先上传或创建简历"})
    return project, version


def _provider_or_422(services: AppServices, kind: str):
    try:
        return services.providers.resolve(kind)
    except ProviderConfigurationError as error:
        raise HTTPException(422, detail={"code": error.code, "message": str(error)}) from error
