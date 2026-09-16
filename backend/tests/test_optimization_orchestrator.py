from pathlib import Path
from types import SimpleNamespace

import pytest

from resume_mvp.api.dependencies import ProviderRegistry
from resume_mvp.database import create_database
from resume_mvp.domain import (
    Fact,
    JobAnalysis,
    JobRequirement,
    MatchItem,
    MatchReport,
    ResumeDocument,
    ResumePatch,
    ResumePatchOperation,
    SkillGroup,
    SourcedText,
)
from resume_mvp.optimization_models import LayoutReport, OptimizationReview
from resume_mvp.optimization_orchestrator import OptimizationOrchestrator
from resume_mvp.repositories import ProjectRepository


class StubProvider:
    async def complete_json(self, prompt: str, schema: type):
        raise AssertionError("orchestrator tests must use injected agent hooks")


@pytest.mark.anyio
async def test_default_render_uses_latex_with_selected_template_and_photo(monkeypatch):
    import resume_mvp.optimization_orchestrator as module
    resume = ResumeDocument.blank()
    resume.basics.photo_data_url = 'data:image/png;base64,dGVzdA=='
    context = SimpleNamespace(template_id='overleaf-cn', application_type='campus')
    def build(document, template, application):
        assert document is resume
        assert (template, application) == ('overleaf-cn', 'campus')
        return 'latex-source'
    def compile(source, *, photo_data_url):
        assert source == 'latex-source'
        assert photo_data_url == resume.basics.photo_data_url
        return b'pdf-result'
    def analyze(pdf, document, application):
        assert pdf == b'pdf-result' and document is resume and application == 'campus'
        return passing_layout()
    monkeypatch.setattr(module, 'build_latex', build)
    monkeypatch.setattr(module, 'compile_latex_to_pdf', compile)
    monkeypatch.setattr(module, 'analyze_pdf_layout', analyze)
    result = await OptimizationOrchestrator._default_render(None, context, resume)
    assert result.page_count == 1


def review(*, score: int = 88, requires_user_input: bool = False) -> OptimizationReview:
    return OptimizationReview(
        factuality_passed=True,
        expression_score=score,
        requires_user_input=requires_user_input,
        questions=[],
        rejection_reasons=[] if score >= 80 else ["表达仍偏空泛"],
        refinement_instructions=[] if score >= 80 else ["压缩空话并保留量化结果"],
    )


def passing_layout() -> LayoutReport:
    return LayoutReport(page_count=1, density_by_page=[0.8], issues=[])


def strong_match() -> MatchReport:
    return MatchReport(
        coverage=0.9,
        items=[
            MatchItem(
                requirement_id="req-python",
                requirement="Python API 开发",
                status="已有证据",
                fact_ids=["fact-1"],
                reason="简历已覆盖",
                weight=2,
            )
        ],
    )


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


