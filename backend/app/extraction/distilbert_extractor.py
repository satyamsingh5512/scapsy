from functools import cached_property
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from transformers.pipelines import Pipeline
else:
    Pipeline = Any

from app.config import get_settings
from app.extraction.contracts import (
    ExtractedField,
    ExtractionContext,
    ExtractionResult,
    ExtractionSchema,
    score_field_coverage,
)

logger = structlog.get_logger(__name__)


class DistilBertExtractor:
    extractor_name = "distilbert_qa"

    @cached_property
    def qa_pipeline(self) -> Pipeline:
        settings = get_settings()
        try:
            from transformers import pipeline

            return pipeline(
                task="question-answering",
                model=settings.hf_qa_model,
                tokenizer=settings.hf_qa_model,
            )
        except ImportError as exc:
            raise RuntimeError("Transformers is not installed. Install optional dependencies: pip install -e backend[ml]") from exc
        except Exception as exc:
            logger.warning("hf_model_load_failed", model=settings.hf_qa_model, error=str(exc))
            raise RuntimeError(f"HuggingFace QA model '{settings.hf_qa_model}' could not be loaded: {exc}") from exc

    async def extract(self, context: ExtractionContext, schema: ExtractionSchema) -> ExtractionResult:
        page_text = context.text()
        if not page_text:
            return ExtractionResult(
                extractor_name=self.extractor_name,
                schema_name=schema.name,
                confidence=0.0,
                errors=["No page text available for transformer extraction"],
            )

        fields: dict[str, ExtractedField] = {}
        errors: list[str] = []

        try:
            qa = self.qa_pipeline
        except RuntimeError as exc:
            return ExtractionResult(
                extractor_name=self.extractor_name,
                schema_name=schema.name,
                confidence=0.0,
                errors=[str(exc)],
            )

        for field in schema.fields:
            question = field.question or f"What is the {field.description or field.name}?"
            try:
                answer = qa(question=question, context=page_text)
            except Exception as exc:
                errors.append(f"{field.name}: transformer inference failed: {exc}")
                continue

            value = str(answer.get("answer", "")).strip()
            score = float(answer.get("score", 0.0))
            if not value or score < 0.18:
                continue

            fields[field.name] = ExtractedField(
                name=field.name,
                value=value,
                confidence=min(0.92, round(score, 4)),
                source="distilbert_qa",
                evidence=question,
            )

        return ExtractionResult(
            extractor_name=self.extractor_name,
            schema_name=schema.name,
            fields=fields,
            confidence=score_field_coverage(fields, schema.name),
            errors=errors,
        )
