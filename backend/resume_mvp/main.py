from collections.abc import Mapping
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from resume_mvp.api.autofill import router as autofill_router
from resume_mvp.api.dependencies import AppServices, ProviderRegistry
from resume_mvp.api.exports import router as exports_router
from resume_mvp.api.optimization import router as optimization_router
from resume_mvp.api.practice import router as practice_router
from resume_mvp.api.profile import router as profile_router
from resume_mvp.api.projects import router as projects_router
from resume_mvp.api.providers import router as providers_router
from resume_mvp.api.timeline import router as timeline_router
from resume_mvp.config import settings
from resume_mvp.database import create_database
from resume_mvp.optimization_orchestrator import OptimizationOrchestrator
from resume_mvp.provider_store import PROVIDER_SETTINGS_FILE
from resume_mvp.providers import AIProvider
from resume_mvp.providers.e2e import E2EProvider
from resume_mvp.repositories import ProjectRepository
from resume_mvp.secret_store import SecretStore, create_platform_secret_store


def create_app(
    *,
    data_dir: Path | None = None,
    test_providers: Mapping[str, AIProvider] | None = None,
    secret_store: SecretStore | None = None,
) -> FastAPI:
    app = FastAPI(title="中文 AI 简历工作台", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ],
        allow_origin_regex=r"^chrome-extension://.*$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    root = data_dir or settings.data_dir
    default_test_kind = ""
    providers = test_providers
    if providers is None and os.environ.get("RESUME_MVP_TEST_PROVIDER") == "1":
        providers = {"test": E2EProvider()}
        default_test_kind = "test"
    elif providers:
        # Prefer an explicit test provider kind when injecting fakes in unit tests.
        default_test_kind = "test" if "test" in providers else next(iter(providers))
    repository = ProjectRepository(create_database(root / "resume.db"))
    provider_registry = ProviderRegistry(
        providers,
        default_test_kind=default_test_kind,
        persist_path=None if default_test_kind else root / PROVIDER_SETTINGS_FILE,
        secret_store=secret_store if secret_store is not None else create_platform_secret_store(),
    )
    # Recover from process death without auto-calling external providers.
    repository.fail_stale_optimization_runs()
    app.state.services = AppServices(
        repository=repository,
        providers=provider_registry,
        optimization=OptimizationOrchestrator(repository, provider_registry),
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "resume-mvp"}

    @app.get("/", include_in_schema=False)
    def frontend() -> RedirectResponse:
        """Avoid a confusing 404 when the backend port is opened directly."""
        return RedirectResponse("http://127.0.0.1:5173/", status_code=307)

    app.include_router(projects_router)
    app.include_router(optimization_router)
    app.include_router(profile_router)
    app.include_router(autofill_router)
    app.include_router(providers_router)
    app.include_router(exports_router)
    app.include_router(practice_router)
    app.include_router(timeline_router)
    return app


app = create_app()
