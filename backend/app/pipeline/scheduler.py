import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
import structlog
from celery import Celery, group
from celery.schedules import crontab
from sqlalchemy import select

from app.config import get_settings
from app.crawler.playwright_manager import PlaywrightManager
from app.db.session import AsyncSessionLocal
from app.models.job import Job, JobStatus
from app.models.page import Page, PageStatus
from app.pipeline.kafka_producer import KafkaRawPageProducer

settings = get_settings()
_redbeat_available = False
try:
    import redbeat  # noqa: F401

    _redbeat_available = True
except Exception:
    _redbeat_available = False
logger = structlog.get_logger(__name__)


def configure_worker_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.app_debug else logging.INFO,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.app_debug else logging.INFO
        ),
        cache_logger_on_first_use=True,
    )


configure_worker_logging()

celery_app = Celery(
    "webintel",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.pipeline.scheduler"],
)

celery_config = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": settings.celery_timezone,
    "enable_utc": True,
    "task_track_started": True,
    "task_acks_late": True,
    "worker_prefetch_multiplier": 1,
    "broker_connection_retry_on_startup": True,
    "beat_schedule": {
        "webintel-pipeline-heartbeat": {
            "task": "app.pipeline.scheduler.pipeline_heartbeat",
            "schedule": crontab(minute="*/5"),
        },
    },
}
if _redbeat_available:
    celery_config["beat_scheduler"] = "redbeat.RedBeatScheduler"
    celery_config["redbeat_redis_url"] = settings.redbeat_redis_url

celery_app.conf.update(**celery_config)


def _run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("Celery tasks must run in a worker process without an active event loop")


@celery_app.task(name="app.pipeline.scheduler.pipeline_heartbeat")
def pipeline_heartbeat() -> dict[str, str]:
    payload = {
        "status": "ok",
        "service": "webintel-celery",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("pipeline_heartbeat", **payload)
    return payload


@celery_app.task(name="app.pipeline.scheduler.enqueue_crawl_job")
def enqueue_crawl_job(
    job_id: str,
    seed_urls: list[str],
    render_javascript: bool = False,
    metadata: dict[str, Any] | None = None,
    page_ids: list[str] | None = None,
) -> dict[str, Any]:
    parsed_job_id = str(UUID(job_id))
    crawl_metadata = metadata or {}
    signatures = [
        crawl_url.s(
            job_id=parsed_job_id,
            url=url,
            render_javascript=render_javascript,
            metadata={**crawl_metadata, "seed_index": index, "page_id": page_ids[index] if page_ids else None},
        )
        for index, url in enumerate(seed_urls)
    ]
    result = group(signatures).apply_async()
    logger.info(
        "crawl_job_enqueued",
        job_id=parsed_job_id,
        url_count=len(seed_urls),
        render_javascript=render_javascript,
        group_id=result.id,
    )
    return {
        "job_id": parsed_job_id,
        "url_count": len(seed_urls),
        "render_javascript": render_javascript,
        "group_id": result.id,
    }


@celery_app.task(
    name="app.pipeline.scheduler.crawl_url",
    autoretry_for=(TimeoutError, ConnectionError, httpx.HTTPError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def crawl_url(
    job_id: str,
    url: str,
    render_javascript: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed_job_id = UUID(job_id)
    if render_javascript:
        result = _run_async(_crawl_with_playwright(parsed_job_id, url, metadata or {}))
    else:
        result = _run_async(_crawl_with_http(parsed_job_id, url, metadata or {}))
    persisted = _run_async(_persist_crawl_result(parsed_job_id, result, metadata or {}))
    logger.info(
        "crawl_url_completed",
        job_id=job_id,
        url=url,
        render_javascript=render_javascript,
        html_sha256=result["raw_html_sha256"],
    )
    return {**result, "persisted": persisted}


async def _crawl_with_playwright(job_id: UUID, url: str, metadata: dict[str, Any]) -> dict[str, Any]:
    async with PlaywrightManager() as manager:
        rendered = await manager.render_page(url)
        async with KafkaRawPageProducer() as producer:
            message = await producer.publish_html(
                job_id=job_id,
                url=url,
                final_url=rendered.final_url,
                domain=rendered.domain,
                raw_html=rendered.html,
                http_status=rendered.http_status,
                content_type=rendered.content_type,
                title=rendered.title,
                source="celery",
                render_strategy="playwright",
                metadata={**metadata, **rendered.metadata, "fetched_at": rendered.fetched_at.isoformat()},
            )
            return message.model_dump(mode="json")


async def _crawl_with_http(job_id: UUID, url: str, metadata: dict[str, Any]) -> dict[str, Any]:
    timeout = httpx.Timeout(settings.crawler_request_timeout_seconds)
    headers = {"User-Agent": settings.crawler_user_agent}
    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    final_url = str(response.url)
    domain = urlparse(final_url).netloc.lower()
    content_type = response.headers.get("content-type")
    html = response.text
    async with KafkaRawPageProducer() as producer:
        message = await producer.publish_html(
            job_id=job_id,
            url=url,
            final_url=final_url,
            domain=domain,
            raw_html=html,
            http_status=response.status_code,
            content_type=content_type,
            title=None,
            source="celery",
            render_strategy="http",
            metadata={
                **metadata,
                "elapsed_seconds": response.elapsed.total_seconds(),
                "response_headers": dict(response.headers),
            },
        )
        return message.model_dump(mode="json")


async def _persist_crawl_result(job_id: UUID, raw_page_payload: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    page_id = metadata.get("page_id")
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            logger.warning("crawl_persist_missing_job", job_id=str(job_id))
            return {"status": "missing_job"}

        page: Page | None = None
        if page_id:
            page_result = await session.execute(select(Page).where(Page.id == UUID(str(page_id))))
            page = page_result.scalar_one_or_none()
        if page is None:
            page_result = await session.execute(select(Page).where(Page.job_id == job_id, Page.url == str(raw_page_payload["url"])))
            page = page_result.scalar_one_or_none()
        if page is None:
            page = Page(
                job_id=job_id,
                url=str(raw_page_payload["url"]),
                canonical_url=str(raw_page_payload.get("final_url") or raw_page_payload["url"]),
                domain=str(raw_page_payload.get("domain") or urlparse(str(raw_page_payload["url"])).netloc.lower()),
                status=PageStatus.queued,
                page_metadata={},
            )
            session.add(page)
            await session.flush()

        page.status = PageStatus.fetched
        page.canonical_url = str(raw_page_payload.get("final_url") or page.url)
        page.domain = str(raw_page_payload.get("domain") or page.domain)
        page.http_status = raw_page_payload.get("http_status")
        page.content_type = raw_page_payload.get("content_type")
        page.title = raw_page_payload.get("title")
        page.raw_html_sha256 = raw_page_payload.get("raw_html_sha256")
        page.page_metadata = {**(page.page_metadata or {}), **(raw_page_payload.get("metadata") or {})}
        page.fetched_at = datetime.now(timezone.utc)

        page.status = PageStatus.fetched
        await session.flush()

        counts = await session.execute(select(Page.status).where(Page.job_id == job_id))
        statuses = [row[0] for row in counts.all()]
        job.pages_discovered = max(job.pages_discovered, len(statuses))
        job.status = JobStatus.running

        await session.commit()
        logger.info(
            "crawl_result_persisted",
            job_id=str(job_id),
            page_id=str(page.id),
            html_sha256=page.raw_html_sha256,
        )
        return {"status": "persisted", "page_id": str(page.id)}
