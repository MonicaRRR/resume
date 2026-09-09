"""Normalize resume content for dense, printable layout without inventing facts."""

from __future__ import annotations

from resume_mvp.domain import ResumeDocument, SkillGroup, SourcedText


_GENERIC_SKILL_NAMES = {"", "技能", "专业技能", "skills", "skill"}


def tidy_resume_for_layout(resume: ResumeDocument) -> ResumeDocument:
    """Drop empty shells and normalize skill groups before export / preview."""
    cleaned = resume.model_copy(deep=True)
    cleaned.skills = normalize_skill_groups(cleaned.skills)

    cleaned.work_experience = [
        item
        for item in cleaned.work_experience
        if item.company.strip() or item.title.strip() or any(bullet.value.strip() for bullet in item.bullets)
    ]
    for item in cleaned.work_experience:
        item.bullets = _merge_sparse_bullets(_nonempty_sourced(item.bullets))

    cleaned.projects = [
        item
        for item in cleaned.projects
        if item.name.strip() or item.role.strip() or any(bullet.value.strip() for bullet in item.bullets)
    ]
    for item in cleaned.projects:
        item.bullets = _merge_sparse_bullets(_nonempty_sourced(item.bullets))

    cleaned.education = [
        item
        for item in cleaned.education
        if item.institution.strip() or item.degree.strip() or item.field.strip()
    ]
    for item in cleaned.education:
        item.highlights = _nonempty_sourced(item.highlights)

    cleaned.certificates = [item for item in cleaned.certificates if item.name.strip()]
    cleaned.awards = [item for item in cleaned.awards if item.name.strip()]
    cleaned.custom_sections = [
        section.model_copy(update={"items": _nonempty_sourced(section.items)})
        for section in cleaned.custom_sections
        if section.title.strip() and any(entry.value.strip() for entry in section.items)
    ]
    return cleaned


def normalize_skill_groups(groups: list[SkillGroup]) -> list[SkillGroup]:
    named: list[SkillGroup] = []
    generic_items: list[SourcedText] = []

    for group in groups:
        expanded = _expand_skill_items(_nonempty_sourced(group.items))
        if not expanded:
            continue
        if is_generic_skill_group_name(group.name):
            generic_items.extend(expanded)
            continue
        named.append(
            SkillGroup(
                id=group.id,
                name=group.name.strip(),
                items=_dedupe_sourced(expanded),
            )
        )

    if generic_items:
        named.append(SkillGroup(name="专业技能", items=_dedupe_sourced(generic_items)))
    return named


def is_generic_skill_group_name(name: str) -> bool:
    return name.strip().lower() in _GENERIC_SKILL_NAMES


def skill_lines_for_export(groups: list[SkillGroup]) -> list[str]:
    """One printable line per skill point; avoid repeating '专业技能' under the section heading."""
    lines: list[str] = []
    for group in normalize_skill_groups(groups):
        items = [item.value.strip() for item in group.items if item.value.strip()]
        if not items:
            continue
        if is_generic_skill_group_name(group.name):
            lines.extend(items)
            continue
        lines.append(f"{group.name}：{'、'.join(items)}")
    return lines


def _nonempty_sourced(items: list[SourcedText]) -> list[SourcedText]:
    return [item for item in items if item.value.strip()]


def _dedupe_sourced(items: list[SourcedText]) -> list[SourcedText]:
    seen: set[str] = set()
    result: list[SourcedText] = []
    for item in items:
        key = item.value.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _expand_skill_items(items: list[SourcedText]) -> list[SourcedText]:
    expanded: list[SourcedText] = []
    for item in items:
        parts = _split_skill_tokens(item.value)
        if len(parts) <= 1:
            expanded.append(item)
            continue
        for part in parts:
            expanded.append(
                SourcedText(
                    value=part,
                    source_fact_ids=list(item.source_fact_ids),
                    origin=item.origin,
                    confidence=item.confidence,
                )
            )
    return expanded


def _split_skill_tokens(value: str) -> list[str]:
    text = value.strip()
    if "：" in text or ":" in text:
        return [text]
    if len(text) > 40:
        return [text]
    parts = [part.strip() for part in text.replace("，", "、").replace(",", "、").split("、")]
    parts = [part for part in parts if part]
    if len(parts) < 2:
        return [text]
    if any(len(part) > 18 for part in parts):
        return [text]
    return parts


def _merge_sparse_bullets(items: list[SourcedText]) -> list[SourcedText]:
    """Merge consecutive ultra-short bullets so the page does not look hollow."""
    if len(items) < 2:
        return items
    merged: list[SourcedText] = []
    buffer: list[SourcedText] = []

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        if len(buffer) == 1:
            merged.append(buffer[0])
        else:
            first = buffer[0]
            fact_ids: list[str] = []
            for item in buffer:
                fact_ids.extend(item.source_fact_ids)
            merged.append(
                SourcedText(
                    value="；".join(item.value.strip() for item in buffer),
                    source_fact_ids=list(dict.fromkeys(fact_ids)),
                    origin=first.origin,
                    confidence=min(item.confidence for item in buffer),
                )
            )
        buffer = []

    for item in items:
        if len(item.value.strip()) <= 8:
            buffer.append(item)
            if len(buffer) >= 3:
                flush()
            continue
        flush()
        merged.append(item)
    flush()
    return merged
