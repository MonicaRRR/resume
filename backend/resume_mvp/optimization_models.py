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
    kind: Literal[
        "short_tail", "orphan_heading", "awkward_page_break", "sparse_last_page",
        "one_page_overflow",
    ]
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
