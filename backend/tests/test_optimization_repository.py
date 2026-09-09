from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from resume_mvp.database import create_database
from resume_mvp.domain import ResumeDocument, SkillGroup, SourcedText
from resume_mvp.optimization_models import LayoutIssue, LayoutReport, OptimizationRun
from resume_mvp.repositories import ProjectRepository
from resume_mvp.tables import LayoutReportRecord, OptimizationRunRecord, OptimizationStepRecord


@pytest.fixture
def repository(tmp_path: Path) -> ProjectRepository:
    repo = ProjectRepository(create_database(tmp_path / "resume.db"))
    profile = ResumeDocument.blank()
    profile.basics.name = "测试用户"
    profile.skills = [SkillGroup(category="语言", items=[SourcedText(value="Python")])]
    repo.save_profile(profile)
    return repo


@pytest.fixture
def seeded_project(repository: ProjectRepository):
    return repository.create(
        title="后端开发",
        company_name="示例科技",
        application_type="experienced",
        job_description="负责 API 开发",
    )


def make_run(project_id: str, *, status: str = "queued") -> OptimizationRun:
    return OptimizationRun(
        project_id=project_id,
        input_version_id="version-1",
        template_id="classic-cn",
        provider="test-provider",
        mode="deep",
        status=status,
    )


def test_roundtrips_optimization_run(repository: ProjectRepository, seeded_project) -> None:
    run = make_run(seeded_project.id)
    run.input_version_id = seeded_project.active_resume_version_id

    created = repository.create_optimization_run(run)
    updated = repository.update_optimization_run(created.id, status="rendering", iteration=1)
    loaded = repository.get_optimization_run(run.id)

    assert (created.id, updated.status, loaded.status, loaded.iteration) == (
        run.id,
        "rendering",
        "rendering",
        1,
    )

    with repository._sessions() as session:
        record = session.get(OptimizationRunRecord, run.id)
        assert record is not None
        assert record.status == record.payload["status"] == "rendering"


def test_step_attempts_are_immutable(repository: ProjectRepository, seeded_project) -> None:
    run = make_run(seeded_project.id)
    run.input_version_id = seeded_project.active_resume_version_id
    seeded_run = repository.create_optimization_run(run)

    first = repository.save_optimization_step(
        seeded_run.id, "analysis", 0, 1, "hash", {"ok": True}, "succeeded"
    )
    second = repository.save_optimization_step(
        seeded_run.id, "analysis", 0, 2, "hash", {"ok": True}, "succeeded"
    )

    assert first.attempt == 1
    assert second.attempt == 2
    assert [step.attempt for step in repository.list_optimization_steps(seeded_run.id)] == [1, 2]

    with repository._sessions() as session:
        assert session.query(OptimizationStepRecord).count() == 2


def test_reuses_successful_equivalent_checkpoint_for_24_hours(repository: ProjectRepository, seeded_project) -> None:
    first = make_run(seeded_project.id)
    first.input_version_id = seeded_project.active_resume_version_id
    source = repository.create_optimization_run(first)
    second = make_run(seeded_project.id)
    second.input_version_id = seeded_project.active_resume_version_id
    target = repository.create_optimization_run(second)
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)

    repository.save_optimization_step(
        source.id,
        "analysis",
        0,
        1,
        "same-input",
        {"summary": "cached"},
        "succeeded",
        created_at=now - timedelta(hours=23),
    )
    reusable = repository.find_reusable_optimization_step(
        target.id, "analysis", 0, "same-input", now=now
    )

    assert reusable is not None
    assert reusable.run_id == source.id
    assert reusable.output == {"summary": "cached"}


@pytest.mark.parametrize(
    ("status", "age", "input_hash"),
    [
        ("succeeded", timedelta(hours=24, seconds=1), "same-input"),
        ("failed", timedelta(hours=1), "same-input"),
        ("succeeded", timedelta(hours=1), "different-input"),
    ],
)
def test_does_not_reuse_expired_failed_or_mismatched_checkpoint(
    repository: ProjectRepository,
    seeded_project,
    status: str,
    age: timedelta,
    input_hash: str,
) -> None:
    source = make_run(seeded_project.id)
    source.input_version_id = seeded_project.active_resume_version_id
    source_run = repository.create_optimization_run(source)
    target = make_run(seeded_project.id)
    target.input_version_id = seeded_project.active_resume_version_id
    target_run = repository.create_optimization_run(target)
    now = datetime(2026, 9, 10, 12, tzinfo=timezone.utc)
    repository.save_optimization_step(
        source_run.id,
        "analysis",
        0,
        1,
        input_hash,
        {"summary": "cached"},
        status,
        created_at=now - age,
    )

    assert repository.find_reusable_optimization_step(
        target_run.id, "analysis", 0, "same-input", now=now
    ) is None


def test_layout_report_roundtrips_by_run_and_iteration(
    repository: ProjectRepository, seeded_project
) -> None:
    run = make_run(seeded_project.id)
    run.input_version_id = seeded_project.active_resume_version_id
    seeded_run = repository.create_optimization_run(run)
    report = LayoutReport(
        page_count=2,
        density_by_page=[0.82, 0.31],
        issues=[LayoutIssue(kind="short_tail", severity="warning", message="尾行过短")],
    )

    saved = repository.save_layout_report(seeded_run.id, 1, report)
    loaded = repository.get_layout_report(seeded_run.id, 1)

    assert saved == report
    assert loaded == report
    with repository._sessions() as session:
        record = session.scalar(
            select(LayoutReportRecord).where(
                LayoutReportRecord.run_id == seeded_run.id,
                LayoutReportRecord.iteration == 1,
            )
        )
        assert record is not None
        assert record.payload["severe_issue_count"] == 0


def test_cancel_marks_only_requested_run(repository: ProjectRepository, seeded_project) -> None:
    first = make_run(seeded_project.id)
    first.input_version_id = seeded_project.active_resume_version_id
    second = make_run(seeded_project.id)
    second.input_version_id = seeded_project.active_resume_version_id
    runs = [repository.create_optimization_run(first), repository.create_optimization_run(second)]

    cancelled = repository.request_optimization_cancel(runs[0].id)

    assert cancelled.cancel_requested is True
    assert repository.get_optimization_run(runs[0].id).cancel_requested is True
    assert repository.get_optimization_run(runs[1].id).cancel_requested is False


def test_project_delete_removes_optimization_children(
    repository: ProjectRepository, seeded_project
) -> None:
    run = make_run(seeded_project.id)
    run.input_version_id = seeded_project.active_resume_version_id
    seeded_run = repository.create_optimization_run(run)
    repository.save_optimization_step(
        seeded_run.id, "analysis", 0, 1, "hash", {"ok": True}, "succeeded"
    )
    repository.save_layout_report(seeded_run.id, 0, LayoutReport())

    repository.delete(seeded_project.id)

    with repository._sessions() as session:
        assert session.query(OptimizationStepRecord).count() == 0
        assert session.query(LayoutReportRecord).count() == 0
        assert session.query(OptimizationRunRecord).count() == 0
