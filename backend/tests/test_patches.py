import pytest

from resume_mvp.domain import Fact, ResumeDocument, ResumePatch, ResumePatchOperation
from resume_mvp.patches import PatchConflictError, apply_resume_patch


def sample_resume_and_patch() -> tuple[ResumeDocument, ResumePatch, Fact]:
    fact = Fact(
        category="工作经历",
        statement="负责企业服务产品规划",
        source_type="manual",
        user_confirmed=True,
    )
    resume = ResumeDocument.blank()
    resume.basics.summary.value = "产品经理"
    resume.basics.target_role.value = "产品经理"
    patch = ResumePatch(
        operations=[
            ResumePatchOperation(
                id="op-summary",
                path="/basics/summary",
                before=resume.basics.summary.model_dump(mode="json"),
                after={
                    "value": "面向企业服务的产品经理",
                    "source_fact_ids": [fact.id],
                    "origin": "ai_rewrite",
                    "confidence": 1,
                },
                reason="突出业务领域",
                source_fact_ids=[fact.id],
            ),
            ResumePatchOperation(
                id="op-role",
                path="/basics/target_role",
                before=resume.basics.target_role.model_dump(mode="json"),
                after={
                    "value": "高级产品经理",
                    "source_fact_ids": [fact.id],
                    "origin": "ai_rewrite",
                    "confidence": 1,
                },
                reason="匹配岗位名称",
                source_fact_ids=[fact.id],
            ),
        ]
    )
    return resume, patch, fact


def test_applies_only_explicitly_accepted_operations() -> None:
    """Catches AI suggestions silently changing unchecked resume fields."""
    resume, patch, fact = sample_resume_and_patch()

    updated = apply_resume_patch(resume, patch, {"op-summary"}, facts=[fact])

    assert updated.basics.summary.value == "面向企业服务的产品经理"
    assert updated.basics.target_role.value == "产品经理"
    assert resume.basics.summary.value == "产品经理"


def test_rejects_stale_before_value() -> None:
    """Catches overwriting a manual edit made after AI produced its patch."""
    resume, patch, fact = sample_resume_and_patch()
    patch.operations[0].before = {**patch.operations[0].before, "value": "已被别人修改"}

    with pytest.raises(PatchConflictError, match="内容已变化"):
        apply_resume_patch(resume, patch, {"op-summary"}, facts=[fact])


def test_rejects_unknown_fact_reference() -> None:
    """Catches a plausible-sounding rewrite with no user evidence."""
    resume, patch, _ = sample_resume_and_patch()

    with pytest.raises(ValueError, match="缺少事实依据"):
        apply_resume_patch(resume, patch, {"op-summary"}, facts=[])
