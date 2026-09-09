from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pydantic import BaseModel, Field

from resume_mvp.providers.base import (
    AIProvider,
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderUsage,
)


T = TypeVar("T", bound=BaseModel)
Sleep = Callable[[float], Awaitable[None]]
Jitter = Callable[[float], float]


class ProviderCallStats(BaseModel):
    call_count: int = Field(default=0, ge=0)
    usage: ProviderUsage | None = None


class RetryPolicy(BaseModel):
    max_attempts: int = Field(default=3, ge=1)
    base_delay_seconds: float = Field(default=1, ge=0)
    max_delay_seconds: float = Field(default=30, ge=0)


class RetryingProvider:
    """Apply a bounded retry policy without changing the AIProvider call contract."""

    def __init__(
        self,
        provider: AIProvider,
        *,
        policy: RetryPolicy | None = None,
        sleep: Sleep = asyncio.sleep,
        jitter: Jitter | None = None,
    ) -> None:
        self.provider = provider
        self.policy = policy or RetryPolicy()
        self.sleep = sleep
        self.jitter = jitter or (lambda delay: delay)
        self.stats = ProviderCallStats()

    async def complete_json(self, prompt: str, schema: type[T]) -> T:
        for attempt in range(self.policy.max_attempts):
            self.stats.call_count += 1
            try:
                result = await self.provider.complete_json(prompt, schema)
            except (ProviderNetworkError, ProviderServerError, ProviderRateLimitError, ProviderTimeoutError, TimeoutError) as error:
                if attempt + 1 >= self.policy.max_attempts:
                    raise
                await self.sleep(self._retry_delay(error, attempt))
                continue
            self._record_usage(getattr(self.provider, "last_usage", None))
            return result

        raise RuntimeError("retry loop exited without a provider result")

    def _retry_delay(
        self,
        error: ProviderNetworkError | ProviderServerError | ProviderRateLimitError | ProviderTimeoutError | TimeoutError,
        attempt: int,
    ) -> float:
        retry_after = error.retry_after_seconds if isinstance(error, ProviderRateLimitError) else None
        if retry_after is not None:
            delay = min(self.policy.max_delay_seconds, max(0, retry_after))
        else:
            delay = min(self.policy.max_delay_seconds, self.policy.base_delay_seconds * (2 ** attempt))
        return max(0, self.jitter(delay))

    def _record_usage(self, raw_usage: object) -> None:
        if raw_usage is None:
            return
        try:
            usage = raw_usage if isinstance(raw_usage, ProviderUsage) else ProviderUsage.model_validate(raw_usage)
        except Exception:
            return
        if usage.input_tokens is None and usage.output_tokens is None:
            return
        current = self.stats.usage
        if current is None:
            self.stats.usage = usage
            return
        self.stats.usage = ProviderUsage(
            input_tokens=_add_optional_tokens(current.input_tokens, usage.input_tokens),
            output_tokens=_add_optional_tokens(current.output_tokens, usage.output_tokens),
        )


def _add_optional_tokens(current: int | None, next_value: int | None) -> int | None:
    if current is None:
        return next_value
    if next_value is None:
        return current
    return current + next_value
