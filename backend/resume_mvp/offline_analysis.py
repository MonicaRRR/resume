from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any

from resume_mvp.domain import (
    ExperienceAsk,
    FollowupQuestion,
    JobAnalysis,
    JobRequirement,
    MatchReport,
    PatchDiscussionResult,
    PracticeEvaluation,
    PracticeFeedback,
    PracticeQuestion,
    QuestionList,
    ResumeDocument,
    ResumePatch,
    ResumePatchOperation,
)
from resume_mvp.matching import calculate_match
from resume_mvp.optimization_models import OptimizationReview


_TECH_TERMS = (
    "Python", "Java", "Golang", "Go", "C++", "JavaScript", "TypeScript", "React", "Vue",
    "FastAPI", "Django", "Spring", "MySQL", "PostgreSQL", "Redis", "MongoDB", "SQL",
    "Docker", "Kubernetes", "K8s", "Linux", "Git", "API", "微服务", "机器学习", "深度学习",
    "数据分析", "数据仓库", "大模型", "LLM", "NLP", "计算机视觉",
)
_RESPONSIBILITY_MARKERS = ("负责", "参与", "完成", "设计", "开发", "维护", "建设", "推动", "支持")
_REQUIREMENT_MARKERS = (
    "要求", "熟悉", "掌握", "具备", "经验", "能力", "优先", "本科", "硕士", "博士",
    "年以上", "应届", "专业", "能够", "善于",
)
_SOFT_MARKERS = ("沟通", "协作", "责任心", "学习能力", "抗压", "主动", "逻辑", "表达")


def prompt_payload(prompt: str) -> dict[str, Any]:
    for marker in ("输入数据：\n", "输入："):
        if marker not in prompt:
            continue
        candidate = prompt.split(marker, 1)[1].splitlines()[0].strip()
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def analyze_job_description(company_name: str, job_description: str) -> JobAnalysis:
    del company_name
    lines = _segments(job_description)
    title = _role_title(job_description, lines)
    responsibilities = _unique(
        line for line in lines if any(marker in line for marker in _RESPONSIBILITY_MARKERS)
    )[:8]
    requirement_lines = _unique(
        line for line in lines if any(marker in line for marker in _REQUIREMENT_MARKERS)
    )
    if not requirement_lines:
        requirement_lines = responsibilities or lines[:6]

    requirements: list[JobRequirement] = []
    for index, line in enumerate(requirement_lines[:12]):
        weight = 1.0
        if any(marker in line for marker in ("必须", "至少", "年以上", "本科", "硕士", "博士")):
            weight = 2.0
        elif "优先" in line or "加分" in line:
            weight = 0.75
        requirements.append(
            JobRequirement(
                id=_stable_id("req", line, index),
                text=line,
                evidence_quote=line,
                weight=weight,
            )
        )

    keywords = _extract_keywords(job_description)
    bonus = [line for line in lines if "优先" in line or "加分" in line][:5]
    topics = keywords[:5] or [item.text[:30] for item in requirements[:5]]
    return JobAnalysis(
        role_title=title,
        seniority=_seniority(job_description),
        responsibilities=responsibilities,
        requirements=requirements,
        bonus_skills=bonus,
        keywords=keywords,
        interview_topics=topics,
        written_topics=topics,
    )


def match_resume(analysis: JobAnalysis, resume: ResumeDocument, facts: list[dict[str, Any]]) -> MatchReport:
    from resume_mvp.domain import Fact

    return calculate_match(
        analysis,
        resume,
        [Fact.model_validate(item) for item in facts],
    )


