# WebIntel AI Production Scaffold

## 1. Project Summary

WebIntel AI is a distributed, self-healing web intelligence platform for analysts, researchers, and enterprise teams that need repeatable web monitoring, extraction, storage, and visualization from natural-language instructions. The primary flow is: create a natural-language job, classify the target sites as static or dynamic, crawl with Scrapy or Playwright, extract structured records through a five-tier fallback chain, store raw and normalized artifacts in PostgreSQL, Elasticsearch, Neo4j, and MinIO, then visualize findings through feeds, dashboards, graph exploration, search, alerts, and observability screens.

## 2. Tech Stack

Backend: Python 3.11 + FastAPI; GraphQL: Strawberry; Workers: Celery + RedBeat; Broker: Kafka; DB: PostgreSQL 16 (asyncpg); Search: Elasticsearch 8.x; Graph DB: Neo4j 5; Object store: MinIO; Crawler: Scrapy + Playwright; ML: Hugging Face Transformers (DistilBERT), spaCy, sentence-transformers; RL: Stable-Baselines3 (PPO); Frontend: React 18 + TypeScript + Vite; UI: shadcn/ui + Tailwind; Charts: Recharts; Graph: D3.js.

## 3. Repo Scaffold

```text
backend/app/main.py                         FastAPI app factory, CORS, lifecycle, root health.
backend/app/api/v1/router.py                REST router assembly.
backend/app/api/v1/jobs.py                  Create/list/detail/cancel crawl jobs.
backend/app/api/v1/data.py                  Extracted record listing and filtering.
backend/app/api/v1/ai_engine.py             NL instruction to schema generation.
backend/app/api/v1/system.py                Health and readiness matrix endpoints.
backend/app/graphql/schema.py               Strawberry GraphQL types, query, mutation, subscription scaffold.
backend/app/models/base.py                  SQLAlchemy async base, UUID and timestamp mixins.
backend/app/models/job.py                   Job SQL model and status enum.
backend/app/models/page.py                  Page SQL model and crawl state.
backend/app/models/extracted_data.py        Record SQL model for normalized extracted payloads.
backend/app/schemas/jobs.py                 Pydantic request/response schemas.
backend/app/schemas/data.py                 Pydantic extracted record schemas.
backend/app/schemas/system.py               Health/readiness response schemas.
backend/app/crawler/base_spider.py          Scrapy spider and page fetching foundation.
backend/app/crawler/playwright_manager.py   Dynamic rendering manager.
backend/app/extraction/regex_extractor.py   Tier 1 deterministic extraction.
backend/app/extraction/spacy_extractor.py   Tier 2 NLP entity extraction.
backend/app/extraction/distilbert_extractor.py Tier 3 HF QA/classifier extraction.
backend/app/extraction/llm_extractor.py     Tier 4 OpenAI LLM extraction.
backend/app/extraction/fallback_chain.py    Confidence-gated fallback orchestration.
backend/app/ml/train_distilbert.py          DistilBERT fine-tune template, to add from section 8.
backend/app/rl/crawl_policy.py              PPO crawl policy template, to add from section 8.
backend/app/pipeline/messages.py            Kafka message contracts.
backend/app/pipeline/kafka_producer.py      Async producer abstraction.
backend/app/pipeline/scheduler.py           Celery task entry points.
backend/app/storage/records.py              Postgres/ES/MinIO writer target module.
backend/alembic/versions/*.py               Migration examples.
backend/scripts/check_system.py             CLI readiness checker for working/degraded/broken status.
src/App.tsx                                 Operations console shell.
src/components/IntelligenceFeed.tsx         Record feed.
src/components/JobManager.tsx               Job list and cancel controls.
src/components/AiInstructionBuilder.tsx     NL job creation flow.
src/components/SystemHealthStrip.tsx        Dependency health strip.
src/components/diagnostics/ReadinessMatrix.tsx Working/degraded/broken capability UI.
src/pages/*.tsx                             Future full-screen route targets for the 9 UX screens.
backend/Dockerfile                          API/worker image.
docker-compose.yml                          Local Postgres, Redis, Kafka, ES, API, workers.
.github/workflows/ci.yml                    Lint, test, build, Docker smoke checks.
.github/workflows/deploy.yml                Deployment pipeline.
deploy/fly/fly.toml                         Fly.io manifest template.
```

## 4. Data Models And Schemas

Pydantic model template:

