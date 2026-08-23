# Chinese AI Resume MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first Chinese resume creation, optimization, export, interview, and written-practice MVP with OpenAI-compatible API and Codex CLI providers.

**Architecture:** A React/Vite browser client talks to a local FastAPI service. The service owns SQLite persistence, resume ingestion, fact-backed immutable versions, AI provider adapters, DOCX/JSON exports, and practice sessions; the client owns the guided workflow, diff approval, A4 templates, and browser PDF printing.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic 2, SQLAlchemy 2, PyMuPDF, python-docx, httpx, pytest; React 19, TypeScript, Vite, React Router, TanStack Query, Zustand, Zod, Vitest, Testing Library, Playwright, pnpm.

**Spec:** `docs/superpowers/specs/2026-08-23-chinese-ai-resume-mvp-design.md`

## Global Constraints

- MVP is a local single-user Web application and requires no account.
- MVP UI, generated content, fixtures, and errors are Chinese-only.
- Every project has `application_type`: `campus`, `internship`, or `experienced`; campus/internship target exactly one A4 page with compact layout and export blocking on overflow, while experienced resumes may paginate naturally.
- Supported uploads are DOCX, text-based PDF, and TXT; scanned-PDF OCR is excluded.
- Implement OpenAI-compatible `/v1/chat/completions` and local Codex CLI providers; keep the local-model interface only, with no Qwen runtime integration.
- AI may rewrite only facts provided by upload, questionnaire, or manual entry; missing facts become questions.
- AI suggestions are pending patches until the user explicitly accepts them; history is immutable and reversible.
- Provide four built-in Chinese ATS-friendly templates and prefer imported style profiles when available.
- Export DOCX and JSON from the service; export PDF through the browser print flow.
- API keys never enter SQLite, exported JSON, ordinary logs, or frontend persistent storage.
- Do not add authentication, cloud sync, voice, distributed queues, desktop packaging, or automated job submission.

## Planned File Map

```text
.
├── README.md                         # setup, privacy, provider, and workflow guide
├── Makefile                          # one-command install/test/dev/build entry points
├── .gitignore
├── backend/
│   ├── pyproject.toml                # Python dependencies and pytest configuration
│   ├── resume_mvp/
│   │   ├── main.py                   # FastAPI construction and router assembly
│   │   ├── config.py                 # data path and upload limits
│   │   ├── database.py               # SQLAlchemy engine/session lifecycle
│   │   ├── domain.py                 # Pydantic resume, fact, patch, analysis types
│   │   ├── tables.py                 # SQLAlchemy records
│   │   ├── repositories.py           # project/version/practice persistence
│   │   ├── ingestion.py              # TXT/DOCX/PDF import and quality report
│   │   ├── patches.py                # patch validation/application/version helpers
│   │   ├── matching.py               # explainable JD coverage calculation
│   │   ├── page_policy.py            # one-page estimates and compact layout tokens
│   │   ├── providers/
│   │   │   ├── base.py               # provider protocol and provider errors
│   │   │   ├── openai_compatible.py  # HTTP chat-completions adapter
│   │   │   └── codex.py              # ephemeral read-only Codex process adapter
│   │   ├── ai_workflows.py           # prompts and typed AI orchestration
│   │   ├── exports.py                # DOCX/JSON and Codex handoff documents
│   │   ├── practice.py               # interview/written-practice orchestration
│   │   └── api/
│   │       ├── projects.py           # project, import, facts, analysis, patch routes
│   │       ├── providers.py          # in-memory provider settings and connection tests
│   │       ├── exports.py            # download routes
│   │       └── practice.py           # training routes
│   └── tests/                         # unit and integration tests mirroring modules
└── web/
    ├── package.json
    ├── vite.config.ts
    ├── playwright.config.ts
    ├── src/
    │   ├── main.tsx                  # providers and router bootstrap
    │   ├── app.tsx                   # route definitions and shell
    │   ├── api/client.ts             # typed local API client
    │   ├── types.ts                  # browser-side Zod schemas and types
    │   ├── state/editor.ts           # unsaved resume and patch-review state
    │   ├── pages/HomePage.tsx
    │   ├── pages/WorkspacePage.tsx
    │   ├── pages/PracticePage.tsx
    │   ├── pages/SettingsPage.tsx
    │   ├── components/ProjectForm.tsx
    │   ├── components/ResumeIntake.tsx
    │   ├── components/JobAnalysisPanel.tsx
    │   ├── components/PatchReview.tsx
    │   ├── components/ResumeEditor.tsx
    │   ├── components/ResumePreview.tsx
    │   ├── components/TemplatePicker.tsx
    │   ├── components/ProviderStatus.tsx
    │   ├── components/PracticePanel.tsx
    │   ├── templates/registry.tsx     # four template renderers and selection metadata
    │   └── styles.css                 # tokens, responsive layout, print rules, focus states
    ├── src/**/*.test.tsx              # component tests adjacent to components
    └── e2e/resume-flow.spec.ts        # complete browser workflow
```

---

### Task 1: Runnable project shell and health contract

**Files:**
- Create: `.gitignore`
- Create: `Makefile`
- Create: `backend/pyproject.toml`
- Create: `backend/resume_mvp/__init__.py`
- Create: `backend/resume_mvp/main.py`
- Create: `backend/tests/test_health.py`
- Create: `web/package.json`
- Create: `web/tsconfig.json`
- Create: `web/vite.config.ts`
- Create: `web/index.html`
- Create: `web/src/main.tsx`
- Create: `web/src/app.tsx`
- Create: `web/src/app.test.tsx`
- Create: `web/src/test/setup.ts`
- Create: `web/src/styles.css`

**Interfaces:**
- Produces: `create_app() -> FastAPI`, `GET /api/health -> {"status":"ok","service":"resume-mvp"}`.
- Produces: a React root that renders `简历证据工作台` and a development proxy from `/api` to `127.0.0.1:8000`.

