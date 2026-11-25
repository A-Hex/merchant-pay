# CEO-Pay - common tasks. Run from the repository root.
BACK := src/backend
FRONT := src/frontend

.PHONY: up down logs migrate seed reset-demo test lint gen-api dev-back dev-front install

install:            ## install backend + frontend dependencies
	cd $(BACK) && uv sync
	cd $(FRONT) && npm install

up:                 ## start Postgres + API (http://localhost:8000/api/docs)
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f backend

migrate:            ## apply DB migrations (inside the API container)
	docker compose exec backend alembic upgrade head

seed reset-demo:    ## wipe + reseed deterministic demo data (+ workbook in data/source/)
	docker compose exec backend python -m app.seed.reset

test:               ## backend tests + frontend typecheck
	cd $(BACK) && uv run pytest -q
	cd $(FRONT) && npx tsc --noEmit

lint:
	cd $(BACK) && uv run ruff check .
	cd $(FRONT) && npx tsc --noEmit

gen-api:            ## regenerate frontend API types from the FastAPI schema (no server needed)
	cd $(BACK) && uv run python -c "import json; from app.main import create_app; print(json.dumps(create_app().openapi()))" > ../frontend/openapi.json
	cd $(FRONT) && npx openapi-typescript openapi.json -o src/api/schema.d.ts && rm openapi.json

dev-back:           ## run API locally with reload (needs `docker compose up -d db`)
	cd $(BACK) && uv run alembic upgrade head && uv run uvicorn app.main:app --reload

dev-front:          ## run the web app (http://localhost:5173)
	cd $(FRONT) && npm run dev
