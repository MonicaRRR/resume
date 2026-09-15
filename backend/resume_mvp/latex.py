"""Render structured Chinese resumes as safe UTF-8 XeLaTeX source."""

from __future__ import annotations

from resume_mvp.domain import ApplicationType, ResumeDocument
from resume_mvp.layout_tidy import skill_lines_for_export, tidy_resume_for_layout


def build_latex(
    resume: ResumeDocument,
    template_id: str,
    application_type: ApplicationType = "experienced",
) -> str:
    """Build deterministic LaTeX source without interpolating raw user commands."""
    resume = tidy_resume_for_layout(resume)
    compact = application_type in {"campus", "internship"}
    font_size = "9pt" if compact else "11pt"
    margin = "1.2cm" if compact else "1.6cm"
    accent = {
        "classic-cn": "111111",
        "clear-single": "2457D6",
        "pro-double": "214A72",
        "project-focus": "7A3E8E",
        "career-depth": "8A4C2A",
    }.get(template_id, "2457D6")
    lines = [
        f"% resume-evidence-workbench template={_escape(template_id)}",
        f"\\documentclass[{font_size}]{{article}}",
        "\\usepackage[UTF8]{ctex}",
        "\\usepackage[a4paper,"
        + f"margin={margin}"
        + "]{geometry}",
        "\\usepackage{enumitem}",
        "\\usepackage{xcolor}",
        "\\usepackage{hyperref}",
        "\\usepackage{graphicx}",
        "\\definecolor{resumeaccent}{HTML}{" + accent + "}",
        "\\pagestyle{empty}",
        "\\setlength{\\parindent}{0pt}",
        "\\setlist[itemize]{leftmargin=1.2em,nosep}",
        "\\begin{document}",
        "\\begin{center}",
        "{\\Huge \\textbf{" + _escape(resume.basics.name or "姓名") + "}}\\\\",
    ]
    contact = _contact_line(resume)
    if contact:
        lines.append(_escape(contact) + "\\\\")
    if resume.basics.target_role.value.strip():
        lines.append("{\\color{resumeaccent} " + _escape(resume.basics.target_role.value) + "}\\\\")
    lines.extend(["\\end{center}", "\\vspace{-0.4em}"])

    show_summary = application_type == "experienced" and resume.basics.summary.value.strip()
    if show_summary:
        lines.extend(_section("个人简介", [resume.basics.summary.value]))

    order = list(resume.section_order)
    if template_id == "project-focus" and "projects" in order:
        order.remove("projects")
        order.insert(1, "projects")
    for section in order:
        if section == "education" and resume.education:
            body = []
            for item in resume.education:
                dates = _dates(item.start_date, item.end_date)
                label = "，".join(v for v in [item.institution, item.field, item.degree] if v)
                body.append(f"\\textbf{{{_escape(label)}}}" + (f"\\hfill {_escape(dates)}" if dates else ""))
                body.extend(item.highlights)
            lines.extend(_section("教育经历", body, sourced=True))
        elif section == "work_experience" and resume.work_experience:
            body = []
            for item in resume.work_experience:
                title = "，".join(v for v in [item.company, item.title] if v)
                dates = _dates(item.start_date, item.end_date)
                body.append(f"\\textbf{{{_escape(title)}}}" + (f"\\hfill {_escape(dates)}" if dates else ""))
                body.extend(item.bullets)
            lines.extend(_section("实习工作经历", body, sourced=True))
        elif section == "projects" and resume.projects:
            body = []
            for item in resume.projects:
                title = "，".join(v for v in [item.name, item.role] if v)
                dates = _dates(item.start_date, item.end_date)
                body.append(f"\\textbf{{{_escape(title)}}}" + (f"\\hfill {_escape(dates)}" if dates else ""))
                body.extend(item.bullets)
            lines.extend(_section("项目经历", body, sourced=True))
        elif section == "skills" and resume.skills:
            skills = skill_lines_for_export(resume.skills)
            if skills:
                lines.extend(_section("专业技能", skills))
    if resume.certificates:
        lines.extend(_section("证书", [entry.name for entry in resume.certificates]))
    if resume.awards:
        lines.extend(_section("奖项", [entry.name for entry in resume.awards]))
    lines.append("\\end{document}")
    return "\n".join(lines) + "\n"


def _section(title: str, values: list, *, sourced: bool = False) -> list[str]:
    result = [f"\\section*{{{_escape(title)}}}"]
    for value in values:
        text = value.value if sourced and hasattr(value, "value") else str(value)
        if not text.strip():
            continue
        if sourced and hasattr(value, "value") and text == value.value and not text.startswith("\\textbf{"):
            result.append("\\begin{itemize}")
            result.append("\\item " + _escape(text))
            result.append("\\end{itemize}")
        else:
            result.append(text if text.startswith("\\textbf{") else _escape(text))
    return result


def _escape(value: str) -> str:
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(char, char) for char in str(value))


def _dates(start: str, end: str) -> str:
    return " -- ".join(value for value in [start.strip(), end.strip()] if value)


def _contact_line(resume: ResumeDocument) -> str:
    basics = resume.basics
    return " · ".join(value for value in [basics.phone, basics.email, basics.location] if value.strip())