- [ ] **Step 1: Add failing backend health test and minimal project metadata**

```python
from fastapi.testclient import TestClient
from resume_mvp.main import create_app

def test_health_reports_service_identity():
    response = TestClient(create_app()).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "resume-mvp"}
```

Declare FastAPI, Uvicorn, Pydantic, SQLAlchemy, httpx, PyMuPDF, python-docx and pytest dependencies in `backend/pyproject.toml`. Configure pytest with `pythonpath = ["."]`.

- [ ] **Step 2: Run the backend test and verify RED**

Run: `cd backend && uv run pytest tests/test_health.py -q`

Expected: FAIL because `resume_mvp.main` does not exist.

- [ ] **Step 3: Implement `create_app` and health route**

```python
def create_app() -> FastAPI:
    app = FastAPI(title="中文 AI 简历工作台", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "resume-mvp"}

    return app

app = create_app()
```

- [ ] **Step 4: Run the backend test and verify GREEN**

Run: `cd backend && uv run pytest tests/test_health.py -q`

Expected: `1 passed`.

- [ ] **Step 5: Add failing frontend shell test and Vite test configuration**

```tsx
import { render, screen } from "@testing-library/react";
import { App } from "./app";

test("显示产品身份和隐私说明", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "简历证据工作台" })).toBeInTheDocument();
  expect(screen.getByText("简历默认只保存在本机")).toBeInTheDocument();
});
```

Declare React, React DOM, React Router, TanStack Query, Zustand, Zod, Vite, Vitest, jsdom and Testing Library in `web/package.json`.

- [ ] **Step 6: Run the frontend test and verify RED**

Run: `cd web && pnpm install && pnpm test -- --run src/app.test.tsx`

Expected: FAIL because `App` does not exist.

- [ ] **Step 7: Implement the accessible application shell**

Render a `main` element containing the product heading, `简历默认只保存在本机`, and a disabled loading-free project area. Add `pnpm dev`, `test`, `build`, and `lint` scripts. Make `make dev` start Uvicorn and Vite with a trap that stops both processes.

- [ ] **Step 8: Verify shell tests and commit**

Run: `cd web && pnpm test -- --run src/app.test.tsx && pnpm build && cd ../backend && uv run pytest -q`

Expected: frontend test passes, Vite build exits 0, backend test passes.

```bash
git add .gitignore Makefile backend web
git commit -m "chore: scaffold local resume workspace"
```

---

### Task 2: Fact-backed resume domain and local persistence

**Files:**
- Create: `backend/resume_mvp/config.py`
- Create: `backend/resume_mvp/database.py`
- Create: `backend/resume_mvp/domain.py`
- Create: `backend/resume_mvp/tables.py`
- Create: `backend/resume_mvp/repositories.py`
- Create: `backend/tests/test_domain.py`
- Create: `backend/tests/test_repositories.py`

**Interfaces:**
- Produces: `Fact`, `SourcedText`, `ResumeDocument`, `ResumeVersion`, `JobProject`, `JobAnalysis`, `ResumePatchOperation`, `ResumePatch`.
- Produces: `ProjectRepository.create`, `.list`, `.get`, `.update`, `.save_version`, `.list_versions`, `.activate_version`.

- [ ] **Step 1: Write failing domain tests**

```python
def test_ai_rewrite_requires_supporting_facts():
    with pytest.raises(ValidationError, match="事实来源"):
        SourcedText(value="提升转化率 40%", origin="ai_rewrite", source_fact_ids=[])

def test_blank_resume_has_stable_chinese_section_order():
    resume = ResumeDocument.blank()
    assert resume.section_order == ["basics", "work_experience", "projects", "education", "skills"]
```

- [ ] **Step 2: Run domain tests and verify RED**

Run: `cd backend && uv run pytest tests/test_domain.py -q`

Expected: FAIL because domain types do not exist.

- [ ] **Step 3: Implement typed domain objects**

Use UUID strings for stable IDs. `SourcedText` must reject `origin="ai_rewrite"` when `source_fact_ids` is empty. Model basics, education, work, projects, skills, certificates, awards, custom sections, layout profile, and section order without untyped nested dictionaries.

- [ ] **Step 4: Run domain tests and verify GREEN**

Run: `cd backend && uv run pytest tests/test_domain.py -q`

Expected: all domain tests pass.

- [ ] **Step 5: Write failing repository lifecycle test**

```python
def test_project_versions_are_immutable_and_switchable(repository):
    project = repository.create(title="后端开发", company_name="示例科技", job_description="负责 API 开发")
    first = repository.save_version(project.id, ResumeDocument.blank(), reason="初始版本")
    second_resume = ResumeDocument.blank()
    second_resume.basics.name = "林晓"
    second = repository.save_version(project.id, second_resume, reason="补充姓名")
    repository.activate_version(project.id, first.id)
    assert repository.get(project.id).active_resume_version_id == first.id
    assert [v.id for v in repository.list_versions(project.id)] == [second.id, first.id]
```

- [ ] **Step 6: Run repository test and verify RED**

Run: `cd backend && uv run pytest tests/test_repositories.py -q`

Expected: FAIL because repository and tables do not exist.

- [ ] **Step 7: Implement SQLite records and repository**

Store project metadata, current analysis JSON, selected template, immutable resume-version JSON, facts JSON, and timestamps. `DatabaseSettings.data_dir` defaults to `.data` under the repository root and can be overridden by `RESUME_DATA_DIR`. Tests inject a temporary SQLite file.

- [ ] **Step 8: Verify domain and repository suite and commit**

Run: `cd backend && uv run pytest tests/test_domain.py tests/test_repositories.py -q`

Expected: all tests pass.

```bash
git add backend/resume_mvp backend/tests
git commit -m "feat: add fact-backed resume persistence"
```

---

### Task 3: Resume ingestion with quality reporting

**Files:**
- Create: `backend/resume_mvp/ingestion.py`
- Create: `backend/tests/test_ingestion.py`

