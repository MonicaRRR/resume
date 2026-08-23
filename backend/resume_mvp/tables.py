from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from resume_mvp.database import Base
from resume_mvp.domain import new_id, utc_now


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str] = mapped_column(String(200), default="")
    job_description: Mapped[str] = mapped_column(Text)
    job_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    active_resume_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    selected_template_id: Mapped[str] = mapped_column(String(50), default="clear-single")
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
