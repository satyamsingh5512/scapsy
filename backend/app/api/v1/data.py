from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.extracted_data import ExtractedData
from app.models.page import Page
from app.schemas.data import ExtractedDataListResponse, ExtractedDataResponse
from app.security.dependencies import require_auth

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("", response_model=ExtractedDataListResponse)
async def list_extracted_data(
    session: DbSession,
    job_id: UUID | None = None,
    schema_name: str | None = None,
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _user=Depends(require_auth),
) -> ExtractedDataListResponse:
    base_query = (
        select(ExtractedData, Page)
        .join(Page, ExtractedData.page_id == Page.id)
        .where(ExtractedData.confidence >= min_confidence)
    )
    base_query = _apply_filters(base_query, job_id, schema_name)

    count_query = select(func.count()).select_from(
        _apply_filters(
            select(ExtractedData.id)
            .join(Page, ExtractedData.page_id == Page.id)
            .where(ExtractedData.confidence >= min_confidence),
            job_id,
            schema_name,
        ).subquery()
    )
    total = (await session.execute(count_query)).scalar_one()
    rows = (
        await session.execute(
            base_query.order_by(ExtractedData.created_at.desc()).limit(limit).offset(offset)
        )
    ).all()

    items = [
        ExtractedDataResponse(
            id=record.id,
            page_id=record.page_id,
            job_id=page.job_id,
            url=page.url,
            extractor_name=record.extractor_name,
            schema_name=record.schema_name,
            data=record.data,
            confidence=record.confidence,
            validation_errors=record.validation_errors,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
        for record, page in rows
    ]
    return ExtractedDataListResponse(items=items, total=total, limit=limit, offset=offset)


def _apply_filters(
    query: Select[tuple[ExtractedData, Page]] | Select[tuple[UUID]],
    job_id: UUID | None,
    schema_name: str | None,
) -> Select[tuple[ExtractedData, Page]] | Select[tuple[UUID]]:
    if job_id is not None:
        query = query.where(Page.job_id == job_id)
    if schema_name is not None:
        query = query.where(ExtractedData.schema_name == schema_name)
    return query
