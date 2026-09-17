.PHONY: install dev test build e2e seed-smoke smoke-sandbox whitebox whitebox-campus

install:
	cd backend && uv sync
	cd web && pnpm install

dev:
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && UV_CACHE_DIR="$(CURDIR)/.uv-cache" uv run uvicorn resume_mvp.main:app --host 127.0.0.1 --port 8000 --reload) & \
	(cd web && pnpm dev) & \
	wait

test:
	cd backend && uv run pytest -q
	cd web && pnpm test -- --run

build:
	cd backend && uv run python -c "from resume_mvp.main import app; assert app.title"
	cd web && pnpm build

e2e:
	cd web && pnpm e2e

seed-smoke:
	cd backend && .venv/bin/python scripts/seed_smoke_profile.py
	cd backend && .venv/bin/python scripts/seed_smoke_project.py

smoke-sandbox:
	cd backend && .venv/bin/python scripts/smoke_sandbox.py

whitebox:
	cd backend && .venv/bin/python scripts/whitebox_optimization.py

whitebox-campus:
	cd backend && .venv/bin/python scripts/whitebox_optimization.py \
		--tag campus \
		--profile fixtures/smoke_profile_campus.json \
		--project fixtures/smoke_project_campus.json
