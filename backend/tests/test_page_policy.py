from resume_mvp.domain import ResumeDocument, SourcedText, WorkExperienceEntry
from resume_mvp.page_policy import evaluate_page_policy


def test_campus_and_internship_use_compact_one_page_policy() -> None:
    """Catches early-career projects accidentally using unlimited pagination."""
    resume = ResumeDocument.blank()
    resume.basics.summary = SourcedText(value="具备后端开发基础")

    campus = evaluate_page_policy(resume, "campus")
    internship = evaluate_page_policy(resume, "internship")

    assert campus.max_pages == 1
    assert internship.compact is True
    assert campus.overflow is False


def test_long_campus_resume_overflows_without_truncating_content() -> None:
    """Catches one-page enforcement that silently discards long experience text."""
    long_text = "负责接口设计、稳定性治理与性能优化，" * 180
    resume = ResumeDocument(
        work_experience=[
            WorkExperienceEntry(
                company="示例科技",
                title="后端工程师",
                bullets=[SourcedText(value=long_text)],
            )
        ]
    )

    result = evaluate_page_policy(resume, "campus")

    assert result.overflow is True
    assert resume.work_experience[0].bullets[0].value == long_text
    assert result.largest_sections[0] == "work_experience"


def test_experienced_resume_never_blocks_for_length() -> None:
    """Catches social-hire resumes being forced into the campus one-page policy."""
    resume = ResumeDocument.blank()
    resume.basics.summary = SourcedText(value="长期从事企业系统研发" * 500)

    result = evaluate_page_policy(resume, "experienced")

    assert result.max_pages is None
    assert result.overflow is False
    assert result.compact is False
