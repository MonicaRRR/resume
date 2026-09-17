"""AI evidence matching + merge with deterministic hard-skill/education rules."""

from __future__ import annotations

from resume_mvp.ai_workflows import (
    _complete_with_repair,
    _experience_inventory,
    _prompt,
    _safe_resume,
)
from resume_mvp.domain import Fact, JobAnalysis, JobRequirement, MatchItem, MatchReport, ResumeDocument
from resume_mvp.matching import _collect_evidence, _normalize, calculate_match
from resume_mvp.providers.base import AIProvider


_STATUS_RANK = {
    "没有证据": 0,
    "证据较弱": 1,
    "软性要求": 2,
    "已有证据": 3,
}


async def analyze_evidence_match(
    provider: AIProvider,
    analysis: JobAnalysis,
    resume: ResumeDocument,
    facts: list[Fact],
) -> MatchReport:
    """Ask the model to map each JD requirement to resume/fact evidence."""
    fact_catalog = [
        {"id": fact.id, "category": fact.category, "statement": fact.statement}
        for fact in facts
    ]
    prompt = _prompt(
        task="对照用户简历与事实库，为每条 JD 要求做证据匹配（不改简历）",
        constraints=[
            "仅使用中文",
            "必须为 job_analysis.requirements 中每一条输出一个 items 元素，requirement_id 必须与要求 id 一致",
            "status 只能是：已有证据 / 证据较弱 / 没有证据 / 软性要求",
            "已有证据：简历或事实中能直接或较强对应；excerpts 摘录原文，fact_ids 只能来自 allowed_fact_ids；reason 可简述为何匹配",
            "证据较弱：有间接相关经历但表述不完全对齐；必须写 reason，说明「已有什么相关内容」以及「还缺什么才够硬」",
            "没有证据：确实找不到可核对内容；reason 说明缺哪类经历/技能",
            "专业技能栏只能视为自报能力，不能单独支撑「已有证据」；若只在技能栏命中，最多标为「证据较弱」，并说明还缺工作/项目中的使用场景、行动和结果",
            "判断实践能力时优先引用工作/实习/项目要点；只有这些经历能直接对应要求时，才可标为「已有证据」",
            "软性要求：业务抽象/建模/沟通/学习能力/方案设计等素质项，简历很少逐字出现——不要轻易标没有证据；标软性要求，reason 说明为何属软性、可如何在项目要点中间接体现",
            "禁止编造公司、项目、数字或技能；excerpts 必须能在 resume 或 facts 中找到依据（允许轻微截断）",
            "weight 使用对应要求的 weight",
            "coverage 先可粗估，服务端会按 status 重算",
        ],
        data={
            "job_analysis": analysis.model_dump(mode="json"),
            "resume": _safe_resume(resume),
            "experience_inventory": _experience_inventory(resume),
            "facts": [fact.model_dump(mode="json") for fact in facts],
            "allowed_fact_ids": [fact.id for fact in facts],
            "fact_catalog": fact_catalog,
        },
    )
    ai_report = await _complete_with_repair(provider, prompt, MatchReport)
    return merge_ai_and_rule_match(ai_report, analysis, resume, facts)


def merge_ai_and_rule_match(
    ai_report: MatchReport,
    analysis: JobAnalysis,
    resume: ResumeDocument,
    facts: list[Fact],
) -> MatchReport:
    """AI first; deterministic rules can upgrade education / skill / stack hard hits."""
    rules = calculate_match(analysis, resume, facts)
    rule_by_id = {item.requirement_id: item for item in rules.items}
    ai_by_id = {item.requirement_id: item for item in ai_report.items}
    allowed_facts = {fact.id for fact in facts}

    merged_items: list[MatchItem] = []
    for requirement in analysis.requirements:
        ai_item = ai_by_id.get(requirement.id)
        rule_item = rule_by_id.get(requirement.id)
        base = ai_item or MatchItem(
            requirement_id=requirement.id,
            requirement=requirement.text,
            status="没有证据",
            weight=requirement.weight,
        )
        item = _normalize_ai_item(base, requirement, allowed_facts, resume, facts)
        item = _downgrade_skill_only_item(item, resume, facts)
        if rule_item is not None:
            item = _merge_with_rule(item, rule_item, requirement)
        merged_items.append(item)

    return MatchReport(coverage=_coverage(merged_items), items=merged_items)


