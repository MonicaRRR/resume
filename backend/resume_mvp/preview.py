from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from resume_mvp.layout_analysis import pdf_page_count


class PreviewConversionError(RuntimeError):
    pass


def convert_docx_to_pdf(docx_bytes: bytes, *, timeout: float = 90) -> bytes:
    """Render a DOCX to PDF via LibreOffice for faithful pagination preview."""
    if not docx_bytes:
        raise PreviewConversionError("DOCX 内容为空")

    binary = _libreoffice_binary()
    if binary is None:
        raise PreviewConversionError("未找到 LibreOffice（soffice），无法生成 PDF 预览")

    with TemporaryDirectory(prefix="resume-preview-") as directory:
        root = Path(directory)
        source = root / "resume.docx"
        source.write_bytes(docx_bytes)
        profile = root / "lo-profile"
        profile.mkdir()
        command = [
            binary,
            "--headless",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation={profile.as_uri()}",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(root),
            str(source),
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise PreviewConversionError("PDF 预览生成超时，请稍后重试") from error

        pdf_path = root / "resume.pdf"
        if not pdf_path.exists():
            detail = (completed.stderr or completed.stdout or "").strip()
            raise PreviewConversionError(
                f"LibreOffice 未能生成 PDF{('：' + detail[:200]) if detail else ''}"
            )
        return pdf_path.read_bytes()


def count_pdf_pages(pdf_bytes: bytes) -> int:
    return pdf_page_count(pdf_bytes)


def render_pdf_page_pngs(pdf_bytes: bytes, *, dpi: float = 144) -> list[bytes]:
    """Rasterize PDF pages so the UI can preview without the browser PDF plugin."""
    import fitz

    if not pdf_bytes:
        raise PreviewConversionError("PDF 内容为空")

    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if document.page_count < 1:
            raise PreviewConversionError("PDF 没有可预览的页面")
        matrix = fitz.Matrix(dpi / 72, dpi / 72)
        pages: list[bytes] = []
        for page in document:
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            pages.append(pixmap.tobytes("png"))
        return pages
    finally:
        document.close()


def _libreoffice_binary() -> str | None:
    from shutil import which

    return which("soffice") or which("libreoffice")
