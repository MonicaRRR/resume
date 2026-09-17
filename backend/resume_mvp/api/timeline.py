from fastapi import APIRouter, Depends, HTTPException

from resume_mvp.api.dependencies import AppServices, get_services
from resume_mvp.domain import ProjectTimeline
from resume_mvp.repositories import ProjectNotFoundError


router = APIRouter(prefix="/api/projects", tags=["timeline"])


@router.get("/{project_id}/timeline", response_model=ProjectTimeline)
def get_project_timeline(
    project_id: str,
    services: AppServices = Depends(get_services),
) -> ProjectTimeline:
    try:
        return services.repository.get_timeline(project_id)
    except ProjectNotFoundError as error:
        raise HTTPException(
            404,
            detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在"},
        ) from error
