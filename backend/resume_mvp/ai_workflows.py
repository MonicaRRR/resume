from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel

from resume_mvp.domain import (
    ApplicationType,
    Fact,
    FollowupQuestion,
    JobAnalysis,
    QuestionList,
    ResumeDocument,
    ResumePatch,
)
from resume_mvp.providers.base import AIProvider, ProviderFormatError


T = TypeVar("T", bound=BaseModel)


class UnsupportedFactError(ValueError):
    pass


class JobEvidenceError(ValueError):
    pass


async def analyze_job(
    provider: AIProvider,
    company_name: str,
    job_description: str,
) -> JobAnalysis:
    prompt = _prompt(
        task="分析中文职位描述",
        constraints=[
            "仅使用中文",
            "每项岗位要求的 evidence_quote 必须逐字摘自 JD",
            "推断项设置 inferred=true",
            "不要加入 JD 中不存在的任职条件",
        ],
        data={"company_name": company_name, "job_description": job_description},
    )
    analysis = await _complete_with_repair(provider, prompt, JobAnalysis)
    for requirement in analysis.requirements:
        quote = requirement.evidence_quote.strip()
        if not quote or quote not in job_description:
            raise JobEvidenceError(f"岗位要求“{requirement.text}”的依据无法在 JD 中定位")
    return analysis


async def generate_followup_questions(
    provider: AIProvider,
    analysis: JobAnalysis,
    resume: ResumeDocument,
    facts: list[Fact],
) -> list[FollowupQuestion]:
    prompt = _prompt(
        task="根据证据缺口生成简短追问",
        constraints=[
            "一次只问一个可由用户本人回答的问题",
            "不得假设用户拥有未提供的经历",
            "优先询问职责边界、方法、规模和可量化结果",
            "每个问题均可跳过",
        ],
        data={
            "job_analysis": analysis.model_dump(mode="json"),
            "resume": _safe_resume(resume),
            "facts": [fact.model_dump(mode="json") for fact in facts],
        },
    )
    response = await _complete_with_repair(provider, prompt, QuestionList)
    weights = {requirement.id: requirement.weight for requirement in analysis.requirements}
    ordered = sorted(
        response.items,
        key=lambda question: weights.get(question.requirement_id, 0),
        reverse=True,
    )
    result: list[FollowupQuestion] = []
    seen: set[str] = set()
    for question in ordered:
        key = _normalized_topic(question.topic)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(question)
        if len(result) == 5:
            break
    return result


async def suggest_resume_patch(
    provider: AIProvider,
    analysis: JobAnalysis,
    resume: ResumeDocument,
    facts: list[Fact],
    application_type: ApplicationType = "experienced",
) -> ResumePatch:
    page_constraint = (
        "校招/实习版本必须优化为一页 A4：使用更紧凑表达，优先合并重复内容；不得截断文字、隐藏经历或删除事实。"
        if application_type in {"campus", "internship"}
        else "社招版本允许自然分页，保留高价值经历。"
    )
    prompt = _prompt(
        task="生成待用户审阅的简历补丁",
        constraints=[
            "只能改写、重排或删减已有内容，不能创造事实",
            "每个操作必须引用 source_fact_ids",
            "使用 JSON Pointer 路径",
            "before 必须与输入简历中的当前值完全一致",
            "不要修改姓名、电话或邮箱",
            page_constraint,
        ],
        data={
            "job_analysis": analysis.model_dump(mode="json"),
            "resume": _safe_resume(resume),
            "facts": [fact.model_dump(mode="json") for fact in facts],
        },
    )
    patch = await _complete_with_repair(provider, prompt, ResumePatch)
    known_facts = {fact.id for fact in facts}
    for operation in patch.operations:
        unknown = set(operation.source_fact_ids) - known_facts
        if unknown:
            raise UnsupportedFactError(f"修改“{operation.path}”缺少事实依据：{', '.join(sorted(unknown))}")
    return patch


async def _complete_with_repair(
    provider: AIProvider,
    prompt: str,
    schema: type[T],
) -> T:
    try:
        return await provider.complete_json(prompt, schema)
    except ProviderFormatError as error:
        repair_prompt = _prompt(
            task="只修复为指定 JSON 结构，不增删事实",
            constraints=["不要解释", "不要添加 Markdown 代码块"],
            data={
                "invalid_response": error.raw_response,
                "json_schema": schema.model_json_schema(),
            },
        )
        return await provider.complete_json(repair_prompt, schema)


def _safe_resume(resume: ResumeDocument) -> dict:
    payload = resume.model_dump(mode="json")
    payload["basics"]["email"] = ""
    payload["basics"]["phone"] = ""
    return payload


def _prompt(*, task: str, constraints: list[str], data: dict) -> str:
    return "\n".join(
        [
            f"任务：{task}",
            "约束：",
            *[f"- {constraint}" for constraint in constraints],
            "输入数据：",
            json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        ]
    )


def _normalized_topic(topic: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", topic.lower())
