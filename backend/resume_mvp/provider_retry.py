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
            before_call_count = _actual_call_count(self.provider)
            result: T | None = None
            retry_error: ProviderNetworkError | ProviderServerError | ProviderRateLimitError | ProviderTimeoutError | TimeoutError | None = None
            try:
                result = await self.provider.complete_json(prompt, schema)
            except (ProviderNetworkError, ProviderServerError, ProviderRateLimitError, ProviderTimeoutError, TimeoutError) as error:
                retry_error = error
            finally:
                self._record_provider_calls(before_call_count)
                self._record_usage(getattr(self.provider, "last_usage", None))

            if retry_error is not None:
                if not _is_retryable(retry_error) or attempt + 1 >= self.policy.max_attempts:
                    raise retry_error
                await self.sleep(self._retry_delay(retry_error, attempt))
                continue
            if result is not None:
                return result

        raise RuntimeError("retry loop exited without a provider result")

    def _retry_delay(
        self,
        error: ProviderNetworkError | ProviderServerError | ProviderRateLimitError | ProviderTimeoutError | TimeoutError,
        attempt: int,
    ) -> float:
        retry_after = error.retry_after_seconds if isinstance(error, ProviderRateLimitError) else None
        if retry_after is not None:
            delay = max(0, retry_after)
        else:
            delay = self.policy.base_delay_seconds * (2 ** attempt)
        return min(self.policy.max_delay_seconds, max(0, self.jitter(delay)))

    def _record_provider_calls(self, before_call_count: int | None) -> None:
        after_call_count = _actual_call_count(self.provider)
        if before_call_count is not None and after_call_count is not None and after_call_count >= before_call_count:
            self.stats.call_count += after_call_count - before_call_count
            return
        self.stats.call_count += 1

    def _record_usage(self, raw_usage: object) -> None:
        try:
            usage = raw_usage if isinstance(raw_usage, ProviderUsage) else ProviderUsage.model_validate(raw_usage)
        except Exception:
            usage = ProviderUsage()
        current = self.stats.usage
        if current is None:
            if usage.input_tokens is None and usage.output_tokens is None:
                return
            self.stats.usage = usage
            return
        self.stats.usage = ProviderUsage(
            input_tokens=_add_optional_tokens(current.input_tokens, usage.input_tokens),
            output_tokens=_add_optional_tokens(current.output_tokens, usage.output_tokens),
        )


def _add_optional_tokens(current: int | None, next_value: int | None) -> int | None:
    if current is None or next_value is None:
        return None
    return current + next_value


def _is_retryable(error: ProviderNetworkError | ProviderServerError | ProviderRateLimitError | ProviderTimeoutError | TimeoutError) -> bool:
    return not isinstance(error, ProviderServerError) or 500 <= error.status_code <= 599


def _actual_call_count(provider: object) -> int | None:
    value = getattr(provider, "actual_call_count", None)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None
