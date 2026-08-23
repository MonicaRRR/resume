from resume_mvp.domain import (
    Fact,
    JobAnalysis,
    JobRequirement,
    ResumeDocument,
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
    assert report.coverage == 0.67
