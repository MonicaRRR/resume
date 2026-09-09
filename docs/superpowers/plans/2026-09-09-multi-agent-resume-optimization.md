# Multi-Agent Resume Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为中文简历工作台增加快速/深度双模式的多 Agent 优化闭环，使事实证据、JD 匹配、中文表达与真实模板排版能够被独立生成、检测、审查和有限返工。

**Architecture:** 后端以持久化状态机编排三个逻辑 Agent，将候选简历实际导出为 DOCX、转换为 PDF，再使用 PyMuPDF 检测页数、行宽和分页问题。前端创建并轮询优化任务，最终仍返回现有 `ResumePatch` 供用户逐条确认，候选内容不会自动写入正式简历版本。

**Tech Stack:** Python 3.12、FastAPI、Pydantic 2、SQLAlchemy 2、PyMuPDF、python-docx、LibreOffice；React 19、TypeScript 5、TanStack Query、Zod、Vitest、Pytest、Playwright。

**Spec:** `docs/superpowers/specs/2026-09-09-multi-agent-resume-optimization-design.md`

## Global Constraints

- 产品界面、错误提示、Agent 提示和输出仅使用中文。
- 快速优化是默认模式；深度优化由用户主动选择。
- 全部逻辑 Agent 使用用户当前选择的同一个模型服务。
- 深度模式包含一次初始生成和最多两次返工；连续两轮无改善立即停止。
- 校招和实习简历最终不得超过一页；社招允许自然分页。
- 最后一行宽度不足正文可用宽度 25% 才判定为短尾行。
- 所有 AI 修改必须引用已有事实；修改可追溯率必须为 100%。
- 高权重 JD 要求覆盖率门槛为 80%，综合表达评分门槛为 80 分，严重排版问题必须为 0。
- 用户逐条确认之前，不得创建正式简历版本或覆盖当前简历。
- 429、502、网络错误和超时只重试失败步骤；API Key 和完整简历正文不得写入运行日志。
- 不在本计划中增加账号、云同步、本地 Qwen 或多模型路由。

## File Structure

### Backend

- Create `backend/resume_mvp/optimization_models.py`: optimization, layout, review, and quality contracts.
- Create `backend/resume_mvp/optimization_quality.py`: deterministic gates and stop rules.
- Create `backend/resume_mvp/layout_analysis.py`: actual PDF geometry analysis.
- Create `backend/resume_mvp/provider_retry.py`: bounded retry and usage collection.
- Create `backend/resume_mvp/optimization_agents.py`: layout-aware writer and independent reviewer.
- Create `backend/resume_mvp/optimization_orchestrator.py`: persisted state machine.
- Create `backend/resume_mvp/api/optimization.py`: run lifecycle API.
- Modify `backend/resume_mvp/domain.py`: optional layout evidence on patch operations.
- Modify `backend/resume_mvp/providers/base.py` and `providers/openai_compatible.py`: rate-limit metadata and optional usage.
- Modify `backend/resume_mvp/tables.py` and `repositories.py`: run, step, and layout persistence.
- Modify `backend/resume_mvp/api/dependencies.py` and `main.py`: wire and expose the orchestrator.

### Frontend

- Create `web/src/hooks/useOptimizationRun.ts`: create, poll, cancel, and resume runs.
- Create `web/src/components/OptimizationLauncher.tsx`: quick/deep selection.
- Create `web/src/components/OptimizationProgress.tsx`: progress, budget, wait, error, cancel, and resume states.
- Modify `web/src/types.ts` and `web/src/api/client.ts`: run contracts and API methods.
- Modify `web/src/pages/WorkspacePage.tsx`: task-based optimization flow.
- Modify `web/src/components/PatchReview.tsx`: layout and review evidence.
- Modify `web/src/styles.css`, component tests, and `web/e2e/resume-flow.spec.ts`.

---

### Task 1: Define stable optimization contracts

**Files:**
- Create: `backend/resume_mvp/optimization_models.py`
- Modify: `backend/resume_mvp/domain.py`
- Test: `backend/tests/test_optimization_models.py`

**Interfaces:**
- Consumes: `ResumePatch`, `FollowupQuestion`, `ApplicationType`, `new_id`, `utc_now`.
- Produces: `OptimizationMode`, `OptimizationStatus`, `OptimizationStepKind`, `LayoutIssue`, `LayoutReport`, `OptimizationReview`, `QualityGateResult`, `OptimizationRun`; optional `layout_issue_ids` and `expected_layout_benefit` on `ResumePatchOperation`.

- [ ] **Step 1: Write failing contract tests**

```python
from resume_mvp.domain import ResumePatchOperation
from resume_mvp.optimization_models import LayoutIssue, LayoutReport, OptimizationRun


def test_patch_operation_accepts_optional_layout_evidence() -> None:
    operation = ResumePatchOperation(
        path="/projects/0/bullets", before=[], after=[], reason="消除短尾行",
        source_fact_ids=["fact-1"], layout_issue_ids=["layout-1"],
        expected_layout_benefit="将三字尾行收回上一行",
    )
    assert operation.layout_issue_ids == ["layout-1"]


def test_optimization_run_defaults_to_bounded_loop() -> None:
    run = OptimizationRun(
        project_id="p1", input_version_id="v1", template_id="classic-cn",
        provider="openai-compatible", mode="deep",
    )
    assert (run.status, run.iteration, run.max_refinements) == ("queued", 0, 2)
    assert (run.max_model_calls, run.max_total_tokens) == (12, 120_000)


def test_layout_report_counts_severe_issues() -> None:
    report = LayoutReport(
        page_count=2,
        issues=[LayoutIssue(kind="one_page_overflow", severity="severe", message="超过一页")],
    )
    assert report.severe_issue_count == 1
```

- [ ] **Step 2: Run tests and verify the missing-module failure**

Run: `cd backend && uv run pytest tests/test_optimization_models.py -v`

Expected: FAIL because `resume_mvp.optimization_models` and the new optional operation fields do not exist.

- [ ] **Step 3: Implement the contracts**

