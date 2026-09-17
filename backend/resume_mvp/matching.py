"""Match JD requirements against auditable facts and resume evidence text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from resume_mvp.domain import EducationEntry, Fact, JobAnalysis, MatchItem, MatchReport, ResumeDocument


# Tech aliases only — do not alias soft verbs like 熟悉/使用 (causes false positives).
_TECH_ALIASES: dict[str, set[str]] = {
    "python": {"python", "py"},
    "javascript": {"javascript", "js"},
    "typescript": {"typescript", "ts"},
    "postgresql": {"postgresql", "postgres", "pgsql"},
    "kubernetes": {"kubernetes", "k8s"},
    "microservice": {"microservice", "microservices", "微服务"},
    "mysql": {"mysql"},
    "redis": {"redis"},
    "docker": {"docker", "容器"},
    "linux": {"linux"},
    "git": {"git"},
    "fastapi": {"fastapi"},
    "django": {"django"},
    "flask": {"flask"},
    "spring": {"spring", "springboot"},
    "java": {"java"},
    "golang": {"golang", "go"},
    "react": {"react", "reactjs"},
    "vue": {"vue", "vuejs"},
    "api": {"api", "接口", "rest", "restful"},
    "sql": {"sql"},
    "database": {"database", "db", "数据库"},
    "backend": {"backend", "后端", "服务端"},
    "frontend": {"frontend", "前端"},
}

_STOPWORDS = {
    "熟悉", "掌握", "精通", "使用", "具备", "了解", "熟练", "良好", "能力", "优先",
    "相关", "经验", "负责", "参与", "进行", "完成", "工作", "以上", "以及", "或者",
    "等", "的", "和", "与", "及", "对", "在", "为", "把", "被", "将", "等有",
    "年月", "毕业", "应届生", "应届", "学历", "专业", "及以上",
}

_MAJOR_ALIASES = {
    "计算机", "软件", "软件工程", "人工智能", "ai", "cs", "计算机科学", "网络工程",
    "信息安全", "数据科学", "电子信息", "自动化", "通信工程", "物联网", "智能科学",
}

_DEGREE_RANK = {
    "大专": 1,
    "专科": 1,
    "本科": 2,
    "学士": 2,
    "硕士": 3,
    "研究生": 3,
    "博士": 4,
}

_FRONTEND_MARKERS = {
    "前端", "frontend", "react", "vue", "angular", "typescript", "javascript", "js", "ts",
    "小程序", "css", "html", "nextjs", "nuxt",
}
_BACKEND_MARKERS = {
    "后端", "backend", "服务端", "fastapi", "django", "flask", "spring", "springboot",
    "java", "golang", "go", "python", "nodejs", "node", "express", "nestjs",
}
_LANGUAGE_GROUPS: dict[str, set[str]] = {
    "python": {"python", "py"},
    "java": {"java"},
    "go": {"go", "golang"},
    "javascript": {"javascript", "js", "typescript", "ts", "nodejs", "node"},
    "cpp": {"c++", "cpp"},
    "c": {"c语言"},
    "rust": {"rust"},
    "csharp": {"c#", "csharp", "dotnet"},
    "php": {"php"},
    "ruby": {"ruby"},
    "swift": {"swift"},
    "kotlin": {"kotlin"},
    "scala": {"scala"},
}

_SOFT_PATTERNS = [
    r"面向业务",
    r"技术方案",
    r"业务问题",
    r"沟通能力",
    r"表达能力",
    r"学习能力",
    r"抗压",
    r"责任心",
    r"团队合作",
    r"团队协作",
    r"协作能力",
    r"主人翁",
    r"自我驱动",
    r"主动性强",
    r"逻辑清晰",
    r"问题分析",
    r"抽象思维",
    r"综合素质",
    r"快速学习",
    r"热情",
    r"好奇心",
]


@dataclass
class EvidenceSnippet:
    text: str
    fact_ids: list[str] = field(default_factory=list)
    source: str = "other"


@dataclass
class EvidenceDecision:
    """A business decision; retrieval scores are deliberately kept out of it."""

    status: str
    snippets: list[EvidenceSnippet] = field(default_factory=list)
    reason: str = ""


def calculate_match(
    analysis: JobAnalysis,
    resume: ResumeDocument,
    facts: list[Fact],
) -> MatchReport:
    evidence = _collect_evidence(resume, facts)
    items: list[MatchItem] = []
    weighted_score = 0.0
    total_weight = sum(requirement.weight for requirement in analysis.requirements)

    for requirement in analysis.requirements:
        req_text = f"{requirement.text} {requirement.evidence_quote}"
        if _is_soft_requirement(req_text):
            item, contribution = _soft_requirement_item(requirement, resume)
            items.append(item)
            weighted_score += contribution
            continue

        has_education_gate = _has_education_requirement(req_text)
        has_capability_gate = any(
            marker in req_text.lower()
            for marker in ("全栈", "跨语言", "多语言", "fullstack", "full-stack", "polyglot", "前后端")
        )
        has_tech_gate = bool(_tech_concepts(requirement.text))
        edu_score, edu_snippets = _education_requirement_match(req_text, resume)
        cap_score, cap_snippets = _capability_requirement_match(req_text, resume, evidence)
        scored = [
            (_best_similarity(requirement.text, requirement.evidence_quote, snippet.text), snippet)
            for snippet in evidence
        ]
        # evidence_quote broadens retrieval, while the normalized requirement
        # remains the authoritative set of atoms to prove.
        text_decision = _decide_text_evidence(requirement.text, scored)
        capability_decision = _capability_decision(cap_score, cap_snippets)
        education_decision = _education_decision(edu_score, edu_snippets)
        decision = _combine_decisions(
            text_decision,
            capability_decision,
            education_decision if has_education_gate else None,
            has_non_education_gate=has_capability_gate or has_tech_gate,
        )
        status = decision.status
        contribution = requirement.weight * {
            "已有证据": 1.0,
            "证据较弱": 0.5,
            "没有证据": 0.0,
        }[status]

        supporting = list(decision.snippets)
        supporting.sort(
            key=lambda snippet: max(
                _best_similarity(requirement.text, requirement.evidence_quote, snippet.text),
                edu_score if snippet in edu_snippets else 0.0,
                cap_score if snippet in cap_snippets else 0.0,
            ),
            reverse=True,
        )
        seen_text: set[str] = set()
        unique: list[EvidenceSnippet] = []
        for snippet in supporting:
            key = snippet.text.strip()
            if not key or key in seen_text:
                continue
            seen_text.add(key)
            unique.append(snippet)
            if len(unique) >= 3:
                break

        fact_ids: list[str] = []
        for snippet in unique:
            fact_ids.extend(snippet.fact_ids)
        excerpts = [snippet.text for snippet in unique]
        items.append(
            MatchItem(
                requirement_id=requirement.id,
                requirement=requirement.text,
                status=status,
                fact_ids=list(dict.fromkeys(fact_ids)),
                excerpts=excerpts,
                reason=decision.reason or _rule_match_reason(status, excerpts, requirement.text),
                weight=requirement.weight,
            )
        )
        weighted_score += contribution

    coverage = weighted_score / total_weight if total_weight else 0.0
    return MatchReport(coverage=round(coverage, 2), items=items)


def _has_education_requirement(text: str) -> bool:
    return any(
        marker in text
        for marker in ("学历", "应届", "届", "毕业", "本科", "硕士", "博士", "专业", "大专")
    )


def _tech_concepts(text: str) -> set[str]:
    """Return canonical concrete-tech concepts mentioned by the text."""
    tokens = _content_tokens(text)
    concepts: set[str] = set()
    for name, aliases in _TECH_ALIASES.items():
        if name in tokens or aliases & tokens:
            concepts.add(name)
    return concepts


def _decide_text_evidence(
    requirement_text: str,
    ranked: list[tuple[float, EvidenceSnippet]],
) -> EvidenceDecision:
    """Use semantic rule outcomes for status; similarity only orders candidates."""
    required_tech = _tech_concepts(requirement_text)
    normalized_requirement = _normalize(requirement_text)
    strong: list[EvidenceSnippet] = []
    weak: list[EvidenceSnippet] = []

    for score, snippet in sorted(ranked, key=lambda item: item[0], reverse=True):
        normalized_evidence = _normalize(snippet.text)
        exact = bool(
            normalized_requirement
            and normalized_evidence
            and (
                normalized_requirement in normalized_evidence
                or normalized_evidence in normalized_requirement
            )
        )
        evidence_tech = _tech_concepts(snippet.text)
        covers_tech = bool(required_tech) and required_tech <= evidence_tech
        related = exact or covers_tech or score > 0
        if not related:
            continue
        if snippet.source == "experience" and (exact or covers_tech):
            strong.append(snippet)
        else:
            weak.append(snippet)

    if strong:
        return EvidenceDecision("已有证据", strong[:3])
    if weak:
        skill_only = all(snippet.source == "skill" for snippet in weak)
        reason = (
            "仅在专业技能栏发现自报能力，尚缺工作/项目中的使用场景、行动和结果证据。"
            if skill_only
            else "有相关线索，但尚缺能完整对应要求的工作/项目行动与结果证据。"
        )
        return EvidenceDecision("证据较弱", weak[:3], reason)
    return EvidenceDecision("没有证据")


def _education_decision(score: float, snippets: list[EvidenceSnippet]) -> EvidenceDecision:
    if score == 1.0:
        return EvidenceDecision("已有证据", snippets)
    if score > 0:
        return EvidenceDecision(
            "证据较弱",
            snippets,
            "教育背景仅满足部分条件，硬性学历、专业或毕业时间要求不能互相抵消。",
        )
    return EvidenceDecision("没有证据", snippets, "教育背景不满足或缺少该硬性条件所需的信息。")


def _capability_decision(score: float, snippets: list[EvidenceSnippet]) -> EvidenceDecision:
    if score == 1.0:
        return EvidenceDecision("已有证据", snippets)
    if score > 0:
        return EvidenceDecision("证据较弱", snippets, "能力信号只覆盖了该要求的一部分。")
    return EvidenceDecision("没有证据")


def _combine_decisions(
    text: EvidenceDecision,
    capability: EvidenceDecision,
    education: EvidenceDecision | None,
    *,
    has_non_education_gate: bool,
) -> EvidenceDecision:
    rank = {"没有证据": 0, "证据较弱": 1, "已有证据": 2}
    optional = [item for item in (text, capability) if item.status != "没有证据"]
    evidence = max(optional, key=lambda item: rank[item.status]) if optional else text

    # Education/eligibility clauses are mandatory. A lexical or technology hit
    # must never compensate for a failed degree, major, or graduation window.
    if education is not None and education.status != "已有证据":
        snippets = [*education.snippets, *evidence.snippets]
        return EvidenceDecision(education.status, snippets, education.reason)
    if education is not None:
        # A pure education requirement is complete once all education atoms pass.
        if not has_non_education_gate:
            return EvidenceDecision("已有证据", education.snippets)
        snippets = [*education.snippets, *evidence.snippets]
        return EvidenceDecision(evidence.status, snippets, evidence.reason)
    return evidence


def _is_soft_requirement(text: str) -> bool:
    # Hard education/eligibility screens are never soft.
    if any(marker in text for marker in ("学历", "应届", "届毕业", "毕业", "本科及以上", "硕士及以上")):
        return False
    if re.search(r"\d{2}届", text) or re.search(r"20\d{2}\s*年.*毕业", text):
        return False
    soft_hits = sum(1 for pattern in _SOFT_PATTERNS if re.search(pattern, text))
    if soft_hits == 0:
        return False
    tokens = _expand_tech(_content_tokens(text))
    tech_hits = len({token for token in tokens if _is_tech_token(token)})
    if soft_hits >= 1 and tech_hits == 0:
        return True
    if soft_hits >= 2 and tech_hits <= 1:
        return True
    return False


def _soft_requirement_item(requirement, resume: ResumeDocument) -> tuple[MatchItem, float]:
    proxies: list[str] = []
    for item in resume.projects[:2]:
        label = " / ".join(part for part in [item.name, item.role] if part.strip())
        if label:
            proxies.append(f"可间接对照项目：{label}")
    for item in resume.work_experience[:1]:
        label = " / ".join(part for part in [item.company, item.title] if part.strip())
        if label:
            proxies.append(f"可间接对照经历：{label}")
    excerpts = [
        "软性要求：简历很少逐字写这类素质，不必强行对齐；可在项目要点里写清业务问题、方案取舍与结果。",
        *proxies[:2],
    ]
    # Soft items should not tank coverage like missing hard skills.
    contribution = requirement.weight * 0.75
    return (
        MatchItem(
            requirement_id=requirement.id,
            requirement=requirement.text,
            status="软性要求",
            fact_ids=[],
            excerpts=excerpts,
            reason="属素质/方法论类软性要求，简历很少逐字出现；可在项目要点中补业务问题、假设与验证路径。",
            weight=requirement.weight,
        ),
        contribution,
    )


def _rule_match_reason(status: str, excerpts: list[str], requirement_text: str) -> str:
    if status == "已有证据":
        return "规则命中与该要求高度相关的简历/事实表述。"
    if status == "证据较弱":
        if excerpts:
            preview = excerpts[0][:40]
            return (
                f"仅有间接相关表述（如「{preview}」），"
                f"与「{requirement_text[:24]}」尚未形成可直接核对的完整对应或结果证据。"
            )
        return "有零散相关信号，但缺少可核对的直接经历描述或结果证据。"
    if status == "没有证据":
        return "简历与事实库中未找到可核对的对应经历或技能。"
    return ""


def _capability_requirement_match(
    req_text: str,
    resume: ResumeDocument,
    evidence: list[EvidenceSnippet],
) -> tuple[float, list[EvidenceSnippet]]:
    """Match '全栈 / 跨语言' style asks via stack signals, not literal wording."""
    wants_fullstack = any(
        marker in req_text.lower()
        for marker in ("全栈", "fullstack", "full-stack", "full stack", "前后端")
    )
    wants_polyglot = any(
        marker in req_text.lower()
        for marker in ("跨语言", "多语言", "polyglot", "多种编程语言", "多种语言")
    )
    if not wants_fullstack and not wants_polyglot:
        return 0.0, []

    corpus = " ".join(snippet.text for snippet in evidence).lower()
    languages = _detected_language_groups(corpus)
    has_frontend = any(marker in corpus for marker in _FRONTEND_MARKERS)
    has_backend = any(marker in corpus for marker in _BACKEND_MARKERS)
    role_fullstack = any("全栈" in f"{item.role}{item.name}".lower() for item in resume.projects)
    role_fullstack = role_fullstack or any("全栈" in item.title.lower() for item in resume.work_experience)

    notes: list[str] = []
    score = 0.0

    if wants_fullstack:
        if role_fullstack:
            score = max(score, 0.92)
            notes.append("角色/项目已写明全栈")
        elif has_frontend and has_backend:
            score = max(score, 0.85)
            notes.append("同时覆盖前端与后端技术栈")
        elif has_frontend or has_backend:
            score = max(score, 0.35)
            notes.append("仅见到单端技术栈，全栈证据偏弱")

    if wants_polyglot:
        if len(languages) >= 2:
            score = max(score, 0.88)
            notes.append("跨语言信号：" + "、".join(sorted(languages)))
        elif len(languages) == 1:
            score = max(score, 0.3)
            notes.append(f"目前主要见到 {next(iter(languages))}，跨语言证据不足")

    if score <= 0:
        return 0.0, []

    # Retrieve concrete supporting snippets with expanded query terms (lightweight lexical RAG).
    query_terms = set()
    if wants_fullstack:
        query_terms |= _FRONTEND_MARKERS | _BACKEND_MARKERS | {"全栈", "前后端"}
    if wants_polyglot:
        for group in _LANGUAGE_GROUPS.values():
            query_terms |= group
    retrieved = _retrieve_snippets(evidence, query_terms, limit=3)
    summary = EvidenceSnippet(
        text="能力匹配：" + "；".join(notes) if notes else "能力匹配：简历技术栈可覆盖该要求",
        fact_ids=[],
        source="experience" if role_fullstack or any(item.source == "experience" for item in retrieved) else "skill",
    )
    requested_checks: list[bool] = []
    if wants_fullstack:
        requested_checks.append(role_fullstack or (has_frontend and has_backend))
    if wants_polyglot:
        requested_checks.append(len(languages) >= 2)
    has_practical_evidence = role_fullstack or any(
        item.source == "experience" for item in retrieved
    )
    decision_signal = 1.0 if all(requested_checks) and has_practical_evidence else 0.5
    return decision_signal, [summary, *retrieved]


def _detected_language_groups(corpus: str) -> set[str]:
    found: set[str] = set()
    normalized = corpus.lower()
    for name, aliases in _LANGUAGE_GROUPS.items():
        if any(alias in normalized for alias in aliases):
            found.add(name)
    return found


def _retrieve_snippets(
    evidence: list[EvidenceSnippet],
    query_terms: set[str],
    *,
    limit: int = 3,
) -> list[EvidenceSnippet]:
    """Tiny lexical retriever: expand JD intent terms and rank resume snippets."""
    ranked: list[tuple[int, EvidenceSnippet]] = []
    for snippet in evidence:
        hay = snippet.text.lower()
        hits = sum(1 for term in query_terms if term and term in hay)
        if hits:
            ranked.append((hits, snippet))
    ranked.sort(key=lambda item: (-item[0], -len(item[1].text)))
    seen: set[str] = set()
    result: list[EvidenceSnippet] = []
    for _, snippet in ranked:
        if snippet.text in seen:
            continue
        seen.add(snippet.text)
        result.append(snippet)
        if len(result) >= limit:
            break
    return result


def _education_requirement_match(req_text: str, resume: ResumeDocument) -> tuple[float, list[EvidenceSnippet]]:
    if not resume.education:
        return 0.0, []
    if not any(marker in req_text for marker in ("学历", "应届", "届", "毕业", "本科", "硕士", "博士", "专业", "大专")):
        return 0.0, []

    wanted_years = _wanted_grad_years(req_text)
    wanted_window = _wanted_grad_window(req_text)
    wanted_degree = _wanted_min_degree(req_text)
    wants_major = any(alias in req_text.lower() for alias in _MAJOR_ALIASES) or "相关专业" in req_text

    best_score = 0.0
    best_snippets: list[EvidenceSnippet] = []
    for item in resume.education:
        score, snippet = _score_education_entry(
            item, req_text, wanted_years, wanted_window, wanted_degree, wants_major
        )
        if score > best_score:
            best_score = score
            best_snippets = [snippet] if snippet else []
    return best_score, best_snippets


def _score_education_entry(
    item: EducationEntry,
    req_text: str,
    wanted_years: set[int],
    wanted_window: tuple[tuple[int, int], tuple[int, int]] | None,
    wanted_degree: int,
    wants_major: bool,
) -> tuple[float, EvidenceSnippet | None]:
    checks: list[bool] = []
    notes: list[str] = []

    grad_year = _parse_year(item.end_date)
    grad_period = _parse_year_month(item.end_date)
    if wanted_window or wanted_years:
        if wanted_window and grad_period:
            (start_year, start_month), (end_year, end_month) = wanted_window
            start_key = start_year * 100 + start_month
            end_key = end_year * 100 + end_month
            grad_key = grad_period[0] * 100 + grad_period[1]
            year_ok = start_key <= grad_key <= end_key
        else:
            year_ok = grad_year in wanted_years if grad_year else False
        checks.append(year_ok)
        if grad_year:
            cohort = _cohort_label_for_date(item.end_date)
            notes.append(f"{item.end_date or grad_year}毕业" + (f"（{cohort}）" if cohort else ""))
        elif year_ok is False:
            notes.append("毕业时间未填或不匹配")

    if wanted_degree:
        degree_rank = _degree_rank(item.degree)
        degree_ok = degree_rank >= wanted_degree
        checks.append(degree_ok)
        if item.degree.strip():
            notes.append(item.degree.strip())

    if wants_major:
        major_ok = _major_matches(item.field, req_text)
        checks.append(major_ok)
        if item.field.strip():
            notes.append(item.field.strip())

    if not checks:
        # Generic education mention — weak credit if any education exists.
        header = _education_header(item)
        return (0.35, EvidenceSnippet(header, source="education")) if header else (0.0, None)

    header = _education_header(item)
    detail = "；".join(notes) if notes else header
    snippet = EvidenceSnippet(f"教育背景：{detail}" if detail else header, source="education")
    # Education clauses are conjunctive hard gates: a degree hit cannot hide a
    # graduation-window or major mismatch.  The numeric value here is only an
    # internal enum bridge (complete / partial), not a similarity confidence.
    return (1.0 if all(checks) else 0.5), snippet


def _education_header(item: EducationEntry) -> str:
    parts = [
        item.institution.strip(),
        item.degree.strip(),
        item.field.strip(),
        " - ".join(part for part in [item.start_date.strip(), item.end_date.strip()] if part),
    ]
    return "，".join(part for part in parts if part)


def _wanted_grad_years(text: str) -> set[int]:
    years: set[int] = set()
    for match in re.finditer(r"20(\d{2})\s*届", text):
        # 27届 => graduating around 2027
        years.add(2000 + int(match.group(1)))
    for match in re.finditer(r"(20\d{2})\s*年", text):
        years.add(int(match.group(1)))
    # Window like 2026年9月-2027年8月：both years count as acceptable graduation years.
    return years


def _wanted_grad_window(text: str) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """Return an explicit window, or the conventional Sep–Aug cohort window."""
    explicit = re.search(
        r"(20\d{2})\s*年?\s*(\d{1,2})\s*月?\s*"
        r"(?:[-—–~～至到]|(?:\s+))+\s*"
        r"(20\d{2})\s*年?\s*(\d{1,2})\s*月?",
        text,
    )
    if explicit:
        return (
            (int(explicit.group(1)), int(explicit.group(2))),
            (int(explicit.group(3)), int(explicit.group(4))),
        )
    cohort = re.search(r"(?<!\d)(?:20)?(\d{2})\s*届", text)
    if cohort:
        year = 2000 + int(cohort.group(1))
        return ((year - 1, 9), (year, 8))
    return None


def _cohort_label(grad_year: int) -> str:
    return f"{grad_year % 100:02d}届"


def _cohort_label_for_date(value: str) -> str:
    parsed = _parse_year_month(value)
    if not parsed:
        year = _parse_year(value)
        return _cohort_label(year) if year else ""
    year, month = parsed
    return _cohort_label(year + 1 if month >= 9 else year)


def _wanted_min_degree(text: str) -> int:
    if "博士" in text:
        return _DEGREE_RANK["博士"]
    if "硕士" in text or "研究生" in text:
        return _DEGREE_RANK["硕士"]
    if "本科" in text or "学士" in text:
        return _DEGREE_RANK["本科"]
    if "大专" in text or "专科" in text:
        return _DEGREE_RANK["大专"]
    return 0


def _degree_rank(degree: str) -> int:
    text = degree.strip().lower()
    best = 0
    for name, rank in _DEGREE_RANK.items():
        if name in text:
            best = max(best, rank)
    return best


def _major_matches(field: str, req_text: str) -> bool:
    field_l = field.lower()
    if not field.strip():
        return False
    if "相关专业" in req_text and any(alias in field_l for alias in _MAJOR_ALIASES):
        return True
    for alias in _MAJOR_ALIASES:
        if alias in req_text.lower() and alias in field_l:
            return True
    # JD lists several majors; any resume major in the family is enough.
    if any(alias in field_l for alias in _MAJOR_ALIASES) and any(alias in req_text.lower() for alias in _MAJOR_ALIASES):
        return True
    return False


def _parse_year(value: str) -> int | None:
    match = re.search(r"(20\d{2})", value or "")
    return int(match.group(1)) if match else None


def _parse_year_month(value: str) -> tuple[int, int] | None:
    match = re.search(r"(20\d{2})(?:[./-](\d{1,2}))?", value or "")
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2) or 6)
    if month < 1 or month > 12:
        return None
    return year, month


def _collect_evidence(resume: ResumeDocument, facts: list[Fact]) -> list[EvidenceSnippet]:
    snippets: list[EvidenceSnippet] = []
    seen: set[str] = set()

    def add(text: str, fact_ids: list[str] | None = None, source: str = "other") -> None:
        cleaned = text.strip()
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        snippets.append(EvidenceSnippet(text=cleaned, fact_ids=list(fact_ids or []), source=source))

    for fact in facts:
        category = fact.category
        source = (
            "experience"
            if "工作" in category or "实习" in category or "项目" in category
            else "skill"
            if "技能" in category
            else "education"
            if "教育" in category
            else "other"
        )
        add(fact.statement, [fact.id], source)

    if resume.basics.summary.value.strip():
        add(resume.basics.summary.value, list(resume.basics.summary.source_fact_ids))
    if resume.basics.target_role.value.strip():
        add(resume.basics.target_role.value, list(resume.basics.target_role.source_fact_ids))

    for item in resume.work_experience:
        header = " ".join(part for part in [item.company, item.title] if part.strip())
        if header:
            add(header, source="experience")
        for bullet in item.bullets:
            add(bullet.value, list(bullet.source_fact_ids), "experience")

    for item in resume.projects:
        header = " ".join(part for part in [item.name, item.role] if part.strip())
        if header:
            add(header, source="experience")
        for bullet in item.bullets:
            add(bullet.value, list(bullet.source_fact_ids), "experience")

    for item in resume.education:
        header = _education_header(item)
        if header:
            add(header, source="education")
            grad_year = _parse_year(item.end_date)
            if grad_year:
                cohort = _cohort_label_for_date(item.end_date)
                add(f"{header}，{item.end_date}毕业，{cohort}应届", source="education")
        for highlight in item.highlights:
            add(highlight.value, list(highlight.source_fact_ids), "education")

    for group in resume.skills:
        for item in group.items:
            add(item.value, list(item.source_fact_ids), "skill")
            for part in re.split(r"[、,，/|]", item.value):
                add(part.strip(), list(item.source_fact_ids), "skill")

    for entry in resume.certificates:
        add(entry.name)
    for entry in resume.awards:
        add(entry.name)
    for section in resume.custom_sections:
        for item in section.items:
            add(item.value, list(item.source_fact_ids))

    return snippets


def _best_similarity(requirement: str, evidence_quote: str, statement: str) -> float:
    scores = [_similarity(requirement, statement)]
    quote = evidence_quote.strip()
    if quote and "未在 JD" not in quote:
        scores.append(_similarity(quote, statement) * 0.9)
    return max(scores)


def _similarity(requirement: str, statement: str) -> float:
    normalized_requirement = _normalize(requirement)
    normalized_statement = _normalize(statement)
    if not normalized_requirement or not normalized_statement:
        return 0.0
    if normalized_requirement in normalized_statement or normalized_statement in normalized_requirement:
        return 1.0

    requirement_tokens = _expand_tech(_content_tokens(requirement))
    statement_tokens = _expand_tech(_content_tokens(statement))
    if not requirement_tokens:
        return 0.0

    overlap = requirement_tokens & statement_tokens
    base = len(overlap) / len(requirement_tokens)

    tech_tokens = {token for token in requirement_tokens if _is_tech_token(token)}
    if tech_tokens:
        tech_hit = len(tech_tokens & statement_tokens) / len(tech_tokens)
        if tech_hit == 0:
            return min(base * 0.35, 0.2)
        base = max(base, 0.5 * base + 0.5 * tech_hit)
        if tech_hit == 1.0:
            base = max(base, 0.55 if len(tech_tokens) == 1 else 0.75)

    for token in tech_tokens:
        if len(token) >= 2 and _normalize(token) in normalized_statement:
            base = max(base, 0.55)

    return min(base, 1.0)


def _content_tokens(value: str) -> set[str]:
    return {token for token in _tokens(value) if token not in _STOPWORDS and not token.isdigit()}


def _is_tech_token(token: str) -> bool:
    if re.fullmatch(r"[a-z0-9+#.]{2,}", token):
        return True
    if token in _TECH_ALIASES:
        return True
    return any(token in aliases for aliases in _TECH_ALIASES.values())


def _expand_tech(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for token in list(tokens):
        for key, aliases in _TECH_ALIASES.items():
            if token == key or token in aliases:
                expanded.add(key)
                expanded.update(aliases)
    return expanded


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.lower())


def _tokens(value: str) -> set[str]:
    lowered = value.lower()
    ascii_tokens = set(re.findall(r"[a-z0-9+#.]{2,}", lowered))
    chinese_chunks = re.findall(r"[\u4e00-\u9fff]+", lowered)
    chinese_tokens: set[str] = set()
    for chunk in chinese_chunks:
        if len(chunk) <= 2:
            chinese_tokens.add(chunk)
            continue
        chinese_tokens.add(chunk)
        chinese_tokens.update(chunk[index : index + 2] for index in range(len(chunk) - 1))
        if len(chunk) >= 3:
            chinese_tokens.update(chunk[index : index + 3] for index in range(len(chunk) - 2))
    return ascii_tokens | chinese_tokens
