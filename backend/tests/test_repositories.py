from pathlib import Path
import sqlite3

import pytest

from resume_mvp.database import create_database
from resume_mvp.domain import ResumeDocument, SkillGroup, SourcedText
from resume_mvp.repositories import ProjectRepository


@pytest.fixture
def repository(tmp_path: Path) -> ProjectRepository:
    session_factory = create_database(tmp_path / "resume.db")
    repo = ProjectRepository(session_factory)
    profile = ResumeDocument.blank()
    profile.basics.name = "测试用户"
    profile.skills = [SkillGroup(category="语言", items=[SourcedText(value="Python")])]
    repo.save_profile(profile)
    return repo


def test_project_versions_are_immutable_and_switchable(repository: ProjectRepository) -> None:
    """Catches overwriting history or failing to activate an older version."""
    project = repository.create(
        title="后端开发",
        company_name="示例科技",
        application_type="experienced",
        job_description="负责 API 开发",
    )
    seeded_id = project.active_resume_version_id
    first = repository.save_version(project.id, ResumeDocument.blank(), reason="初始版本")

    second_resume = ResumeDocument.blank()
    second_resume.basics.name = "林晓"
    second = repository.save_version(project.id, second_resume, reason="补充姓名")
    repository.activate_version(project.id, first.id)

    assert repository.get(project.id).active_resume_version_id == first.id
    assert [version.id for version in repository.list_versions(project.id)] == [second.id, first.id, seeded_id]
    assert repository.get_version(first.id).resume.basics.name == ""


def test_database_migrates_application_type_for_existing_projects(tmp_path: Path) -> None:
    """Catches upgrades that require users to delete their existing local database."""
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE projects (
            id VARCHAR PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            company_name VARCHAR(200) NOT NULL,
            job_description TEXT NOT NULL,
            job_analysis JSON,
            active_resume_version_id VARCHAR,
            selected_template_id VARCHAR(50) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
        """
    )
    connection.commit()
    connection.close()

    repository = ProjectRepository(create_database(path))
    profile = ResumeDocument.blank()
    profile.basics.name = "测试用户"
    profile.skills = [SkillGroup(category="语言", items=[SourcedText(value="Python")])]
    repository.save_profile(profile)
    project = repository.create(
        title="校招后端",
        company_name="",
        application_type="campus",
        job_description="负责 Python API",
    )

    assert project.application_type == "campus"
