from fastapi.testclient import TestClient

from resume_mvp.main import create_app


def test_health_reports_service_identity() -> None:
    response = TestClient(create_app()).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "resume-mvp"}


def test_backend_root_redirects_to_frontend() -> None:
    response = TestClient(create_app()).get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "http://127.0.0.1:5173/"
