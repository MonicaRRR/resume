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
    email: str = ""
    phone: str = ""
    location: str = ""
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
            "work_experience",
            "projects",
            "education",
            "skills",
        ]
    )
    layout_profile: LayoutProfile = Field(default_factory=LayoutProfile)

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


class ResumePatchOperation(BaseModel):
    id: str = Field(default_factory=new_id)
    op: Literal["replace", "reorder"] = "replace"
    path: str
    before: Any
    after: Any
    reason: str
    jd_requirement_ids: list[str] = Field(default_factory=list)
    source_fact_ids: list[str] = Field(default_factory=list)
    risk: Literal["low", "medium", "high"] = "low"


class ResumePatch(BaseModel):
    operations: list[ResumePatchOperation] = Field(default_factory=list)


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
    job_description: str
    job_analysis: JobAnalysis | None = None
    active_resume_version_id: str | None = None
    selected_template_id: str = "clear-single"
    created_at: datetime
    updated_at: datetime
