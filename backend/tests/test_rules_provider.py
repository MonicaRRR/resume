from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from resume_mvp.domain import (
    Fact,
    JobAnalysis,
    PracticeEvaluation,
    PracticeQuestion,
    QuestionList,
    ResumeDocument,
    ResumePatch,
)
from resume_mvp.main import create_app
from resume_mvp.providers.rules import RulesProvider


def _resume() -> ResumeDocument:
    return ResumeDocument.model_validate(
        {
            "basics": {"name": "林宁"},
            "work_experience": [
                {
                    "id": "w1",
                    "company": "甲公司",
                    "title": "工程师",
                    "bullets": [
                        {
                            "value": "维护内部工具，使用 Python 和 FastAPI 开发订单 API",
                            "source_fact_ids": ["fact-work"],
                            "origin": "manual",
                        }
                    ],
                }
            ],
            "projects": [
                {
                    "id": "p1",
                    "name": "数据看板",
                    "bullets": [
                        {
                            "value": "整理需求，使用 React 开发数据看板",
                            "source_fact_ids": ["fact-project"],
                            "origin": "manual",
                        }
                    ],
                }
            ],
        }
    )


@pytest.mark.anyio
async def test_rules_provider_derives_outputs_from_inputs() -> None:
    provider = RulesProvider()
    analysis = await provider.complete_json(
        '输入数据：\n{"company_name":"甲公司","job_description":"职位：后端工程师\\n'
        '负责 Python API 开发；熟悉 FastAPI 和 SQL；本科及以上学历"}',
        JobAnalysis,
    )
    assert analysis.role_title == "后端工程师"
    assert "Python" in analysis.keywords
    assert any("FastAPI" in item.evidence_quote for item in analysis.requirements)

    resume = _resume()
    facts = [
        Fact(id="fact-work", category="工作/实习经历", statement="使用 Python 和 FastAPI 开发订单 API", source_type="manual"),
        Fact(id="fact-project", category="项目经历", statement="使用 React 开发数据看板", source_type="manual"),
    ]
    data = {
        "job_analysis": analysis.model_dump(mode="json"),
        "resume": resume.model_dump(mode="json"),
        "facts": [fact.model_dump(mode="json") for fact in facts],
        "application_type": "campus",
    }
    import json

    prompt = "输入数据：\n" + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    questions = await provider.complete_json(prompt, QuestionList)
    patch = await provider.complete_json(prompt, ResumePatch)

    assert all(question.requirement_id in {item.id for item in analysis.requirements} for question in questions.items)
    assert patch.experience_asks
    assert all("99%" not in str(operation.after) for operation in patch.operations)
    assert all(set(operation.source_fact_ids) <= {"fact-work", "fact-project"} for operation in patch.operations)


@pytest.mark.anyio
async def test_rules_practice_evaluates_submitted_answer_without_writing_one() -> None:
    provider = RulesProvider()
    question = PracticeQuestion(
        id="q1",
        category="专业题",
        prompt="请说明 Python API 经验",
        requirement_ids=["req-1"],
    )
    evaluation = await provider.complete_json(
        '输入：{"kind":"interview","question":'
        + question.model_dump_json()
        + ',"answer":"我使用 Python 开发接口，并处理异常。"}',
        PracticeEvaluation,
    )
    assert evaluation.feedback.improved_answer == ""
    assert "规则模式" in evaluation.explanation
    assert evaluation.feedback.percentage_score is None


def test_default_rules_mode_supports_project_creation_without_api(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))
    state = client.get("/api/settings/providers").json()
    assert state["kind"] == "rules"
    assert state["configured"] is True

    profile = _resume().model_dump(mode="json")
    assert client.put("/api/profile", json={"resume": profile}).status_code == 200
    created = client.post(
        "/api/projects",
        json={
            "title": "后端岗位",
            "company_name": "甲公司",
            "application_type": "experienced",
            "job_description": "职位：后端工程师\n负责 Python API 开发；熟悉 FastAPI 和 SQL",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["job_analysis"]["role_title"] == "后端工程师"
    assert body["match_report"]["items"]
