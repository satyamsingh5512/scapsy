from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from elasticsearch import AsyncElasticsearch

from app.config import get_settings


async def index_record(
    *,
    record_id: str,
    job_id: str,
    page_id: str | None,
    url: str,
    schema_name: str,
    extractor_name: str,
    confidence: float,
    data: dict[str, Any],
    change: dict[str, Any],
) -> None:
    settings = get_settings()
    client = AsyncElasticsearch(str(settings.elasticsearch_url))
    try:
        await client.index(
            index=settings.elasticsearch_index,
            id=record_id,
            document={
                "record_id": record_id,
                "job_id": job_id,
                "page_id": page_id,
                "url": url,
                "schema_name": schema_name,
                "extractor_name": extractor_name,
                "confidence": confidence,
                "data": data,
                "change": change,
                "indexed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    finally:
        await client.close()
