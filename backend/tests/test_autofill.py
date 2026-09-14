from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from resume_mvp.autofill import (
    AgentAutofillResponse,
    PageField,
    build_autofill_plan,
    build_rules_plan,
    flatten_profile,
)
from resume_mvp.domain import Basics, ResumeDocument, SourcedText
from resume_mvp.main import create_app
from resume_mvp.providers.base import ProviderError


class _AutofillAgent:
    def __init__(self, response: AgentAutofillResponse | None = None, *, fail: bool = False) -> None:
        self.response = response or AgentAutofillResponse()
        self.fail = fail

    async def complete_json(self, prompt: str, schema: type):
        if self.fail:
            raise ProviderError("simulated agent failure")
        assert schema is AgentAutofillResponse
        return self.response


def _resume_with_name(name: str = "张宁", phone: str = "13800001234") -> ResumeDocument:
    return ResumeDocument(
        basics=Basics(
            name=name,
            phone=phone,
            email="",
            target_role=SourcedText(value="后端工程师"),
            summary=SourcedText(value=""),
        )
    )


def test_flatten_profile_skips_empty_meaning() -> None:
    flat = flatten_profile(_resume_with_name())
    assert flat["name"] == "张宁"
    assert flat["phone"] == "13800001234"
    assert flat["email"] == ""
    assert flat["target_role"] == "后端工程师"


def test_rules_fill_name_and_phone() -> None:
    profile = flatten_profile(_resume_with_name())
    fields = [
        PageField(id="f-name", label="姓名"),
        PageField(id="f-phone", placeholder="请输入手机号"),
        PageField(id="f-submit", type="submit", label="立即投递"),
    ]
    plan = build_rules_plan(fields, profile)
    by_id = {action.field_id: action for action in plan.actions}
    assert by_id["f-name"].value == "张宁"
    assert by_id["f-phone"].value == "13800001234"
    assert "f-submit" not in by_id
    assert plan.empty_reminders == []


def test_rules_empty_reminder_when_profile_missing() -> None:
    profile = flatten_profile(_resume_with_name())
    fields = [PageField(id="f-email", label="邮箱")]
    plan = build_rules_plan(fields, profile)
    assert plan.actions == []
    assert len(plan.empty_reminders) == 1
    assert plan.empty_reminders[0].field_id == "f-email"
    assert plan.empty_reminders[0].profile_key == "email"


@pytest.mark.anyio
async def test_agent_fills_unmatched_without_inventing() -> None:
    profile = flatten_profile(_resume_with_name())
    fields = [
        PageField(id="f-name", label="姓名"),
        PageField(id="f-weird", label="联系人称呼"),
        PageField(id="f-email", label="电子邮箱"),
    ]
    agent = _AutofillAgent(
        AgentAutofillResponse(
            mappings=[
                {"field_id": "f-weird", "profile_key": "name"},
                {"field_id": "f-email", "profile_key": "email"},
                {"field_id": "f-weird", "profile_key": "invented_key"},
            ],
            empty_field_ids=[],
        )
    )
    plan = await build_autofill_plan(fields, profile, provider=agent)
    assert plan.mode == "hybrid"
    values = {action.field_id: action.value for action in plan.actions}
    assert values["f-name"] == "张宁"
    assert values["f-weird"] == "张宁"
    assert "f-email" not in values
    assert any(item.field_id == "f-email" for item in plan.empty_reminders)


@pytest.mark.anyio
async def test_agent_failure_falls_back_to_rules() -> None:
    profile = flatten_profile(_resume_with_name())
    fields = [
        PageField(id="f-name", label="姓名"),
        PageField(id="f-weird", label="联系人称呼"),
    ]
    plan = await build_autofill_plan(fields, profile, provider=_AutofillAgent(fail=True))
    assert plan.mode == "rules"
    assert plan.actions[0].field_id == "f-name"
    assert "f-weird" in plan.unmatched_fields
    assert plan.warnings


def test_autofill_plan_api_uses_saved_profile(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))
    resume = _resume_with_name().model_dump(mode="json")
    saved = client.put("/api/profile", json={"resume": resume})
    assert saved.status_code == 200

    response = client.post(
        "/api/autofill/plan",
        json={
            "page_title": "示例投递",
            "fields": [
                {"id": "n1", "label": "姓名"},
                {"id": "e1", "label": "邮箱"},
                {"id": "s1", "type": "submit", "label": "提交申请"},
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "rules"
    assert {item["field_id"] for item in body["actions"]} == {"n1"}
    assert body["actions"][0]["value"] == "张宁"
    assert body["empty_reminders"][0]["field_id"] == "e1"
    assert all(item["field_id"] != "s1" for item in body["actions"])


def test_autofill_plan_api_hybrid_with_test_provider(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path, test_providers={"test": _AutofillAgent(
        AgentAutofillResponse(
            mappings=[{"field_id": "f-alias", "profile_key": "name"}],
            empty_field_ids=[],
        )
    )}))
    resume = _resume_with_name().model_dump(mode="json")
    assert client.put("/api/profile", json={"resume": resume}).status_code == 200
    response = client.post(
        "/api/autofill/plan",
        json={
            "provider": "test",
            "fields": [
                {"id": "f-name", "label": "姓名"},
                {"id": "f-alias", "label": "联系人称呼"},
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "hybrid"
    values = {item["field_id"]: item["value"] for item in body["actions"]}
    assert values["f-name"] == "张宁"
    assert values["f-alias"] == "张宁"
    assert values["f-alias"]  # agent source present
    assert any(item["source"] == "agent" for item in body["actions"])