```python
# backend/resume_mvp/optimization_models.py
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, computed_field
from resume_mvp.domain import FollowupQuestion, ResumePatch, new_id, utc_now

OptimizationMode = Literal["quick", "deep"]
OptimizationStatus = Literal[
    "queued", "analyzing", "waiting_for_user", "optimizing", "rendering",
    "reviewing", "retry_wait", "ready_for_user", "failed", "cancelled",
]
OptimizationStepKind = Literal["analysis", "baseline_render", "optimization", "render", "review"]

class LayoutIssue(BaseModel):
    id: str = Field(default_factory=new_id)
    kind: Literal["short_tail", "orphan_heading", "awkward_page_break", "sparse_last_page", "one_page_overflow"]
    severity: Literal["info", "warning", "severe"]
    message: str
    page: int = Field(default=1, ge=1)
    target_path: str = ""
    text_excerpt: str = ""
    measured_ratio: float | None = Field(default=None, ge=0)

class LayoutReport(BaseModel):
    page_count: int = Field(default=1, ge=1)
    density_by_page: list[float] = Field(default_factory=list)
    issues: list[LayoutIssue] = Field(default_factory=list)

    @computed_field
    @property
    def severe_issue_count(self) -> int:
        return sum(issue.severity == "severe" for issue in self.issues)

class OptimizationReview(BaseModel):
    factuality_passed: bool
    expression_score: int = Field(ge=0, le=100)
    requires_user_input: bool = False
    questions: list[FollowupQuestion] = Field(default_factory=list)
    rejection_reasons: list[str] = Field(default_factory=list)
    refinement_instructions: list[str] = Field(default_factory=list)

class QualityGateResult(BaseModel):
    passed: bool
    factuality_passed: bool
    traceability: float = Field(ge=0, le=1)
    jd_coverage: float = Field(ge=0, le=1)
    expression_score: int = Field(ge=0, le=100)
    page_policy_passed: bool
    severe_layout_issues: int = Field(ge=0)
    reasons: list[str] = Field(default_factory=list)

class OptimizationRun(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    input_version_id: str
    template_id: str
    provider: str
    model: str = ""
    prompt_version: str = "multi-agent-v1"
    mode: OptimizationMode
    status: OptimizationStatus = "queued"
    iteration: int = Field(default=0, ge=0)
    max_refinements: int = Field(default=2, ge=0, le=2)
    max_model_calls: int = Field(default=12, ge=1, le=12)
    max_total_tokens: int = Field(default=120_000, ge=1)
    call_count: int = Field(default=0, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    patch: ResumePatch | None = None
    baseline_layout_report: LayoutReport | None = None
    layout_report: LayoutReport | None = None
    review: OptimizationReview | None = None
    quality: QualityGateResult | None = None
    message: str = ""
    cancel_requested: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
```

Add to `ResumePatchOperation` with defaults so old patches remain valid:

```python
layout_issue_ids: list[str] = Field(default_factory=list)
expected_layout_benefit: str = ""
```

- [ ] **Step 4: Run contract and domain tests**

Run: `cd backend && uv run pytest tests/test_optimization_models.py tests/test_domain.py -v`

Expected: PASS, including old patch fixtures without layout fields.

- [ ] **Step 5: Commit**

```bash
git add backend/resume_mvp/domain.py backend/resume_mvp/optimization_models.py backend/tests/test_optimization_models.py
git commit -m "feat: define optimization run contracts"
```

### Task 2: Implement deterministic quality gates

**Files:**
- Create: `backend/resume_mvp/optimization_quality.py`
- Test: `backend/tests/test_optimization_quality.py`

**Interfaces:**
- Consumes: `ResumePatch`, facts, candidate `MatchReport`, `LayoutReport`, `OptimizationReview`, `ApplicationType`.
- Produces: `evaluate_quality(...) -> QualityGateResult` and `should_refine(history, iteration, max_refinements) -> bool`.

- [ ] **Step 1: Write failing hard-gate tests**

```python
def test_rejects_untraceable_operation(match_report, review) -> None:
    result = evaluate_quality(ungrounded_patch(), [], match_report, one_page_layout(), review, "campus")
    assert result.passed is False
    assert result.traceability == 0

def test_campus_rejects_two_pages(match_report, facts, grounded_patch, review) -> None:
    result = evaluate_quality(grounded_patch, facts, match_report, LayoutReport(page_count=2), review, "campus")
    assert result.page_policy_passed is False

def test_experienced_allows_two_pages(match_report, facts, grounded_patch, review) -> None:
    result = evaluate_quality(grounded_patch, facts, match_report, LayoutReport(page_count=2), review, "experienced")
    assert result.page_policy_passed is True

def test_stops_after_two_non_improving_refinements() -> None:
    history = [quality(score=72), quality(score=72), quality(score=71)]
    assert should_refine(history, iteration=2, max_refinements=2) is False
```

- [ ] **Step 2: Run tests and verify missing functions**

Run: `cd backend && uv run pytest tests/test_optimization_quality.py -v`

Expected: FAIL because `evaluate_quality` and `should_refine` do not exist.

- [ ] **Step 3: Implement thresholds without model calls**

```python
def evaluate_quality(patch, facts, candidate_match, layout, review, application_type):
    known = {fact.id for fact in facts}
    traceability = 1.0 if not patch.operations else sum(
        bool(op.source_fact_ids) and all(item in known for item in op.source_fact_ids)
        for op in patch.operations
    ) / len(patch.operations)
    jd_coverage = candidate_match.coverage
    page_ok = application_type == "experienced" or layout.page_count <= 1
    factuality = review.factuality_passed and traceability == 1.0
    reasons = []
    if not factuality: reasons.append("存在无事实依据的修改")
    if jd_coverage < 0.8: reasons.append("高权重 JD 覆盖率不足 80%")
    if not page_ok: reasons.append("校招/实习简历超过一页")
    if layout.severe_issue_count: reasons.append("仍存在严重排版问题")
    if review.expression_score < 80: reasons.append("综合表达评分不足 80 分")
    return QualityGateResult(
        passed=not reasons, factuality_passed=factuality, traceability=traceability,
        jd_coverage=jd_coverage, expression_score=review.expression_score,
        page_policy_passed=page_ok, severe_layout_issues=layout.severe_issue_count,
        reasons=reasons,
    )
```

`should_refine` returns false when quality passed, iteration reached 2, or the latest two refinements did not improve `(factuality, page policy, negative severe issue count, JD coverage, expression score)`.

- [ ] **Step 4: Run quality, matching, and patch tests**

Run: `cd backend && uv run pytest tests/test_optimization_quality.py tests/test_matching.py tests/test_patches.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/resume_mvp/optimization_quality.py backend/tests/test_optimization_quality.py
git commit -m "feat: add deterministic optimization quality gates"
```

### Task 3: Analyze real PDF layout

**Files:**
- Create: `backend/resume_mvp/layout_analysis.py`
- Modify: `backend/resume_mvp/preview.py`
- Test: `backend/tests/test_layout_analysis.py`

