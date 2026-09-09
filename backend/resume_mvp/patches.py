from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from resume_mvp.domain import Fact, ResumeDocument, ResumePatch


class PatchConflictError(ValueError):
    pass


_ALLOWED_ROOTS = {
    "basics",
    "education",
    "work_experience",
    "projects",
    "skills",
    "certificates",
    "awards",
    "custom_sections",
    "section_order",
}

_ROOT_ALIASES = {
    "basic": "basics",
    "work": "work_experience",
    "works": "work_experience",
    "workExperience": "work_experience",
    "workExperiences": "work_experience",
    "work_experiences": "work_experience",
    "experiences": "work_experience",
    "experience": "work_experience",
    "internship": "work_experience",
    "internships": "work_experience",
    "project": "projects",
    "skill": "skills",
    "certificate": "certificates",
    "award": "awards",
    "custom_section": "custom_sections",
    "customSections": "custom_sections",
    "sectionOrder": "section_order",
    "sections": "section_order",
}

_BASICS_SHORTCUTS = {
    "summary",
    "target_role",
    "targetRole",
    "name",
    "email",
    "phone",
    "location",
}


def normalize_patch_path(path: str) -> str:
    """Normalize common AI path mistakes into allowed JSON Pointers."""
    raw = (path or "").strip().replace("\\", "/")
    if not raw:
        return raw
    if not raw.startswith("/"):
        raw = f"/{raw}"
    parts = [part for part in raw.split("/") if part != ""]
    if not parts:
        return "/"
    # Drop accidental resume/document prefixes.
    if parts[0] in {"resume", "document", "data", "payload"} and len(parts) > 1:
        parts = parts[1:]
    root = parts[0]
    if root in _BASICS_SHORTCUTS:
        mapped = "target_role" if root in {"targetRole", "target_role"} else root
        parts = ["basics", mapped, *parts[1:]]
    elif root in _ROOT_ALIASES:
        parts[0] = _ROOT_ALIASES[root]
    elif root == "targetRole":
        parts = ["basics", "target_role", *parts[1:]]
    # camelCase field fixes under known roots
    fixed: list[str] = []
    for index, part in enumerate(parts):
        if index > 0 and part == "targetRole":
            fixed.append("target_role")
        elif index > 0 and part == "sourceFactIds":
            fixed.append("source_fact_ids")
        else:
            fixed.append(part)
    return "/" + "/".join(fixed)


def is_allowed_patch_path(path: str) -> bool:
    try:
        parts = _pointer_parts(normalize_patch_path(path))
    except ValueError:
        return False
    return bool(parts) and parts[0] in _ALLOWED_ROOTS


def apply_resume_patch(
    resume: ResumeDocument,
    patch: ResumePatch,
    accepted_operation_ids: set[str],
    *,
    facts: list[Fact],
) -> ResumeDocument:
    payload = resume.model_dump(mode="json")
    baseline = deepcopy(payload)
    fact_ids = {fact.id for fact in facts}
    accepted = [operation for operation in patch.operations if operation.id in accepted_operation_ids]

    # Validate all accepted ops against the original resume first, then write.
    # Sequential before-checks against an evolving tree break when multiple
    # accepted ops touch related fields in one batch.
    normalized_ops: list[tuple[object, str]] = []
    for operation in accepted:
        unknown_facts = set(operation.source_fact_ids) - fact_ids
        if unknown_facts:
            raise ValueError(f"缺少事实依据：{', '.join(sorted(unknown_facts))}")
        path = normalize_patch_path(operation.path)
        parts = _pointer_parts(path)
        if not parts or parts[0] not in _ALLOWED_ROOTS:
            raise ValueError(f"补丁路径不允许修改该字段：{operation.path}")
        try:
            parent, key = _resolve_parent(baseline, parts)
            current = _read(parent, key)
        except ValueError as error:
            raise ValueError(f"补丁路径不存在：{path}") from error
        if not _equivalent(current, operation.before):
            if _semantic_diverged(current, operation.before):
                raise PatchConflictError(f"{path} 内容已变化，请重新生成建议")
        normalized_ops.append((operation, path))

    for operation, path in normalized_ops:
        parts = _pointer_parts(path)
        parent, key = _resolve_parent(payload, parts)
        current = _read(parent, key)
        if operation.op == "replace":
            _write(parent, key, _ensure_ai_sources(deepcopy(operation.after), operation.source_fact_ids))
        else:
            if not isinstance(current, list) or not isinstance(operation.after, list):
                raise ValueError("重排操作只能用于列表")
            if sorted(map(_canonical, current)) != sorted(map(_canonical, operation.after)):
                raise ValueError("重排操作不能增加或删除内容")
            _write(parent, key, deepcopy(operation.after))

    return ResumeDocument.model_validate(payload)


def read_pointer(resume: ResumeDocument | dict[str, Any], pointer: str) -> Any:
    payload = resume if isinstance(resume, dict) else resume.model_dump(mode="json")
    parts = _pointer_parts(normalize_patch_path(pointer))
    parent, key = _resolve_parent(payload, parts)
    return _read(parent, key)


def _ensure_ai_sources(value: Any, fallback_ids: list[str]) -> Any:
    """Keep ai_rewrite SourcedText nodes valid for ResumeDocument validation."""
    if isinstance(value, dict):
        next_value = {key: _ensure_ai_sources(child, fallback_ids) for key, child in value.items()}
        if "value" in next_value and next_value.get("origin") == "ai_rewrite":
            sources = next_value.get("source_fact_ids")
            if not isinstance(sources, list) or not sources:
                next_value["source_fact_ids"] = list(fallback_ids)
        return next_value
    if isinstance(value, list):
        return [_ensure_ai_sources(item, fallback_ids) for item in value]
    return value


def _pointer_parts(pointer: str) -> list[str]:
    if not pointer.startswith("/"):
        raise ValueError("补丁路径必须是 JSON Pointer")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]


def _resolve_parent(payload: dict[str, Any], parts: list[str]) -> tuple[Any, str]:
    current: Any = payload
    for part in parts[:-1]:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise ValueError("补丁路径不存在")
    return current, parts[-1]


def _read(parent: Any, key: str) -> Any:
    if isinstance(parent, dict) and key in parent:
        return parent[key]
    if isinstance(parent, list) and key.isdigit() and int(key) < len(parent):
        return parent[int(key)]
    raise ValueError("补丁路径不存在")


def _write(parent: Any, key: str, value: Any) -> None:
    if isinstance(parent, dict):
        parent[key] = value
        return
    if isinstance(parent, list) and key.isdigit() and int(key) < len(parent):
        parent[int(key)] = value
        return
    raise ValueError("补丁路径不存在")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _equivalent(left: Any, right: Any) -> bool:
    if left == right:
        return True
    return _canonical(left) == _canonical(right)


def _textish(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict) and "value" in value:
        return str(value.get("value") or "").strip()
    if isinstance(value, list):
        return "\n".join(_textish(item) for item in value)
    if isinstance(value, dict):
        parts = [
            _textish(value.get(key))
            for key in ("company", "title", "name", "role", "institution", "bullets", "items", "highlights", "detail")
            if key in value
        ]
        text = "\n".join(part for part in parts if part)
        if text:
            return text
    return _canonical(value)


def _semantic_diverged(current: Any, before: Any) -> bool:
    """True when live content no longer matches the suggestion baseline in substance."""
    current_text = _textish(current)
    before_text = _textish(before)
    if current_text or before_text:
        return current_text != before_text
    return not _equivalent(current, before)
