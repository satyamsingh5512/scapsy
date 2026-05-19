from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlparse

import structlog
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RenderedPage:
    url: str
    final_url: str
    domain: str
    html: str
    title: str | None
    http_status: int | None
    content_type: str | None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class PlaywrightManager:
    def __init__(self) -> None:
        settings = get_settings()
        self.headless = settings.playwright_headless
        self.navigation_timeout_ms = settings.playwright_navigation_timeout_ms
        self.block_resource_types = set(settings.playwright_block_resource_types)
        self.user_agent = settings.crawler_user_agent
        self._playwright: Any | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def start(self) -> None:
        if self._browser is not None:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(user_agent=self.user_agent)
        await self._context.route("**/*", self._route_request)
        logger.info("playwright_started", headless=self.headless)

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        logger.info("playwright_stopped")

    async def render_page(self, url: str, wait_until: str = "networkidle") -> RenderedPage:
        await self.start()
        if self._context is None:
            raise RuntimeError("Playwright context did not initialize")

        page: Page = await self._context.new_page()
        response = None
        try:
            response = await page.goto(
                url,
                wait_until=wait_until,
                timeout=self.navigation_timeout_ms,
            )
            html = await page.content()
            title = await page.title()
            final_url = page.url
            headers = response.headers if response is not None else {}
            result = RenderedPage(
                url=url,
                final_url=final_url,
                domain=urlparse(final_url).netloc.lower(),
                html=html,
                title=title or None,
                http_status=response.status if response is not None else None,
                content_type=headers.get("content-type"),
                metadata={
                    "wait_until": wait_until,
                    "blocked_resource_types": sorted(self.block_resource_types),
                },
            )
            logger.info(
                "page_rendered",
                url=url,
                final_url=final_url,
                status=result.http_status,
                html_bytes=len(html.encode("utf-8", errors="replace")),
            )
            return result
        finally:
            await page.close()

    async def _route_request(self, route: Any) -> None:
        request = route.request
        if request.resource_type in self.block_resource_types:
            await route.abort()
            return
        await route.continue_()
