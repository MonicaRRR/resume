#!/usr/bin/env python3
"""Load the fictional smoke-test profile into the local SQLite experience library."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resume_mvp.database import create_database
from resume_mvp.domain import ResumeDocument
from resume_mvp.profile import profile_is_ready
from resume_mvp.repositories import ProjectRepository


DEFAULT_FIXTURE = ROOT / "fixtures" / "smoke_profile.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="写入冒烟测试用假经历库")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE,
        help="简历 JSON 路径（默认 fixtures/smoke_profile.json）",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=ROOT / ".data" / "resume.db",
        help="SQLite 路径（默认 backend/.data/resume.db）",
    )
    args = parser.parse_args()

    payload = json.loads(args.fixture.read_text(encoding="utf-8"))
    resume = ResumeDocument.model_validate(payload)
    args.db.parent.mkdir(parents=True, exist_ok=True)
    repository = ProjectRepository(create_database(args.db))
    saved, facts = repository.save_profile(resume)

    print(f"已写入经历库 → {args.db}")
    print(f"姓名：{saved.basics.name}")
    print(
        "规模："
        f"教育 {len(saved.education)} · "
        f"工作 {len(saved.work_experience)} · "
        f"项目 {len(saved.projects)} · "
        f"技能组 {len(saved.skills)} · "
        f"证书 {len(saved.certificates)} · "
        f"奖项 {len(saved.awards)} · "
        f"自定义 {len(saved.custom_sections)}"
    )
    print(f"派生事实：{len(facts)} 条 · ready={profile_is_ready(saved)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