**Interfaces:**
- Consumes: `ResumeDocument`, `Fact`, `LayoutProfile` from Task 2.
- Produces: `ImportResult(resume, facts, layout_profile, quality_score, warnings)`.
- Produces: `import_resume(filename: str, content_type: str, data: bytes) -> ImportResult`.

- [ ] **Step 1: Write failing TXT, DOCX, and PDF import tests**

```python
def test_txt_import_preserves_lines_as_confirmable_facts():
    result = import_resume("resume.txt", "text/plain", "张宁\n产品经理\n负责增长实验".encode())
    assert result.resume.basics.name == "张宁"
    assert any("增长实验" in fact.statement for fact in result.facts)
    assert result.quality_score > 0

def test_rejects_scanned_or_empty_pdf():
    with pytest.raises(ResumeImportError, match="未提取到可用文字"):
        import_resume("scan.pdf", "application/pdf", make_blank_pdf())
```

Create DOCX and text-PDF bytes inside tests with `python-docx` and PyMuPDF, so fixtures remain reproducible.

- [ ] **Step 2: Run ingestion tests and verify RED**

Run: `cd backend && uv run pytest tests/test_ingestion.py -q`

Expected: FAIL because `import_resume` does not exist.

- [ ] **Step 3: Implement validation, extraction, and section heuristics**

Accept only `.txt`, `.docx`, `.pdf`, enforce a 10 MiB limit, and verify extension plus content type. Extract DOCX paragraph/run styles, PDF block coordinates/font/size/color, and UTF-8 TXT. Recognize Chinese headings such as `教育经历`, `工作经历`, `项目经历`, `技能`, and `证书`; place unrecognized text in a custom `原始内容` section rather than dropping it.

- [ ] **Step 4: Add quality and warning behavior**

Calculate quality from non-empty text, recognized sections, dates, and contact-like fields. Return warnings for low section recognition, unusual encodings, and PDF visual reconstruction. Never return an empty official resume version.

- [ ] **Step 5: Verify ingestion suite and commit**

Run: `cd backend && uv run pytest tests/test_ingestion.py -q`

Expected: TXT and generated DOCX/PDF tests pass; empty PDF is rejected.

```bash
git add backend/resume_mvp/ingestion.py backend/tests/test_ingestion.py
git commit -m "feat: import Chinese resume documents"
```

---

### Task 4: Safe patches, explainable matching, and version rollback

**Files:**
- Create: `backend/resume_mvp/patches.py`
- Create: `backend/resume_mvp/matching.py`
- Create: `backend/tests/test_patches.py`
- Create: `backend/tests/test_matching.py`

**Interfaces:**
- Consumes: domain types and `ProjectRepository`.
- Produces: `apply_resume_patch(resume, patch, accepted_operation_ids) -> ResumeDocument`.
- Produces: `calculate_match(job_analysis, resume, facts) -> MatchReport`.

- [ ] **Step 1: Write failing patch safety tests**

```python
def test_applies_only_explicitly_accepted_operations():
    updated = apply_resume_patch(resume, patch, accepted_operation_ids={"op-summary"})
    assert updated.basics.summary.value == "面向企业服务的产品经理"
    assert updated.basics.target_role.value == "产品经理"

def test_rejects_stale_before_value():
    patch.operations[0].before = "已被别人修改"
    with pytest.raises(PatchConflictError, match="内容已变化"):
        apply_resume_patch(resume, patch, {patch.operations[0].id})
```

- [ ] **Step 2: Run patch tests and verify RED**

Run: `cd backend && uv run pytest tests/test_patches.py -q`

Expected: FAIL because patch service does not exist.

- [ ] **Step 3: Implement allow-listed JSON Pointer patching**

Support replace and reorder operations only on resume fields defined by `ResumeDocument`. Validate the `before` value, supporting fact IDs, path existence, and accepted operation IDs. Deep-copy the source resume and revalidate the final object.

- [ ] **Step 4: Write failing explainable-match test**

```python
def test_match_report_links_requirements_to_facts():
    report = calculate_match(analysis, resume, facts)
    assert report.items[0].status == "已有证据"
    assert report.items[0].fact_ids == [facts[0].id]
    assert 0 <= report.coverage <= 1
```

- [ ] **Step 5: Implement deterministic matching baseline**

Normalize ASCII case and Chinese punctuation, match exact phrases and token overlap, and classify each requirement as `已有证据`, `证据较弱`, or `没有证据`. Calculate coverage as weighted supported requirements divided by total weight and retain supporting excerpts.

- [ ] **Step 6: Verify patch/matching suites and commit**

Run: `cd backend && uv run pytest tests/test_patches.py tests/test_matching.py tests/test_repositories.py -q`

Expected: all tests pass.

```bash
git add backend/resume_mvp/patches.py backend/resume_mvp/matching.py backend/tests
git commit -m "feat: add safe resume patches and matching"
```

---

### Task 5: OpenAI-compatible and Codex provider adapters

**Files:**
- Create: `backend/resume_mvp/providers/__init__.py`
- Create: `backend/resume_mvp/providers/base.py`
- Create: `backend/resume_mvp/providers/openai_compatible.py`
- Create: `backend/resume_mvp/providers/codex.py`
- Create: `backend/tests/test_openai_provider.py`
- Create: `backend/tests/test_codex_provider.py`

**Interfaces:**
- Produces: `await AIProvider.complete_json(prompt: str, schema: type[T]) -> T`.
- Produces: `OpenAICompatibleProvider`, `CodexProvider`, `ProviderError`, `ProviderAuthError`, `ProviderTimeoutError`, `ProviderFormatError`.
- Codex consumes an injectable `ProcessRunner` to make process behavior testable without paid/model calls.

- [ ] **Step 1: Write failing OpenAI-compatible adapter test**

