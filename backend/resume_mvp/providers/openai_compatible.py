from __future__ import annotations

from typing import TypeVar

import httpx
from pydantic import BaseModel

from resume_mvp.providers.base import (
    ProviderAuthError,
    ProviderError,
    ProviderTimeoutError,
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

    async def complete_json(self, prompt: str, schema: type[T]) -> T:
        client = self._client or httpx.AsyncClient()
        owns_client = self._client is None
        try:
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
            raise ProviderError("无法连接模型服务") from error
        finally:
            if owns_client:
                await client.aclose()

        if response.status_code in {401, 403}:
            raise ProviderAuthError("模型服务拒绝了凭据")
        if not response.is_success:
            raise ProviderError(f"模型服务返回错误状态 {response.status_code}")
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise ProviderError("模型服务响应缺少消息内容") from error
        if not isinstance(content, str):
            raise ProviderError("模型服务响应消息不是文本")
        return validate_json_response(content, schema)

    def _chat_url(self) -> str:
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"
