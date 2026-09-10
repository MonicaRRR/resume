#!/usr/bin/env python3
"""Isolated sandbox smoke: seed fixtures → quick/deep optimize → apply → preview/export."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from resume_mvp.domain import JobAnalysis, ResumeDocument
from resume_mvp.main import create_app
from resume_mvp.matching import calculate_match
from resume_mvp.providers.e2e import E2EProvider


PROFILE = ROOT / "fixtures" / "smoke_profile.json"
PROJECT = ROOT / "fixtures" / "smoke_project.json"


class SmokeError(RuntimeError):
    pass


def _ok(step: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"✓ {step}{suffix}")


def _fail(step: str, detail: str) -> None:
    raise SmokeError(f"✗ {step}: {detail}")


def _wait_ready(client: TestClient, project_id: str, run_id: str, *, timeout: float = 180.0) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/projects/{project_id}/optimization-runs/{run_id}")
        if response.status_code != 200:
            _fail("poll optimization", response.text)
        last = response.json()
        status = last["status"]
        if status in {"ready_for_user", "waiting_for_user", "failed", "cancelled"}:
            return last
        time.sleep(0.4)
    _fail("poll optimization", f"timeout last={last.get('status')} {last.get('message')}")
    raise AssertionError  # unreachable


def run_smoke(data_dir: Path) -> None:
    app = create_app(data_dir=data_dir, test_providers={"test": E2EProvider()})
    client = TestClient(app)

    health = client.get("/api/health")
    if health.status_code != 200 or health.json().get("status") != "ok":
        _fail("health", health.text)
    _ok("health")

    profile_payload = {"resume": json.loads(PROFILE.read_text(encoding="utf-8"))}
    profile = client.put("/api/profile", json=profile_payload)
    if profile.status_code != 200 or not profile.json().get("ready"):
        _fail("seed profile", profile.text)
    body = profile.json()
    _ok(
        "seed profile",
        f"{body['resume']['basics']['name']} · facts={len(body['facts'])}",
    )

    project_fix = json.loads(PROJECT.read_text(encoding="utf-8"))
    created = client.post(
        "/api/projects",
        json={
            "title": project_fix["title"],
            "company_name": project_fix["company_name"],
            "application_type": project_fix["application_type"],
            "job_description": project_fix["job_description"],
        },
    )
    if created.status_code not in {200, 201}:
        _fail("create project", created.text)
    project = created.json()
    project_id = project["id"]

    analysis = JobAnalysis.model_validate(project_fix["job_analysis"])
    versions = client.get(f"/api/projects/{project_id}/versions")
    if versions.status_code != 200 or not versions.json():
        _fail("list versions", versions.text)
    version = versions.json()[0]
    resume = ResumeDocument.model_validate(version["resume"])
    from resume_mvp.domain import Fact

    facts = [Fact.model_validate(item) for item in version["facts"]]
    match = calculate_match(analysis, resume, facts)
    # Overlay richer canned analysis for smoke realism.
    services = app.state.services
    services.repository.update(
        project_id,
        job_analysis=analysis,
        match_report=match,
        selected_template_id=project_fix.get("selected_template_id"),
    )
    project = client.get(f"/api/projects/{project_id}").json()
    if not project.get("job_analysis") or not project.get("match_report"):
        _fail("attach analysis/match", str(project.keys()))
    _ok(
        "create project",
        f"{project['title']} · match={project['match_report']['coverage']:.0%}",
    )

    preview = client.post(f"/api/projects/{project_id}/preview/pdf", json={})
    if preview.status_code != 200 or not preview.content.startswith(b"%PDF"):
        _fail("preview pdf", f"status={preview.status_code} body={preview.text[:200]}")
    _ok("preview pdf", f"{len(preview.content)} bytes")

    # --- quick optimize ---
    quick = client.post(
        f"/api/projects/{project_id}/optimization-runs",
        json={"mode": "quick", "provider": "test"},
    )
    if quick.status_code != 202:
        _fail("quick start", quick.text)
    quick_run = _wait_ready(client, project_id, quick.json()["id"])
    if quick_run["status"] != "ready_for_user" or not quick_run.get("patch", {}).get("operations"):
        _fail("quick ready", json.dumps(quick_run, ensure_ascii=False)[:400])
    _ok(
        "quick optimize",
        f"calls={quick_run['call_count']} ops={len(quick_run['patch']['operations'])}",
    )

    op_ids = [op["id"] for op in quick_run["patch"]["operations"][:1]]
    applied = client.post(
        f"/api/projects/{project_id}/resume/apply-patch",
        json={"patch": quick_run["patch"], "accepted_operation_ids": op_ids},
    )
    if applied.status_code != 200:
        _fail("apply patch", applied.text)
    _ok("apply patch", f"version={applied.json()['id'][:8]}")

    # --- deep optimize on current draft ---
    deep = client.post(
        f"/api/projects/{project_id}/optimization-runs",
        json={"mode": "deep", "provider": "test"},
    )
    if deep.status_code != 202:
        _fail("deep start", deep.text)
    deep_run = _wait_ready(client, project_id, deep.json()["id"], timeout=240.0)
    if deep_run["status"] != "ready_for_user":
        _fail("deep ready", json.dumps(deep_run, ensure_ascii=False)[:500])
    quality = deep_run.get("quality") or {}
    _ok(
        "deep optimize",
        f"calls={deep_run['call_count']} iteration={deep_run['iteration']} "
        f"passed={quality.get('passed')} expression={quality.get('expression_score')}",
    )

    docx = client.post(
        f"/api/projects/{project_id}/export/docx",
        json={"template_id": project_fix.get("selected_template_id", "classic-cn")},
    )
    if docx.status_code != 200 or len(docx.content) < 1000:
        _fail("export docx", f"status={docx.status_code} size={len(docx.content)}")
    _ok("export docx", f"{len(docx.content)} bytes")

    providers = client.get("/api/settings/providers")
    if providers.status_code != 200 or providers.json().get("kind") != "test":
        _fail("provider state", providers.text)
    _ok("provider sandbox", providers.json()["kind"])


def main() -> int:
    print("=== sandbox smoke (isolated DB + E2EProvider) ===")
    with tempfile.TemporaryDirectory(prefix="resume-smoke-") as tmp:
        try:
            run_smoke(Path(tmp))
        except SmokeError as error:
            print(str(error), file=sys.stderr)
            return 1
    print("=== sandbox smoke PASSED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
