#!/usr/bin/env python3
"""Create a fictional job project for local smoke testing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resume_mvp.database import create_database
from resume_mvp.domain import JobAnalysis, ResumeDocument
from resume_mvp.matching import calculate_match
from resume_mvp.profile import profile_is_ready
from resume_mvp.repositories import ProfileRequiredError, ProjectRepository


DEFAULT_PROJECT = ROOT / "fixtures" / "smoke_project.json"
DEFAULT_PROFILE = ROOT / "fixtures" / "smoke_profile.json"
SMOKE_TITLE = "冒烟·后端平台研发"


def _ensure_profile(repository: ProjectRepository, profile_path: Path) -> None:
    resume, _ = repository.get_profile()
    if profile_is_ready(resume):
        return
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    repository.save_profile(ResumeDocument.model_validate(payload))
    print(f"经历库为空，已自动导入 {profile_path.name}")


def _replace_existing(repository: ProjectRepository, title: str) -> None:
    for project in repository.list():
        if project.title == title:
            repository.delete(project.id)
            print(f"已删除旧冒烟项目：{project.id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="写入冒烟测试用假求职项目")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--profile-fixture", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--db", type=Path, default=ROOT / ".data" / "resume.db")
    args = parser.parse_args()

    data = json.loads(args.fixture.read_text(encoding="utf-8"))
    analysis = JobAnalysis.model_validate(data["job_analysis"])
    args.db.parent.mkdir(parents=True, exist_ok=True)
    repository = ProjectRepository(create_database(args.db))

    try:
        _ensure_profile(repository, args.profile_fixture)
    except Exception as exc:  # noqa: BLE001
        print(f"无法准备经历库：{exc}", file=sys.stderr)
        return 1

    _replace_existing(repository, data.get("title") or SMOKE_TITLE)

    try:
        project = repository.create(
            title=data["title"],
            company_name=data.get("company_name", ""),
            application_type=data["application_type"],
            job_description=data["job_description"],
        )
    except ProfileRequiredError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    template_id = data.get("selected_template_id")
    version = repository.get_active_version(project.id)
    assert version is not None
    match = calculate_match(analysis, version.resume, version.facts)
    project = repository.update(
        project.id,
        job_analysis=analysis,
        match_report=match,
        selected_template_id=template_id,
    )

    print(f"已创建求职项目 → {args.db}")
    print(f"标题：{project.title}")
    print(f"公司：{project.company_name} · 类型：{project.application_type}")
    print(f"项目 ID：{project.id}")
    print(f"匹配覆盖率：{match.coverage:.0%} · 要求 {len(match.items)} 条")
    print(f"打开：http://127.0.0.1:5173/projects/{project.id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