```python
@pytest.mark.anyio
async def test_openai_provider_posts_chat_completions_and_validates_json(httpx_mock):
    httpx_mock.add_response(json={"choices": [{"message": {"content": '{"items":["Python"]}'}}]})
    result = await provider.complete_json("提取技能", SkillList)
    request = httpx_mock.get_request()
    assert request.url.path == "/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer secret"
    assert result.items == ["Python"]
```

- [ ] **Step 2: Run OpenAI adapter test and verify RED**

Run: `cd backend && uv run pytest tests/test_openai_provider.py -q`

Expected: FAIL because provider does not exist.

- [ ] **Step 3: Implement HTTP adapter and typed error mapping**

Use `httpx.AsyncClient` to POST model, messages, temperature, and `response_format={"type":"json_object"}`. Parse fenced or plain JSON. Map 401/403, timeout, non-success, and invalid JSON into distinct provider errors without including the API key in messages. Cancelling the request must cancel the pending HTTP operation.

- [ ] **Step 4: Write failing Codex command-minimization test**

```python
@pytest.mark.anyio
async def test_codex_uses_ephemeral_read_only_context(tmp_path, fake_runner):
    result = await provider.complete_json("分析岗位", JobAnalysis)
    command = fake_runner.last_command
    assert command[:2] == ["codex", "exec"]
    assert "--ephemeral" in command
    assert ["--sandbox", "read-only"] == command[command.index("--sandbox"):command.index("--sandbox") + 2]
    assert "--output-schema" in command
    assert result.role_title == "后端工程师"
    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 5: Run Codex adapter test and verify RED**

Run: `cd backend && uv run pytest tests/test_codex_provider.py -q`

Expected: FAIL because Codex provider does not exist.

- [ ] **Step 6: Implement ephemeral Codex adapter**

Create a temporary directory, write only JSON Schema and last-message paths, pass the prompt over stdin, and use `asyncio.create_subprocess_exec` for `codex exec - --ephemeral --sandbox read-only --ask-for-approval never --output-schema <schema> --output-last-message <output> --color never`. Set a configurable timeout, parse the output file, map login/timeout/process errors, terminate the child on cancellation, and remove the directory in `finally`.

- [ ] **Step 7: Verify provider tests and commit**

Run: `cd backend && uv run pytest tests/test_openai_provider.py tests/test_codex_provider.py -q`

Expected: all adapter tests pass with fake HTTP/process dependencies.

```bash
git add backend/resume_mvp/providers backend/tests/test_openai_provider.py backend/tests/test_codex_provider.py
git commit -m "feat: add API and Codex AI providers"
```

---

### Task 6: Typed JD, resume, and question workflows

**Files:**
- Create: `backend/resume_mvp/ai_workflows.py`
- Create: `backend/tests/test_ai_workflows.py`

**Interfaces:**
- Consumes: `AIProvider`, domain models, `calculate_match`.
- Produces: `await analyze_job(provider, company, jd) -> JobAnalysis`.
- Produces: `await generate_followup_questions(provider, analysis, resume, facts) -> list[FollowupQuestion]`.
- Produces: `await suggest_resume_patch(provider, analysis, resume, facts) -> ResumePatch`.

- [ ] **Step 1: Write failing workflow tests with a deterministic provider**

```python
@pytest.mark.anyio
async def test_suggestion_rejects_unsupported_fact_ids(fake_provider):
    fake_provider.response = patch_with_fact("missing-fact")
    with pytest.raises(UnsupportedFactError, match="缺少事实依据"):
        await suggest_resume_patch(fake_provider, analysis, resume, facts=[])

@pytest.mark.anyio
async def test_job_inferences_retain_jd_evidence(fake_provider):
    result = await analyze_job(fake_provider, "示例科技", "负责 Python API 与数据库优化")
    assert result.requirements[0].evidence_quote in "负责 Python API 与数据库优化"

@pytest.mark.anyio
async def test_invalid_structured_output_gets_one_format_repair(fake_provider):
    fake_provider.responses = ["not-json", valid_analysis()]
    result = await analyze_job(fake_provider, "示例科技", "负责 Python API")
    assert result.role_title
    assert fake_provider.calls == 2
```

- [ ] **Step 2: Run workflow tests and verify RED**

Run: `cd backend && uv run pytest tests/test_ai_workflows.py -q`

Expected: FAIL because workflow functions do not exist.

- [ ] **Step 3: Implement prompts and post-validation**

Prompts must say: use Chinese, return the supplied schema, never invent facts, quote JD evidence, and turn missing evidence into a question. Strip unnecessary contact details before provider calls. After completion, verify evidence quotes are literal JD substrings and every patch fact ID exists. If parsing or schema validation fails, make exactly one second provider call containing the invalid response and instruction `只修复为指定 JSON 结构，不增删事实`; then raise `ProviderFormatError` if validation still fails.

- [ ] **Step 4: Add question prioritization and duplicate control**

Return at most five questions, prioritize missing high-weight requirements, and deduplicate by normalized topic. Questions must be answerable about the user's own history and include a `可跳过` flag.

- [ ] **Step 5: Verify workflow suite and commit**

Run: `cd backend && uv run pytest tests/test_ai_workflows.py tests/test_matching.py tests/test_patches.py -q`

Expected: all tests pass.

```bash
git add backend/resume_mvp/ai_workflows.py backend/tests/test_ai_workflows.py
git commit -m "feat: orchestrate fact-safe AI resume workflows"
```

---

### Task 7: Project, provider, import, analysis, and patch HTTP APIs

**Files:**
- Modify: `backend/resume_mvp/main.py`
- Create: `backend/resume_mvp/api/__init__.py`
- Create: `backend/resume_mvp/api/dependencies.py`
- Create: `backend/resume_mvp/api/projects.py`
- Create: `backend/resume_mvp/api/providers.py`
- Create: `backend/tests/test_project_api.py`
- Create: `backend/tests/test_provider_api.py`

**Interfaces:**
- Consumes: repository, ingestion, providers, workflows, patches.
- Produces: the project and provider endpoints listed in the design spec through `/api/projects` and `/api/settings/providers`.

- [ ] **Step 1: Write failing project journey API test**

```python
def test_project_import_analyze_and_apply_selected_patch(client, fake_provider):
    created = client.post("/api/projects", json={
        "title": "后端工程师", "company_name": "示例科技", "job_description": "负责 Python API"
    }).json()
    imported = client.post(
        f"/api/projects/{created['id']}/resume/import",
        files={"file": ("resume.txt", "张宁\n后端工程师\n使用 Python 开发 API", "text/plain")},
    )
    assert imported.status_code == 200
    analysis = client.post(f"/api/projects/{created['id']}/analyze-jd", json={"provider":"test"})
    assert analysis.status_code == 200
