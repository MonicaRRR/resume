from __future__ import annotations

from io import BytesIO
import json

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from resume_mvp.domain import (
    ApplicationType,
    Fact,
    JobAnalysis,
    JobProject,
    ResumeDocument,
    ResumeVersion,
    utc_now,
)


_TEMPLATE_STYLES = {
    "clear-single": {"font": "Microsoft YaHei", "accent": "2457D6", "margin": 1.7},
    "pro-double": {"font": "Microsoft YaHei", "accent": "214A72", "margin": 1.5},
    "project-focus": {"font": "Microsoft YaHei", "accent": "7A3E8E", "margin": 1.6},
    "career-depth": {"font": "SimSun", "accent": "8A4C2A", "margin": 1.8},
}


def build_docx(
    resume: ResumeDocument,
    template_id: str,
    application_type: ApplicationType = "experienced",
) -> bytes:
    style = _TEMPLATE_STYLES.get(template_id, _TEMPLATE_STYLES["clear-single"])
    compact = application_type in {"campus", "internship"}
    document = Document()
    section = document.sections[0]
    margin = Cm(min(style["margin"], 1.25) if compact else style["margin"])
    section.top_margin = section.bottom_margin = margin
    section.left_margin = section.right_margin = margin

    normal = document.styles["Normal"]
    normal.font.name = style["font"]
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), style["font"])
    normal.font.size = Pt(9 if compact else 10)
    normal.paragraph_format.space_after = Pt(1 if compact else 4)
    normal.paragraph_format.line_spacing = 1.0 if compact else 1.15

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = title.add_run(resume.basics.name or "姓名")
    _style_run(name_run, style["font"], 20, style["accent"], bold=True)
    if resume.basics.target_role.value:
        role = document.add_paragraph()
        role.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _style_run(role.add_run(resume.basics.target_role.value), style["font"], 10, "687386")

    contact = " · ".join(
        value for value in [resume.basics.phone, resume.basics.email, resume.basics.location] if value
    )
    if contact:
        paragraph = document.add_paragraph(contact)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    if resume.basics.summary.value:
        _heading(document, "个人简介", style, compact=compact)
        document.add_paragraph(resume.basics.summary.value)

    section_order = list(resume.section_order)
    if template_id == "project-focus" and "projects" in section_order:
        section_order.remove("projects")
        section_order.insert(1, "projects")

    for section_name in section_order:
        if section_name == "work_experience" and resume.work_experience:
            _heading(document, "工作经历", style, compact=compact)
            for item in resume.work_experience:
                _entry_title(document, item.company, item.title, item.start_date, item.end_date, style)
                _bullets(document, [bullet.value for bullet in item.bullets])
        elif section_name == "projects" and resume.projects:
            _heading(document, "项目经历", style, compact=compact)
            for item in resume.projects:
                _entry_title(document, item.name, item.role, item.start_date, item.end_date, style)
                _bullets(document, [bullet.value for bullet in item.bullets])
        elif section_name == "education" and resume.education:
            _heading(document, "教育经历", style, compact=compact)
            for item in resume.education:
                detail = " · ".join(value for value in [item.degree, item.field] if value)
                _entry_title(document, item.institution, detail, item.start_date, item.end_date, style)
                _bullets(document, [highlight.value for highlight in item.highlights])
        elif section_name == "skills" and resume.skills:
            _heading(document, "专业技能", style, compact=compact)
            for group in resume.skills:
                document.add_paragraph(
                    f"{group.name}：{'、'.join(item.value for item in group.items)}"
                )
        elif section_name == "custom_sections":
            for custom in resume.custom_sections:
                _heading(document, custom.title, style, compact=compact)
                _bullets(document, [item.value for item in custom.items])

    if resume.certificates:
        _heading(document, "证书", style, compact=compact)
        _bullets(document, [entry.name for entry in resume.certificates])
    if resume.awards:
        _heading(document, "奖项", style, compact=compact)
        _bullets(document, [entry.name for entry in resume.awards])

    output = BytesIO()
    document.save(output)
    return output.getvalue()


def build_resume_json(project: JobProject, version: ResumeVersion) -> bytes:
    payload = {
        "format": "resume-evidence-workbench/v1",
        "exported_at": utc_now().isoformat(),
        "project": {
            "id": project.id,
            "title": project.title,
            "company_name": project.company_name,
            "application_type": project.application_type,
            "job_description": project.job_description,
            "selected_template_id": project.selected_template_id,
        },
        "version_id": version.id,
        "resume": version.resume.model_dump(mode="json"),
        "facts": [fact.model_dump(mode="json") for fact in version.facts],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def build_codex_handoff(
    project: JobProject,
    analysis: JobAnalysis | None,
    resume: ResumeDocument,
    facts: list[Fact],
) -> str:
    safe_resume = resume.model_dump(mode="json")
    safe_resume["basics"]["email"] = ""
    safe_resume["basics"]["phone"] = ""
    confirmed = [fact.model_dump(mode="json") for fact in facts if fact.user_confirmed]
    analysis_payload = analysis.model_dump(mode="json") if analysis else {}
    return "\n\n".join(
        [
            "# Codex 求职上下文",
            "## 任务\n基于以下 JD 与事实帮助优化中文简历或进行求职训练。",
            f"## 目标\n项目：{project.title}\n公司：{project.company_name or '未填写'}",
            "## JD 摘要\n```json\n"
            + json.dumps(analysis_payload, ensure_ascii=False, indent=2)
            + "\n```",
            "## 已确认事实\n```json\n"
            + json.dumps(confirmed, ensure_ascii=False, indent=2)
            + "\n```",
            "## 当前简历\n```json\n"
            + json.dumps(safe_resume, ensure_ascii=False, indent=2)
            + "\n```",
            "## 待解决问题\n请指出证据不足的岗位要求，并一次提出一个问题。",
            "## 输出约束\n仅使用中文；不得虚构事实；每项改写必须注明对应事实；先给建议，不直接覆盖简历。",
        ]
    )


def _heading(document: Document, text: str, style: dict, *, compact: bool = False) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(6 if compact else 10)
    paragraph.paragraph_format.space_after = Pt(2 if compact else 4)
    _style_run(
        paragraph.add_run(text),
        style["font"],
        10.5 if compact else 12,
        style["accent"],
        bold=True,
    )


def _entry_title(
    document: Document,
    primary: str,
    secondary: str,
    start: str,
    end: str,
    style: dict,
) -> None:
    paragraph = document.add_paragraph()
    _style_run(paragraph.add_run(primary), style["font"], 10.5, "172033", bold=True)
    if secondary:
        paragraph.add_run(f"  {secondary}")
    dates = " – ".join(value for value in [start, end] if value)
    if dates:
        paragraph.add_run(f"    {dates}")


def _bullets(document: Document, values: list[str]) -> None:
    for value in values:
        if value:
            document.add_paragraph(value, style="List Bullet")


def _style_run(
    run,
    font: str,
    size: float,
    color: str,
    *,
    bold: bool = False,
) -> None:
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    run.bold = bold
