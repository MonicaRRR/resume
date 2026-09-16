from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from resume_mvp.domain import MatchReport, PracticeSession, ResumeDocument, SourcedText
from resume_mvp.main import create_app
from resume_mvp.optimization_models import OptimizationRun


def test_project_timeline_projects_all_job_activity_without_writes(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path, test_providers={})
    repository = app.state.services.repository
    repository.save_profile(
        ResumeDocument.model_validate(
            {
                "basics": {"name": "张宁"},
                "skills": [{"name": "技能", "items": [SourcedText(value="Python").model_dump()]}],
            }
        )
    )
    project = repository.create(
        title="后端工程师",
        company_name="示例科技",
        application_type="experienced",
        job_description="负责 Python API",
    )
    version = repository.get_active_version(project.id)
    assert version is not None
    project = repository.update(
        project.id,
        match_report=MatchReport(coverage=0.75, items=[]),
    )
    repository.create_optimization_run(
        OptimizationRun(
            id="run-1",
            project_id=project.id,
            input_version_id=version.id,
            template_id="classic-cn",
            provider="test",
            mode="quick",
            status="ready_for_user",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        )
    )
    repository.save_practice(
        PracticeSession(
            id="practice-1",
            project_id=project.id,
            kind="interview",
            status="completed",
            created_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )
    )

    client = TestClient(app)
    response = client.get(f"/api/projects/{project.id}/timeline")

    assert response.status_code == 200
    events = response.json()
    assert {event["kind"] for event in events} == {
        "resume_version",
        "match_report",
        "optimization_run",
        "practice_session",
    }
    practice = next(event for event in events if event["kind"] == "practice_session")
    assert practice["source_id"] == "practice-1"
    assert practice["label"] == "模拟面试"
    assert events.index(practice) < next(
        index for index, event in enumerate(events) if event["kind"] == "optimization_run"
    )

    # The projection is read-only: querying it does not create another version.
    assert len(repository.list_versions(project.id)) == 1


def test_project_timeline_returns_404_for_unknown_project(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path, test_providers={}))
    response = client.get("/api/projects/missing/timeline")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "PROJECT_NOT_FOUND"
