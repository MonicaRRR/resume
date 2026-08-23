from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from resume_mvp.api.dependencies import AppServices, get_services
from resume_mvp.domain import JobProject, ResumeVersion
from resume_mvp.exports import build_codex_handoff, build_docx, build_resume_json
from resume_mvp.page_policy import evaluate_page_policy
from resume_mvp.repositories import ProjectNotFoundError


router = APIRouter(prefix="/api/projects", tags=["exports"])


class HandoffResponse(BaseModel):
    markdown: str


@router.post("/{project_id}/export/docx")
def export_docx(project_id: str, services: AppServices = Depends(get_services)) -> Response:
    project, version = _active(services, project_id)
    policy = evaluate_page_policy(version.resume, project.application_type)
    if policy.overflow:
        raise HTTPException(
            422,
            detail={
                "code": "RESUME_OVERFLOW",
                "message": "当前内容超过一页，请先使用一页优化建议精简排版",
                "largest_sections": policy.largest_sections[:3],
            },
        )
    try:
        content = build_docx(
            version.resume,
            project.selected_template_id,
            project.application_type,
        )
    except Exception as error:
        raise HTTPException(500, detail={"code": "EXPORT_FAILED", "message": "DOCX 导出失败"}) from error
    if not content:
        raise HTTPException(500, detail={"code": "EXPORT_FAILED", "message": "DOCX 导出结果为空"})
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": _attachment(f"{project.title}.docx")},
    )


@router.get("/{project_id}/export/json")
def export_json(project_id: str, services: AppServices = Depends(get_services)) -> Response:
    project, version = _active(services, project_id)
    return Response(
        build_resume_json(project, version),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": _attachment(f"{project.title}.json")},
    )


@router.post("/{project_id}/codex-handoff", response_model=HandoffResponse)
def codex_handoff(project_id: str, services: AppServices = Depends(get_services)) -> HandoffResponse:
    project, version = _active(services, project_id)
    return HandoffResponse(
        markdown=build_codex_handoff(
            project,
            project.job_analysis,
            version.resume,
            version.facts,
        )
    )


def _active(services: AppServices, project_id: str) -> tuple[JobProject, ResumeVersion]:
    try:
        project = services.repository.get(project_id)
    except ProjectNotFoundError as error:
        raise HTTPException(404, detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在"}) from error
    version = services.repository.get_active_version(project_id)
    if version is None:
        raise HTTPException(409, detail={"code": "RESUME_REQUIRED", "message": "请先上传或创建简历"})
    return project, version


def _attachment(filename: str) -> str:
    return f"attachment; filename*=UTF-8''{quote(filename)}"
