from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedModel, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.page import Page


class ExtractedData(UUIDPrimaryKey, TimestampedModel, Base):
    __tablename__ = "extracted_data"

    page_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extractor_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    schema_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    source_text: Mapped[str | None] = mapped_column(Text)
    validation_errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    page: Mapped["Page"] = relationship(back_populates="extracted_data")
