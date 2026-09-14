from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel

from resume_mvp.domain import (
    ApplicationType,
    ExperienceAsk,
    Fact,
    FollowupQuestion,
    JobAnalysis,
    PatchDiscussionResult,
    QuestionList,
    ResumeDocument,
    ResumePatch,
    ResumePatchOperation,
)
from resume_mvp.providers.base import AIProvider, ProviderFormatError
from resume_mvp.style_guides import select_style_guides, style_guides_for_prompt
from resume_mvp.text_tidy import tidy_paste_artifacts, tidy_value_tree


T = TypeVar("T", bound=BaseModel)


class UnsupportedFactError(ValueError):
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
            "每项岗位要求的 evidence_quote 尽量逐字摘自 JD",
            "若无法逐字摘录（概括、合并多句、措辞改写），必须设置 inferred=true，仍保留该要求，不要丢弃",
            "inferred=true 时 evidence_quote 可写最接近的原文片段；实在没有则写短说明，但不得因此省略该要求",
            "不要加入 JD 中完全不存在的任职条件；能从 JD 合理读出的优先项/加分项应保留并标 inferred",
        ],
        data={"company_name": company_name, "job_description": job_description},
    )
    analysis = await _complete_with_repair(provider, prompt, JobAnalysis)
    for requirement in analysis.requirements:
        quote = requirement.evidence_quote.strip()
        located = _quote_located_in_jd(quote, job_description)
        if located:
            requirement.evidence_quote = located
            continue
        requirement.inferred = True
        if quote:
            # Keep the model’s wording so the UI still shows what it meant,
            # but mark clearly that it was not found verbatim.
            if "未在 JD" not in quote and "未能定位" not in quote:
                requirement.evidence_quote = f"{quote}（未在 JD 原文精确定位）"
        else:
            requirement.evidence_quote = "（未能在 JD 原文精确定位依据，已按语义保留为推断项）"
    return analysis


def _quote_located_in_jd(quote: str, job_description: str) -> str | None:
    """Return a JD substring matching the quote, allowing light whitespace drift."""
    cleaned = quote.strip()
    if not cleaned:
        return None
    if cleaned in job_description:
        return cleaned

    def compact(text: str) -> str:
        return re.sub(r"\s+", "", text)

    compact_jd = compact(job_description)
    compact_quote = compact(cleaned)
    if not compact_quote or compact_quote not in compact_jd:
        return None

    # Recover an approximate original span for display when only whitespace differed.
    pattern = re.compile(r"\s*".join(map(re.escape, compact_quote)))
    match = pattern.search(job_description)
    if match:
        return match.group(0)
    return cleaned


