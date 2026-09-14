import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from resume_mvp.domain import JobAnalysis, JobRequirement, MatchReport, ResumePatch
from resume_mvp.main import create_app
from resume_mvp.providers import AIProvider
from resume_mvp.providers.base import ProviderRateLimitError


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
        if schema is MatchReport:
            return MatchReport.model_validate(
                {
                    "coverage": 1,
                    "items": [
                        {
                            "requirement_id": "req-python",
                            "requirement": "Python API 开发",
                            "status": "已有证据",
                            "fact_ids": [],
                            "excerpts": ["使用 Python 开发 API"],
                            "weight": 2,
                        }
                    ],
                }
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

    profile = client.put(
        "/api/profile",
        json={
            "resume": {
                "basics": {
                    "name": "张宁",
                    "email": "",
                    "phone": "",
                    "location": "",
                    "target_role": {"value": "后端工程师", "source_fact_ids": [], "origin": "manual", "confidence": 1},
                    "summary": {"value": "", "source_fact_ids": [], "origin": "manual", "confidence": 1},
                },
                "education": [],
                "work_experience": [{
                    "id": "w1",
                    "company": "示例科技",
                    "title": "实习生",
                    "start_date": "",
                    "end_date": "",
                    "bullets": [{"value": "使用 Python 开发 API", "source_fact_ids": [], "origin": "manual", "confidence": 1}],
                }],
                "projects": [],
                "skills": [{"id": "s1", "name": "技能", "items": [{"value": "Python", "source_fact_ids": [], "origin": "manual", "confidence": 1}]}],
                "certificates": [],
                "awards": [],
                "custom_sections": [],
                "section_order": ["basics", "work_experience", "skills"],
                "layout_profile": {
                    "source_kind": "builtin", "font_family": "", "heading_font_family": "", "accent_color": "",
                    "base_font_size": None, "line_height": None, "columns": 1, "imported": False,
                },
            }
        },
    )
    assert profile.status_code == 200
    assert profile.json()["ready"] is True

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
    assert project["active_resume_version_id"]
    assert project["job_analysis"]["role_title"] == "后端工程师"
    assert project["match_report"]["items"][0]["status"] == "已有证据"

    versions = client.get(f"/api/projects/{project['id']}/versions")
    assert versions.status_code == 200
    assert versions.json()[0]["resume"]["basics"]["name"] == "张宁"

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
    assert any(version["reason"] == "从个人经历库创建投递底稿" for version in versions)


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


def _seed_profile(client: TestClient) -> None:
    response = client.put(
        "/api/profile",
        json={
            "resume": {
                "basics": {
                    "name": "张宁",
                    "email": "",
                    "phone": "",
                    "location": "",
                    "target_role": {"value": "后端", "source_fact_ids": [], "origin": "manual", "confidence": 1},
                    "summary": {"value": "", "source_fact_ids": [], "origin": "manual", "confidence": 1},
                },
                "education": [],
                "work_experience": [{
                    "id": "w1", "company": "A", "title": "实习", "start_date": "", "end_date": "",
                    "bullets": [{"value": "Python", "source_fact_ids": [], "origin": "manual", "confidence": 1}],
                }],
                "projects": [],
                "skills": [],
                "certificates": [],
                "awards": [],
                "custom_sections": [],
                "section_order": ["basics", "work_experience"],
                "layout_profile": {
                    "source_kind": "builtin", "font_family": "", "heading_font_family": "", "accent_color": "",
                    "base_font_size": None, "line_height": None, "columns": 1, "imported": False,
                },
            }
        },
    )
    assert response.status_code == 200


def test_project_api_roundtrips_application_type(tmp_path: Path) -> None:
    """Catches losing the page policy when a project is stored and fetched."""
    client = TestClient(create_app(data_dir=tmp_path, test_providers={"test": JourneyProvider()}))
    _seed_profile(client)

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


def test_create_project_requires_profile(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.post(
        "/api/projects",
        json={
            "title": "后端工程师",
            "company_name": "",
            "application_type": "experienced",
            "job_description": "负责 Python API",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PROFILE_REQUIRED"


def test_create_project_requires_provider_when_profile_ready(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))
    _seed_profile(client)
    response = client.post(
        "/api/projects",
        json={
            "title": "后端工程师",
            "company_name": "",
            "application_type": "experienced",
            "job_description": "负责 Python API",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PROVIDER_REQUIRED"


def test_create_project_preserves_rate_limit_status_and_created_project(tmp_path: Path) -> None:
    """Catches a created project being hidden behind a mislabeled provider failure."""
    class RateLimitedProvider:
        async def complete_json(self, prompt: str, schema: type):
            raise ProviderRateLimitError("1309 Coding Plan 套餐已到期", retry_after_seconds=2)

    client = TestClient(create_app(data_dir=tmp_path, test_providers={"limited": RateLimitedProvider()}))
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

    assert response.status_code == 429
    detail = response.json()["detail"]
    assert detail["code"] == "PROVIDER_RATE_LIMITED"
    assert detail["retry_after_seconds"] == 2.0
    projects = client.get("/api/projects").json()
    assert len(projects) == 1
    assert detail["project_id"] == projects[0]["id"]


def test_restore_from_profile_resets_corrupted_project_draft(tmp_path: Path) -> None:
    """One-click restore must put the experience library back as the active delivery draft."""
    client = TestClient(create_app(data_dir=tmp_path, test_providers={"test": JourneyProvider()}))
    _seed_profile(client)
    project = client.post(
        "/api/projects",
        json={
            "title": "后端工程师",
            "company_name": "示例科技",
            "application_type": "experienced",
            "job_description": "负责 Python API",
        },
    ).json()
    versions = client.get(f"/api/projects/{project['id']}/versions").json()
    resume = versions[0]["resume"]
    resume["projects"] = []
    resume["basics"]["summary"] = {
        "value": "被 AI 改坏的概述",
        "source_fact_ids": [],
        "origin": "manual",
        "confidence": 1,
    }
    broken = client.put(
        f"/api/projects/{project['id']}/resume",
        json={"resume": resume, "facts": versions[0]["facts"], "reason": "AI 误改"},
    )
    assert broken.status_code == 200
    assert broken.json()["resume"]["basics"]["summary"]["value"] == "被 AI 改坏的概述"

    restored = client.post(f"/api/projects/{project['id']}/resume/restore-from-profile")
    assert restored.status_code == 200
    assert restored.json()["reason"] == "从经历库一键复原"
    assert restored.json()["resume"]["basics"]["summary"]["value"] == ""
    assert restored.json()["resume"]["work_experience"]
    assert restored.json()["resume"]["basics"]["name"] == "张宁"

    project_after = client.get(f"/api/projects/{project['id']}").json()
    assert project_after["active_resume_version_id"] == restored.json()["id"]


def test_delete_project_removes_it(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path, test_providers={"test": JourneyProvider()}))
    _seed_profile(client)
    created = client.post(
        "/api/projects",
        json={
            "title": "待删除项目",
            "company_name": "示例",
            "application_type": "experienced",
            "job_description": "负责 Python API 开发",
        },
    )
    assert created.status_code == 201
    project_id = created.json()["id"]

    deleted = client.delete(f"/api/projects/{project_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    assert all(item["id"] != project_id for item in client.get("/api/projects").json())
