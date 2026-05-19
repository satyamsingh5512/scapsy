from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extracted_data import ExtractedData
from app.storage.change_detection import diff_records


@dataclass(frozen=True)
class StorageResult:
    record_id: UUID
    change: dict[str, Any]


async def write_record(
    session: AsyncSession,
    *,
    page_id: UUID,
    data: dict[str, Any],
    confidence: float,
    extractor_name: str,
    schema_name: str,
    previous_data: dict[str, Any] | None = None,
) -> StorageResult:
    record = ExtractedData(
        page_id=page_id,
        data=data,
        confidence=Decimal(str(confidence)).quantize(Decimal("0.0001")),
        extractor_name=extractor_name,
        schema_name=schema_name,
        validation_errors=[],
    )
    session.add(record)
    await session.flush()
    change = diff_records(previous_data, data)
    return StorageResult(record_id=record.id, change=change)