```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, AnyHttpUrl, Field

class JobCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    instruction: str = Field(min_length=10, max_length=4000)
    seed_urls: list[AnyHttpUrl]
    max_pages: int = Field(default=100, ge=1, le=10000)

class PageResponse(BaseModel):
    id: UUID
    job_id: UUID
    url: str
    status: str
    http_status: int | None
    fetched_at: datetime | None

class RecordResponse(BaseModel):
    id: UUID
    job_id: UUID
    page_id: UUID
    url: str
    data: dict
    confidence: float

class AlertResponse(BaseModel):
    id: UUID
    severity: str
    title: str
    status: str
    context: dict

class UserResponse(BaseModel):
    id: UUID
    email: str
    role: str
```

SQLAlchemy models already exist for `Job`, `Page`, and `ExtractedData`. Add `Alert` and `User` tables in the next migration:

```python
def upgrade() -> None:
    op.create_table("users", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("email", sa.String(320), unique=True, nullable=False), sa.Column("role", sa.String(64), nullable=False))
    op.create_table("alerts", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("severity", sa.String(32), nullable=False), sa.Column("title", sa.String(255), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("context", postgresql.JSONB(), nullable=False))
```

## 5. API Spec

REST endpoints:

```text
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/jobs
GET    /api/v1/jobs?limit=50&offset=0
GET    /api/v1/jobs/{job_id}
POST   /api/v1/jobs/{job_id}/cancel
GET    /api/v1/data?job_id=&q=&limit=50
POST   /api/v1/ai-engine/schemas
GET    /api/v1/alerts
POST   /api/v1/alerts/{alert_id}/ack
GET    /api/v1/system/health
GET    /api/v1/system/readiness
GET    /metrics
```

Auth: RS256 access JWT expires in 15 minutes; refresh JWT expires in 7 days. Store private/public keys as Docker secrets or Fly secrets: `JWT_PRIVATE_KEY_PEM`, `JWT_PUBLIC_KEY_PEM`.

Example create job:

```json
{
  "name": "Monitor supplier pricing",
  "instruction": "Extract product names, prices, stock status, and change alerts.",
  "seed_urls": ["https://example.com/products"],
  "render_javascript": true,
  "max_pages": 100
}
```

Response:

```json
{
  "id": "9a6229a1-7390-4dac-9b4d-f39b51ec9f2e",
  "name": "Monitor supplier pricing",
  "status": "running",
  "scheduler_task_id": "celery-task-id"
}
```

GraphQL schema types are scaffolded in `backend/app/graphql/schema.py`: `JobNode`, `RecordNode`, `AlertNode`, `Query.jobs`, `Query.records`, `Mutation.createJob`, and `Subscription.jobEvents`.

## 6. Crawler Design

Decision pseudocode:

```python
def choose_fetcher(url, analyzer):
    signals = analyzer.inspect(url)
    if signals.robots_disallowed:
        return Flag("blocked_by_robots")
    if signals.captcha_detected:
        return Flag("captcha_required")
    if signals.requires_js or signals.dom_changes_after_load or signals.spa_framework_detected:
        return PlaywrightFetcher(profile=rotating_browser_profile())
    return ScrapyFetcher(headers=rotating_http_profile())
```

Heuristics: HTML size under 5 KB with large JS bundles, `__NEXT_DATA__`, `window.__NUXT__`, empty product containers, delayed network calls, login walls, anti-bot fingerprints, and CAPTCHA keywords trigger Playwright or manual review flags. Proxy rotation uses per-domain pools with sticky sessions for authenticated flows, backoff on 403/429, and quarantine on repeated TLS or CAPTCHA failures. UA/TLS rotation is profile-based so header order, viewport, locale, timezone, and TLS fingerprint stay internally consistent. Robots are fetched, cached by host, honored by default, and logged with override decisions only for approved enterprise allowlists.

## 7. Extraction Fallback Chain

Tiers:

```text
Tier 1 Regex/rules: prices, dates, emails, SKUs, known labels. Threshold >=0.90.
Tier 2 spaCy: NER, dependency windows, noun chunks. Threshold >=0.84.
Tier 3 DistilBERT: field QA or token classification. Threshold >=0.78.
Tier 4 Hosted LLM: JSON-only extraction with schema and page evidence. Threshold >=0.72.
Tier 5 Ollama local: private mode fallback, no external network. Threshold >=0.68.
```

Confidence scoring:

```python
confidence = 0.45 * model_score + 0.2 * schema_validity + 0.15 * evidence_density + 0.1 * source_agreement + 0.1 * freshness
fallback = confidence < tier_threshold or required_fields_missing
```

