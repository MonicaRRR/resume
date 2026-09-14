from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from resume_mvp.domain import ResumeDocument
from resume_mvp.providers.base import AIProvider, ProviderError


class PageField(BaseModel):
    id: str = Field(min_length=1)
    tag: str = "input"
    type: str = "text"
    name: str = ""
    label: str = ""
    placeholder: str = ""
    aria_label: str = ""
    nearby_text: str = ""
    options: list[str] = Field(default_factory=list)


class FillAction(BaseModel):
    field_id: str
    value: str
    profile_key: str
    source: Literal["rules", "agent"] = "rules"


class EmptyReminder(BaseModel):
    field_id: str
    label: str = ""
    profile_key: str | None = None
    reason: str = "经历库无对应内容，已留空"


class AutofillPlan(BaseModel):
    actions: list[FillAction] = Field(default_factory=list)
    empty_reminders: list[EmptyReminder] = Field(default_factory=list)
    unmatched_fields: list[str] = Field(default_factory=list)
    mode: Literal["rules", "hybrid"] = "rules"
    warnings: list[str] = Field(default_factory=list)


class AgentFillMapping(BaseModel):
    field_id: str
    profile_key: str = ""


class AgentAutofillResponse(BaseModel):
    mappings: list[AgentFillMapping] = Field(default_factory=list)
    empty_field_ids: list[str] = Field(default_factory=list)


_SUBMIT_HINTS = ("投递", "提交", "申请", "发送简历", "立即申请", "confirm", "submit", "apply now")
_SKIP_TYPES = {"password", "file", "hidden", "checkbox", "radio", "button", "submit", "reset", "image"}

# Longer aliases first within each key for more specific matches.
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("真实姓名", "姓名", "名字", "full name", "fullname", "name"),
    "phone": ("手机号码", "手机号", "联系电话", "电话", "手机", "mobile", "phone", "tel"),
    "email": ("电子邮箱", "邮箱", "邮件", "e-mail", "email"),
    "gender": ("性别", "gender", "sex"),
    "birthday": ("出生日期", "出生年月", "生日", "birthday", "date of birth", "dob"),
    "location": ("现居住地", "所在城市", "工作城市", "城市", "地点", "住址", "location", "city"),
    "wechat": ("微信号", "微信", "wechat", "weixin"),
    "political_status": ("政治面貌", "政治状况", "political"),
    "target_role": ("期望职位", "目标职位", "求职意向", "意向岗位", "target role", "desired position"),
    "summary": ("个人简介", "自我评价", "个人总结", "summary", "about me"),
    "education.0.institution": ("毕业院校", "学校名称", "院校", "学校", "university", "school", "college"),
    "education.0.field": ("所学专业", "专业名称", "专业", "major", "field of study"),
    "education.0.degree": ("学历学位", "最高学历", "学历", "学位", "degree"),
    "education.0.start_date": ("入学时间", "入学日期", "education start"),
    "education.0.end_date": ("毕业时间", "毕业日期", "education end"),
    "work_experience.0.company": ("公司名称", "就职公司", "工作单位", "公司", "company", "employer"),
    "work_experience.0.title": ("职位名称", "岗位名称", "担任职务", "职位", "职务", "job title", "title", "position"),
    "work_experience.0.start_date": ("入职时间", "工作开始", "work start"),
    "work_experience.0.end_date": ("离职时间", "工作结束", "work end"),
    "work_experience.0.bullets": ("工作内容", "工作描述", "岗位职责", "工作经历描述", "job description"),
    "projects.0.name": ("项目名称", "项目名", "project name"),
    "projects.0.role": ("项目角色", "担任角色", "project role"),
    "projects.0.bullets": ("项目描述", "项目经历", "project description"),
    "skills": ("专业技能", "技能特长", "掌握技能", "技能", "skills"),
}


