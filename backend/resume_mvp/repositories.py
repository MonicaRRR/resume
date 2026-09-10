from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from resume_mvp.domain import (
    ApplicationType,
    Fact,
    JobAnalysis,
    JobProject,
    MatchReport,
    PracticeSession,
    ResumeDocument,
    ResumeVersion,
    utc_now,
)
from resume_mvp.optimization_models import LayoutReport, OptimizationRun, OptimizationStepKind
from resume_mvp.tables import (
    LayoutReportRecord,
    OptimizationRunRecord,
    OptimizationStepRecord,
    PracticeSessionRecord,
    ProjectRecord,
    ResumeVersionRecord,
    UserProfileRecord,
)
from resume_mvp.profile import facts_from_resume, profile_is_ready


class ProjectNotFoundError(LookupError):
    pass


class VersionNotFoundError(LookupError):
    pass


class PracticeSessionNotFoundError(LookupError):
    pass


class OptimizationRunNotFoundError(LookupError):
    pass


class LayoutReportNotFoundError(LookupError):
    pass


class ProfileRequiredError(ValueError):
    pass


class ProjectRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._sessions = session_factory
        self._clock = clock

    def get_profile(self) -> tuple[ResumeDocument, list[Fact]]:
        with self._sessions() as session:
            record = session.get(UserProfileRecord, "default")
            if record is None or not record.resume:
                return ResumeDocument.blank(), []
            resume = ResumeDocument.model_validate(record.resume)
            facts = [Fact.model_validate(fact) for fact in (record.facts or [])]
            return resume, facts

    def save_profile(self, resume: ResumeDocument) -> tuple[ResumeDocument, list[Fact]]:
        facts = facts_from_resume(resume)
        with self._sessions() as session:
            record = session.get(UserProfileRecord, "default")
            payload = resume.model_dump(mode="json")
            fact_payload = [fact.model_dump(mode="json") for fact in facts]
            if record is None:
                record = UserProfileRecord(id="default", resume=payload, facts=fact_payload)
                session.add(record)
            else:
                record.resume = payload
                record.facts = fact_payload
                record.updated_at = utc_now()
            session.commit()
            return resume, facts

    def create(
        self,
        *,
        title: str,
        company_name: str,
        application_type: ApplicationType,
        job_description: str,
    ) -> JobProject:
        profile_resume, profile_facts = self.get_profile()
        if not profile_is_ready(profile_resume):
            raise ProfileRequiredError("请先完善个人经历库（至少填写姓名，以及教育/工作/项目/技能之一）")

        with self._sessions() as session:
            record = ProjectRecord(
                title=title.strip(),
                company_name=company_name.strip(),
                application_type=application_type,
                job_description=job_description.strip(),
            )
            session.add(record)
            session.flush()
            version = ResumeVersionRecord(
                project_id=record.id,
                resume=profile_resume.model_dump(mode="json"),
                facts=[fact.model_dump(mode="json") for fact in profile_facts],
                reason="从个人经历库创建投递底稿",
            )
            session.add(version)
            session.flush()
            record.active_resume_version_id = version.id
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

    def delete(self, project_id: str) -> None:
        with self._sessions() as session:
            record = session.get(ProjectRecord, project_id)
            if record is None:
                raise ProjectNotFoundError(project_id)
            session.execute(
                delete(PracticeSessionRecord).where(PracticeSessionRecord.project_id == project_id)
            )
            optimization_run_ids = select(OptimizationRunRecord.id).where(
                OptimizationRunRecord.project_id == project_id
            )
            session.execute(
                delete(LayoutReportRecord).where(LayoutReportRecord.run_id.in_(optimization_run_ids))
            )
            session.execute(
                delete(OptimizationStepRecord).where(OptimizationStepRecord.run_id.in_(optimization_run_ids))
            )
            session.execute(
                delete(OptimizationRunRecord).where(OptimizationRunRecord.project_id == project_id)
            )
            session.execute(
                delete(ResumeVersionRecord).where(ResumeVersionRecord.project_id == project_id)
            )
            session.delete(record)
            session.commit()

    def update(
        self,
        project_id: str,
        *,
        title: str | None = None,
        company_name: str | None = None,
        application_type: ApplicationType | None = None,
        job_description: str | None = None,
        job_analysis: JobAnalysis | None = None,
        match_report: MatchReport | None = None,
        selected_template_id: str | None = None,
        clear_match_report: bool = False,
    ) -> JobProject:
        with self._sessions() as session:
            record = session.get(ProjectRecord, project_id)
            if record is None:
                raise ProjectNotFoundError(project_id)
            if title is not None:
                record.title = title.strip()
            if company_name is not None:
                record.company_name = company_name.strip()
            if application_type is not None:
                record.application_type = application_type
            if job_description is not None:
                record.job_description = job_description.strip()
            if job_analysis is not None:
                record.job_analysis = job_analysis.model_dump(mode="json")
            if match_report is not None:
                record.match_report = match_report.model_dump(mode="json")
            if clear_match_report:
                record.match_report = None
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

    def restore_from_profile(self, project_id: str) -> ResumeVersion:
        """Replace the active project draft with a fresh copy of the experience library."""
        self.get(project_id)
        profile_resume, profile_facts = self.get_profile()
        if not profile_is_ready(profile_resume):
            raise ProfileRequiredError("经历库不完整，请先完善后再复原")
        # Deep-copy via dump/validate so later project edits never mutate the library.
        resume = ResumeDocument.model_validate(profile_resume.model_dump(mode="json"))
        facts = [Fact.model_validate(fact.model_dump(mode="json")) for fact in profile_facts]
        return self.save_version(
            project_id,
            resume,
            reason="从经历库一键复原",
            facts=facts,
        )

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

    def create_optimization_run(self, run: OptimizationRun) -> OptimizationRun:
        """Persist a validated, frozen optimization input and return its payload."""
        run_payload = run.model_dump(mode="python") if isinstance(run, OptimizationRun) else run
        validated = OptimizationRun.model_validate(run_payload)
        with self._sessions() as session:
            project = session.get(ProjectRecord, validated.project_id)
            if project is None:
                raise ProjectNotFoundError(validated.project_id)
            version = session.get(ResumeVersionRecord, validated.input_version_id)
            if version is None or version.project_id != validated.project_id:
                raise VersionNotFoundError(validated.input_version_id)
            record = OptimizationRunRecord(
                id=validated.id,
                project_id=validated.project_id,
                input_version_id=validated.input_version_id,
                status=validated.status,
                payload=validated.model_dump(mode="json"),
                updated_at=validated.updated_at,
            )
            session.add(record)
            session.commit()
            return validated

    def get_optimization_run(self, run_id: str) -> OptimizationRun:
        with self._sessions() as session:
            record = session.get(OptimizationRunRecord, run_id)
            if record is None:
                raise OptimizationRunNotFoundError(run_id)
            return self._optimization_run(record)

    def update_optimization_run(self, run_id: str, **changes: Any) -> OptimizationRun:
        """Update the JSON payload and indexed status in one transaction."""
        with self._sessions() as session:
            record = session.get(OptimizationRunRecord, run_id)
            if record is None:
                raise OptimizationRunNotFoundError(run_id)
            current = OptimizationRun.model_validate(record.payload)
            if any(field in changes for field in ("id", "project_id", "input_version_id")):
                raise ValueError("optimization run identity is immutable")
            payload = current.model_dump(mode="python")
            payload.update(changes)
            payload["updated_at"] = self._clock()
            updated = OptimizationRun.model_validate(payload)
            record.status = updated.status
            record.payload = updated.model_dump(mode="json")
            record.updated_at = updated.updated_at
            session.commit()
            return updated

    def adopt_optimization_input_version(self, run_id: str, version_id: str) -> OptimizationRun:
        """Point a waiting run at a newer active resume version after user fact updates."""
        with self._sessions() as session:
            record = session.get(OptimizationRunRecord, run_id)
            if record is None:
                raise OptimizationRunNotFoundError(run_id)
            current = OptimizationRun.model_validate(record.payload)
            if current.status != "waiting_for_user":
                raise ValueError("only waiting runs can adopt a new input version")
            version = session.get(ResumeVersionRecord, version_id)
            if version is None or version.project_id != record.project_id:
                raise VersionNotFoundError(version_id)
            payload = current.model_dump(mode="python")
            payload["input_version_id"] = version_id
            payload["updated_at"] = self._clock()
            updated = OptimizationRun.model_validate(payload)
            record.input_version_id = version_id
            record.status = updated.status
            record.payload = updated.model_dump(mode="json")
            record.updated_at = updated.updated_at
            session.commit()
            return updated

    def save_optimization_step(
        self,
        run_id: str,
        kind: OptimizationStepKind,
        iteration: int,
        attempt: int,
        input_hash: str,
        output: dict | None,
        status: str,
        error_code: str = "",
        *,
        created_at: datetime | None = None,
    ) -> OptimizationStepRecord:
        """Insert an immutable step attempt for an existing run."""
        with self._sessions() as session:
            self._require_optimization_run(session, run_id)
            record = OptimizationStepRecord(
                run_id=run_id,
                kind=kind,
                iteration=iteration,
                attempt=attempt,
                input_hash=input_hash,
                output=output,
                status=status,
                error_code=error_code,
                created_at=created_at or self._clock(),
            )
            session.add(record)
            session.flush()
            session.commit()
            return record

    def find_reusable_optimization_step(
        self,
        run_id: str | None = None,
        kind: OptimizationStepKind | None = None,
        iteration: int | None = None,
        input_hash: str | None = None,
        *,
        project_id: str | None = None,
        now: datetime | None = None,
    ) -> OptimizationStepRecord | None:
        """Find a successful equivalent checkpoint created within the last 24 hours.

        Reuse always requires either a target run or an explicit project scope. A
        checkpoint from another run is eligible only within that same project.
        """
        if (run_id is None) == (project_id is None):
            raise ValueError("target run or project scope is required")
        if not isinstance(kind, str) or not isinstance(iteration, int) or not input_hash:
            raise ValueError("kind, iteration, and input_hash are required")

        current_time = now or self._clock()
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        cutoff = current_time - timedelta(hours=24)
        with self._sessions() as session:
            if run_id is not None:
                run = self._require_optimization_run(session, run_id)
                project_id = run.project_id
            elif session.get(ProjectRecord, project_id) is None:
                raise ProjectNotFoundError(project_id)
            query = (
                select(OptimizationStepRecord)
                .join(
                    OptimizationRunRecord,
                    OptimizationRunRecord.id == OptimizationStepRecord.run_id,
                )
                .where(
                    OptimizationStepRecord.kind == kind,
                    OptimizationStepRecord.iteration == iteration,
                    OptimizationStepRecord.input_hash == input_hash,
                    OptimizationStepRecord.status == "succeeded",
                    OptimizationStepRecord.created_at >= cutoff,
                )
                .order_by(
                    OptimizationStepRecord.created_at.desc(),
                    OptimizationStepRecord.attempt.desc(),
                )
            )
            query = query.where(OptimizationRunRecord.project_id == project_id)
            return session.scalars(query).first()

    def list_optimization_steps(
        self,
        run_id: str,
        *,
        kind: OptimizationStepKind | None = None,
        iteration: int | None = None,
    ) -> list[OptimizationStepRecord]:
        with self._sessions() as session:
            self._require_optimization_run(session, run_id)
            query = select(OptimizationStepRecord).where(
                OptimizationStepRecord.run_id == run_id
            )
            if kind is not None:
                query = query.where(OptimizationStepRecord.kind == kind)
            if iteration is not None:
                query = query.where(OptimizationStepRecord.iteration == iteration)
            query = query.order_by(
                OptimizationStepRecord.iteration.asc(),
                OptimizationStepRecord.kind.asc(),
                OptimizationStepRecord.attempt.asc(),
            )
            return list(session.scalars(query).all())

    def save_layout_report(
        self,
        run_id: str,
        iteration: int,
        report: LayoutReport,
        *,
        created_at: datetime | None = None,
    ) -> LayoutReport:
        report_payload = (
            report.model_dump(mode="python") if isinstance(report, LayoutReport) else report
        )
        validated = LayoutReport.model_validate(report_payload)
        with self._sessions() as session:
            self._require_optimization_run(session, run_id)
            record = session.scalar(
                select(LayoutReportRecord).where(
                    LayoutReportRecord.run_id == run_id,
                    LayoutReportRecord.iteration == iteration,
                )
            )
            if record is None:
                record = LayoutReportRecord(
                    run_id=run_id,
                    iteration=iteration,
                    payload=validated.model_dump(mode="json"),
                    created_at=created_at or self._clock(),
                )
                session.add(record)
            else:
                record.payload = validated.model_dump(mode="json")
                if created_at is not None:
                    record.created_at = created_at
            session.commit()
            return validated

    def get_layout_report(self, run_id: str, iteration: int) -> LayoutReport:
        with self._sessions() as session:
            self._require_optimization_run(session, run_id)
            record = session.scalar(
                select(LayoutReportRecord).where(
                    LayoutReportRecord.run_id == run_id,
                    LayoutReportRecord.iteration == iteration,
                )
            )
            if record is None:
                raise LayoutReportNotFoundError(f"{run_id}:{iteration}")
            return LayoutReport.model_validate(record.payload)

    def request_optimization_cancel(self, run_id: str) -> OptimizationRun:
        return self.update_optimization_run(run_id, cancel_requested=True)

    def fail_stale_optimization_runs(
        self,
        *,
        message: str = "上次运行被中断，可点击继续",
    ) -> list[OptimizationRun]:
        """Mark in-flight runs as failed after process restart; do not call providers."""
        active = (
            "queued",
            "analyzing",
            "optimizing",
            "rendering",
            "reviewing",
            "retry_wait",
        )
        with self._sessions() as session:
            records = list(
                session.scalars(
                    select(OptimizationRunRecord).where(OptimizationRunRecord.status.in_(active))
                ).all()
            )
            updated: list[OptimizationRun] = []
            now = self._clock()
            for record in records:
                current = OptimizationRun.model_validate(record.payload)
                payload = current.model_dump(mode="python")
                payload["status"] = "failed"
                payload["message"] = message
                payload["updated_at"] = now
                failed = OptimizationRun.model_validate(payload)
                record.status = failed.status
                record.payload = failed.model_dump(mode="json")
                record.updated_at = failed.updated_at
                updated.append(failed)
            session.commit()
            return updated

    @staticmethod
    def _require_optimization_run(session: Session, run_id: str) -> OptimizationRunRecord:
        record = session.get(OptimizationRunRecord, run_id)
        if record is None:
            raise OptimizationRunNotFoundError(run_id)
        return record

    @staticmethod
    def _optimization_run(record: OptimizationRunRecord) -> OptimizationRun:
        return OptimizationRun.model_validate(record.payload)

    @staticmethod
    def _project(record: ProjectRecord) -> JobProject:
        return JobProject(
            id=record.id,
            title=record.title,
            company_name=record.company_name,
            application_type=record.application_type,
            job_description=record.job_description,
            job_analysis=JobAnalysis.model_validate(record.job_analysis) if record.job_analysis else None,
            match_report=MatchReport.model_validate(record.match_report) if getattr(record, "match_report", None) else None,
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