**Interfaces:**
- Consumes: PDF bytes, candidate `ResumeDocument`, and `ApplicationType`.
- Produces: `analyze_pdf_layout(pdf_bytes, resume, application_type) -> LayoutReport`.

- [ ] **Step 1: Write synthetic PDF geometry tests**

```python
def test_detects_short_tail_on_known_resume_bullet() -> None:
    resume = resume_with_project_bullet("负责接口设计与性能优化，降低响应延迟并完成上线验证")
    pdf = pdf_with_two_lines(
        first="负责接口设计与性能优化，降低响应延迟并完成上线",
        last="验证", first_width=320, last_width=24,
    )
    report = analyze_pdf_layout(pdf, resume, "experienced")
    issue = next(item for item in report.issues if item.kind == "short_tail")
    assert issue.target_path == "/projects/0/bullets/0"
    assert issue.measured_ratio < 0.25

def test_contact_heading_and_date_are_excluded() -> None:
    report = analyze_pdf_layout(
        pdf_with_short_standalone_lines(["张宁", "项目经历", "2026.09"]),
        resume_with_project_bullet("完整项目描述"), "experienced",
    )
    assert all(item.kind != "short_tail" for item in report.issues)

def test_campus_two_page_pdf_is_severe_overflow() -> None:
    report = analyze_pdf_layout(two_page_pdf(), ResumeDocument.blank(), "campus")
    assert any(item.kind == "one_page_overflow" and item.severity == "severe" for item in report.issues)
```

- [ ] **Step 2: Run tests and verify missing module**

Run: `cd backend && uv run pytest tests/test_layout_analysis.py -v`

Expected: FAIL because `layout_analysis.py` does not exist.

- [ ] **Step 3: Implement line extraction and JSON Pointer matching**

Use `fitz.Page.get_text("dict")`. Build a lookup for summary, education highlights, work/project bullets, skills, certificates, awards, and custom sections. Only mapped editable paragraphs with at least two lines participate in short-tail detection.

```python
def analyze_pdf_layout(pdf_bytes, resume, application_type):
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages = [_page_geometry(page) for page in document]
    finally:
        document.close()
    issues = _short_tail_issues(pages, _resume_text_paths(resume), threshold=0.25)
    issues.extend(_orphan_heading_issues(pages))
    issues.extend(_sparse_last_page_issues(pages))
    if application_type in {"campus", "internship"} and len(pages) > 1:
        issues.append(LayoutIssue(
            kind="one_page_overflow", severity="severe", page=2,
            message=f"校招/实习简历实际为 {len(pages)} 页",
        ))
    return LayoutReport(
        page_count=max(1, len(pages)),
        density_by_page=[page.density for page in pages], issues=issues,
    )
```

Compute `measured_ratio = final_line_width / paragraph_available_width`; require `< 0.25`. Exclude names, headings, dates, contact fields, and unmatched standalone lines. Mark a last page with less than 25% vertical content occupancy as `sparse_last_page`.

- [ ] **Step 4: Run layout and preview regressions**

Run: `cd backend && uv run pytest tests/test_layout_analysis.py tests/test_preview.py tests/test_exports.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/resume_mvp/layout_analysis.py backend/resume_mvp/preview.py backend/tests/test_layout_analysis.py
git commit -m "feat: detect resume layout issues from rendered PDF"
```

### Task 4: Persist runs, steps, and layout reports

**Files:**
- Modify: `backend/resume_mvp/tables.py`
- Modify: `backend/resume_mvp/repositories.py`
- Test: `backend/tests/test_optimization_repository.py`

**Interfaces:**
- Consumes: `OptimizationRun`, `OptimizationStepKind`, `LayoutReport`.
- Produces: `create_optimization_run`, `get_optimization_run`, `update_optimization_run`, `save_optimization_step`, `find_reusable_optimization_step`, `list_optimization_steps`, `save_layout_report`, `request_optimization_cancel`.

- [ ] **Step 1: Write failing repository tests**

```python
def test_roundtrips_optimization_run(repository, seeded_project) -> None:
    run = repository.create_optimization_run(make_run(seeded_project.id))
    repository.update_optimization_run(run.id, status="rendering", iteration=1)
    loaded = repository.get_optimization_run(run.id)
    assert (loaded.status, loaded.iteration) == ("rendering", 1)

def test_step_attempts_are_immutable(repository, seeded_run) -> None:
    repository.save_optimization_step(seeded_run.id, "analysis", 0, 1, "hash", {"ok": True}, "succeeded")
    repository.save_optimization_step(seeded_run.id, "analysis", 0, 2, "hash", {"ok": True}, "succeeded")
    assert [step.attempt for step in repository.list_optimization_steps(seeded_run.id)] == [1, 2]

def test_cancel_marks_only_requested_run(repository, two_runs) -> None:
    repository.request_optimization_cancel(two_runs[0].id)
    assert repository.get_optimization_run(two_runs[0].id).cancel_requested is True
    assert repository.get_optimization_run(two_runs[1].id).cancel_requested is False
```

- [ ] **Step 2: Run tests and verify missing persistence**

Run: `cd backend && uv run pytest tests/test_optimization_repository.py -v`

Expected: FAIL because the tables and methods do not exist.

- [ ] **Step 3: Add focused records and atomic mapping methods**

```python
class OptimizationRunRecord(Base):
    __tablename__ = "optimization_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    input_version_id: Mapped[str] = mapped_column(ForeignKey("resume_versions.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

class OptimizationStepRecord(Base):
    __tablename__ = "optimization_steps"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("optimization_runs.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    iteration: Mapped[int] = mapped_column(default=0)
    attempt: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(32))
    input_hash: Mapped[str] = mapped_column(String(64))
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class LayoutReportRecord(Base):
    __tablename__ = "layout_reports"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("optimization_runs.id", ondelete="CASCADE"), index=True)
    iteration: Mapped[int] = mapped_column(default=0)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
```

Keep `status` duplicated as an indexed column and inside validated payload; update both in one transaction. Delete optimization children explicitly in `ProjectRepository.delete` to match existing SQLite behavior.

- [ ] **Step 4: Run persistence regressions**

Run: `cd backend && uv run pytest tests/test_optimization_repository.py tests/test_repositories.py tests/test_health.py -v`

Expected: PASS and a new database includes all three tables.

- [ ] **Step 5: Commit**

