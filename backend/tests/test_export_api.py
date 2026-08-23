from pathlib import Path

from docx import Document
from fastapi.testclient import TestClient

from resume_mvp.main import create_app


def create_project_with_resume(client: TestClient) -> str:
    project = client.post(
        "/api/projects",
        json={
            "title": "后端工程师",
            "company_name": "示例科技",
            "application_type": "experienced",
            "job_description": "负责 Python API",
        },
    ).json()
    client.post(
        f"/api/projects/{project['id']}/resume/import",
        files={"file": ("resume.txt", "张宁\n后端工程师\n使用 Python 开发 API", "text/plain")},
    )
    return project["id"]


def test_export_routes_return_reopenable_files_and_handoff(tmp_path: Path) -> None:
    """Catches attachment routes returning the wrong version or media type."""
    client = TestClient(create_app(data_dir=tmp_path))
    project_id = create_project_with_resume(client)

    docx_response = client.post(f"/api/projects/{project_id}/export/docx")
    assert docx_response.status_code == 200
    assert docx_response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    path = tmp_path / "export.docx"
    path.write_bytes(docx_response.content)
    assert "张宁" in "\n".join(p.text for p in Document(path).paragraphs)

    json_response = client.get(f"/api/projects/{project_id}/export/json")
    assert json_response.status_code == 200
    assert json_response.json()["resume"]["basics"]["name"] == "张宁"

    handoff = client.post(f"/api/projects/{project_id}/codex-handoff")
    assert handoff.status_code == 200
    assert "不得虚构事实" in handoff.json()["markdown"]


def test_campus_docx_export_is_blocked_when_content_estimate_overflows(tmp_path: Path) -> None:
    """Catches export of a campus resume known to exceed the one-page capacity."""
    client = TestClient(create_app(data_dir=tmp_path))
    project = client.post(
        "/api/projects",
        json={
            "title": "校招后端工程师",
            "company_name": "",
            "application_type": "campus",
            "job_description": "负责 Python API",
        },
    ).json()
    long_text = "负责接口设计、稳定性治理与性能优化，" * 180
    client.post(
        f"/api/projects/{project['id']}/resume/import",
        files={"file": ("resume.txt", f"张宁\n后端工程师\n{long_text}", "text/plain")},
    )

    response = client.post(f"/api/projects/{project['id']}/export/docx")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "RESUME_OVERFLOW"
