import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedModel, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.extracted_data import ExtractedData
    from app.models.job import Job


class PageStatus(str, enum.Enum):
    discovered = "discovered"
    queued = "queued"
    fetched = "fetched"
    extracted = "extracted"
    failed = "failed"
    skipped = "skipped"


class Page(UUIDPrimaryKey, TimestampedModel, Base):
    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("job_id", "url", name="uq_pages_job_id_url"),
    )

    job_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[PageStatus] = mapped_column(
        Enum(PageStatus, name="page_status"),
        default=PageStatus.discovered,
        nullable=False,
        index=True,
    )
    http_status: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(Text)
    raw_html_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    page_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    job: Mapped["Job"] = relationship(back_populates="pages")
    extracted_data: Mapped[list["ExtractedData"]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