```bash
git add backend/resume_mvp/tables.py backend/resume_mvp/repositories.py backend/tests/test_optimization_repository.py
git commit -m "feat: persist optimization loop checkpoints"
```

### Task 5: Add bounded provider retries and optional usage accounting

**Files:**
- Create: `backend/resume_mvp/provider_retry.py`
- Modify: `backend/resume_mvp/providers/base.py`
- Modify: `backend/resume_mvp/providers/openai_compatible.py`
- Test: `backend/tests/test_provider_retry.py`
- Test: `backend/tests/test_openai_provider.py`

**Interfaces:**
- Consumes: any `AIProvider`.
- Produces: `ProviderNetworkError`, `ProviderServerError`, `ProviderRateLimitError`, `ProviderUsage`, `ProviderCallStats`, `RetryPolicy`, `RetryingProvider`.

- [ ] **Step 1: Write failing status and retry tests**

```python
@pytest.mark.anyio
async def test_openai_provider_exposes_retry_after(httpx_mock) -> None:
    httpx_mock.add_response(status_code=429, headers={"Retry-After": "2"})
    provider = OpenAICompatibleProvider(base_url="https://example.test/v1", api_key="x", model="glm")
    with pytest.raises(ProviderRateLimitError) as captured:
        await provider.complete_json("x", ProbeSchema)
    assert captured.value.retry_after_seconds == 2

@pytest.mark.anyio
async def test_retries_only_recoverable_errors() -> None:
    sleep = AsyncMock()
    wrapped = RetryingProvider(FlakyProvider([ProviderRateLimitError("限流", 1), ProbeSchema(ok=True)]), sleep=sleep)
    assert (await wrapped.complete_json("x", ProbeSchema)).ok is True
    sleep.assert_awaited_once_with(1)

@pytest.mark.anyio
async def test_does_not_retry_auth_error() -> None:
    wrapped = RetryingProvider(AlwaysFails(ProviderAuthError("bad key")))
    with pytest.raises(ProviderAuthError):
        await wrapped.complete_json("x", ProbeSchema)
    assert wrapped.stats.call_count == 1
```

- [ ] **Step 2: Run tests and verify 429 is still generic**

Run: `cd backend && uv run pytest tests/test_provider_retry.py tests/test_openai_provider.py -v`

Expected: FAIL because retry contracts do not exist.

- [ ] **Step 3: Implement recoverable classification and injected delay**

```python
class ProviderRateLimitError(ProviderError):
    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds

class ProviderNetworkError(ProviderError):
    pass

class ProviderServerError(ProviderError):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code

class ProviderUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0

class ProviderCallStats(BaseModel):
    call_count: int = 0
    usage: ProviderUsage | None = None

class RetryPolicy(BaseModel):
    max_attempts: int = 3
    base_delay_seconds: float = 1
    max_delay_seconds: float = 30
```

On 429 parse numeric `Retry-After` and raise `ProviderRateLimitError`. Convert `httpx.HTTPError` to `ProviderNetworkError`; on 5xx raise `ProviderServerError` retaining the status. `RetryingProvider` retries only those three exceptions plus `ProviderTimeoutError`; authentication and format failures are immediate except for the existing single JSON-repair call. Inject `sleep` and jitter for deterministic tests. Read `usage.prompt_tokens` and `usage.completion_tokens` when the provider supplies them; keep token fields null for Codex or providers without usage.

- [ ] **Step 4: Run provider regressions**

Run: `cd backend && uv run pytest tests/test_provider_retry.py tests/test_openai_provider.py tests/test_provider_api.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/resume_mvp/providers/base.py backend/resume_mvp/providers/openai_compatible.py backend/resume_mvp/provider_retry.py backend/tests/test_provider_retry.py backend/tests/test_openai_provider.py
git commit -m "feat: add bounded provider retry handling"
```

### Task 6: Implement the layout-aware writer and independent reviewer

**Files:**
- Create: `backend/resume_mvp/optimization_agents.py`
- Modify: `backend/resume_mvp/ai_workflows.py`
- Test: `backend/tests/test_optimization_agents.py`

**Interfaces:**
- Consumes: provider, `JobAnalysis`, `MatchReport`, base resume, facts, application type, optional prior layout/report review.
- Produces: `generate_optimization_patch(...) -> ResumePatch`, `review_optimization_candidate(...) -> OptimizationReview`.

- [ ] **Step 1: Write failing prompt and grounding tests**

```python
@pytest.mark.anyio
async def test_writer_receives_layout_issue_and_returns_id() -> None:
    provider = RecordingProvider(result=patch_with_layout_issue("layout-1", "fact-1"))
    patch = await generate_optimization_patch(
        provider, analysis(), match_report(), resume(), facts(), "campus",
        layout_report=short_tail_report("layout-1"), previous_review=None,
    )
    assert "最后一行宽度不足" in provider.prompt
    assert patch.operations[0].layout_issue_ids == ["layout-1"]

@pytest.mark.anyio
async def test_writer_drops_unknown_fact_or_layout_ids() -> None:
    provider = RecordingProvider(result=patch_with_layout_issue("fake-layout", "fake-fact"))
    patch = await generate_optimization_patch(
        provider, analysis(), match_report(), resume(), facts(), "experienced",
        layout_report=short_tail_report("layout-1"), previous_review=None,
    )
    assert patch.operations == []

@pytest.mark.anyio
async def test_reviewer_is_told_not_to_rewrite() -> None:
    provider = RecordingProvider(result=passing_review())
    await review_optimization_candidate(provider, analysis(), match_report(), candidate(), facts(), layout_report())
    assert "不能直接生成替换文本" in provider.prompt
```

- [ ] **Step 2: Run tests and verify missing functions**

Run: `cd backend && uv run pytest tests/test_optimization_agents.py -v`

Expected: FAIL because `optimization_agents.py` does not exist.

- [ ] **Step 3: Implement minimal-context prompts and two grounding passes**

Reuse `_prompt`, `_complete_with_repair`, `_safe_resume`, `_ground_patch_operations`. Writer constraints must preserve facts, numbers, technology and useful JD terms; prefer deleting low-information wording; forbid meaningless expansion. Drop operations containing unknown layout IDs after existing fact grounding.

```python
async def generate_optimization_patch(provider, analysis, match, resume, facts, application_type, *, layout_report, previous_review):
    prompt = _writer_prompt(analysis, match, resume, facts, application_type, layout_report, previous_review)
    patch = await _complete_with_repair(provider, prompt, ResumePatch)
    grounded = _ground_patch_operations(patch, resume=resume, facts=facts)
    allowed = {item.id for item in (layout_report.issues if layout_report else [])}
    operations = [op for op in grounded.operations if all(item in allowed for item in op.layout_issue_ids)]
    return grounded.model_copy(update={"operations": operations})
```

