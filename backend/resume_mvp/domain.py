from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


Origin = Literal["upload", "questionnaire", "manual", "ai_rewrite"]
ApplicationType = Literal["campus", "internship", "experienced"]


class SourcedText(BaseModel):
    value: str = ""
    source_fact_ids: list[str] = Field(default_factory=list)
    origin: Origin = "manual"
    confidence: float = Field(default=1.0, ge=0, le=1)

    @model_validator(mode="after")
    def require_sources_for_ai(self) -> SourcedText:
        if self.origin == "ai_rewrite" and not self.source_fact_ids:
            raise ValueError("AI 改写必须包含事实来源")
        return self


class Basics(BaseModel):
    name: str = ""
    gender: str = ""
    birthday: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    wechat: str = ""
    political_status: str = ""
    photo_data_url: str = ""
    target_role: SourcedText = Field(default_factory=SourcedText)
    summary: SourcedText = Field(default_factory=SourcedText)


class EducationEntry(BaseModel):
    id: str = Field(default_factory=new_id)
    institution: str = ""
    degree: str = ""
    field: str = ""
    start_date: str = ""
    end_date: str = ""
    highlights: list[SourcedText] = Field(default_factory=list)


class WorkExperienceEntry(BaseModel):
    id: str = Field(default_factory=new_id)
    company: str = ""
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    bullets: list[SourcedText] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str = ""
    bullets: list[SourcedText] = Field(default_factory=list)


