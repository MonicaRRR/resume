from __future__ import annotations

import json
import re
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)


class ProviderError(RuntimeError):
    pass


class ProviderAuthError(ProviderError):
    pass


class ProviderTimeoutError(ProviderError):
    pass


class ProviderFormatError(ProviderError):
    def __init__(self, message: str, *, raw_response: str = "") -> None:
        super().__init__(message)
        self.raw_response = raw_response


class AIProvider(Protocol):
    async def complete_json(self, prompt: str, schema: type[T]) -> T:
        ...


def validate_json_response(raw: str, schema: type[T]) -> T:
    candidate = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1)
    try:
        payload = json.loads(candidate)
        return schema.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as error:
        raise ProviderFormatError("模型没有返回要求的 JSON 结构", raw_response=raw) from error