The reviewer receives no phone, email, WeChat, address, or photo; it returns scores and instructions only, never replacement text.

- [ ] **Step 4: Run Agent and existing workflow tests**

Run: `cd backend && uv run pytest tests/test_optimization_agents.py tests/test_ai_workflows.py tests/test_evidence_match.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/resume_mvp/optimization_agents.py backend/resume_mvp/ai_workflows.py backend/tests/test_optimization_agents.py
git commit -m "feat: add layout-aware resume agents"
```

### Task 7: Build the persisted optimization orchestrator

**Files:**
- Create: `backend/resume_mvp/optimization_orchestrator.py`
- Modify: `backend/resume_mvp/api/dependencies.py`
- Test: `backend/tests/test_optimization_orchestrator.py`

**Interfaces:**
- Consumes: repository checkpoints, provider registry, `build_docx`, `convert_docx_to_pdf`, layout analyzer, Agent functions, quality gates.
- Produces: `OptimizationOrchestrator.create_run(project_id, mode, provider)`, `execute(run_id)`, `cancel(run_id)`, `resume(run_id)`.

- [ ] **Step 1: Write failing state-machine tests**

```python
@pytest.mark.anyio
async def test_deep_run_refines_once_then_is_ready(harness) -> None:
    harness.reviews.extend([review(score=72), review(score=88)])
    run = await harness.orchestrator.create_run(harness.project_id, "deep", "test")
    result = await harness.orchestrator.execute(run.id)
    assert (result.status, result.iteration) == ("ready_for_user", 1)
    assert (harness.writer_calls, harness.renderer_calls, harness.reviewer_calls) == (2, 2, 2)

@pytest.mark.anyio
async def test_quick_run_skips_reviewer(harness) -> None:
    run = await harness.orchestrator.create_run(harness.project_id, "quick", "test")
    result = await harness.orchestrator.execute(run.id)
    assert result.status == "ready_for_user"
    assert harness.reviewer_calls == 0

@pytest.mark.anyio
async def test_waiting_for_user_keeps_completed_steps(harness) -> None:
    harness.reviews.append(review(requires_user_input=True))
    run = await harness.orchestrator.create_run(harness.project_id, "deep", "test")
    result = await harness.orchestrator.execute(run.id)
    assert result.status == "waiting_for_user"
    assert harness.repository.list_optimization_steps(run.id)[0].kind == "analysis"

@pytest.mark.anyio
async def test_resume_adopts_new_fact_version_and_invalidates_only_downstream_steps(harness) -> None:
    waiting = await harness.make_waiting_run()
    new_version = harness.add_confirmed_fact("项目峰值处理 3000 QPS")
    result = await harness.orchestrator.resume(waiting.id)
    assert result.input_version_id == new_version.id
    assert harness.analysis_calls == 1
    assert harness.writer_calls == 2

@pytest.mark.anyio
async def test_cancel_is_observed_between_steps(harness) -> None:
    harness.cancel_after_analysis = True
    run = await harness.orchestrator.create_run(harness.project_id, "deep", "test")
    assert (await harness.orchestrator.execute(run.id)).status == "cancelled"
```

- [ ] **Step 2: Run tests and verify missing orchestrator**

Run: `cd backend && uv run pytest tests/test_optimization_orchestrator.py -v`

Expected: FAIL because `OptimizationOrchestrator` does not exist.

- [ ] **Step 3: Implement explicit transitions and checkpoint reuse**

```python
class OptimizationOrchestrator:
    async def execute(self, run_id: str) -> OptimizationRun:
        run = self.repository.get_optimization_run(run_id)
        if run.status in {"ready_for_user", "failed", "cancelled"}:
            return run
        context = self._load_frozen_context(run)
        analysis, match = await self._analysis_step(run, context)
        previous_layout = await self._baseline_render_step(run, context)
        previous_review = None
        history = []
        while True:
            self._raise_if_cancelled(run.id)
            patch = await self._optimization_step(run, context, analysis, match, previous_layout, previous_review)
            accepted = {op.id for op in patch.operations}
            candidate = apply_resume_patch(context.resume, patch, accepted, facts=context.facts)
            layout = await self._render_step(run, context, candidate)
            if run.mode == "quick":
                return self._finish_quick(run, patch, layout)
            review = await self._review_step(run, context, analysis, match, candidate, layout)
            candidate_match = calculate_match(analysis, candidate, context.facts)
            quality = evaluate_quality(patch, context.facts, candidate_match, layout, review, context.application_type)
            history.append(quality)
            if quality.passed:
                return self._finish_ready(run, patch, layout, review, quality)
            if review.requires_user_input:
                return self._finish_waiting(run, patch, layout, review, quality)
            if not should_refine(history, run.iteration, run.max_refinements):
                return self._finish_ready_with_warnings(run, patch, layout, review, quality)
            run = self.repository.update_optimization_run(run.id, iteration=run.iteration + 1)
            previous_layout, previous_review = layout, review
```

Before the first writer call, render the frozen input resume as `baseline_render`; save it in `baseline_layout_report` and pass its issues to the writer. Each candidate is matched again with `calculate_match(analysis, candidate, facts)`, and that candidate match is passed to `evaluate_quality`. Each step computes an input hash and reuses the latest successful matching checkpoint, including a step from another run with the same resume-version/JD/template/model/prompt-version hash created within 24 hours. Persist `retry_wait` before sleeping, aggregate call/usage stats, and persist only redacted input summaries. Freeze input version, template, provider model, and prompt version at run creation. When a `waiting_for_user` run resumes after `POST /facts` creates a new active version, explicitly adopt that version, retain JD analysis when its hash is unchanged, and invalidate baseline-render/writer/render/review checkpoints whose input hash changed. Enforce `max_model_calls=12` and `max_total_tokens=120000` when usage is available; call count remains the hard fallback for providers without usage. Serialize calls per provider with `asyncio.Semaphore(1)`. `resume` continues the same run; it does not silently create a second run.

Wire it into application services explicitly:

```python
@dataclass(frozen=True)
class AppServices:
    repository: ProjectRepository
    providers: ProviderRegistry
    optimization: OptimizationOrchestrator
```

In `create_app`, construct `repository` and `providers` first, pass both to `OptimizationOrchestrator`, then create `AppServices`. Use a `TYPE_CHECKING` import if required to avoid a runtime import cycle.