def flatten_profile(resume: ResumeDocument) -> dict[str, str]:
    """Stable key → value map for autofill. Empty strings mean unavailable."""
    basics = resume.basics
    flat: dict[str, str] = {
        "name": basics.name.strip(),
        "phone": basics.phone.strip(),
        "email": basics.email.strip(),
        "gender": basics.gender.strip(),
        "birthday": basics.birthday.strip(),
        "location": basics.location.strip(),
        "wechat": basics.wechat.strip(),
        "political_status": basics.political_status.strip(),
        "target_role": basics.target_role.value.strip(),
        "summary": basics.summary.value.strip(),
    }
    for index, item in enumerate(resume.education):
        prefix = f"education.{index}"
        flat[f"{prefix}.institution"] = item.institution.strip()
        flat[f"{prefix}.field"] = item.field.strip()
        flat[f"{prefix}.degree"] = item.degree.strip()
        flat[f"{prefix}.start_date"] = item.start_date.strip()
        flat[f"{prefix}.end_date"] = item.end_date.strip()
        highlights = "；".join(h.value.strip() for h in item.highlights if h.value.strip())
        flat[f"{prefix}.highlights"] = highlights
    for index, item in enumerate(resume.work_experience):
        prefix = f"work_experience.{index}"
        flat[f"{prefix}.company"] = item.company.strip()
        flat[f"{prefix}.title"] = item.title.strip()
        flat[f"{prefix}.start_date"] = item.start_date.strip()
        flat[f"{prefix}.end_date"] = item.end_date.strip()
        bullets = "；".join(b.value.strip() for b in item.bullets if b.value.strip())
        flat[f"{prefix}.bullets"] = bullets
    for index, item in enumerate(resume.projects):
        prefix = f"projects.{index}"
        flat[f"{prefix}.name"] = item.name.strip()
        flat[f"{prefix}.role"] = item.role.strip()
        flat[f"{prefix}.start_date"] = item.start_date.strip()
        flat[f"{prefix}.end_date"] = item.end_date.strip()
        bullets = "；".join(b.value.strip() for b in item.bullets if b.value.strip())
        flat[f"{prefix}.bullets"] = bullets
    skill_parts: list[str] = []
    for group in resume.skills:
        for entry in group.items:
            text = entry.value.strip()
            if text:
                skill_parts.append(text)
    flat["skills"] = "、".join(skill_parts)
    return flat


def _normalize(text: str) -> str:
    return re.sub(r"[\s\-_:：·•]+", "", text.strip().lower())


def _field_haystack(field: PageField) -> str:
    parts = [field.label, field.placeholder, field.aria_label, field.name, field.nearby_text]
    return _normalize(" ".join(parts))


def _field_display_label(field: PageField) -> str:
    for candidate in (field.label, field.aria_label, field.placeholder, field.name, field.nearby_text):
        if candidate.strip():
            return candidate.strip()
    return field.id


def _looks_like_submit(field: PageField) -> bool:
    if field.tag.lower() == "button" or field.type.lower() in {"submit", "button"}:
        return True
    haystack = _field_haystack(field)
    return any(_normalize(hint) in haystack for hint in _SUBMIT_HINTS)


def is_fillable_field(field: PageField) -> bool:
    if field.type.lower() in _SKIP_TYPES:
        return False
    if _looks_like_submit(field):
        return False
    return field.tag.lower() in {"input", "textarea", "select"}


def match_profile_key(field: PageField, available_keys: set[str]) -> str | None:
    """Return best profile key alias hit, preferring keys that exist in the flat map."""
    haystack = _field_haystack(field)
    if not haystack:
        return None
    hits: list[tuple[int, str]] = []
    for key, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            normalized_alias = _normalize(alias)
            if normalized_alias and normalized_alias in haystack:
                # Prefer longer alias match; then prefer keys that exist in profile map.
                score = len(normalized_alias) * 10 + (1 if key in available_keys else 0)
                hits.append((score, key))
                break
    if not hits:
        return None
    hits.sort(key=lambda item: item[0], reverse=True)
    return hits[0][1]


def build_rules_plan(fields: list[PageField], profile: dict[str, str]) -> AutofillPlan:
    actions: list[FillAction] = []
    empty_reminders: list[EmptyReminder] = []
    unmatched: list[str] = []
    available = set(profile)

    for field in fields:
        if not is_fillable_field(field):
            continue
        key = match_profile_key(field, available)
        if key is None:
            unmatched.append(field.id)
            continue
        value = profile.get(key, "").strip()
        if value:
            actions.append(
                FillAction(field_id=field.id, value=value, profile_key=key, source="rules")
            )
        else:
            empty_reminders.append(
                EmptyReminder(
                    field_id=field.id,
                    label=_field_display_label(field),
                    profile_key=key,
                    reason="经历库无对应内容，已留空",
                )
            )
    return AutofillPlan(
        actions=actions,
        empty_reminders=empty_reminders,
        unmatched_fields=unmatched,
        mode="rules",
        warnings=[],
    )


