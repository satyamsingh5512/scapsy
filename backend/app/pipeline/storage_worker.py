import asyncio
import json
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Self
from uuid import UUID

import structlog
from aiokafka import AIOKafkaConsumer
from sqlalchemy import select

from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.extracted_data import ExtractedData
from app.models.job import Job, JobStatus
from app.models.page import Page, PageStatus
from app.pipeline.messages import ExtractedDataMessage
from app.storage.graph import write_graph
from app.storage.object_store import upload_json
from app.storage.records import write_record
from app.storage.search import index_record

logger = structlog.get_logger(__name__)


class KafkaStorageWorker:
    def __init__(self) -> None:
        settings = get_settings()
        self.extracted_data_topic = settings.kafka_extracted_data_topic
        self._consumer = AIOKafkaConsumer(
            self.extracted_data_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=f"{settings.kafka_extraction_group_id}-storage",
            client_id=f"{settings.kafka_client_id}-storage",
            security_protocol=settings.kafka_security_protocol,
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
            enable_auto_commit=False,
        )
        self._started = False

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.stop()

    async def start(self) -> None:
        if self._started:
            return
        await self._consumer.start()
        self._started = True
        logger.info("kafka_storage_worker_started", topic=self.extracted_data_topic)

    async def stop(self) -> None:
        if not self._started:
            return
        await self._consumer.stop()
        self._started = False
        logger.info("kafka_storage_worker_stopped")

    async def run_forever(self) -> None:
        await self.start()
        try:
            async for record in self._consumer:
                await self.process_record(record.value)
                await self._consumer.commit()
        finally:
            await self.stop()

    async def process_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = ExtractedDataMessage.model_validate(payload)
        async with AsyncSessionLocal() as session:
            page = await _get_page(session, message)
            if page is None:
                logger.warning("storage_missing_page", job_id=str(message.job_id), url=str(message.url))
                return {"status": "missing_page"}

            previous = await _get_previous_record(session, page.id, message.schema_name)
            storage = await write_record(
                session,
                page_id=page.id,
                data=message.data,
                confidence=message.confidence,
                extractor_name=message.extractor_name,
                schema_name=message.schema_name,
                previous_data=previous.data if previous else None,
            )

            page.status = PageStatus.extracted
            if message.raw_html_sha256:
                page.raw_html_sha256 = message.raw_html_sha256

            await _update_job_status(session, message.job_id)
            await _create_alert_if_needed(session, message, storage.change)
            await session.commit()

            await _sync_external_stores(message, str(storage.record_id), storage.change)
            logger.info(
                "storage_record_written",
                job_id=str(message.job_id),
                page_id=str(page.id),
                record_id=str(storage.record_id),
                change=storage.change.get("type"),
            )
            return {"status": "persisted", "record_id": str(storage.record_id)}


async def _get_page(session, message: ExtractedDataMessage) -> Page | None:
    if message.page_id:
        result = await session.execute(select(Page).where(Page.id == message.page_id))
        page = result.scalar_one_or_none()
        if page:
            return page
    result = await session.execute(
        select(Page).where(Page.job_id == message.job_id, Page.url == str(message.url))
    )
    return result.scalar_one_or_none()


async def _get_previous_record(session, page_id: UUID, schema_name: str) -> ExtractedData | None:
    result = await session.execute(
        select(ExtractedData)
        .where(ExtractedData.page_id == page_id, ExtractedData.schema_name == schema_name)
        .order_by(ExtractedData.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _update_job_status(session, job_id: UUID) -> None:
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        return

    counts = await session.execute(select(Page.status).where(Page.job_id == job_id))
    statuses = [row[0] for row in counts.all()]
    processed = sum(1 for status in statuses if status in {PageStatus.extracted, PageStatus.failed, PageStatus.skipped})
    failed = sum(1 for status in statuses if status == PageStatus.failed)
    job.pages_processed = processed
    job.pages_discovered = max(job.pages_discovered, len(statuses))
    if processed >= len(statuses) and statuses:
        job.status = JobStatus.failed if failed == len(statuses) else JobStatus.completed
        job.completed_at = job.completed_at or datetime.now(timezone.utc)
    else:
        job.status = JobStatus.running


async def _create_alert_if_needed(session, message: ExtractedDataMessage, change: dict[str, Any]) -> None:
    change_type = change.get("type")
    if change_type not in {"created", "changed"}:
        return

    severity = AlertSeverity.info if change_type == "created" else AlertSeverity.warning
    title = "Extraction change detected" if change_type == "changed" else "New extraction record"
    alert = Alert(
        severity=severity,
        title=title,
        status=AlertStatus.open,
        context={
            "job_id": str(message.job_id),
            "page_id": str(message.page_id) if message.page_id else None,
            "url": str(message.url),
            "schema_name": message.schema_name,
            "changed_fields": change.get("changed_fields", []),
        },
        detail="Automated change detection from storage worker.",
    )
    session.add(alert)


async def _sync_external_stores(message: ExtractedDataMessage, record_id: str, change: dict[str, Any]) -> None:
    settings = get_settings()
    payload = {
        "job_id": str(message.job_id),
        "page_id": str(message.page_id) if message.page_id else None,
        "url": str(message.url),
        "schema_name": message.schema_name,
        "extractor_name": message.extractor_name,
        "confidence": message.confidence,
        "data": message.data,
        "change": change,
    }

    try:
        await index_record(
            record_id=record_id,
            job_id=str(message.job_id),
            page_id=str(message.page_id) if message.page_id else None,
            url=str(message.url),
            schema_name=message.schema_name,
            extractor_name=message.extractor_name,
            confidence=message.confidence,
            data=message.data,
            change=change,
        )
    except Exception as exc:
        logger.warning("storage_elasticsearch_failed", error=str(exc))

    try:
        await write_graph(
            job_id=str(message.job_id),
            page_id=str(message.page_id) if message.page_id else None,
            url=str(message.url),
            schema_name=message.schema_name,
            record_id=record_id,
            data=message.data,
        )
    except Exception as exc:
        logger.warning("storage_neo4j_failed", error=str(exc))

    try:
        object_name = f"{message.job_id}/{record_id}.json"
        await asyncio.to_thread(upload_json, settings.minio_record_bucket, object_name, payload)
    except Exception as exc:
        logger.warning("storage_minio_failed", error=str(exc))


def run_storage_worker() -> None:
    async def _run() -> None:
        async with KafkaStorageWorker() as worker:
            await worker.run_forever()

    asyncio.run(_run())


if __name__ == "__main__":
    run_storage_worker()
