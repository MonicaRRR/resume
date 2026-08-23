from collections.abc import Mapping
from pathlib import Path

from fastapi import FastAPI

from resume_mvp.api.dependencies import AppServices, ProviderRegistry
from resume_mvp.api.projects import router as projects_router
from resume_mvp.api.providers import router as providers_router
from resume_mvp.config import settings
from resume_mvp.database import create_database
from resume_mvp.providers import AIProvider
from resume_mvp.repositories import ProjectRepository


def create_app(
    *,
    data_dir: Path | None = None,
    test_providers: Mapping[str, AIProvider] | None = None,
) -> FastAPI:
    app = FastAPI(title="中文 AI 简历工作台", version="0.1.0")
    root = data_dir or settings.data_dir
    app.state.services = AppServices(
        repository=ProjectRepository(create_database(root / "resume.db")),
        providers=ProviderRegistry(test_providers),
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "resume-mvp"}

    app.include_router(projects_router)
    app.include_router(providers_router)
    return app


app = create_app()
