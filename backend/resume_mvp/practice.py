from __future__ import annotations

import json
from typing import Literal

from resume_mvp.domain import (
    JobProject,
    PracticeEvaluation,
    PracticeFeedback,
    PracticeQuestion,
    PracticeQuestionList,
    PracticeSession,
    PracticeTurn,
    QuestionSet,
    ResumeDocument,
    utc_now,
)
from resume_mvp.providers.base import AIProvider


_FEEDBACK_DIMENSIONS = ("相关性", "具体性", "证据", "结构", "表达")


async def start_practice(
    kind: Literal["interview", "written"],
    provider: AIProvider,
    project: JobProject,
    resume: ResumeDocument,
) -> PracticeSession:
    safe_resume = resume.model_dump(mode="json")
    safe_resume["basics"]["email"] = ""
    safe_resume["basics"]["phone"] = ""
    mode_instruction = (
        "生成一道面试题，类别从岗位动机、经历深挖、行为题、专业题中选择。"
        if kind == "interview"
        else "生成一道岗位笔试练习题，可包含提示，但不得返回答案或解析。"
    )
    prompt = "\n".join(
        [
            "任务：开始中文求职训练",
            f"训练类型：{kind}",
            mode_instruction,
            "题目必须依据 JD 或当前简历，并填写对应 requirement_ids 或 fact_ids。",
            "输入：" + json.dumps(
                {
                    "job_analysis": project.job_analysis.model_dump(mode="json") if project.job_analysis else {},
                    "resume": safe_resume,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        ]
    )
    question = await provider.complete_json(prompt, PracticeQuestion)
    question = question.model_copy(update={"explanation": None})
    return PracticeSession(project_id=project.id, kind=kind, current_question=question)


async def start_practice_from_set(
    question_set: QuestionSet,
    project: JobProject,
    resume: ResumeDocument,
    provider: AIProvider | None = None,
) -> PracticeSession:
    """Materialize a reusable set into an isolated session question queue."""
    questions = [
        PracticeQuestion.model_validate(question.model_dump(mode="python"))
        for question in question_set.questions
    ]
    if question_set.source in ("rules", "mixed"):
        questions.extend(_questions_from_rules(question_set, project))
    if question_set.source in ("ai", "mixed"):
        if provider is None:
            raise ValueError("AI 或混合题集需要配置模型提供方")
        remaining = max(question_set.question_count - len(questions), 0)
        if remaining:
            safe_resume = resume.model_dump(mode="json")
            safe_resume["basics"]["email"] = ""
            safe_resume["basics"]["phone"] = ""
            prompt = "\n".join(
                [
                    "任务：按可复用题集生成中文求职训练题。",
                    "不得输出候选人的联系方式、原文简历、答案或解析。",
                    f"生成 {remaining} 题，题型为 {question_set.kind}。",
                    "每题填写 answer_points、dimensions、difficulty；依据 JD/简历时填写引用 ID。",
                    "题集规则：" + json.dumps(question_set.rules, ensure_ascii=False),
                    "输入：" + json.dumps(
                        {
                            "job_analysis": project.job_analysis.model_dump(mode="json")
                            if project.job_analysis
                            else {},
                            "resume": safe_resume,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                ]
            )
            generated = await provider.complete_json(prompt, PracticeQuestionList)
            questions.extend(generated.items[:remaining])
    questions = questions[: question_set.question_count]
    if not questions:
        raise ValueError("题集未生成任何题目")
    sanitized = [
        question.model_copy(update={"explanation": None}) for question in questions
    ]
    return PracticeSession(
        project_id=project.id,
        kind=question_set.kind,
        question_set_id=question_set.id,
        current_question=sanitized[0],
        pending_questions=sanitized[1:],
    )


def _questions_from_rules(
    question_set: QuestionSet,
    project: JobProject,
) -> list[PracticeQuestion]:
    rules = question_set.rules
    categories = rules.get("categories") or ["岗位匹配"]
    if isinstance(categories, str):
        categories = [categories]
    difficulty = rules.get("difficulty", "medium")
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"
    dimensions = rules.get("dimensions") or []
    if isinstance(dimensions, str):
        dimensions = [dimensions]
    requirements = project.job_analysis.requirements if project.job_analysis else []
    questions: list[PracticeQuestion] = []
    for index, requirement in enumerate(requirements):
        questions.append(
            PracticeQuestion(
                category=str(categories[index % len(categories)]),
                prompt=f"请结合具体经历说明你如何满足：{requirement.text}",
                requirement_ids=[requirement.id],
                answer_points=[requirement.text],
                dimensions=[str(item) for item in dimensions],
                difficulty=difficulty,
            )
        )
        if len(questions) >= question_set.question_count:
            break
    return questions


async def answer_practice(
    session: PracticeSession,
    answer: str,
    provider: AIProvider,
) -> PracticeTurn:
    if session.current_question is None:
        raise ValueError("当前训练没有待回答题目")
    prompt = "\n".join(
        [
            "任务：评价中文求职训练回答",
            "必须分别评价相关性、具体性、证据、结构、表达，不使用百分制。",
            "笔试题在此时才可返回 explanation。面试可根据回答给出 follow_up。",
            "输入：" + json.dumps(
                {
                    "kind": session.kind,
                    "question": session.current_question.model_dump(mode="json"),
                    "answer": answer,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        ]
    )
    evaluation = await provider.complete_json(prompt, PracticeEvaluation)
    feedback = _complete_feedback(evaluation.feedback)
    turn = PracticeTurn(
        question=session.current_question,
        answer=answer,
        feedback=feedback,
        explanation=evaluation.explanation,
        follow_up=evaluation.follow_up,
    )
    session.turns.append(turn)
    session.weaknesses = list(dict.fromkeys([*session.weaknesses, *feedback.weaknesses]))
    session.current_question = evaluation.next_question
    if session.current_question is None and session.pending_questions:
        session.current_question = session.pending_questions.pop(0)
    session.status = "active" if evaluation.next_question else "completed"
    if session.current_question is not None:
        session.status = "active"
    session.updated_at = utc_now()
    return turn


def _complete_feedback(feedback: PracticeFeedback) -> PracticeFeedback:
    dimensions = {
        name: feedback.dimensions.get(name, "本轮未提供足够信息")
        for name in _FEEDBACK_DIMENSIONS
    }
    return feedback.model_copy(update={"dimensions": dimensions, "percentage_score": None})