LLM prompt template:

```text
You extract structured intelligence from web text.
Return only JSON matching this schema: {schema}
Instruction: {instruction}
Text: {page_text}
Include "_evidence" with short snippets and "_confidence" from 0 to 1.
```

Ollama private mode: set `OLLAMA_BASE_URL=http://ollama:11434` in `.env` or Docker secret and route Tier 5 requests to `/api/generate` with `format=json`.

## 8. ML And RL

Dataset JSONL:

```json
{"url":"https://example.com/a","text":"Widget A costs $19","fields":{"product":"Widget A","price":"$19"},"spans":[{"field":"price","start":15,"end":18}]}
```

DistilBERT hyperparameters: `distilbert-base-uncased`, max length 384, doc stride 96, batch size 16, learning rate `3e-5`, epochs 3, warmup 10%, weight decay 0.01, early stop on validation F1. Evaluation reports micro/macro F1 and per-field F1; acceptance target is F1 >= 0.893.

RL crawl policy:

```text
State: domain reputation, depth, response status, latency, content novelty, extraction yield, robots state, CAPTCHA flag.
Action: continue, pause, switch proxy, switch render mode, lower concurrency, prioritize URL, stop domain.
Reward: +yield +novelty -latency -errors -CAPTCHA -robots_violation -duplicate_content.
```

Offline training replays historical crawl traces into PPO. Online training writes decisions in shadow mode first, then gates real actions behind domain-level safety limits.

## 9. Streaming And Storage

Kafka topics:

```text
webintel.jobs.created
webintel.pages.discovered
webintel.pages.raw
webintel.records.extracted
webintel.alerts.created
webintel.system.events
```

Consumer groups: `crawl-workers`, `extraction-workers`, `storage-writers`, `alert-evaluators`, `indexers`. Storage worker writes normalized jobs/pages/records to Postgres, searchable record documents to Elasticsearch, entity relationships to Neo4j, and raw HTML/screenshots to MinIO. Change detection computes canonical text, SimHash, DOM-path keyed field hashes, and JSON Patch diffs; alerts fire when semantic or configured field changes cross thresholds.

## 10. Frontend UI/UX

Screens:

```text
Intelligence Feed: FeedToolbar, RecordCard, ConfidenceBadge, DiffDrawer; state {records, filters, selectedRecord}; query records; subscription recordCreated; keyboard list navigation and visible focus.
Job Manager: JobTable, JobStatusPill, JobTimeline, CancelJobDialog; state {jobs, selectedJob}; query jobs/job; subscription jobEvents; table headers and aria-live status changes.
AI Instruction Builder: InstructionTextarea, SeedUrlInput, SchemaPreview, RunButton; state {instruction, seedUrls, schema}; mutation createJob/generateSchema; labels and validation text.
Category Dashboards: MetricTiles, TrendChart, CategoryTable; state {category, range}; query categoryMetrics; color-independent chart labels.
Graph Explorer: GraphCanvas, NodeInspector, RelationshipFilter; state {nodes, edges, selected}; query graphNeighbors; SVG roles, zoom controls, non-pointer alternatives.
Search: SearchBox, Facets, ResultList, SavedSearchMenu; state {q, filters, results}; query searchRecords; labelled inputs and result count announcements.
Alerts: AlertQueue, SeverityFilter, AckButton, AlertDetail; state {alerts, selected}; query alerts; mutation ackAlert; clear severity text plus color.
Observability: ReadinessMatrix, ServiceMap, LatencyChart, LogStream; state {checks, traces, metrics}; query readiness; aria-live failures.
Settings: ApiKeySecrets, CrawlPolicyForm, PrivacyModeToggle, TeamMembers; state {settings, dirty}; mutations updateSettings; confirmation for risky controls.
```

Component template:

```tsx
export interface ScreenProps<TState> {
  state: TState;
  onRefresh: () => Promise<void>;
}

export function PanelShell({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="rounded-md border border-border bg-white p-4 shadow-panel"><h2 className="text-lg font-black">{title}</h2>{children}</section>;
}
```

## 11. Observability And Security

Prometheus metrics: `http_requests_total`, `http_request_duration_seconds`, `crawl_pages_total`, `crawl_fetch_duration_seconds`, `extraction_tier_total`, `extraction_confidence`, `kafka_consumer_lag`, `job_duration_seconds`, `captcha_detected_total`, `robots_blocked_total`, `llm_invocations_total`. OpenTelemetry hooks wrap API requests, Celery tasks, Kafka publish/consume, crawler fetches, and extraction tiers. Logs are JSON with `timestamp`, `level`, `event`, `trace_id`, `job_id`, `page_id`, `domain`, and `duration_ms`.

