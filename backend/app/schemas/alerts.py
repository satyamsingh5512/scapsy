from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.alert import AlertSeverity, AlertStatus


class AlertResponse(BaseModel):
    id: UUID
    severity: AlertSeverity
    title: str
    status: AlertStatus
    context: dict[str, Any]
    detail: str | None
    created_at: datetime
    updated_at: datetime


class AlertListResponse(BaseModel):
    items: list[AlertResponse]
    total: int
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class AlertAckResponse(BaseModel):
    id: UUID
    status: AlertStatus
    message: str
