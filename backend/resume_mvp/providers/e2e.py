from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

from resume_mvp.domain import (
    JobAnalysis,
    JobRequirement,
    PracticeEvaluation,
    PracticeFeedback,
    PracticeQuestion,
    QuestionList,
    ResumePatch,
)


T = TypeVar("T", bound=BaseModel)


class E2EProvider:
    """Deterministic model used only by the opt-in browser test server."""

    async def complete_json(self, prompt: str, schema: type[T]) -> T:
        payload = _input_payload(prompt)
        if schema is JobAnalysis:
            job_description = str(payload.get("job_description", ""))
            quote = "Python API" if "Python API" in job_description else job_description[:12]
            return schema.model_validate(
                JobAnalysis(
                    role_title="后端工程师",
                    seniority="初中级",
                    responsibilities=["开发与维护后端接口"],
                    requirements=[
                        JobRequirement(
                            id="req-core",
                            text="Python API 开发",
                            evidence_quote=quote,
                            weight=2,
                        )
                    ],
                    keywords=["Python", "API", "数据库"],
                    interview_topics=["接口稳定性"],
                    written_topics=["幂等设计"],
                )
            )
        if schema is ResumePatch:
            resume = payload.get("resume", {})
            facts = payload.get("facts", [])
            target = resume.get("basics", {}).get("target_role", {})
            fact_ids = list(target.get("source_fact_ids", []))
            if not fact_ids and facts:
                fact_ids = [facts[0]["id"]]
            after = {
                **target,
                "value": "具备 Python API 开发经验的后端工程师",
                "source_fact_ids": fact_ids,
                "origin": "ai_rewrite",
                "confidence": 1,
            }
            return schema.model_validate(
                ResumePatch(
                    operations=[
                        {
                            "id": "op-target-role",
                            "path": "/basics/target_role",
                            "before": target,
                            "after": after,
                            "reason": "突出岗位核心技术要求",
                            "jd_requirement_ids": ["req-core"],
                            "source_fact_ids": fact_ids,
                            "risk": "low",
                        }
                    ]
                )
            )
        if schema is QuestionList:
            return schema.model_validate(
                QuestionList(
                    items=[
                        {
                            "id": "question-result",
                            "question": "你在 API 开发中解决过什么具体难题？",
                            "topic": "技术难题",
                            "requirement_id": "req-core",
                            "rationale": "补充可验证的项目证据",
                        }
                    ]
                )
            )
        if schema is PracticeQuestion:
            return schema.model_validate(
                PracticeQuestion(
                    id="practice-api",
                    category="专业题",
                    prompt="请结合经历说明你如何保证 API 的稳定性？",
                    hint="可从监控、异常处理和容量治理展开",
                    requirement_ids=["req-core"],
                )
            )
        if schema is PracticeEvaluation:
            return schema.model_validate(
                PracticeEvaluation(
                    feedback=PracticeFeedback(
                        dimensions={
                            "相关性": "紧扣接口稳定性",
                            "具体性": "可以补充技术选择",
                            "证据": "已引用个人经历",
                            "结构": "回答层次清楚",
                            "表达": "语言简洁",
                        },
                        summary="回答方向正确，可进一步补充结果证据。",
                        improved_answer="我先建立指标、日志和链路追踪，再用限流与降级保护核心接口。",
                        weaknesses=["量化结果"],
                    ),
                    explanation="稳定性设计应覆盖发现、预防、止损与复盘。",
                    follow_up="这些措施最终改善了哪些指标？",
                    next_question=None,
                )
            )
        return schema.model_validate({"status": "ok"})


def _input_payload(prompt: str) -> dict:
    for marker in ("输入数据：\n", "输入："):
        if marker in prompt:
            candidate = prompt.split(marker, 1)[1].splitlines()[0]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                return {}
    return {}
