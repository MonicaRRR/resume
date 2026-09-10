from __future__ import annotations

from resume_mvp.ai_workflows import (
    _complete_with_repair,
    _ground_patch_operations,
    _prompt,
    _safe_resume,
)
from resume_mvp.domain import (
    ApplicationType,
    Fact,
    JobAnalysis,
    MatchReport,
    ResumeDocument,
    ResumePatch,
)
from resume_mvp.optimization_models import LayoutReport, OptimizationReview
from resume_mvp.providers.base import AIProvider


async def generate_optimization_patch(
    provider: AIProvider,
    analysis: JobAnalysis,
    match: MatchReport,
    resume: ResumeDocument,
    facts: list[Fact],
    application_type: ApplicationType,
    *,
    layout_report: LayoutReport | None,
    previous_review: OptimizationReview | None,
) -> ResumePatch:
    prompt = _writer_prompt(
        analysis,
        match,
        resume,
        facts,
        application_type,
        layout_report,
        previous_review,
    )
    patch = await _complete_with_repair(provider, prompt, ResumePatch)
    grounded = _ground_patch_operations(patch, resume=resume, facts=facts)
    allowed = {item.id for item in (layout_report.issues if layout_report else [])}
    operations = [
        op
        for op in grounded.operations
        if all(issue_id in allowed for issue_id in op.layout_issue_ids)
    ]
    return grounded.model_copy(update={"operations": operations})


async def review_optimization_candidate(
    provider: AIProvider,
    analysis: JobAnalysis,
    match: MatchReport,
    candidate: ResumeDocument,
    facts: list[Fact],
    layout_report: LayoutReport | None,
) -> OptimizationReview:
    prompt = _reviewer_prompt(analysis, match, candidate, facts, layout_report)
    return await _complete_with_repair(provider, prompt, OptimizationReview)


def _writer_prompt(
    analysis: JobAnalysis,
    match: MatchReport,
    resume: ResumeDocument,
    facts: list[Fact],
    application_type: ApplicationType,
    layout_report: LayoutReport | None,
    previous_review: OptimizationReview | None,
) -> str:
    page_constraint = (
        "校招/实习最终不得超过一页；优先压缩低信息表述与短尾行，禁止为填版面无意义扩写。"
        if application_type in {"campus", "internship"}
        else "社招允许自然分页；优先消除孤立标题、稀疏末页和短尾行，禁止无意义扩写。"
    )
    return _prompt(
        task="基于事实、JD 匹配与真实排版问题，生成局部简历优化建议",
        constraints=[
            "只输出局部修改操作，不覆盖整份简历",
            "只能改写、重排或压缩已有内容；不能创造公司、职位、项目、数字、证书或技能",
            "必须保留相关数字、成果、技术栈和有用的 JD 关键词",
            "优先删除低信息密度措辞、合并重复职责或重组句式；禁止为填充版面而无意义扩写",
            "每条操作必须引用 source_fact_ids，且只能使用输入 facts / allowed_fact_ids",
            "若修改由版面触发，必须填写 layout_issue_ids 与 expected_layout_benefit，且只能引用 layout_report.issues 中已有 id",
            "before 必须与输入简历当前值一致；after 保持同一 JSON 结构",
            "不要修改姓名、性别、生日、电话、邮箱、微信、住址、政治面貌或证件照",
            "不要自动应用任何修改——输出仅供后续审查与用户确认",
            page_constraint,
        ],
        data={
            "application_type": application_type,
            "job_analysis": analysis.model_dump(mode="json"),
            "match_report": match.model_dump(mode="json"),
            "resume": _safe_resume(resume),
            "facts": [fact.model_dump(mode="json") for fact in facts],
            "allowed_fact_ids": [fact.id for fact in facts],
            "layout_report": layout_report.model_dump(mode="json") if layout_report else None,
            "previous_review": previous_review.model_dump(mode="json") if previous_review else None,
        },
    )


def _reviewer_prompt(
    analysis: JobAnalysis,
    match: MatchReport,
    candidate: ResumeDocument,
    facts: list[Fact],
    layout_report: LayoutReport | None,
) -> str:
    return _prompt(
        task="独立审查候选简历优化结果，只给评分与返工指令",
        constraints=[
            "你是独立审查者，不能直接生成替换文本",
            "只返回 factuality_passed、expression_score、requires_user_input、questions、rejection_reasons、refinement_instructions",
            "检查是否存在编造、夸大或无法追溯的表述",
            "检查是否遗漏重要经历或高权重 JD 要求",
            "检查中文表达是否简洁、具体且无重复",
            "检查是否仍有严重排版问题，以及是否满足求职类型的页数策略",
            "若需要用户补充事实，设置 requires_user_input=true 并给出 questions",
            "不要输出修改后的简历正文、after 文本或补丁操作",
        ],
        data={
            "job_analysis": analysis.model_dump(mode="json"),
            "match_report": match.model_dump(mode="json"),
            "candidate_resume": _safe_resume(candidate),
            "facts": [
                {
                    "id": fact.id,
                    "category": fact.category,
                    "statement": fact.statement,
                }
                for fact in facts
            ],
            "layout_report": layout_report.model_dump(mode="json") if layout_report else None,
        },
    )
