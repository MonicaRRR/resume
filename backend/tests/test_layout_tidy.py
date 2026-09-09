from io import BytesIO

from docx import Document

from resume_mvp.domain import ResumeDocument, SkillGroup, SourcedText, WorkExperienceEntry
from resume_mvp.exports import build_docx
from resume_mvp.layout_tidy import (
    normalize_skill_groups,
    skill_lines_for_export,
    tidy_resume_for_layout,
)


def test_skill_lines_split_and_drop_empty_duplicate_labels() -> None:
    groups = [
        SkillGroup(name="技能", items=[]),
        SkillGroup(name="专业技能", items=[SourcedText(value="Python、SQL、Git")]),
        SkillGroup(name="技能", items=[SourcedText(value="")]),
        SkillGroup(name="语言", items=[SourcedText(value="英语 CET-6")]),
    ]

    lines = skill_lines_for_export(groups)

    assert "专业技能：Python、SQL、Git" not in lines
    assert "技能：" not in "\n".join(lines)
    assert lines == ["语言：英语 CET-6", "Python", "SQL", "Git"]


def test_normalize_drops_empty_skill_shells() -> None:
    cleaned = normalize_skill_groups(
        [
            SkillGroup(name="技能", items=[]),
            SkillGroup(name="", items=[SourcedText(value="Docker")]),
        ]
    )
    assert len(cleaned) == 1
    assert cleaned[0].name == "专业技能"
    assert [item.value for item in cleaned[0].items] == ["Docker"]


def test_tidy_merges_ultra_short_bullets() -> None:
    resume = ResumeDocument.blank()
    resume.work_experience = [
        WorkExperienceEntry(
            company="示例",
            title="实习",
            bullets=[
                SourcedText(value="写接口"),
                SourcedText(value="写测试"),
                SourcedText(value="参与联调与上线复盘"),
            ],
        )
    ]
    tidied = tidy_resume_for_layout(resume)
    values = [item.value for item in tidied.work_experience[0].bullets]
    assert values == ["写接口；写测试", "参与联调与上线复盘"]


def test_docx_skills_section_uses_bullets_without_repeated_heading() -> None:
    resume = ResumeDocument.blank()
    resume.basics.name = "测试"
    resume.skills = [
        SkillGroup(name="专业技能", items=[SourcedText(value="Python、FastAPI、PostgreSQL")]),
        SkillGroup(name="技能", items=[]),
    ]

    document = Document(BytesIO(build_docx(resume, "clear-single")))
    texts = [paragraph.text for paragraph in document.paragraphs]
    skill_heading_indexes = [index for index, text in enumerate(texts) if text == "专业技能"]
    assert len(skill_heading_indexes) == 1
    assert "专业技能：Python" not in "\n".join(texts)
    assert "Python" in texts
    assert "FastAPI" in texts
    assert "PostgreSQL" in texts
