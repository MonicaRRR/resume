from __future__ import annotations

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


def apply_resume_patch(
    resume: ResumeDocument,
    patch: ResumePatch,
    accepted_operation_ids: set[str],
    *,
    facts: list[Fact],
) -> ResumeDocument:
    payload = resume.model_dump(mode="json")
    fact_ids = {fact.id for fact in facts}

    for operation in patch.operations:
        if operation.id not in accepted_operation_ids:
            continue
        unknown_facts = set(operation.source_fact_ids) - fact_ids
        if unknown_facts:
            raise ValueError(f"缺少事实依据：{', '.join(sorted(unknown_facts))}")
        parts = _pointer_parts(operation.path)
        if not parts or parts[0] not in _ALLOWED_ROOTS:
            raise ValueError("补丁路径不允许修改该字段")
        parent, key = _resolve_parent(payload, parts)
        current = _read(parent, key)
        if current != operation.before:
            raise PatchConflictError(f"{operation.path} 内容已变化，请重新生成建议")
        if operation.op == "replace":
            _write(parent, key, deepcopy(operation.after))
        else:
            if not isinstance(current, list) or not isinstance(operation.after, list):
                raise ValueError("重排操作只能用于列表")
            if sorted(map(str, current)) != sorted(map(str, operation.after)):
                raise ValueError("重排操作不能增加或删除内容")
            _write(parent, key, deepcopy(operation.after))

    return ResumeDocument.model_validate(payload)


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
    if isinstance(parent, dict) and key in parent:
        parent[key] = value
        return
    if isinstance(parent, list) and key.isdigit() and int(key) < len(parent):
        parent[int(key)] = value
        return
    raise ValueError("补丁路径不存在")