def _normalize_ai_item(
    item: MatchItem,
    requirement: JobRequirement,
    allowed_facts: set[str],
    resume: ResumeDocument,
    facts: list[Fact],
) -> MatchItem:
    status = item.status if item.status in _STATUS_RANK else "没有证据"
    fact_ids = [fact_id for fact_id in item.fact_ids if fact_id in allowed_facts]
    source_snippets = _collect_evidence(resume, facts)
    normalized_sources = [_normalize(snippet.text) for snippet in source_snippets]
    excerpts = []
    for text in item.excerpts:
        cleaned = text.strip()
        normalized = _normalize(cleaned)
        if not normalized:
            continue
        # The model may trim punctuation/whitespace, but may not embellish the
        # source.  Keep only spans that can be found in a real resume/fact item.
        if any(normalized in source for source in normalized_sources):
            excerpts.append(cleaned)
        if len(excerpts) == 4:
            break

    grounded = bool(excerpts or fact_ids)
    if status in {"已有证据", "证据较弱"} and not grounded:
        status = "没有证据"
    reason = (item.reason or "").strip()
    if item.status in {"已有证据", "证据较弱"} and not grounded:
        reason = "模型返回的证据摘录无法在当前简历或事实库中定位，已按无可核验证据处理。"
    if status == "证据较弱" and not reason:
        if excerpts:
            reason = f"仅有间接相关表述（如「{excerpts[0][:40]}」），尚未写清与该要求的直接对应关系或可验证结果。"
        else:
            reason = "有零散相关信号，但缺少可核对的直接经历描述或结果证据。"
    if status == "没有证据" and not reason:
        reason = "简历与事实库中未找到可核对的对应经历或技能。"
    if status == "软性要求" and not reason:
        reason = "属素质/方法论类软性要求，简历很少逐字出现；可在项目要点中补业务问题、假设与验证路径。"
    return MatchItem(
        requirement_id=requirement.id,
        requirement=requirement.text,
        status=status,
        fact_ids=list(dict.fromkeys(fact_ids)),
        excerpts=excerpts,
        reason=reason,
        weight=requirement.weight,
    )


def _downgrade_skill_only_item(
    item: MatchItem,
    resume: ResumeDocument,
    facts: list[Fact],
) -> MatchItem:
    """A skills-list claim alone is self-report, not demonstrated practice."""
    if item.status != "已有证据":
        return item
    experience_fact_ids = {
        fact.id
        for fact in facts
        if any(marker in fact.category for marker in ("工作", "实习", "项目"))
    }
    if any(fact_id in experience_fact_ids for fact_id in item.fact_ids):
        return item

    experience_texts = [
        text.strip()
        for text in [
            *(
                f"{entry.company} {entry.title}"
                for entry in resume.work_experience
            ),
            *(
                bullet.value
                for entry in resume.work_experience
                for bullet in entry.bullets
            ),
            *(
                f"{entry.name} {entry.role}"
                for entry in resume.projects
            ),
            *(
                bullet.value
                for entry in resume.projects
                for bullet in entry.bullets
            ),
        ]
        if text.strip()
    ]
    for excerpt in item.excerpts:
        if any(excerpt in text or text in excerpt for text in experience_texts):
            return item

    skill_fact_ids = {fact.id for fact in facts if "技能" in fact.category}
    skill_texts = [
        skill.value.strip()
        for group in resume.skills
        for skill in group.items
        if skill.value.strip()
    ]
    fact_evidence_is_skill_only = bool(item.fact_ids) and all(
        fact_id in skill_fact_ids for fact_id in item.fact_ids
    )
    excerpt_evidence_is_skill_only = bool(item.excerpts) and all(
        any(excerpt in text or text in excerpt for text in skill_texts)
        for excerpt in item.excerpts
    )
    if not fact_evidence_is_skill_only and not excerpt_evidence_is_skill_only:
        return item
    return item.model_copy(update={
        "status": "证据较弱",
        "reason": "目前只在专业技能栏发现自报能力，尚缺工作/项目中的使用场景、行动和结果证据。",
    })


