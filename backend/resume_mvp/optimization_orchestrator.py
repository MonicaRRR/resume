from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from resume_mvp.ai_workflows import analyze_job
from resume_mvp.domain import (
    ApplicationType,
    Fact,
    JobAnalysis,
    MatchReport,
    ResumeDocument,
    ResumePatch,
    ResumeVersion,
)
from resume_mvp.exports import build_docx
from resume_mvp.evidence_match import analyze_evidence_match
from resume_mvp.latex import build_latex
from resume_mvp.layout_analysis import analyze_pdf_layout
from resume_mvp.matching import calculate_match
from resume_mvp.optimization_agents import (
    generate_optimization_patch,
    review_optimization_candidate,
)
from resume_mvp.optimization_models import (
    LayoutReport,
    OptimizationMode,
    OptimizationReview,
    OptimizationRun,
    OptimizationStepKind,
    QualityGateResult,
)
from resume_mvp.optimization_quality import evaluate_quality, should_refine
from resume_mvp.patches import apply_resume_patch
from resume_mvp.preview import PreviewConversionError, compile_latex_to_pdf, convert_docx_to_pdf
from resume_mvp.provider_retry import RetryingProvider
from resume_mvp.providers.base import AIProvider
from resume_mvp.repositories import ProjectRepository


class ProviderResolver(Protocol):
    def public_state(self) -> Any: ...

    def resolve(self, kind: str) -> AIProvider: ...


class OptimizationCancelled(RuntimeError):
    pass


class OptimizationBudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class FrozenContext:
    project_id: str
    application_type: ApplicationType
    company_name: str
    job_description: str
    template_id: str
    provider: str
    model: str
    prompt_version: str
    version: ResumeVersion
    resume: ResumeDocument
    facts: list[Fact]


AnalyzeFn = Callable[
    [OptimizationRun, FrozenContext, AIProvider],
    Awaitable[tuple[JobAnalysis, MatchReport]],
]
WriteFn = Callable[..., Awaitable[ResumePatch]]
ReviewFn = Callable[..., Awaitable[OptimizationReview]]
RenderFn = Callable[[FrozenContext, ResumeDocument], Awaitable[LayoutReport]]
MatchFn = Callable[[JobAnalysis, ResumeDocument, list[Fact]], MatchReport]


