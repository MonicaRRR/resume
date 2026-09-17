from resume_mvp.domain import (
    EducationEntry,
    Fact,
    JobAnalysis,
    JobRequirement,
    MatchItem,
    MatchReport,
    ProjectEntry,
    ResumeDocument,
    SkillGroup,
    SourcedText,
)
from resume_mvp.evidence_match import merge_ai_and_rule_match


def test_rules_upgrade_education_when_ai_misses() -> None:
    resume = ResumeDocument.blank()
    resume.education = [
        EducationEntry(
            institution="示例大学",
            degree="本科",
            field="软件工程",
            end_date="2027.06",
        )
    ]
    analysis = JobAnalysis(
        requirements=[
            JobRequirement(
                id="edu",
                text="2027届应届生本科计算机相关专业",
                evidence_quote="27届本科",
                weight=1,
            )
        ]
    )
    ai = MatchReport(
        coverage=0,
        items=[
            MatchItem(
                requirement_id="edu",
                requirement=analysis.requirements[0].text,
                status="没有证据",
                weight=1,
            )
        ],
    )

    merged = merge_ai_and_rule_match(ai, analysis, resume, facts=[])

    assert merged.items[0].status == "已有证据"
    assert any("教育背景" in excerpt for excerpt in merged.items[0].excerpts)


def test_rules_do_not_upgrade_skill_list_without_practical_evidence() -> None:
    resume = ResumeDocument.blank()
    resume.skills = [SkillGroup(name="专业技能", items=[SourcedText(value="Python、FastAPI")])]
    analysis = JobAnalysis(
        requirements=[
            JobRequirement(id="py", text="熟悉 Python", evidence_quote="Python", weight=1),
        ]
    )
    ai = MatchReport(
        coverage=0.5,
        items=[
            MatchItem(
                requirement_id="py",
                requirement="熟悉 Python",
                status="证据较弱",
                excerpts=["做过一点开发"],
                weight=1,
            )
        ]
    )

    merged = merge_ai_and_rule_match(ai, analysis, resume, facts=[])

    assert merged.items[0].status == "证据较弱"


def test_ai_skill_only_strong_claim_is_downgraded() -> None:
    resume = ResumeDocument.blank()
    resume.skills = [SkillGroup(name="专业技能", items=[SourcedText(value="Python、FastAPI")])]
    fact = Fact(
        id="skill-fact",
        category="专业技能",
        statement="Python、FastAPI",
        source_type="manual",
        user_confirmed=True,
    )
    analysis = JobAnalysis(requirements=[
        JobRequirement(id="py", text="熟悉 Python", evidence_quote="Python", weight=1),
    ])
    ai = MatchReport(coverage=1, items=[
        MatchItem(
            requirement_id="py",
            requirement="熟悉 Python",
            status="已有证据",
            fact_ids=[fact.id],
            excerpts=["Python、FastAPI"],
            weight=1,
        )
    ])

    merged = merge_ai_and_rule_match(ai, analysis, resume, facts=[fact])

    assert merged.items[0].status == "证据较弱"
    assert "工作/项目" in merged.items[0].reason


def test_weak_status_keeps_or_fills_reason() -> None:
    resume = ResumeDocument.blank()
    resume.projects = [
        ProjectEntry(name="分析平台", bullets=[SourcedText(value="做过数据分析报表")])
    ]
    analysis = JobAnalysis(
        requirements=[
            JobRequirement(id="ml", text="熟悉机器学习落地", evidence_quote="机器学习", weight=1),
        ]
    )
    ai = MatchReport(
        coverage=0.5,
        items=[
            MatchItem(
                requirement_id="ml",
                requirement="熟悉机器学习落地",
                status="证据较弱",
                excerpts=["做过数据分析报表"],
                reason="仅写过数据分析，未写模型训练、评估指标或上线效果。",
                weight=1,
            )
        ],
    )

    merged = merge_ai_and_rule_match(ai, analysis, resume, facts=[])

    assert merged.items[0].status == "证据较弱"
    assert "数据分析" in merged.items[0].reason
    assert "模型" in merged.items[0].reason or "评估" in merged.items[0].reason or "上线" in merged.items[0].reason


