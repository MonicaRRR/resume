from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROVIDER_SETTINGS_FILE = "provider_settings.json"


def load_provider_settings(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    # Never trust a persisted API key even if an older build wrote one.
    payload.pop("api_key", None)
    return payload


def save_provider_settings(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    safe = {
        "kind": str(payload.get("kind") or ""),
        "base_url": str(payload.get("base_url") or ""),
        "model": str(payload.get("model") or ""),
        "timeout": float(payload.get("timeout") or 90),
        "temperature": float(payload.get("temperature") or 0.2),
        "codex_confirmed": bool(payload.get("codex_confirmed")),
    }
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
