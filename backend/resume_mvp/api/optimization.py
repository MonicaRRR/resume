from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from resume_mvp.api.dependencies import (
    AppServices,
    ProviderConfigurationError,
    get_services,
)
from resume_mvp.optimization_models import OptimizationMode, OptimizationRun
from resume_mvp.repositories import (
    OptimizationRunNotFoundError,
    ProjectNotFoundError,
)


router = APIRouter(prefix="/api/projects", tags=["optimization"])


class OptimizationCreate(BaseModel):
    mode: OptimizationMode = "quick"
    provider: str = Field(min_length=1)


@router.post(
    "/{project_id}/optimization-runs",
    response_model=OptimizationRun,
    status_code=202,
)
async def create_optimization_run(
    project_id: str,
    body: OptimizationCreate,
    background: BackgroundTasks,
    services: AppServices = Depends(get_services),
) -> OptimizationRun:
    _project_and_active_version_or_error(services, project_id)
    _provider_or_422(services, body.provider)
    try:
        run = await services.optimization.create_run(project_id, body.mode, body.provider)
    except ProjectNotFoundError as error:
        raise HTTPException(
            404,
            detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在"},
        ) from error
    except ValueError as error:
        raise HTTPException(
            409,
            detail={"code": "RESUME_REQUIRED", "message": str(error)},
        ) from error
    background.add_task(services.optimization.execute, run.id)
    return run


@router.get(
    "/{project_id}/optimization-runs/latest",
    response_model=OptimizationRun | None,
)
def get_latest_optimization_run(
    project_id: str,
    services: AppServices = Depends(get_services),
) -> OptimizationRun | None:
    try:
        services.repository.get(project_id)
    except ProjectNotFoundError as error:
        raise HTTPException(
            404,
            detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在"},
        ) from error
    return services.repository.latest_optimization_run(project_id)


@router.get(
    "/{project_id}/optimization-runs/{run_id}",
    response_model=OptimizationRun,
)
def get_optimization_run(
    project_id: str,
    run_id: str,
    services: AppServices = Depends(get_services),
) -> OptimizationRun:
    return _owned_run_or_404(services, project_id, run_id)


@router.post(
    "/{project_id}/optimization-runs/{run_id}/cancel",
    response_model=OptimizationRun,
)
async def cancel_optimization_run(
    project_id: str,
    run_id: str,
    services: AppServices = Depends(get_services),
) -> OptimizationRun:
    _owned_run_or_404(services, project_id, run_id)
    return await services.optimization.cancel(run_id)


@router.post(
    "/{project_id}/optimization-runs/{run_id}/resume",
    response_model=OptimizationRun,
    status_code=202,
)
async def resume_optimization_run(
    project_id: str,
    run_id: str,
    background: BackgroundTasks,
    services: AppServices = Depends(get_services),
) -> OptimizationRun:
    run = _owned_run_or_404(services, project_id, run_id)
    try:
        prepared = await services.optimization.prepare_resume(run.id)
    except ValueError as error:
        raise HTTPException(
            409,
            detail={"code": "RESUME_NOT_ALLOWED", "message": str(error)},
        ) from error
    background.add_task(services.optimization.execute, prepared.id)
    return prepared


def _project_and_active_version_or_error(services: AppServices, project_id: str) -> None:
    try:
        project = services.repository.get(project_id)
    except ProjectNotFoundError as error:
        raise HTTPException(
            404,
            detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在"},
        ) from error
    if services.repository.get_active_version(project_id) is None:
        raise HTTPException(
            409,
            detail={"code": "RESUME_REQUIRED", "message": "请先上传或创建简历"},
        )
    _ = project


def _provider_or_422(services: AppServices, kind: str):
    try:
        return services.providers.resolve(kind)
    except ProviderConfigurationError as error:
        raise HTTPException(422, detail={"code": error.code, "message": str(error)}) from error


def _owned_run_or_404(
    services: AppServices,
    project_id: str,
    run_id: str,
) -> OptimizationRun:
    try:
        services.repository.get(project_id)
    except ProjectNotFoundError as error:
        raise HTTPException(
            404,
            detail={"code": "PROJECT_NOT_FOUND", "message": "项目不存在"},
        ) from error
    try:
        run = services.repository.get_optimization_run(run_id)
    except OptimizationRunNotFoundError as error:
        raise HTTPException(
            404,
            detail={"code": "OPTIMIZATION_RUN_NOT_FOUND", "message": "优化任务不存在"},
        ) from error
    if run.project_id != project_id:
        raise HTTPException(
            404,
            detail={"code": "OPTIMIZATION_RUN_NOT_FOUND", "message": "优化任务不存在"},
        )
    return run