```

- [ ] **Step 2: Run project API test and verify RED**

Run: `cd backend && uv run pytest tests/test_project_api.py -q`

Expected: FAIL with 404 for `/api/projects`.

- [ ] **Step 3: Implement project APIs and dependency injection**

Provide list/create/get/patch, import, manual resume save, versions, activate version, analyze JD, create facts, follow-up questions, suggest patch, and apply accepted operation routes. AI endpoints are `async def` and await the provider; if the browser aborts the request, cancellation propagates to HTTP or terminates the Codex child. Convert domain exceptions to stable Chinese `detail.code` and `detail.message` payloads.

- [ ] **Step 4: Write failing provider-settings security test**

```python
def test_provider_settings_never_echo_or_persist_api_key(client):
    response = client.patch("/api/settings/providers", json={
        "kind":"openai-compatible", "base_url":"http://localhost:9999", "model":"demo", "api_key":"secret"
    })
    assert "secret" not in response.text
    assert "secret" not in client.get("/api/settings/providers").text
```

- [ ] **Step 5: Implement in-memory provider registry and connection tests**

Store non-secret provider metadata in process memory, keep the key only in a private in-memory field, accept environment-variable fallback, and return only `configured: true/false`. Add a lightweight provider test route that reports distinct Chinese auth, timeout, and unavailable errors.

- [ ] **Step 6: Verify API suites and commit**

Run: `cd backend && uv run pytest tests/test_project_api.py tests/test_provider_api.py -q`

Expected: both suites pass with isolated temporary data and fake providers.

```bash
git add backend/resume_mvp backend/tests
git commit -m "feat: expose local resume workflow API"
```

---

### Task 8: Exports and Codex chat handoff

**Files:**
- Create: `backend/resume_mvp/exports.py`
- Create: `backend/resume_mvp/api/exports.py`
- Modify: `backend/resume_mvp/main.py`
- Create: `backend/tests/test_exports.py`
- Create: `backend/tests/test_export_api.py`

**Interfaces:**
- Produces: `build_docx(resume, template_id) -> bytes`.
- Produces: `build_resume_json(project, resume) -> bytes`.
- Produces: `build_codex_handoff(project, analysis, resume, facts) -> str`.

- [ ] **Step 1: Write failing export tests**

```python
def test_docx_export_can_be_reopened_and_contains_current_resume():
    data = build_docx(sample_resume(), "clear-single")
    doc = Document(BytesIO(data))
    assert "张宁" in "\n".join(p.text for p in doc.paragraphs)

def test_json_export_excludes_secrets():
    payload = json.loads(build_resume_json(project, resume))
    assert payload["resume"]["basics"]["name"] == "张宁"
    assert "api_key" not in json.dumps(payload)
```

- [ ] **Step 2: Run export tests and verify RED**

Run: `cd backend && uv run pytest tests/test_exports.py -q`

Expected: FAIL because export builders do not exist.

- [ ] **Step 3: Implement DOCX, JSON, and Markdown handoff builders**

Map the four template IDs to Chinese font, heading, margin, accent, and column-safe DOCX styles. DOCX remains editable and uses tables only where needed for the professional two-column template. Handoff sections are `任务`, `JD 摘要`, `已确认事实`, `当前简历`, `待解决问题`, `输出约束`; omit email and phone unless the user explicitly includes them in a selected fact.

- [ ] **Step 4: Add download routes and failing-route behavior**

Return attachment filenames with safe Chinese-role slugs and correct MIME types. A missing project/version returns 404; export generation errors return `EXPORT_FAILED` and never return a zero-byte attachment.

- [ ] **Step 5: Verify exports and commit**

Run: `cd backend && uv run pytest tests/test_exports.py tests/test_export_api.py -q`

Expected: DOCX/JSON reopen tests and route tests pass.

```bash
git add backend/resume_mvp/exports.py backend/resume_mvp/api/exports.py backend/resume_mvp/main.py backend/tests
git commit -m "feat: export resumes and Codex handoffs"
```

---

### Task 9: Interview and written-practice backend

**Files:**
- Create: `backend/resume_mvp/practice.py`
- Create: `backend/resume_mvp/api/practice.py`
- Modify: `backend/resume_mvp/tables.py`
- Modify: `backend/resume_mvp/repositories.py`
- Modify: `backend/resume_mvp/main.py`
- Create: `backend/tests/test_practice.py`
- Create: `backend/tests/test_practice_api.py`

**Interfaces:**
- Produces: `await start_practice(kind, provider, project, resume) -> PracticeSession`.
- Produces: `await answer_practice(session, answer, provider) -> PracticeTurn`.
- Produces: `POST /api/projects/{id}/practice/sessions`, `POST /api/practice/sessions/{id}/answer`, and `GET /api/practice/sessions/{id}`.

- [ ] **Step 1: Write failing practice tests**

```python
@pytest.mark.anyio
async def test_interview_feedback_uses_named_dimensions(fake_provider):
    session = await start_practice("interview", fake_provider, project, resume)
    turn = await answer_practice(session, "我负责重构订单接口……", fake_provider)
    assert set(turn.feedback.dimensions) == {"相关性", "具体性", "证据", "结构", "表达"}
    assert turn.feedback.percentage_score is None