async def generate_followup_questions(
    provider: AIProvider,
    analysis: JobAnalysis,
    resume: ResumeDocument,
    facts: list[Fact],
    application_type: ApplicationType = "experienced",
) -> list[FollowupQuestion]:
    inventory = _experience_inventory(resume)
    thin_projects = inventory["project_count"] <= 2
    campus_like = application_type in {"campus", "internship"}
    if campus_like:
        guidance_hint = (
            "guidance 用 2–4 条短提示帮助回忆（课程设计、实验室、比赛、个人工具、开源贡献、助研等），"
            "写成可勾选的线索，不要编造用户做过"
        )
        thin_hint = (
            "当前项目经历偏少：至少一半问题应询问是否还有与 JD 关键词相关的项目/课程/比赛经历，"
            "并在 guidance 里给出具体回忆方向"
            if thin_projects
            else "若某条 JD 要求缺少项目证据，可追问是否有对应项目或可迁移经历"
        )
    else:
        guidance_hint = (
            "guidance 用 2–4 条短提示帮助回忆（工作专项、跨团队推进、故障复盘、性能治理、内部平台、"
            "开源/个人工具等），写成可勾选的线索；社招不要引导课程设计、课设、竞赛、黑客松、数学建模"
        )
        thin_hint = (
            "当前项目经历偏少：至少一半问题应询问是否还有与 JD 相关的工作项目或可迁移业务/技术专项，"
            "并在 guidance 里给出具体回忆方向；禁止提示课程设计或竞赛"
            if thin_projects
            else "若某条 JD 要求缺少项目证据，可追问是否有对应工作项目或可迁移专项；禁止提示课程设计或竞赛"
        )
    prompt = _prompt(
        task="根据证据缺口生成简短追问",
        constraints=[
            "一次只问一个可由用户本人回答的问题",
            "不得假设用户拥有未提供的经历",
            "优先询问职责边界、方法、规模和可量化结果",
            "把追问当作与用户的讨论：说明为何与当前 JD 相关",
            "每个问题均可跳过",
            guidance_hint,
            thin_hint,
        ],
        data={
            "job_analysis": analysis.model_dump(mode="json"),
            "resume": _safe_resume(resume),
            "experience_inventory": inventory,
            "facts": [fact.model_dump(mode="json") for fact in facts],
            "project_coverage": "thin" if thin_projects else "ok",
            "application_type": application_type,
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
    if thin_projects and not any("项目" in item.topic or "项目" in item.question for item in result):
        result = [_default_project_followup(analysis, resume, application_type), *result][:5]
    return result


async def suggest_resume_patch(
    provider: AIProvider,
    analysis: JobAnalysis,
    resume: ResumeDocument,
    facts: list[Fact],
    application_type: ApplicationType = "experienced",
) -> ResumePatch:
    page_constraint = (
        "校招/实习优先压到一页，但不得为压页把项目删到太空：素材够时通常保留 2–3 个最相关项目；"
        "优先按 JD 改写 bullets 与排序，只有明显弱相关且删后仍够密时才建议移出；删减须用户勾选同意。"
        if application_type in {"campus", "internship"}
        else "社招允许自然分页；按 JD 相关性排序与改写，弱相关可后移或移出，须用户同意；勿过度删减导致版面空疏。"
    )
    fact_catalog = [
        {"id": fact.id, "category": fact.category, "statement": fact.statement}
        for fact in facts
    ]
    style_guides = style_guides_for_prompt(select_style_guides(analysis, application_type, limit=4))
    inventory = _experience_inventory(resume)
    campus_like = application_type in {"campus", "internship"}
    if campus_like:
        ask_constraints = [
            "若 experience_inventory.project_count ≤ 2，或相对 JD 明显缺项目证据：必须在 experience_asks 里给出 1–2 条追问，询问用户是否还有相关项目/课程设计/比赛/个人工具",
            "experience_asks.question 用口语直接问；guidance 给 2–4 条回忆引导（点名 JD 关键词，提示课程大作业、实验室、黑客松、开源、助研、实习边角项目等），不得断言用户一定做过",
        ]
    else:
        ask_constraints = [
            "若 experience_inventory.project_count ≤ 2，或相对 JD 明显缺项目证据：必须在 experience_asks 里给出 1–2 条追问，询问是否还有相关工作项目、业务专项或可迁移技术成果",
            "experience_asks.question 用口语直接问；guidance 给 2–4 条回忆引导（点名 JD 关键词，提示上一份工作未单列的模块、跨团队推进、故障复盘、性能治理、内部平台、开源/个人工具等）",
            "社招禁止在 experience_asks / guidance 中引导课程设计、课设、毕设、竞赛、黑客松、数学建模等校园向经历",
        ]
    prompt = _prompt(
        task="基于用户经历素材库，生成面向当前 JD 的简历适配建议（待用户逐项同意）",
        constraints=[
            "用户简历是完整素材库：可含大量实习/工作/项目/技能，无需全部出现在投递版",
            "你的职责是筛选、润色、重排、压缩与岗位对齐——不是替用户编造经历，也不是把素材库原样誊抄",
            "只能改写、重排或建议删减已有内容；不能创造公司、职位、项目、数字、证书或技能",
            "适配优先于删减：先把已有项目/实习 bullets 改写成对齐 JD 关键词与职责的表述，再考虑压缩或移出弱相关",
            "必须对照 JD 与 experience_inventory 做相关性判断：高相关靠前并深挖改写，弱相关缩短/后移；仅当明显无关且删后版面仍充实才建议移出",
            "首轮必须尽量给齐投递版骨架（有内容的章节都要有实质适配，禁止只改 1–2 处点缀）",
            "若 skills 非空：必须输出一条 /skills 适配（分类分行、对齐 JD 关键词；去掉空「技能」分组；标题下不要再写「专业技能：」）",
            "若 work_experience 数量 ≥ 1：至少一条高相关 /work_experience/*/bullets 的 JD 适配改写（STAR 收紧，半行以上）",
            "若 work_experience 数量 ≥ 2：可再给排序或弱相关压缩；优先改写高相关，而非只润色无关措辞或盲目删段",
            "若 projects 数量 ≥ 1：必须至少输出一条针对项目 bullets（如 /projects/0/bullets）的 JD 适配改写，突出岗位匹配点，不得编造新成果",
            "若 projects 数量 ≥ 3：可另给一条 /projects 排序或轻度筛选建议；projects ≤ 2 时禁止建议整段移出项目，应全部保留并加强改写",
            "禁止“有什么写什么”：弱相关项目不要只做同义润色；要么改写成突出可迁移能力，要么明确建议缩短/后移",
            "若专业技能过短（如仅 Python/SQL）：应建议按类别拆成多条 items（每条一行），类别名用「后端/数据/工具」等，不要再生成空的「技能」分组，也不要在组名里重复「专业技能」",
            "技能 after 结构：优先一个分组 name=专业技能，items 为 2–5 条充实要点（每条 ≥ 半行，如「后端：Python、FastAPI、PostgreSQL」）；禁止多个空 SkillGroup，禁止把三点挤成 items 里的一句话却仍只占视觉一行的含糊写法",
            "优先保留与 JD 高相关、有结果证据的条目；删减后若版面会明显空疏，则不应删，改为压缩单条篇幅",
            "writing_style_guides 只提供结构与句式参考：可学习排序、压缩与表达方式，严禁引入其中未在用户事实出现的公司/项目/指标（含参考 PDF 戏仿人名与经历）",
            "若某条建议的措辞灵感来自写法范式，仍必须绑定用户自己的 source_fact_ids",
            "每条建议必须说明：为何适配该 JD、依据哪条 JD 要求、引用哪些 source_fact_ids",
            "reason 用中文写清「筛选 / 润色 / 适配」意图，便于用户决定是否同意；筛选类须点名保留/移出了哪些条目；适配类须点名对齐了哪些 JD 关键词",
            "每个操作必须引用 source_fact_ids；path 必须是 JSON Pointer，且根字段只能是 allowed_patch_roots 之一",
            "path 示例：/projects、/projects/0/bullets、/work_experience/1/bullets、/basics/summary、/skills、/section_order；禁止 /summary、/project、/work 等简写或英文别名",
            "source_fact_ids 必须且只能从输入 allowed_fact_ids / facts 的 id 中选择，禁止编造任何新的 UUID 或事实编号",
            "严禁把 UUID、fact id、source_fact_ids 写进 after 的正文（value/bullets 等）；这些 id 只能出现在 JSON 的 source_fact_ids 字段",
            "before 必须与输入简历中的当前值完全一致",
            "after 必须与 before 保持同一 JSON 结构（同为带 value 的文本对象、或同为 bullets 列表等），禁止输出残缺对象或把整段经历换成空 {} / []",
            "优先修改文本字段（如 .../value、bullets 里的 value）；筛选整表时改 /projects 或 /work_experience 列表本身",
            "若用户原文含 LaTeX/排版残留（如 \\item、\\textbf{}、90/\\%、90/%、多余的 \\{}、\\\\），在 after 中清理为通顺中文与正常百分号（如 90%）",
            "经历描述若本是分点，after 用多条 bullets 或在 value 内用换行分点，不要揉成难读的一整段；高相关项目建议 2–4 条充实 bullets",
            "注意版面密度：避免一行只有几个字的空疏排版；过短条目应合并进相邻句、并入同类 bullets，或删去无信息填充，而不是单独占一行",
            "技能/亮点若过碎（如单独一行「Python」），应合并为「语言：Python、…」类紧凑写法；合并时只能使用已有事实，不得编造",
            "润色时兼顾可读性与版面：句子宜充实到约占半行以上；过短则合并或基于已有事实扩写场景，禁止为填版面而灌水",
            "除非 reason 明确写「建议移出/删除/不放入投递版」，否则不得把原本有实质内容的字段改成空字符串或空列表",
            "每条建议必须互不重复：同一 path 只出现一次；不要同时改父路径与子路径（如 /work_experience/0 与 /work_experience/0/bullets）",
            "不要对同一段经历给出多条同义改写；若只需润色一次，合并为一条",
            "before 与 after 文本实质相同的无效建议不要输出",
            "建议数量通常 6–12 条：首轮应覆盖技能/实习/项目等有内容章节的实质适配，不要因「精炼」只给两三条；仍禁止同义重复与空操作",
            *ask_constraints,
            "experience_asks 不算改稿：不要把虚构项目写进 operations；只提问帮助用户补充素材",
            "不要修改姓名、性别、生日、电话、邮箱、微信、政治面貌或证件照",
            "不要自动应用任何修改——输出仅供用户审阅勾选",
            page_constraint,
        ],
        data={
            "job_analysis": analysis.model_dump(mode="json"),
            "resume": _safe_resume(resume),
            "experience_inventory": inventory,
            "facts": [fact.model_dump(mode="json") for fact in facts],
            "allowed_fact_ids": [fact.id for fact in facts],
            "fact_catalog": fact_catalog,
            "project_coverage": "thin" if inventory["project_count"] <= 2 else "ok",
            "application_type": application_type,
            "allowed_patch_roots": sorted(
                [
                    "basics",
                    "education",
                    "work_experience",
                    "projects",
                    "skills",
                    "certificates",
                    "awards",
                    "custom_sections",
                    "section_order",
                ]
            ),
            "writing_style_guides": style_guides,
        },
    )
    patch = await _complete_with_repair(provider, prompt, ResumePatch)
    grounded = _ground_patch_operations(patch, resume=resume, facts=facts)
    return _ensure_experience_asks(
        grounded,
        resume=resume,
        analysis=analysis,
        application_type=application_type,
    )


def _experience_inventory(resume: ResumeDocument) -> dict:
    def excerpt(bullets: list) -> str:
        texts = [str(getattr(item, "value", "") or "").strip() for item in bullets]
        joined = "；".join(text for text in texts if text)
        return joined[:280]

    return {
        "project_count": len(resume.projects),
        "work_count": len(resume.work_experience),
        "projects": [
            {
                "index": index,
                "name": item.name,
                "role": item.role,
                "excerpt": excerpt(item.bullets),
            }
            for index, item in enumerate(resume.projects)
        ],
        "work_experience": [
            {
                "index": index,
                "company": item.company,
                "title": item.title,
                "excerpt": excerpt(item.bullets),
            }
            for index, item in enumerate(resume.work_experience)
        ],
    }


def _collect_fact_ids(value: object) -> list[str]:
    found: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            raw = node.get("source_fact_ids")
            if isinstance(raw, list):
                found.extend(str(item) for item in raw if item)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return found


def _rewrite_fact_ids(value: object, valid_ids: list[str], known_ids: set[str]) -> object:
    if isinstance(value, dict):
        next_value = {
            key: _rewrite_fact_ids(child, valid_ids, known_ids)
            for key, child in value.items()
        }
        if "source_fact_ids" in next_value:
            current = next_value.get("source_fact_ids")
            kept = [item for item in current if isinstance(current, list) and item in known_ids]
            next_value["source_fact_ids"] = kept or list(valid_ids)
        return next_value
    if isinstance(value, list):
        return [_rewrite_fact_ids(item, valid_ids, known_ids) for item in value]
    return value


def _facts_for_path(path: str, facts: list[Fact]) -> list[str]:
    root = path.strip("/").split("/", 1)[0] if path else ""
    category_map = {
        "basics": ("基本信息", "个人概述"),
        "education": ("教育经历",),
        "work_experience": ("工作/实习经历",),
        "projects": ("项目经历",),
        "skills": ("专业技能",),
        "certificates": ("证书",),
        "awards": ("奖项",),
    }
    categories = category_map.get(root)
    if categories:
        matched = [fact.id for fact in facts if fact.category in categories]
        if matched:
            return matched
    return [fact.id for fact in facts]


def _facts_matching_text(text: str, facts: list[Fact]) -> list[str]:
    haystack = text.strip()
    if not haystack:
        return []
    scored: list[tuple[int, str]] = []
    for fact in facts:
        statement = fact.statement.strip()
        if not statement:
            continue
        if statement in haystack or haystack in statement:
            scored.append((len(statement), fact.id))
    scored.sort(reverse=True)
    return [fact_id for _, fact_id in scored]


def _ground_patch_operations(
    patch: ResumePatch,
    *,
    resume: ResumeDocument,
    facts: list[Fact],
) -> ResumePatch:
    known_ids = {fact.id for fact in facts}
    resume_payload = resume.model_dump(mode="json")
    grounded: list[ResumePatchOperation] = []

    for operation in patch.operations:
        from resume_mvp.patches import normalize_patch_path, read_pointer

        path = normalize_patch_path(operation.path)
        try:
            live_before = read_pointer(resume_payload, path)
        except Exception:
            # Drop unusable pointers so they never reach "同意应用".
            continue

        cited = [
            *[str(item) for item in operation.source_fact_ids if item],
            *_collect_fact_ids(operation.after),
            *_collect_fact_ids(operation.before),
            *_collect_fact_ids(live_before),
        ]
        valid = [fact_id for fact_id in dict.fromkeys(cited) if fact_id in known_ids]

        if not valid:
            after_text = json.dumps(operation.after, ensure_ascii=False) if operation.after is not None else ""
            valid = _facts_matching_text(after_text, facts)

        if not valid:
            valid = [fact_id for fact_id in _collect_fact_ids(live_before) if fact_id in known_ids]

        if not valid:
            valid = _facts_for_path(path, facts)

        if not valid:
            continue

        after = tidy_value_tree(
            _align_after_shape(
                live_before,
                _rewrite_fact_ids(operation.after, valid, known_ids),
            )
        )
        reason = tidy_paste_artifacts(operation.reason)
        if _is_unintended_wipe(live_before, after, reason):
            continue

        if operation.op == "replace" and _text_content(live_before) == _text_content(after):
            continue

        candidate = operation.model_copy(
            update={
                "id": operation.id,
                "path": path,
                "reason": reason or operation.reason,
                "source_fact_ids": valid,
                "after": after,
                "before": live_before,
            }
        )
        grounded = _merge_non_duplicate(grounded, candidate)

    return ResumePatch(operations=grounded, experience_asks=list(patch.experience_asks))


def _ensure_experience_asks(
    patch: ResumePatch,
    *,
    resume: ResumeDocument,
    analysis: JobAnalysis,
    application_type: ApplicationType = "experienced",
) -> ResumePatch:
    if len(resume.projects) > 2 and patch.experience_asks:
        return patch
    if len(resume.projects) > 2:
        return patch
    if patch.experience_asks:
        cleaned = [
            ask.model_copy(
                update={
                    "question": tidy_paste_artifacts(ask.question).strip() or ask.question,
                    "guidance": tidy_paste_artifacts(ask.guidance).strip(),
                }
            )
            for ask in patch.experience_asks
            if (ask.question or "").strip()
        ][:2]
        if cleaned:
            return patch.model_copy(update={"experience_asks": cleaned})
    return patch.model_copy(
        update={"experience_asks": [_default_project_ask(analysis, resume, application_type)]}
    )


def _jd_keyword_hints(analysis: JobAnalysis, *, limit: int = 5) -> list[str]:
    hints: list[str] = []
    for item in [*analysis.keywords, *[req.text for req in analysis.requirements]]:
        text = re.sub(r"\s+", "", str(item or "").strip())
        if len(text) < 2:
            continue
        if text not in hints:
            hints.append(text)
        if len(hints) >= limit:
            break
    return hints or [analysis.role_title or "目标岗位"]


def _default_project_ask(
    analysis: JobAnalysis,
    resume: ResumeDocument,
    application_type: ApplicationType = "experienced",
) -> ExperienceAsk:
    keywords = _jd_keyword_hints(analysis)
    joined = "、".join(keywords[:4])
    existing = "、".join(item.name for item in resume.projects if item.name.strip()) or "（当前几乎没有项目条目）"
    if application_type in {"campus", "internship"}:
        guidance = "\n".join(
            [
                f"· 课程大作业 / 毕设里有没有用到 {joined}？",
                f"· 实验室、助研、比赛（黑客松/数学建模/创新创业）是否做过相关原型？",
                f"· 个人工具、脚本、开源贡献、兴趣项目里有没有能对应 JD 的？",
                f"· 实习中未单独成段、但可拆出来写的小模块？",
            ]
        )
        question = (
            f"现在项目经历偏少（已有：{existing}）。你是否还有与「{joined}」相关的项目、课程或比赛经历，"
            "愿意补充进素材库？"
        )
    else:
        guidance = "\n".join(
            [
                f"· 上一份工作里有没有未单独成段、但可对齐「{joined}」的模块或专项？",
                f"· 跨团队推进、故障复盘、性能/稳定性治理等成果能否拆出来写？",
                f"· 内部平台、中台建设、技术债治理类经历？",
                f"· 个人工具、开源贡献里有没有能对应 JD 的？（不要写课程设计或竞赛）",
            ]
        )
        question = (
            f"现在项目经历偏少（已有：{existing}）。你是否还有与「{joined}」相关的工作项目或可迁移业务/技术专项，"
            "愿意补充进素材库？"
        )
    return ExperienceAsk(
        question=question,
        guidance=guidance,
        topic="相关项目补充",
        jd_keywords=keywords,
    )


def _default_project_followup(
    analysis: JobAnalysis,
    resume: ResumeDocument,
    application_type: ApplicationType = "experienced",
) -> FollowupQuestion:
    ask = _default_project_ask(analysis, resume, application_type)
    return FollowupQuestion(
        question=ask.question,
        topic=ask.topic,
        rationale="项目经历相对 JD 偏少，先确认是否还有可补充的相关经历",
        guidance=ask.guidance,
        skippable=True,
    )


def _path_key(path: str) -> str:
    return path.rstrip("/") or "/"


def _paths_overlap(left: str, right: str) -> bool:
    a = _path_key(left)
    b = _path_key(right)
    return a == b or a.startswith(f"{b}/") or b.startswith(f"{a}/")


def _entry_scope(path: str) -> str:
    """Collapse /work_experience/0/bullets -> /work_experience/0 for overlap checks."""
    parts = [part for part in _path_key(path).split("/") if part]
    if len(parts) >= 2 and parts[1].isdigit():
        return "/" + "/".join(parts[:2])
    if parts:
        return "/" + parts[0]
    return "/"


def _normalized_dup_text(value: object) -> str:
    text = _text_content(value)
    return re.sub(r"\s+", "", text).lower()


def _texts_near_duplicate(left: object, right: object) -> bool:
    a = _normalized_dup_text(left)
    b = _normalized_dup_text(right)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(shorter) < 12:
        return False
    return shorter in longer and len(shorter) / len(longer) >= 0.72


def _merge_non_duplicate(
    kept: list[ResumePatchOperation],
    candidate: ResumePatchOperation,
) -> list[ResumePatchOperation]:
    """Drop path / parent-child / near-identical rewrites; keep the more specific path when overlapping."""
    drop_candidate = False
    remove_indexes: set[int] = set()
    for index, existing in enumerate(kept):
        path_overlap = _paths_overlap(existing.path, candidate.path)
        near_duplicate = (
            _entry_scope(existing.path) == _entry_scope(candidate.path)
            and _texts_near_duplicate(existing.after, candidate.after)
        ) or (
            _texts_near_duplicate(existing.after, candidate.after)
            and _texts_near_duplicate(existing.before, candidate.before)
        )
        if path_overlap:
            if len(_path_key(candidate.path)) > len(_path_key(existing.path)):
                remove_indexes.add(index)
            else:
                drop_candidate = True
        elif near_duplicate:
            drop_candidate = True
    if drop_candidate:
        return kept
    remaining = [item for index, item in enumerate(kept) if index not in remove_indexes]
    remaining.append(candidate)
    return remaining


def _text_content(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        if "value" in value:
            return str(value.get("value") or "").strip()
        parts = [
            _text_content(value.get(key))
            for key in ("company", "title", "name", "role", "institution", "degree", "field", "detail", "bullets", "items", "highlights")
            if key in value
        ]
        return "\n".join(part for part in parts if part)
    if isinstance(value, list):
        return "\n".join(part for part in (_text_content(item) for item in value) if part)
    return ""


def _is_unintended_wipe(before: object, after: object, reason: str) -> bool:
    before_text = _text_content(before)
    after_text = _text_content(after)
    if len(before_text) < 8 or after_text:
        return False
    deletion_markers = ("移出", "删除", "清空", "不放入", "去掉", "移除", "省略")
    return not any(marker in reason for marker in deletion_markers)


def _align_after_shape(before: object, after: object) -> object:
    """Keep after structurally compatible with before so UI/apply don't get broken JSON blobs."""
    if isinstance(before, dict) and "value" in before:
        if isinstance(after, str):
            return {
                **before,
                "value": after,
                "origin": "ai_rewrite",
            }
        if isinstance(after, dict) and "value" in after:
            merged = {**before, **after}
            merged["value"] = str(after.get("value") or "")
            if after.get("origin"):
                merged["origin"] = after["origin"]
            return merged
        text = _text_content(after)
        return {**before, "value": text, "origin": "ai_rewrite"}

    if isinstance(before, list):
        template = (
            before[0]
            if before and isinstance(before[0], dict) and "value" in before[0]
            else {"value": "", "source_fact_ids": [], "origin": "ai_rewrite", "confidence": 1.0}
        )
        if isinstance(after, str):
            return [{**template, "value": after, "origin": "ai_rewrite"}]
        if isinstance(after, dict) and "value" in after:
            return [{**template, **after, "origin": after.get("origin") or "ai_rewrite"}]
        if isinstance(after, list):
            normalized: list[object] = []
            for index, item in enumerate(after):
                base = (
                    before[index]
                    if index < len(before) and isinstance(before[index], dict)
                    else template
                )
                if isinstance(item, str):
                    normalized.append({**base, "value": item, "origin": "ai_rewrite"} if isinstance(base, dict) else item)
                elif isinstance(item, dict) and "value" in item and isinstance(base, dict):
                    normalized.append({**base, **item})
                else:
                    normalized.append(item)
            return normalized
        return before

    if isinstance(before, dict) and isinstance(after, dict):
        merged = {**before, **after}
        if "id" in before:
            merged["id"] = before["id"]
        for key in ("company", "title", "name", "role", "institution", "degree", "field"):
            if key in before and key in after and not str(after.get(key) or "").strip() and str(before.get(key) or "").strip():
                merged[key] = before[key]
        if "bullets" in before:
            merged["bullets"] = _align_after_shape(before.get("bullets"), after.get("bullets", before.get("bullets")))
        if "items" in before:
            merged["items"] = _align_after_shape(before.get("items"), after.get("items", before.get("items")))
        if "highlights" in before:
            merged["highlights"] = _align_after_shape(
                before.get("highlights"), after.get("highlights", before.get("highlights"))
            )
        if "detail" in before:
            merged["detail"] = _align_after_shape(before.get("detail"), after.get("detail", before.get("detail")))
        return merged

    return after


async def refine_patch_operation(
    provider: AIProvider,
    analysis: JobAnalysis,
    resume: ResumeDocument,
    facts: list[Fact],
    operation: ResumePatchOperation,
    message: str,
    history: list[dict[str, str]] | None = None,
    application_type: ApplicationType = "experienced",
) -> PatchDiscussionResult:
    """Discuss one patch item; only include draft_operation when proposing a concrete rewrite."""
    page_constraint = (
        "校招/实习版本优先保持一页可排版；可建议压缩，不得编造。"
        if application_type in {"campus", "internship"}
        else "社招允许自然分页；仍不得编造经历。"
    )
    prompt = _prompt(
        task="与用户讨论这一条简历修改建议；只有在你同意且准备好具体改写时才给出草案",
        constraints=[
            "这是讨论，不是立即改稿：你可以反驳、追问、指出风险，或解释为何维持原建议更好",
            "reply 必须用中文写完整回复；即使用户要求改写，也先说明你的判断",
            "仅当 proposes_change=true 时才填写 draft_operation；否则 draft_operation 必须为 null",
            "不同意用户意见、需要更多信息、或只是澄清时：proposes_change=false，draft_operation=null",
            "若提出改写：draft_operation 只输出这一条 operation，不要新增其他操作",
            "draft_operation 保持 path 与 op 与当前建议一致，除非用户明确要求改到相邻字段且仍在同一条目语义内",
            "draft_operation.before 必须等于输入中的 current_before（简历当前值）",
            "draft_operation.after 必须与 before 同一结构；清理排版残留（\\item、90/%、\\% 等）为通顺中文与正常百分号",
            "注意版面：避免一行只有几个字；过短内容应合并或基于已有事实写充实一点，不要空疏占行",
            "draft_operation 正文禁止出现任何 UUID 或 fact id",
            "除非明确建议移出/删除，否则不得把有内容的字段改成空",
            "只能改写已有事实，不得编造公司、职位、项目、数字或技能",
            "不要修改姓名、性别、生日、电话、邮箱、微信、政治面貌或证件照",
            "source_fact_ids 必须且只能从 allowed_fact_ids 中选择",
            "draft_operation.reason 用中文说明本轮拟做的调整；正式写入前仍须用户点「采用此改写」",
            page_constraint,
        ],
        data={
            "user_message": message.strip(),
            "discussion_history": history or [],
            "job_analysis": analysis.model_dump(mode="json"),
            "current_before": operation.before,
            "current_operation": operation.model_dump(mode="json"),
            "resume_excerpt": _safe_resume(resume),
            "allowed_fact_ids": [fact.id for fact in facts],
            "fact_catalog": [
                {"id": fact.id, "category": fact.category, "statement": fact.statement}
                for fact in facts
            ],
        },
    )
    result = await _complete_with_repair(provider, prompt, PatchDiscussionResult)
    draft = result.draft_operation
    if not result.proposes_change or draft is None:
        return PatchDiscussionResult(reply=result.reply.strip() or "已收到。", proposes_change=False, draft_operation=None)

    revised = draft.model_copy(
        update={
            "id": operation.id,
            "path": operation.path,
            "op": operation.op,
        }
    )
    grounded = _ground_patch_operations(
        ResumePatch(operations=[revised]),
        resume=resume,
        facts=facts,
    )
    return PatchDiscussionResult(
        reply=result.reply.strip() or "我准备了一版改写，请确认是否采用。",
        proposes_change=True,
        draft_operation=grounded.operations[0],
    )


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
    payload["basics"]["wechat"] = ""
    payload["basics"]["location"] = ""
    if payload["basics"].get("photo_data_url"):
        payload["basics"]["photo_data_url"] = "[已上传证件照]"
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
