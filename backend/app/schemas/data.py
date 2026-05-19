from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class ExtractedDataResponse(BaseModel):
    id: UUID
    page_id: UUID
    job_id: UUID
    url: HttpUrl | str
    extractor_name: str
    schema_name: str
    data: dict[str, Any]
    confidence: Decimal
    validation_errors: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class ExtractedDataListResponse(BaseModel):
    items: list[ExtractedDataResponse]
    total: int
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
