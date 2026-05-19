# WebIntel AI

Distributed web intelligence MVP for seed-URL crawling, extraction, persistence, and operations monitoring.

## Quickstart

From the project root:

```powershell
npm install
npm run dev
```

That single command starts Docker services, runs Alembic migrations, and launches the UI.

If you run from WSL, Docker Desktop must have WSL integration enabled for your distro. If Docker is not available yet, `npm run dev` will explain the missing dependency and you can still run the UI alone with:

```powershell
npm run dev:ui
```

Open:

- API: `http://localhost:8000/docs`
- UI: `http://localhost:5173`

## MVP Flow

- Create a job from the operations console or `POST /api/v1/jobs`.
- Celery fetches each seed URL with HTTP or Playwright.
- Raw HTML is published to Kafka and processed by extraction and storage workers.
- The storage worker persists records to PostgreSQL and pushes snapshots to Elasticsearch, Neo4j, and MinIO.
- Job, page, health, and extracted intelligence are available through the API and dashboard.

## Useful Commands

```powershell
npm run dev
npm run build
npm run check:system
npm run logs
npm run docker:down
docker compose logs -f backend-api celery-worker extraction-worker
docker compose logs -f backend-api celery-worker extraction-worker storage-worker
docker compose exec backend-api alembic upgrade head
docker compose down
```

Set `OPENAI_API_KEY` in the backend environment to enable the OpenAI extraction and schema-generation tiers.

Auth setup:

- Set `JWT_PRIVATE_KEY_PEM` and `JWT_PUBLIC_KEY_PEM` for RS256 tokens.
- Optional bootstrap admin: `BOOTSTRAP_ADMIN_EMAIL` + `BOOTSTRAP_ADMIN_PASSWORD` (first login only).
- Seed admin manually: `python backend/scripts/seed_admin.py`
- UI token: set `localStorage.setItem("webintel_access_token", "<access_token>")` after logging in.

Optional services are wired into Docker Compose: Neo4j (`7474/7687`), MinIO (`9000/9001`), and Ollama (`11434`).

## Working / Broken Checks

The dashboard now includes a readiness matrix that separates capabilities into working, degraded, and broken states. From a terminal, run:

```powershell
npm run check:system
```

This calls `/health` and `/api/v1/system/readiness` and exits non-zero if a required dependency is down.

## Production Plan

The full scaffold, API plan, crawler design, extraction tiers, ML/RL plan, 9-screen UI spec, observability/security plan, CI/CD notes, 12-week board, acceptance criteria, and risk register live in:

- `docs/WEBINTEL_AI_IMPLEMENTATION_PLAN.md`
# scapsy
