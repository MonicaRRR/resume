# FreeAiHR-Inspired Job Assistant Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the five highest-value FreeAiHR-inspired capabilities to the local Chinese resume workbench without introducing enterprise-only infrastructure.

**Architecture:** Extend the existing PracticeSession and ProviderRegistry boundaries. Add lightweight persisted question sets, interview scoring/report data, a unified job timeline projection, and explicit provider/task capability metadata. Keep SQLite, local-first storage, and existing API compatibility.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy JSON records, React, TypeScript, Vitest, Pytest.

**Source reference:** The upstream FreeAiHR repository documents resume parsing, job matching, question sets, text/voice interviews, reports, provider configuration, and role-based enterprise features. AGPL source is referenced for domain boundaries only; enterprise auth/SSO/license code is out of scope.

## Global Constraints

- Existing local single-user flows must keep working.
- No PostgreSQL, Redis, Celery, SSO, billing, or remote invite dependency in this MVP.
- Chinese UI only.
- Existing `PracticeSession` API remains backward compatible.

### Task 1: Question library and question sets

**Files:** Modify `backend/resume_mvp/domain.py`, `tables.py`, `repositories.py`, `main.py`; create `backend/resume_mvp/question_sets.py`, `api/question_sets.py`; tests in `backend/tests/test_question_sets_api.py`.

- [ ] Add persisted question-set JSON records with source type (`jd`, `resume`, `project`), questions, reuse count, and timestamps.
- [ ] Add create/list/get endpoints and deterministic fallback question generation from current JD/resume when no provider is available.
- [ ] Add frontend API/types and a minimal question-set picker in the practice entry flow.

### Task 2: Multi-round interview engine

**Files:** Modify `practice.py`, `domain.py`, `api/practice.py`; tests in `backend/tests/test_practice_api.py`.

- [ ] Add interview mode labels (`technical`, `hr`, `manager`) and preserve them in sessions.
- [ ] Generate next questions using session history and question sets, with one-question-at-a-time behavior.
- [ ] Keep written practice behavior unchanged.

### Task 3: Scoring and reports

**Files:** Modify `domain.py`, `practice.py`, `api/practice.py`; frontend `PracticePanel.tsx`; tests in backend and frontend.

- [ ] Persist per-turn numeric dimensions and a session summary report.
- [ ] Add report endpoint and UI summary with strengths, risks, and follow-up recommendations.
- [ ] Ensure missing AI output falls back to deterministic rubric scoring.

### Task 4: Job-seeking timeline

**Files:** Create `backend/resume_mvp/timeline.py`, `api/timeline.py`; frontend timeline component; tests in `backend/tests/test_timeline_api.py`.

- [ ] Project a timeline from resume versions, match reports, optimization runs, and practice sessions.
- [ ] Return stable chronological events with source IDs and concise Chinese labels.
- [ ] Display timeline in the workspace without changing existing records.

### Task 5: Provider capabilities and task state

**Files:** Modify provider registry/settings APIs and frontend settings; tests in `backend/tests/test_provider_capabilities.py`.

- [ ] Expose provider capabilities (`json`, `vision`, `voice`, `local`) and task availability.
- [ ] Add a small task-state model for queued/running/waiting/completed/failed UI state, reusing existing optimization status conventions.
- [ ] Keep current API credential storage and provider selection behavior intact.
