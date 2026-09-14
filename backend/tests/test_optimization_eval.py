from __future__ import annotations

import json
from pathlib import Path

import pytest

from resume_mvp.domain import Fact, MatchReport, ResumePatch
from resume_mvp.optimization_models import LayoutReport, OptimizationReview, QualityGateResult
from resume_mvp.optimization_quality import evaluate_quality


def load_eval_cases() -> list[dict]:
    path = Path(__file__).parent / "fixtures" / "optimization_eval_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_quality_from_fixture(case: dict) -> QualityGateResult:
    return evaluate_quality(
        ResumePatch.model_validate(case["candidate_patch"]),
        [Fact.model_validate(item) for item in case["facts"]],
        MatchReport.model_validate(case["candidate_match"]),
        LayoutReport.model_validate(case["layout_report"]),
        OptimizationReview.model_validate(case["review"]),
        case["application_type"],
    )


@pytest.mark.parametrize("case", load_eval_cases(), ids=lambda case: case["name"])
def test_optimization_eval_case(case: dict) -> None:
    result = evaluate_quality_from_fixture(case)
    assert result.model_dump(mode="json") == case["expected_quality"]
