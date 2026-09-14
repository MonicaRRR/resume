from pathlib import Path

from fastapi.testclient import TestClient

from resume_mvp.domain import (
    JobAnalysis,
    JobRequirement,
    PracticeEvaluation,
    PracticeFeedback,
    PracticeQuestion,
)
from resume_mvp.main import create_app
from resume_mvp.providers.e2e import E2EProvider
from tests.test_export_api import _seed_profile


class ApiPracticeProvider:
    async def complete_json(self, prompt: str, schema: type):
        if schema is JobAnalysis:
            return JobAnalysis(
                role_title="后端工程师",
                requirements=[
                    JobRequirement(text="Python API", evidence_quote="负责 Python API")
                ],
            )
        if schema is PracticeQuestion:
            return PracticeQuestion(category="专业题", prompt="如何保证 API 稳定性？", hint="考虑可观测性")
        if schema is PracticeEvaluation:
            return PracticeEvaluation(
                feedback=PracticeFeedback(
                    dimensions={name: "有依据" for name in ["相关性", "具体性", "证据", "结构", "表达"]},
                    summary="继续补充实例",
                )
            )
        return await E2EProvider().complete_json(prompt, schema)


def test_practice_session_is_saved_across_answer_roundtrip(tmp_path: Path) -> None:
    """Catches training state disappearing between local HTTP requests."""
    client = TestClient(
        create_app(data_dir=tmp_path, test_providers={"test": ApiPracticeProvider()})
    )
    _seed_profile(client)
    project = client.post(
        "/api/projects",
        json={
            "title": "后端工程师",
            "company_name": "",
            "application_type": "experienced",
            "job_description": "负责 Python API",
        },
    ).json()
    client.post(
        f"/api/projects/{project['id']}/resume/import",
        files={"file": ("resume.txt", "张宁\n后端工程师\n使用 Python 开发 API", "text/plain")},
    )
    client.post(f"/api/projects/{project['id']}/analyze-jd", json={"provider": "test"})

    started = client.post(
        f"/api/projects/{project['id']}/practice/sessions",
        json={"kind": "interview", "provider": "test"},
    )
    assert started.status_code == 201
    session = started.json()
    assert session["current_question"]["prompt"] == "如何保证 API 稳定性？"

    answered = client.post(
        f"/api/practice/sessions/{session['id']}/answer",
        json={"answer": "我通过指标、日志和链路追踪监控接口。", "provider": "test"},
    )
    assert answered.status_code == 200
    assert len(answered.json()["turns"]) == 1

    fetched = client.get(f"/api/practice/sessions/{session['id']}")
    assert fetched.json()["turns"][0]["answer"].startswith("我通过指标")
