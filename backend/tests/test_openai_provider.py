import json

import httpx
import pytest
from pydantic import BaseModel

from resume_mvp.provider_retry import RetryingProvider
from resume_mvp.providers.base import (
    ProviderAuthError,
    ProviderFormatError,
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderServerError,
    ProviderUsage,
)
from resume_mvp.providers.openai_compatible import OpenAICompatibleProvider
from resume_mvp.domain import JobAnalysis
from resume_mvp.ai_workflows import analyze_job


class SkillList(BaseModel):
    items: list[str]


@pytest.mark.anyio
async def test_job_analysis_sends_types_and_repairs_real_provider_shape_errors() -> None:
    requests = []
    async def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        system = body['messages'][0]['content']
        assert json.dumps(JobAnalysis.model_json_schema(), ensure_ascii=False) in system
        payload = {
            'role_title': '后端工程师',
            'requirements': [{'id': 'r1', 'text': '熟悉 Python', 'evidence_quote': '熟悉 Python',
                              'weight': '高' if len(requests) == 1 else 2, 'inferred': False}],
            'bonus_skills': [{'text': 'SQL'}] if len(requests) == 1 else ['SQL'],
        }
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(payload)}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(base_url='http://model.local', api_key='secret', model='demo', client=client)
        result = await analyze_job(provider, '公司', '熟悉 Python，SQL 加分')
    assert result.requirements[0].weight == 2
    assert result.bonus_skills == ['SQL']
    assert len(requests) == 2
    repair = requests[1]['messages'][1]['content']
    assert 'float_parsing' in repair and 'string_type' in repair
    assert 'validation_errors' in repair


@pytest.mark.anyio
async def test_openai_provider_posts_chat_completions_and_validates_json() -> None:
    """Catches calling the wrong compatible endpoint or returning unvalidated text."""
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"items":["Python"]}'}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        base_url="http://model.local",
        api_key="secret",
        model="demo-model",
        client=client,
    )

    result = await provider.complete_json("提取技能", SkillList)
    await client.aclose()

    assert captured["path"] == "/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret"
    assert captured["body"]["model"] == "demo-model"  # type: ignore[index]
    assert result.items == ["Python"]


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://open.bigmodel.cn/api/paas/v4/", "https://open.bigmodel.cn/api/paas/v4/chat/completions"),
        ("https://open.bigmodel.cn/api/paas/v4/chat/completions", "https://open.bigmodel.cn/api/paas/v4/chat/completions"),
        ("https://api.openai.com/v1", "https://api.openai.com/v1/chat/completions"),
        ("https://gateway.example.com", "https://gateway.example.com/v1/chat/completions"),
    ],
)
def test_chat_url_supports_versioned_and_complete_compatible_endpoints(base_url: str, expected: str) -> None:
    provider = OpenAICompatibleProvider(base_url=base_url, api_key="secret", model="demo")

    assert provider._chat_url() == expected


@pytest.mark.anyio
async def test_openai_provider_maps_auth_error_without_leaking_key() -> None:
    """Catches secret-bearing upstream failures reaching logs or the interface."""
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid secret")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        base_url="http://model.local",
        api_key="top-secret",
        model="demo-model",
        client=client,
    )

    with pytest.raises(ProviderAuthError) as error:
        await provider.complete_json("提取技能", SkillList)
    await client.aclose()

    assert "top-secret" not in str(error.value)


@pytest.mark.anyio
async def test_openai_provider_exposes_numeric_retry_after() -> None:
    """A 429 must retain a numeric server retry delay for the retry wrapper."""
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(429, headers={"Retry-After": "2.5"}))
    )
    provider = OpenAICompatibleProvider(
        base_url="http://model.local", api_key="secret", model="demo-model", client=client
    )

    with pytest.raises(ProviderRateLimitError) as error:
        await provider.complete_json("提取技能", SkillList)
    await client.aclose()

    assert error.value.retry_after_seconds == 2.5


@pytest.mark.anyio
async def test_openai_provider_maps_server_and_network_errors() -> None:
    """Collapsing 5xx or HTTP transport failures into generic ProviderError must fail this test."""
    server_client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(502)))
    server = OpenAICompatibleProvider(
        base_url="http://model.local", api_key="secret", model="demo-model", client=server_client
    )
    with pytest.raises(ProviderServerError) as server_error:
        await server.complete_json("提取技能", SkillList)
    await server_client.aclose()

    async def network_failure(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    network_client = httpx.AsyncClient(transport=httpx.MockTransport(network_failure))
    network = OpenAICompatibleProvider(
        base_url="http://model.local", api_key="secret", model="demo-model", client=network_client
    )
    with pytest.raises(ProviderNetworkError):
        await network.complete_json("提取技能", SkillList)
    await network_client.aclose()

    assert server_error.value.status_code == 502


@pytest.mark.anyio
async def test_openai_provider_exposes_optional_usage_without_fabricating_values() -> None:
    """Usage extraction must preserve supplied values and leave an absent usage block unavailable."""
    responses = iter(
        [
            {"choices": [{"message": {"content": '{\"items\":[\"Python\"]}'}}], "usage": {"prompt_tokens": 5, "completion_tokens": 3}},
            {"choices": [{"message": {"content": '{\"items\":[\"SQL\"]}'}}]},
        ]
    )

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(responses))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        base_url="http://model.local", api_key="secret", model="demo-model", client=client
    )

    await provider.complete_json("提取技能", SkillList)
    assert provider.last_usage == ProviderUsage(input_tokens=5, output_tokens=3)
    await provider.complete_json("提取技能", SkillList)
    await client.aclose()

    assert provider.last_usage is None


@pytest.mark.anyio
async def test_openai_usage_is_counted_when_structured_response_validation_fails() -> None:
    """A billed malformed structured response must contribute usage before format repair begins."""
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": '{\"items\": 7}'}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 3},
                },
            )
        )
    )
    wrapped = RetryingProvider(
        OpenAICompatibleProvider(base_url="http://model.local", api_key="secret", model="demo-model", client=client)
    )

    with pytest.raises(ProviderFormatError):
        await wrapped.complete_json("提取技能", SkillList)
    await client.aclose()

    assert wrapped.stats.call_count == 1
    assert wrapped.stats.usage == ProviderUsage(input_tokens=5, output_tokens=3)