class OrchestratorHarness:
    def __init__(self, tmp_path: Path) -> None:
        self.repository = ProjectRepository(create_database(tmp_path / "resume.db"))
        profile = ResumeDocument.blank()
        profile.basics.name = "测试用户"
        profile.basics.summary = SourcedText(value="熟悉后端开发", origin="manual")
        profile.skills = [SkillGroup(name="语言", items=[SourcedText(value="Python")])]
        self.repository.save_profile(profile)
        project = self.repository.create(
            title="后端开发",
            company_name="示例科技",
            application_type="campus",
            job_description="负责 Python API 开发",
        )
        version = self.repository.get_active_version(project.id)
        assert version is not None
        fact = Fact(
            id="fact-1",
            category="项目经历",
            statement="用 FastAPI 完成订单服务重构",
            source_type="manual",
            user_confirmed=True,
        )
        resume = version.resume.model_copy(deep=True)
        resume.basics.summary = SourcedText(
            value="熟悉后端开发",
            source_fact_ids=["fact-1"],
            origin="manual",
        )
        saved = self.repository.save_version(
            project.id,
            resume,
            reason="准备优化底稿",
            facts=[fact],
        )
        self.project_id = project.id
        self.input_version_id = saved.id
        self.reviews: list[OptimizationReview] = []
        self.analysis_calls = 0
        self.writer_calls = 0
        self.renderer_calls = 0
        self.reviewer_calls = 0
        self.cancel_after_analysis = False
        self.providers = ProviderRegistry({"test": StubProvider()}, default_test_kind="test")
        self.orchestrator = OptimizationOrchestrator(
            self.repository,
            self.providers,
            analyze_fn=self._analyze,
            write_fn=self._write,
            review_fn=self._review,
            render_fn=self._render,
            match_fn=lambda *_args: strong_match(),
        )

    async def _analyze(self, run, context, provider):
        self.analysis_calls += 1
        if self.cancel_after_analysis:
            self.repository.request_optimization_cancel(run.id)
        return analysis(), strong_match()

    async def _write(
        self,
        provider,
        job_analysis,
        match,
        resume,
        facts,
        application_type,
        *,
        layout_report,
        previous_review,
    ):
        self.writer_calls += 1
        before = resume.basics.summary.model_dump(mode="json")
        return ResumePatch(
            operations=[
                ResumePatchOperation(
                    path="/basics/summary",
                    before=before,
                    after={
                        "value": "用 FastAPI 完成订单服务重构，覆盖 Python API 开发",
                        "source_fact_ids": ["fact-1"],
                        "origin": "ai_rewrite",
                        "confidence": 1,
                    },
                    reason="对齐 JD 并压缩空话",
                    jd_requirement_ids=["req-python"],
                    source_fact_ids=["fact-1"],
                    layout_issue_ids=[],
                    expected_layout_benefit="",
                )
            ]
        )

    async def _review(self, provider, job_analysis, match, candidate, facts, layout_report):
        self.reviewer_calls += 1
        if not self.reviews:
            return review(score=88)
        return self.reviews.pop(0)

    async def _render(self, context, resume):
        # Baseline render uses the frozen input resume; candidate renders differ.
        if resume.basics.summary.value == "熟悉后端开发":
            return passing_layout()
        self.renderer_calls += 1
        return passing_layout()

    async def make_waiting_run(self):
        self.reviews.append(review(requires_user_input=True, score=70))
        run = await self.orchestrator.create_run(self.project_id, "deep", "test")
        return await self.orchestrator.execute(run.id)

    def add_confirmed_fact(self, statement: str):
        version = self.repository.get_active_version(self.project_id)
        assert version is not None
        facts = list(version.facts)
        facts.append(
            Fact(
                category="项目经历",
                statement=statement,
                source_type="manual",
                user_confirmed=True,
            )
        )
        resume = version.resume.model_copy(deep=True)
        return self.repository.save_version(
            self.project_id,
            resume,
            reason="补充事实",
            facts=facts,
        )


@pytest.fixture
def harness(tmp_path: Path) -> OrchestratorHarness:
    return OrchestratorHarness(tmp_path)


@pytest.mark.anyio
async def test_deep_run_refines_once_then_is_ready(harness: OrchestratorHarness) -> None:
    harness.reviews.extend([review(score=72), review(score=88)])
    run = await harness.orchestrator.create_run(harness.project_id, "deep", "test")
    result = await harness.orchestrator.execute(run.id)
    assert (result.status, result.iteration) == ("ready_for_user", 1)
    assert (harness.writer_calls, harness.renderer_calls, harness.reviewer_calls) == (2, 2, 2)


@pytest.mark.anyio
async def test_quick_run_skips_reviewer(harness: OrchestratorHarness) -> None:
    run = await harness.orchestrator.create_run(harness.project_id, "quick", "test")
    result = await harness.orchestrator.execute(run.id)
    assert result.status == "ready_for_user"
    assert harness.reviewer_calls == 0


@pytest.mark.anyio
async def test_waiting_for_user_keeps_completed_steps(harness: OrchestratorHarness) -> None:
    harness.reviews.append(review(requires_user_input=True))
    run = await harness.orchestrator.create_run(harness.project_id, "deep", "test")
    result = await harness.orchestrator.execute(run.id)
    assert result.status == "waiting_for_user"
    assert harness.repository.list_optimization_steps(run.id)[0].kind == "analysis"


@pytest.mark.anyio
async def test_resume_adopts_new_fact_version_and_invalidates_only_downstream_steps(
    harness: OrchestratorHarness,
) -> None:
    waiting = await harness.make_waiting_run()
    new_version = harness.add_confirmed_fact("项目峰值处理 3000 QPS")
    result = await harness.orchestrator.resume(waiting.id)
    assert result.input_version_id == new_version.id
    assert harness.analysis_calls == 1
    assert harness.writer_calls == 2


@pytest.mark.anyio
async def test_cancel_is_observed_between_steps(harness: OrchestratorHarness) -> None:
    harness.cancel_after_analysis = True
    run = await harness.orchestrator.create_run(harness.project_id, "deep", "test")
    assert (await harness.orchestrator.execute(run.id)).status == "cancelled"