def followup_questions(
    analysis: JobAnalysis,
    resume: ResumeDocument,
    facts: list[dict[str, Any]],
) -> QuestionList:
    report = match_resume(analysis, resume, facts)
    questions: list[FollowupQuestion] = []
    for item in sorted(report.items, key=lambda value: value.weight, reverse=True):
        if item.status == "已有证据":
            continue
        existing = f"当前相关线索：{item.excerpts[0][:60]}。" if item.excerpts else ""
        questions.append(
            FollowupQuestion(
                id=_stable_id("question", item.requirement_id),
                question=f"你是否有能证明「{item.requirement}」的工作或项目经历？具体做了什么、结果如何？",
                topic=item.requirement[:30],
                requirement_id=item.requirement_id,
                rationale=f"{existing}该要求目前为「{item.status}」，需要可核对的经历证据。",
                guidance="可从职责边界、使用方法、项目规模、问题与结果中选择你确实做过的内容回答；没有可跳过。",
                skippable=True,
            )
        )
        if len(questions) == 5:
            break
    if not questions and analysis.requirements:
        requirement = max(analysis.requirements, key=lambda item: item.weight)
        questions.append(
            FollowupQuestion(
                id=_stable_id("question", requirement.id),
                question=f"围绕「{requirement.text}」，哪段现有经历最能代表你的贡献？",
                topic=requirement.text[:30],
                requirement_id=requirement.id,
                rationale="帮助把已有证据讲得更具体，不新增事实。",
                guidance="说明情境、你的行动和已有结果；仅填写真实发生过的内容。",
            )
        )
    return QuestionList(items=questions)


def resume_patch(
    analysis: JobAnalysis,
    resume: ResumeDocument,
    facts: list[dict[str, Any]],
    *,
    application_type: str = "experienced",
) -> ResumePatch:
    payload = resume.model_dump(mode="json")
    operations: list[ResumePatchOperation] = []
    allowed_ids = {str(item.get("id")) for item in facts if item.get("id")}
    terms = _analysis_terms(analysis)

    for root in ("work_experience", "projects"):
        entries = payload.get(root, [])
        ranked = sorted(
            enumerate(entries),
            key=lambda pair: (-_keyword_score(json.dumps(pair[1], ensure_ascii=False), terms), pair[0]),
        )
        reordered = [entry for _, entry in ranked]
        if reordered != entries:
            cited = _fact_ids(reordered) & allowed_ids
            operations.append(
                ResumePatchOperation(
                    id=_stable_id("op", root, "reorder"),
                    op="reorder",
                    path=f"/{root}",
                    before=entries,
                    after=reordered,
                    reason="按 JD 关键词命中度将相关经历前置；只调整顺序，不改动事实。",
                    jd_requirement_ids=_matched_requirement_ids(analysis, reordered),
                    source_fact_ids=sorted(cited),
                    risk="low",
                )
            )

    # Reorder clauses inside a single bullet when that exposes existing JD evidence.
    for root in ("work_experience", "projects"):
        for entry_index, entry in enumerate(payload.get(root, [])):
            for bullet_index, bullet in enumerate(entry.get("bullets", [])):
                value = str(bullet.get("value") or "")
                reordered_value = _prioritize_clauses(value, terms)
                if reordered_value == value:
                    continue
                cited = set(bullet.get("source_fact_ids") or []) & allowed_ids
                if not cited:
                    cited = _matching_fact_ids(value, facts)
                if not cited:
                    continue
                after = {**bullet, "value": reordered_value, "source_fact_ids": sorted(cited), "origin": "ai_rewrite"}
                operations.append(
                    ResumePatchOperation(
                        id=_stable_id("op", root, entry_index, bullet_index),
                        path=f"/{root}/{entry_index}/bullets/{bullet_index}",
                        before=bullet,
                        after=after,
                        reason="把原句中与 JD 直接相关的内容前置；保留原有措辞、数字和事实。",
                        jd_requirement_ids=_matched_requirement_ids(analysis, [value]),
                        source_fact_ids=sorted(cited),
                        risk="low",
                    )
                )
                if len(operations) >= 8:
                    break

    asks: list[ExperienceAsk] = []
    if len(resume.projects) <= 2:
        hints = analysis.keywords[:4] or [analysis.role_title or "目标岗位"]
        asks.append(
            ExperienceAsk(
                id=_stable_id("ask", *hints),
                question=f"是否还有与「{'、'.join(hints)}」相关、但尚未录入的真实项目或工作专项？",
                guidance="只补充确实发生过的经历；可回忆职责、方法、规模和结果，没有可跳过。",
                jd_keywords=hints,
            )
        )

    # Campus/internship output is intentionally conservative: priority operations
    # help one-page selection, but rules never delete evidence without consent.
    if application_type in {"campus", "internship"}:
        for operation in operations:
            operation.reason += " 一页版应优先保留这些高相关内容，低相关内容仅建议用户审阅后移出。"
    return ResumePatch(operations=operations, experience_asks=asks)


