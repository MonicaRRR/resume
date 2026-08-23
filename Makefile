.PHONY: install dev test build e2e

install:
	cd backend && uv sync
	cd web && pnpm install

dev:
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && uv run uvicorn resume_mvp.main:app --host 127.0.0.1 --port 8000 --reload) & \
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
