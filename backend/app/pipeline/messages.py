from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class RawPageMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    url: HttpUrl
    final_url: HttpUrl | None = None
    domain: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    http_status: int | None = None
    content_type: str | None = None
    title: str | None = None
    raw_html: str
    raw_html_sha256: str
    source: str
    render_strategy: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrawlRequest(BaseModel):
    job_id: UUID
    url: HttpUrl
    render_javascript: bool = False
    depth: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractedDataMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    page_id: UUID | None = None
    url: HttpUrl | str
    raw_html_sha256: str | None = None
    schema_name: str
    extractor_name: str
    confidence: float
    data: dict[str, Any]
    errors: list[str] = Field(default_factory=list)
