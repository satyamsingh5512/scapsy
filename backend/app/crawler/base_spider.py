from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import scrapy
import structlog
from scrapy import Request
from scrapy.http import Response
from twisted.internet.defer import Deferred
from twisted.internet.defer import ensureDeferred

from app.config import get_settings
from app.pipeline.kafka_producer import KafkaRawPageProducer

logger = structlog.get_logger(__name__)


class WebIntelBaseSpider(scrapy.Spider):
    name = "webintel_base"
    custom_settings = {
        "LOG_FORMAT": "%(message)s",
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_FAIL_ON_DATALOSS": False,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 2,
    }

    @classmethod
    def update_settings(cls, settings: Any) -> None:
        super().update_settings(settings)
        app_settings = get_settings()
        settings.set("USER_AGENT", app_settings.crawler_user_agent, priority="spider")
        settings.set("DOWNLOAD_TIMEOUT", app_settings.crawler_request_timeout_seconds, priority="spider")
        settings.set("CONCURRENT_REQUESTS", app_settings.crawler_max_concurrency, priority="spider")

    def __init__(
        self,
        job_id: str,
        seed_urls: str | list[str],
        max_depth: int = 1,
        follow_links: bool = True,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.job_id = UUID(job_id)
        self.start_urls = self._coerce_urls(seed_urls)
        self.max_depth = max_depth
        self.follow_links = follow_links
        self.kafka_producer = KafkaRawPageProducer()

    def start_requests(self) -> Any:
        for url in self.start_urls:
            yield Request(
                url=url,
                callback=self.parse,
                errback=self.handle_error,
                meta={"depth": 0},
                dont_filter=False,
            )

    def parse(self, response: Response) -> Deferred:
        return ensureDeferred(self._parse_response(response))

    async def _parse_response(self, response: Response) -> list[Request]:
        depth = int(response.meta.get("depth", 0))
        final_url = response.url
        html = response.text
        title = self._extract_title(response)
        await self.kafka_producer.publish_html(
            job_id=self.job_id,
            url=response.request.url,
            final_url=final_url,
            domain=urlparse(final_url).netloc.lower(),
            raw_html=html,
            http_status=response.status,
            content_type=response.headers.get("Content-Type", b"").decode("utf-8", errors="replace") or None,
            title=title,
            source="scrapy",
            render_strategy="http",
            metadata={
                "depth": depth,
                "referer": response.request.headers.get("Referer", b"").decode("utf-8", errors="replace") or None,
            },
        )

        if not self.follow_links or depth >= self.max_depth:
            return []

        requests: list[Request] = []
        for href in response.css("a::attr(href)").getall():
            absolute_url = response.urljoin(href)
            if self._should_follow(response.url, absolute_url):
                requests.append(
                    Request(
                        url=absolute_url,
                        callback=self.parse,
                        errback=self.handle_error,
                        meta={"depth": depth + 1},
                    )
                )
        return requests

    def handle_error(self, failure: Any) -> None:
        request = failure.request
        logger.warning(
            "scrapy_request_failed",
            job_id=str(self.job_id),
            url=request.url,
            error=str(failure.value),
        )

    def closed(self, reason: str) -> Deferred:
        logger.info("spider_closed", job_id=str(self.job_id), reason=reason)
        return ensureDeferred(self.kafka_producer.stop())

    def _should_follow(self, source_url: str, target_url: str) -> bool:
        source_domain = urlparse(source_url).netloc.lower()
        target = urlparse(target_url)
        return target.scheme in {"http", "https"} and target.netloc.lower() == source_domain

    def _extract_title(self, response: Response) -> str | None:
        title = response.css("title::text").get()
        if title is None:
            return None
        normalized = " ".join(title.split())
        return normalized or None

    def _coerce_urls(self, seed_urls: str | list[str]) -> list[str]:
        if isinstance(seed_urls, list):
            return seed_urls
        return [url.strip() for url in seed_urls.split(",") if url.strip()]