def _apply_agent_mappings(
    plan: AutofillPlan,
    *,
    fields_by_id: dict[str, PageField],
    profile: dict[str, str],
    remaining_ids: set[str],
    agent: AgentAutofillResponse,
) -> AutofillPlan:
    claimed = {action.field_id for action in plan.actions} | {
        item.field_id for item in plan.empty_reminders
    }
    for mapping in agent.mappings:
        if mapping.field_id not in remaining_ids or mapping.field_id in claimed:
            continue
        key = mapping.profile_key.strip()
        if not key or key not in profile:
            continue
        field = fields_by_id.get(mapping.field_id)
        if field is None or not is_fillable_field(field):
            continue
        value = profile[key].strip()
        if value:
            plan.actions.append(
                FillAction(
                    field_id=mapping.field_id,
                    value=value,
                    profile_key=key,
                    source="agent",
                )
            )
        else:
            plan.empty_reminders.append(
                EmptyReminder(
                    field_id=mapping.field_id,
                    label=_field_display_label(field),
                    profile_key=key,
                    reason="经历库无对应内容，已留空",
                )
            )
        claimed.add(mapping.field_id)
        remaining_ids.discard(mapping.field_id)

    for field_id in agent.empty_field_ids:
        if field_id not in remaining_ids or field_id in claimed:
            continue
        field = fields_by_id.get(field_id)
        if field is None:
            continue
        plan.empty_reminders.append(
            EmptyReminder(
                field_id=field_id,
                label=_field_display_label(field),
                profile_key=None,
                reason="未能从经历库匹配，已留空，请人工核对",
            )
        )
        claimed.add(field_id)
        remaining_ids.discard(field_id)

    plan.unmatched_fields = sorted(remaining_ids)
    plan.mode = "hybrid"
    return plan


async def build_autofill_plan(
    fields: list[PageField],
    profile: dict[str, str],
    *,
    provider: AIProvider | None = None,
    page_url: str = "",
    page_title: str = "",
) -> AutofillPlan:
    plan = build_rules_plan(fields, profile)
    remaining = set(plan.unmatched_fields)
    if not remaining or provider is None:
        return plan

    fields_by_id = {field.id: field for field in fields}
    remaining_fields = [fields_by_id[field_id] for field_id in remaining if field_id in fields_by_id]
    non_empty_profile = {key: value for key, value in profile.items() if value}
    preview = {
        key: (value[:80] + "…" if len(value) > 80 else value)
        for key, value in non_empty_profile.items()
    }
    prompt = (
        "你是招聘网站在线简历表单的字段映射助手。只输出 JSON。\n"
        "规则：\n"
        "1. 只能把页面字段映射到 profile_keys 里已有的键；禁止编造经历内容。\n"
        "2. mappings 里 profile_key 必须来自 profile_keys；若页面字段需要填写但经历库没有合适键或值为空，放入 empty_field_ids。\n"
        "3. 不要建议点击投递/提交/申请按钮。\n"
        "4. 只处理 remaining_fields。\n"
        f"page_title: {page_title}\n"
        f"page_url: {page_url}\n"
        f"profile_keys: {json.dumps(sorted(non_empty_profile.keys()), ensure_ascii=False)}\n"
        f"profile_preview: {json.dumps(preview, ensure_ascii=False)}\n"
        f"remaining_fields: {json.dumps([field.model_dump() for field in remaining_fields], ensure_ascii=False)}\n"
        '返回形如 {"mappings":[{"field_id":"...","profile_key":"..."}],"empty_field_ids":["..."]} 的 JSON。'
    )
    try:
        agent = await provider.complete_json(prompt, AgentAutofillResponse)
    except ProviderError as error:
        plan.warnings.append(f"模型补洞失败，已降级为纯规则：{error}")
        return plan
    except Exception as error:  # noqa: BLE001 — never block fill on agent crash
        plan.warnings.append(f"模型补洞异常，已降级为纯规则：{error}")
        return plan

    return _apply_agent_mappings(
        plan,
        fields_by_id=fields_by_id,
        profile=profile,
        remaining_ids=remaining,
        agent=agent,
    )
