import pytest
from pydantic import ValidationError

from resume_mvp.domain import ResumeDocument, SourcedText


def test_ai_rewrite_requires_supporting_facts() -> None:
    """Catches fabricated AI copy that is detached from user-provided facts."""
    with pytest.raises(ValidationError, match="事实来源"):
        SourcedText(value="提升转化率 40%", origin="ai_rewrite", source_fact_ids=[])


def test_blank_resume_has_stable_chinese_section_order() -> None:
    """Catches blank resumes whose editor sections render in an unusable order."""
    resume = ResumeDocument.blank()

    assert resume.section_order == [
        "basics",
        "work_experience",
        "projects",
        "education",
        "skills",
    ]
