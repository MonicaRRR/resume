from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from resume_mvp.main import create_app
from resume_mvp.providers.codex import CodexDetectResult, CodexModelOption, ProcessResult, detect_codex, load_codex_model_options


def test_provider_settings_never_echo_api_key(tmp_path: Path) -> None:
    """Catches API secrets leaking through write or read responses."""
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.patch(
        "/api/settings/providers",
        json={
            "kind": "openai-compatible",
            "base_url": "http://localhost:9999",
            "model": "demo",
            "api_key": "top-secret",
            "timeout": 60,
            "temperature": 0.2,
        },
    )

    assert response.status_code == 200
    assert "top-secret" not in response.text
    fetched = client.get("/api/settings/providers")
    assert "top-secret" not in fetched.text
    assert fetched.json()["configured"] is True


def test_codex_settings_persist_across_restarts(tmp_path: Path) -> None:
    """Catches Codex requiring re-detect after every backend restart."""
    first = TestClient(create_app(data_dir=tmp_path))
    response = first.patch(
        "/api/settings/providers",
        json={"kind": "codex", "codex_confirmed": True, "model": "gpt-demo"},
    )
    assert response.status_code == 200
    assert response.json()["configured"] is True

    restarted = TestClient(create_app(data_dir=tmp_path))
    state = restarted.get("/api/settings/providers").json()
    assert state["kind"] == "codex"
    assert state["model"] == "gpt-demo"
    assert state["codex_confirmed"] is True
    assert state["configured"] is True
    assert "api_key" not in state


def test_openai_metadata_persists_but_key_does_not(tmp_path: Path) -> None:
    first = TestClient(create_app(data_dir=tmp_path))
    assert first.patch(
        "/api/settings/providers",
        json={
            "kind": "openai-compatible",
            "base_url": "http://localhost:9999/v1",
            "model": "demo",
            "api_key": "top-secret",
            "timeout": 60,
            "temperature": 0.2,
        },
    ).status_code == 200

    restarted = TestClient(create_app(data_dir=tmp_path))
    state = restarted.get("/api/settings/providers").json()
    assert state["base_url"] == "http://localhost:9999/v1"
    assert state["model"] == "demo"
    assert state["configured"] is False
    saved = (tmp_path / "provider_settings.json").read_text(encoding="utf-8")
    assert "top-secret" not in saved


def test_codex_requires_explicit_privacy_confirmation(tmp_path: Path) -> None:
    """Catches accidental activation of a cloud-backed Codex provider."""
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.patch(
        "/api/settings/providers",
        json={"kind": "codex", "codex_confirmed": False},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CODEX_CONSENT_REQUIRED"


def test_e2e_provider_requires_explicit_environment_flag(tmp_path: Path, monkeypatch) -> None:
    """Catches a deterministic test model becoming available in normal runs."""
    monkeypatch.delenv("RESUME_MVP_TEST_PROVIDER", raising=False)
    normal = TestClient(create_app(data_dir=tmp_path / "normal"))
    assert normal.get("/api/settings/providers").json()["configured"] is False

    monkeypatch.setenv("RESUME_MVP_TEST_PROVIDER", "1")
    enabled = TestClient(create_app(data_dir=tmp_path / "e2e"))
    state = enabled.get("/api/settings/providers").json()
    assert state["kind"] == "test"
    assert state["configured"] is True


def test_load_codex_model_options_from_cache(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text('model = "gpt-demo"\n', encoding="utf-8")
    (tmp_path / "models_cache.json").write_text(
        json.dumps({
            "models": [
                {"slug": "gpt-demo", "display_name": "Demo", "description": "demo model", "visibility": "list"},
                {"slug": "hidden", "display_name": "Hidden", "visibility": "hidden"},
            ]
        }),
        encoding="utf-8",
    )
    default_model, models = load_codex_model_options(tmp_path)
    assert default_model == "gpt-demo"
    assert [item.slug for item in models] == ["gpt-demo"]


@pytest.mark.anyio
async def test_detect_codex_requires_install_and_login(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("resume_mvp.providers.codex.shutil.which", lambda _name: None)
    missing = await detect_codex(codex_home=tmp_path)
    assert missing.available is False
    assert "未找到" in missing.message

    class FakeRunner:
        async def run(self, command, *, stdin, cwd, timeout):
            payload = {
                "codexVersion": "0.1.0",
                "checks": {
                    "auth.credentials": {"status": "fail", "summary": "missing"},
                    "config.load": {"status": "ok", "details": {"model": "gpt-demo"}},
                },
            }
            return ProcessResult(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("resume_mvp.providers.codex.shutil.which", lambda _name: "/usr/bin/codex")
    unauthenticated = await detect_codex(runner=FakeRunner(), codex_home=tmp_path)
    assert unauthenticated.installed is True
    assert unauthenticated.authenticated is False
    assert unauthenticated.available is False


@pytest.mark.anyio
async def test_detect_codex_returns_selectable_models(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "models_cache.json").write_text(
        json.dumps({
            "models": [
                {"slug": "gpt-a", "display_name": "Model A", "description": "A", "visibility": "list"},
                {"slug": "gpt-b", "display_name": "Model B", "description": "B", "visibility": "list"},
            ]
        }),
        encoding="utf-8",
    )
    (tmp_path / "auth.json").write_text("{}", encoding="utf-8")

    class FakeRunner:
        async def run(self, command, *, stdin, cwd, timeout):
            payload = {
                "codexVersion": "0.2.0",
                "checks": {
                    "auth.credentials": {"status": "ok", "summary": "auth is configured"},
                    "config.load": {"status": "ok", "details": {"model": "gpt-b"}},
                },
            }
            return ProcessResult(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("resume_mvp.providers.codex.shutil.which", lambda _name: "/usr/bin/codex")
    result = await detect_codex(runner=FakeRunner(), codex_home=tmp_path)
    assert result.available is True
    assert result.default_model == "gpt-b"
    assert [item.slug for item in result.models] == ["gpt-a", "gpt-b"]


def test_codex_detect_endpoint(tmp_path: Path, monkeypatch) -> None:
    async def fake_detect() -> CodexDetectResult:
        return CodexDetectResult(
            installed=True,
            authenticated=True,
            available=True,
            version="9.9.9",
            default_model="gpt-x",
            models=[CodexModelOption(slug="gpt-x", display_name="GPT X", description="x")],
            message="ok",
        )

    monkeypatch.setattr("resume_mvp.providers.codex.detect_codex", fake_detect)
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.post("/api/settings/providers/codex/detect")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["models"][0]["slug"] == "gpt-x"
