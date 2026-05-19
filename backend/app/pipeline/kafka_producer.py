import hashlib
import json
from types import TracebackType
from typing import Any, Self
from uuid import UUID

import structlog
from aiokafka import AIOKafkaProducer
from pydantic import HttpUrl

from app.config import get_settings
from app.pipeline.messages import RawPageMessage

logger = structlog.get_logger(__name__)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


class KafkaRawPageProducer:
    def __init__(self, topic: str | None = None) -> None:
        settings = get_settings()
        self._settings = settings
        self.topic = topic or settings.kafka_raw_pages_topic
        self._producer: AIOKafkaProducer | None = None
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
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._settings.kafka_bootstrap_servers,
            client_id=self._settings.kafka_client_id,
            security_protocol=self._settings.kafka_security_protocol,
            value_serializer=lambda value: json.dumps(value, separators=(",", ":"), default=str).encode("utf-8"),
            key_serializer=lambda value: value.encode("utf-8"),
            acks="all",
            compression_type="gzip",
            enable_idempotence=True,
        )
        await self._producer.start()
        self._started = True
        logger.info("kafka_raw_page_producer_started", topic=self.topic)

    async def stop(self) -> None:
        if not self._started:
            return
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None
        self._started = False
        logger.info("kafka_raw_page_producer_stopped", topic=self.topic)

    async def publish(self, message: RawPageMessage) -> None:
        await self.start()
        payload = message.model_dump(mode="json")
        if self._producer is None:
            raise RuntimeError("Kafka producer did not initialize")
        await self._producer.send_and_wait(
            self.topic,
            key=str(message.job_id),
            value=payload,
        )
        logger.info(
            "raw_page_published",
            topic=self.topic,
            job_id=str(message.job_id),
            url=str(message.url),
            html_sha256=message.raw_html_sha256,
            render_strategy=message.render_strategy,
        )

    async def publish_html(
        self,
        *,
        job_id: UUID,
        url: str | HttpUrl,
        domain: str,
        raw_html: str,
        source: str,
        render_strategy: str,
        final_url: str | HttpUrl | None = None,
        http_status: int | None = None,
        content_type: str | None = None,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RawPageMessage:
        message = RawPageMessage(
            job_id=job_id,
            url=url,
            final_url=final_url,
            domain=domain,
            http_status=http_status,
            content_type=content_type,
            title=title,
            raw_html=raw_html,
            raw_html_sha256=sha256_text(raw_html),
            source=source,
            render_strategy=render_strategy,
            metadata=metadata or {},
        )
        await self.publish(message)
        return message
