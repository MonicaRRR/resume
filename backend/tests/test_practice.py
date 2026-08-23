import pytest

from resume_mvp.domain import (
    JobAnalysis,
    JobProject,
    PracticeEvaluation,
    PracticeFeedback,
    PracticeQuestion,
    ResumeDocument,
    utc_now,
)
from resume_mvp.practice import answer_practice, start_practice


class PracticeProvider:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses

    async def complete_json(self, prompt: str, schema: type):
        return schema.model_validate(self.responses.pop(0))


def project() -> JobProject:
    now = utc_now()
    return JobProject(
        id="project-1",
        title="后端工程师",
        application_type="experienced",
        job_description="负责 Python API",
        job_analysis=JobAnalysis(role_title="后端工程师"),
        created_at=now,
        updated_at=now,
    )


@pytest.mark.anyio
async def test_interview_feedback_uses_named_dimensions() -> None:
    """Catches opaque or pseudo-precise interview scores."""
    question = PracticeQuestion(category="经历深挖", prompt="请介绍一次接口重构")
    evaluation = PracticeEvaluation(
        feedback=PracticeFeedback(
            dimensions={
                "相关性": "紧扣接口重构",
                "具体性": "需要补充规模",
                "证据": "给出了个人职责",
                "结构": "建议使用 STAR",
                "表达": "表述清楚",
            },
            summary="补充量化结果",
            improved_answer="我负责重构订单接口……",
        )
    )
    provider = PracticeProvider([question, evaluation])
    session = await start_practice("interview", provider, project(), ResumeDocument.blank())

    turn = await answer_practice(session, "我负责重构订单接口……", provider)

    assert set(turn.feedback.dimensions) == {"相关性", "具体性", "证据", "结构", "表达"}
    assert turn.feedback.percentage_score is None
    assert session.turns == [turn]


@pytest.mark.anyio
async def test_written_practice_hides_explanation_before_answer() -> None:
    """Catches answer explanations being revealed before the user attempts a question."""
    question = PracticeQuestion(
        category="案例题",
        prompt="如何定位接口延迟？",
        hint="先拆分链路耗时",
        explanation="不应提前显示",
    )
    provider = PracticeProvider([question])

    session = await start_practice("written", provider, project(), ResumeDocument.blank())

    assert session.current_question.hint == "先拆分链路耗时"
    assert session.current_question.explanation is None