class SkillGroup(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str = "技能"
    items: list[SourcedText] = Field(default_factory=list)


class NamedEntry(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str = ""
    detail: SourcedText = Field(default_factory=SourcedText)
    date: str = ""


class CustomSection(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    items: list[SourcedText] = Field(default_factory=list)


class LayoutProfile(BaseModel):
    source_kind: Literal["builtin", "docx", "pdf", "txt"] = "builtin"
    font_family: str = ""
    heading_font_family: str = ""
    accent_color: str = ""
    base_font_size: float | None = None
    line_height: float | None = None
    columns: int = Field(default=1, ge=1, le=2)
    imported: bool = False


class ResumeDocument(BaseModel):
    basics: Basics = Field(default_factory=Basics)
    education: list[EducationEntry] = Field(default_factory=list)
    work_experience: list[WorkExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    skills: list[SkillGroup] = Field(default_factory=list)
    certificates: list[NamedEntry] = Field(default_factory=list)
    awards: list[NamedEntry] = Field(default_factory=list)
    custom_sections: list[CustomSection] = Field(default_factory=list)
    section_order: list[str] = Field(
        default_factory=lambda: [
            "basics",
            "education",
            "skills",
            "work_experience",
            "projects",
        ]
    )
    layout_profile: LayoutProfile = Field(default_factory=LayoutProfile)

    @model_validator(mode="after")
    def migrate_legacy_default_section_order(self) -> ResumeDocument:
        """Upgrade known legacy defaults so existing libraries pick up the new layout."""
        legacy_orders = {
            ("basics", "work_experience", "projects", "education", "skills"),
            ("basics", "education", "work_experience", "projects", "skills"),
            (
                "basics",
                "education",
                "work_experience",
                "projects",
                "skills",
                "certificates",
                "awards",
                "custom_sections",
            ),
            (
                "basics",
                "work_experience",
                "projects",
                "education",
                "skills",
                "certificates",
                "awards",
                "custom_sections",
            ),
        }
        if tuple(self.section_order) in legacy_orders:
            extras = [name for name in self.section_order if name not in {
                "basics", "education", "skills", "work_experience", "projects",
            }]
            self.section_order = [
                "basics",
                "education",
                "skills",
                "work_experience",
                "projects",
                *extras,
            ]
        return self

    @classmethod
    def blank(cls) -> ResumeDocument:
        return cls()


class Fact(BaseModel):
    id: str = Field(default_factory=new_id)
    category: str
    statement: str
    source_type: Literal["upload", "questionnaire", "manual"]
    source_location: str = ""
    user_confirmed: bool = False


class JobRequirement(BaseModel):
    id: str = Field(default_factory=new_id)
    text: str
    evidence_quote: str
    weight: float = Field(default=1.0, gt=0)
    inferred: bool = False


class JobAnalysis(BaseModel):
    role_title: str = ""
    seniority: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[JobRequirement] = Field(default_factory=list)
    bonus_skills: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    interview_topics: list[str] = Field(default_factory=list)
    written_topics: list[str] = Field(default_factory=list)


class MatchItem(BaseModel):
    requirement_id: str
    requirement: str
    status: Literal["已有证据", "证据较弱", "没有证据", "软性要求"]
    fact_ids: list[str] = Field(default_factory=list)
    excerpts: list[str] = Field(default_factory=list)
    reason: str = ""
    weight: float = 1.0


class MatchReport(BaseModel):
    coverage: float = Field(ge=0, le=1)
    items: list[MatchItem] = Field(default_factory=list)


class ResumePatchOperation(BaseModel):
    id: str = Field(default_factory=new_id)
    op: Literal["replace", "reorder"] = "replace"
    path: str
    before: Any
    after: Any
    reason: str
    jd_requirement_ids: list[str] = Field(default_factory=list)
    source_fact_ids: list[str] = Field(default_factory=list)
    layout_issue_ids: list[str] = Field(default_factory=list)
    expected_layout_benefit: str = ""
    risk: Literal["low", "medium", "high"] = "low"


class ExperienceAsk(BaseModel):
    """Soft prompt when inventory looks thin for the JD—helps user recall more projects."""

    id: str = Field(default_factory=new_id)
    question: str
    guidance: str = ""
    topic: str = "相关项目补充"
    jd_keywords: list[str] = Field(default_factory=list)


class ResumePatch(BaseModel):
    operations: list[ResumePatchOperation] = Field(default_factory=list)
    experience_asks: list[ExperienceAsk] = Field(default_factory=list)


class PatchDiscussionResult(BaseModel):
    """AI discussion about one patch item; draft applies only after user confirms."""

    reply: str
    proposes_change: bool = False
    draft_operation: ResumePatchOperation | None = None


class FollowupQuestion(BaseModel):
    id: str = Field(default_factory=new_id)
    question: str
    topic: str
    requirement_id: str = ""
    rationale: str = ""
    guidance: str = ""
    skippable: bool = True


class QuestionList(BaseModel):
    items: list[FollowupQuestion] = Field(default_factory=list)


class PracticeQuestion(BaseModel):
    id: str = Field(default_factory=new_id)
    category: str
    prompt: str
    hint: str = ""
    explanation: str | None = None
    requirement_ids: list[str] = Field(default_factory=list)
    fact_ids: list[str] = Field(default_factory=list)
    answer_points: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    follow_up: str = ""


class PracticeQuestionList(BaseModel):
    items: list[PracticeQuestion] = Field(default_factory=list)


class PracticeFeedback(BaseModel):
    dimensions: dict[str, str] = Field(default_factory=dict)
    summary: str
    improved_answer: str = ""
    weaknesses: list[str] = Field(default_factory=list)
    percentage_score: None = None


class PracticeEvaluation(BaseModel):
    feedback: PracticeFeedback
    explanation: str = ""
    follow_up: str = ""
    next_question: PracticeQuestion | None = None


class PracticeTurn(BaseModel):
    id: str = Field(default_factory=new_id)
    question: PracticeQuestion
    answer: str
    feedback: PracticeFeedback
    explanation: str = ""
    follow_up: str = ""
    answered_at: datetime = Field(default_factory=utc_now)


class PracticeSession(BaseModel):
    id: str = Field(default_factory=new_id)
    project_id: str
    kind: Literal["interview", "written"]
    status: Literal["active", "completed"] = "active"
    current_question: PracticeQuestion | None = None
    turns: list[PracticeTurn] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    question_set_id: str | None = None
    pending_questions: list[PracticeQuestion] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


QuestionSetSource = Literal["fixed", "rules", "ai", "mixed"]


class QuestionSet(BaseModel):
    """Reusable practice configuration; it contains no candidate answers."""

    id: str = Field(default_factory=new_id)
    project_id: str | None = None
    title: str = Field(default="", max_length=200)
    name: str = Field(default="", max_length=200)
    description: str = ""
    kind: Literal["interview", "written"] = "interview"
    source: QuestionSetSource = "fixed"
    questions: list[PracticeQuestion] = Field(default_factory=list)
    rules: dict[str, Any] = Field(default_factory=dict)
    question_count: int = Field(default=5, ge=1, le=50)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def synchronize_title(self) -> QuestionSet:
        label = (self.title or self.name).strip()
        if not label:
            raise ValueError("题集标题不能为空")
        self.title = label
        self.name = label
        return self


TimelineEventType = Literal[
    "project_created",
    "resume_version",
    "optimization_run",
    "practice_session",
]


class TimelineEvent(BaseModel):
    """A deliberately small, privacy-safe projection of project activity."""

    id: str
    type: TimelineEventType
    title: str
    occurred_at: datetime
    status: str = ""
    resource_id: str = ""
    summary: str = ""


class ProjectTimeline(BaseModel):
    project_id: str
    events: list[TimelineEvent] = Field(default_factory=list)


class ResumeVersion(BaseModel):
    id: str
    project_id: str
    resume: ResumeDocument
    facts: list[Fact] = Field(default_factory=list)
    reason: str
    created_at: datetime


class JobProject(BaseModel):
    id: str
    title: str
    company_name: str = ""
    application_type: ApplicationType = "experienced"
    job_description: str
    job_analysis: JobAnalysis | None = None
    match_report: MatchReport | None = None
    active_resume_version_id: str | None = None
    selected_template_id: str = "classic-cn"
    created_at: datetime
    updated_at: datetime