def _merge_with_rule(
    ai_item: MatchItem,
    rule_item: MatchItem,
    requirement: JobRequirement,
) -> MatchItem:
    req_text = f"{requirement.text} {requirement.evidence_quote}"
    hard = _is_hard_rule_domain(req_text)
    if not hard:
        # Soft domains: if AI missed entirely but rules tagged soft, keep soft.
        if ai_item.status == "没有证据" and rule_item.status == "软性要求":
            return rule_item.model_copy(
                update={
                    "requirement_id": requirement.id,
                    "requirement": requirement.text,
                    "weight": requirement.weight,
                    "reason": rule_item.reason
                    or ai_item.reason
                    or "属素质/方法论类软性要求，简历很少逐字出现；可在项目要点中补业务问题、假设与验证路径。",
                }
            )
        return ai_item

    is_education_gate = any(
        marker in req_text
        for marker in ("学历", "应届", "届", "毕业", "本科", "硕士", "博士", "专业")
    )
    if is_education_gate and _STATUS_RANK[rule_item.status] < _STATUS_RANK[ai_item.status]:
        # Eligibility rules are authoritative and conjunctive.  An AI semantic
        # hit cannot compensate for a failed graduation, degree, or major atom.
        return rule_item.model_copy(update={
            "requirement_id": requirement.id,
            "requirement": requirement.text,
            "weight": requirement.weight,
        })

    if _STATUS_RANK[rule_item.status] <= _STATUS_RANK[ai_item.status]:
        # Rules weaker or equal — keep AI, maybe fill empty excerpts.
        if ai_item.excerpts or not rule_item.excerpts:
            return ai_item
        return ai_item.model_copy(update={"excerpts": rule_item.excerpts[:3]})

    # Rules stronger on hard domain — upgrade status / evidence.
    excerpts = rule_item.excerpts or ai_item.excerpts
    fact_ids = list(dict.fromkeys([*rule_item.fact_ids, *ai_item.fact_ids]))
    reason = ai_item.reason
    if rule_item.status == "已有证据":
        reason = rule_item.reason or "规则命中学历/技能/技术栈等硬条件，已提升为已有证据。"
    elif rule_item.status == "证据较弱" and not reason:
        reason = rule_item.reason or "规则仅部分命中相关信号，证据仍偏弱。"
    return MatchItem(
        requirement_id=requirement.id,
        requirement=requirement.text,
        status=rule_item.status,
        fact_ids=fact_ids,
        excerpts=excerpts[:4],
        reason=reason,
        weight=requirement.weight,
    )


def _is_hard_rule_domain(text: str) -> bool:
    if any(marker in text for marker in ("学历", "应届", "届", "毕业", "本科", "硕士", "博士", "专业")):
        return True
    if any(marker in text.lower() for marker in ("全栈", "跨语言", "fullstack", "polyglot", "前后端")):
        return True
    # Concrete tech tokens — rules are good at these.
    tech_markers = (
        "python", "java", "go", "golang", "react", "vue", "typescript", "javascript",
        "kubernetes", "k8s", "docker", "mysql", "postgresql", "redis", "fastapi",
        "django", "spring", "linux", "sql", "api",
    )
    lowered = text.lower()
    return any(marker in lowered for marker in tech_markers)


def _coverage(items: list[MatchItem]) -> float:
    total = sum(item.weight for item in items)
    if not total:
        return 0.0
    score = 0.0
    for item in items:
        if item.status == "已有证据":
            score += item.weight
        elif item.status == "软性要求":
            score += item.weight * 0.75
        elif item.status == "证据较弱":
            score += item.weight * 0.5
    return round(score / total, 2)