- [ ] **Step 4: Run orchestrator, export, and patch tests**

Run: `cd backend && uv run pytest tests/test_optimization_orchestrator.py tests/test_export_api.py tests/test_patches.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/resume_mvp/optimization_orchestrator.py backend/resume_mvp/api/dependencies.py backend/tests/test_optimization_orchestrator.py
git commit -m "feat: orchestrate bounded resume optimization loops"
```

### Task 8: Expose optimization run APIs

**Files:**
- Create: `backend/resume_mvp/api/optimization.py`
- Modify: `backend/resume_mvp/main.py`
- Test: `backend/tests/test_optimization_api.py`

**Interfaces:**
- Consumes: `OptimizationOrchestrator` and repository.
- Produces: create, get, cancel, and resume endpoints under `/api/projects/{project_id}/optimization-runs`.

- [ ] **Step 1: Write failing API lifecycle tests**

```python
def test_create_deep_run_returns_accepted_contract(client, project_id) -> None:
    response = client.post(
        f"/api/projects/{project_id}/optimization-runs",
        json={"mode": "deep", "provider": "test"},
    )
    assert response.status_code == 202
    assert response.json()["mode"] == "deep"

def test_run_cannot_be_read_through_another_project(client, first_project, second_project) -> None:
    run = create_run(client, first_project)
    response = client.get(f"/api/projects/{second_project}/optimization-runs/{run['id']}")
    assert response.status_code == 404

def test_cancel_is_idempotent(client, project_id) -> None:
    run = create_run(client, project_id)
    url = f"/api/projects/{project_id}/optimization-runs/{run['id']}/cancel"
    assert client.post(url).status_code == 200
    assert client.post(url).status_code == 200
```

- [ ] **Step 2: Run tests and verify missing routes**

Run: `cd backend && uv run pytest tests/test_optimization_api.py -v`

Expected: FAIL with 404.

- [ ] **Step 3: Implement routes and background execution**

```python
class OptimizationCreate(BaseModel):
    mode: OptimizationMode = "quick"
    provider: str

@router.post("/{project_id}/optimization-runs", response_model=OptimizationRun, status_code=202)
async def create_run(project_id: str, body: OptimizationCreate, background: BackgroundTasks, services=Depends(get_services)):
    run = await services.optimization.create_run(project_id, body.mode, body.provider)
    background.add_task(services.optimization.execute, run.id)
    return run
```

Add `GET /{run_id}`, `POST /{run_id}/cancel`, and `POST /{run_id}/resume`. Validate project, active version, run ownership, and provider before creation. `resume` may adopt a newer active version only when the run is `waiting_for_user`; for interrupted runs it keeps the original frozen input. On startup, convert stale active states to `failed` with “上次运行被中断，可点击继续”; do not automatically trigger external calls. Preserve `/resume/suggest` as the legacy quick-mode compatibility endpoint.

- [ ] **Step 4: Run API and project journey tests**

Run: `cd backend && uv run pytest tests/test_optimization_api.py tests/test_project_api.py tests/test_health.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/resume_mvp/api/optimization.py backend/resume_mvp/main.py backend/tests/test_optimization_api.py
git commit -m "feat: expose optimization run APIs"
```

### Task 9: Add frontend run schemas, client methods, and polling hook

**Files:**
- Modify: `web/src/types.ts`
- Modify: `web/src/api/client.ts`
- Create: `web/src/hooks/useOptimizationRun.ts`
- Create: `web/src/hooks/useOptimizationRun.test.tsx`

**Interfaces:**
- Consumes: Task 8 endpoints.
- Produces: `OptimizationRunSchema`, `OptimizationRun`, four API methods, `useOptimizationRun(projectId)`.

- [ ] **Step 1: Write a failing polling lifecycle test**

```tsx
test("polls an active run and stops when ready", async () => {
  vi.mocked(api.createOptimizationRun).mockResolvedValue(run({ status: "queued" }));
  vi.mocked(api.getOptimizationRun)
    .mockResolvedValueOnce(run({ status: "reviewing" }))
    .mockResolvedValueOnce(run({ status: "ready_for_user", patch: patch() }));
  const { result } = renderHook(() => useOptimizationRun("project-1"), { wrapper });
  await act(() => result.current.start("deep", "openai-compatible"));
  await waitFor(() => expect(result.current.run?.status).toBe("ready_for_user"));
  expect(api.getOptimizationRun).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run the hook test and verify missing types**

Run: `cd web && pnpm exec vitest run src/hooks/useOptimizationRun.test.tsx`

Expected: FAIL because schemas and hook do not exist.

- [ ] **Step 3: Add exact Zod contracts and terminal-aware polling**

```ts
export const OptimizationModeSchema = z.enum(["quick", "deep"]);
export type OptimizationMode = z.infer<typeof OptimizationModeSchema>;
export const OptimizationStatusSchema = z.enum([
  "queued", "analyzing", "waiting_for_user", "optimizing", "rendering",
  "reviewing", "retry_wait", "ready_for_user", "failed", "cancelled",
]);
export const LayoutIssueSchema = z.object({
  id: z.string(),
  kind: z.enum(["short_tail", "orphan_heading", "awkward_page_break", "sparse_last_page", "one_page_overflow"]),
  severity: z.enum(["info", "warning", "severe"]),
  message: z.string(), page: z.number(), target_path: z.string(), text_excerpt: z.string(),
  measured_ratio: z.number().nullable(),
});
export const LayoutReportSchema = z.object({
  page_count: z.number(), density_by_page: z.array(z.number()),
  issues: z.array(LayoutIssueSchema), severe_issue_count: z.number(),
});
export const OptimizationReviewSchema = z.object({
  factuality_passed: z.boolean(), expression_score: z.number(),
  requires_user_input: z.boolean(), questions: z.array(FollowupQuestionSchema),
  rejection_reasons: z.array(z.string()), refinement_instructions: z.array(z.string()),
});
export const QualityGateResultSchema = z.object({
  passed: z.boolean(), factuality_passed: z.boolean(), traceability: z.number(),
  jd_coverage: z.number(), expression_score: z.number(), page_policy_passed: z.boolean(),
  severe_layout_issues: z.number(), reasons: z.array(z.string()),
});
export const OptimizationRunSchema = z.object({
  id: z.string(), project_id: z.string(), input_version_id: z.string(), template_id: z.string(),
  provider: z.string(), model: z.string().default(""), prompt_version: z.string(),
  mode: OptimizationModeSchema, status: OptimizationStatusSchema, iteration: z.number(),
  max_refinements: z.number(), max_model_calls: z.number(), max_total_tokens: z.number(),
  call_count: z.number(), input_tokens: z.number().nullable(), output_tokens: z.number().nullable(),
  patch: ResumePatchSchema.nullable(), baseline_layout_report: LayoutReportSchema.nullable(),
  layout_report: LayoutReportSchema.nullable(), review: OptimizationReviewSchema.nullable(),
  quality: QualityGateResultSchema.nullable(), message: z.string(), cancel_requested: z.boolean(),
  created_at: z.string(), updated_at: z.string(),
});
export type OptimizationRun = z.infer<typeof OptimizationRunSchema>;

