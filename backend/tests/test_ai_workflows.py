import pytest

from resume_mvp.ai_workflows import (
    JobEvidenceError,
    UnsupportedFactError,
    analyze_job,
    generate_followup_questions,
    suggest_resume_patch,
)
from resume_mvp.domain import (
    Fact,
    FollowupQuestion,
    JobAnalysis,
    JobRequirement,
    QuestionList,
    ResumeDocument,
    ResumePatch,
    ResumePatchOperation,
)
from resume_mvp.providers.base import ProviderFormatError


class FakeProvider:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    async def complete_json(self, prompt: str, schema: type):
        self.prompts.append(prompt)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return schema.model_validate(response)


def valid_analysis() -> JobAnalysis:
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


@pytest.mark.anyio
async def test_suggestion_rejects_unsupported_fact_ids() -> None:
    """Catches AI patches that cite facts the user never supplied."""
    patch = ResumePatch(
        operations=[
            ResumePatchOperation(
                path="/basics/summary",
                before={"value": "", "source_fact_ids": [], "origin": "manual", "confidence": 1},
                after={
                    "value": "提升吞吐 40%",
                    "source_fact_ids": ["missing-fact"],
                    "origin": "ai_rewrite",
                    "confidence": 1,
                },
                reason="突出成果",
                source_fact_ids=["missing-fact"],
            )
        ]
    )
    provider = FakeProvider([patch])

    with pytest.raises(UnsupportedFactError, match="缺少事实依据"):
        await suggest_resume_patch(provider, valid_analysis(), ResumeDocument.blank(), facts=[])


@pytest.mark.anyio
async def test_job_inferences_retain_literal_jd_evidence() -> None:
    """Catches job-analysis claims whose citations are absent from the JD."""
    provider = FakeProvider([valid_analysis()])

    result = await analyze_job(provider, "示例科技", "负责 Python API 与数据库优化")

    assert result.requirements[0].evidence_quote in "负责 Python API 与数据库优化"


@pytest.mark.anyio
async def test_job_analysis_rejects_nonexistent_evidence_quote() -> None:
    """Catches fabricated JD citations even when the response schema is valid."""
    analysis = valid_analysis()
    analysis.requirements[0].evidence_quote = "要求十年经验"
    provider = FakeProvider([analysis])

    with pytest.raises(JobEvidenceError, match="无法在 JD 中定位"):
        await analyze_job(provider, "示例科技", "负责 Python API 与数据库优化")


@pytest.mark.anyio
async def test_invalid_structured_output_gets_one_format_repair() -> None:
    """Catches permanent failure on one malformed model response or unlimited retries."""
    provider = FakeProvider(
        [ProviderFormatError("格式错误", raw_response="not-json"), valid_analysis()]
    )

    result = await analyze_job(provider, "示例科技", "负责 Python API")

    assert result.role_title == "后端工程师"
    assert len(provider.prompts) == 2
    assert "只修复为指定 JSON 结构，不增删事实" in provider.prompts[1]


@pytest.mark.anyio
async def test_followup_questions_are_limited_deduplicated_and_private() -> None:
    """Catches question floods and unnecessary contact details sent to a model."""
    resume = ResumeDocument.blank()
    resume.basics.email = "private@example.com"
    resume.basics.phone = "13800000000"
    questions = QuestionList(
        items=[
            FollowupQuestion(question=f"问题 {index}", topic="量化成果" if index < 2 else f"主题 {index}")
            for index in range(7)
        ]
    )
    provider = FakeProvider([questions])

    result = await generate_followup_questions(provider, valid_analysis(), resume, facts=[])

    assert len(result) == 5
    assert len({question.topic for question in result}) == 5
    assert "private@example.com" not in provider.prompts[0]
    assert "13800000000" not in provider.prompts[0]


@pytest.mark.anyio
async def test_campus_suggestion_prompt_requires_one_page_without_truncation() -> None:
    """Catches campus optimization prompts that omit the approved one-page policy."""
    provider = FakeProvider([ResumePatch()])

    await suggest_resume_patch(
        provider,
        valid_analysis(),
        ResumeDocument.blank(),
        facts=[],
        application_type="campus",
    )

    assert "一页 A4" in provider.prompts[0]
    assert "不得截断" in provider.prompts[0]
