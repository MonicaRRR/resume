from __future__ import annotations

import fitz
import pytest

from resume_mvp.domain import Basics, CustomSection, ProjectEntry, ResumeDocument, SkillGroup, SourcedText
from resume_mvp.exports import build_docx
from resume_mvp.layout_analysis import analyze_pdf_layout
from resume_mvp.preview import convert_docx_to_pdf


def resume_with_project_bullet(bullet: str) -> ResumeDocument:
    return ResumeDocument(
        projects=[
            ProjectEntry(
                name="简历优化工具",
                bullets=[SourcedText(value=bullet)],
            )
        ]
    )


def pdf_with_two_lines(*, first: str, last: str, first_width: float, last_width: float) -> bytes:
    document = fitz.open()
    page = document.new_page()
    _insert_line(page, first, y=100, width=first_width)
    _insert_line(page, last, y=114, width=last_width)
    payload = document.tobytes()
    document.close()
    return payload


def pdf_with_short_standalone_lines(lines: list[str]) -> bytes:
    document = fitz.open()
    page = document.new_page()
    for index, text in enumerate(lines):
        _insert_line(page, text, y=100 + (index * 24), width=40)
    payload = document.tobytes()
    document.close()
    return payload


def two_page_pdf() -> bytes:
    document = fitz.open()
    document.new_page()
    document.new_page()
    payload = document.tobytes()
    document.close()
    return payload


def two_page_pdf_with_orphan_heading(heading: str) -> bytes:
    document = fitz.open()
    first_page = document.new_page()
    _insert_line(first_page, heading, y=760, width=80)
    second_page = document.new_page()
    _insert_line(second_page, "下一页的正文内容", y=100, width=140)
    payload = document.tobytes()
    document.close()
    return payload


def _insert_line(page: fitz.Page, text: str, *, y: float, width: float) -> None:
    font = fitz.Font("china-s")
    natural_width = font.text_length(text, fontsize=10)
    page.insert_text(
        (72, y),
        text,
        fontname="china-s",
        fontsize=10,
        morph=(fitz.Point(72, y), fitz.Matrix(width / natural_width, 1)),
    )


def test_detects_short_tail_on_known_resume_bullet() -> None:
    resume = resume_with_project_bullet("负责接口设计与性能优化，降低响应延迟并完成上线验证")
    pdf = pdf_with_two_lines(
        first="负责接口设计与性能优化，降低响应延迟并完成上线",
        last="验证",
        first_width=320,
        last_width=24,
    )

    report = analyze_pdf_layout(pdf, resume, "experienced")

    issue = next(item for item in report.issues if item.kind == "short_tail")
    assert issue.target_path == "/projects/0/bullets/0"
    assert issue.measured_ratio is not None
    assert issue.measured_ratio < 0.25


def test_tail_at_exactly_one_quarter_is_not_short() -> None:
    resume = resume_with_project_bullet("负责接口设计与性能优化，降低响应延迟并完成上线验证")
    pdf = pdf_with_two_lines(
        first="负责接口设计与性能优化，降低响应延迟并完成上线",
        last="验证",
        first_width=320,
        last_width=80,
    )

    report = analyze_pdf_layout(pdf, resume, "experienced")

    assert all(item.kind != "short_tail" for item in report.issues)


def test_detects_short_tail_on_merged_named_skill_group() -> None:
    resume = ResumeDocument(
        skills=[
            SkillGroup(
                name="后端",
                items=[
                    SourcedText(value="负责接口设计与性能优化，降低响应延迟并完成上线"),
                    SourcedText(value="验证"),
                ],
            )
        ]
    )
    pdf = pdf_with_two_lines(
        first="后端：负责接口设计与性能优化，降低响应延迟并完成上线、",
        last="验证",
        first_width=320,
        last_width=24,
    )

    report = analyze_pdf_layout(pdf, resume, "experienced")

    issue = next(item for item in report.issues if item.kind == "short_tail")
    assert issue.target_path == "/skills/0/items"


def test_contact_heading_and_date_are_excluded() -> None:
    report = analyze_pdf_layout(
        pdf_with_short_standalone_lines(["张宁", "项目经历", "2026.09"]),
        resume_with_project_bullet("完整项目描述"),
        "experienced",
    )

    assert all(item.kind != "short_tail" for item in report.issues)


def test_campus_two_page_pdf_is_severe_overflow() -> None:
    report = analyze_pdf_layout(two_page_pdf(), ResumeDocument.blank(), "campus")

    assert any(
        item.kind == "one_page_overflow" and item.severity == "severe"
        for item in report.issues
    )


@pytest.mark.integration
def test_detects_project_bullet_tail_from_real_exported_pdf() -> None:
    # Last clause is intentionally short so the wrapped final PDF line stays under 25% width.
    bullet = ("完成订单检索接口优化与监控看板建设，推动限流熔断与故障复盘落地。" * 3) + "短。"
    resume = ResumeDocument(
        basics=Basics(name="张宁"),
        projects=[ProjectEntry(name="可靠消息投递平台", bullets=[SourcedText(value=bullet)])],
    )
    pdf = convert_docx_to_pdf(build_docx(resume, "clear-single", "experienced"))

    report = analyze_pdf_layout(pdf, resume, "experienced")

    issue = next(item for item in report.issues if item.kind == "short_tail")
    assert issue.target_path == "/projects/0/bullets/0"
    assert issue.measured_ratio is not None
    assert issue.measured_ratio < 0.25


def test_detects_custom_section_heading_orphaned_on_first_page() -> None:
    title = "开源贡献"
    resume = ResumeDocument(custom_sections=[CustomSection(title=title)])

    report = analyze_pdf_layout(two_page_pdf_with_orphan_heading(title), resume, "experienced")

    assert any(
        item.kind == "orphan_heading" and item.page == 1 and item.text_excerpt == title
        for item in report.issues
    )
