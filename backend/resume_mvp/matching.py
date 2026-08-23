from __future__ import annotations

import re

from resume_mvp.domain import Fact, JobAnalysis, MatchItem, MatchReport, ResumeDocument


def calculate_match(
    analysis: JobAnalysis,
    resume: ResumeDocument,
    facts: list[Fact],
) -> MatchReport:
    del resume  # Facts are the auditable source; rendered copy must not inflate coverage.
    items: list[MatchItem] = []
    weighted_score = 0.0
    total_weight = sum(requirement.weight for requirement in analysis.requirements)

    for requirement in analysis.requirements:
        scored = [(_similarity(requirement.text, fact.statement), fact) for fact in facts]
        strongest = max((score for score, _ in scored), default=0.0)
        if strongest >= 0.6:
            status = "已有证据"
            contribution = requirement.weight
            threshold = 0.6
        elif strongest >= 0.25:
            status = "证据较弱"
            contribution = requirement.weight * 0.5
            threshold = 0.25
        else:
            status = "没有证据"
            contribution = 0.0
            threshold = 1.1
        supporting = [fact for score, fact in scored if score >= threshold]
        items.append(
            MatchItem(
                requirement_id=requirement.id,
                requirement=requirement.text,
                status=status,
                fact_ids=[fact.id for fact in supporting],
                excerpts=[fact.statement for fact in supporting],
                weight=requirement.weight,
            )
        )
        weighted_score += contribution

    coverage = weighted_score / total_weight if total_weight else 0.0
    return MatchReport(coverage=round(coverage, 2), items=items)


def _similarity(requirement: str, statement: str) -> float:
    normalized_requirement = _normalize(requirement)
    normalized_statement = _normalize(statement)
    if normalized_requirement and normalized_requirement in normalized_statement:
        return 1.0
    requirement_tokens = _tokens(requirement)
    statement_tokens = _tokens(statement)
    if not requirement_tokens:
        return 0.0
    return len(requirement_tokens & statement_tokens) / len(requirement_tokens)


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
        else:
            chinese_tokens.update(chunk[index:index + 2] for index in range(len(chunk) - 1))
    return ascii_tokens | chinese_tokens
