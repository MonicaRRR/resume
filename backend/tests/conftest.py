import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def isolate_os_credentials(monkeypatch):
    # HTTP tests inject their own secret stores; never consult user credentials.
    monkeypatch.setattr("resume_mvp.main.create_platform_secret_store", lambda: None)
