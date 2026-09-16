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


class ProviderNetworkError(ProviderError):
    pass


class ProviderServerError(ProviderError):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class ProviderRateLimitError(ProviderError):
    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ProviderFormatError(ProviderError):
    def __init__(self, message: str, *, raw_response: str = "", validation_errors: list[dict] | None = None) -> None:
        super().__init__(message)
        self.raw_response = raw_response
        self.validation_errors = validation_errors or []


class ProviderUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None


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
    except ValidationError as error:
        details = [{"loc": list(item["loc"]), "type": item["type"]} for item in error.errors()]
        raise ProviderFormatError(
            "模型返回字段类型不符合要求", raw_response=raw, validation_errors=details
        ) from error
    except json.JSONDecodeError as error:
        raise ProviderFormatError("模型没有返回要求的 JSON 结构", raw_response=raw) from error
