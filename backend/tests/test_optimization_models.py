from resume_mvp.domain import ResumePatchOperation
from resume_mvp.optimization_models import LayoutIssue, LayoutReport, OptimizationRun


def test_patch_operation_accepts_optional_layout_evidence() -> None:
    operation = ResumePatchOperation(
        path="/projects/0/bullets", before=[], after=[], reason="消除短尾行",
        source_fact_ids=["fact-1"], layout_issue_ids=["layout-1"],
        expected_layout_benefit="将三字尾行收回上一行",
    )
    assert operation.layout_issue_ids == ["layout-1"]


def test_optimization_run_defaults_to_bounded_loop() -> None:
    run = OptimizationRun(
        project_id="p1", input_version_id="v1", template_id="classic-cn",
        provider="openai-compatible", mode="deep",
    )
    assert (run.status, run.iteration, run.max_refinements) == ("queued", 0, 2)
    assert (run.max_model_calls, run.max_total_tokens) == (12, 120_000)


def test_layout_report_counts_severe_issues() -> None:
    report = LayoutReport(
        page_count=2,
        issues=[LayoutIssue(kind="one_page_overflow", severity="severe", message="超过一页")],
    )
    assert report.severe_issue_count == 1
