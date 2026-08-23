from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from resume_mvp.domain import (
    Fact,
    JobAnalysis,
    JobProject,
    PracticeSession,
    ResumeDocument,
    ResumeVersion,
    utc_now,
)
from resume_mvp.tables import PracticeSessionRecord, ProjectRecord, ResumeVersionRecord


class ProjectNotFoundError(LookupError):
    pass


class VersionNotFoundError(LookupError):
    pass


class PracticeSessionNotFoundError(LookupError):
    pass


class ProjectRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def create(self, *, title: str, company_name: str, job_description: str) -> JobProject:
        with self._sessions() as session:
            record = ProjectRecord(
                title=title.strip(),
                company_name=company_name.strip(),
                job_description=job_description.strip(),
            )
            session.add(record)
            session.commit()
            return self._project(record)

    def list(self) -> list[JobProject]:
        with self._sessions() as session:
            records = session.scalars(
                select(ProjectRecord).order_by(ProjectRecord.updated_at.desc())
            ).all()
            return [self._project(record) for record in records]

    def get(self, project_id: str) -> JobProject:
        with self._sessions() as session:
            record = session.get(ProjectRecord, project_id)
            if record is None:
                raise ProjectNotFoundError(project_id)
            return self._project(record)

    def update(
        self,
        project_id: str,
        *,
        title: str | None = None,
        company_name: str | None = None,
        job_description: str | None = None,
        job_analysis: JobAnalysis | None = None,
        selected_template_id: str | None = None,
    ) -> JobProject:
        with self._sessions() as session:
            record = session.get(ProjectRecord, project_id)
            if record is None:
                raise ProjectNotFoundError(project_id)
            if title is not None:
                record.title = title.strip()
            if company_name is not None:
                record.company_name = company_name.strip()
            if job_description is not None:
                record.job_description = job_description.strip()
            if job_analysis is not None:
                record.job_analysis = job_analysis.model_dump(mode="json")
            if selected_template_id is not None:
                record.selected_template_id = selected_template_id
            record.updated_at = utc_now()
            session.commit()
            return self._project(record)

    def save_version(
        self,
        project_id: str,
        resume: ResumeDocument,
        *,
        reason: str,
        facts: Iterable[Fact] = (),
    ) -> ResumeVersion:
        with self._sessions() as session:
            project = session.get(ProjectRecord, project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            version = ResumeVersionRecord(
                project_id=project_id,
                resume=resume.model_dump(mode="json"),
                facts=[fact.model_dump(mode="json") for fact in facts],
                reason=reason,
            )
            session.add(version)
            session.flush()
            project.active_resume_version_id = version.id
            project.updated_at = utc_now()
            session.commit()
            return self._version(version)

    def list_versions(self, project_id: str) -> list[ResumeVersion]:
        self.get(project_id)
        with self._sessions() as session:
            records = session.scalars(
                select(ResumeVersionRecord)
                .where(ResumeVersionRecord.project_id == project_id)
                .order_by(ResumeVersionRecord.created_at.desc())
            ).all()
            return [self._version(record) for record in records]

    def get_version(self, version_id: str) -> ResumeVersion:
        with self._sessions() as session:
            record = session.get(ResumeVersionRecord, version_id)
            if record is None:
                raise VersionNotFoundError(version_id)
            return self._version(record)

    def get_active_version(self, project_id: str) -> ResumeVersion | None:
        project = self.get(project_id)
        if project.active_resume_version_id is None:
            return None
        return self.get_version(project.active_resume_version_id)

    def activate_version(self, project_id: str, version_id: str) -> JobProject:
        with self._sessions() as session:
            project = session.get(ProjectRecord, project_id)
            version = session.get(ResumeVersionRecord, version_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            if version is None or version.project_id != project_id:
                raise VersionNotFoundError(version_id)
            project.active_resume_version_id = version.id
            project.updated_at = utc_now()
            session.commit()
            return self._project(project)

    def save_practice(self, practice: PracticeSession) -> PracticeSession:
        with self._sessions() as session:
            project = session.get(ProjectRecord, practice.project_id)
            if project is None:
                raise ProjectNotFoundError(practice.project_id)
            record = session.get(PracticeSessionRecord, practice.id)
            if record is None:
                record = PracticeSessionRecord(
                    id=practice.id,
                    project_id=practice.project_id,
                    payload=practice.model_dump(mode="json"),
                    updated_at=practice.updated_at,
                )
                session.add(record)
            else:
                record.payload = practice.model_dump(mode="json")
                record.updated_at = practice.updated_at
            session.commit()
            return practice

    def get_practice(self, session_id: str) -> PracticeSession:
        with self._sessions() as session:
            record = session.get(PracticeSessionRecord, session_id)
            if record is None:
                raise PracticeSessionNotFoundError(session_id)
            return PracticeSession.model_validate(record.payload)

    @staticmethod
    def _project(record: ProjectRecord) -> JobProject:
        return JobProject(
            id=record.id,
            title=record.title,
            company_name=record.company_name,
            job_description=record.job_description,
            job_analysis=JobAnalysis.model_validate(record.job_analysis) if record.job_analysis else None,
            active_resume_version_id=record.active_resume_version_id,
            selected_template_id=record.selected_template_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _version(record: ResumeVersionRecord) -> ResumeVersion:
        return ResumeVersion(
            id=record.id,
            project_id=record.project_id,
            resume=ResumeDocument.model_validate(record.resume),
            facts=[Fact.model_validate(fact) for fact in record.facts],
            reason=record.reason,
            created_at=record.created_at,
        )
