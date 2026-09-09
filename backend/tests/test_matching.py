from resume_mvp.domain import (
    EducationEntry,
    Fact,
    JobAnalysis,
    JobRequirement,
    ProjectEntry,
    ResumeDocument,
    SkillGroup,
    SourcedText,
    WorkExperienceEntry,
)
from resume_mvp.matching import calculate_match


def test_match_report_links_requirements_to_facts() -> None:
    """Catches coverage labels that cannot show the evidence behind them."""
    fact = Fact(
        id="fact-python",
        category="工作经历",
        statement="使用 Python 开发订单 API",
        source_type="manual",
        user_confirmed=True,
    )
    resume = ResumeDocument(
        work_experience=[
            WorkExperienceEntry(
                company="示例科技",
                title="后端工程师",
                bullets=[
                    SourcedText(
                        value="使用 Python 开发订单 API",
                        source_fact_ids=[fact.id],
                        origin="manual",
                    )
                ],
            )
        ]
    )
    analysis = JobAnalysis(
        role_title="后端工程师",
        requirements=[
            JobRequirement(
                id="req-python",
                text="Python API 开发",
                evidence_quote="负责 Python API 开发",
                weight=2,
            ),
            JobRequirement(
                id="req-k8s",
                text="Kubernetes",
                evidence_quote="熟悉 Kubernetes",
                weight=1,
            ),
        ],
    )

    report = calculate_match(analysis, resume, [fact])

    assert report.items[0].status == "已有证据"
    assert report.items[0].fact_ids == [fact.id]
    assert report.items[1].status == "没有证据"
    assert report.items[1].reason
    assert report.coverage == 0.67


def test_match_uses_resume_skills_even_without_facts() -> None:
    """Catches false '没有证据' when skills exist only on the resume body."""
    resume = ResumeDocument.blank()
    resume.skills = [
        SkillGroup(
            name="专业技能",
            items=[SourcedText(value="后端：Python、FastAPI、PostgreSQL")],
        )
    ]
    analysis = JobAnalysis(
        requirements=[
            JobRequirement(id="r1", text="熟悉 Python", evidence_quote="熟悉 Python", weight=1),
            JobRequirement(id="r2", text="PostgreSQL", evidence_quote="熟悉 PostgreSQL", weight=1),
            JobRequirement(id="r3", text="Kubernetes", evidence_quote="熟悉 K8s", weight=1),
        ]
    )

    report = calculate_match(analysis, resume, facts=[])

    assert report.items[0].status == "已有证据"
    assert report.items[1].status == "已有证据"
    assert report.items[2].status == "没有证据"
    assert "Python" in report.items[0].excerpts[0] or "后端" in report.items[0].excerpts[0]


def test_match_aliases_k8s_to_kubernetes_in_project_bullets() -> None:
    resume = ResumeDocument.blank()
    resume.projects = [
        ProjectEntry(
            name="平台化",
            role="开发",
            bullets=[SourcedText(value="基于 Kubernetes 部署微服务并做滚动发布")],
        )
    ]
    analysis = JobAnalysis(
        requirements=[
            JobRequirement(id="r1", text="熟悉 K8s", evidence_quote="熟悉 K8s 与容器化", weight=1),
        ]
    )

    report = calculate_match(analysis, resume, facts=[])

    assert report.items[0].status == "已有证据"
    assert "Kubernetes" in report.items[0].excerpts[0]


def test_match_education_eligibility_against_education_background() -> None:
    resume = ResumeDocument.blank()
    resume.education = [
        EducationEntry(
            institution="示例大学",
            degree="本科",
            field="计算机科学与技术",
            start_date="2023.09",
            end_date="2027.06",
        )
    ]
    analysis = JobAnalysis(
        requirements=[
            JobRequirement(
                id="edu",
                text="2026年9月-2027年8月毕业的27届应届生/本科及以上学历，计算机、软件工程、人工智能等相关专业",
                evidence_quote="27届应届生，本科及以上，计算机相关专业",
                weight=2,
            )
        ]
    )

    report = calculate_match(analysis, resume, facts=[])

    assert report.items[0].status == "已有证据"
    assert "教育背景" in report.items[0].excerpts[0]
    assert "计算机" in report.items[0].excerpts[0]


def test_soft_business_design_requirement_is_not_hard_miss() -> None:
    resume = ResumeDocument.blank()
    resume.projects = [
        ProjectEntry(name="订单中心", role="后端", bullets=[SourcedText(value="完成下单链路改造")])
    ]
    analysis = JobAnalysis(
        requirements=[
            JobRequirement(
                id="soft",
                text="能面向业务问题设计技术方案",
                evidence_quote="具备业务理解与方案设计能力",
                weight=1,
            )
        ]
    )

    report = calculate_match(analysis, resume, facts=[])

    assert report.items[0].status == "软性要求"
    assert "软性要求" in report.items[0].excerpts[0]
    assert "软性" in report.items[0].reason
    assert report.coverage >= 0.7


def test_fullstack_and_polyglot_requirements_use_stack_signals() -> None:
    resume = ResumeDocument.blank()
    resume.skills = [
        SkillGroup(
            name="专业技能",
            items=[
                SourcedText(value="后端：Python、Go、FastAPI"),
                SourcedText(value="前端：React、TypeScript"),
            ],
        )
    ]
    resume.projects = [
        ProjectEntry(
            name="校园通",
            role="全栈开发",
            bullets=[SourcedText(value="用 Python 与 React 完成前后端联调")],
        )
    ]
    analysis = JobAnalysis(
        requirements=[
            JobRequirement(
                id="cap",
                text="能够接受跨语言、全栈化开发",
                evidence_quote="跨语言、全栈化开发",
                weight=1,
            )
        ]
    )

    report = calculate_match(analysis, resume, facts=[])

    assert report.items[0].status == "已有证据"
    assert any(
        "能力匹配" in excerpt or "全栈" in excerpt or "跨语言" in excerpt
        for excerpt in report.items[0].excerpts
    )
