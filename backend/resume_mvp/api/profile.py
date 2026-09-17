from __future__ import annotations

import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from resume_mvp.api.dependencies import AppServices, get_services
from resume_mvp.domain import Fact, ResumeDocument
from resume_mvp.ingestion import ImportResult, ResumeImportError, import_resume
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


@router.get("/export/json")
def export_profile_json(services: AppServices = Depends(get_services)) -> Response:
    """Download a portable, versioned backup of the complete experience library."""
    resume, facts = services.repository.get_profile()
    payload = {
        "schema_version": 1,
        "resume": resume.model_dump(mode="json"),
        "facts": [fact.model_dump(mode="json") for fact in facts],
        "ready": profile_is_ready(resume),
    }
    filename = quote("个人经历库.json")
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.put("", response_model=ProfilePayload)
def save_profile(body: ProfileSaveInput, services: AppServices = Depends(get_services)) -> ProfilePayload:
    resume, facts = services.repository.save_profile(body.resume)
    return ProfilePayload(resume=resume, facts=facts, ready=profile_is_ready(resume))


@router.post("/import", response_model=ImportResult)
async def import_profile_resume(
    file: UploadFile = File(...),
    services: AppServices = Depends(get_services),
) -> ImportResult:
    """Parse an uploaded resume into structured fields without writing the profile yet."""
    del services  # parsing is stateless; persistence stays on explicit PUT /api/profile
    try:
        return import_resume(
            file.filename or "resume.txt",
            file.content_type or "application/octet-stream",
            await file.read(),
        )
    except ResumeImportError as error:
        raise HTTPException(422, detail={"code": "IMPORT_FAILED", "message": str(error)}) from error
