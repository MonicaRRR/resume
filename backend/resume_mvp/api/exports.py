from __future__ import annotations

import base64
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from resume_mvp.api.dependencies import AppServices, get_services
from resume_mvp.domain import JobProject, ResumeDocument, ResumeVersion, SourcedText
from resume_mvp.exports import build_codex_handoff, build_docx, build_resume_json
from resume_mvp.latex import build_latex
from resume_mvp.preview import (
    PreviewConversionError,
    convert_docx_to_pdf,
    compile_latex_to_pdf,
    count_pdf_pages,
    render_pdf_page_pngs,
)
from resume_mvp.repositories import ProjectNotFoundError


router = APIRouter(prefix="/api/projects", tags=["exports"])


class HandoffResponse(BaseModel):
    markdown: str


class PreviewPdfInput(BaseModel):
    resume: ResumeDocument | None = None
    template_id: str | None = None


class ExportDocxInput(BaseModel):
    resume: ResumeDocument | None = None
    template_id: str | None = None


@router.post("/{project_id}/export/latex")
def export_latex(project_id: str, body: ExportDocxInput = Body(default_factory=ExportDocxInput), services: AppServices = Depends(get_services)) -> Response:
    project, version = _active(services, project_id)
    resume = _resume_for_project(project, body.resume or version.resume)
    source = build_latex(resume, body.template_id or project.selected_template_id, project.application_type)
    return Response(source.encode("utf-8"), media_type="application/x-tex; charset=utf-8", headers={"Content-Disposition": _attachment(f"{project.title}.tex")})


class PreviewPagesResponse(BaseModel):
    page_count: int = Field(ge=1)
    pages: list[str]


@router.post("/{project_id}/export/docx")
def export_docx(
    project_id: str,
    body: ExportDocxInput = Body(default_factory=ExportDocxInput),
    services: AppServices = Depends(get_services),
) -> Response:
    """Export Word from the provided draft when present; otherwise the saved active version."""
    project, version = _active(services, project_id)
    resume = _resume_for_project(project, body.resume or version.resume)
    template_id = body.template_id or project.selected_template_id
    try:
        content = build_docx(resume, template_id, project.application_type)
    except Exception as error:
        raise HTTPException(500, detail={"code": "EXPORT_FAILED", "message": "DOCX 导出失败"}) from error
    if not content:
        raise HTTPException(500, detail={"code": "EXPORT_FAILED", "message": "DOCX 导出结果为空"})
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": _attachment(f"{project.title}.docx")},
    )


@router.post("/{project_id}/preview/pdf")
def preview_pdf(
    project_id: str,
    body: PreviewPdfInput,
    services: AppServices = Depends(get_services),
) -> Response:
    """Build the same DOCX as export, convert to PDF for download / print."""
    project, version = _active(services, project_id)
    resume = _resume_for_project(project, body.resume or version.resume)
    template_id = body.template_id or project.selected_template_id
    try:
        pdf, pages = _build_preview_pdf(project, resume, template_id)
    except PreviewConversionError as error:
        raise HTTPException(503, detail={"code": "PREVIEW_UNAVAILABLE", "message": str(error)}) from error
    except Exception as error:
        raise HTTPException(500, detail={"code": "PREVIEW_FAILED", "message": "预览生成失败"}) from error
    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline; filename=resume-preview.pdf",
            "X-Resume-Page-Count": str(pages),
            "Cache-Control": "no-store",
        },
    )


@router.post("/{project_id}/preview/pages", response_model=PreviewPagesResponse)
def preview_pages(
    project_id: str,
    body: PreviewPdfInput,
    services: AppServices = Depends(get_services),
) -> PreviewPagesResponse:
    """Word→PDF→PNG pages for reliable in-app preview (avoids black PDF iframes)."""
    project, version = _active(services, project_id)
    resume = _resume_for_project(project, body.resume or version.resume)
    template_id = body.template_id or project.selected_template_id
    try:
        pdf, _pages = _build_preview_pdf(project, resume, template_id)
        pngs = render_pdf_page_pngs(pdf)
    except PreviewConversionError as error:
        raise HTTPException(503, detail={"code": "PREVIEW_UNAVAILABLE", "message": str(error)}) from error
    except Exception as error:
        raise HTTPException(500, detail={"code": "PREVIEW_FAILED", "message": "预览生成失败"}) from error
    return PreviewPagesResponse(
        page_count=len(pngs),
        pages=[base64.b64encode(png).decode("ascii") for png in pngs],
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


def _build_preview_pdf(
    project: JobProject,
    resume: ResumeDocument,
    template_id: str,
) -> tuple[bytes, int]:
    try:
        source = build_latex(resume, template_id, project.application_type)
        if resume.basics.photo_data_url:
            pdf = compile_latex_to_pdf(source, photo_data_url=resume.basics.photo_data_url)
        else:
            pdf = compile_latex_to_pdf(source)
    except PreviewConversionError as latex_error:
        # Keep DOCX as an optional compatibility path for existing installs;
        # callers still receive the clear unavailable error if both engines fail.
        try:
            docx = build_docx(resume, template_id, project.application_type)
            pdf = convert_docx_to_pdf(docx)
        except PreviewConversionError:
            raise latex_error
    return pdf, count_pdf_pages(pdf)


def _resume_for_project(project: JobProject, resume: ResumeDocument) -> ResumeDocument:
    """Keep reusable profile data separate from the role for this application."""
    role = (project.job_analysis.role_title if project.job_analysis else "").strip()
    scoped = resume.model_copy(deep=True)
    scoped.basics.target_role = SourcedText(value=role, origin="manual") if role else SourcedText()
    return scoped


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
