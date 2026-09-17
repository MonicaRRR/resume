import pytest

from resume_mvp.ai_workflows import (
    _align_after_shape,
    _ground_patch_operations,
    analyze_job,
    generate_followup_questions,
    suggest_resume_patch,
)
from resume_mvp.domain import (
    EducationEntry,
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
async def test_suggestion_drops_ops_without_usable_facts() -> None:
    """Invalid fact-only patches should be dropped instead of shown to the user."""
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

    result = await suggest_resume_patch(provider, valid_analysis(), ResumeDocument.blank(), facts=[])
    assert result.operations == []


@pytest.mark.anyio
async def test_suggestion_rewrites_hallucinated_fact_ids() -> None:
    """Catches hard failures when the model invents UUIDs but real project facts exist."""
    fact = Fact(
        id="fact-project-1",
        category="项目经历",
        statement="完成订单系统重构",
        source_type="manual",
        user_confirmed=True,
    )
    patch = ResumePatch(
        operations=[
            ResumePatchOperation(
                path="/projects",
                before=[],
                after=[{"name": "订单系统", "role": "负责人", "start_date": "", "end_date": "", "bullets": []}],
                reason="保留与 JD 相关的项目",
                source_fact_ids=["6f9f97fa-f5fa-4487-996d-0867fa9ac459", "missing-fact"],
            )
        ]
    )
    provider = FakeProvider([patch])

    result = await suggest_resume_patch(provider, valid_analysis(), ResumeDocument.blank(), facts=[fact])

    assert result.operations[0].source_fact_ids == ["fact-project-1"]


@pytest.mark.anyio
async def test_job_inferences_retain_literal_jd_evidence() -> None:
    """Catches job-analysis claims whose citations are absent from the JD."""
    provider = FakeProvider([valid_analysis()])

    result = await analyze_job(provider, "示例科技", "负责 Python API 与数据库优化")

    assert result.requirements[0].evidence_quote in "负责 Python API 与数据库优化"


@pytest.mark.anyio
async def test_job_analysis_marks_unlocated_quote_as_inferred() -> None:
    """Unlocatable citations should be annotated, not block JD analysis."""
    analysis = valid_analysis()
    analysis.requirements[0].evidence_quote = "要求十年经验"
    analysis.requirements[0].inferred = False
    provider = FakeProvider([analysis])

    result = await analyze_job(provider, "示例科技", "负责 Python API 与数据库优化")

    assert result.requirements[0].inferred is True
    assert "未在 JD 原文精确定位" in result.requirements[0].evidence_quote


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
async def test_followups_skip_cohort_requirement_with_sufficient_evidence() -> None:
    resume = ResumeDocument.blank()
    resume.education = [EducationEntry(
        institution="示例大学",
        degree="硕士",
        field="人工智能",
        start_date="2024-09",
        end_date="2026-10",
    )]
    analysis = JobAnalysis(requirements=[
        JobRequirement(
            id="grad",
            text="2027届本科及以上，计算机相关专业",
            evidence_quote="2027届本科及以上",
            weight=2,
        ),
        JobRequirement(
            id="testing",
            text="具备自动化测试实践",
            evidence_quote="自动化测试",
            weight=1,
        ),
    ])
    provider = FakeProvider([QuestionList(items=[
        FollowupQuestion(
            id="ask-grad",
            question="你是否属于2027届？",
            topic="校招资格",
            requirement_id="grad",
        ),
        FollowupQuestion(
            id="ask-testing",
            question="你做过哪些自动化测试？",
            topic="自动化测试",
            requirement_id="testing",
        ),
    ])])

    result = await generate_followup_questions(provider, analysis, resume, facts=[])

    assert "ask-grad" not in [question.id for question in result]
    assert "ask-testing" in [question.id for question in result]
    assert "evidence_status" in provider.prompts[0]


@pytest.mark.anyio
async def test_thin_projects_attach_experience_asks() -> None:
    provider = FakeProvider([ResumePatch(operations=[])])
    resume = ResumeDocument.blank()

    result = await suggest_resume_patch(
        provider,
        valid_analysis(),
        resume,
        facts=[],
        application_type="campus",
    )

    assert result.experience_asks
    assert "项目" in result.experience_asks[0].question
    assert result.experience_asks[0].guidance
    assert "experience_asks" in provider.prompts[0]
    assert "课程设计" in provider.prompts[0] or "课程" in provider.prompts[0]


@pytest.mark.anyio
async def test_experienced_thin_projects_avoid_campus_asks() -> None:
    provider = FakeProvider([ResumePatch(operations=[])])
    result = await suggest_resume_patch(
        provider,
        valid_analysis(),
        ResumeDocument.blank(),
        facts=[],
        application_type="experienced",
    )
    ask = result.experience_asks[0]
    assert "工作项目" in ask.question or "专项" in ask.question
    assert "课程" not in ask.question
    assert "比赛" not in ask.question
    assert "课程大作业" not in ask.guidance
    assert "黑客松" not in ask.guidance
    assert "数学建模" not in ask.guidance
    assert "社招禁止" in provider.prompts[0]


@pytest.mark.anyio
async def test_campus_suggestion_prompt_requires_one_page_with_user_consent() -> None:
    """Catches campus prompts that drop one-page policy or silent truncation without consent."""
    provider = FakeProvider([ResumePatch()])

    await suggest_resume_patch(
        provider,
        valid_analysis(),
        ResumeDocument.blank(),
        facts=[],
        application_type="campus",
    )

    prompt = provider.prompts[0]
    assert "一页" in prompt
    assert "不得编造" in prompt
    assert "用户勾选同意" in prompt
    assert "筛选" in prompt or "适配" in prompt
    assert "writing_style_guides" in prompt
    assert "campus-one-pager" in prompt
    assert "layout-density-skills" in prompt
    assert "投递版骨架" in prompt or "6–12" in prompt
    assert "/skills" in prompt
    assert "LaTeX" in prompt or "\\item" in prompt
    assert "互不重复" in prompt or "同义改写" in prompt
    assert "experience_inventory" in prompt
    assert "allowed_patch_roots" in prompt
    assert "experience_asks" in prompt
    assert "/projects" in prompt


def test_align_after_shape_wraps_plain_text_for_sourced_fields() -> None:
    before = {"value": "旧文", "source_fact_ids": ["f1"], "origin": "manual", "confidence": 1}
    assert _align_after_shape(before, "新文")["value"] == "新文"
    bullets_before = [before]
    aligned = _align_after_shape(bullets_before, "整段新描述")
    assert isinstance(aligned, list) and aligned[0]["value"] == "整段新描述"


def test_grounding_drops_unintended_empty_rewrites() -> None:
    fact = Fact(
        id="fact-1",
        category="工作/实习经历",
        statement="负责支付链路重构并提升稳定性",
        source_type="manual",
        user_confirmed=True,
    )
    resume = ResumeDocument.blank()
    resume.work_experience = []
    from resume_mvp.domain import WorkExperienceEntry, SourcedText

    resume.work_experience = [
        WorkExperienceEntry(
            company="示例",
            title="工程师",
            bullets=[SourcedText(value="负责支付链路重构并提升稳定性", source_fact_ids=["fact-1"])],
        )
    ]
    before = resume.model_dump(mode="json")["work_experience"][0]["bullets"]
    patch = ResumePatch(
        operations=[
            ResumePatchOperation(
                path="/work_experience/0/bullets",
                before=before,
                after=[],
                reason="优化表述突出岗位关键词",
                source_fact_ids=["fact-1"],
            ),
            ResumePatchOperation(
                path="/work_experience/0/bullets",
                before=before,
                after=[{"value": "面向支付链路做重构，提升稳定性", "source_fact_ids": ["fact-1"], "origin": "ai_rewrite", "confidence": 1}],
                reason="润色工作描述",
                source_fact_ids=["fact-1"],
            ),
        ]
    )

    grounded = _ground_patch_operations(patch, resume=resume, facts=[fact])

    assert len(grounded.operations) == 1
    assert "支付链路" in grounded.operations[0].after[0]["value"]


def test_grounding_dedupes_overlapping_and_near_duplicate_ops() -> None:
    fact = Fact(
        id="fact-1",
        category="工作/实习经历",
        statement="负责支付链路重构并提升稳定性",
        source_type="manual",
        user_confirmed=True,
    )
    from resume_mvp.domain import SourcedText, WorkExperienceEntry

    resume = ResumeDocument.blank()
    resume.work_experience = [
        WorkExperienceEntry(
            company="示例",
            title="工程师",
            bullets=[SourcedText(value="负责支付链路重构并提升稳定性", source_fact_ids=["fact-1"])],
        )
    ]
    payload = resume.model_dump(mode="json")
    entry = payload["work_experience"][0]
    bullets = entry["bullets"]
    rewritten = [
        {
            "value": "面向支付链路做重构，提升稳定性",
            "source_fact_ids": ["fact-1"],
            "origin": "ai_rewrite",
            "confidence": 1,
        }
    ]
    patch = ResumePatch(
        operations=[
            ResumePatchOperation(
                path="/work_experience/0",
                before=entry,
                after={**entry, "bullets": rewritten},
                reason="整段润色",
                source_fact_ids=["fact-1"],
            ),
            ResumePatchOperation(
                path="/work_experience/0/bullets",
                before=bullets,
                after=rewritten,
                reason="只改描述",
                source_fact_ids=["fact-1"],
            ),
            ResumePatchOperation(
                path="/work_experience/0/bullets",
                before=bullets,
                after=[
                    {
                        "value": "面向支付链路做重构，提升稳定性。",
                        "source_fact_ids": ["fact-1"],
                        "origin": "ai_rewrite",
                        "confidence": 1,
                    }
                ],
                reason="再次同义改写",
                source_fact_ids=["fact-1"],
            ),
        ]
    )

    grounded = _ground_patch_operations(patch, resume=resume, facts=[fact])

    assert len(grounded.operations) == 1
    assert grounded.operations[0].path == "/work_experience/0/bullets"
