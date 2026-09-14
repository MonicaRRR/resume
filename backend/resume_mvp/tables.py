from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from resume_mvp.database import Base
from resume_mvp.domain import new_id, utc_now


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str] = mapped_column(String(200), default="")
    application_type: Mapped[str] = mapped_column(String(20), default="experienced")
    job_description: Mapped[str] = mapped_column(Text)
    job_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    match_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    active_resume_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    selected_template_id: Mapped[str] = mapped_column(String(50), default="classic-cn")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ResumeVersionRecord(Base):
    __tablename__ = "resume_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    resume: Mapped[dict] = mapped_column(JSON)
    facts: Mapped[list] = mapped_column(JSON, default=list)
    reason: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class PracticeSessionRecord(Base):
    __tablename__ = "practice_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class UserProfileRecord(Base):
    __tablename__ = "user_profile"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="default")
    resume: Mapped[dict] = mapped_column(JSON, default=dict)
    facts: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class OptimizationRunRecord(Base):
    """The indexed projection and validated payload for one optimization run."""

    __tablename__ = "optimization_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    input_version_id: Mapped[str] = mapped_column(
        ForeignKey("resume_versions.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class OptimizationStepRecord(Base):
    """An immutable attempt at one optimization step."""

    __tablename__ = "optimization_steps"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "kind", "iteration", "attempt",
            name="uq_optimization_step_attempt",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("optimization_runs.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))
    iteration: Mapped[int] = mapped_column(default=0)
    attempt: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(32))
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LayoutReportRecord(Base):
    __tablename__ = "layout_reports"
    __table_args__ = (
        UniqueConstraint("run_id", "iteration", name="uq_layout_report_run_iteration"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("optimization_runs.id", ondelete="CASCADE"), index=True
    )
    iteration: Mapped[int] = mapped_column(default=0)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
