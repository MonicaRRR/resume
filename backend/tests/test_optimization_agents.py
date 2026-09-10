import pytest

from resume_mvp.domain import (
    Fact,
    JobAnalysis,
    JobRequirement,
    MatchItem,
    MatchReport,
    ResumeDocument,
    ResumePatch,
    ResumePatchOperation,
    SourcedText,
)
from resume_mvp.optimization_agents import (
    generate_optimization_patch,
    review_optimization_candidate,
)
from resume_mvp.optimization_models import LayoutIssue, LayoutReport, OptimizationReview


class RecordingProvider:
    def __init__(self, result: object) -> None:
        self.result = result
        self.prompt = ""

    async def complete_json(self, prompt: str, schema: type):
        self.prompt = prompt
        return schema.model_validate(self.result)


def analysis() -> JobAnalysis:
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


def match_report() -> MatchReport:
    return MatchReport(
        coverage=0.5,
        items=[
            MatchItem(
                requirement_id="req-python",
                requirement="Python API 开发",
                status="证据较弱",
                fact_ids=["fact-1"],
                reason="有相关经历但表述偏泛",
                weight=2,
            )
        ],
    )


def facts() -> list[Fact]:
    return [
        Fact(
            id="fact-1",
            category="项目经历",
            statement="用 FastAPI 完成订单服务重构",
            source_type="manual",
            user_confirmed=True,
        )
    ]


def resume() -> ResumeDocument:
    document = ResumeDocument.blank()
    document.basics.summary = SourcedText(
        value="熟悉后端开发",
        source_fact_ids=["fact-1"],
        origin="manual",
    )
    document.basics.email = "private@example.com"
    document.basics.phone = "13800000000"
    document.basics.wechat = "wx-secret"
    document.basics.location = "上海市浦东新区隐秘路 1 号"
    document.basics.photo_data_url = "data:image/png;base64,abc"
    return document


def candidate() -> ResumeDocument:
    return resume()


def short_tail_report(issue_id: str) -> LayoutReport:
    return LayoutReport(
        page_count=1,
        density_by_page=[0.82],
        issues=[
            LayoutIssue(
                id=issue_id,
                kind="short_tail",
                severity="warning",
                message="最后一行宽度不足正文可用宽度的 25%",
                page=1,
                target_path="/basics/summary",
                text_excerpt="熟悉后端开发",
                measured_ratio=0.12,
            )
        ],
    )


def layout_report() -> LayoutReport:
    return short_tail_report("layout-1")


def patch_with_layout_issue(layout_id: str, fact_id: str) -> ResumePatch:
    return ResumePatch(
        operations=[
            ResumePatchOperation(
                path="/basics/summary",
                before={
                    "value": "熟悉后端开发",
                    "source_fact_ids": ["fact-1"],
                    "origin": "manual",
                    "confidence": 1,
                },
                after={
                    "value": "用 FastAPI 完成订单服务重构",
                    "source_fact_ids": [fact_id],
                    "origin": "ai_rewrite",
                    "confidence": 1,
                },
                reason="压缩短尾行并突出 Python API 证据",
                jd_requirement_ids=["req-python"],
                source_fact_ids=[fact_id],
                layout_issue_ids=[layout_id],
                expected_layout_benefit="消除短尾行",
            )
        ]
    )


def passing_review() -> OptimizationReview:
    return OptimizationReview(
        factuality_passed=True,
        expression_score=88,
        requires_user_input=False,
        rejection_reasons=[],
        refinement_instructions=[],
    )


@pytest.mark.anyio
async def test_writer_receives_layout_issue_and_returns_id() -> None:
    provider = RecordingProvider(result=patch_with_layout_issue("layout-1", "fact-1"))
    patch = await generate_optimization_patch(
        provider,
        analysis(),
        match_report(),
        resume(),
        facts(),
        "campus",
        layout_report=short_tail_report("layout-1"),
        previous_review=None,
    )
    assert "最后一行宽度不足" in provider.prompt
    assert patch.operations[0].layout_issue_ids == ["layout-1"]


@pytest.mark.anyio
async def test_writer_drops_unknown_fact_or_layout_ids() -> None:
    provider = RecordingProvider(result=patch_with_layout_issue("fake-layout", "fake-fact"))
    patch = await generate_optimization_patch(
        provider,
        analysis(),
        match_report(),
        resume(),
        facts(),
        "experienced",
        layout_report=short_tail_report("layout-1"),
        previous_review=None,
    )
    assert patch.operations == []


@pytest.mark.anyio
async def test_reviewer_is_told_not_to_rewrite() -> None:
    provider = RecordingProvider(result=passing_review())
    await review_optimization_candidate(
        provider,
        analysis(),
        match_report(),
        candidate(),
        facts(),
        layout_report(),
    )
    assert "不能直接生成替换文本" in provider.prompt
    assert "private@example.com" not in provider.prompt
    assert "13800000000" not in provider.prompt
    assert "wx-secret" not in provider.prompt
    assert "隐秘路" not in provider.prompt
    assert "data:image/png;base64,abc" not in provider.prompt
