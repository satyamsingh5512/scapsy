import json
import re
from typing import Any

import structlog
from fastapi import APIRouter
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config import get_settings
from app.extraction.contracts import ExtractionField, ExtractionSchema, FieldType
from app.schemas.ai_engine import AiSchemaRequest, AiSchemaResponse

router = APIRouter()
logger = structlog.get_logger(__name__)


class AiFieldSpec(BaseModel):
    name: str
    description: str
    field_type: FieldType
    required: bool = False
    examples: list[str] = Field(default_factory=list)


class AiSchemaSpec(BaseModel):
    fields: list[AiFieldSpec]


@router.post("/schemas", response_model=AiSchemaResponse)
async def generate_extraction_schema(payload: AiSchemaRequest) -> AiSchemaResponse:
    settings = get_settings()
    if settings.openai_api_key:
        schema, raw = await _generate_with_openai(payload)
        return AiSchemaResponse(
            extraction_schema=schema,
            pydantic_model_code=_schema_to_pydantic_code(schema),
            provider="openai",
            raw=raw,
        )

    schema = _generate_with_heuristics(payload)
    return AiSchemaResponse(
        extraction_schema=schema,
        pydantic_model_code=_schema_to_pydantic_code(schema),
        provider="heuristic",
        raw={"reason": "OPENAI_API_KEY is not configured; used deterministic local parser."},
    )


async def _generate_with_openai(payload: AiSchemaRequest) -> tuple[ExtractionSchema, dict[str, Any]]:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    json_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "fields": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "field_type": {"type": "string", "enum": [field_type.value for field_type in FieldType]},
                        "required": {"type": "boolean"},
                        "examples": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name", "description", "field_type", "required", "examples"],
                },
            }
        },
        "required": ["fields"],
    }
    response = await client.responses.create(
        model=settings.openai_extraction_model,
        input=[
            {
                "role": "system",
                "content": (
                    "Convert natural-language web scraping instructions into a compact extraction schema. "
                    "Use snake_case field names and choose the closest field_type."
                ),
            },
            {"role": "user", "content": payload.instruction},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "webintel_schema_builder",
                "schema": json_schema,
                "strict": True,
            }
        },
    )
    try:
        parsed = AiSchemaSpec.model_validate_json(response.output_text)
    except (ValidationError, json.JSONDecodeError) as exc:
        logger.warning("ai_schema_validation_failed", error=str(exc), output=response.output_text)
        raise

    schema = ExtractionSchema(
        name=payload.schema_name,
        description=payload.instruction,
        fields=[ExtractionField(**field.model_dump()) for field in parsed.fields],
    )
    return schema, parsed.model_dump(mode="json")


def _generate_with_heuristics(payload: AiSchemaRequest) -> ExtractionSchema:
    instruction = payload.instruction.lower()
    candidates: list[ExtractionField] = []
    mapping = {
        "email": FieldType.email,
        "phone": FieldType.phone,
        "price": FieldType.money,
        "cost": FieldType.money,
        "date": FieldType.date,
        "url": FieldType.url,
        "link": FieldType.url,
        "company": FieldType.organization,
        "organization": FieldType.organization,
        "person": FieldType.person,
        "name": FieldType.text,
        "address": FieldType.location,
        "location": FieldType.location,
        "title": FieldType.text,
        "description": FieldType.text,
    }
    for keyword, field_type in mapping.items():
        if keyword in instruction:
            name = _to_snake_case(keyword if keyword != "cost" else "price")
            if name not in {field.name for field in candidates}:
                candidates.append(
                    ExtractionField(
                        name=name,
                        description=f"Extract the {keyword} requested by the user.",
                        field_type=field_type,
                        required=True,
                        question=f"What is the {keyword}?",
                    )
                )

    quoted = re.findall(r"['\"]([^'\"]{2,80})['\"]", payload.instruction)
    for phrase in quoted:
        name = _to_snake_case(phrase)
        if name and name not in {field.name for field in candidates}:
            candidates.append(
                ExtractionField(
                    name=name,
                    description=f"Extract {phrase}.",
                    field_type=FieldType.text,
                    required=False,
                    question=f"What is {phrase}?",
                )
            )

    if not candidates:
        candidates = [
            ExtractionField(
                name="summary",
                description="A concise structured summary of the requested page intelligence.",
                field_type=FieldType.text,
                required=True,
                question="What is the most important information requested by the user?",
            )
        ]

    return ExtractionSchema(name=payload.schema_name, description=payload.instruction, fields=candidates)


def _schema_to_pydantic_code(schema: ExtractionSchema) -> str:
    type_map = {
        FieldType.number: "float",
        FieldType.integer: "int",
        FieldType.boolean: "bool",
        FieldType.money: "str",
    }
    lines = ["from pydantic import BaseModel, Field", "", f"class {_to_pascal_case(schema.name)}(BaseModel):"]
    for field in schema.fields:
        python_type = type_map.get(field.field_type, "str")
        if not field.required:
            python_type = f"{python_type} | None"
            assignment = f"Field(default=None, description={field.description!r})"
        else:
            assignment = f"Field(description={field.description!r})"
        lines.append(f"    {field.name}: {python_type} = {assignment}")
    return "\n".join(lines)


def _to_snake_case(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    cleaned = re.sub(r"_+", "_", cleaned)
    if cleaned and cleaned[0].isdigit():
        cleaned = f"field_{cleaned}"
    return cleaned[:64] or "field"


def _to_pascal_case(value: str) -> str:
    return "".join(part.capitalize() for part in _to_snake_case(value).split("_")) or "GeneratedSchema"