const terminal = new Set(["ready_for_user", "failed", "cancelled", "waiting_for_user"]);

export function useOptimizationRun(projectId: string) {
  const [runId, setRunId] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["optimization-run", projectId, runId],
    queryFn: () => api.getOptimizationRun(projectId, runId!),
    enabled: Boolean(projectId && runId),
    refetchInterval: (query) => terminal.has(query.state.data?.status ?? "") ? false : 1000,
  });
  return {
    run: query.data,
    start: async (mode: OptimizationMode, provider: string) => {
      const created = await api.createOptimizationRun(projectId, mode, provider);
      setRunId(created.id);
      return created;
    },
    cancel: () => runId ? api.cancelOptimizationRun(projectId, runId) : Promise.resolve(),
    resume: () => runId ? api.resumeOptimizationRun(projectId, runId) : Promise.resolve(),
  };
}

// Add these properties inside the existing exported `api` object.
createOptimizationRun: (projectId: string, mode: OptimizationMode, provider: string) => request(
  `/api/projects/${projectId}/optimization-runs`, OptimizationRunSchema,
  json("POST", { mode, provider }),
),
getOptimizationRun: (projectId: string, runId: string) => request(
  `/api/projects/${projectId}/optimization-runs/${runId}`, OptimizationRunSchema,
),
cancelOptimizationRun: (projectId: string, runId: string) => request(
  `/api/projects/${projectId}/optimization-runs/${runId}/cancel`, OptimizationRunSchema, { method: "POST" },
),
resumeOptimizationRun: (projectId: string, runId: string) => request(
  `/api/projects/${projectId}/optimization-runs/${runId}/resume`, OptimizationRunSchema, { method: "POST" },
),
```

Default absent `layout_issue_ids`, `expected_layout_benefit`, review, quality, and usage fields so legacy data parses.

- [ ] **Step 4: Run frontend data tests**

Run: `cd web && pnpm exec vitest run src/hooks/useOptimizationRun.test.tsx src/components/PatchReview.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/types.ts web/src/api/client.ts web/src/hooks/useOptimizationRun.ts web/src/hooks/useOptimizationRun.test.tsx
git commit -m "feat: add optimization run client state"
```

### Task 10: Build dual-mode launcher and progress UI

**Files:**
- Create: `web/src/components/OptimizationLauncher.tsx`
- Create: `web/src/components/OptimizationProgress.tsx`
- Create: `web/src/components/OptimizationLauncher.test.tsx`
- Create: `web/src/components/OptimizationProgress.test.tsx`
- Modify: `web/src/pages/WorkspacePage.tsx`
- Modify: `web/src/pages/WorkspacePage.flow.test.ts`
- Modify: `web/src/styles.css`

**Interfaces:**
- Consumes: `useOptimizationRun`, provider, project, template.
- Produces: mode selection, visible status, cancel/resume, and final `setPatch(run.patch)`.

- [ ] **Step 1: Write failing UI state tests**

```tsx
test("defaults to quick and explains deep mode cost", () => {
  render(<OptimizationLauncher disabled={false} onStart={vi.fn()} />);
  expect(screen.getByRole("radio", { name: /快速优化/ })).toBeChecked();
  expect(screen.getByText(/最多两轮返工/)).toBeInTheDocument();
});

test("shows retry wait without model reasoning", () => {
  render(<OptimizationProgress run={run({ status: "retry_wait", message: "模型限流，稍后重试" })} />);
  expect(screen.getByText("模型限流，稍后重试")).toBeInTheDocument();
  expect(screen.queryByText(/chain of thought|思维链/i)).not.toBeInTheDocument();
});

test("offers resume for interrupted run", () => {
  render(<OptimizationProgress run={run({ status: "failed", message: "上次运行被中断，可点击继续" })} onResume={vi.fn()} />);
  expect(screen.getByRole("button", { name: "继续运行" })).toBeEnabled();
});
```

- [ ] **Step 2: Run tests and verify missing components**

Run: `cd web && pnpm exec vitest run src/components/OptimizationLauncher.test.tsx src/components/OptimizationProgress.test.tsx src/pages/WorkspacePage.flow.test.ts`

Expected: FAIL because the components do not exist.

- [ ] **Step 3: Implement exact stage labels and Workspace integration**

```ts
export const optimizationStageLabels = {
  queued: "等待开始",
  analyzing: "分析事实与岗位",
  waiting_for_user: "等待补充事实",
  optimizing: "生成修改方案",
  rendering: "检查真实模板排版",
  reviewing: "独立质量审查",
  retry_wait: "模型繁忙，等待重试",
  ready_for_user: "可以逐条审阅",
  failed: "优化未完成",
  cancelled: "已取消",
} as const;
```

Replace `suggest()` with `startOptimization(mode)`. Transfer `run.patch` to `PatchReview` only once when ready. Preserve the run summary after transfer. Disable template switching while a run is active because inputs are frozen; re-enable it for all terminal states. Show only structured summaries, not internal reasoning.

- [ ] **Step 4: Run UI flow regressions**

Run: `cd web && pnpm exec vitest run src/components/OptimizationLauncher.test.tsx src/components/OptimizationProgress.test.tsx src/pages/WorkspacePage.flow.test.ts src/app.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/OptimizationLauncher.tsx web/src/components/OptimizationProgress.tsx web/src/components/OptimizationLauncher.test.tsx web/src/components/OptimizationProgress.test.tsx web/src/pages/WorkspacePage.tsx web/src/pages/WorkspacePage.flow.test.ts web/src/styles.css
git commit -m "feat: add quick and deep optimization UI"
```

### Task 11: Show layout evidence and review quality on patch cards

**Files:**
- Modify: `web/src/components/PatchReview.tsx`
- Modify: `web/src/components/PatchReview.test.tsx`
- Modify: `web/src/pages/WorkspacePage.tsx`
- Modify: `web/src/styles.css`

**Interfaces:**
- Consumes: optional `optimization: OptimizationRun` plus operation metadata.
- Produces: visible layout reasons, before/after page and density result, quality summary; acceptance behavior remains unchanged.

- [ ] **Step 1: Write failing evidence and safety tests**

```tsx
test("shows layout benefit without auto-selecting", () => {
  render(<PatchReview patch={layoutPatch()} optimization={passingRun()} onApply={vi.fn()} />);
  expect(screen.getByText("消除 3 字尾行")).toBeInTheDocument();
  expect(screen.getByText(/JD 覆盖 86%/)).toBeInTheDocument();
  expect(screen.getByText(/实际 1 页/)).toBeInTheDocument();
  expect(screen.getByText("0/1 已同意")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /应用已同意/ })).toBeDisabled();
});