@pytest.mark.anyio
async def test_written_practice_can_reveal_hint_before_explanation(fake_provider):
    session = await start_practice("written", fake_provider, project, resume)
    assert session.current_question.hint
    assert session.current_question.explanation is None
```

- [ ] **Step 2: Run practice tests and verify RED**

Run: `cd backend && uv run pytest tests/test_practice.py -q`

Expected: FAIL because practice service does not exist.

- [ ] **Step 3: Implement typed practice prompts and persistence**

Interview categories are motivation, experience drill-down, behavioral, professional, and candidate questions. Written categories are choice, short answer, case, and professional. Store prompts, answers, follow-ups, evidence links, and feedback; reveal explanations only after an answer.

- [ ] **Step 4: Implement practice routes and lifecycle tests**

Validate `kind`, require an active resume and analysis, preserve the session on provider failure, and return saved weakness summaries at completion.

- [ ] **Step 5: Verify practice suites and commit**

Run: `cd backend && uv run pytest tests/test_practice.py tests/test_practice_api.py -q`

Expected: practice service and route tests pass.

```bash
git add backend/resume_mvp backend/tests
git commit -m "feat: add interview and written practice"
```

---

### Task 9A: Application type and one-page policy

**Files:**
- Modify: `backend/resume_mvp/domain.py`
- Modify: `backend/resume_mvp/tables.py`
- Modify: `backend/resume_mvp/repositories.py`
- Create: `backend/resume_mvp/page_policy.py`
- Modify: `backend/resume_mvp/api/projects.py`
- Modify: `backend/resume_mvp/api/exports.py`
- Modify: `backend/resume_mvp/exports.py`
- Create: `backend/tests/test_page_policy.py`
- Modify: `backend/tests/test_project_api.py`
- Modify: `backend/tests/test_exports.py`
- Modify: `backend/tests/test_export_api.py`

**Interfaces:**
- Produces: `ApplicationType = Literal["campus", "internship", "experienced"]` on every `JobProject`.
- Produces: `evaluate_page_policy(resume, application_type) -> PagePolicyResult` with `compact`, `max_pages`, `estimated_units`, `capacity_units`, `overflow`.

- [ ] **Step 1: Write failing page-policy and project-roundtrip tests**

```python
def test_campus_and_internship_use_compact_one_page_policy():
    assert evaluate_page_policy(short_resume, "campus").max_pages == 1
    assert evaluate_page_policy(short_resume, "internship").compact is True

def test_experienced_resume_never_blocks_for_length():
    result = evaluate_page_policy(long_resume, "experienced")
    assert result.max_pages is None
    assert result.overflow is False

def test_project_api_roundtrips_application_type(client):
    response = client.post("/api/projects", json={
        "title":"实习申请", "company_name":"", "application_type":"internship", "job_description":"参与 Python API 开发"
    })
    assert response.json()["application_type"] == "internship"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd backend && uv run pytest tests/test_page_policy.py tests/test_project_api.py -q`

Expected: FAIL because projects and policy do not contain `application_type`.

- [ ] **Step 3: Implement persistence and deterministic capacity policy**

Count visible Chinese/ASCII characters plus fixed costs for headings and entries. Campus/internship use compact tokens and a hand-checked one-page capacity derived from the built-in A4 preview; experienced resumes return unlimited capacity. The estimator never removes or truncates content.

- [ ] **Step 4: Apply policy to prompts and exports**

Add the application type and one-page constraint to resume-suggestion prompts. `build_docx` accepts application type and uses compact margins, 9-point body text, tighter paragraph spacing, and compact headings for campus/internship. The DOCX route returns `422 RESUME_OVERFLOW` before generation when the deterministic estimate exceeds one page.

- [ ] **Step 5: Verify policy, API, exports, and commit**

Run: `cd backend && uv run pytest tests/test_page_policy.py tests/test_project_api.py tests/test_exports.py tests/test_export_api.py -q`

Expected: one-page rules and all existing export/API behavior pass.

```bash
git add backend docs/superpowers
git commit -m "feat: enforce compact one-page campus resumes"
```

---

### Task 10: Frontend types, API client, routing, and project home

**Files:**
- Modify: `web/src/main.tsx`
- Modify: `web/src/app.tsx`
- Create: `web/src/types.ts`
- Create: `web/src/api/client.ts`
- Create: `web/src/pages/HomePage.tsx`
- Create: `web/src/pages/WorkspacePage.tsx`
- Create: `web/src/pages/PracticePage.tsx`
- Create: `web/src/pages/SettingsPage.tsx`
- Create: `web/src/components/ProjectForm.tsx`
- Create: `web/src/components/ProviderStatus.tsx`
- Create: `web/src/pages/HomePage.test.tsx`
- Create: `web/src/components/ProjectForm.test.tsx`

**Interfaces:**
- Consumes: Task 7-9 HTTP APIs.
- Produces: `api` typed methods and routes `/`, `/projects/:id`, `/projects/:id/practice`, `/settings`.

- [ ] **Step 1: Write failing project-form behavior tests**

```tsx
test("JD 为空时不创建项目并给出中文提示", async () => {
  render(<ProjectForm onCreate={vi.fn()} />);
  await user.click(screen.getByRole("button", { name: "创建求职项目" }));
  expect(screen.getByText("请先粘贴职位描述")).toBeInTheDocument();
});

test("公司名称可以留空", async () => {
  const onCreate = vi.fn();
  render(<ProjectForm onCreate={onCreate} />);
  await user.type(screen.getByLabelText("项目名称"), "后端工程师");
  await user.type(screen.getByLabelText("职位描述"), "负责 Python API 开发");
  await user.click(screen.getByRole("button", { name: "创建求职项目" }));
  expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({ company_name: "" }));
});

