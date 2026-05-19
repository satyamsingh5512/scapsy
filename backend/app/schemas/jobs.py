from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.models.job import JobStatus
from app.models.page import PageStatus


class JobCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    seed_urls: list[HttpUrl] = Field(min_length=1)
    instruction: str | None = Field(default=None, max_length=4_000)
    extraction_schema: dict[str, Any] = Field(default_factory=dict)
    crawl_config: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=100)
    max_pages: int = Field(default=100, ge=1, le=100_000)
    render_javascript: bool = False


class JobResponse(BaseModel):
    id: UUID
    name: str
    status: JobStatus
    seed_urls: list[str]
    extraction_schema: dict[str, Any]
    crawl_config: dict[str, Any]
    priority: int
    max_pages: int
    pages_discovered: int
    pages_processed: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobCreateResponse(JobResponse):
    scheduler_task_id: str | None = None


class PageSummaryResponse(BaseModel):
    id: UUID
    job_id: UUID
    url: str
    canonical_url: str | None
    domain: str
    status: PageStatus
    http_status: int | None
    content_type: str | None
    title: str | None
    raw_html_sha256: str | None
    error_message: str | None
    fetched_at: datetime | None
    created_at: datetime
    updated_at: datetime


class JobDetailResponse(JobResponse):
    pages: list[PageSummaryResponse]


class JobListResponse(BaseModel):
    items: list[JobResponse]
    total: int
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class JobCancelResponse(BaseModel):
    id: UUID
    status: JobStatus
    message: str
