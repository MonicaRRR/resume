from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from resume_mvp.autofill import AgentAutofillResponse
from resume_mvp.domain import (
    JobAnalysis,
    MatchReport,
    PatchDiscussionResult,
    PracticeEvaluation,
    PracticeQuestion,
    QuestionList,
    ResumeDocument,
    ResumePatch,
)
from resume_mvp.offline_analysis import (
    analyze_job_description,
    discuss_patch,
    evaluate_practice,
    followup_questions,
    match_resume,
    optimization_review,
    practice_question,
    prompt_payload,
    resume_patch,
)
from resume_mvp.optimization_models import OptimizationReview


T = TypeVar("T", bound=BaseModel)


class RulesProvider:
    """Offline deterministic analysis. It never calls a model or the network."""

    async def complete_json(self, prompt: str, schema: type[T]) -> T:
        data = prompt_payload(prompt)
        if schema is JobAnalysis:
            result = analyze_job_description(
                str(data.get("company_name") or ""),
                str(data.get("job_description") or ""),
            )
        elif schema is MatchReport:
            analysis = JobAnalysis.model_validate(data.get("job_analysis") or {})
            resume = ResumeDocument.model_validate(data.get("resume") or {})
            result = match_resume(analysis, resume, list(data.get("facts") or []))
        elif schema is QuestionList:
            analysis = JobAnalysis.model_validate(data.get("job_analysis") or {})
            resume = ResumeDocument.model_validate(data.get("resume") or {})
            result = followup_questions(analysis, resume, list(data.get("facts") or []))
        elif schema is ResumePatch:
            analysis = JobAnalysis.model_validate(data.get("job_analysis") or {})
            resume = ResumeDocument.model_validate(data.get("resume") or {})
            result = resume_patch(
                analysis,
                resume,
                list(data.get("facts") or []),
                application_type=str(data.get("application_type") or "experienced"),
            )
        elif schema is PracticeQuestion:
            result = practice_question(data)
        elif schema is PracticeEvaluation:
            result = evaluate_practice(data)
        elif schema is OptimizationReview:
            result = optimization_review()
        elif schema is PatchDiscussionResult:
            result = discuss_patch(data)
        elif schema is AgentAutofillResponse:
            # Rules mode deliberately does not infer profile-field mappings.
            fields = list(data.get("remaining_fields") or [])
            result = AgentAutofillResponse(
                mappings=[],
                empty_field_ids=[str(item.get("id")) for item in fields if item.get("id")],
            )
        else:
            result = schema.model_validate({"status": "ok"})
        return schema.model_validate(result)
