from __future__ import annotations

from resume_mvp.domain import Fact, ResumeDocument, new_id


def facts_from_resume(resume: ResumeDocument) -> list[Fact]:
    """Derive confirmed facts from the user's profile library for AI grounding."""
    facts: list[Fact] = []

    def add(category: str, statement: str, location: str) -> str | None:
        text = statement.strip()
        if not text:
            return None
        fact_id = new_id()
        facts.append(
            Fact(
                id=fact_id,
                category=category,
                statement=text,
                source_type="manual",
                source_location=location,
                user_confirmed=True,
            )
        )
        return fact_id

    basics = resume.basics
    if basics.name.strip():
        add("基本信息", f"姓名：{basics.name.strip()}", "基本信息")
    if basics.gender.strip():
        add("基本信息", f"性别：{basics.gender.strip()}", "基本信息")
    if basics.birthday.strip():
        add("基本信息", f"生日：{basics.birthday.strip()}", "基本信息")
    if basics.political_status.strip():
        add("基本信息", f"政治面貌：{basics.political_status.strip()}", "基本信息")
    if basics.target_role.value.strip():
        add("基本信息", f"期望职位：{basics.target_role.value.strip()}", "基本信息")
    if basics.location.strip():
        add("基本信息", f"所在城市：{basics.location.strip()}", "基本信息")
    if basics.wechat.strip():
        add("基本信息", f"微信：{basics.wechat.strip()}", "基本信息")
    if basics.photo_data_url.strip():
        add("基本信息", "已上传证件照", "基本信息")
    if basics.summary.value.strip():
        fact_id = add("个人概述", basics.summary.value, "个人概述")
        if fact_id:
            basics.summary.source_fact_ids = [fact_id]
            basics.summary.origin = "manual"

    for item in resume.education:
        header = " · ".join(
            part for part in [
                item.institution,
                item.degree,
                item.field,
                " ~ ".join(part for part in [item.start_date, item.end_date] if part),
            ] if part
        )
        header_id = add("教育经历", header, "教育经历") if header else None
        for highlight in item.highlights:
            if not highlight.value.strip():
                continue
            fact_id = add("教育经历", highlight.value, "教育亮点")
            if fact_id:
                highlight.source_fact_ids = [fact_id]
                highlight.origin = "manual"
        if header_id and not item.highlights:
            pass

    for item in resume.work_experience:
        header = " · ".join(
            part for part in [
                item.company,
                item.title,
                " ~ ".join(part for part in [item.start_date, item.end_date] if part),
            ] if part
        )
        header_id = add("工作/实习经历", header, "工作经历") if header else None
        for bullet in item.bullets:
            if not bullet.value.strip():
                continue
            fact_id = add("工作/实习经历", bullet.value, "工作要点")
            if fact_id:
                bullet.source_fact_ids = [header_id, fact_id] if header_id else [fact_id]
                bullet.origin = "manual"

    for item in resume.projects:
        header = " · ".join(
            part for part in [
                item.name,
                item.role,
                " ~ ".join(part for part in [item.start_date, item.end_date] if part),
            ] if part
        )
        header_id = add("项目经历", header, "项目经历") if header else None
        for bullet in item.bullets:
            if not bullet.value.strip():
                continue
            fact_id = add("项目经历", bullet.value, "项目要点")
            if fact_id:
                bullet.source_fact_ids = [header_id, fact_id] if header_id else [fact_id]
                bullet.origin = "manual"

    skill_values = [item.value.strip() for group in resume.skills for item in group.items if item.value.strip()]
    if skill_values:
        skill_fact = add("专业技能", "、".join(skill_values), "专业技能")
        for group in resume.skills:
            for item in group.items:
                if item.value.strip() and skill_fact:
                    item.source_fact_ids = [skill_fact]
                    item.origin = "manual"

    return facts


def profile_is_ready(resume: ResumeDocument) -> bool:
    has_name = bool(resume.basics.name.strip())
    has_experience = any(
        [
            any(item.institution.strip() for item in resume.education),
            any(item.company.strip() or item.title.strip() for item in resume.work_experience),
            any(item.name.strip() for item in resume.projects),
            any(item.value.strip() for group in resume.skills for item in group.items),
        ]
    )
    return has_name and has_experience
