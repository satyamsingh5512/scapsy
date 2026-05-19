from collections import Counter
from functools import cached_property
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from spacy.language import Language
else:
    Language = Any

from app.config import get_settings
from app.extraction.contracts import (
    ExtractedField,
    ExtractionContext,
    ExtractionField,
    ExtractionResult,
    ExtractionSchema,
    FieldType,
    score_field_coverage,
)

logger = structlog.get_logger(__name__)


class SpacyNerExtractor:
    extractor_name = "spacy_ner"

    DEFAULT_LABELS_BY_TYPE = {
        FieldType.person: ["PERSON"],
        FieldType.organization: ["ORG"],
        FieldType.location: ["GPE", "LOC", "FAC"],
        FieldType.date: ["DATE"],
        FieldType.money: ["MONEY"],
    }

    @cached_property
    def nlp(self) -> Language:
        settings = get_settings()
        try:
            import spacy

            return spacy.load(settings.spacy_model)
        except ImportError as exc:
            raise RuntimeError("spaCy is not installed. Install optional dependencies: pip install -e backend[ml]") from exc
        except OSError as exc:
            logger.warning("spacy_model_missing", model=settings.spacy_model, error=str(exc))
            raise RuntimeError(
                f"spaCy model '{settings.spacy_model}' is not installed. "
                f"Install it with: python -m spacy download {settings.spacy_model}"
            ) from exc

    async def extract(self, context: ExtractionContext, schema: ExtractionSchema) -> ExtractionResult:
        fields: dict[str, ExtractedField] = {}
        errors: list[str] = []
        try:
            doc = self.nlp(context.text())
        except RuntimeError as exc:
            return ExtractionResult(
                extractor_name=self.extractor_name,
                schema_name=schema.name,
                confidence=0.0,
                errors=[str(exc)],
            )

        entities_by_label: dict[str, list[str]] = {}
        for entity in doc.ents:
            normalized = " ".join(entity.text.split())
            if normalized:
                entities_by_label.setdefault(entity.label_, []).append(normalized)

        for field in schema.fields:
            labels = field.ner_labels or self.DEFAULT_LABELS_BY_TYPE.get(field.field_type, [])
            if not labels:
                continue
            value = self._best_entity(labels, entities_by_label)
            if value is None:
                continue
            fields[field.name] = ExtractedField(
                name=field.name,
                value=value,
                confidence=0.78 if field.ner_labels else 0.74,
                source="spacy_ner",
                evidence=", ".join(labels),
            )

        if errors:
            logger.warning("spacy_extraction_errors", errors=errors)

        return ExtractionResult(
            extractor_name=self.extractor_name,
            schema_name=schema.name,
            fields=fields,
            confidence=score_field_coverage(fields, schema.name),
            errors=errors,
        )

    def _best_entity(self, labels: list[str], entities_by_label: dict[str, list[str]]) -> str | None:
        candidates: list[str] = []
        for label in labels:
            candidates.extend(entities_by_label.get(label, []))
        if not candidates:
            return None
        return Counter(candidates).most_common(1)[0][0]
