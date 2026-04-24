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
- Raw HTML is published to Kafka and processed directly by the MVP worker path.
- The extraction fallback chain stores structured data in PostgreSQL.
- Job, page, health, and extracted intelligence are available through the API and dashboard.

## Useful Commands

```powershell
npm run dev
npm run build
npm run logs
npm run docker:down
docker compose logs -f backend-api celery-worker extraction-worker
docker compose exec backend-api alembic upgrade head
docker compose down
```

Set `OPENAI_API_KEY` in the backend environment to enable the OpenAI extraction and schema-generation tiers.
# scapsy
