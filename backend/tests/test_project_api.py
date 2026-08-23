import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from resume_mvp.domain import JobAnalysis, JobRequirement, ResumePatch
from resume_mvp.main import create_app
from resume_mvp.providers import AIProvider


class JourneyProvider(AIProvider):
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
        if schema is ResumePatch:
            fact_match = re.search(r'"facts":\[\{"id":"([^"]+)"', prompt)
            fact_id = fact_match.group(1) if fact_match else ""
            return ResumePatch.model_validate(
                {
                    "operations": [
                        {
                            "id": "op-summary",
                            "path": "/basics/summary",
                            "before": {"value": "", "source_fact_ids": [], "origin": "manual", "confidence": 1},
                            "after": {
                                "value": "具备 Python API 开发经验",
                                "source_fact_ids": [fact_id],
                                "origin": "ai_rewrite",
                                "confidence": 1,
                            },
                            "reason": "匹配岗位核心要求",
                            "source_fact_ids": [fact_id],
                        }
                    ]
                }
            )
        return schema.model_validate({"items": []})


def test_project_import_analyze_and_apply_selected_patch(tmp_path: Path) -> None:
    """Catches broken wiring across the MVP's core local API journey."""
    app = create_app(data_dir=tmp_path, test_providers={"test": JourneyProvider()})
    client = TestClient(app)

    created = client.post(
        "/api/projects",
        json={
            "title": "后端工程师",
            "company_name": "示例科技",
            "application_type": "experienced",
            "job_description": "负责 Python API",
        },
    )
    assert created.status_code == 201
    project = created.json()

    imported = client.post(
        f"/api/projects/{project['id']}/resume/import",
        files={
            "file": (
                "resume.txt",
                "张宁\n后端工程师\n使用 Python 开发 API",
                "text/plain",
            )
        },
    )
    assert imported.status_code == 200
    assert imported.json()["resume"]["basics"]["name"] == "张宁"

    analysis = client.post(
        f"/api/projects/{project['id']}/analyze-jd",
        json={"provider": "test"},
    )
    assert analysis.status_code == 200
    assert analysis.json()["role_title"] == "后端工程师"

    suggested = client.post(
        f"/api/projects/{project['id']}/resume/suggest",
        json={"provider": "test"},
    )
    assert suggested.status_code == 200
    patch = suggested.json()
    applied = client.post(
        f"/api/projects/{project['id']}/resume/apply-patch",
        json={"patch": patch, "accepted_operation_ids": ["op-summary"]},
    )
    assert applied.status_code == 200
    assert applied.json()["resume"]["basics"]["summary"]["value"] == "具备 Python API 开发经验"

    versions = client.get(f"/api/projects/{project['id']}/versions").json()
    assert len(versions) == 2
    assert json.dumps(versions, ensure_ascii=False).count("初始导入") == 1


def test_project_requires_nonempty_jd(tmp_path: Path) -> None:
    """Catches projects that can enter AI analysis with no target evidence."""
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.post(
        "/api/projects",
        json={
            "title": "后端工程师",
            "company_name": "",
            "application_type": "experienced",
            "job_description": "  ",
        },
    )

    assert response.status_code == 422


def test_project_api_roundtrips_application_type(tmp_path: Path) -> None:
    """Catches losing the page policy when a project is stored and fetched."""
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.post(
        "/api/projects",
        json={
            "title": "实习申请",
            "company_name": "",
            "application_type": "internship",
            "job_description": "参与 Python API 开发",
        },
    )

    assert response.status_code == 201
    assert response.json()["application_type"] == "internship"
