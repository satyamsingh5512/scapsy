from typing import Any

from pydantic import BaseModel, Field

from app.extraction.contracts import ExtractionSchema


class AiSchemaRequest(BaseModel):
    instruction: str = Field(min_length=8, max_length=4_000)
    schema_name: str = Field(default="ai_generated_schema", min_length=1, max_length=120)


class AiSchemaResponse(BaseModel):
    extraction_schema: ExtractionSchema
    pydantic_model_code: str
    provider: str
    raw: dict[str, Any] = Field(default_factory=dict)
