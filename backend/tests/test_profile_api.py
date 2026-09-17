from pathlib import Path
import json

from fastapi.testclient import TestClient

from resume_mvp.main import create_app


SAMPLE_TXT = """张宁
女 | 上海 | 13800001234 | zhangning@example.com

教育背景
浙江大学，软件工程，硕士 2023.09 - 2026.06
主修分布式系统

职业经历
极光云科技，后端实习生 2025.06 - 2025.09
使用 Python 开发 API

项目经历
校园即时通讯，后端负责人 2022.10 - 2023.05
实现 WebSocket 会话

专业技能
Python、FastAPI、SQL
"""


def test_profile_import_fills_resume_without_persisting(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))

    before = client.get("/api/profile").json()
    assert before["resume"]["basics"]["name"] == ""

    imported = client.post(
        "/api/profile/import",
        files={"file": ("resume.txt", SAMPLE_TXT.encode("utf-8"), "text/plain")},
    )
    assert imported.status_code == 200, imported.text
    body = imported.json()
    assert body["resume"]["basics"]["name"] == "张宁"
    assert body["quality_score"] >= 0
    assert isinstance(body["warnings"], list)

    after = client.get("/api/profile").json()
    assert after["resume"]["basics"]["name"] == ""
    assert after["ready"] is False

    saved = client.put("/api/profile", json={"resume": body["resume"]})
    assert saved.status_code == 200
    assert saved.json()["resume"]["basics"]["name"] == "张宁"
    assert saved.json()["ready"] is True
    assert client.get("/api/profile").json()["resume"]["basics"]["name"] == "张宁"


def test_profile_import_rejects_unsupported_type(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))
    response = client.post(
        "/api/profile/import",
        files={"file": ("photo.png", b"not-a-resume", "image/png")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "IMPORT_FAILED"


def test_profile_json_backup_can_be_exported_and_imported_as_draft(tmp_path: Path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))
    resume = client.get("/api/profile").json()["resume"]
    resume["basics"]["name"] = "备份用户"
    resume["skills"] = [{
        "id": "skill-json",
        "name": "测试技能",
        "items": [{
            "value": "Python",
            "source_fact_ids": [],
            "origin": "manual",
            "confidence": 1,
        }],
    }]
    saved = client.put("/api/profile", json={"resume": resume})
    assert saved.status_code == 200

    exported = client.get("/api/profile/export/json")
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/json")
    assert "attachment" in exported.headers["content-disposition"]
    backup = exported.json()
    assert backup["schema_version"] == 1
    assert backup["resume"]["basics"]["name"] == "备份用户"

    # Import remains draft-only and accepts the complete exported envelope.
    client.put("/api/profile", json={"resume": client.get("/api/profile").json()["resume"]})
    imported = client.post(
        "/api/profile/import",
        files={
            "file": (
                "profile.json",
                json.dumps(backup, ensure_ascii=False).encode("utf-8"),
                "application/json",
            )
        },
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["resume"]["basics"]["name"] == "备份用户"
    assert imported.json()["quality_score"] == 1
