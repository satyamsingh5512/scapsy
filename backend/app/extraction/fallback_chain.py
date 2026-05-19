import asyncio
import json
from collections.abc import Iterable
from types import TracebackType
from typing import Any, Self
from uuid import UUID

import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import select

from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.extraction.contracts import ExtractionContext, ExtractionResult, ExtractionSchema, score_field_coverage
from app.extraction.distilbert_extractor import DistilBertExtractor
from app.extraction.llm_extractor import LlmExtractor
from app.extraction.regex_extractor import RegexHeuristicExtractor
from app.extraction.spacy_extractor import SpacyNerExtractor
from app.extraction.schema_factory import schema_from_job_payload
from app.models.job import Job
from app.models.page import Page
from app.pipeline.messages import RawPageMessage

logger = structlog.get_logger(__name__)


class ExtractionFallbackChain:
    def __init__(
        self,
        extractors: Iterable[Any] | None = None,
        confidence_threshold: float | None = None,
    ) -> None:
        settings = get_settings()
        self.confidence_threshold = confidence_threshold or settings.extraction_confidence_threshold
        self.extractors = list(
            extractors
            or [
                RegexHeuristicExtractor(),
                SpacyNerExtractor(),
                DistilBertExtractor(),
                LlmExtractor(),
            ]
        )

    async def extract(self, context: ExtractionContext, schema: ExtractionSchema) -> ExtractionResult:
        aggregate = ExtractionResult(extractor_name="fallback_chain", schema_name=schema.name)
        required_names = schema.required_field_names()

        for extractor in self.extractors:
            result = await extractor.extract(context, schema)
            aggregate = aggregate.merge(result)
            aggregate.extractor_name = "fallback_chain"
            aggregate.confidence = self._score_result(aggregate, required_names)
            logger.info(
                "extractor_tier_completed",
                extractor=result.extractor_name,
                schema=schema.name,
                tier_confidence=result.confidence,
                aggregate_confidence=aggregate.confidence,
                fields=list(result.fields.keys()),
                errors=result.errors,
            )
            if self._is_high_confidence(aggregate, required_names):
                break

        return aggregate

    def _is_high_confidence(self, result: ExtractionResult, required_names: set[str]) -> bool:
        if result.confidence < self.confidence_threshold:
            return False
        return required_names.issubset(result.fields.keys())

    def _score_result(self, result: ExtractionResult, required_names: set[str]) -> float:
        base = score_field_coverage(result.fields, result.schema_name)
        if not required_names:
            return base
        required_coverage = len(required_names.intersection(result.fields.keys())) / len(required_names)
        return min(1.0, round((base * 0.7) + (required_coverage * 0.3), 4))


class KafkaExtractionWorker:
    def __init__(self) -> None:
        settings = get_settings()
        self.raw_pages_topic = settings.kafka_raw_pages_topic
        self.extracted_data_topic = settings.kafka_extracted_data_topic
        self._consumer = AIOKafkaConsumer(
            self.raw_pages_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_extraction_group_id,
            client_id=f"{settings.kafka_client_id}-extractor",
            security_protocol=settings.kafka_security_protocol,
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
            enable_auto_commit=False,
        )
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            client_id=f"{settings.kafka_client_id}-extracted-data",
            security_protocol=settings.kafka_security_protocol,
            value_serializer=lambda value: json.dumps(value, separators=(",", ":"), default=str).encode("utf-8"),
            key_serializer=lambda value: value.encode("utf-8"),
            acks="all",
            compression_type="gzip",
            enable_idempotence=True,
        )
        self.chain = ExtractionFallbackChain()
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
        await self._producer.start()
        self._started = True
        logger.info(
            "kafka_extraction_worker_started",
            raw_pages_topic=self.raw_pages_topic,
            extracted_data_topic=self.extracted_data_topic,
        )

    async def stop(self) -> None:
        if not self._started:
            return
        await self._consumer.stop()
        await self._producer.stop()
        self._started = False
        logger.info("kafka_extraction_worker_stopped")

    async def run_forever(self) -> None:
        await self.start()
        try:
            async for record in self._consumer:
                await self.process_record(record.value)
                await self._consumer.commit()
        finally:
            await self.stop()

    async def process_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw_page = RawPageMessage.model_validate(payload)
        schema, page_id = await self._load_schema_and_page(raw_page)
        if schema is None:
            return {"status": "missing_job", "job_id": str(raw_page.job_id)}
        context = ExtractionContext(
            url=str(raw_page.final_url or raw_page.url),
            html=raw_page.raw_html,
            title=raw_page.title,
            metadata=raw_page.metadata,
        )
        result = await self.chain.extract(context, schema)
        output = {
            "job_id": str(raw_page.job_id),
            "page_id": str(page_id) if page_id else None,
            "url": str(raw_page.final_url or raw_page.url),
            "raw_html_sha256": raw_page.raw_html_sha256,
            "schema_name": schema.name,
            "extractor_name": result.extractor_name,
            "confidence": result.confidence,
            "data": result.data,
            "fields": {name: field.model_dump(mode="json") for name, field in result.fields.items()},
            "errors": result.errors,
        }
        await self._producer.send_and_wait(
            self.extracted_data_topic,
            key=str(raw_page.job_id),
            value=output,
        )
        logger.info(
            "extracted_data_published",
            job_id=str(raw_page.job_id),
            url=output["url"],
            confidence=result.confidence,
            fields=list(result.fields.keys()),
        )
        return output

    async def _load_schema_and_page(self, raw_page: RawPageMessage) -> tuple[ExtractionSchema | None, UUID | None]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Job).where(Job.id == raw_page.job_id))
            job = result.scalar_one_or_none()
            if job is None:
                logger.warning("extraction_missing_job", job_id=str(raw_page.job_id))
                return None, None
            page_id = raw_page.metadata.get("page_id") if isinstance(raw_page.metadata, dict) else None
            page = None
            if page_id:
                page_result = await session.execute(select(Page).where(Page.id == UUID(str(page_id))))
                page = page_result.scalar_one_or_none()
            if page is None:
                page_result = await session.execute(
                    select(Page).where(Page.job_id == raw_page.job_id, Page.url == str(raw_page.url))
                )
                page = page_result.scalar_one_or_none()
            return schema_from_job_payload(job.extraction_schema, job.crawl_config.get("instruction")), page.id if page else None


def run_extraction_worker() -> None:
    async def _run() -> None:
        async with KafkaExtractionWorker() as worker:
            await worker.run_forever()

    asyncio.run(_run())