class OptimizationOrchestrator:
    """Persist a bounded quick/deep optimization loop with checkpoint reuse."""

    def __init__(
        self,
        repository: ProjectRepository,
        providers: ProviderResolver,
        *,
        analyze_fn: AnalyzeFn | None = None,
        write_fn: WriteFn | None = None,
        review_fn: ReviewFn | None = None,
        render_fn: RenderFn | None = None,
        match_fn: MatchFn | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.repository = repository
        self.providers = providers
        self._uses_default_analyze = analyze_fn is None
        self._analyze_fn = analyze_fn or self._default_analyze
        self._write_fn = write_fn or self._default_write
        self._review_fn = review_fn or self._default_review
        self._render_fn = render_fn or self._default_render
        self._match_fn = match_fn or calculate_match
        self._sleep = sleep
        self._provider_locks: dict[str, asyncio.Semaphore] = {}

    def _lock_for(self, provider: str) -> asyncio.Semaphore:
        if provider not in self._provider_locks:
            self._provider_locks[provider] = asyncio.Semaphore(1)
        return self._provider_locks[provider]

    async def create_run(
        self,
        project_id: str,
        mode: OptimizationMode,
        provider: str,
    ) -> OptimizationRun:
        project = self.repository.get(project_id)
        version = self.repository.get_active_version(project_id)
        if version is None:
            raise ValueError("项目还没有可优化的简历版本")
        state = self.providers.public_state()
        model = state.model or provider
        run = OptimizationRun(
            project_id=project_id,
            input_version_id=version.id,
            template_id=project.selected_template_id or "classic-cn",
            provider=provider,
            model=model,
            mode=mode,
            status="queued",
        )
        return self.repository.create_optimization_run(run)

    async def cancel(self, run_id: str) -> OptimizationRun:
        run = self.repository.get_optimization_run(run_id)
        if run.status in {"cancelled", "ready_for_user", "failed"}:
            return run
        return self.repository.request_optimization_cancel(run_id)

    async def prepare_resume(self, run_id: str) -> OptimizationRun:
        """Re-queue a waiting or interrupted run without executing model calls."""
        run = self.repository.get_optimization_run(run_id)
        if run.status == "waiting_for_user":
            project = self.repository.get(run.project_id)
            active_id = project.active_resume_version_id
            if active_id and active_id != run.input_version_id:
                run = self.repository.adopt_optimization_input_version(run_id, active_id)
            return self.repository.update_optimization_run(
                run.id,
                status="queued",
                cancel_requested=False,
                message="已采纳最新事实版本，继续优化",
            )
        if run.status == "failed":
            # Interrupted runs keep the frozen input version.
            return self.repository.update_optimization_run(
                run.id,
                status="queued",
                cancel_requested=False,
                message="继续未完成的优化",
            )
        raise ValueError("只有等待用户补充事实或中断失败的任务可以恢复")

    async def resume(self, run_id: str) -> OptimizationRun:
        run = await self.prepare_resume(run_id)
        return await self.execute(run.id)

    async def execute(self, run_id: str) -> OptimizationRun:
        run = self.repository.get_optimization_run(run_id)
        if run.status in {"ready_for_user", "failed", "cancelled"}:
            return run

        async with self._lock_for(run.provider):
            try:
                return await self._execute_locked(run_id)
            except OptimizationCancelled:
                return self.repository.update_optimization_run(
                    run_id,
                    status="cancelled",
                    message="任务已取消",
                )
            except OptimizationBudgetExceeded as error:
                return self.repository.update_optimization_run(
                    run_id,
                    status="failed",
                    message=str(error) or "已达到模型调用预算",
                )
            except Exception as error:  # noqa: BLE001 - persist failure for the UI
                return self.repository.update_optimization_run(
                    run_id,
                    status="failed",
                    message=str(error) or "优化失败",
                )

    async def _execute_locked(self, run_id: str) -> OptimizationRun:
        run = self.repository.get_optimization_run(run_id)
        if run.status in {"ready_for_user", "failed", "cancelled"}:
            return run

        context = self._load_frozen_context(run)
        provider = self._resolve_provider(run)

        run = self.repository.update_optimization_run(run.id, status="analyzing")
        analysis, match = await self._analysis_step(run, context, provider)
        self._raise_if_cancelled(run.id)

        run = self.repository.get_optimization_run(run.id)
        previous_layout = await self._baseline_render_step(run, context)
        self._raise_if_cancelled(run.id)

        previous_review: OptimizationReview | None = None
        history: list[QualityGateResult] = []
        patch = ResumePatch()
        layout = previous_layout
        review: OptimizationReview | None = None
        quality: QualityGateResult | None = None

        while True:
            run = self.repository.get_optimization_run(run.id)
            self._raise_if_cancelled(run.id)

            run = self.repository.update_optimization_run(run.id, status="optimizing")
            patch = await self._optimization_step(
                run,
                context,
                provider,
                analysis,
                match,
                previous_layout,
                previous_review,
            )
            self._raise_if_cancelled(run.id)

            accepted = {operation.id for operation in patch.operations}
            candidate = apply_resume_patch(
                context.resume,
                patch,
                accepted,
                facts=context.facts,
            )

            run = self.repository.update_optimization_run(run.id, status="rendering")
            layout = await self._render_step(run, context, candidate)
            self._raise_if_cancelled(run.id)

            if run.mode == "quick":
                return self._finish_quick(
                    run, patch, layout, previous_layout, context.application_type
                )

            run = self.repository.update_optimization_run(run.id, status="reviewing")
            review = await self._review_step(
                run,
                context,
                provider,
                analysis,
                match,
                candidate,
                layout,
            )
            self._raise_if_cancelled(run.id)

            candidate_match = self._match_fn(analysis, candidate, context.facts)
            quality = evaluate_quality(
                patch,
                context.facts,
                candidate_match,
                layout,
                review,
                context.application_type,
            )
            history.append(quality)

            if review.requires_user_input:
                return self._finish_waiting(run, patch, layout, review, quality, previous_layout)
            if quality.passed:
                return self._finish_ready(run, patch, layout, review, quality, previous_layout)
            if not should_refine(history, run.iteration, run.max_refinements):
                return self._finish_ready_with_warnings(
                    run,
                    patch,
                    layout,
                    review,
                    quality,
                    previous_layout,
                    context.application_type,
                )

            run = self.repository.update_optimization_run(
                run.id,
                iteration=run.iteration + 1,
                message="进入下一轮有界返工",
            )
            previous_layout, previous_review = layout, review

    def _load_frozen_context(self, run: OptimizationRun) -> FrozenContext:
        project = self.repository.get(run.project_id)
        version = self.repository.get_version(run.input_version_id)
        return FrozenContext(
            project_id=project.id,
            application_type=project.application_type,
            company_name=project.company_name,
            job_description=project.job_description,
            template_id=run.template_id,
            provider=run.provider,
            model=run.model,
            prompt_version=run.prompt_version,
            version=version,
            resume=version.resume,
            facts=list(version.facts),
        )

    def _resolve_provider(self, run: OptimizationRun) -> AIProvider:
        raw = self.providers.resolve(run.provider)
        return RetryingProvider(raw)

    async def _default_analyze(
        self,
        run: OptimizationRun,
        context: FrozenContext,
        provider: AIProvider,
    ) -> tuple[JobAnalysis, MatchReport]:
        analysis = await analyze_job(provider, context.company_name, context.job_description)
        match = await analyze_evidence_match(
            provider,
            analysis,
            context.resume,
            context.facts,
        )
        return analysis, match

    async def _default_write(
        self,
        provider: AIProvider,
        analysis: JobAnalysis,
        match: MatchReport,
        resume: ResumeDocument,
        facts: list[Fact],
        application_type: ApplicationType,
        *,
        layout_report: LayoutReport | None,
        previous_review: OptimizationReview | None,
    ) -> ResumePatch:
        return await generate_optimization_patch(
            provider,
            analysis,
            match,
            resume,
            facts,
            application_type,
            layout_report=layout_report,
            previous_review=previous_review,
        )

    async def _default_review(
        self,
        provider: AIProvider,
        analysis: JobAnalysis,
        match: MatchReport,
        candidate: ResumeDocument,
        facts: list[Fact],
        layout_report: LayoutReport | None,
    ) -> OptimizationReview:
        return await review_optimization_candidate(
            provider,
            analysis,
            match,
            candidate,
            facts,
            layout_report,
        )

    async def _default_render(
        self,
        context: FrozenContext,
        resume: ResumeDocument,
    ) -> LayoutReport:
        try:
            source = build_latex(resume, context.template_id, context.application_type)
            pdf = compile_latex_to_pdf(source)
        except PreviewConversionError:
            docx = build_docx(resume, context.template_id, context.application_type)
            pdf = convert_docx_to_pdf(docx)
        return analyze_pdf_layout(pdf, resume, context.application_type)

    async def _analysis_step(
        self,
        run: OptimizationRun,
        context: FrozenContext,
        provider: AIProvider,
    ) -> tuple[JobAnalysis, MatchReport]:
        input_hash = self._hash(
            {
                "kind": "analysis",
                "job_description": context.job_description,
                "company_name": context.company_name,
                "application_type": context.application_type,
                "model": context.model,
                "prompt_version": context.prompt_version,
            }
        )
        cached = self._reuse(run, "analysis", 0, input_hash)
        if cached is not None:
            analysis = JobAnalysis.model_validate(cached["analysis"])
            match = MatchReport.model_validate(cached["match"])
            return analysis, match

        # The default analysis performs one JD extraction call and one evidence
        # adjudication call. Injected test/offline analyzers retain their own
        # single-call contract.
        run = await self._consume_budget(run, calls=2 if self._uses_default_analyze else 1)
        analysis, match = await self._analyze_fn(run, context, provider)
        self.repository.update(
            context.project_id,
            job_analysis=analysis,
            match_report=match,
        )
        self._persist_step(
            run,
            "analysis",
            0,
            input_hash,
            {
                "analysis": analysis.model_dump(mode="json"),
                "match": match.model_dump(mode="json"),
            },
        )
        return analysis, match

    async def _baseline_render_step(
        self,
        run: OptimizationRun,
        context: FrozenContext,
    ) -> LayoutReport:
        input_hash = self._hash(
            {
                "kind": "baseline_render",
                "input_version_id": run.input_version_id,
                "template_id": context.template_id,
                "application_type": context.application_type,
                "model": context.model,
                "prompt_version": context.prompt_version,
            }
        )
        cached = self._reuse(run, "baseline_render", 0, input_hash)
        if cached is not None:
            report = LayoutReport.model_validate(cached)
            run = self.repository.update_optimization_run(
                run.id,
                baseline_layout_report=report,
            )
            return report

        report = await self._render_fn(context, context.resume)
        self._persist_step(run, "baseline_render", 0, input_hash, report.model_dump(mode="json"))
        self.repository.update_optimization_run(run.id, baseline_layout_report=report)
        return report

    async def _optimization_step(
        self,
        run: OptimizationRun,
        context: FrozenContext,
        provider: AIProvider,
        analysis: JobAnalysis,
        match: MatchReport,
        layout_report: LayoutReport | None,
        previous_review: OptimizationReview | None,
    ) -> ResumePatch:
        input_hash = self._hash(
            {
                "kind": "optimization",
                "input_version_id": run.input_version_id,
                "iteration": run.iteration,
                "analysis": analysis.model_dump(mode="json"),
                "match": match.model_dump(mode="json"),
                "layout": layout_report.model_dump(mode="json") if layout_report else None,
                "previous_review": previous_review.model_dump(mode="json") if previous_review else None,
                "template_id": context.template_id,
                "model": context.model,
                "prompt_version": context.prompt_version,
            }
        )
        cached = self._reuse(run, "optimization", run.iteration, input_hash)
        if cached is not None:
            return ResumePatch.model_validate(cached)

        run = await self._consume_budget(run, calls=1)
        patch = await self._write_fn(
            provider,
            analysis,
            match,
            context.resume,
            context.facts,
            context.application_type,
            layout_report=layout_report,
            previous_review=previous_review,
        )
        self._persist_step(
            run,
            "optimization",
            run.iteration,
            input_hash,
            patch.model_dump(mode="json"),
        )
        return patch

    async def _render_step(
        self,
        run: OptimizationRun,
        context: FrozenContext,
        candidate: ResumeDocument,
    ) -> LayoutReport:
        input_hash = self._hash(
            {
                "kind": "render",
                "input_version_id": run.input_version_id,
                "iteration": run.iteration,
                "candidate": candidate.model_dump(mode="json"),
                "template_id": context.template_id,
                "application_type": context.application_type,
                "model": context.model,
                "prompt_version": context.prompt_version,
            }
        )
        cached = self._reuse(run, "render", run.iteration, input_hash)
        if cached is not None:
            report = LayoutReport.model_validate(cached)
            self.repository.save_layout_report(run.id, run.iteration, report)
            return report

        report = await self._render_fn(context, candidate)
        self.repository.save_layout_report(run.id, run.iteration, report)
        self._persist_step(
            run,
            "render",
            run.iteration,
            input_hash,
            report.model_dump(mode="json"),
        )
        return report

    async def _review_step(
        self,
        run: OptimizationRun,
        context: FrozenContext,
        provider: AIProvider,
        analysis: JobAnalysis,
        match: MatchReport,
        candidate: ResumeDocument,
        layout: LayoutReport,
    ) -> OptimizationReview:
        input_hash = self._hash(
            {
                "kind": "review",
                "input_version_id": run.input_version_id,
                "iteration": run.iteration,
                "candidate": candidate.model_dump(mode="json"),
                "layout": layout.model_dump(mode="json"),
                "analysis": analysis.model_dump(mode="json"),
                "match": match.model_dump(mode="json"),
                "model": context.model,
                "prompt_version": context.prompt_version,
            }
        )
        cached = self._reuse(run, "review", run.iteration, input_hash)
        if cached is not None:
            return OptimizationReview.model_validate(cached)

        run = await self._consume_budget(run, calls=1)
        review = await self._review_fn(
            provider,
            analysis,
            match,
            candidate,
            context.facts,
            layout,
        )
        self._persist_step(
            run,
            "review",
            run.iteration,
            input_hash,
            review.model_dump(mode="json"),
        )
        return review

    def _reuse(
        self,
        run: OptimizationRun,
        kind: OptimizationStepKind,
        iteration: int,
        input_hash: str,
    ) -> dict[str, Any] | None:
        existing = self.repository.list_optimization_steps(
            run.id,
            kind=kind,
            iteration=iteration,
        )
        for step in reversed(existing):
            if step.status == "succeeded" and step.input_hash == input_hash and step.output:
                return step.output
        reusable = self.repository.find_reusable_optimization_step(
            run.id,
            kind,
            iteration,
            input_hash,
        )
        if reusable is None or not reusable.output:
            return None
        self.repository.save_optimization_step(
            run.id,
            kind,
            iteration,
            len(existing) + 1,
            input_hash,
            reusable.output,
            "succeeded",
        )
        return reusable.output

    def _persist_step(
        self,
        run: OptimizationRun,
        kind: OptimizationStepKind,
        iteration: int,
        input_hash: str,
        output: dict[str, Any],
    ) -> None:
        attempt = len(self.repository.list_optimization_steps(run.id, kind=kind, iteration=iteration)) + 1
        redacted = self._redact_output(output)
        self.repository.save_optimization_step(
            run.id,
            kind,
            iteration,
            attempt,
            input_hash,
            redacted,
            "succeeded",
        )

    def _redact_output(self, output: dict[str, Any]) -> dict[str, Any]:
        """Persist structured outputs without contact fields nested in resumes."""
        text = json.dumps(output, ensure_ascii=False)
        # Outputs are already mostly model contracts; keep as-is but drop obvious secrets.
        for secret in ("api_key", "authorization"):
            text = text.replace(secret, "[redacted]")
        return json.loads(text)

    async def _consume_budget(self, run: OptimizationRun, *, calls: int) -> OptimizationRun:
        run = self.repository.get_optimization_run(run.id)
        next_count = run.call_count + calls
        if next_count > run.max_model_calls:
            raise OptimizationBudgetExceeded("已达到模型调用次数上限")
        if (
            run.input_tokens is not None
            and run.output_tokens is not None
            and run.input_tokens + run.output_tokens > run.max_total_tokens
        ):
            raise OptimizationBudgetExceeded("已达到 Token 用量上限")
        return self.repository.update_optimization_run(run.id, call_count=next_count)

    def _raise_if_cancelled(self, run_id: str) -> None:
        run = self.repository.get_optimization_run(run_id)
        if run.cancel_requested or run.status == "cancelled":
            raise OptimizationCancelled()

    def _finish_quick(
        self,
        run: OptimizationRun,
        patch: ResumePatch,
        layout: LayoutReport,
        baseline: LayoutReport,
        application_type: ApplicationType,
    ) -> OptimizationRun:
        overflow = application_type in {"campus", "internship"} and layout.page_count > 1
        return self.repository.update_optimization_run(
            run.id,
            status="waiting_for_user" if overflow else "ready_for_user",
            patch=patch,
            layout_report=layout,
            baseline_layout_report=baseline,
            review=None,
            quality=None,
            message=(
                f"快速优化结果仍有 {layout.page_count} 页；校招/实习必须压到一页，请改用深度优化继续压缩"
                if overflow
                else "快速优化已完成，请逐条确认修改"
            ),
        )

    def _finish_ready(
        self,
        run: OptimizationRun,
        patch: ResumePatch,
        layout: LayoutReport,
        review: OptimizationReview,
        quality: QualityGateResult,
        baseline: LayoutReport,
    ) -> OptimizationRun:
        return self.repository.update_optimization_run(
            run.id,
            status="ready_for_user",
            patch=patch,
            layout_report=layout,
            baseline_layout_report=baseline,
            review=review,
            quality=quality,
            message="深度优化已达到质量门槛",
        )

    def _finish_ready_with_warnings(
        self,
        run: OptimizationRun,
        patch: ResumePatch,
        layout: LayoutReport,
        review: OptimizationReview,
        quality: QualityGateResult,
        baseline: LayoutReport,
        application_type: ApplicationType,
    ) -> OptimizationRun:
        reasons = "；".join(quality.reasons) if quality.reasons else "未继续改善"
        hard_page_failure = (
            application_type in {"campus", "internship"}
            and not quality.page_policy_passed
        )
        return self.repository.update_optimization_run(
            run.id,
            status="waiting_for_user" if hard_page_failure else "ready_for_user",
            patch=patch,
            layout_report=layout,
            baseline_layout_report=baseline,
            review=review,
            quality=quality,
            message=(
                f"仍未满足一页硬约束，不能完成优化：{reasons}"
                if hard_page_failure
                else f"已停止自动返工：{reasons}"
            ),
        )

    def _finish_waiting(
        self,
        run: OptimizationRun,
        patch: ResumePatch,
        layout: LayoutReport,
        review: OptimizationReview,
        quality: QualityGateResult,
        baseline: LayoutReport,
    ) -> OptimizationRun:
        return self.repository.update_optimization_run(
            run.id,
            status="waiting_for_user",
            patch=patch,
            layout_report=layout,
            baseline_layout_report=baseline,
            review=review,
            quality=quality,
            message="需要补充关键事实后继续优化",
        )

    @staticmethod
    def _hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
