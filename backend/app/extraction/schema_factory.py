from typing import Any

from app.extraction.contracts import ExtractionField, ExtractionSchema, FieldType


def schema_from_job_payload(payload: dict[str, Any], instruction: str | None = None) -> ExtractionSchema:
    if payload:
        try:
            return ExtractionSchema.model_validate(payload)
        except Exception:
            fields = payload.get("fields") if isinstance(payload, dict) else None
            if isinstance(fields, list) and fields:
                return ExtractionSchema(
                    name=str(payload.get("name") or "job_schema"),
                    description=str(payload.get("description") or instruction or "Job extraction schema"),
                    fields=[ExtractionField.model_validate(field) for field in fields],
                )
    return default_schema(instruction)


def default_schema(instruction: str | None = None) -> ExtractionSchema:
    description = instruction or "Extract the page title, summary, emails, phone numbers, and URLs."
    return ExtractionSchema(
        name="default_page_intelligence",
        description=description,
        fields=[
            ExtractionField(
                name="title",
                description="The page title or primary headline.",
                field_type=FieldType.text,
                required=False,
                question="What is the page title?",
            ),
            ExtractionField(
                name="email",
                description="A contact email address present on the page.",
                field_type=FieldType.email,
                required=False,
                question="What contact email is listed?",
            ),
            ExtractionField(
                name="phone",
                description="A contact phone number present on the page.",
                field_type=FieldType.phone,
                required=False,
                question="What phone number is listed?",
            ),
            ExtractionField(
                name="url",
                description="A relevant URL present on the page.",
                field_type=FieldType.url,
                required=False,
                question="What relevant URL is listed?",
            ),
        ],
    )
