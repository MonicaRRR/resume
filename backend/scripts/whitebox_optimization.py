#!/usr/bin/env python3
"""White-box optimization simulation: dump every intermediate artifact to disk."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from resume_mvp.domain import Fact, JobAnalysis, ResumeDocument
from resume_mvp.main import create_app
from resume_mvp.matching import calculate_match
from resume_mvp.providers.e2e import E2EProvider


DEFAULT_PROFILE = ROOT / "fixtures" / "smoke_profile.json"
DEFAULT_PROJECT = ROOT / "fixtures" / "smoke_project.json"


def _dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, (bytes, bytearray)):
        path.write_bytes(payload)
        return
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
        return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _wait_ready(client: TestClient, project_id: str, run_id: str, timeout: float = 240.0) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/projects/{project_id}/optimization-runs/{run_id}")
        response.raise_for_status()
        last = response.json()
        if last["status"] in {"ready_for_user", "waiting_for_user", "failed", "cancelled"}:
            return last
        time.sleep(0.35)
    raise TimeoutError(f"run stuck at {last.get('status')}: {last.get('message')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="白盒优化：导出逐步中间产物")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--tag", default="", help="输出子目录标签，如 campus")
    parser.add_argument("--mode", choices=("quick", "deep"), default="deep")
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = f"{args.tag}-{stamp}" if args.tag else stamp
    out_dir = ROOT / ".data" / "whitebox" / folder
    data_dir = out_dir / "_sandbox_db"
    data_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(data_dir=data_dir, test_providers={"test": E2EProvider()})
    client = TestClient(app)

    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    project_fix = json.loads(args.project.read_text(encoding="utf-8"))
    app_type = project_fix.get("application_type", "experienced")

    print(f"输出目录：{out_dir}")
    print(f"求职类型：{app_type} · 模式：{args.mode}")
    _dump(out_dir / "00-input-profile.json", profile)
    _dump(out_dir / "00-input-project.json", project_fix)

    put = client.put("/api/profile", json={"resume": profile})
    put.raise_for_status()
    _dump(out_dir / "01-profile-saved.json", put.json())

    created = client.post(
        "/api/projects",
        json={
            "title": project_fix["title"] + "·白盒",
            "company_name": project_fix["company_name"],
            "application_type": app_type,
            "job_description": project_fix["job_description"],
        },
    )
    if created.status_code not in {200, 201}:
        print(created.text, file=sys.stderr)
        return 1
    project = created.json()
    project_id = project["id"]
    _dump(out_dir / "02-project-created-by-e2e-provider.json", project)

    analysis = JobAnalysis.model_validate(project_fix["job_analysis"])
    versions = client.get(f"/api/projects/{project_id}/versions").json()
    version = versions[0]
    resume = ResumeDocument.model_validate(version["resume"])
    facts = [Fact.model_validate(item) for item in version["facts"]]
    match = calculate_match(analysis, resume, facts)
    app.state.services.repository.update(
        project_id,
        job_analysis=analysis,
        match_report=match,
        selected_template_id=project_fix.get("selected_template_id", "classic-cn"),
    )
    project = client.get(f"/api/projects/{project_id}").json()
    _dump(out_dir / "03-job-analysis.json", project["job_analysis"])
    _dump(out_dir / "03-match-report.json", project["match_report"])
    _dump(out_dir / "03-active-resume.json", version["resume"])
    _dump(out_dir / "03-facts.json", version["facts"])

    preview = client.post(f"/api/projects/{project_id}/preview/pdf", json={})
    if preview.status_code == 200 and preview.content.startswith(b"%PDF"):
        _dump(out_dir / "04-baseline-preview.pdf", preview.content)
        print(f"基线 PDF：{len(preview.content)} bytes")
    else:
        _dump(out_dir / "04-baseline-preview-error.txt", preview.text)

    started = client.post(
        f"/api/projects/{project_id}/optimization-runs",
        json={"mode": args.mode, "provider": "test"},
    )
    if started.status_code != 202:
        print(started.text, file=sys.stderr)
        return 1
    run_meta = started.json()
    _dump(out_dir / "05-run-accepted.json", run_meta)
    print(f"{args.mode} 优化 run_id={run_meta['id']}")

    final = _wait_ready(client, project_id, run_meta["id"])
    _dump(out_dir / "06-run-final.json", final)

    steps = app.state.services.repository.list_optimization_steps(run_meta["id"])
    step_index: list[dict] = []
    for index, step in enumerate(steps, start=1):
        name = f"07-step-{index:02d}-iter{step.iteration}-{step.kind}-a{step.attempt}"
        payload = {
            "id": step.id,
            "kind": step.kind,
            "iteration": step.iteration,
            "attempt": step.attempt,
            "status": step.status,
            "error_code": step.error_code,
            "input_hash": step.input_hash,
            "created_at": step.created_at,
            "output": step.output,
        }
        _dump(out_dir / f"{name}.json", payload)
        step_index.append(
            {
                "file": f"{name}.json",
                "kind": step.kind,
                "iteration": step.iteration,
                "attempt": step.attempt,
                "status": step.status,
                "output_keys": list((step.output or {}).keys()),
            }
        )

    for iteration in sorted({step.iteration for step in steps} | {0}):
        try:
            layout = app.state.services.repository.get_layout_report(run_meta["id"], iteration)
        except Exception:  # noqa: BLE001
            continue
        _dump(out_dir / f"08-layout-iter{iteration}.json", layout.model_dump(mode="json"))

    if final.get("patch"):
        _dump(out_dir / "09-candidate-patch.json", final["patch"])
    if final.get("review"):
        _dump(out_dir / "09-review.json", final["review"])
    if final.get("quality"):
        _dump(out_dir / "09-quality-gate.json", final["quality"])
    if final.get("layout_report"):
        _dump(out_dir / "09-final-layout.json", final["layout_report"])

    ops = (final.get("patch") or {}).get("operations") or []
    if ops and final.get("status") == "ready_for_user":
        applied = client.post(
            f"/api/projects/{project_id}/resume/apply-patch",
            json={"patch": final["patch"], "accepted_operation_ids": [ops[0]["id"]]},
        )
        if applied.status_code == 200:
            _dump(out_dir / "10-resume-after-apply.json", applied.json()["resume"])
            after_pdf = client.post(f"/api/projects/{project_id}/preview/pdf", json={})
            if after_pdf.status_code == 200 and after_pdf.content.startswith(b"%PDF"):
                _dump(out_dir / "10-after-apply-preview.pdf", after_pdf.content)

    type_label = {"campus": "校招", "internship": "实习", "experienced": "社招"}.get(app_type, app_type)
    readme = f"""# 白盒优化产物（{type_label} · {args.mode}）