test("labels a below-threshold stopped run", () => {
  render(<PatchReview patch={patch()} optimization={runWithWarnings()} onApply={vi.fn()} />);
  expect(screen.getByRole("alert")).toHaveTextContent("已达到自动返工上限");
});
```

- [ ] **Step 2: Run tests and verify missing prop**

Run: `cd web && pnpm exec vitest run src/components/PatchReview.test.tsx`

Expected: FAIL because `optimization` metadata is not rendered.

- [ ] **Step 3: Implement optional evidence blocks**

Add `optimization?: OptimizationRun`. Resolve `layout_issue_ids` against the baseline and final reports. Show `expected_layout_benefit` only when non-empty, and compare `baseline_layout_report` with `layout_report` for page/density changes. Keep `selected` initialized to an empty set; a passing score must never imply user acceptance. Label scores as “本次简历与该 JD 的内部优化指标，不代表录取概率”.

- [ ] **Step 4: Run review and preview tests**

Run: `cd web && pnpm exec vitest run src/components/PatchReview.test.tsx src/pages/WorkspacePage.flow.test.ts src/components/ResumePreview.test.tsx`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/PatchReview.tsx web/src/components/PatchReview.test.tsx web/src/pages/WorkspacePage.tsx web/src/styles.css
git commit -m "feat: explain optimization quality and layout gains"
```

### Task 12: Add evaluation fixtures, end-to-end coverage, and docs

**Files:**
- Create: `backend/tests/fixtures/optimization_eval_cases.json`
- Create: `backend/tests/test_optimization_eval.py`
- Modify: `web/e2e/resume-flow.spec.ts`
- Modify: `README.md`

**Interfaces:**
- Consumes: complete flow.
- Produces: deterministic Chinese quality baselines and operating documentation.

- [ ] **Step 1: Add three fictional evaluation fixtures and a failing parameterized test**

Each `campus`, `internship`, and `experienced` object contains `name`, `application_type`, `job_analysis`, `resume`, `facts`, `candidate_patch`, `candidate_match`, `layout_report`, `review`, and `expected_quality`.

```python
def load_eval_cases() -> list[dict]:
    path = Path(__file__).parent / "fixtures" / "optimization_eval_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))

def evaluate_quality_from_fixture(case: dict) -> QualityGateResult:
    return evaluate_quality(
        ResumePatch.model_validate(case["candidate_patch"]),
        [Fact.model_validate(item) for item in case["facts"]],
        MatchReport.model_validate(case["candidate_match"]),
        LayoutReport.model_validate(case["layout_report"]),
        OptimizationReview.model_validate(case["review"]),
        case["application_type"],
    )

@pytest.mark.parametrize("case", load_eval_cases(), ids=lambda case: case["name"])
def test_optimization_eval_case(case) -> None:
    result = evaluate_quality_from_fixture(case)
    assert result.model_dump(mode="json") == case["expected_quality"]
```

- [ ] **Step 2: Run evaluation tests**

Run: `cd backend && uv run pytest tests/test_optimization_eval.py -v`

Expected: FAIL on the first mismatched expected metric. Change a fixture only if the desired business rule is incorrect; otherwise fix the deterministic calculator.

- [ ] **Step 3: Extend the Playwright journey**

Configure the fixed test provider to return a low first review and a passing second review. The browser journey selects “深度优化”, observes “独立质量审查”, reaches “可以逐条审阅”, confirms no suggestion is preselected, selects one operation, confirms it, and verifies a new version appears.

```ts
test("深度优化经过审查返工后仍由用户确认", async ({ page }) => {
  await createProfileAndProject(page, { applicationType: "campus" });
  await page.getByRole("link", { name: /进入项目/ }).click();
  await page.getByRole("button", { name: "建议确认" }).click();
  await page.getByRole("radio", { name: /深度优化/ }).check();
  await page.getByRole("button", { name: "开始优化" }).click();
  await expect(page.getByText("独立质量审查")).toBeVisible();
  await expect(page.getByText("可以逐条审阅")).toBeVisible();
  await expect(page.getByText(/0\/\d+ 已同意/)).toBeVisible();
  await page.getByRole("button", { name: "同意这项" }).click();
  await page.getByLabel("我同意仅应用已勾选的建议").check();
  await page.getByRole("button", { name: /应用已同意的修改/ }).click();
  await expect(page.getByText("应用 AI 建议")).toBeVisible();
});
```

Run: `make e2e`

Expected: PASS with Chromium installed.

- [ ] **Step 4: Document operating behavior**

Update `README.md` with quick/deep differences; up to three writer calls; LibreOffice requirement; 429 retry, cancellation, checkpoints and interruption recovery; sensitive-field exclusion; scores not being hiring predictions; user confirmation remaining mandatory.

- [ ] **Step 5: Run complete verification**

```bash
make test
make build
make e2e
git diff --check
git status --short
```

Expected: backend and frontend tests pass, production build succeeds, Playwright passes, `git diff --check` has no output, and only intended evaluation/documentation changes remain before commit.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/fixtures/optimization_eval_cases.json backend/tests/test_optimization_eval.py web/e2e/resume-flow.spec.ts README.md
git commit -m "test: verify multi-agent optimization loop"
```

## Execution Checkpoints

- After Task 3: inspect one generated PDF and confirm reported short-tail excerpts match visible lines.
- After Task 7: review the state-machine diff before exposing HTTP endpoints.
- After Task 10: run the local app and verify cancel or refresh never applies a patch.
- After Task 12: compare quick/deep call counts and quality metrics, then record the baseline in the final handoff.
