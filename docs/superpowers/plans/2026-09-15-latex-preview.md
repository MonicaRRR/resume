# LaTeX Resume Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide LaTeX-based resume output and a usable preview without LibreOffice, while refreshing education evidence from the current resume.

**Architecture:** Add a pure renderer module for escaped UTF-8 XeLaTeX, compiler detection with safe temporary execution, and a browser fallback that uses the existing structured resume data. Keep existing DOCX export intact.

**Tech Stack:** Python, FastAPI, XeLaTeX/Tectonic when available, React, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-09-15-latex-preview-design.md`

## Global Constraints

- Chinese text must remain UTF-8 and must be escaped before LaTeX interpolation.
- Missing TeX compiler must not make preview unusable.
- Existing DOCX export remains available.

### Task 1: LaTeX source renderer

**Files:** Create `backend/resume_mvp/latex.py`; Test `backend/tests/test_latex.py`.

- [ ] Write tests for Chinese escaping, education rendering, and one-page compact options.
- [ ] Implement `build_latex(resume, template_id, application_type) -> str` with safe escaping and deterministic sections.
- [ ] Run `pytest backend/tests/test_latex.py -v`.

### Task 2: API output and compiler fallback

**Files:** Modify `backend/resume_mvp/api/exports.py`, `backend/resume_mvp/preview.py`; Test `backend/tests/test_preview.py`.

- [ ] Add a `.tex` download endpoint.
- [ ] Add TeX compiler detection and safe PDF compilation.
- [ ] Return a typed unavailable response when no compiler exists so clients can fall back.
- [ ] Add tests for endpoint and compiler absence.

### Task 3: Web preview fallback

**Files:** Modify `web/src/components/ResumePreview.tsx`; Test `web/src/components/ResumePreview.test.tsx`.

- [ ] Add a structured HTML preview fallback when PNG preview reports missing compiler.
- [ ] Update labels and download action for LaTeX output.
- [ ] Run frontend tests and build.

### Task 4: Education evidence refresh

**Files:** Modify `backend/resume_mvp/api/projects.py`; Test `backend/tests/test_evidence_match.py`.

- [ ] Add a regression test proving an active version with education gets refreshed deterministic evidence.
- [ ] Ensure cached reports are merged against current education before response.
- [ ] Run backend test suite.
