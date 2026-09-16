from __future__ import annotations

"""Question-set generation kept deliberately provider-independent for local use."""

from resume_mvp.domain import JobProject, PracticeQuestion, QuestionSet, QuestionSetSource, ResumeDocument, ResumeVersion, utc_now


def build_fallback_question_set(
    project: JobProject,
    version: ResumeVersion | None,
    source_type: QuestionSetSource,
) -> QuestionSet:
    """Build stable, useful questions when no model provider is configured."""
    resume = version.resume if version else ResumeDocument.blank()
    questions: list[PracticeQuestion] = []
    analysis = project.job_analysis

    if source_type == "jd":
        requirements = analysis.requirements if analysis else []
        topics = (analysis.interview_topics if analysis else []) or ["岗位职责和任职要求"]
        for requirement in requirements[:3]:
            questions.append(
                PracticeQuestion(
                    category="岗位要求",
                    prompt=f"请结合你的真实经历，说明你如何满足“{requirement.text}”，并给出可验证的结果。",
                    hint="建议按背景、行动、结果（STAR）回答。",
                    requirement_ids=[requirement.id],
                )
            )
        for topic in topics[:2]:
            questions.append(
                PracticeQuestion(
                    category="岗位深挖",
                    prompt=f"围绕“{topic}”，面试官最应该了解你做过什么？请讲一个具体例子。",
                    hint="说明你的个人贡献，不要只描述团队工作。",
                )
            )
        title = "基于岗位描述的面试题集"
    elif source_type == "project":
        projects = resume.projects or []
        for item in projects[:5]:
            questions.append(
                PracticeQuestion(
                    category="项目深挖",
                    prompt=f"请介绍项目“{item.name or '该项目'}”中最困难的问题，以及你具体如何解决。",
                    hint="重点说明技术决策、取舍和结果。",
                    fact_ids=[bullet.source_fact_ids[0] for bullet in item.bullets if bullet.source_fact_ids][:3],
                )
            )
        if not questions:
            questions.append(
                PracticeQuestion(category="项目深挖", prompt="请介绍一个最能代表你能力的项目，你承担了什么工作？", hint="按背景、行动、结果组织。")
            )
        title = "项目经历深挖题集"
    else:
        entries = [*resume.work_experience, *resume.projects]
        for item in entries[:4]:
            name = getattr(item, "company", "") or getattr(item, "name", "") or "这段经历"
            questions.append(
                PracticeQuestion(
                    category="经历复盘",
                    prompt=f"请复盘“{name}”这段经历：目标是什么，你的贡献和最终结果分别是什么？",
                    hint="尽量补充规模、指标和具体产出。",
                )
            )
        questions.extend(
            [
                PracticeQuestion(category="自我介绍", prompt="请用一分钟介绍自己，并说明为什么适合这个岗位。", hint="突出与岗位最相关的两项经历。"),
                PracticeQuestion(category="职业动机", prompt="你为什么选择这个岗位？未来希望在哪些方面继续成长？", hint="回答要和岗位及已有经历相互印证。"),
            ]
        )
        title = "基于个人经历的面试题集"

    if not questions:
        questions = [
            PracticeQuestion(category="岗位动机", prompt="你为什么申请这个岗位？请结合自己的经历说明。", hint="避免只说兴趣，补充事实依据。"),
            PracticeQuestion(category="经历深挖", prompt="请介绍一项最有代表性的经历，以及你取得的结果。", hint="按 STAR 结构回答。"),
        ]
    now = utc_now()
    return QuestionSet(
        project_id=project.id,
        title=title,
        source_type=source_type,
        questions=questions,
        created_at=now,
        updated_at=now,
    )