Security: JWT RS256, per-route rate limits, URL allow/deny validation, SSRF protection for private IP ranges, schema validation for every extraction payload, Docker/Fly secrets for credentials, no secrets in Git, GDPR private mode that disables hosted LLM calls and stores raw HTML with TTL. Differential privacy aggregation adds Laplace noise for shared analytics and suppresses small cohorts.

## 12. CI/CD And Deploy

Commands:

```bash
npm install
npm run build
cd backend && pytest
npm run docker:up
npm run check:system
```

GitHub Actions should run Python tests, TypeScript build, Docker image build, and a smoke call to `/health`. Deployment builds immutable images, applies migrations, deploys API and workers, runs `/api/v1/system/readiness`, and rolls back if health is not `ok` or if API P95 exceeds the SLO for two consecutive windows.

## 13. Tests And Benchmarks

Unit: schema factory, regex extractor, fallback thresholds, URL validation, auth token rotation. Integration: create job to queued pages, Celery enqueue, Kafka message serialization, Postgres writes, ES indexing. E2E: Playwright UI creates job and verifies dashboard update. Locust: create/list/get jobs, data feed polling, schema generation under realistic analyst traffic. Extraction benchmark script loads JSONL, runs fallback chain, computes exact/partial per-field F1, and fails below 0.893. API P95 target is under 120 ms for read endpoints excluding crawler and ML work.

## 14. Acceptance Criteria

```text
M1 Local boot: docker compose starts API, DB, Redis, Kafka, ES; /health returns ok; readiness matrix lists working/degraded/broken.
M2 Job flow: create job -> run crawler -> record appears in Postgres and dashboard within 30 seconds for static fixture.
M3 Extraction: benchmark F1 >= 0.893 on locked test set; LLM invocation rate <= 5% after rule/spaCy/DistilBERT tuning.
M4 Storage: raw HTML in MinIO, records in Postgres and Elasticsearch, relationships in Neo4j, all linked by job_id/page_id.
M5 UX: all 9 screens render responsive, keyboard navigable, and pass axe critical checks.
M6 Security: JWT RS256 15m/7d, rate limits, SSRF guard, secrets outside Git, private mode disables hosted LLMs.
M7 Observability: metrics, traces, JSON logs, readiness checks, and alerting dashboard operational.
M8 Deploy: CI green, Fly deployment healthy, rollback tested.
```

## 12-Week Prioritized Task Board

| Week | Owner | Deliverables | Acceptance |
| --- | --- | --- | --- |
| 1 | Backend | Auth, URL validation, readiness matrix | Health/readiness passes locally |
| 2 | Backend | Job/page/record models and migrations | CRUD tests pass |
| 3 | Crawler | Site analyzer, Scrapy/Playwright routing | Static and dynamic fixtures crawled |
| 4 | Pipeline | Kafka topics, Celery tasks, storage worker | Page message persists record |
| 5 | ML | Regex/spaCy fallback tuning | F1 baseline report generated |
| 6 | ML | DistilBERT fine-tune/eval scripts | F1 >= 0.893 on test set |
| 7 | AI | Hosted LLM and Ollama private mode | LLM rate <= 5% on benchmark |
| 8 | Frontend | Feed, Jobs, Instruction Builder | Create job from UI works |
| 9 | Frontend | Dashboards, Search, Alerts | Queries and subscriptions wired |
| 10 | Graph | Neo4j writer and D3 explorer | Entity graph opens from record |
| 11 | SRE | Metrics, traces, Locust, CI/CD | API P95 < 120 ms reads |
| 12 | Product | Hardening, docs, release checklist | End-to-end demo accepted |

## Risk Register

Anti-bot blocking may reduce crawl yield; mitigate with robots-first design, domain throttles, proxy reputation, and CAPTCHA flagging. Extraction drift may lower F1; mitigate with benchmark gates, active learning, and per-field confidence. LLM cost or privacy exposure may grow; mitigate with strict fallback thresholds, private mode, and invocation budget alerts. Distributed debugging may slow operations; mitigate with trace IDs across API, Kafka, Celery, and crawler logs. Legal/compliance risk may vary by target site; mitigate with allowlists, robots handling, data TTLs, and audit logs.
