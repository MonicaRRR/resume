from __future__ import annotations

import re
from typing import Any


_PERCENT_SLASH = re.compile(r"(\d+(?:\.\d+)?)\s*/\s*%")
_LATEX_PERCENT = re.compile(r"\\%")
_UUID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_LATEX_COMMON = [
    (re.compile(r"\\item\b\s*", re.IGNORECASE), ""),
    (re.compile(r"\\&"), "&"),
    (re.compile(r"\\_"), "_"),
    (re.compile(r"\\\$"), "$"),
    (re.compile(r"\\#"), "#"),
    (re.compile(r"\\\\"), "\n"),
]
_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_MULTI_NL = re.compile(r"\n{3,}")

_META_KEYS = {
    "id",
    "source_fact_ids",
    "jd_requirement_ids",
    "origin",
    "confidence",
    "op",
    "path",
    "risk",
}
_TEXT_KEYS = {
    "value",
    "name",
    "title",
    "company",
    "role",
    "institution",
    "degree",
    "field",
    "reason",
    "statement",
}


def tidy_paste_artifacts(text: str) -> str:
    """Fix paste artifacts and strip leaked fact UUIDs from human-readable text."""
    if not text:
        return text
    cleaned = text.replace("\r\n", "\n")
    cleaned = _LATEX_PERCENT.sub("%", cleaned)
    cleaned = _PERCENT_SLASH.sub(r"\1%", cleaned)
    cleaned = _UUID.sub("", cleaned)
    if "\\" in cleaned:
        for pattern, replacement in _LATEX_COMMON:
            cleaned = pattern.sub(replacement, cleaned)
    cleaned = _MULTI_SPACE.sub(" ", cleaned)
    cleaned = _MULTI_NL.sub("\n\n", cleaned)
    cleaned = re.sub(r"[（\[]\s*[）\]]", "", cleaned)
    cleaned = re.sub(r"\s+([，。；、,.])", r"\1", cleaned)
    return cleaned.strip()


def tidy_value_tree(node: Any) -> Any:
    """Tidy human text leaves; never rewrite id / source_fact_ids arrays."""
    if isinstance(node, str):
        return tidy_paste_artifacts(node)
    if isinstance(node, list):
        return [tidy_value_tree(item) for item in node]
    if isinstance(node, dict):
        cleaned: dict[str, Any] = {}
        for key, value in node.items():
            if key in _META_KEYS:
                cleaned[key] = value
            elif key in _TEXT_KEYS and isinstance(value, str):
                cleaned[key] = tidy_paste_artifacts(value)
            else:
                cleaned[key] = tidy_value_tree(value)
        return cleaned
    return node
