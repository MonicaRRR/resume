from io import BytesIO

import fitz
import pytest
from docx import Document
from docx.shared import Pt, RGBColor

from resume_mvp.ingestion import ResumeImportError, import_resume


def make_docx() -> bytes:
    document = Document()
    name = document.add_paragraph()
    run = name.add_run("张宁")
    run.font.name = "Microsoft YaHei"
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(36, 87, 214)
    document.add_paragraph("后端工程师")
    document.add_paragraph("工作经历")
    document.add_paragraph("示例科技｜后端工程师")
    document.add_paragraph("使用 Python 开发 API")
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def make_blank_pdf() -> bytes:
    document = fitz.open()
    document.new_page()
    return document.tobytes()


def test_txt_import_preserves_lines_as_confirmable_facts() -> None:
    """Catches importers that drop source lines and leave AI without evidence."""
    result = import_resume(
        "resume.txt",
        "text/plain",
        "张宁\n产品经理\n负责增长实验".encode(),
    )

    assert result.resume.basics.name == "张宁"
    assert result.resume.basics.target_role.value == "产品经理"
    assert any("增长实验" in fact.statement for fact in result.facts)
    assert result.quality_score > 0


def test_docx_import_preserves_a_style_profile() -> None:
    """Catches DOCX parsing that extracts text but loses the reusable visual profile."""
    result = import_resume(
        "resume.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        make_docx(),
    )

    assert result.resume.basics.name == "张宁"
    assert result.layout_profile.source_kind == "docx"
    assert result.layout_profile.imported is True
    assert result.layout_profile.font_family == "Microsoft YaHei"
    assert result.layout_profile.accent_color == "#2457D6"


def test_rejects_scanned_or_empty_pdf() -> None:
    """Catches silent creation of an empty resume from an image-only PDF."""
    with pytest.raises(ResumeImportError, match="未提取到可用文字"):
        import_resume("scan.pdf", "application/pdf", make_blank_pdf())


def test_rejects_mismatched_extension_and_content_type() -> None:
    """Catches files disguised with a supported extension."""
    with pytest.raises(ResumeImportError, match="文件类型不匹配"):
        import_resume("resume.pdf", "text/plain", b"plain text")