def practice_question(data: dict[str, Any]) -> PracticeQuestion:
    analysis = JobAnalysis.model_validate(data.get("job_analysis") or {})
    resume = ResumeDocument.model_validate(data.get("resume") or {})
    requirement = max(analysis.requirements, key=lambda item: item.weight, default=None)
    fact_ids = sorted(_fact_ids(resume.model_dump(mode="json")))
    if requirement:
        prompt = f"请结合你简历中的真实经历，说明你如何满足「{requirement.text}」。"
        requirement_ids = [requirement.id]
        category = "经历深挖" if resume.work_experience or resume.projects else "专业题"
    else:
        prompt = f"请说明你为什么适合{analysis.role_title or '这个岗位'}，并只引用简历中的真实经历。"
        requirement_ids = []
        category = "岗位动机"
    return PracticeQuestion(
        id=_stable_id("practice", prompt),
        category=category,
        prompt=prompt,
        hint="可按情境—任务—行动—结果组织；没有的数据不要补写。",
        requirement_ids=requirement_ids,
        fact_ids=fact_ids[:5],
    )


def evaluate_practice(data: dict[str, Any]) -> PracticeEvaluation:
    question = PracticeQuestion.model_validate(data.get("question") or {})
    answer = str(data.get("answer") or "").strip()
    concrete = bool(re.search(r"\d|通过|使用|负责|设计|开发|优化|解决|完成", answer))
    structured = len(re.split(r"[。；\n]", answer)) >= 3
    relevant_terms = _tokens(question.prompt)
    relevant = any(token.lower() in answer.lower() for token in relevant_terms)
    dimensions = {
        "相关性": "回答提及了题目中的岗位要求。" if relevant else "尚未直接回应题目中的岗位要求。",
        "具体性": "包含具体行动或结果线索。" if concrete else "可补充你真实采取的行动与已有结果。",
        "证据": "回答提供了可继续核对的经历线索。" if concrete else "当前表述偏概括，尚缺可核对的经历细节。",
        "结构": "回答有较清晰的分段或叙事顺序。" if structured else "可按情境—任务—行动—结果重新组织。",
        "表达": "表述完整且较简洁。" if 20 <= len(answer) <= 500 else "建议控制篇幅并使用完整句子。",
    }
    weaknesses = [name for name, text in dimensions.items() if text.startswith(("尚", "可", "当前", "建议"))]
    summary = "回答基于你提交的内容进行规则检查，" + ("已有具体证据线索。" if concrete else "下一步应补充真实行动与结果。")
    return PracticeEvaluation(
        feedback=PracticeFeedback(
            dimensions=dimensions,
            summary=summary,
            improved_answer="",
            weaknesses=weaknesses,
        ),
        explanation="规则模式只检查相关词、具体行动线索与结构，不生成或代写新事实。",
        follow_up=f"你能补充一个与「{question.prompt[:35]}」直接相关、确实发生过的行动或结果吗？",
        next_question=None,
    )


def optimization_review() -> OptimizationReview:
    return OptimizationReview(
        factuality_passed=True,
        expression_score=85,
        requires_user_input=False,
        rejection_reasons=[],
        refinement_instructions=[],
    )


def discuss_patch(data: dict[str, Any]) -> PatchDiscussionResult:
    operation = data.get("current_operation") or {}
    message = str(data.get("user_message") or "")
    return PatchDiscussionResult(
        reply=(
            "规则模式不会根据自由文本生成新的改写。当前建议只重排已有事实；"
            f"已记录你的意见「{message[:80]}」，你可以保留原文或直接不采用该建议。"
        ),
        proposes_change=False,
        draft_operation=None,
    )