test("创建项目必须选择校招、实习或社招", async () => {
  render(<ProjectForm onCreate={onCreate} />);
  await user.click(screen.getByRole("radio", { name: "校招" }));
  expect(screen.getByRole("radio", { name: "校招" })).toBeChecked();
});
```

- [ ] **Step 2: Run frontend tests and verify RED**

Run: `cd web && pnpm test -- --run src/components/ProjectForm.test.tsx`

Expected: FAIL because project form does not exist.

- [ ] **Step 3: Implement Zod contracts, fetch client, query provider, and routes**

Parse every response through a named Zod schema. Convert API `detail.message`, network failures, and unexpected responses into Chinese UI errors. Keep API keys out of Zustand, localStorage, URLs, and query cache.

- [ ] **Step 4: Implement project home and provider status**

Show project cards with company, role, application type, update time, and active stage. Provide an empty state with `创建第一份针对岗位的简历`. Provider status distinguishes unconfigured, connected, unavailable, and currently testing.

- [ ] **Step 5: Verify page tests and commit**

Run: `cd web && pnpm test -- --run src/pages/HomePage.test.tsx src/components/ProjectForm.test.tsx && pnpm build`

Expected: tests pass and production build exits 0.

```bash
git add web/src
git commit -m "feat: add project home and typed web client"
```

---

### Task 11: Resume workbench, templates, patch review, and printing

**Files:**
- Create: `web/src/state/editor.ts`
- Create: `web/src/components/ResumeIntake.tsx`
- Create: `web/src/components/JobAnalysisPanel.tsx`
- Create: `web/src/components/PatchReview.tsx`
- Create: `web/src/components/ResumeEditor.tsx`
- Create: `web/src/components/ResumePreview.tsx`
- Create: `web/src/components/TemplatePicker.tsx`
- Create: `web/src/templates/registry.tsx`
- Modify: `web/src/pages/WorkspacePage.tsx`
- Modify: `web/src/styles.css`
- Create: `web/src/components/PatchReview.test.tsx`
- Create: `web/src/components/TemplatePicker.test.tsx`
- Create: `web/src/components/ResumePreview.test.tsx`

**Interfaces:**
- Consumes: project/import/analysis/patch/export APIs.
- Produces: `TEMPLATES` with IDs `clear-single`, `pro-double`, `project-focus`, `career-depth`.
- Produces: editor actions `loadResume`, `editField`, `togglePatch`, `setTemplate`, `discardDraft`.

- [ ] **Step 1: Write failing patch-review and template-stability tests**

```tsx
test("默认不接受 AI 修改，用户可以逐项勾选", async () => {
  render(<PatchReview patch={patch} onApply={onApply} />);
  expect(screen.getByRole("checkbox", { name: /面向企业服务/ })).not.toBeChecked();
  await user.click(screen.getByRole("checkbox", { name: /面向企业服务/ }));
  await user.click(screen.getByRole("button", { name: "应用已选修改" }));
  expect(onApply).toHaveBeenCalledWith([patch.operations[0].id]);
});

test("切换模板不改变简历内容", async () => {
  render(<TemplateHarness resume={resume} />);
  await user.click(screen.getByRole("button", { name: "专业双栏" }));
  expect(screen.getByText("张宁")).toBeInTheDocument();
  expect(screen.getByText("使用 Python 开发 API")).toBeInTheDocument();
});

test("校招简历溢出一页时阻止导出但不截断内容", () => {
  render(<ResumePreview resume={longResume} applicationType="campus" measuredOverflow />);
  expect(screen.getByText("当前内容超过一页")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "打印或保存 PDF" })).toBeDisabled();
  expect(screen.getByText(longResume.work_experience.at(-1)!.company)).toBeVisible();
});
```

- [ ] **Step 2: Run workbench component tests and verify RED**

Run: `cd web && pnpm test -- --run src/components/PatchReview.test.tsx src/components/TemplatePicker.test.tsx`

Expected: FAIL because components do not exist.

- [ ] **Step 3: Implement the three-column workflow and evidence rail**

Left column stages are `岗位信息`, `个人事实`, `匹配分析`, `简历优化`, `导出`, `求职训练`. Center shows the current task. Right shows A4 preview. Each changed resume bullet has an evidence marker that opens its source facts and JD requirement; this is the interface's signature element.

`ResumeIntake` offers `上传现有简历` and `从经历开始`. The manual path collects target role, education, recent experience, representative projects, and skills, then presents one server-generated follow-up question at a time with `保存回答` and `跳过`. Every saved answer creates a visible fact the user can edit or confirm.

- [ ] **Step 4: Implement four content-stable template renderers**

All templates consume the same `ResumeDocument`. `clear-single` is strict single column; `pro-double` reserves a narrow skills rail; `project-focus` emphasizes project titles and outcomes; `career-depth` emphasizes chronological work history. Imported layout tokens override font/accent/spacing only when valid. Campus and internship projects apply compact font, gap, line-height, and margin tokens; experienced projects render natural A4 page breaks.

Export `recommendTemplate(resume, analysis)` from `registry.tsx`: choose `project-focus` when project evidence outweighs work evidence, `pro-double` when categorized skills exceed eight, `career-depth` when work entries exceed three, otherwise `clear-single`. Show the recommendation reason and keep manual selection authoritative.

- [ ] **Step 5: Implement deliberate visual system and responsive/print CSS**

Use paper white `#F7F8FA`, ink `#172033`, cobalt `#2457D6`, review red `#C9364F`, muted slate `#687386`, and line `#DDE2EA`. UI type uses PingFang SC/Noto Sans CJK/system sans; preview headings use Songti SC/Noto Serif CJK/system serif. Use squared paper sheets, restrained 8px controls, visible 3px keyboard focus, reduced-motion media query, mobile stage tabs, and `@page { size: A4; margin: 0; }` with navigation hidden in print.

