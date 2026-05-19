from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.schemas.alerts import AlertAckResponse, AlertListResponse, AlertResponse
from app.security.dependencies import require_auth

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    session: DbSession,
    status_filter: AlertStatus | None = None,
    severity: AlertSeverity | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _user=Depends(require_auth),
) -> AlertListResponse:
    query = select(Alert)
    if status_filter is not None:
        query = query.where(Alert.status == status_filter)
    if severity is not None:
        query = query.where(Alert.severity == severity)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()
    rows = (await session.execute(query.order_by(Alert.created_at.desc()).limit(limit).offset(offset))).scalars().all()

    items = [
        AlertResponse(
            id=alert.id,
            severity=alert.severity,
            title=alert.title,
            status=alert.status,
            context=alert.context,
            detail=alert.detail,
            created_at=alert.created_at,
            updated_at=alert.updated_at,
        )
        for alert in rows
    ]
    return AlertListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/{alert_id}/ack", response_model=AlertAckResponse)
async def acknowledge_alert(alert_id: UUID, session: DbSession, _user=Depends(require_auth)) -> AlertAckResponse:
    result = await session.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if alert.status != AlertStatus.acknowledged:
        alert.status = AlertStatus.acknowledged
        await session.commit()
    return AlertAckResponse(id=alert.id, status=alert.status, message="Alert acknowledged.")
