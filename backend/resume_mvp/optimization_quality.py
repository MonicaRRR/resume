"""Deterministic quality gates for resume optimization candidates."""

from collections.abc import Sequence

from resume_mvp.domain import ApplicationType, Fact, MatchReport, ResumePatch
from resume_mvp.optimization_models import (
    LayoutReport,
    OptimizationReview,
    QualityGateResult,
)


def evaluate_quality(
    patch: ResumePatch,
    facts: Sequence[Fact],
    candidate_match: MatchReport,
    layout: LayoutReport,
    review: OptimizationReview,
    application_type: ApplicationType,
) -> QualityGateResult:
    """Evaluate a candidate using only persisted, deterministic reports.

    Every patch operation must cite at least one known fact.  An empty patch
    has nothing to substantiate and therefore receives full traceability.
    """
    known_fact_ids = {fact.id for fact in facts}
    if not patch.operations:
        traceability = 1.0
    else:
        grounded_operations = sum(
            bool(operation.source_fact_ids)
            and all(fact_id in known_fact_ids for fact_id in operation.source_fact_ids)
            for operation in patch.operations
        )
        traceability = grounded_operations / len(patch.operations)

    jd_coverage = candidate_match.coverage
    page_policy_passed = (
        application_type == "experienced" or layout.page_count <= 1
    )
    factuality_passed = review.factuality_passed and traceability == 1.0

    reasons: list[str] = []
    if not factuality_passed:
        reasons.append("存在无事实依据的修改")
    if jd_coverage < 0.8:
        reasons.append("高权重 JD 覆盖率不足 80%")
    if not page_policy_passed:
        reasons.append("校招/实习简历超过一页")
    if layout.severe_issue_count:
        reasons.append("仍存在严重排版问题")
    if review.expression_score < 80:
        reasons.append("综合表达评分不足 80 分")

    return QualityGateResult(
        passed=not reasons,
        factuality_passed=factuality_passed,
        traceability=traceability,
        jd_coverage=jd_coverage,
        expression_score=review.expression_score,
        page_policy_passed=page_policy_passed,
        severe_layout_issues=layout.severe_issue_count,
        reasons=reasons,
    )


def _quality_score(quality: QualityGateResult) -> tuple[int, int, int, float, int]:
    """Return the ordered dimensions used to detect measurable improvement."""
    return (
        int(quality.factuality_passed),
        int(quality.page_policy_passed),
        -quality.severe_layout_issues,
        quality.jd_coverage,
        quality.expression_score,
    )


def should_refine(
    history: Sequence[QualityGateResult], iteration: int, max_refinements: int
) -> bool:
    """Return whether another bounded refinement should be attempted."""
    if not history:
        return iteration < max_refinements

    latest = history[-1]
    if latest.passed or iteration >= max_refinements:
        return False

    # Once two consecutive refinements fail to improve the quality tuple,
    # further model calls cannot satisfy this deterministic stopping rule.
    if len(history) >= 3:
        previous, before_previous = history[-2], history[-3]
        if (
            _quality_score(previous) <= _quality_score(before_previous)
            and _quality_score(latest) <= _quality_score(previous)
        ):
            return False

    return True
