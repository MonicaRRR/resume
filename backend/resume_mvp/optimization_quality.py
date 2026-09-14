"""Deterministic quality gates for resume optimization candidates."""

from collections.abc import Sequence

from resume_mvp.domain import ApplicationType, Fact, MatchReport, ResumePatch, ResumePatchOperation
from resume_mvp.optimization_models import (
    LayoutReport,
    OptimizationReview,
    QualityGateResult,
)

_HARD_MAX_REFINEMENTS = 2


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
        reasons.extend(_factuality_detail_reasons(patch.operations, known_fact_ids, review))
    if jd_coverage < 0.8:
        reasons.append(f"高权重 JD 覆盖率不足 80%（当前 {jd_coverage:.0%}）")
    if not page_policy_passed:
        reasons.append(f"校招/实习简历超过一页（当前 {layout.page_count} 页）")
    if layout.severe_issue_count:
        reasons.extend(_severe_layout_reasons(layout))
    if review.expression_score < 80:
        reasons.append(f"综合表达评分不足 80 分（当前 {review.expression_score} 分）")

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


def _op_label(operation: ResumePatchOperation, index: int) -> str:
    path = (operation.path or "").strip() or f"第 {index} 条建议"
    reason = (operation.reason or "").strip()
    if reason:
        short = reason if len(reason) <= 36 else f"{reason[:36]}…"
        return f"{path}（{short}）"
    return path


def _factuality_detail_reasons(
    operations: Sequence[ResumePatchOperation],
    known_fact_ids: set[str],
    review: OptimizationReview,
) -> list[str]:
    details: list[str] = []
    for index, operation in enumerate(operations, start=1):
        label = _op_label(operation, index)
        if not operation.source_fact_ids:
            details.append(f"无事实依据：建议 {label} 未绑定任何事实")
            continue
        unknown = [fact_id for fact_id in operation.source_fact_ids if fact_id not in known_fact_ids]
        if unknown:
            shown = "、".join(unknown[:3])
            suffix = "…" if len(unknown) > 3 else ""
            details.append(f"无事实依据：建议 {label} 引用了未知事实编号（{shown}{suffix}）")

    if not review.factuality_passed:
        if review.rejection_reasons:
            for item in review.rejection_reasons[:5]:
                text = str(item or "").strip()
                if text:
                    details.append(f"审查判定：{text}")
        elif not details:
            details.append("审查判定存在无事实依据的改写，但未给出具体位置")

    if not details:
        details.append("存在无事实依据的修改（未能定位到具体建议）")
    return details


def _severe_layout_reasons(layout: LayoutReport) -> list[str]:
    severe = [issue for issue in layout.issues if issue.severity == "severe"]
    if not severe:
        return ["仍存在严重排版问题"]
    reasons: list[str] = []
    for issue in severe[:5]:
        where = f" @ {issue.target_path}" if issue.target_path else ""
        page = f"第 {issue.page} 页"
        reasons.append(f"严重排版：{issue.message}（{page}{where}）")
    if len(severe) > 5:
        reasons.append(f"另有 {len(severe) - 5} 条严重排版问题未列出")
    return reasons


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
    refinement_limit = min(max_refinements, _HARD_MAX_REFINEMENTS)
    if not history:
        return iteration < refinement_limit

    latest = history[-1]
    if latest.passed or iteration >= refinement_limit:
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
