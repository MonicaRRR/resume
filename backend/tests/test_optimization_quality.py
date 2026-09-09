from resume_mvp.domain import Fact, MatchReport, ResumePatch, ResumePatchOperation
from resume_mvp.optimization_models import LayoutIssue, LayoutReport, OptimizationReview, QualityGateResult
from resume_mvp.optimization_quality import evaluate_quality, should_refine


def _fact(fact_id: str = "fact-1") -> Fact:
    return Fact(
        id=fact_id,
        category="工作经历",
        statement="负责订单 API 开发",
        source_type="manual",
        user_confirmed=True,
    )


def _grounded_patch() -> ResumePatch:
    return ResumePatch(
        operations=[
            ResumePatchOperation(
                id="op-1",
                path="/basics/summary",
                before={"value": "后端工程师"},
                after={"value": "负责订单 API 开发"},
                reason="突出相关经验",
                source_fact_ids=["fact-1"],
            )
        ]
    )


def _ungrounded_patch() -> ResumePatch:
    patch = _grounded_patch()
    patch.operations[0].source_fact_ids = []
    return patch


def _match_report(coverage: float = 1.0) -> MatchReport:
    return MatchReport(
        coverage=coverage,
        items=[
            {
                "requirement_id": "req-1",
                "requirement": "Python API 开发",
                "status": "已有证据",
                "fact_ids": ["fact-1"],
                "weight": 2,
            }
        ],
    )


def _review(
    *, factuality_passed: bool = True, expression_score: int = 90
) -> OptimizationReview:
    return OptimizationReview(
        factuality_passed=factuality_passed,
        expression_score=expression_score,
    )


def _quality(
    *, passed: bool = False, expression_score: int = 72, coverage: float = 0.8
) -> QualityGateResult:
    return QualityGateResult(
        passed=passed,
        factuality_passed=True,
        traceability=1.0,
        jd_coverage=coverage,
        expression_score=expression_score,
        page_policy_passed=True,
        severe_layout_issues=0,
    )


def test_rejects_untraceable_operation() -> None:
    result = evaluate_quality(
        _ungrounded_patch(), [], _match_report(), LayoutReport(), _review(), "campus"
    )

    assert result.passed is False
    assert result.traceability == 0
    assert result.factuality_passed is False
    assert "事实依据" in result.reasons[0]


def test_campus_rejects_two_pages() -> None:
    result = evaluate_quality(
        _grounded_patch(), [_fact()], _match_report(), LayoutReport(page_count=2), _review(), "campus"
    )

    assert result.page_policy_passed is False
    assert result.passed is False
    assert "校招/实习简历超过一页" in result.reasons


def test_internship_rejects_two_pages() -> None:
    result = evaluate_quality(
        _grounded_patch(), [_fact()], _match_report(), LayoutReport(page_count=2), _review(), "internship"
    )

    assert result.page_policy_passed is False


def test_experienced_allows_two_pages() -> None:
    result = evaluate_quality(
        _grounded_patch(), [_fact()], _match_report(), LayoutReport(page_count=2), _review(), "experienced"
    )

    assert result.page_policy_passed is True
    assert result.passed is True


def test_rejects_quality_thresholds_and_reports_all_reasons() -> None:
    layout = LayoutReport(
        page_count=1,
        issues=[LayoutIssue(kind="orphan_heading", severity="severe", message="孤行标题")],
    )
    result = evaluate_quality(
        _grounded_patch(), [_fact()], _match_report(coverage=0.79), layout,
        _review(expression_score=79), "experienced"
    )

    assert result.passed is False
    assert result.severe_layout_issues == 1
    assert result.reasons == [
        "高权重 JD 覆盖率不足 80%",
        "仍存在严重排版问题",
        "综合表达评分不足 80 分",
    ]


def test_empty_patch_is_fully_traceable() -> None:
    result = evaluate_quality(
        ResumePatch(), [], _match_report(), LayoutReport(), _review(), "experienced"
    )

    assert result.traceability == 1.0
    assert result.factuality_passed is True


def test_refines_until_quality_passes_or_budget_is_exhausted() -> None:
    assert should_refine([_quality(passed=False)], iteration=0, max_refinements=2) is True
    assert should_refine([_quality(passed=True)], iteration=0, max_refinements=2) is False
    assert should_refine([_quality()], iteration=2, max_refinements=2) is False


def test_stops_at_hard_iteration_two_even_if_budget_is_larger() -> None:
    assert should_refine([_quality()], iteration=2, max_refinements=3) is False


def test_stops_after_two_non_improving_refinements() -> None:
    history = [_quality(expression_score=72), _quality(expression_score=72), _quality(expression_score=71)]

    assert should_refine(history, iteration=1, max_refinements=2) is False