def _segments(text: str) -> list[str]:
    cleaned = re.sub(r"\r\n?", "\n", text)
    parts = re.split(r"[\n。；;]+|(?=\d+[.、]\s*)", cleaned)
    return _unique(re.sub(r"^[\s\-*•·\d.、（）()]+", "", part).strip(" ：:") for part in parts)[:30]


def _role_title(text: str, lines: list[str]) -> str:
    patterns = (
        r"(?:职位|岗位|招聘岗位|岗位名称|职位名称)\s*[：:]\s*([^\n，。；]{2,30})",
        r"招聘\s*([^\n，。；]{2,20}(?:工程师|经理|专员|设计师|分析师|顾问|实习生))",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    for line in lines[:4]:
        match = re.search(r"([\w\u4e00-\u9fff+/#-]{2,24}(?:工程师|经理|专员|设计师|分析师|顾问|实习生))", line)
        if match:
            return match.group(1)
    return ""


def _seniority(text: str) -> str:
    match = re.search(r"(\d+\s*[-—~至]\s*\d+\s*年|\d+\s*年以上|应届|实习)", text)
    return match.group(1).replace(" ", "") if match else ""


def _extract_keywords(text: str) -> list[str]:
    found = [term for term in _TECH_TERMS if re.search(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", text, re.I)]
    degree = [term for term in ("博士", "硕士", "本科", "应届") if term in text]
    return _unique([*found, *degree])[:15]


def _analysis_terms(analysis: JobAnalysis) -> list[str]:
    values = [*analysis.keywords]
    for requirement in analysis.requirements:
        values.extend(_tokens(requirement.text))
    return _unique(value for value in values if len(value) >= 2)[:40]


def _tokens(text: str) -> list[str]:
    latin = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", text)
    known = [term for term in _TECH_TERMS if term.lower() in text.lower()]
    chinese = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
    stopped = {"负责", "参与", "要求", "具备", "熟悉", "掌握", "能力", "经验", "以及", "相关"}
    return _unique([*known, *latin, *(item for item in chinese if item not in stopped)])


def _keyword_score(text: str, terms: Iterable[str]) -> int:
    lowered = text.lower()
    return sum(1 for term in terms if term.lower() in lowered)


def _prioritize_clauses(value: str, terms: list[str]) -> str:
    separator = "；" if "；" in value else "，"
    clauses = [item.strip() for item in value.split(separator) if item.strip()]
    if len(clauses) < 2:
        return value
    ranked = sorted(enumerate(clauses), key=lambda pair: (-_keyword_score(pair[1], terms), pair[0]))
    result = separator.join(clause for _, clause in ranked)
    return result if result != separator.join(clauses) else value


def _matched_requirement_ids(analysis: JobAnalysis, values: object) -> list[str]:
    text = json.dumps(values, ensure_ascii=False).lower()
    scored = [
        (sum(1 for token in _tokens(req.text) if token.lower() in text), req.id)
        for req in analysis.requirements
    ]
    return [req_id for score, req_id in sorted(scored, reverse=True) if score > 0][:5]


def _fact_ids(value: object) -> set[str]:
    result: set[str] = set()
    if isinstance(value, dict):
        result.update(str(item) for item in value.get("source_fact_ids", []) if item)
        for child in value.values():
            result.update(_fact_ids(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_fact_ids(child))
    return result


def _matching_fact_ids(text: str, facts: list[dict[str, Any]]) -> set[str]:
    compact = re.sub(r"\s+", "", text)
    return {
        str(fact["id"])
        for fact in facts
        if fact.get("id")
        and fact.get("statement")
        and (
            re.sub(r"\s+", "", str(fact["statement"])) in compact
            or compact in re.sub(r"\s+", "", str(fact["statement"]))
        )
    }


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _stable_id(prefix: str, *values: object) -> str:
    digest = hashlib.sha256("|".join(map(str, values)).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-rules-{digest}"
