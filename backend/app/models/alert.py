import enum
from typing import Any

from sqlalchemy import Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampedModel, UUIDPrimaryKey


class AlertSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class AlertStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class Alert(UUIDPrimaryKey, TimestampedModel, Base):
    __tablename__ = "alerts"

    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status"),
        nullable=False,
        default=AlertStatus.open,
        index=True,
    )
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    detail: Mapped[str | None] = mapped_column(Text)
