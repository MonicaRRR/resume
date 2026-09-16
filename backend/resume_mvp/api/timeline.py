from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from resume_mvp.api.dependencies import AppServices, get_services
from resume_mvp.repositories import ProjectNotFoundError
from resume_mvp.timeline import TimelineEvent, project_timeline


router = APIRouter(tags=["timeline"])


@router.get("/api/projects/{project_id}/timeline", response_model=list[TimelineEvent])
def get_project_timeline(
    project_id: str,
    services: AppServices = Depends(get_services),
) -> list[TimelineEvent]:
    try:
        project = services.repository.get(project_id)
        versions = services.repository.list_versions(project_id)
        optimization_runs = services.repository.list_optimization_runs(project_id)
        practice_sessions = services.repository.list_practice(project_id)
    except ProjectNotFoundError as error:
        raise HTTPException(
            404,
            detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在"},
        ) from error
    return project_timeline(project, versions, optimization_runs, practice_sessions)
