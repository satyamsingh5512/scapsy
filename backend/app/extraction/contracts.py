from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings


class FieldType(str, Enum):
    text = "text"
    number = "number"
    integer = "integer"
    boolean = "boolean"
    url = "url"
    email = "email"
    phone = "phone"
    date = "date"
    money = "money"
    organization = "organization"
    person = "person"
    location = "location"


class ExtractionField(BaseModel):
    name: str
    description: str
    field_type: FieldType = FieldType.text
    required: bool = False
    examples: list[str] = Field(default_factory=list)
    regex: str | None = None
    question: str | None = None
    ner_labels: list[str] = Field(default_factory=list)


class ExtractionSchema(BaseModel):
    name: str = "default"
    description: str = "Structured data extraction schema"
    fields: list[ExtractionField]

    def required_field_names(self) -> set[str]:
        return {field.name for field in self.fields if field.required}


class ExtractedField(BaseModel):
    name: str
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
    evidence: str | None = None


class ExtractionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    extractor_name: str
    schema_name: str
    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    errors: list[str] = Field(default_factory=list)

    @property
    def data(self) -> dict[str, Any]:
        return {name: field.value for name, field in self.fields.items()}

    def merge(self, other: ExtractionResult) -> ExtractionResult:
        merged = self.model_copy(deep=True)
        for name, field in other.fields.items():
            current = merged.fields.get(name)
            if current is None or field.confidence > current.confidence:
                merged.fields[name] = field
        merged.errors.extend(other.errors)
        merged.confidence = score_field_coverage(merged.fields, merged.schema_name)
        return merged


class ExtractorProtocol(BaseModel):
    extractor_name: str


class ExtractionContext(BaseModel):
    url: str
    html: str
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def text(self) -> str:
        settings = get_settings()
        soup = BeautifulSoup(self.html, "html.parser")
        for tag in soup(["script", "style", "noscript", "template", "svg"]):
            tag.decompose()
        parts = [chunk.strip() for chunk in soup.get_text(separator="\n").splitlines() if chunk.strip()]
        text = "\n".join(parts)
        return text[: settings.extraction_max_text_chars]


ExtractionMode = Literal["regex", "spacy", "distilbert", "llm"]


def score_field_coverage(fields: dict[str, ExtractedField], schema_name: str) -> float:
    if not fields:
        return 0.0
    confidence_sum = sum(field.confidence for field in fields.values())
    base = confidence_sum / len(fields)
    # A named schema usually indicates a narrower extraction target, so complete high-confidence
    # field coverage should move through the fallback chain faster.
    schema_bonus = 0.03 if schema_name and schema_name != "default" else 0.0
    return min(1.0, round(base + schema_bonus, 4))
