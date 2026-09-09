from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from resume_mvp.provider_retry import RetryingProvider, RetryPolicy
from resume_mvp.providers.base import (
    ProviderAuthError,
    ProviderFormatError,
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderTimeoutError,
    ProviderUsage,
)
from resume_mvp.providers.codex import CodexProvider, ProcessResult


class Probe(BaseModel):
    ok: bool


class FlakyProvider:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls = 0
        self.last_usage: ProviderUsage | None = None

    async def complete_json(self, prompt: str, schema: type[Probe]) -> Probe:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, tuple):
            response, usage = outcome
            self.last_usage = usage
            if isinstance(response, Exception):
                raise response
            return schema.model_validate(response)
        if isinstance(outcome, Exception):
            raise outcome
        self.last_usage = None
        return schema.model_validate(outcome)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error",
    [
        ProviderNetworkError("网络中断"),
        ProviderServerError("服务不可用", status_code=502),
        ProviderRateLimitError("请求过于频繁", retry_after_seconds=1),
        ProviderTimeoutError("模型请求超时"),
    ],
)
async def test_retries_each_recoverable_provider_error(error: Exception) -> None:
    """A recoverable first failure must lead to a second real provider call."""
    provider = FlakyProvider([error, {"ok": True}])
    sleep = AsyncMock()

    result = await RetryingProvider(provider, sleep=sleep).complete_json("ping", Probe)

    assert result.ok is True
    assert provider.calls == 2
    assert sleep.await_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "error",
    [ProviderAuthError("凭据无效"), ProviderFormatError("格式错误", raw_response="not-json")],
)
async def test_does_not_retry_auth_or_format_errors(error: Exception) -> None:
    """Changing retry classification to include auth or malformed JSON must fail this test."""
    provider = FlakyProvider([error])
    sleep = AsyncMock()
    wrapped = RetryingProvider(provider, sleep=sleep)

    with pytest.raises(type(error)):
        await wrapped.complete_json("ping", Probe)

    assert provider.calls == 1
    assert wrapped.stats.call_count == 1
    sleep.assert_not_awaited()


@pytest.mark.anyio
async def test_does_not_retry_non_5xx_server_errors() -> None:
    """Broadening server retries beyond 5xx must cause a second underlying call here."""
    provider = FlakyProvider([ProviderServerError("not found", status_code=404), {"ok": True}])
    sleep = AsyncMock()
    wrapped = RetryingProvider(provider, sleep=sleep)

    with pytest.raises(ProviderServerError) as error:
        await wrapped.complete_json("ping", Probe)

    assert error.value.status_code == 404
    assert provider.calls == 1
    assert wrapped.stats.call_count == 1
    sleep.assert_not_awaited()


@pytest.mark.anyio
async def test_stops_at_max_attempts_with_capped_exponential_backoff() -> None:
    """Removing the attempt bound or delay cap must make the call and delay assertions fail."""
    provider = FlakyProvider([ProviderServerError("bad gateway", 502)] * 3)
    sleep = AsyncMock()
    wrapped = RetryingProvider(
        provider,
        policy=RetryPolicy(max_attempts=3, base_delay_seconds=2, max_delay_seconds=3),
        sleep=sleep,
        jitter=lambda delay: delay + 0.5,
    )

    with pytest.raises(ProviderServerError):
        await wrapped.complete_json("ping", Probe)

    assert provider.calls == 3
    assert wrapped.stats.call_count == 3
    assert [call.args[0] for call in sleep.await_args_list] == [2.5, 3]


@pytest.mark.anyio
async def test_rate_limit_retry_after_overrides_exponential_delay() -> None:
    """Ignoring a numeric Retry-After header must fail the observed server-directed delay."""
    provider = FlakyProvider([ProviderRateLimitError("限流", retry_after_seconds=7), {"ok": True}])
    sleep = AsyncMock()

    result = await RetryingProvider(provider, sleep=sleep).complete_json("ping", Probe)

    assert result.ok is True
    sleep.assert_awaited_once_with(7)


@pytest.mark.anyio
async def test_collects_usage_from_actual_successful_provider_calls() -> None:
    """Dropping provider-reported usage or counting retries as one call must fail this test."""
    provider = FlakyProvider(
        [
            ProviderNetworkError("网络中断"),
            ({"ok": True}, ProviderUsage(input_tokens=12, output_tokens=8)),
        ]
    )
    wrapped = RetryingProvider(provider, sleep=AsyncMock())

    await wrapped.complete_json("ping", Probe)

    assert wrapped.stats.call_count == 2
    assert wrapped.stats.usage == ProviderUsage(input_tokens=12, output_tokens=8)


