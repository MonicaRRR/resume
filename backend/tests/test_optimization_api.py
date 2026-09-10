from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from resume_mvp.database import create_database
from resume_mvp.domain import JobAnalysis, JobRequirement, MatchReport, ResumePatch
from resume_mvp.main import create_app
from resume_mvp.optimization_models import LayoutReport, OptimizationReview
from resume_mvp.providers import AIProvider
from resume_mvp.repositories import ProjectRepository


class OptimizationApiProvider(AIProvider):
    async def complete_json(self, prompt: str, schema: type):
        if schema is JobAnalysis:
            return JobAnalysis(
                role_title="后端工程师",
                requirements=[
                    JobRequirement(
                        id="req-python",
                        text="Python API 开发",
                        evidence_quote="负责 Python API",
                        weight=2,
                    )
                ],
            )
        if schema is MatchReport:
            return MatchReport(coverage=1, items=[])
        if schema is ResumePatch:
            return ResumePatch(operations=[])
        if schema is OptimizationReview:
            return OptimizationReview(factuality_passed=True, expression_score=90)
        return schema.model_validate({})


async def _fake_render(context, resume) -> LayoutReport:
    return LayoutReport(page_count=1, density_by_page=[0.8], issues=[])


def _seed_profile(client: TestClient) -> None:
    assert (
        client.put(
            "/api/profile",
            json={
                "resume": {
                    "basics": {
                        "name": "张宁",
                        "email": "",
                        "phone": "",
                        "location": "",
                        "target_role": {
                            "value": "后端工程师",
                            "source_fact_ids": [],
                            "origin": "manual",
                            "confidence": 1,
                        },
                        "summary": {
                            "value": "",
                            "source_fact_ids": [],
                            "origin": "manual",
                            "confidence": 1,
                        },
                    },
                    "education": [],
                    "work_experience": [
                        {
                            "id": "w1",
                            "company": "示例科技",
                            "title": "实习生",
                            "start_date": "",
                            "end_date": "",
                            "bullets": [
                                {
                                    "value": "使用 Python 开发 API",
                                    "source_fact_ids": [],
                                    "origin": "manual",
                                    "confidence": 1,
                                }
                            ],
                        }
                    ],
                    "projects": [],
                    "skills": [
                        {
                            "id": "s1",
                            "name": "技能",
                            "items": [
                                {
                                    "value": "Python",
                                    "source_fact_ids": [],
                                    "origin": "manual",
                                    "confidence": 1,
                                }
                            ],
                        }
                    ],
                    "certificates": [],
                    "awards": [],
                    "custom_sections": [],
                    "section_order": [
                        "basics",
                        "work_experience",
                        "projects",
                        "education",
                        "skills",
                    ],
                    "layout_profile": {
                        "source_kind": "builtin",
                        "font_family": "",
                        "heading_font_family": "",
                        "accent_color": "",
                        "base_font_size": None,
                        "line_height": None,
                        "columns": 1,
                        "imported": False,
                    },
                }
            },
        ).status_code
        == 200
    )


def _create_project(client: TestClient) -> str:
    _seed_profile(client)
    response = client.post(
        "/api/projects",
        json={
            "title": "后端工程师",
            "company_name": "示例科技",
            "application_type": "experienced",
            "job_description": "负责 Python API",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _build_client(tmp_path: Path) -> TestClient:
    app = create_app(data_dir=tmp_path, test_providers={"test": OptimizationApiProvider()})
    app.state.services.optimization._render_fn = _fake_render
    return TestClient(app)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return _build_client(tmp_path)


@pytest.fixture
def project_id(client: TestClient) -> str:
    return _create_project(client)


def create_run(client: TestClient, project_id: str, *, mode: str = "quick") -> dict:
    response = client.post(
        f"/api/projects/{project_id}/optimization-runs",
        json={"mode": mode, "provider": "test"},
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_create_deep_run_returns_accepted_contract(client: TestClient, project_id: str) -> None:
    response = client.post(
        f"/api/projects/{project_id}/optimization-runs",
        json={"mode": "deep", "provider": "test"},
    )
    assert response.status_code == 202
    assert response.json()["mode"] == "deep"


def test_run_cannot_be_read_through_another_project(client: TestClient, project_id: str) -> None:
    first_project = project_id
    second_project = _create_project(client)
    run = create_run(client, first_project)
    response = client.get(f"/api/projects/{second_project}/optimization-runs/{run['id']}")
    assert response.status_code == 404


def test_cancel_is_idempotent(client: TestClient, project_id: str) -> None:
    run = create_run(client, project_id)
    url = f"/api/projects/{project_id}/optimization-runs/{run['id']}/cancel"
    assert client.post(url).status_code == 200
    assert client.post(url).status_code == 200


def test_stale_active_runs_are_failed_on_startup(tmp_path: Path) -> None:
    client = _build_client(tmp_path)
    project_id = _create_project(client)
    run = create_run(client, project_id, mode="quick")

    repo = ProjectRepository(create_database(tmp_path / "resume.db"))
    repo.update_optimization_run(run["id"], status="rendering", message="进行中")

    restarted = create_app(data_dir=tmp_path, test_providers={"test": OptimizationApiProvider()})
    loaded = restarted.state.services.repository.get_optimization_run(run["id"])
    assert loaded.status == "failed"
    assert "上次运行被中断" in loaded.message


def test_resume_requeues_interrupted_failed_run(client: TestClient, project_id: str, tmp_path: Path) -> None:
    run = create_run(client, project_id)
    repo = ProjectRepository(create_database(tmp_path / "resume.db"))
    frozen = repo.get_optimization_run(run["id"])
    repo.update_optimization_run(
        run["id"],
        status="failed",
        message="上次运行被中断，可点击继续",
    )

    response = client.post(f"/api/projects/{project_id}/optimization-runs/{run['id']}/resume")
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["input_version_id"] == frozen.input_version_id
