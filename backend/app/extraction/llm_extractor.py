import json
from typing import Any

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings
from app.extraction.contracts import (
    ExtractedField,
    ExtractionContext,
    ExtractionField,
    ExtractionResult,
    ExtractionSchema,
    score_field_coverage,
)

logger = structlog.get_logger(__name__)


class LlmFieldOutput(BaseModel):
    value: Any | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str | None = None


class LlmExtractionOutput(BaseModel):
    fields: dict[str, LlmFieldOutput]


class LlmExtractor:
    extractor_name = "openai_structured_fallback"

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.openai_extraction_model
        self._client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def extract(self, context: ExtractionContext, schema: ExtractionSchema) -> ExtractionResult:
        if self._client is None:
            return ExtractionResult(
                extractor_name=self.extractor_name,
                schema_name=schema.name,
                confidence=0.0,
                errors=["OPENAI_API_KEY is not configured"],
            )

        response_schema = self._response_json_schema(schema)
        prompt = self._build_prompt(context, schema)

        try:
            response = await self._client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You extract structured data from web pages. Return only fields supported "
                            "by the provided JSON schema. Use null when a value is not present."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "webintel_extraction",
                        "schema": response_schema,
                        "strict": True,
                    }
                },
            )
        except Exception as exc:
            logger.warning("llm_extraction_failed", schema=schema.name, error=str(exc))
            return ExtractionResult(
                extractor_name=self.extractor_name,
                schema_name=schema.name,
                confidence=0.0,
                errors=[f"OpenAI extraction failed: {exc}"],
            )

        try:
            parsed = LlmExtractionOutput.model_validate_json(response.output_text)
        except (ValidationError, json.JSONDecodeError) as exc:
            return ExtractionResult(
                extractor_name=self.extractor_name,
                schema_name=schema.name,
                confidence=0.0,
                errors=[f"OpenAI response validation failed: {exc}"],
            )

        fields: dict[str, ExtractedField] = {}
        allowed_names = {field.name for field in schema.fields}
        for name, output in parsed.fields.items():
            if name not in allowed_names or output.value is None or output.value == "":
                continue
            fields[name] = ExtractedField(
                name=name,
                value=output.value,
                confidence=output.confidence,
                source="openai_json_schema",
                evidence=output.evidence,
            )

        return ExtractionResult(
            extractor_name=self.extractor_name,
            schema_name=schema.name,
            fields=fields,
            confidence=score_field_coverage(fields, schema.name),
            errors=[],
        )

    def _build_prompt(self, context: ExtractionContext, schema: ExtractionSchema) -> str:
        fields = [
            {
                "name": field.name,
                "description": field.description,
                "type": field.field_type.value,
                "required": field.required,
                "examples": field.examples,
            }
            for field in schema.fields
        ]
        return (
            f"URL: {context.url}\n"
            f"Page title: {context.title or ''}\n"
            f"Extraction schema: {json.dumps({'name': schema.name, 'fields': fields}, ensure_ascii=True)}\n\n"
            f"Page text:\n{context.text()}"
        )

    def _response_json_schema(self, schema: ExtractionSchema) -> dict[str, Any]:
        field_properties = {
            field.name: {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "value": self._json_type_for_field(field),
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence": {"type": ["string", "null"]},
                },
                "required": ["value", "confidence", "evidence"],
            }
            for field in schema.fields
        }
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "fields": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": field_properties,
                    "required": [field.name for field in schema.fields],
                }
            },
            "required": ["fields"],
        }

    def _json_type_for_field(self, field: ExtractionField) -> dict[str, Any]:
        if field.field_type.value in {"number", "money"}:
            return {"type": ["number", "string", "null"]}
        if field.field_type.value == "integer":
            return {"type": ["integer", "string", "null"]}
        if field.field_type.value == "boolean":
            return {"type": ["boolean", "null"]}
        return {"type": ["string", "null"]}