- 时间：{stamp}
- Provider：`E2EProvider`（固定假模型，不外发）
- 求职类型：`{app_type}`（{type_label}）
- 模式：{args.mode}
- 夹具：`{args.profile.name}` + `{args.project.name}`
- 项目：{project.get('title')}
- run_id：`{run_meta['id']}`
- 终态：`{final.get('status')}` — {final.get('message')}
- 模型调用：{final.get('call_count')}/{final.get('max_model_calls')} · 轮次 {final.get('iteration')}
- 质量：{json.dumps(final.get('quality'), ensure_ascii=False)}
- 匹配覆盖：{(project.get('match_report') or {}).get('coverage')}

## 文件导读

| 文件 | 含义 |
|------|------|
| `00-input-*` | 冒烟夹具输入 |
| `01-profile-saved.json` | 写入经历库后的 profile + 派生 facts |
| `02-project-created-*.json` | 创建项目时 E2E 自动 JD 分析（随后被 03 覆盖） |
| `03-job-analysis.json` | 白盒用的岗位分析 |
| `03-match-report.json` | 确定性匹配报告 |
| `03-active-resume.json` / `03-facts.json` | 优化输入底稿 |
| `04-baseline-preview.pdf` | 优化前真实 PDF 预览 |
| `05-run-accepted.json` | HTTP 202 接受的 run |
| `06-run-final.json` | 终态 run（含 patch/review/quality） |
| `07-step-*.json` | 编排器持久化的逐步检查点 |
| `08-layout-iter*.json` | 各轮真实排版检测（校招关注一页策略） |
| `09-*` | 终稿补丁 / 审查 / 质量门 |
| `10-*` | 用户同意第 1 条后的简历与 PDF |

## 步骤索引

```json
{json.dumps(step_index, ensure_ascii=False, indent=2)}
```
"""
    _dump(out_dir / "README.md", readme)
    _dump(
        out_dir / "INDEX.json",
        {
            "out_dir": str(out_dir),
            "tag": args.tag or None,
            "application_type": app_type,
            "mode": args.mode,
            "run_id": run_meta["id"],
            "status": final.get("status"),
            "message": final.get("message"),
            "call_count": final.get("call_count"),
            "iteration": final.get("iteration"),
            "match_coverage": (project.get("match_report") or {}).get("coverage"),
            "quality": final.get("quality"),
            "layout_final": final.get("layout_report"),
            "steps": step_index,
        },
    )

    print("=== 白盒完成 ===")
    print(f"类型：{app_type} · 终态：{final.get('status')} · {final.get('message')}")
    print(f"调用：{final.get('call_count')} · 轮次：{final.get('iteration')}")
    print(f"质量：{final.get('quality')}")
    print(f"匹配：{(project.get('match_report') or {}).get('coverage')}")
    print(f"步骤数：{len(step_index)}")
    print(f"打开：{out_dir / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
