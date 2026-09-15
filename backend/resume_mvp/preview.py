from __future__ import annotations

import subprocess
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile
import shutil

from lxml import etree

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

    prepared_docx, preview_fonts = _substitute_missing_cjk_fonts(docx_bytes)
    with TemporaryDirectory(prefix="resume-preview-") as directory:
        root = Path(directory)
        source = root / "resume.docx"
        source.write_bytes(prepared_docx)
        profile = root / "lo-profile"
        profile.mkdir()
        _link_preview_fonts(profile, preview_fonts)
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


def compile_latex_to_pdf(source_text: str, *, timeout: float = 90) -> bytes:
    """Compile UTF-8 XeLaTeX source in an isolated temporary directory."""
    if not source_text.strip():
        raise PreviewConversionError("LaTeX 内容为空")
    from shutil import which

    binary = which("xelatex") or which("tectonic")
    if binary is None:
        raise PreviewConversionError("未找到 XeLaTeX 编译器，已切换浏览器预览")
    with TemporaryDirectory(prefix="resume-latex-") as directory:
        root = Path(directory)
        source = root / "resume.tex"
        source.write_text(source_text, encoding="utf-8")
        if "template=overleaf-cn" in source_text:
            template_root = Path(__file__).resolve().parents[1] / "templates" / "overleaf-resume-chinese"
            if template_root.exists():
                shutil.copy2(template_root / "setting.cls", root / "setting.cls")
                shutil.copytree(template_root / "Font", root / "Font")
        command = [binary, "-interaction=nonstopmode", "-halt-on-error", source.name]
        if Path(binary).name == "tectonic":
            command = [binary, "--untrusted", source.name]
        try:
            completed = subprocess.run(command, cwd=root, check=False, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise PreviewConversionError("LaTeX PDF 生成超时，请稍后重试") from error
        pdf_path = root / "resume.pdf"
        if not pdf_path.exists():
            detail = (completed.stderr or completed.stdout or "").strip()
            raise PreviewConversionError(f"LaTeX 未能生成 PDF{('：' + detail[:200]) if detail else ''}")
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


def _substitute_missing_cjk_fonts(docx_bytes: bytes) -> tuple[bytes, set[str]]:
    installed = _installed_font_families()
    if not installed:
        return docx_bytes, set()

    source = BytesIO(docx_bytes)
    output = BytesIO()
    changed = False
    preview_fonts: set[str] = set()
    with ZipFile(source) as archive, ZipFile(output, "w", ZIP_DEFLATED) as rewritten:
        for item in archive.infolist():
            payload = archive.read(item.filename)
            if item.filename.endswith(".xml"):
                payload, part_changed, part_fonts = _replace_missing_cjk_fonts_in_xml(payload, installed)
                changed = changed or part_changed
                preview_fonts.update(part_fonts)
            rewritten.writestr(item, payload)
    return (output.getvalue() if changed else docx_bytes), preview_fonts


def _installed_font_families() -> dict[str, str]:
    from shutil import which

    binary = which("fc-list")
    if binary is None:
        return {}
    try:
        completed = subprocess.run(
            [binary, "-f", "%{family}\\n"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    families: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        for alias in line.split(","):
            family = alias.strip()
            if family:
                families.setdefault(family.casefold(), family)
    return families


def _replace_missing_cjk_fonts_in_xml(
    payload: bytes,
    installed: dict[str, str],
) -> tuple[bytes, bool, set[str]]:
    try:
        root = etree.fromstring(payload)
    except etree.XMLSyntaxError:
        return payload, False, set()

    namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    east_asia = f"{{{namespace}}}eastAsia"
    font_attributes = [
        f"{{{namespace}}}ascii",
        f"{{{namespace}}}hAnsi",
        east_asia,
        f"{{{namespace}}}cs",
    ]
    changed = False
    preview_fonts: set[str] = set()
    for fonts in root.xpath(".//w:rFonts", namespaces={"w": namespace}):
        requested = fonts.get(east_asia)
        if not requested or requested.casefold() in installed:
            continue
        replacement = _cjk_fallback_font(requested, installed)
        if replacement is None:
            continue
        preview_fonts.add(replacement)
        for attribute in font_attributes:
            if fonts.get(attribute):
                fonts.set(attribute, replacement)
        changed = True
    if not changed:
        return payload, False, set()
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True), True, preview_fonts


def _cjk_fallback_font(requested: str, installed: dict[str, str]) -> str | None:
    serif = any(marker in requested.casefold() for marker in ("simsun", "song", "fang", "kai", "serif"))
    candidates = (
        ("Songti SC", "Noto Serif CJK SC", "Source Han Serif SC", "Arial Unicode MS", "PingFang SC")
        if serif
        else ("PingFang SC", "Hiragino Sans GB", "Sarasa Gothic SC", "Sarasa Fixed SC", "Noto Sans CJK SC", "Arial Unicode MS")
    )
    for candidate in candidates:
        available = installed.get(candidate.casefold())
        if available:
            return available
    return None


def _link_preview_fonts(profile: Path, families: set[str]) -> None:
    if not families:
        return
    font_directory = profile / "user" / "fonts"
    font_directory.mkdir(parents=True, exist_ok=True)
    for index, family in enumerate(sorted(families)):
        font_file = _font_file(family)
        if font_file is None:
            continue
        link = font_directory / f"{index}-{font_file.name}"
        try:
            link.symlink_to(font_file)
        except OSError:
            continue


def _font_file(family: str) -> Path | None:
    from shutil import which

    binary = which("fc-match")
    if binary is None:
        return None
    try:
        completed = subprocess.run(
            [binary, "-f", "%{file}", family],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    path = Path(completed.stdout.strip())
    return path if path.is_file() else None
