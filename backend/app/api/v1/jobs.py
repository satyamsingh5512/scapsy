from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

import structlog
from celery.exceptions import CeleryError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.extraction.schema_factory import default_schema
from app.models.job import Job, JobStatus
from app.models.page import Page, PageStatus
from app.pipeline.scheduler import enqueue_crawl_job
from app.schemas.jobs import (
    JobCancelResponse,
    JobCreateRequest,
    JobCreateResponse,
    JobDetailResponse,
    JobListResponse,
    JobResponse,
    PageSummaryResponse,
)
from app.security.dependencies import require_auth

router = APIRouter()
logger = structlog.get_logger(__name__)
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    payload: JobCreateRequest,
    session: DbSession,
    _user=Depends(require_auth),
) -> JobCreateResponse:
    schema_payload = payload.extraction_schema or default_schema(payload.instruction).model_dump(mode="json")
    job = Job(
        name=payload.name,
        status=JobStatus.pending,
        seed_urls=[str(url) for url in payload.seed_urls],
        extraction_schema=schema_payload,
        crawl_config={
            **payload.crawl_config,
            "instruction": payload.instruction,
            "render_javascript": payload.render_javascript,
        },
        priority=payload.priority,
        max_pages=payload.max_pages,
        pages_discovered=len(payload.seed_urls),
    )
    session.add(job)
    await session.flush()

    pages = [
        Page(
            job_id=job.id,
            url=str(url),
            canonical_url=None,
            domain=urlparse(str(url)).netloc.lower(),
            status=PageStatus.queued,
            page_metadata={"seed_index": index},
        )
        for index, url in enumerate(payload.seed_urls)
    ]
    session.add_all(pages)
    await session.commit()
    await session.refresh(job)
    for page in pages:
        await session.refresh(page)

    try:
        task = enqueue_crawl_job.delay(
            job_id=str(job.id),
            seed_urls=job.seed_urls,
            render_javascript=payload.render_javascript,
            metadata={"api_job_id": str(job.id)},
            page_ids=[str(page.id) for page in pages],
        )
    except CeleryError as exc:
        job.status = JobStatus.failed
        job.error_message = f"Failed to enqueue crawl job: {exc}"
        await session.commit()
        logger.warning("job_enqueue_failed", job_id=str(job.id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to enqueue crawl job. Check Celery broker connectivity.",
        ) from exc

    job.status = JobStatus.running
    job.started_at = datetime.now(timezone.utc)
    job.crawl_config = {**job.crawl_config, "scheduler_task_id": task.id}
    await session.commit()
    await session.refresh(job)

    logger.info("job_created", job_id=str(job.id), seed_url_count=len(job.seed_urls), task_id=task.id)
    return JobCreateResponse(**_job_to_dict(job), scheduler_task_id=task.id)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _user=Depends(require_auth),
) -> JobListResponse:
    total = (await session.execute(select(func.count()).select_from(Job))).scalar_one()
    rows = (
        await session.execute(select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return JobListResponse(items=[JobResponse(**_job_to_dict(job)) for job in rows], total=total, limit=limit, offset=offset)


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job_status(job_id: UUID, session: DbSession, _user=Depends(require_auth)) -> JobDetailResponse:
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    pages = (
        await session.execute(select(Page).where(Page.job_id == job_id).order_by(Page.created_at.asc()))
    ).scalars().all()
    return JobDetailResponse(**_job_to_dict(job), pages=[_page_to_response(page) for page in pages])


@router.post("/{job_id}/cancel", response_model=JobCancelResponse)
async def cancel_job(job_id: UUID, session: DbSession, _user=Depends(require_auth)) -> JobCancelResponse:
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status in {JobStatus.completed, JobStatus.failed, JobStatus.cancelled}:
        return JobCancelResponse(id=job.id, status=job.status, message="Job is already terminal.")

    job.status = JobStatus.cancelled
    job.completed_at = datetime.now(timezone.utc)
    await session.execute(
        Page.__table__.update()
        .where(Page.job_id == job_id, Page.status.in_([PageStatus.queued, PageStatus.discovered]))
        .values(status=PageStatus.skipped)
    )
    await session.commit()
    logger.info("job_cancelled", job_id=str(job_id))
    return JobCancelResponse(id=job.id, status=job.status, message="Job cancellation recorded.")


def _job_to_dict(job: Job) -> dict[str, object]:
    return {
        "id": job.id,
        "name": job.name,
        "status": job.status,
        "seed_urls": job.seed_urls,
        "extraction_schema": job.extraction_schema,
        "crawl_config": job.crawl_config,
        "priority": job.priority,
        "max_pages": job.max_pages,
        "pages_discovered": job.pages_discovered,
        "pages_processed": job.pages_processed,
        "error_message": job.error_message,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _page_to_response(page: Page) -> PageSummaryResponse:
    return PageSummaryResponse(
        id=page.id,
        job_id=page.job_id,
        url=page.url,
        canonical_url=page.canonical_url,
        domain=page.domain,
        status=page.status,
        http_status=page.http_status,
        content_type=page.content_type,
        title=page.title,
        raw_html_sha256=page.raw_html_sha256,
        error_message=page.error_message,
        fetched_at=page.fetched_at,
        created_at=page.created_at,
        updated_at=page.updated_at,
    )