Version history buttons call the activate-version API after confirmation. Use `ResizeObserver` plus A4 content bounds to measure the preview. Campus/internship overflow keeps every section visible, marks the largest sections, shows `生成一页优化建议`, and disables PDF/DOCX controls; experienced resumes paginate naturally. The export stage provides `打印或保存 PDF`, `下载 DOCX`, `下载 JSON`, `复制 Codex 上下文`, and `下载 Codex 上下文`; printing calls `window.print()` and downloads use response blobs without opening user data in a new remote tab.

- [ ] **Step 6: Verify component tests, accessibility queries, and print build**

Run: `cd web && pnpm test -- --run src/components/PatchReview.test.tsx src/components/TemplatePicker.test.tsx src/components/ResumePreview.test.tsx && pnpm build`

Expected: tests pass, every control is reachable by role/label, production build exits 0.

```bash
git add web/src
git commit -m "feat: build resume evidence workbench"
```

---

### Task 12: Provider settings and training UI

**Files:**
- Modify: `web/src/pages/SettingsPage.tsx`
- Modify: `web/src/pages/PracticePage.tsx`
- Create: `web/src/components/PracticePanel.tsx`
- Create: `web/src/pages/SettingsPage.test.tsx`
- Create: `web/src/components/PracticePanel.test.tsx`

**Interfaces:**
- Consumes: provider and practice APIs.
- Produces: process-memory-only API key form and complete text interview/written-practice flow.

- [ ] **Step 1: Write failing secret-lifecycle and practice tests**

```tsx
test("保存连接后清空 API Key 输入框", async () => {
  render(<SettingsPage />);
  await user.type(screen.getByLabelText("API Key"), "secret");
  await user.click(screen.getByRole("button", { name: "保存并测试连接" }));
  expect(screen.getByLabelText("API Key")).toHaveValue("");
});

test("笔试解析在提交答案前不可见", () => {
  render(<PracticePanel session={writtenSession} />);
  expect(screen.queryByText("参考解析")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "查看提示" })).toBeEnabled();
});
```

- [ ] **Step 2: Run settings/practice tests and verify RED**

Run: `cd web && pnpm test -- --run src/pages/SettingsPage.test.tsx src/components/PracticePanel.test.tsx`

Expected: FAIL because functional settings and practice components do not exist.

- [ ] **Step 3: Implement provider settings**

Support API and Codex cards, base URL/model/timeout/temperature fields, password-type API key, `保存并测试连接`, and Codex privacy confirmation. Never persist the API key client-side and clear it after every request.

- [ ] **Step 4: Implement training flow**

Allow interview or written mode, one question at a time, answer submission, follow-up, hint, evidence drawer, feedback dimensions, and saved weakness summary. Show provider errors inline without discarding the current answer.

- [ ] **Step 5: Verify settings/training tests and commit**

Run: `cd web && pnpm test -- --run src/pages/SettingsPage.test.tsx src/components/PracticePanel.test.tsx && pnpm build`

Expected: tests pass and build exits 0.

```bash
git add web/src
git commit -m "feat: add provider settings and job practice UI"
```

---

### Task 13: End-to-end journey, operational docs, and full verification

**Files:**
- Create: `web/playwright.config.ts`
- Create: `web/e2e/resume-flow.spec.ts`
- Create: `backend/tests/fixtures/sample_resume.txt`
- Create: `README.md`
- Modify: `Makefile`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: `make install`, `make dev`, `make test`, `make build`, and a documented local workflow.

- [ ] **Step 1: Write the failing browser journey**

```ts
test("从中文经历到针对岗位的简历和模拟面试", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "创建求职项目" }).click();
  await page.getByLabel("项目名称").fill("后端工程师");
  await page.getByLabel("职位描述").fill("负责 Python API 与数据库性能优化");
  await page.getByRole("button", { name: "保存项目" }).click();
  await page.getByLabel("上传现有简历").setInputFiles("../backend/tests/fixtures/sample_resume.txt");
  await expect(page.getByText("张宁")).toBeVisible();
  await page.getByRole("button", { name: "分析职位描述" }).click();
  await expect(page.getByText("匹配分析")).toBeVisible();
  await page.getByRole("button", { name: "生成优化建议" }).click();
  await page.getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "应用已选修改" }).click();
  await page.getByRole("button", { name: "专业双栏" }).click();
  await expect(page.locator(".resume-sheet")).toContainText("张宁");
});
```

Use a deterministic in-process fake provider enabled only by `RESUME_MVP_TEST_PROVIDER=1`; production mode must reject provider kind `test`.

- [ ] **Step 2: Run E2E and verify RED**

Run: `make e2e`

Expected: FAIL at the first missing or mismatched journey behavior.

- [ ] **Step 3: Close E2E wiring gaps without adding new scope**

Wire the existing routes and components until the fixed journey passes. Add no new feature that is absent from the approved spec. Make print mode expose the current `.resume-sheet`, hide controls, and retain all visible resume text.

- [ ] **Step 4: Write local setup and privacy documentation**

Document prerequisites, `make install`, `make dev`, ports, `.data` location, supported file types, API settings, Codex login requirement, what leaves the machine, export behavior, testing, known PDF/template limitations, and future Qwen3.8 27B adapter point.

- [ ] **Step 5: Run fresh full verification**

Run: `make test && make build && make e2e`

Expected: backend pytest has zero failures, frontend Vitest has zero failures, backend import check exits 0, Vite production build exits 0, and Playwright journey passes.

- [ ] **Step 6: Review requirement coverage and repository state**

Run: `git status --short && git diff --check && rg -n "TO[D]O|T[B]D|FIX[M]E" README.md backend web docs/superpowers`

Expected: only intentional plan checkbox changes may be uncommitted, `git diff --check` is clean, and the placeholder scan returns no implementation placeholders.

- [ ] **Step 7: Commit delivery**

```bash
git add README.md Makefile backend web docs/superpowers/plans/2026-08-23-chinese-ai-resume-mvp.md
git commit -m "test: verify complete Chinese resume MVP"
```
