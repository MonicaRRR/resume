import json

import httpx
import pytest
from pydantic import BaseModel

from resume_mvp.providers.base import ProviderAuthError
from resume_mvp.providers.openai_compatible import OpenAICompatibleProvider


class SkillList(BaseModel):
    items: list[str]


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
