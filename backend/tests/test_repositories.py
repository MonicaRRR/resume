from pathlib import Path

import pytest

from resume_mvp.database import create_database
from resume_mvp.domain import ResumeDocument
from resume_mvp.repositories import ProjectRepository


@pytest.fixture
def repository(tmp_path: Path) -> ProjectRepository:
    session_factory = create_database(tmp_path / "resume.db")
    return ProjectRepository(session_factory)


def test_project_versions_are_immutable_and_switchable(repository: ProjectRepository) -> None:
    """Catches overwriting history or failing to activate an older version."""
    project = repository.create(
        title="后端开发",
        company_name="示例科技",
        job_description="负责 API 开发",
    )
    first = repository.save_version(project.id, ResumeDocument.blank(), reason="初始版本")

    second_resume = ResumeDocument.blank()
    second_resume.basics.name = "林晓"
    second = repository.save_version(project.id, second_resume, reason="补充姓名")
    repository.activate_version(project.id, first.id)

    assert repository.get(project.id).active_resume_version_id == first.id
    assert [version.id for version in repository.list_versions(project.id)] == [second.id, first.id]
    assert repository.get_version(first.id).resume.basics.name == ""