@pytest.mark.anyio
async def test_keeps_a_token_total_unknown_when_any_call_omits_that_component() -> None:
    """Retaining a partial token total after one call omits it would falsely imply completeness."""
    provider = FlakyProvider(
        [
            ({"ok": True}, ProviderUsage(input_tokens=12, output_tokens=8)),
            ({"ok": True}, ProviderUsage(input_tokens=None, output_tokens=5)),
        ]
    )
    wrapped = RetryingProvider(provider, sleep=AsyncMock())

    await wrapped.complete_json("first", Probe)
    await wrapped.complete_json("second", Probe)

    assert wrapped.stats.call_count == 2
    assert wrapped.stats.usage == ProviderUsage(input_tokens=None, output_tokens=13)


@pytest.mark.anyio
async def test_records_usage_when_a_model_response_fails_schema_validation() -> None:
    """Moving usage collection after success-only validation must lose this billed failed response."""
    provider = FlakyProvider(
        [(ProviderFormatError("格式错误", raw_response="bad"), ProviderUsage(input_tokens=12, output_tokens=8))]
    )
    wrapped = RetryingProvider(provider, sleep=AsyncMock())

    with pytest.raises(ProviderFormatError):
        await wrapped.complete_json("ping", Probe)

    assert wrapped.stats.call_count == 1
    assert wrapped.stats.usage == ProviderUsage(input_tokens=12, output_tokens=8)


@pytest.mark.anyio
async def test_keeps_usage_unavailable_when_provider_does_not_report_it() -> None:
    """Fabricating zero tokens for a provider without usage must fail this test."""
    wrapped = RetryingProvider(FlakyProvider([{"ok": True}]), sleep=AsyncMock())

    await wrapped.complete_json("ping", Probe)

    assert wrapped.stats.call_count == 1
    assert wrapped.stats.usage is None


@pytest.mark.anyio
async def test_keeps_codex_usage_unavailable_without_fabricating_zeros(tmp_path) -> None:
    """Adding fake token accounting to Codex must fail this usage-availability contract."""

    class Runner:
        async def run(self, command, *, stdin, cwd, timeout):
            output = next(item for item in command if item.endswith("last-message.json"))
            from pathlib import Path

            Path(output).write_text('{"ok": true}', encoding="utf-8")
            return ProcessResult(returncode=0, stdout="", stderr="")

    wrapped = RetryingProvider(CodexProvider(runner=Runner(), temp_parent=tmp_path), sleep=AsyncMock())

    assert (await wrapped.complete_json("ping", Probe)).ok is True
    assert wrapped.stats.call_count == 1
    assert wrapped.stats.usage is None


@pytest.mark.anyio
async def test_counts_each_codex_schema_fallback_runner_call(tmp_path) -> None:
    """Counting the provider facade once instead of both CLI invocations must fail this test."""
    runner_calls = 0

    class Runner:
        async def run(self, command, *, stdin, cwd, timeout):
            nonlocal runner_calls
            runner_calls += 1
            if "--output-schema" in command:
                return ProcessResult(returncode=1, stdout="", stderr="invalid_json_schema")
            output = next(item for item in command if item.endswith("last-message.json"))
            from pathlib import Path

            Path(output).write_text('{"ok": true}', encoding="utf-8")
            return ProcessResult(returncode=0, stdout="", stderr="")

    wrapped = RetryingProvider(CodexProvider(runner=Runner(), temp_parent=tmp_path), sleep=AsyncMock())

    assert (await wrapped.complete_json("ping", Probe)).ok is True
    assert runner_calls == 2
    assert wrapped.stats.call_count == 2


@pytest.mark.anyio
async def test_counts_codex_schema_fallback_calls_when_fallback_fails_format_validation(tmp_path) -> None:
    """A fallback's malformed result is still two actual runner calls, despite raising immediately."""
    runner_calls = 0

    class Runner:
        async def run(self, command, *, stdin, cwd, timeout):
            nonlocal runner_calls
            runner_calls += 1
            if "--output-schema" in command:
                return ProcessResult(returncode=1, stdout="", stderr="invalid_json_schema")
            output = next(item for item in command if item.endswith("last-message.json"))
            from pathlib import Path

            Path(output).write_text("not-json", encoding="utf-8")
            return ProcessResult(returncode=0, stdout="", stderr="")

    wrapped = RetryingProvider(CodexProvider(runner=Runner(), temp_parent=tmp_path), sleep=AsyncMock())

    with pytest.raises(ProviderFormatError):
        await wrapped.complete_json("ping", Probe)

    assert runner_calls == 2
    assert wrapped.stats.call_count == 2