def test_weak_without_reason_gets_fallback() -> None:
    resume = ResumeDocument.blank()
    resume.projects = [
        ProjectEntry(name="部署平台", bullets=[SourcedText(value="参与过容器化部署")])
    ]
    analysis = JobAnalysis(
        requirements=[
            JobRequirement(id="k8s", text="熟悉 Kubernetes", evidence_quote="K8s", weight=1),
        ]
    )
    ai = MatchReport(
        coverage=0.5,
        items=[
            MatchItem(
                requirement_id="k8s",
                requirement="熟悉 Kubernetes",
                status="证据较弱",
                excerpts=["参与过容器化部署"],
                weight=1,
            )
        ],
    )

    merged = merge_ai_and_rule_match(ai, analysis, resume, facts=[])

    assert merged.items[0].status == "证据较弱"
    assert merged.items[0].reason
    assert "间接" in merged.items[0].reason or "缺少" in merged.items[0].reason


def test_ai_strong_evidence_not_downgraded_by_rules() -> None:
    resume = ResumeDocument.blank()
    fact = Fact(id="f1", category="项目", statement="主导订单建模与抽象拆分", source_type="manual", user_confirmed=True)
    analysis = JobAnalysis(
        requirements=[
            JobRequirement(id="soft", text="具备业务抽象与建模能力", evidence_quote="业务抽象", weight=1),
        ]
    )
    ai = MatchReport(
        coverage=1,
        items=[
            MatchItem(
                requirement_id="soft",
                requirement="具备业务抽象与建模能力",
                status="已有证据",
                fact_ids=["f1"],
                excerpts=["主导订单建模与抽象拆分"],
                weight=1,
            )
        ]
    )

    merged = merge_ai_and_rule_match(ai, analysis, resume, facts=[fact])

    assert merged.items[0].status == "已有证据"
    assert merged.items[0].fact_ids == ["f1"]


def test_unverifiable_ai_excerpt_is_removed_and_cannot_support_a_match() -> None:
    resume = ResumeDocument.blank()
    analysis = JobAnalysis(requirements=[
        JobRequirement(id="k8s", text="熟悉 Kubernetes", evidence_quote="K8s", weight=1),
    ])
    ai = MatchReport(coverage=1, items=[
        MatchItem(
            requirement_id="k8s",
            requirement="熟悉 Kubernetes",
            status="已有证据",
            excerpts=["负责 Kubernetes 万节点集群并将故障率降低 80%"],
            weight=1,
        )
    ])

    merged = merge_ai_and_rule_match(ai, analysis, resume, facts=[])

    assert merged.items[0].status == "没有证据"
    assert merged.items[0].excerpts == []
    assert "无法" in merged.items[0].reason


def test_education_rule_can_downgrade_ai_when_one_hard_atom_fails() -> None:
    resume = ResumeDocument.blank()
    resume.education = [EducationEntry(
        institution="示例大学",
        degree="本科",
        field="计算机科学",
        end_date="2026-06",
    )]
    analysis = JobAnalysis(requirements=[JobRequirement(
        id="edu",
        text="2027届本科及以上学历，计算机相关专业",
        evidence_quote="2027届本科及以上学历",
    )])
    ai = MatchReport(coverage=1, items=[MatchItem(
        requirement_id="edu",
        requirement="2027届本科及以上学历，计算机相关专业",
        status="已有证据",
        excerpts=["示例大学，本科，计算机科学，2026-06"],
    )])

    merged = merge_ai_and_rule_match(ai, analysis, resume, facts=[])

    assert merged.items[0].status == "证据较弱"
    assert "部分条件" in merged.items[0].reason
