# Task 4 report

## Result

Implemented persistence for optimization runs, immutable step attempts, and layout reports in `backend/resume_mvp/tables.py` and `backend/resume_mvp/repositories.py`.

- `OptimizationRunRecord` stores an indexed status projection alongside a validated serialized `OptimizationRun` payload; updates keep both values synchronized in one transaction.
- `OptimizationStepRecord` stores immutable `(run, kind, iteration, attempt)` records with input hash, output, status, error code, and timestamp.
- `LayoutReportRecord` round-trips validated `LayoutReport` payloads by run and iteration.
- Added checkpoint lookup scoped to the target project, restricted to successful matching hashes created within 24 hours. The API accepts an injectable clock/current timestamp for deterministic tests.
- Added cancellation persistence and explicit optimization-child deletion in `ProjectRepository.delete`.

## Tests

Passed:

```text
uv run pytest tests/test_optimization_repository.py -v
9 passed

uv run pytest tests/test_optimization_repository.py tests/test_repositories.py tests/test_health.py -v
12 passed

git diff --check
no output
```

The full backend suite was also run: 127 passed, 8 failed. The failures are existing export/preview/practice API setup failures where project creation returned no `id`; none exercised Task 4 persistence.

## Concerns

The repository records use SQLite-compatible JSON and timestamp columns. Existing SQLite databases receive the three new tables through `create_all`; no destructive migration is required. The full-suite failures remain outside this task's files and were not modified.

## Commit

`feat: persist optimization loop checkpoints` (final commit on this worktree)

## Review fix round 1

Addressed the three requested review findings:

- Checkpoint reuse now requires a target run or explicit project scope and always filters by that project; no-scope and cross-project matches are rejected.
- `OptimizationRun` and `LayoutReport` are serialized before validation so in-place mutations cannot bypass Pydantic constraints.
- The immutable-attempt test repeats the exact same key, asserts rejection, and verifies the original row remains unchanged while retaining the 1/2 attempt ordering test.

Verification:

```text
uv run pytest tests/test_optimization_repository.py -v
12 passed

uv run pytest tests/test_optimization_repository.py tests/test_repositories.py tests/test_health.py -v
15 passed

git diff --check
no output
```

Fix commit: `fix: tighten optimization checkpoint persistence invariants` (final commit on this worktree)
