from __future__ import annotations

import math
import re
from typing import TypeVar

import httpx
from pydantic import BaseModel

from resume_mvp.providers.base import (
    ProviderAuthError,
    ProviderError,
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderUsage,
    validate_json_response,
)


T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 90,
        temperature: float = 0.2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self._client = client
        self.last_usage: ProviderUsage | None = None
        self.actual_call_count = 0

    async def complete_json(self, prompt: str, schema: type[T]) -> T:
        self.last_usage = None
        client = self._client or httpx.AsyncClient()
        owns_client = self._client is None
        try:
            self.actual_call_count += 1
            response = await client.post(
                self._chat_url(),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是中文求职材料助手。只返回符合要求的 JSON。",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": self.temperature,
                    "response_format": {"type": "json_object"},
                },
                timeout=self.timeout,
            )
        except httpx.TimeoutException as error:
            raise ProviderTimeoutError("模型请求超时") from error
        except httpx.HTTPError as error:
            raise ProviderNetworkError("无法连接模型服务") from error
        finally:
            if owns_client:
                await client.aclose()

        if response.status_code in {401, 403}:
            raise ProviderAuthError("模型服务拒绝了凭据")
        if response.status_code == 429:
            raise ProviderRateLimitError(
                "模型服务请求过于频繁",
                retry_after_seconds=_retry_after_seconds(response.headers.get("Retry-After")),
            )
        if 500 <= response.status_code <= 599:
            raise ProviderServerError(
                f"模型服务返回错误状态 {response.status_code}",
                status_code=response.status_code,
            )
        if not response.is_success:
            raise ProviderError(f"模型服务返回错误状态 {response.status_code}")
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise ProviderError("模型服务响应缺少消息内容") from error
        if not isinstance(content, str):
            raise ProviderError("模型服务响应消息不是文本")
        self.last_usage = _usage_from_payload(payload)
        return validate_json_response(content, schema)

    def _chat_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        if re.search(r"/v\d+(?:\.\d+)?$", self.base_url):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"


def _retry_after_seconds(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if not math.isfinite(parsed) or parsed < 0:
        return None
    return parsed


def _usage_from_payload(payload: object) -> ProviderUsage | None:
    if not isinstance(payload, dict):
        return None
    raw_usage = payload.get("usage")
    if not isinstance(raw_usage, dict):
        return None
    input_tokens = raw_usage.get("prompt_tokens")
    output_tokens = raw_usage.get("completion_tokens")
    input_value = input_tokens if isinstance(input_tokens, int) and not isinstance(input_tokens, bool) else None
    output_value = output_tokens if isinstance(output_tokens, int) and not isinstance(output_tokens, bool) else None
    if input_value is None and output_value is None:
        return None
    return ProviderUsage(input_tokens=input_value, output_tokens=output_value)
