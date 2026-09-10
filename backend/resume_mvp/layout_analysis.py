"""Detect visible resume layout problems from the rendered PDF geometry."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from resume_mvp.domain import ApplicationType, ResumeDocument
from resume_mvp.layout_tidy import is_generic_skill_group_name
from resume_mvp.optimization_models import LayoutIssue, LayoutReport


_SHORT_TAIL_THRESHOLD = 0.25
_SECTION_HEADINGS = {
    "个人简介",
    "教育背景",
    "教育经历",
    "职业经历",
    "工作经历",
    "实习工作经历",
    "项目经历",
    "专业技能",
    "技能",
    "证书",
    "奖项",
}
_DATE_ONLY = re.compile(r"^\d{4}(?:[./-]\d{1,2})?(?:[./-]\d{1,2})?$")
_CONTACT_TEXT = re.compile(r"(?:@|邮箱|邮件|电话|手机|微信|weixin|wechat|\+?\d[\d\s-]{6,})", re.IGNORECASE)
_BULLET_MARKERS = "•●▪◦·\uf0b7"


@dataclass(frozen=True)
class _Line:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)


@dataclass(frozen=True)
class _Paragraph:
    text: str
    lines: list[_Line]


@dataclass(frozen=True)
class _PageGeometry:
    number: int
    width: float
    height: float
    paragraphs: list[_Paragraph]
    density: float
    vertical_occupancy: float


def pdf_page_count(pdf_bytes: bytes) -> int:
    """Return the physical PDF page count used by both preview and analysis."""
    import fitz

    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return max(1, document.page_count)
    finally:
        document.close()


def analyze_pdf_layout(
    pdf_bytes: bytes,
    resume: ResumeDocument,
    application_type: ApplicationType,
) -> LayoutReport:
    """Analyze rendered text geometry without inferring layout from source content."""
    import fitz

    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages = [_page_geometry(page, number=index + 1) for index, page in enumerate(document)]
    finally:
        document.close()

    issues = _short_tail_issues(pages, _resume_text_paths(resume), threshold=_SHORT_TAIL_THRESHOLD)
    headings = _SECTION_HEADINGS | {
        _normalise_text(section.title)
        for section in resume.custom_sections
        if _normalise_text(section.title)
    }
    issues.extend(_orphan_heading_issues(pages, headings))
    issues.extend(_sparse_last_page_issues(pages))
    if application_type in {"campus", "internship"} and len(pages) > 1:
        issues.append(
            LayoutIssue(
                kind="one_page_overflow",
                severity="severe",
                page=2,
                message=f"校招/实习简历实际为 {len(pages)} 页",
            )
        )
    return LayoutReport(
        page_count=max(1, len(pages)),
        density_by_page=[page.density for page in pages],
        issues=issues,
    )


def _page_geometry(page: Any, *, number: int) -> _PageGeometry:
    text = page.get_text("dict")
    paragraphs: list[_Paragraph] = []
    boxes: list[tuple[float, float, float, float]] = []
    for block in text.get("blocks", []):
        if block.get("type") != 0:
            continue
        lines = _block_lines(block)
        if not lines:
            continue
        paragraphs.append(_Paragraph(text="".join(line.text for line in lines), lines=lines))
        boxes.append(tuple(float(value) for value in block["bbox"]))

    page_area = max(1.0, float(page.rect.width) * float(page.rect.height))
    text_area = sum(max(0.0, x1 - x0) * max(0.0, y1 - y0) for x0, y0, x1, y1 in boxes)
    if boxes:
        top = min(y0 for _, y0, _, _ in boxes)
        bottom = max(y1 for _, _, _, y1 in boxes)
        vertical_occupancy = max(0.0, min(1.0, (bottom - top) / float(page.rect.height)))
    else:
        vertical_occupancy = 0.0
    return _PageGeometry(
        number=number,
        width=float(page.rect.width),
        height=float(page.rect.height),
        paragraphs=paragraphs,
        density=max(0.0, min(1.0, text_area / page_area)),
        vertical_occupancy=vertical_occupancy,
    )


def _block_lines(block: dict[str, Any]) -> list[_Line]:
    lines: list[_Line] = []
    for raw_line in block.get("lines", []):
        value = "".join(str(span.get("text", "")) for span in raw_line.get("spans", [])).strip()
        if not value:
            continue
        x0, y0, x1, y1 = (float(value) for value in raw_line["bbox"])
        lines.append(_Line(text=value, x0=x0, y0=y0, x1=x1, y1=y1))
    return lines


def _short_tail_issues(
    pages: list[_PageGeometry],
    paths: dict[str, str],
    *,
    threshold: float,
) -> list[LayoutIssue]:
    """Find wrapped bullets whose last visible line is much shorter than earlier lines.

    LibreOffice PDFs often split one Word paragraph across multiple text blocks and
    keep the bullet glyph on its own line. Matching therefore scans consecutive
    page lines, not only lines inside a single PDF block.
    """
    issues: list[LayoutIssue] = []
    used_paths: set[str] = set()
    for page in pages:
        lines = [line for paragraph in page.paragraphs for line in paragraph.lines]
        index = 0
        while index < len(lines):
            matched: tuple[str, list[_Line], int] | None = None
            for end in range(len(lines), index + 1, -1):
                window = lines[index:end]
                content = [line for line in window if _normalise_text(line.text)]
                if len(content) < 2:
                    continue
                target_path = paths.get(_normalise_text("".join(line.text for line in window)))
                if not target_path or target_path in used_paths:
                    continue
                matched = (target_path, content, end)
                break
            if matched is None:
                index += 1
                continue
            target_path, content, end = matched
            used_paths.add(target_path)
            available_width = max(line.width for line in content)
            if available_width <= 0:
                index = end
                continue
            ratio = content[-1].width / available_width
            if ratio < threshold:
                issues.append(
                    LayoutIssue(
                        kind="short_tail",
                        severity="warning",
                        page=page.number,
                        target_path=target_path,
                        text_excerpt="".join(line.text for line in content),
                        measured_ratio=ratio,
                        message="正文最后一行过短，建议调整措辞或换行",
                    )
                )
            index = end
    return issues


def _editable_paragraphs(
    paragraph: _Paragraph,
    paths: dict[str, str],
) -> list[tuple[str, _Paragraph]]:
    """Keep for unit tests that inject synthetic single-block paragraphs."""
    matches: list[tuple[str, _Paragraph]] = []
    for start, line in enumerate(paragraph.lines):
        if not _normalise_text(line.text):
            continue
        for end in range(start + 2, len(paragraph.lines) + 1):
            lines = paragraph.lines[start:end]
            target_path = paths.get(_normalise_text("".join(item.text for item in lines)))
            if target_path:
                matches.append((target_path, _Paragraph(text="".join(item.text for item in lines), lines=lines)))
                break
    return matches


def _orphan_heading_issues(
    pages: list[_PageGeometry],
    headings: set[str],
) -> list[LayoutIssue]:
    issues: list[LayoutIssue] = []
    for index, page in enumerate(pages[:-1]):
        lines = [line for paragraph in page.paragraphs for line in paragraph.lines]
        if not lines:
            continue
        last_line = max(lines, key=lambda line: line.y1)
        if _normalise_text(last_line.text) not in headings:
            continue
        if last_line.y1 < page.height * 0.6 or not pages[index + 1].paragraphs:
            continue
        issues.append(
            LayoutIssue(
                kind="orphan_heading",
                severity="warning",
                page=page.number,
                text_excerpt=last_line.text,
                message="章节标题出现在页末，正文被拆到下一页",
            )
        )
    return issues


def _sparse_last_page_issues(pages: list[_PageGeometry]) -> list[LayoutIssue]:
    if len(pages) < 2 or pages[-1].vertical_occupancy >= _SHORT_TAIL_THRESHOLD:
        return []
    return [
        LayoutIssue(
            kind="sparse_last_page",
            severity="warning",
            page=pages[-1].number,
            message="最后一页正文垂直占用不足 25%",
        )
    ]


def _resume_text_paths(resume: ResumeDocument) -> dict[str, str]:
    paths: dict[str, str] = {}

    def add(path: str, value: str) -> None:
        normalised = _normalise_text(value)
        if normalised and not _is_non_body_text(value):
            paths.setdefault(normalised, path)

    add("/basics/summary", resume.basics.summary.value)
    for index, entry in enumerate(resume.education):
        for item_index, item in enumerate(entry.highlights):
            add(f"/education/{index}/highlights/{item_index}", item.value)
    for index, entry in enumerate(resume.work_experience):
        for item_index, item in enumerate(entry.bullets):
            add(f"/work_experience/{index}/bullets/{item_index}", item.value)
    for index, entry in enumerate(resume.projects):
        for item_index, item in enumerate(entry.bullets):
            add(f"/projects/{index}/bullets/{item_index}", item.value)
    for index, group in enumerate(resume.skills):
        items = [item.value for item in group.items if item.value.strip()]
        if is_generic_skill_group_name(group.name):
            for item_index, item in enumerate(group.items):
                add(f"/skills/{index}/items/{item_index}", item.value)
        elif items:
            add(f"/skills/{index}/items", f"{group.name.strip()}：{'、'.join(items)}")
    for index, entry in enumerate(resume.certificates):
        add(f"/certificates/{index}/name", entry.name)
    for index, entry in enumerate(resume.awards):
        add(f"/awards/{index}/name", entry.name)
    for index, section in enumerate(resume.custom_sections):
        for item_index, item in enumerate(section.items):
            add(f"/custom_sections/{index}/items/{item_index}", item.value)
    return paths


def _normalise_text(value: str) -> str:
    compact = "".join(value.split())
    return compact.translate(str.maketrans("", "", _BULLET_MARKERS))


def _is_non_body_text(value: str) -> bool:
    compact = _normalise_text(value)
    return bool(
        not compact
        or compact in _SECTION_HEADINGS
        or _DATE_ONLY.fullmatch(compact)
        or _CONTACT_TEXT.search(compact)
    )
