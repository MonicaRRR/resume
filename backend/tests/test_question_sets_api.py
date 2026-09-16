from pathlib import Path

from fastapi.testclient import TestClient

from resume_mvp.domain import JobAnalysis, JobRequirement, MatchReport
from resume_mvp.main import create_app


class QuestionSetProvider:
    async def complete_json(self, prompt: str, schema: type):
        if schema is JobAnalysis:
            return JobAnalysis(requirements=[JobRequirement(text="熟悉 Python", evidence_quote="熟悉 Python")])
        if schema is MatchReport:
            return MatchReport(coverage=0, items=[])
        return schema.model_validate({})


def _client(tmp_path: Path) -> TestClient:
    client = TestClient(create_app(data_dir=tmp_path, test_providers={"test": QuestionSetProvider()}))
    client.put(
        "/api/profile",
        json={"resume": {"basics": {"name": "张宁"}, "education": [], "work_experience": [], "projects": [], "skills": [{"name": "技能", "items": [{"value": "Python"}]}]}},
    )
    return client


def test_question_set_is_persisted_and_reusable_without_provider(tmp_path: Path) -> None:
    client = _client(tmp_path)
    project = client.post(
        "/api/projects",
        json={"title": "后端工程师", "company_name": "示例公司", "application_type": "experienced", "job_description": "熟悉 Python"},
    ).json()
    created = client.post(f"/api/projects/{project['id']}/question-sets", json={"source_type": "jd"})
    assert created.status_code == 201
    payload = created.json()
    assert payload["questions"]
    assert payload["source_type"] == "jd"
    assert client.get(f"/api/projects/{project['id']}/question-sets").json()[0]["id"] == payload["id"]

    reused = client.post(f"/api/question-sets/{payload['id']}/reuse")
    assert reused.status_code == 200
    assert reused.json()["reuse_count"] == 1


def test_question_set_sources_use_resume_and_project_fallbacks(tmp_path: Path) -> None:
    client = _client(tmp_path)
    project = client.post(
        "/api/projects",
        json={"title": "后端工程师", "company_name": "示例公司", "application_type": "experienced", "job_description": "后端开发"},
    ).json()
    for source in ("resume", "project"):
        response = client.post(f"/api/projects/{project['id']}/question-sets", json={"source_type": source})
        assert response.status_code == 201
        assert response.json()["questions"]
