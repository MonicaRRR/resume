from resume_mvp.domain import EducationEntry, ResumeDocument, SourcedText
from resume_mvp.latex import build_latex


def test_latex_keeps_chinese_and_escapes_user_text() -> None:
    resume = ResumeDocument.blank()
    resume.basics.name = "张宁 & 研发"
    resume.basics.summary = SourcedText(value=r"熟悉 C++_Python 90% #1")

    source = build_latex(resume, "clear-single", "experienced")

    assert "张宁 \\& 研发" in source
    assert r"C++\_Python 90\% \#1" in source
    assert "\\documentclass" in source
    assert "\\usepackage[UTF8]" in source


def test_latex_renders_education_fields_and_highlights() -> None:
    resume = ResumeDocument.blank()
    resume.basics.name = "李明"
    resume.education = [
        EducationEntry(
            institution="清华大学",
            degree="本科",
            field="计算机科学与技术",
            start_date="2020.09",
            end_date="2024.06",
            highlights=[SourcedText(value="专业排名前 10%")],
        )
    ]

    source = build_latex(resume, "classic-cn", "campus")

    assert "\\section*{教育经历}" in source
    assert "清华大学" in source
    assert "本科" in source
    assert "2020.09 -- 2024.06" in source
    assert "专业排名前 10\\%" in source


def test_latex_campus_and_internship_use_compact_one_page_options() -> None:
    resume = ResumeDocument.blank()

    campus = build_latex(resume, "clear-single", "campus")
    experienced = build_latex(resume, "clear-single", "experienced")

    assert "10pt" not in campus.split("\\begin{document}", 1)[0]
    assert "9pt" in campus.split("\\begin{document}", 1)[0]
    assert "1.2cm" in campus
    assert "11pt" in experienced.split("\\begin{document}", 1)[0]


def test_overleaf_template_uses_supplied_class_and_macros() -> None:
    resume = ResumeDocument.blank()
    resume.basics.name = "张三"
    resume.education = [EducationEntry(institution="示例大学", degree="本科", field="软件工程")]
    source = build_latex(resume, "overleaf-cn", "campus")
    assert "\\documentclass{setting}" in source
    assert "\\logosection{\\faGraduationCap}{教育经历}" in source
    assert "\\datedline" in source
