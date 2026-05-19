# System Design

```mermaid
flowchart LR
	UI[React Ops Console] --> API[FastAPI + GraphQL]
	API --> DB[(PostgreSQL)]
	API --> Redis[(Redis/RedBeat)]
	API --> Kafka[(Kafka)]

	Scheduler[Celery Scheduler] --> Crawler[Scrapy / Playwright]
	Crawler --> Kafka
	Kafka --> Extractor[Extraction Workers]
	Extractor --> Storage[Storage Worker]

	Storage --> DB
	Storage --> Search[(Elasticsearch)]
	Storage --> Graph[(Neo4j)]
	Storage --> ObjectStore[(MinIO)]

	API --> Observability[Health/Readiness]
	Observability --> UI
```

# Purpose

WebIntel AI is a distributed web intelligence platform for crawling seed URLs, extracting structured data, persisting it across multiple stores, and visualizing operational status and results.

# How It Works

1. A user creates a job in the operations console or via API.
2. Celery schedules crawl tasks that use Scrapy for static pages or Playwright for dynamic sites.
3. Raw HTML is published to Kafka and processed by extraction workers.
4. The storage worker writes normalized records to PostgreSQL and optional stores like Elasticsearch, Neo4j, and MinIO.
5. The API serves job status, data, and health/readiness to the UI.

# Tech Stack

- Frontend: React 18, TypeScript, Vite, Tailwind, shadcn/ui, Recharts
- Backend: Python 3.11, FastAPI, Strawberry GraphQL, SQLAlchemy
- Workers/Queue: Celery, RedBeat, Kafka
- Storage: PostgreSQL, Elasticsearch, Neo4j, MinIO
- Crawling: Scrapy, Playwright
- ML/NLP (optional): spaCy, Transformers (DistilBERT), Stable-Baselines3

# MIT License

MIT License

Copyright (c) 2026 WebIntel AI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
