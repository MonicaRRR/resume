from pathlib import Path

from fastapi.testclient import TestClient

from resume_mvp.main import create_app


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


def test_codex_requires_explicit_privacy_confirmation(tmp_path: Path) -> None:
    """Catches accidental activation of a cloud-backed Codex provider."""
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.patch(
        "/api/settings/providers",
        json={"kind": "codex", "codex_confirmed": False},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CODEX_CONSENT_REQUIRED"
